"""
Slack Bot — Job Hunt Hub (replaces telegram_bot.py).

Uses Slack Bolt + Socket Mode — no public URL required, works inside Docker.

Commands (register these as Slash Commands in api.slack.com → Your App → Slash Commands):
  /jobs    — Show top 20 ATS-scored jobs with a multi-select picker
  /apply   — Trigger pipeline for currently selected jobs
  /status  — Stats dashboard
  /scrape  — Kick off a fresh job scrape (Phase 1)
  /reset   — Clear all selections

Setup (see README or instructions below):
  1. Go to https://api.slack.com/apps → Create New App → From scratch
  2. Give it a name (e.g. "Job Hunt Bot") and pick your workspace
  3. Under "Socket Mode" → Enable Socket Mode → Generate App-Level Token
     - Scope: connections:write
     - Copy the xapp-... token → SLACK_APP_TOKEN in .env
  4. Under "OAuth & Permissions" → Bot Token Scopes:
       chat:write, commands, im:write, channels:read
     → Install to Workspace → copy xoxb-... token → SLACK_BOT_TOKEN in .env
  5. Under "Slash Commands" → create each:
       /jobs, /apply, /status, /scrape, /reset
     (URL can be anything — Socket Mode ignores it)
  6. Under "Interactivity & Shortcuts" → Enable Interactivity
     (Request URL can be anything — Socket Mode handles it)
  7. Create a channel #job-hunt, invite the bot: /invite @JobHuntBot
     Then set SLACK_CHANNEL_ID=C... (copy from channel URL or /channel-details)
  8. docker compose up -d slack

Run standalone:
  docker compose run --rm bot python slack_bot.py
"""

import logging
import subprocess
import time
from typing import Any

import config
from ats_scorer import score_all_pending_jobs
from database import get_db, init_db

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

# ── lazy imports — only pulled in when the bot actually runs ──────────────────
try:
    from slack_bolt import App
    from slack_bolt.adapter.socket_mode import SocketModeHandler
    _SDK_OK = True
except ImportError:
    _SDK_OK = False


# ── In-memory state (single-process) ─────────────────────────────────────────
_state: dict[str, Any] = {
    "scored_jobs":    [],
    "selected_ids":   set(),     # set of int job IDs
    "last_refresh":   0.0,
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _refresh_jobs(threshold: int = 80) -> None:
    logger.info("Scoring jobs (ATS threshold=%d)…", threshold)
    scored = score_all_pending_jobs(threshold=threshold)
    _state["scored_jobs"] = scored
    _state["last_refresh"] = time.time()
    logger.info("Found %d jobs above threshold", len(scored))


def _job_list_blocks() -> list[dict]:
    """Build Slack Block Kit blocks for the job picker."""
    scored = _state["scored_jobs"][:20]
    selected = _state["selected_ids"]

    if not scored:
        return [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        ":x: *No pending jobs above the ATS threshold.*\n"
                        "Run `/scrape` to fetch fresh jobs first."
                    ),
                },
            }
        ]

    lines = [":dart: *Top Jobs — pick which ones to apply to:*\n"]
    options = []
    for i, item in enumerate(scored, 1):
        job     = item["job"]
        jid     = job["id"]
        score   = item["ats_score"]
        grade   = item["ats_grade"]
        company = job["company"][:20]
        role    = job["role"][:32]
        chk     = ":white_check_mark:" if jid in selected else ":white_square_button:"
        missing = ", ".join(item["missing_keywords"][:3]) or "none"

        lines.append(
            f"{i}. {chk} *{role}* @ {company}\n"
            f"   ATS: *{score}/100* ({grade})  |  missing: {missing}"
        )

        label = f"{i}. {company} — {role[:22]} (ATS:{score})"
        options.append({
            "text":  {"type": "plain_text", "text": label[:75], "emoji": True},
            "value": str(jid),
        })

    # Pre-select already-chosen options
    initial = [
        {"text": {"type": "plain_text", "text": o["text"]["text"]}, "value": o["value"]}
        for o in options
        if int(o["value"]) in selected
    ]

    blocks: list[dict] = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": ":dart: Job Selection Hub", "emoji": True},
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "\n".join(lines)},
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*Select jobs to apply to:*"},
            "accessory": {
                "type":        "multi_static_select",
                "placeholder": {"type": "plain_text", "text": "Pick jobs…", "emoji": True},
                "options":     options,
                **({"initial_options": initial} if initial else {}),
                "action_id":   "select_jobs",
            },
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type":      "button",
                    "text":      {"type": "plain_text", "text": ":rocket: Apply to Selected", "emoji": True},
                    "style":     "primary",
                    "action_id": "apply_selected",
                },
                {
                    "type":      "button",
                    "text":      {"type": "plain_text", "text": ":bar_chart: Stats", "emoji": True},
                    "action_id": "get_stats",
                },
                {
                    "type":      "button",
                    "text":      {"type": "plain_text", "text": ":wastebasket: Clear", "emoji": True},
                    "style":     "danger",
                    "action_id": "clear_selections",
                },
                {
                    "type":      "button",
                    "text":      {"type": "plain_text", "text": ":arrows_counterclockwise: Refresh", "emoji": True},
                    "action_id": "refresh_jobs",
                },
            ],
        },
    ]

    return blocks


def _stats_text() -> str:
    with get_db() as c:
        total    = c.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        h1b      = c.execute("SELECT COUNT(*) FROM jobs WHERE h1b_confirmed=1").fetchone()[0]
        pending  = c.execute(
            "SELECT COUNT(*) FROM jobs WHERE applied_status='pending' AND h1b_confirmed=1"
        ).fetchone()[0]
        applied  = c.execute("SELECT COUNT(*) FROM jobs WHERE applied_status='applied'").fetchone()[0]
        emails   = c.execute("SELECT COUNT(*) FROM outreach WHERE status='sent'").fetchone()[0]
        drafts   = c.execute("SELECT COUNT(*) FROM outreach WHERE status='draft'").fetchone()[0]
        contacts = c.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]
    return (
        f":bar_chart: *Job Hunt Stats*\n\n"
        f"Total jobs scraped : *{total}*\n"
        f"H1B-confirmed      : *{h1b}*\n"
        f"Pending (ready)    : *{pending}*\n"
        f"Applied            : *{applied}*\n"
        f"Contacts found     : *{contacts}*\n"
        f"Emails sent        : *{emails}*\n"
        f"Email drafts       : *{drafts}*\n"
        f"Currently selected : *{len(_state['selected_ids'])}*"
    )


def _trigger_apply_pipeline(say) -> None:
    selected = list(_state["selected_ids"])
    if not selected:
        say(":warning: No jobs selected. Use `/jobs` to pick some first.")
        return

    ids_arg = ",".join(str(i) for i in selected)
    say(
        f":rocket: Starting pipeline for *{len(selected)}* selected jobs…\n"
        f"Phase 2 (tailor) → Phase 4 (submit ATS) → Phase 3 (find contacts) → cold emails.\n"
        f"Cold emails only send *after* each application is confirmed submitted.\n"
        f"I'll ping you at every step. Job IDs: `{ids_arg}`"
    )
    # Phase order: tailor → ATS submit → find contacts/draft emails → send cold emails
    subprocess.Popen(
        ["python", "main.py", "--phase", "2,4,3,send", "--job-ids", ids_arg],
        cwd="/app",
    )


# ── Slack Bot factory ─────────────────────────────────────────────────────────

def build_app() -> "App":
    if not _SDK_OK:
        raise ImportError(
            "slack-bolt not installed. Add 'slack-bolt' to requirements.txt "
            "and rebuild the Docker image."
        )

    app = App(token=config.SLACK_BOT_TOKEN)

    # ── /jobs ─────────────────────────────────────────────────────────────────
    @app.command("/jobs")
    def cmd_jobs(ack, respond):
        ack()
        if not _state["scored_jobs"] or time.time() - _state["last_refresh"] > 300:
            respond(":hourglass: Scoring jobs against your resume…")
            _refresh_jobs()
        respond(blocks=_job_list_blocks(), text="Top jobs")

    # ── /apply ────────────────────────────────────────────────────────────────
    @app.command("/apply")
    def cmd_apply(ack, respond):
        ack()
        _trigger_apply_pipeline(respond)

    # ── /stats ────────────────────────────────────────────────────────────────
    @app.command("/stats")
    def cmd_stats(ack, respond):
        ack()
        respond(_stats_text())

    # ── /scrape ───────────────────────────────────────────────────────────────
    @app.command("/scrape")
    def cmd_scrape(ack, respond):
        ack()
        respond(":mag: Starting Phase 1 job scrape in background…\nI'll notify you when done.")
        subprocess.Popen(
            ["python", "main.py", "--phase", "1", "--pages", "5"],
            cwd="/app",
        )

    # ── /reset ────────────────────────────────────────────────────────────────
    @app.command("/reset")
    def cmd_reset(ack, respond):
        ack()
        _state["selected_ids"].clear()
        respond(":white_check_mark: All selections cleared.")

    # ── /help ─────────────────────────────────────────────────────────────────
    @app.command("/help")
    def cmd_help(ack, respond):
        ack()
        respond(
            ":robot_face: *Job Hunt Bot*\n\n"
            "`/jobs`   — Top 20 ATS-scored jobs to select\n"
            "`/apply`  — Run Claude pipeline + send cold emails for selected jobs\n"
            "`/stats`  — Stats dashboard\n"
            "`/scrape` — Kick off a fresh LinkedIn scrape (Phase 1)\n"
            "`/reset`  — Clear all current selections\n\n"
            "_Only jobs scoring ≥80/100 on ATS are shown. "
            "Claude runs only on jobs you select — saves credits._"
        )

    # ── Multi-select dropdown changed ─────────────────────────────────────────
    @app.action("select_jobs")
    def action_select(ack, body):
        ack()
        selected_opts = (
            body.get("actions", [{}])[0].get("selected_options", [])
        )
        _state["selected_ids"] = {int(o["value"]) for o in selected_opts}
        logger.info("Selected job IDs: %s", _state["selected_ids"])

    # ── Apply button ──────────────────────────────────────────────────────────
    @app.action("apply_selected")
    def action_apply(ack, say):
        ack()
        _trigger_apply_pipeline(say)

    # ── Stats button ──────────────────────────────────────────────────────────
    @app.action("get_stats")
    def action_stats(ack, say):
        ack()
        say(_stats_text())

    # ── Clear button ──────────────────────────────────────────────────────────
    @app.action("clear_selections")
    def action_clear(ack, say):
        ack()
        _state["selected_ids"].clear()
        say(":wastebasket: Selections cleared. Use `/jobs` to re-select.")

    # ── Refresh button ────────────────────────────────────────────────────────
    @app.action("refresh_jobs")
    def action_refresh(ack, respond):
        ack()
        respond(":arrows_counterclockwise: Re-scoring jobs…")
        _refresh_jobs()
        respond(blocks=_job_list_blocks(), text="Top jobs (refreshed)")

    # ── "Pick Jobs to Apply" button from scrape-done notification ─────────────
    @app.action("notify_open_jobs")
    def action_notify_open_jobs(ack, say):
        ack()
        if not _state["scored_jobs"] or time.time() - _state["last_refresh"] > 300:
            say(":hourglass: Scoring jobs against your resume…")
            _refresh_jobs()
        say(blocks=_job_list_blocks(), text="Top jobs — pick which ones to apply to")

    return app


# ── Public notify helper (called from main.py after phase 1) ─────────────────

def notify_new_jobs(count: int, top_jobs: list[dict]) -> None:
    """Post a rich new-jobs notification to the configured Slack channel."""
    if not config.SLACK_BOT_TOKEN or not config.SLACK_CHANNEL_ID:
        return
    try:
        from slack_sdk import WebClient
        client = WebClient(token=config.SLACK_BOT_TOKEN)

        # Build top-picks text
        lines = []
        for i, item in enumerate(top_jobs[:5], 1):
            j = item["job"]
            grade = item.get("ats_grade", "")
            lines.append(
                f"{i}. *{j['role']}* @ {j['company']}  "
                f"ATS: *{item['ats_score']}/100* ({grade})"
            )
        picks_text = "\n".join(lines) if lines else "_No scored jobs yet_"

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f":new: Scrape Complete — {count} new jobs found!",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Top picks (ATS ≥ 80):*\n{picks_text}",
                },
            },
            {"type": "divider"},
            {
                "type": "actions",
                "elements": [
                    {
                        "type":      "button",
                        "text":      {"type": "plain_text", "text": ":dart: Pick Jobs to Apply", "emoji": True},
                        "style":     "primary",
                        "action_id": "notify_open_jobs",
                    },
                    {
                        "type":      "button",
                        "text":      {"type": "plain_text", "text": ":bar_chart: Stats", "emoji": True},
                        "action_id": "get_stats",
                    },
                ],
            },
        ]

        client.chat_postMessage(
            channel=config.SLACK_CHANNEL_ID,
            text=f"Scrape complete — {count} new jobs found! Use /jobs to select.",
            blocks=blocks,
        )
    except Exception as exc:
        logger.warning("Slack notify_new_jobs failed: %s", exc)


def send_message(text: str) -> None:
    """Send a plain text message to the configured channel (used by main.py)."""
    if not config.SLACK_BOT_TOKEN or not config.SLACK_CHANNEL_ID:
        return
    try:
        from slack_sdk import WebClient
        client = WebClient(token=config.SLACK_BOT_TOKEN)
        client.chat_postMessage(channel=config.SLACK_CHANNEL_ID, text=text)
    except Exception as exc:
        logger.warning("Slack send_message failed: %s", exc)


# ── Entry point ───────────────────────────────────────────────────────────────

def run_bot() -> None:
    if not config.SLACK_BOT_TOKEN:
        logger.error("SLACK_BOT_TOKEN not set in .env — bot cannot start")
        return
    if not config.SLACK_APP_TOKEN:
        logger.error("SLACK_APP_TOKEN not set in .env — Socket Mode requires xapp-... token")
        return
    if not config.SLACK_CHANNEL_ID:
        logger.warning("SLACK_CHANNEL_ID not set — notifications will be skipped")

    init_db()
    app = build_app()

    # Announce online
    send_message(
        ":white_check_mark: *Job Hunt Bot online!*\n"
        "Use `/jobs` to see top scored jobs, `/help` for all commands."
    )

    logger.info("Starting Slack bot in Socket Mode…")
    handler = SocketModeHandler(app, config.SLACK_APP_TOKEN)
    handler.start()


if __name__ == "__main__":
    run_bot()
