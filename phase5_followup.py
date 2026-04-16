"""
Phase 5 — Follow-up Scheduler + Google Sheets Sync + Daily Digest

Features:
  - APScheduler sends follow-up emails at day 3, 7, and 14 after application
  - Google Sheets sync: logs all jobs + activity
  - Daily Slack/email digest of today's activity + stats
  - SMTP email sender for follow-ups and digest

Run as daemon:
    python phase5_followup.py --daemon

Run once (send due follow-ups now + sync sheets + send digest):
    python phase5_followup.py --now
"""

import argparse
import logging
import smtplib
import time
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

import requests
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

import config
from database import (
    init_db,
    get_due_followups,
    mark_outreach_sent,
    get_today_activity,
    get_stats,
    get_pending_jobs,
    log_event,
    get_db,
)

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)


# ── Follow-up email builder ───────────────────────────────────────────────────

def _build_followup_body(company: str, role: str, day: int) -> tuple[str, str]:
    """Return (subject, body) for a follow-up email."""
    subject = f"Following up — {role} application at {company}"

    if day == 3:
        body = f"""\
Hi,

I wanted to follow up on my application for the {role} position at {company} submitted a few days ago.

I'm genuinely excited about this opportunity and believe my background in {config.YOUR_FIELD} \
aligns well with what you're building. I'd love the chance to discuss how I could contribute to your team.

Please let me know if there's any additional information I can provide.

Best,
{config.YOUR_NAME}
{config.YOUR_EMAIL} | {config.YOUR_PHONE}
{config.YOUR_LINKEDIN}
"""
    elif day == 7:
        body = f"""\
Hi,

I'm checking in on the {role} opening at {company} — I applied about a week ago and remain \
very interested in the role.

If the timeline has shifted or the position has been filled, I completely understand. Otherwise, \
I'd welcome the chance to connect for even a quick call.

Thank you for your time,
{config.YOUR_NAME}
{config.YOUR_EMAIL} | {config.YOUR_LINKEDIN}
"""
    else:  # day 14
        body = f"""\
Hi,

This is my final follow-up on the {role} role at {company}. I've been following your company \
closely and remain enthusiastic about contributing to your team.

If this isn't the right fit or timing, no worries at all — I'd appreciate any feedback when \
you have a moment.

Thank you,
{config.YOUR_NAME}
{config.YOUR_EMAIL}
"""

    return subject, body


# ── SMTP sender ───────────────────────────────────────────────────────────────

def send_email(to: str, subject: str, body: str,
               from_name: str = "") -> bool:
    """Send a plain-text email via SMTP from bhuvanthatthari@gmail.com."""
    smtp_user = config.SMTP_USER or config.APPLICATION_EMAIL
    smtp_pass = config.SMTP_PASSWORD

    if not all([smtp_pass, to]):
        logger.warning("SMTP password not set or missing recipient — skipping send")
        logger.info("  Set SMTP_PASSWORD in .env (Gmail App Password)")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{from_name or config.YOUR_NAME} <{smtp_user}>"
    msg["To"] = to
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, to, msg.as_string())
        logger.info("Email sent to %s — %s", to, subject)
        return True
    except Exception as exc:
        logger.error("SMTP send failed to %s: %s", to, exc)
        return False


# ── Cold email auto-sender ────────────────────────────────────────────────────

def send_cold_emails_for_job(job_id: int) -> int:
    """
    Send all drafted cold emails for a job from bhuvanthatthari@gmail.com.
    Returns count of emails sent.
    """
    from database import get_db
    sent = 0

    with get_db() as conn:
        rows = conn.execute(
            "SELECT o.id, o.subject, o.body, c.email as to_email, "
            "c.name as to_name, c.contact_type "
            "FROM outreach o "
            "JOIN contacts c ON c.id = o.contact_id "
            "WHERE o.job_id = ? AND o.outreach_type = 'cold_email' "
            "  AND o.status = 'draft' AND c.email IS NOT NULL AND c.email != ''",
            (job_id,),
        ).fetchall()

    for row in rows:
        row = dict(row)
        ok = send_email(
            to=row["to_email"],
            subject=row["subject"] or f"Re: {row.get('contact_type', 'Opportunity')}",
            body=row["body"],
        )
        if ok:
            mark_outreach_sent(row["id"])
            log_event("cold_email_sent",
                      f"to={row['to_email']} type={row['contact_type']}",
                      job_id=job_id)
            sent += 1

    return sent


def send_all_pending_cold_emails(limit: int | None = None) -> int:
    """Send all pending cold email drafts across all applied jobs."""
    from database import get_db
    with get_db() as conn:
        rows = conn.execute(
            "SELECT DISTINCT job_id FROM outreach "
            "WHERE outreach_type = 'cold_email' AND status = 'draft'"
        ).fetchall()

    job_ids = [r[0] for r in rows]
    if limit:
        job_ids = job_ids[:limit]

    total = 0
    for jid in job_ids:
        total += send_cold_emails_for_job(jid)
        time.sleep(2)  # respectful send rate

    logger.info("Cold emails sent: %d total", total)
    return total


# ── Follow-up sender ──────────────────────────────────────────────────────────

def send_due_followups(day: int) -> int:
    """Send follow-up emails that are due on `day` days after application."""
    due = get_due_followups(day)
    logger.info("Follow-up day %d: %d emails due", day, len(due))

    sent = 0
    for record in due:
        # Get recipient email from contacts
        with get_db() as conn:
            contact_row = None
            if record.get("contact_id"):
                contact_row = conn.execute(
                    "SELECT * FROM contacts WHERE id = ?", (record["contact_id"],)
                ).fetchone()

        if not contact_row or not contact_row["email"]:
            logger.warning("No email for outreach %d — skipping", record["id"])
            continue

        subject, body = _build_followup_body(record["company"], record["role"], day)

        ok = send_email(
            to=contact_row["email"],
            subject=subject,
            body=body,
        )

        if ok:
            mark_outreach_sent(record["id"])
            log_event("followup_sent",
                      f"day={day} to={contact_row['email']} job={record['job_id']}",
                      job_id=record["job_id"])
            sent += 1

    logger.info("Sent %d follow-up emails (day %d)", sent, day)
    return sent


def schedule_followups_for_job(job_id: int, contact_id: int) -> None:
    """Insert follow-up outreach records at day 3, 7, 14 for a job."""
    from database import save_outreach
    job = __import__("database").get_job(job_id)
    if not job:
        return

    for day in config.FOLLOWUP_DAYS:
        save_outreach(
            job_id=job_id,
            contact_id=contact_id,
            outreach_type="followup",
            subject="",  # generated fresh at send time
            body="",
            followup_day=day,
        )
    logger.info("Scheduled follow-ups (days %s) for job %d", config.FOLLOWUP_DAYS, job_id)


# ── Google Sheets sync ────────────────────────────────────────────────────────

def _get_sheets_service():
    """Build Google Sheets API service from service account credentials."""
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        creds = service_account.Credentials.from_service_account_file(
            config.GOOGLE_SERVICE_ACCOUNT_JSON,
            scopes=["https://www.googleapis.com/auth/spreadsheets"],
        )
        return build("sheets", "v4", credentials=creds)
    except Exception as exc:
        logger.warning("Google Sheets service unavailable: %s", exc)
        return None


def sync_to_sheets() -> bool:
    """Sync jobs and activity to Google Sheets."""
    if not config.GOOGLE_SHEETS_SPREADSHEET_ID:
        logger.info("Google Sheets not configured — skipping sync")
        return False

    svc = _get_sheets_service()
    if not svc:
        return False

    sheet = svc.spreadsheets()
    spreadsheet_id = config.GOOGLE_SHEETS_SPREADSHEET_ID

    # ── Jobs sheet ─────────────────────────────────────────────────────────────
    with get_db() as conn:
        jobs = conn.execute(
            "SELECT id, company, role, jd_url, source, location, "
            "h1b_confirmed, applied_status, applied_at, created_at "
            "FROM jobs ORDER BY created_at DESC"
        ).fetchall()

    headers = ["ID", "Company", "Role", "JD URL", "Source", "Location",
               "H1B Confirmed", "Status", "Applied At", "Created At"]
    rows: list[list[Any]] = [headers]
    for j in jobs:
        rows.append([
            j["id"], j["company"], j["role"], j["jd_url"], j["source"],
            j["location"], "Yes" if j["h1b_confirmed"] else "No",
            j["applied_status"], j["applied_at"] or "", j["created_at"],
        ])

    try:
        sheet.values().update(
            spreadsheetId=spreadsheet_id,
            range="Jobs!A1",
            valueInputOption="RAW",
            body={"values": rows},
        ).execute()
        logger.info("Synced %d jobs to Google Sheets", len(rows) - 1)
    except Exception as exc:
        logger.error("Failed to sync jobs to Sheets: %s", exc)
        return False

    # ── Stats sheet ────────────────────────────────────────────────────────────
    stats = get_stats()
    stats_rows = [
        ["Metric", "Value"],
        ["Total Jobs Found", stats["total_jobs"]],
        ["H1B Confirmed", stats["h1b_jobs"]],
        ["Applied", stats["applied"]],
        ["Interviews", stats["interviews"]],
        ["Emails Sent", stats["emails_sent"]],
        ["Last Updated", datetime.now().strftime("%Y-%m-%d %H:%M")],
    ]

    try:
        sheet.values().update(
            spreadsheetId=spreadsheet_id,
            range="Stats!A1",
            valueInputOption="RAW",
            body={"values": stats_rows},
        ).execute()
        logger.info("Synced stats to Google Sheets")
    except Exception as exc:
        logger.error("Failed to sync stats to Sheets: %s", exc)

    log_event("sheets_sync", f"synced {len(rows)-1} jobs")
    return True


# ── Slack digest ──────────────────────────────────────────────────────────────

def _build_digest_text() -> str:
    stats = get_stats()
    activity = get_today_activity()
    today = datetime.now().strftime("%A, %B %d")

    lines = [
        f"*Job Hunt Digest — {today}*",
        "",
        "📊 *Overall Stats*",
        f"  • Jobs found: {stats['total_jobs']}  |  H1B confirmed: {stats['h1b_jobs']}",
        f"  • Applied: {stats['applied']}  |  Interviews: {stats['interviews']}",
        f"  • Emails sent: {stats['emails_sent']}",
        "",
        f"📅 *Today's Activity ({len(activity)} events)*",
    ]

    event_counts: dict[str, int] = {}
    for ev in activity:
        event_counts[ev["event"]] = event_counts.get(ev["event"], 0) + 1

    for event, count in event_counts.items():
        lines.append(f"  • {event.replace('_', ' ').title()}: {count}")

    if not activity:
        lines.append("  (no activity today)")

    return "\n".join(lines)


def send_slack_digest() -> bool:
    """Post daily digest to Slack via webhook."""
    if not config.SLACK_WEBHOOK_URL:
        logger.info("Slack webhook not configured — skipping digest")
        return False

    text = _build_digest_text()
    payload = {"text": text}

    try:
        resp = requests.post(config.SLACK_WEBHOOK_URL, json=payload, timeout=10)
        resp.raise_for_status()
        logger.info("Slack digest sent")
        return True
    except Exception as exc:
        logger.error("Slack digest failed: %s", exc)
        return False


def send_email_digest() -> bool:
    """Send daily digest via email."""
    if not config.YOUR_EMAIL:
        return False

    text = _build_digest_text().replace("*", "").replace("📊", "").replace("📅", "")
    subject = f"Job Hunt Digest — {datetime.now().strftime('%B %d, %Y')}"
    return send_email(to=config.YOUR_EMAIL, subject=subject, body=text)


# ── Scheduler jobs ────────────────────────────────────────────────────────────

def job_followup_day3() -> None:
    send_due_followups(3)


def job_followup_day7() -> None:
    send_due_followups(7)


def job_followup_day14() -> None:
    send_due_followups(14)


def job_daily_digest() -> None:
    sync_to_sheets()
    send_slack_digest()
    send_email_digest()
    log_event("digest_sent", datetime.now().strftime("%Y-%m-%d"))


def run_now() -> None:
    """Run all scheduled tasks immediately (useful for testing)."""
    init_db()
    logger.info("Running all tasks now...")
    for day in config.FOLLOWUP_DAYS:
        send_due_followups(day)
    sync_to_sheets()
    send_slack_digest()
    send_email_digest()


def run_daemon() -> None:
    """Start APScheduler and block."""
    init_db()
    scheduler = BlockingScheduler(timezone="America/New_York")

    # Follow-ups: check every morning at 9 AM
    scheduler.add_job(job_followup_day3,  CronTrigger(hour=9, minute=0), id="followup_d3")
    scheduler.add_job(job_followup_day7,  CronTrigger(hour=9, minute=5), id="followup_d7")
    scheduler.add_job(job_followup_day14, CronTrigger(hour=9, minute=10), id="followup_d14")

    # Daily digest at 6 PM
    scheduler.add_job(job_daily_digest, CronTrigger(hour=18, minute=0), id="digest")

    logger.info("Scheduler started. Jobs:")
    for j in scheduler.get_jobs():
        next_run = getattr(j, "next_run_time", None) or getattr(j, "trigger", None)
        logger.info("  • %s: next=%s", j.id, next_run)

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Phase 5 — Follow-up scheduler + digest")
    parser.add_argument("--daemon", action="store_true", help="Run as background scheduler")
    parser.add_argument("--now", action="store_true", help="Run all tasks once immediately")
    parser.add_argument("--digest-only", action="store_true", help="Send digest only")
    parser.add_argument("--sync-sheets", action="store_true", help="Sync to Google Sheets only")
    parser.add_argument("--send-cold", action="store_true",
                        help="Send all pending cold emails now")
    parser.add_argument("--limit", type=int, default=None,
                        help="Max cold emails to send (default: all)")
    args = parser.parse_args()

    if args.daemon:
        run_daemon()
    elif args.now:
        run_now()
    elif args.send_cold:
        init_db()
        total = send_all_pending_cold_emails(limit=args.limit)
        logger.info("Sent %d cold emails.", total)
    elif args.digest_only:
        init_db()
        send_slack_digest()
        send_email_digest()
    elif args.sync_sheets:
        init_db()
        sync_to_sheets()
    else:
        parser.print_help()
