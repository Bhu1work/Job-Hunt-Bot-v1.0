"""
notifier.py — Centralized Slack notification helpers.

Every phase imports from here. If Slack isn't configured, all calls are
silent no-ops — nothing in the pipeline ever crashes due to notifications.

Notification events:
  Phase 1  → notify_scrape_done()          [called from phase1_scraper.py]
  Phase 2  → notify_resume_done()          [per job — resume + cover letter made]
             notify_phase2_summary()       [batch complete]
  Phase 3  → notify_phase3_summary()       [contacts found + emails drafted]
  Phase 4  → notify_application_sent()     [per job — form submitted]
             notify_phase4_summary()       [batch complete]
  Phase 5  → notify_cold_email_sent()      [per batch of cold emails sent]
             notify_followup_sent()        [follow-up batch sent]
"""

import logging

logger = logging.getLogger(__name__)


def _send(text: str, blocks: list | None = None) -> None:
    """Fire-and-forget Slack message. Silent no-op if not configured."""
    try:
        import config
        if not config.SLACK_BOT_TOKEN or not config.SLACK_CHANNEL_ID:
            return
        from slack_sdk import WebClient
        client = WebClient(token=config.SLACK_BOT_TOKEN)
        kwargs = {"channel": config.SLACK_CHANNEL_ID, "text": text}
        if blocks:
            kwargs["blocks"] = blocks
        client.chat_postMessage(**kwargs)
    except Exception as exc:
        logger.debug("Slack notify failed (non-fatal): %s", exc)


# ── Phase 2 ───────────────────────────────────────────────────────────────────

def notify_resume_done(role: str, company: str, job_id: int,
                       ats_score: int | None = None) -> None:
    """Fired after Claude tailors resume + cover letter for one job."""
    score_txt = f"  |  ATS: *{ats_score}/100*" if ats_score else ""
    _send(
        f":page_facing_up: Resume + cover letter ready\n"
        f"*{role}* @ {company}{score_txt}  `job #{job_id}`"
    )


def notify_phase2_summary(success: int, total: int) -> None:
    """Fired at end of Phase 2 batch."""
    emoji = ":white_check_mark:" if success == total else ":warning:"
    _send(
        f"{emoji} *Phase 2 complete* — "
        f"{success}/{total} jobs tailored by Claude.\n"
        f"Run `/jobs` → *Apply to Selected* to send cold emails."
    )


# ── Phase 3 ───────────────────────────────────────────────────────────────────

def notify_phase3_summary(contacts: int, emails: int, jobs: int) -> None:
    """Fired at end of Phase 3 batch."""
    _send(
        f":mailbox_with_mail: *Phase 3 complete* — "
        f"{contacts} contacts found across {jobs} companies, "
        f"{emails} cold email drafts ready.\n"
        f"Emails will auto-send when you click *Apply to Selected* in Slack."
    )


# ── Phase 4 ───────────────────────────────────────────────────────────────────

def notify_application_sent(role: str, company: str, job_id: int,
                             ats: str, dry_run: bool = False) -> None:
    """Fired immediately after each ATS form is submitted."""
    tag = " *(DRY RUN)*" if dry_run else ""
    ats_label = ats.replace("_", " ").title()
    _send(
        f":rocket: Application submitted{tag}\n"
        f"*{role}* @ {company}  via {ats_label}  `job #{job_id}`"
    )


def notify_phase4_summary(success: int, total: int, dry_run: bool = False) -> None:
    """Fired at end of Phase 4 batch."""
    tag = " *(DRY RUN)*" if dry_run else ""
    emoji = ":white_check_mark:" if success == total else ":warning:"
    _send(
        f"{emoji} *Phase 4 complete{tag}* — "
        f"{success}/{total} applications submitted via ATS portals."
    )


# ── Phase 5 ───────────────────────────────────────────────────────────────────

def notify_cold_email_sent(count: int, recipient_email: str,
                            company: str, role: str) -> None:
    """Fired after each individual cold email is sent."""
    _send(
        f":email: Cold email sent → *{recipient_email}*\n"
        f"Re: *{role}* @ {company}"
    )


def notify_cold_batch_done(total_sent: int) -> None:
    """Fired after all cold emails in a batch are sent."""
    if total_sent == 0:
        _send(":information_source: Cold email run complete — no new emails to send.")
        return
    _send(
        f":white_check_mark: *{total_sent} cold email(s) sent* "
        f"from bhuvanthatthari@gmail.com\n"
        f"Follow-ups will auto-send at day 3, 7, and 14."
    )


def notify_followup_sent(day: int, count: int) -> None:
    """Fired after a follow-up batch is sent."""
    if count == 0:
        return
    day_label = {3: "Day-3", 7: "Day-7", 14: "Day-14 (final)"}.get(day, f"Day-{day}")
    _send(
        f":arrows_counterclockwise: *{day_label} follow-up* — "
        f"{count} email(s) sent."
    )
