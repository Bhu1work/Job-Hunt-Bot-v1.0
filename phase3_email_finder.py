"""
Phase 3 — Email Finder (Hunter.io primary, Apollo.io fallback)

For each H1B-confirmed job in the DB:
  1. Looks up company domain
  2. Hunter.io: finds HR / hiring manager emails
  3. Apollo.io fallback if Hunter misses
  4. Stores contacts in DB
  5. Flags companies with no email found for manual review
  6. Generates cold emails via Claude (calls phase2 helper)

Run:
    python phase3_email_finder.py [--job-id 42] [--review-gaps]
"""

import argparse
import logging
import time
from urllib.parse import urlparse

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

import config
from database import (
    init_db,
    get_pending_jobs,
    get_job,
    save_contact,
    save_outreach,
    get_contacts_for_job,
    log_event,
)
from phase2_resume_tailor import generate_cold_email, load_master_resume

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)

# Contact types we want to find, in priority order
TARGET_TITLES = {
    "hr": ["hr", "human resources", "talent acquisition", "recruiter", "people ops"],
    "hiring_manager": ["engineering manager", "vp engineering", "director of engineering",
                       "head of engineering", "cto", "vp of data", "director of data"],
    "team_lead": ["senior software engineer", "staff engineer", "principal engineer",
                  "tech lead", "senior data scientist"],
}


# ── Domain resolver ───────────────────────────────────────────────────────────

def _extract_domain(url: str) -> str:
    """Pull hostname from URL, stripping www."""
    parsed = urlparse(url if "://" in url else "https://" + url)
    host = parsed.hostname or ""
    return host.replace("www.", "")


def guess_domain(company_name: str) -> str:
    """
    Attempt to guess company domain by querying Hunter.io's domain-search
    autocomplete, or fallback to a simple heuristic.
    """
    if not config.HUNTER_API_KEY:
        return _heuristic_domain(company_name)

    try:
        resp = requests.get(
            "https://api.hunter.io/v2/domain-search",
            params={
                "company": company_name,
                "api_key": config.HUNTER_API_KEY,
                "limit": 1,
            },
            timeout=10,
        )
        data = resp.json().get("data", {})
        domain = data.get("domain", "")
        if domain:
            return domain
    except Exception as exc:
        logger.debug("Hunter domain lookup failed for %s: %s", company_name, exc)

    return _heuristic_domain(company_name)


def _heuristic_domain(company_name: str) -> str:
    slug = (
        company_name.lower()
        .replace(" inc", "").replace(" llc", "").replace(" ltd", "")
        .replace(",", "").replace(".", "").replace(" ", "")
    )
    return f"{slug}.com"


# ── Hunter.io ─────────────────────────────────────────────────────────────────

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=8))
def hunter_search(domain: str, company: str) -> list[dict]:
    """
    Use Hunter.io domain-search API to find employee emails.
    Returns list of contact dicts: {name, email, title, contact_type}.
    """
    if not config.HUNTER_API_KEY:
        logger.warning("HUNTER_API_KEY not set — skipping Hunter.io")
        return []

    resp = requests.get(
        "https://api.hunter.io/v2/domain-search",
        params={
            "domain": domain,
            "company": company,
            "api_key": config.HUNTER_API_KEY,
            "limit": 10,
        },
        timeout=15,
    )

    # Hard stops for auth / credit failures
    if resp.status_code == 401:
        raise SystemExit(
            "\n" + "─" * 60 + "\n"
            "  Hunter.io API key is invalid.\n"
            "  Check HUNTER_API_KEY in your .env file.\n"
            "  Get your key at: https://hunter.io/api-keys\n"
            + "─" * 60
        )
    if resp.status_code == 402:
        raise SystemExit(
            "\n" + "─" * 60 + "\n"
            "  Hunter.io credits exhausted — monthly quota reached.\n"
            "  Upgrade at: https://hunter.io/users/billing\n"
            "  Tip: Apollo.io fallback will be used automatically next month.\n"
            + "─" * 60
        )
    if resp.status_code == 429:
        logger.warning("Hunter.io rate limit hit — sleeping 30s")
        time.sleep(30)
        return hunter_search(domain, company)   # retry once

    data = resp.json().get("data", {})
    emails = data.get("emails", [])

    contacts = []
    for entry in emails:
        full_name = f"{entry.get('first_name', '')} {entry.get('last_name', '')}".strip()
        title = entry.get("position", "") or ""
        email = entry.get("value", "")
        if not email:
            continue
        contacts.append({
            "name": full_name,
            "email": email,
            "title": title,
            "contact_type": _classify_title(title),
            "source": "hunter",
        })

    logger.info("Hunter.io: %d contacts for %s", len(contacts), domain)
    return contacts


# ── Apollo.io fallback ────────────────────────────────────────────────────────

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=8))
def apollo_search(company: str, domain: str) -> list[dict]:
    """
    Use Apollo.io People Search API as a fallback.
    Returns list of contact dicts.
    """
    if not config.APOLLO_API_KEY:
        logger.warning("APOLLO_API_KEY not set — skipping Apollo.io")
        return []

    headers = {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
        "X-Api-Key": config.APOLLO_API_KEY,
    }

    # Flatten all target title keywords
    title_keywords = [kw for kws in TARGET_TITLES.values() for kw in kws]

    payload = {
        "q_organization_domains": domain,
        "page": 1,
        "per_page": 10,
        "person_titles": title_keywords[:5],  # Apollo limits per request
        "contact_email_status": ["verified", "guessed"],
    }

    try:
        resp = requests.post(
            "https://api.apollo.io/v1/mixed_people/search",
            json=payload,
            headers=headers,
            timeout=15,
        )
    except Exception as exc:
        logger.warning("Apollo search failed for %s: %s", company, exc)
        return []

    if resp.status_code == 401:
        raise SystemExit(
            "\n" + "─" * 60 + "\n"
            "  Apollo.io API key is invalid.\n"
            "  Check APOLLO_API_KEY in your .env file.\n"
            "  Get your key at: https://app.apollo.io/#/settings/integrations/api\n"
            + "─" * 60
        )
    if resp.status_code == 422:
        # Apollo returns 422 for quota exhaustion on free tier
        logger.warning("Apollo.io quota reached for %s — skipping (not a hard stop)", company)
        return []
    if resp.status_code not in (200, 201):
        logger.warning("Apollo unexpected status %d for %s", resp.status_code, company)
        return []

    try:
        people = resp.json().get("people", [])
    except Exception as exc:
        logger.warning("Apollo JSON parse failed for %s: %s", company, exc)
        return []

    contacts = []
    for person in people:
        email = person.get("email", "")
        if not email or email == "email_not_unlocked@domain.com":
            continue
        title = person.get("title", "") or ""
        contacts.append({
            "name": person.get("name", ""),
            "email": email,
            "title": title,
            "contact_type": _classify_title(title),
            "source": "apollo",
        })

    logger.info("Apollo.io: %d contacts for %s", len(contacts), company)
    return contacts


# ── Title classifier ──────────────────────────────────────────────────────────

def _classify_title(title: str) -> str:
    title_lower = title.lower()
    for contact_type, keywords in TARGET_TITLES.items():
        if any(kw in title_lower for kw in keywords):
            return contact_type
    return "other"


# ── Per-job email finding ─────────────────────────────────────────────────────

def find_contacts_for_job(job: dict) -> list[dict]:
    """
    Find HR/HM/team lead contacts for a job's company.
    Returns list of contacts saved to DB.
    """
    company = job["company"]
    job_id = job["id"]

    # Check if already found
    existing = get_contacts_for_job(job_id)
    if existing:
        logger.info("Job %d (%s) already has %d contacts — skipping", job_id, company, len(existing))
        return existing

    domain = guess_domain(company)
    logger.info("Looking up contacts for %s (domain: %s)", company, domain)

    # Primary: Hunter.io
    contacts = hunter_search(domain, company)
    time.sleep(1)

    # Fallback: Apollo
    if len(contacts) < 2:
        apollo_contacts = apollo_search(company, domain)
        # Deduplicate by email
        existing_emails = {c["email"] for c in contacts}
        for ac in apollo_contacts:
            if ac["email"] not in existing_emails:
                contacts.append(ac)
                existing_emails.add(ac["email"])

    if not contacts:
        logger.warning("No contacts found for %s — flagged for manual review", company)
        log_event("email_gap", f"No contacts found for company: {company}", job_id=job_id)
        return []

    # Save to DB
    saved = []
    for c in contacts:
        cid = save_contact(
            company=company,
            name=c["name"],
            title=c["title"],
            email=c["email"],
            source=c["source"],
            contact_type=c["contact_type"],
            job_id=job_id,
        )
        c["id"] = cid
        saved.append(c)

    log_event("contacts_found", f"{len(saved)} contacts for {company}", job_id=job_id)
    return saved


# ── Cold email generation ─────────────────────────────────────────────────────

def generate_outreach_emails(job: dict, contacts: list[dict],
                              master_resume: str) -> list[dict]:
    """
    Generate and save cold emails for each contact.
    Returns list of outreach records.
    """
    outreach_records = []
    for contact in contacts:
        if not contact.get("email"):
            continue
        if contact.get("contact_type") not in ("hr", "hiring_manager", "team_lead"):
            continue

        logger.info("  Generating email for %s (%s)", contact.get("name"), contact.get("contact_type"))

        try:
            email_content = generate_cold_email(job, contact, master_resume)
            oid = save_outreach(
                job_id=job["id"],
                contact_id=contact.get("id"),
                outreach_type="cold_email",
                subject=email_content.get("subject", ""),
                body=email_content.get("body", ""),
            )
            outreach_records.append({"outreach_id": oid, "contact": contact, **email_content})
        except Exception as exc:
            logger.warning("Failed to generate email for %s: %s", contact.get("name"), exc)

    return outreach_records


# ── Gap review report ─────────────────────────────────────────────────────────

def print_gap_report() -> None:
    """Print companies where email finding failed (for weekly 5-min manual review)."""
    from database import get_db
    with get_db() as conn:
        rows = conn.execute(
            "SELECT DISTINCT j.company, j.jd_url, j.role "
            "FROM jobs j "
            "WHERE j.h1b_confirmed = 1 "
            "  AND j.applied_status = 'pending' "
            "  AND NOT EXISTS ("
            "    SELECT 1 FROM contacts c WHERE c.job_id = j.id"
            "  ) "
            "ORDER BY j.company"
        ).fetchall()

    if not rows:
        print("No gaps — all companies have contacts!")
        return

    print(f"\n{'='*60}")
    print(f"EMAIL GAPS — {len(rows)} companies need manual lookup")
    print(f"{'='*60}")
    for r in rows:
        print(f"  • {r['company']} | {r['role']}")
        print(f"    {r['jd_url']}")
    print(f"{'='*60}\n")


# ── Main ──────────────────────────────────────────────────────────────────────

def run(job_id: int | None = None, limit: int | None = None,
        skip_emails: bool = False,
        skip_email_lookup: bool = False) -> None:
    """
    skip_email_lookup=True: skip Hunter/Apollo lookup, only regenerate cold emails
                             for existing contacts. Used by fix_emails.py.
    """
    if not skip_email_lookup:
        # At least one email-finding key must be present
        if not config.HUNTER_API_KEY.strip() and not config.APOLLO_API_KEY.strip():
            raise SystemExit(
                "\n" + "─" * 60 + "\n"
                "  No email-finding API keys configured.\n"
                "  Add at least one to your .env:\n"
                "    HUNTER_API_KEY  → https://hunter.io/api-keys\n"
                "    APOLLO_API_KEY  → https://app.apollo.io/#/settings/integrations/api\n"
                + "─" * 60
            )
    # Claude needed if generating cold email drafts
    if not skip_emails:
        config.validate_keys(require_claude=True)

    init_db()
    master_resume = load_master_resume()

    if job_id:
        job = get_job(job_id)
        jobs = [job] if job else []
    else:
        jobs = get_pending_jobs()
        if limit:
            jobs = jobs[:limit]

    logger.info("Finding contacts for %d jobs (lookup=%s)...",
                len(jobs), not skip_email_lookup)

    total_contacts = 0
    total_emails = 0

    for job in jobs:
        try:
            if skip_email_lookup:
                # Use existing contacts already in DB
                contacts = list(get_contacts_for_job(job["id"]))
            else:
                contacts = find_contacts_for_job(job)
            total_contacts += len(contacts)

            if not skip_emails and contacts:
                outreach = generate_outreach_emails(job, contacts, master_resume)
                total_emails += len(outreach)

        except Exception as exc:
            logger.error("Failed job %d (%s): %s", job["id"], job["company"], exc)
        finally:
            time.sleep(1.5)

    logger.info("Done. %d contacts found, %d emails drafted.", total_contacts, total_emails)

    try:
        from notifier import notify_phase3_summary
        notify_phase3_summary(total_contacts, total_emails, len(jobs))
    except Exception:
        pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Phase 3 — Email finder + cold email drafter")
    parser.add_argument("--job-id", type=int, default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--skip-emails", action="store_true",
                        help="Find contacts only, skip email generation")
    parser.add_argument("--review-gaps", action="store_true",
                        help="Print companies missing contact emails")
    args = parser.parse_args()

    if args.review_gaps:
        print_gap_report()
    else:
        run(job_id=args.job_id, limit=args.limit, skip_emails=args.skip_emails)
