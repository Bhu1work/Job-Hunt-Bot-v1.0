"""
Phase 1 — Job Scraper with H1B Filter

Sources:
  1. MyVisaJobs.com  → authoritative list of H1B-sponsoring companies (DOL LCA filings)
  2. LinkedIn        → job listings cross-referenced against the H1B company list
  3. Indeed          → additional job listings

Run:
    python phase1_scraper.py --field "Software Engineer" --location "United States"
"""

import argparse
import logging
import time
import re
from urllib.parse import urlencode, urljoin, quote_plus

import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from tenacity import retry, stop_after_attempt, wait_exponential

import config
from database import init_db, upsert_company, upsert_job, get_h1b_companies, log_event

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)
ua = UserAgent()


# ── HTTP helpers ──────────────────────────────────────────────────────────────

def _headers() -> dict:
    return {
        "User-Agent": ua.random,
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _get(url: str, params: dict | None = None, timeout: int = 15) -> BeautifulSoup:
    resp = requests.get(url, params=params, headers=_headers(), timeout=timeout)
    resp.raise_for_status()
    time.sleep(1.5)  # polite crawl delay
    return BeautifulSoup(resp.text, "lxml")


# ── MyVisaJobs scraper ────────────────────────────────────────────────────────

MYVISAJOBS_BASE = "https://www.myvisajobs.com"


def scrape_myvisajobs(field: str, pages: int = 10) -> list[dict]:
    """
    Scrape H1B sponsor companies from MyVisaJobs.com LCA filing data.
    Returns list of {name, lca_count, domain}.
    """
    companies = []
    keyword = quote_plus(field)

    for page in range(1, pages + 1):
        url = f"{MYVISAJOBS_BASE}/Search-H1B-LCA.aspx"
        params = {"Keyword": keyword, "Page": page}
        logger.info("MyVisaJobs page %d — %s", page, field)

        try:
            soup = _get(url, params=params)
        except Exception as exc:
            logger.warning("MyVisaJobs page %d failed: %s", page, exc)
            break

        rows = soup.select("table.tbl tr")
        if not rows:
            break

        for row in rows[1:]:  # skip header
            cols = row.find_all("td")
            if len(cols) < 3:
                continue
            name_tag = cols[0].find("a")
            if not name_tag:
                continue

            name = name_tag.get_text(strip=True)
            try:
                lca_count = int(re.sub(r"[^\d]", "", cols[1].get_text()))
            except (ValueError, IndexError):
                lca_count = 0

            href = name_tag.get("href", "")
            company_url = urljoin(MYVISAJOBS_BASE, href)

            companies.append({
                "name": name,
                "lca_count": lca_count,
                "company_url": company_url,
                "domain": "",
            })

        if not rows[1:]:
            break

    logger.info("MyVisaJobs: found %d companies for '%s'", len(companies), field)
    return companies


def save_h1b_companies(companies: list[dict]) -> int:
    """Persist H1B companies to DB, return count saved."""
    saved = 0
    for c in companies:
        try:
            upsert_company(
                name=c["name"],
                h1b_confirmed=True,
                h1b_source="myvisajobs",
                lca_count=c.get("lca_count", 0),
                domain=c.get("domain", ""),
            )
            saved += 1
        except Exception as exc:
            logger.warning("Could not save company %s: %s", c["name"], exc)
    logger.info("Saved %d H1B companies to DB", saved)
    return saved


# ── LinkedIn scraper ──────────────────────────────────────────────────────────

LINKEDIN_JOBS_BASE = "https://www.linkedin.com/jobs/search"


def scrape_linkedin(keyword: str, location: str, pages: int = 5,
                    hours_fresh: int | None = None,
                    mid_level_only: bool = False) -> list[dict]:
    """
    Scrape LinkedIn public job search (no login required for listing pages).

    hours_fresh     : only return jobs posted within N hours (e.g. 4)
                      LinkedIn param: f_TPR=r<seconds>
    mid_level_only  : filter to Associate + Mid-Senior level (f_E=3,4)

    Returns list of raw job dicts.
    """
    jobs = []

    for page in range(pages):
        params = {
            "keywords": keyword,
            "location": location,
            "start": page * 25,
        }

        # Freshness filter — e.g. 4 hours = 14400 seconds
        if hours_fresh:
            params["f_TPR"] = f"r{hours_fresh * 3600}"

        # Experience level: 3 = Associate, 4 = Mid-Senior level
        if mid_level_only:
            params["f_E"] = "3,4"

        logger.info("LinkedIn page %d — '%s' in '%s' (fresh=%sh mid=%s)",
                    page + 1, keyword, location,
                    hours_fresh or "any", mid_level_only)

        try:
            soup = _get(LINKEDIN_JOBS_BASE, params=params)
        except Exception as exc:
            logger.warning("LinkedIn page %d failed: %s", page + 1, exc)
            break

        cards = soup.select("div.base-card")
        if not cards:
            logger.info("LinkedIn: no more cards on page %d", page + 1)
            break

        for card in cards:
            title_tag = card.select_one("h3.base-search-card__title")
            company_tag = card.select_one("h4.base-search-card__subtitle a")
            location_tag = card.select_one("span.job-search-card__location")
            link_tag = card.select_one("a.base-card__full-link")

            if not (title_tag and company_tag and link_tag):
                continue

            jobs.append({
                "role": title_tag.get_text(strip=True),
                "company": company_tag.get_text(strip=True),
                "location": location_tag.get_text(strip=True) if location_tag else "",
                "jd_url": link_tag["href"].split("?")[0],
                "source": "linkedin",
                "description": "",
            })

    logger.info("LinkedIn: found %d raw jobs", len(jobs))
    return jobs


def fetch_linkedin_description(jd_url: str) -> str:
    """Fetch and return the job description text from a LinkedIn job page."""
    try:
        soup = _get(jd_url)
        desc_tag = soup.select_one("div.show-more-less-html__markup")
        return desc_tag.get_text(separator="\n", strip=True) if desc_tag else ""
    except Exception as exc:
        logger.warning("Could not fetch LinkedIn JD %s: %s", jd_url, exc)
        return ""


# ── Indeed scraper ────────────────────────────────────────────────────────────

INDEED_BASE = "https://www.indeed.com/jobs"


def scrape_indeed(keyword: str, location: str, pages: int = 5,
                  hours_fresh: int | None = None,
                  mid_level_only: bool = False) -> list[dict]:
    """
    Scrape Indeed job listings.

    hours_fresh     : only jobs posted within N hours — maps to fromage (days, min 1)
    mid_level_only  : append 'mid level' to keyword search
    """
    jobs = []

    # Indeed's `fromage` param is in days (minimum 1). For ≤24 h we use fromage=1.
    fromage = None
    if hours_fresh:
        fromage = max(1, hours_fresh // 24 or 1)

    search_keyword = f"{keyword} mid level" if mid_level_only else keyword

    for page in range(pages):
        params = {
            "q": search_keyword,
            "l": location,
            "start": page * 10,
            "sort": "date",
        }
        if fromage:
            params["fromage"] = str(fromage)

        logger.info("Indeed page %d — '%s' in '%s' (fromage=%s)",
                    page + 1, search_keyword, location, fromage or "any")

        try:
            soup = _get(INDEED_BASE, params=params)
        except Exception as exc:
            logger.warning("Indeed page %d failed: %s", page + 1, exc)
            break

        cards = soup.select("div.job_seen_beacon")
        if not cards:
            logger.info("Indeed: no more cards on page %d", page + 1)
            break

        for card in cards:
            title_tag = card.select_one("h2.jobTitle a")
            company_tag = card.select_one("span.companyName")
            location_tag = card.select_one("div.companyLocation")

            if not title_tag:
                continue

            job_id = title_tag.get("data-jk") or title_tag.get("id", "")
            jd_url = f"https://www.indeed.com/viewjob?jk={job_id}" if job_id else ""

            jobs.append({
                "role": title_tag.get_text(strip=True),
                "company": company_tag.get_text(strip=True) if company_tag else "",
                "location": location_tag.get_text(strip=True) if location_tag else "",
                "jd_url": jd_url,
                "source": "indeed",
                "description": "",
            })

    logger.info("Indeed: found %d raw jobs", len(jobs))
    return jobs


# ── H1B filter ────────────────────────────────────────────────────────────────

def build_h1b_set() -> set[str]:
    """Return a lowercase set of known H1B-sponsoring company names."""
    companies = get_h1b_companies()
    return {c["name"].lower() for c in companies}


def _normalize(name: str) -> str:
    """Strip legal suffixes and lowercase for fuzzy matching."""
    name = name.lower()
    for suffix in (" inc", " llc", " ltd", " corp", " co.", " corporation", ".", ","):
        name = name.replace(suffix, "")
    return name.strip()


def filter_h1b_jobs(jobs: list[dict], h1b_set: set[str]) -> list[dict]:
    """
    Mark jobs where the company is in the H1B sponsor set.
    Also keeps them all so you can review unmatched ones.
    """
    normalized_h1b = {_normalize(n) for n in h1b_set}
    for job in jobs:
        norm_company = _normalize(job["company"])
        job["h1b_confirmed"] = any(
            norm_company in h or h in norm_company
            for h in normalized_h1b
        )
    return jobs


# ── Save jobs pipeline ────────────────────────────────────────────────────────

def save_jobs(jobs: list[dict], fetch_descriptions: bool = False) -> int:
    saved = 0
    for job in jobs:
        if not job.get("jd_url"):
            continue

        desc = job.get("description", "")
        if fetch_descriptions and not desc and job["source"] == "linkedin":
            desc = fetch_linkedin_description(job["jd_url"])
            job["description"] = desc

        try:
            upsert_job(
                company=job["company"],
                role=job["role"],
                jd_url=job["jd_url"],
                source=job["source"],
                location=job.get("location", ""),
                description=desc,
                h1b_confirmed=job.get("h1b_confirmed", False),
            )
            saved += 1
        except Exception as exc:
            logger.warning("Could not save job %s: %s", job.get("jd_url"), exc)

    logger.info("Saved %d jobs to DB", saved)
    return saved


# ── Main ──────────────────────────────────────────────────────────────────────

def run(field: str, location: str, pages: int = 5,
        fetch_descriptions: bool = False,
        hours_fresh: int | None = None,
        mid_level_only: bool = False) -> None:

    hours_fresh    = hours_fresh    or config.SCRAPE_HOURS_FRESH or None
    mid_level_only = mid_level_only or config.SCRAPE_MID_LEVEL_ONLY

    init_db()
    logger.info(
        "Scrape config — fresh: %sh  mid-level: %s  pages: %d",
        hours_fresh or "any", mid_level_only, pages,
    )

    # Step 1: Build / refresh H1B company list from MyVisaJobs
    logger.info("=== Step 1: Scraping MyVisaJobs for H1B sponsors ===")
    mv_companies = scrape_myvisajobs(field, pages=pages)
    save_h1b_companies(mv_companies)
    h1b_set = build_h1b_set()
    logger.info("H1B company set has %d entries", len(h1b_set))

    all_jobs: list[dict] = []

    # Step 2: LinkedIn
    logger.info("=== Step 2: LinkedIn scrape ===")
    for kw in config.SEARCH_KEYWORDS:
        lj = scrape_linkedin(kw, location, pages=pages,
                             hours_fresh=hours_fresh,
                             mid_level_only=mid_level_only)
        all_jobs.extend(lj)

    # Step 3: Indeed
    logger.info("=== Step 3: Indeed scrape ===")
    for kw in config.SEARCH_KEYWORDS:
        ij = scrape_indeed(kw, location, pages=pages,
                           hours_fresh=hours_fresh,
                           mid_level_only=mid_level_only)
        all_jobs.extend(ij)

    # Step 4: Filter
    logger.info("=== Step 4: Filtering for H1B sponsors ===")
    all_jobs = filter_h1b_jobs(all_jobs, h1b_set)
    h1b_jobs = [j for j in all_jobs if j["h1b_confirmed"]]
    logger.info("%d / %d jobs matched H1B sponsors", len(h1b_jobs), len(all_jobs))

    # Step 5: Persist
    logger.info("=== Step 5: Saving to DB ===")
    total_saved = save_jobs(all_jobs, fetch_descriptions=fetch_descriptions)

    log_event(
        "scrape_complete",
        f"field={field} location={location} total={len(all_jobs)} h1b={len(h1b_jobs)} saved={total_saved}",
    )
    logger.info("Done. %d jobs saved (%d H1B-confirmed).", total_saved, len(h1b_jobs))

    # ── Slack notification ────────────────────────────────────────────────────
    if config.SLACK_BOT_TOKEN and config.SLACK_CHANNEL_ID and total_saved > 0:
        try:
            from ats_scorer import score_all_pending_jobs
            from slack_bot import notify_new_jobs
            top = score_all_pending_jobs(threshold=0)[:5]   # top 5 regardless of threshold
            notify_new_jobs(total_saved, top)
            logger.info("Slack notification sent (%d new jobs)", total_saved)
        except Exception as exc:
            logger.warning("Slack notify after scrape failed: %s", exc)
    elif total_saved == 0:
        if config.SLACK_BOT_TOKEN and config.SLACK_CHANNEL_ID:
            try:
                from slack_bot import send_message
                send_message(
                    f":mag: Scrape complete — no new jobs found this run.\n"
                    f"(H1B-confirmed in DB: {len(h1b_jobs)} total)"
                )
            except Exception as exc:
                logger.warning("Slack notify (no new jobs) failed: %s", exc)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Phase 1 — Job scraper with H1B filter")
    parser.add_argument("--field", default=config.YOUR_FIELD, help="Job title / field")
    parser.add_argument("--location", default="United States", help="Location string")
    parser.add_argument("--pages", type=int, default=5, help="Pages per source")
    parser.add_argument("--fetch-descriptions", action="store_true",
                        help="Also fetch full JD text (slower)")
    parser.add_argument("--hours-fresh", type=int, default=None,
                        help="Only jobs posted within N hours (default: from config)")
    parser.add_argument("--all-levels", action="store_true",
                        help="Include all seniority levels (default: mid-level only)")
    args = parser.parse_args()

    run(
        field=args.field,
        location=args.location,
        pages=args.pages,
        fetch_descriptions=args.fetch_descriptions,
        hours_fresh=args.hours_fresh,
        mid_level_only=not args.all_levels,
    )
