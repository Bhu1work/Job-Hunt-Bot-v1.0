"""
Phase 4 — Auto-Apply via Playwright + LinkedIn Referral DM Drafter

Supports:
  - Greenhouse (boards.greenhouse.io)
  - Lever (jobs.lever.co)
  - Workday (myworkdayjobs.com)

Referral DM generation (manual send required — LinkedIn blocks bots):
  - Searches LinkedIn for employees at target companies
  - Claude drafts personalized DMs for each

Run:
    python phase4_auto_apply.py [--job-id 42] [--dry-run]
    python phase4_auto_apply.py --referrals --company "Stripe"
"""

import argparse
import asyncio
import logging
import re
import time
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright, Page, TimeoutError as PWTimeout
import anthropic

import config
from database import (
    init_db,
    get_pending_jobs,
    get_job,
    get_tailored_docs,
    update_job_status,
    save_outreach,
    log_event,
)

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)

client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)


# ── ATS detector ──────────────────────────────────────────────────────────────

def detect_ats(url: str) -> str:
    """Return ATS platform name from URL."""
    url_lower = url.lower()
    if "greenhouse.io" in url_lower:
        return "greenhouse"
    if "lever.co" in url_lower:
        return "lever"
    if "workday" in url_lower or "myworkdayjobs.com" in url_lower:
        return "workday"
    if "ashbyhq.com" in url_lower:
        return "ashby"
    if "smartrecruiters.com" in url_lower:
        return "smartrecruiters"
    return "unknown"


# ── Common form helpers ───────────────────────────────────────────────────────

async def _fill_if_visible(page: Page, selector: str, value: str) -> bool:
    try:
        el = page.locator(selector).first
        if await el.is_visible(timeout=3000):
            await el.fill(value)
            return True
    except Exception:
        pass
    return False


async def _upload_file(page: Page, selector: str, file_path: str) -> bool:
    try:
        el = page.locator(selector).first
        if await el.is_visible(timeout=3000):
            await el.set_input_files(file_path)
            return True
    except Exception:
        pass
    return False


async def _click_if_visible(page: Page, selector: str) -> bool:
    try:
        el = page.locator(selector).first
        if await el.is_visible(timeout=3000):
            await el.click()
            return True
    except Exception:
        pass
    return False


# ── Greenhouse applier ────────────────────────────────────────────────────────

async def apply_greenhouse(page: Page, job: dict, docs: dict,
                            dry_run: bool = False) -> bool:
    """Fill and submit a Greenhouse application form."""
    logger.info("Greenhouse: navigating to %s", job["jd_url"])
    await page.goto(job["jd_url"], wait_until="networkidle", timeout=30000)

    # Basic personal info
    await _fill_if_visible(page, 'input[name="job_application[first_name]"]', config.YOUR_NAME.split()[0])
    await _fill_if_visible(page, 'input[name="job_application[last_name]"]', config.YOUR_NAME.split()[-1])
    await _fill_if_visible(page, 'input[name="job_application[email]"]', config.YOUR_EMAIL)
    await _fill_if_visible(page, 'input[name="job_application[phone]"]', config.YOUR_PHONE)
    await _fill_if_visible(page, 'input[name="job_application[linkedin_profile_url]"]', config.YOUR_LINKEDIN)

    # Resume upload (use tailored PDF if available)
    resume_path = _get_resume_pdf_for_job(job)
    await _upload_file(page, 'input[type="file"]', resume_path)

    # Cover letter textarea
    if docs.get("cover_letter"):
        await _fill_if_visible(page, 'textarea[name*="cover_letter"]', docs["cover_letter"])
        await _fill_if_visible(page, 'textarea[placeholder*="cover letter" i]', docs["cover_letter"])

    # Work authorization / visa
    await _handle_visa_question(page)

    if dry_run:
        logger.info("DRY RUN — would submit Greenhouse form for %s", job["company"])
        await page.screenshot(path=f"logs/greenhouse_{job['id']}_preview.png")
        return True

    # Submit
    submitted = await _click_if_visible(page, 'input[type="submit"]')
    if not submitted:
        submitted = await _click_if_visible(page, 'button[type="submit"]')

    return submitted


# ── Lever applier ─────────────────────────────────────────────────────────────

async def apply_lever(page: Page, job: dict, docs: dict,
                       dry_run: bool = False) -> bool:
    """Fill and submit a Lever application form."""
    logger.info("Lever: navigating to %s", job["jd_url"])
    await page.goto(job["jd_url"], wait_until="networkidle", timeout=30000)

    # Lever uses /apply suffix
    apply_url = job["jd_url"].rstrip("/") + "/apply"
    if "/apply" not in page.url:
        await page.goto(apply_url, wait_until="networkidle", timeout=30000)

    await _fill_if_visible(page, 'input[name="name"]', config.YOUR_NAME)
    await _fill_if_visible(page, 'input[name="email"]', config.YOUR_EMAIL)
    await _fill_if_visible(page, 'input[name="phone"]', config.YOUR_PHONE)
    await _fill_if_visible(page, 'input[name="urls[LinkedIn]"]', config.YOUR_LINKEDIN)
    await _fill_if_visible(page, 'input[name="urls[GitHub]"]', config.YOUR_GITHUB)

    resume_path = _get_resume_pdf_for_job(job)
    await _upload_file(page, 'input[type="file"]', resume_path)

    if docs.get("cover_letter"):
        await _fill_if_visible(page, 'textarea[name="comments"]', docs["cover_letter"])

    await _handle_visa_question(page)

    if dry_run:
        logger.info("DRY RUN — would submit Lever form for %s", job["company"])
        await page.screenshot(path=f"logs/lever_{job['id']}_preview.png")
        return True

    return await _click_if_visible(page, 'button[type="submit"]')


# ── Workday applier ───────────────────────────────────────────────────────────

async def apply_workday(page: Page, job: dict, docs: dict,
                         dry_run: bool = False) -> bool:
    """
    Workday is complex — multi-step wizard. This handles the common flow.
    Some companies have custom Workday configs; manual fallback may be needed.
    """
    logger.info("Workday: navigating to %s", job["jd_url"])
    await page.goto(job["jd_url"], wait_until="networkidle", timeout=30000)

    # Click "Apply" button
    await _click_if_visible(page, 'a[data-automation-id="applyBtn"]')
    await page.wait_for_timeout(2000)

    # Create account or sign in if required — check for email field
    await _fill_if_visible(page, 'input[data-automation-id="email"]', config.YOUR_EMAIL)
    await _click_if_visible(page, 'button[data-automation-id="createAccountSubmitButton"]')
    await page.wait_for_timeout(2000)

    # Resume upload (use tailored PDF if available)
    resume_path = _get_resume_pdf_for_job(job)
    await _upload_file(page, 'input[data-automation-id="file-upload-input-ref"]', resume_path)
    await page.wait_for_timeout(2000)

    await _handle_visa_question(page)

    if dry_run:
        logger.info("DRY RUN — would submit Workday form for %s", job["company"])
        await page.screenshot(path=f"logs/workday_{job['id']}_preview.png")
        return True

    # Workday has a multi-page wizard; click "Next" until "Submit"
    for _ in range(10):
        next_clicked = await _click_if_visible(page, 'button[data-automation-id="bottom-navigation-next-button"]')
        if not next_clicked:
            break
        await page.wait_for_timeout(1500)

    return await _click_if_visible(page, 'button[data-automation-id="bottom-navigation-footer-button"]')


# ── Visa question handler ─────────────────────────────────────────────────────

async def _handle_visa_question(page: Page) -> None:
    """Answer common work authorization / visa sponsorship questions."""
    # "Are you authorized to work?" — select Yes
    for sel in [
        'select[name*="authorized"]',
        'select[id*="authorized"]',
        'select[name*="work_auth"]',
    ]:
        try:
            await page.select_option(sel, label="Yes", timeout=2000)
        except Exception:
            pass

    # "Will you require sponsorship?" — select Yes
    for sel in [
        'select[name*="sponsorship"]',
        'select[id*="sponsorship"]',
        'select[name*="visa"]',
    ]:
        try:
            await page.select_option(sel, label="Yes", timeout=2000)
        except Exception:
            pass

    # Radio buttons
    for label_text in ["yes", "i will require"]:
        try:
            labels = await page.locator(f'label:has-text("{label_text}")').all()
            for lbl in labels[:2]:
                if "sponsor" in (await lbl.inner_text()).lower():
                    await lbl.click()
        except Exception:
            pass


# ── Main apply dispatcher ─────────────────────────────────────────────────────

def _get_resume_pdf_for_job(job: dict) -> str:
    """Return path to tailored PDF in application folder, or fall back to master PDF."""
    import json
    from application_manager import get_app_folder
    folder = get_app_folder(job)
    meta_file = folder / "metadata.json"
    if meta_file.exists():
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        pdf = meta.get("docs", {}).get("pdf")
        if pdf and Path(pdf).exists():
            return pdf
    return str(Path(config.RESUME_PDF_PATH).resolve())


async def _linkedin_login(page: Page) -> bool:
    """Log in to LinkedIn using stored credentials. Returns True on success."""
    if not (config.LINKEDIN_EMAIL and config.LINKEDIN_PASSWORD):
        return False
    try:
        await page.goto("https://www.linkedin.com/login", timeout=20000,
                        wait_until="domcontentloaded")
        await page.wait_for_timeout(1500)
        await page.fill('#username', config.LINKEDIN_EMAIL)
        await page.fill('#password', config.LINKEDIN_PASSWORD)
        await page.click('[data-litms-control-urn="login-submit"]')
        await page.wait_for_timeout(4000)
        # Verify login worked
        if "feed" in page.url or "jobs" in page.url or "checkpoint" not in page.url:
            logger.info("LinkedIn login: OK")
            return True
        logger.warning("LinkedIn login may have failed (url=%s)", page.url)
        return False
    except Exception as exc:
        logger.warning("LinkedIn login error: %s", exc)
        return False


async def resolve_apply_url(linkedin_url: str) -> str:
    """
    Navigate to a LinkedIn job page (logged in) and extract the external
    "Apply on company website" URL.  Returns "easy_apply::<original_url>"
    sentinel if the job supports LinkedIn Easy Apply.
    Returns original URL on failure.
    """
    if "linkedin.com" not in linkedin_url:
        return linkedin_url

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = await context.new_page()
        try:
            # Login first so we can see the apply button
            await _linkedin_login(page)
            await page.goto(linkedin_url, timeout=25000, wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)

            # Check for Easy Apply
            easy_btn = page.locator('button:has-text("Easy Apply")').first
            if await easy_btn.count() > 0 and await easy_btn.is_visible():
                logger.info("Job supports LinkedIn Easy Apply: %s", linkedin_url)
                return f"easy_apply::{linkedin_url}"

            # Look for "Apply on company website" link
            apply_link = page.locator(
                'a[data-tracking-control-name*="applyLink"],'
                'a.jobs-apply-button--top-card,'
                'a[href*="greenhouse.io"], a[href*="lever.co"],'
                'a[href*="workday"], a[href*="myworkdayjobs"],'
                'a[href*="ashbyhq"], a[href*="smartrecruiters"]'
            ).first
            if await apply_link.count() > 0:
                href = await apply_link.get_attribute("href")
                if href and href.startswith("http"):
                    logger.info("Resolved external apply URL: %s", href)
                    return href

            # Scan page HTML for ATS URLs
            content = await page.content()
            for kw in ["greenhouse.io", "lever.co", "myworkdayjobs.com",
                       "ashbyhq.com", "smartrecruiters.com"]:
                if kw in content:
                    m = re.search(
                        r'https?://[^\s"\'<>]+' + kw.replace(".", r"\.") + r'[^\s"\'<>]*',
                        content
                    )
                    if m:
                        logger.info("Found ATS URL via HTML scan: %s", m.group())
                        return m.group()
        except Exception as exc:
            logger.warning("Could not resolve apply URL for %s: %s", linkedin_url, exc)
        finally:
            await browser.close()

    return linkedin_url  # fall back — ATS detection will mark as unknown


async def apply_linkedin_easy_apply(
        linkedin_url: str, job: dict, docs: dict, dry_run: bool = False
) -> bool:
    """Fill out LinkedIn Easy Apply form and submit (or screenshot on dry-run)."""
    resume_pdf = _get_resume_pdf_for_job(job)
    cover_letter_text = docs.get("cover_letter", "")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = await context.new_page()
        try:
            logged_in = await _linkedin_login(page)
            if not logged_in:
                logger.warning("Skipping Easy Apply — LinkedIn login failed")
                return False

            await page.goto(linkedin_url, timeout=25000, wait_until="domcontentloaded")
            await page.wait_for_timeout(2000)

            # Open Easy Apply modal
            easy_btn = page.locator('button:has-text("Easy Apply")').first
            if not await easy_btn.is_visible():
                logger.warning("Easy Apply button not found for job %d", job["id"])
                return False
            await easy_btn.click()
            await page.wait_for_timeout(2000)

            # Multi-step form — iterate up to 10 pages
            for step in range(10):
                await page.wait_for_timeout(1500)

                # Fill contact fields if visible
                await _fill_if_visible(page, 'input[id*="phoneNumber"]', config.YOUR_PHONE or "")
                await _fill_if_visible(page, 'input[id*="city"]', config.YOUR_LOCATION or "")

                # Upload resume if file input present
                for sel in ['input[type="file"]', 'input[name*="resume"]']:
                    try:
                        el = page.locator(sel).first
                        if await el.count() > 0 and await el.is_visible(timeout=1000):
                            await el.set_input_files(resume_pdf)
                            break
                    except Exception:
                        pass

                # Fill cover letter textarea
                if cover_letter_text:
                    for sel in ['textarea[id*="coverLetter"]', 'textarea']:
                        try:
                            el = page.locator(sel).first
                            if await el.count() > 0 and await el.is_visible(timeout=1000):
                                await el.fill(cover_letter_text[:2000])
                                break
                        except Exception:
                            pass

                # Handle sponsorship / work auth
                await _handle_visa_question(page)

                # Check for "Review" or "Submit" button
                submit_btn = page.locator(
                    'button[aria-label*="Submit"], button:has-text("Submit application")'
                ).first
                if await submit_btn.count() > 0 and await submit_btn.is_visible():
                    if dry_run:
                        await page.screenshot(
                            path=f"logs/dry_run_{job['id']}_easy_apply.png"
                        )
                        logger.info("[DRY RUN] Would submit Easy Apply for job %d", job["id"])
                        return True
                    await submit_btn.click()
                    await page.wait_for_timeout(3000)
                    logger.info("Submitted Easy Apply for job %d", job["id"])
                    return True

                # Next page
                next_btn = page.locator(
                    'button[aria-label*="Continue"], button:has-text("Next")'
                ).first
                if await next_btn.count() > 0 and await next_btn.is_visible():
                    await next_btn.click()
                    await page.wait_for_timeout(1500)
                    continue

                logger.warning("Easy Apply: no Next/Submit button on step %d", step)
                break

        except Exception as exc:
            logger.error("Easy Apply failed for job %d: %s", job["id"], exc)
            return False
        finally:
            await browser.close()

    return False


async def apply_to_job(job: dict, dry_run: bool = False) -> bool:
    """Detect ATS and apply. Resolves LinkedIn URLs to actual company ATS URLs first."""
    jd_url = job["jd_url"]
    docs = get_tailored_docs(job["id"]) or {}

    # Step 1: Resolve LinkedIn redirect → actual ATS URL (or easy_apply sentinel)
    apply_url = await resolve_apply_url(jd_url)

    # Step 2: Handle LinkedIn Easy Apply
    if apply_url.startswith("easy_apply::"):
        original = apply_url[len("easy_apply::"):]
        logger.info("Using LinkedIn Easy Apply for job %d", job["id"])
        success = await apply_linkedin_easy_apply(original, job, docs, dry_run)
        if success and not dry_run:
            update_job_status(job["id"], "applied")
            log_event("applied", f"ATS=linkedin_easy_apply url={original}", job_id=job["id"])
            logger.info("Applied (Easy Apply) to %s @ %s", job["role"], job["company"])
            try:
                from application_manager import mark_applied
                mark_applied(job["id"], ats="linkedin_easy_apply")
            except Exception:
                pass
        return success

    ats = detect_ats(apply_url)

    if ats == "unknown":
        logger.warning(
            "Unknown ATS for job %d — jd=%s resolved=%s",
            job["id"], jd_url, apply_url
        )
        return False

    logger.info("ATS=%s url=%s", ats, apply_url)
    # Patch the URL so handlers use the real apply URL
    job = dict(job)
    job["jd_url"] = apply_url

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        )
        page = await context.new_page()

        try:
            if ats == "greenhouse":
                success = await apply_greenhouse(page, job, docs, dry_run)
            elif ats == "lever":
                success = await apply_lever(page, job, docs, dry_run)
            elif ats == "workday":
                success = await apply_workday(page, job, docs, dry_run)
            else:
                logger.warning("ATS '%s' not yet implemented", ats)
                success = False

            if success and not dry_run:
                update_job_status(job["id"], "applied")
                log_event("applied", f"ATS={ats} url={job['jd_url']}", job_id=job["id"])
                logger.info("✓ Applied to %s @ %s", job["role"], job["company"])
                # Update application folder metadata
                try:
                    from application_manager import mark_applied
                    mark_applied(job["id"], ats=ats)
                except Exception:
                    pass

            return success

        except PWTimeout as exc:
            logger.error("Playwright timeout for job %d: %s", job["id"], exc)
            await page.screenshot(path=f"logs/error_{job['id']}.png")
            return False
        except Exception as exc:
            logger.error("Apply failed for job %d: %s", job["id"], exc)
            return False
        finally:
            await browser.close()


# ── LinkedIn referral DM drafter ──────────────────────────────────────────────

def _referral_dm_prompt(candidate_name: str, employee_name: str,
                         employee_title: str, company: str, role: str,
                         master_resume_snippet: str) -> str:
    return f"""Write a short, genuine LinkedIn DM from {candidate_name} to {employee_name} 
({employee_title} at {company}) asking for a referral for the {role} position.

Rules:
- Max 4 sentences
- Open with something specific to them (their title/role at {company})
- Mention 1 relevant achievement from the resume snippet
- End with a soft, specific ask: "Would you be open to referring me, or passing this along 
  to the hiring team?"
- Do NOT use "I hope this message finds you well" or similar openers
- Be direct but warm — this is a cold DM

Resume snippet:
{master_resume_snippet}

Output ONLY the DM text. No subject line needed.
"""


def draft_referral_dms(company: str, role: str,
                        employees: list[dict]) -> list[dict]:
    """
    Generate personalized LinkedIn referral DMs for a list of employees.
    Employees: [{"name": ..., "title": ..., "linkedin_url": ...}]
    Returns list of {"employee": ..., "dm": ...}
    """
    from phase2_resume_tailor import load_master_resume
    master_resume = load_master_resume()
    snippet = master_resume[:1200]

    dms = []
    for emp in employees[:3]:  # Cap at 3 per company
        prompt = _referral_dm_prompt(
            candidate_name=config.YOUR_NAME,
            employee_name=emp.get("name", "there"),
            employee_title=emp.get("title", "engineer"),
            company=company,
            role=role,
            master_resume_snippet=snippet,
        )
        try:
            message = client.messages.create(
                model=config.CLAUDE_MODEL,
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}],
            )
            dm_text = message.content[0].text
            dms.append({"employee": emp, "dm": dm_text})
            logger.info("Drafted DM for %s @ %s", emp.get("name"), company)
            time.sleep(0.3)
        except Exception as exc:
            logger.warning("DM generation failed for %s: %s", emp.get("name"), exc)

    return dms


def search_linkedin_employees(company: str, titles: list[str],
                               limit: int = 5) -> list[dict]:
    """
    Search LinkedIn for employees with relevant titles at a company.
    Uses the unofficial linkedin-api package (requires your credentials).
    """
    try:
        from linkedin_api import Linkedin
        api = Linkedin(config.LINKEDIN_EMAIL, config.LINKEDIN_PASSWORD)
        results = api.search_people(
            keywords=company,
            keyword_title=" OR ".join(titles[:3]),
            limit=limit,
        )
        employees = []
        for r in results:
            employees.append({
                "name": f"{r.get('firstName', '')} {r.get('lastName', '')}".strip(),
                "title": r.get("headline", ""),
                "linkedin_url": f"https://linkedin.com/in/{r.get('publicIdentifier', '')}",
            })
        return employees
    except Exception as exc:
        logger.warning("LinkedIn employee search failed for %s: %s", company, exc)
        return []


def print_referral_dms(company: str, role: str) -> None:
    """CLI helper: search employees and print draft DMs to stdout for copy-paste."""
    target_titles = ["Software Engineer", "Senior Engineer", "Data Scientist", "Engineering Manager"]
    employees = search_linkedin_employees(company, target_titles)

    if not employees:
        print(f"No LinkedIn employees found for {company} — try searching manually.")
        return

    dms = draft_referral_dms(company, role, employees)

    print(f"\n{'='*60}")
    print(f"REFERRAL DMs for {role} @ {company}  (COPY & SEND MANUALLY)")
    print(f"{'='*60}")
    for item in dms:
        emp = item["employee"]
        print(f"\n→ {emp['name']} | {emp['title']}")
        print(f"  {emp.get('linkedin_url', '')}")
        print(f"\n  {item['dm']}")
        print()
    print(f"{'='*60}\n")


# ── Batch runner ──────────────────────────────────────────────────────────────

async def run_async(job_id: int | None = None, dry_run: bool = False,
                    limit: int | None = None) -> None:
    init_db()

    if job_id:
        job = get_job(job_id)
        jobs = [job] if job else []
    else:
        jobs = get_pending_jobs()
        if limit:
            jobs = jobs[:limit]

    logger.info("%s to %d jobs...", "DRY RUN applying" if dry_run else "Applying", len(jobs))

    success = 0
    for job in jobs:
        # Require tailored docs before applying
        docs = get_tailored_docs(job["id"])
        if not docs:
            logger.warning("Job %d has no tailored docs — run phase2 first", job["id"])
            continue

        ok = await apply_to_job(job, dry_run=dry_run)
        if ok:
            success += 1
        await asyncio.sleep(3)  # pause between applications

    logger.info("Done. %d / %d applications submitted.", success, len(jobs))


def run(job_id: int | None = None, dry_run: bool = False,
        limit: int | None = None) -> None:
    asyncio.run(run_async(job_id=job_id, dry_run=dry_run, limit=limit))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Phase 4 — Auto-apply + referral DMs")
    parser.add_argument("--job-id", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true",
                        help="Fill forms but do not submit")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--referrals", action="store_true",
                        help="Generate referral DMs instead of applying")
    parser.add_argument("--company", type=str, default="",
                        help="Company for referral DM mode")
    parser.add_argument("--role", type=str, default=config.YOUR_FIELD,
                        help="Role for referral DM mode")
    args = parser.parse_args()

    if args.referrals:
        if not args.company:
            parser.error("--company is required with --referrals")
        print_referral_dms(args.company, args.role)
    else:
        run(job_id=args.job_id, dry_run=args.dry_run, limit=args.limit)
