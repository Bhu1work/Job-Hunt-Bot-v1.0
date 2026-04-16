"""
ARCHIVED — Telegram Bot (replaced by slack_bot.py).

This file is kept for reference only. The active bot is slack_bot.py.
Do not import or run this file — config.TELEGRAM_BOT_TOKEN no longer exists.
"""
# ruff: noqa
raise ImportError(
    "telegram_bot.py is archived. Use slack_bot.py instead.\n"
    "Run: docker compose up -d slack"
)


# ── Telegram API helpers ──────────────────────────────────────────────────────

def _api(method: str, **kwargs) -> dict:
    try:
        r = requests.post(f"{BASE_URL}/{method}", json=kwargs, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        logger.error("Telegram API %s failed: %s", method, exc)
        return {}


def send_message(text: str, chat_id: str | None = None,
                 reply_markup: dict | None = None,
                 parse_mode: str = "HTML") -> dict:
    payload: dict[str, Any] = {
        "chat_id": chat_id or config.TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return _api("sendMessage", **payload)


def edit_message(message_id: int, text: str,
                 reply_markup: dict | None = None,
                 chat_id: str | None = None) -> dict:
    payload: dict[str, Any] = {
        "chat_id": chat_id or config.TELEGRAM_CHAT_ID,
        "message_id": message_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return _api("editMessageText", **payload)


def answer_callback(callback_id: str, text: str = "") -> None:
    _api("answerCallbackQuery", callback_query_id=callback_id, text=text)


def get_updates(offset: int = 0) -> list[dict]:
    resp = _api("getUpdates", offset=offset, timeout=30, allowed_updates=["message", "callback_query"])
    return resp.get("result", [])


# ── Job list builder ──────────────────────────────────────────────────────────

def _build_job_list_message(scored_jobs: list[dict],
                             selected_ids: set[int]) -> tuple[str, dict]:
    """Build message text + inline keyboard for job selection."""
    if not scored_jobs:
        return ("No pending jobs found above the ATS threshold.\n"
                "Run: <code>docker compose run --rm scraper</code> first.", {})

    lines = ["<b>🎯 Top Jobs — tap to select for applying</b>\n"]
    buttons = []
    row = []

    for i, item in enumerate(scored_jobs[:20], 1):
        job = item["job"]
        jid = job["id"]
        score = item["ats_score"]
        grade = item["ats_grade"]
        company = job["company"][:18]
        role = job["role"][:30]
        selected = jid in selected_ids
        checkbox = "✅" if selected else "⬜"

        lines.append(
            f"{i}. {checkbox} <b>{role}</b> @ {company}\n"
            f"   ATS: <b>{score}/100</b> ({grade})  "
            f"Missing: {', '.join(item['missing_keywords'][:3]) or 'none'}"
        )

        btn = {
            "text": f"{'✅' if selected else '⬜'} {i}. {company[:12]} ({score})",
            "callback_data": f"toggle:{jid}"
        }
        row.append(btn)
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    # Action buttons
    buttons.append([
        {"text": "🚀 Apply to Selected", "callback_data": "action:apply"},
        {"text": "🗑 Clear All", "callback_data": "action:clear"},
    ])
    buttons.append([
        {"text": "📊 Stats", "callback_data": "action:stats"},
        {"text": "🔄 Refresh", "callback_data": "action:refresh"},
    ])

    text = "\n".join(lines)
    markup = {"inline_keyboard": buttons}
    return text, markup


def _get_stats_text() -> str:
    with get_db() as c:
        total    = c.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        h1b      = c.execute("SELECT COUNT(*) FROM jobs WHERE h1b_confirmed=1").fetchone()[0]
        pending  = c.execute("SELECT COUNT(*) FROM jobs WHERE applied_status='pending' AND h1b_confirmed=1").fetchone()[0]
        applied  = c.execute("SELECT COUNT(*) FROM jobs WHERE applied_status='applied'").fetchone()[0]
        emails   = c.execute("SELECT COUNT(*) FROM outreach WHERE status='sent'").fetchone()[0]
        drafts   = c.execute("SELECT COUNT(*) FROM outreach WHERE status='draft'").fetchone()[0]
        contacts = c.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]
    return (
        f"<b>📊 Job Hunt Stats</b>\n\n"
        f"Total jobs scraped: <b>{total}</b>\n"
        f"H1B-confirmed:      <b>{h1b}</b>\n"
        f"Pending (ready):    <b>{pending}</b>\n"
        f"Applied:            <b>{applied}</b>\n"
        f"Contacts found:     <b>{contacts}</b>\n"
        f"Emails sent:        <b>{emails}</b>\n"
        f"Email drafts:       <b>{drafts}</b>"
    )


# ── Command handlers ──────────────────────────────────────────────────────────

_state: dict = {
    "scored_jobs": [],
    "selected_ids": set(),
    "list_message_id": None,
    "last_refresh": 0.0,
}


def _refresh_jobs(threshold: int = 80) -> None:
    logger.info("Scoring jobs (ATS threshold=%d)...", threshold)
    scored = score_all_pending_jobs(threshold=threshold)
    _state["scored_jobs"] = scored
    _state["last_refresh"] = time.time()
    logger.info("Scored %d jobs above threshold", len(scored))


def handle_command(text: str, chat_id: str) -> None:
    cmd = text.strip().lower().split()[0]

    if cmd in ("/start", "/help"):
        send_message(
            "<b>🤖 Job Hunt Bot</b>\n\n"
            "/jobs   — Show top 20 ATS-scored jobs to select\n"
            "/apply  — Apply + email all selected jobs\n"
            "/status — Stats dashboard\n"
            "/scrape — Trigger a fresh job scrape\n"
            "/reset  — Clear all selections\n\n"
            "<i>Tip: jobs scoring ≥80/100 are shown. Claude only runs on selected jobs — saves credits.</i>",
            chat_id=chat_id
        )

    elif cmd == "/jobs":
        if not _state["scored_jobs"] or time.time() - _state["last_refresh"] > 300:
            send_message("⏳ Scoring jobs against your resume...", chat_id=chat_id)
            _refresh_jobs()
        text_msg, markup = _build_job_list_message(
            _state["scored_jobs"], _state["selected_ids"]
        )
        resp = send_message(text_msg, chat_id=chat_id, reply_markup=markup)
        if resp.get("ok"):
            _state["list_message_id"] = resp["result"]["message_id"]

    elif cmd == "/status":
        send_message(_get_stats_text(), chat_id=chat_id)

    elif cmd == "/apply":
        _trigger_apply(chat_id)

    elif cmd == "/scrape":
        send_message("🔍 Starting job scrape in background...\n"
                     "I'll notify you when done.", chat_id=chat_id)
        import subprocess
        subprocess.Popen(
            ["python", "main.py", "--phase", "1", "--pages", "5"],
            cwd="/app"
        )

    elif cmd == "/reset":
        _state["selected_ids"].clear()
        send_message("✅ Selections cleared.", chat_id=chat_id)
        if _state["list_message_id"]:
            text_msg, markup = _build_job_list_message(
                _state["scored_jobs"], _state["selected_ids"]
            )
            edit_message(_state["list_message_id"], text_msg,
                         reply_markup=markup, chat_id=chat_id)

    else:
        send_message("Unknown command. Send /help", chat_id=chat_id)


def handle_callback(callback: dict) -> None:
    cid   = callback["id"]
    chat_id = str(callback["message"]["chat"]["id"])
    data  = callback.get("data", "")
    msg_id = callback["message"]["message_id"]

    if data.startswith("toggle:"):
        job_id = int(data.split(":")[1])
        if job_id in _state["selected_ids"]:
            _state["selected_ids"].discard(job_id)
            answer_callback(cid, "⬜ Deselected")
        else:
            _state["selected_ids"].add(job_id)
            answer_callback(cid, "✅ Selected")
        # Update the message to reflect new selections
        text_msg, markup = _build_job_list_message(
            _state["scored_jobs"], _state["selected_ids"]
        )
        edit_message(msg_id, text_msg, reply_markup=markup, chat_id=chat_id)

    elif data == "action:apply":
        answer_callback(cid, "🚀 Starting apply pipeline...")
        _trigger_apply(chat_id)

    elif data == "action:clear":
        _state["selected_ids"].clear()
        answer_callback(cid, "🗑 Cleared")
        text_msg, markup = _build_job_list_message(
            _state["scored_jobs"], _state["selected_ids"]
        )
        edit_message(msg_id, text_msg, reply_markup=markup, chat_id=chat_id)

    elif data == "action:refresh":
        answer_callback(cid, "🔄 Refreshing...")
        _refresh_jobs()
        text_msg, markup = _build_job_list_message(
            _state["scored_jobs"], _state["selected_ids"]
        )
        edit_message(msg_id, text_msg, reply_markup=markup, chat_id=chat_id)

    elif data == "action:stats":
        answer_callback(cid)
        send_message(_get_stats_text(), chat_id=chat_id)


def _trigger_apply(chat_id: str) -> None:
    selected = list(_state["selected_ids"])
    if not selected:
        send_message("⚠️ No jobs selected. Use /jobs to select jobs first.", chat_id=chat_id)
        return

    send_message(
        f"🚀 Starting pipeline for <b>{len(selected)}</b> selected jobs...\n"
        f"Phase 2 (Claude tailor) → Phase 3 (email find) → send cold emails.\n"
        f"I'll update you when done.",
        chat_id=chat_id
    )

    import subprocess
    ids_arg = ",".join(str(i) for i in selected)
    subprocess.Popen(
        ["python", "main.py", "--phase", "2,3,send",
         "--job-ids", ids_arg],
        cwd="/app"
    )


def notify_new_jobs(count: int, top_jobs: list[dict]) -> None:
    """Send notification about newly scraped jobs to configured chat."""
    if not config.TELEGRAM_CHAT_ID:
        return
    lines = [f"🆕 <b>{count} new jobs scraped!</b> Top picks:\n"]
    for item in top_jobs[:5]:
        j = item["job"]
        lines.append(
            f"• <b>{j['role']}</b> @ {j['company']} "
            f"[ATS: {item['ats_score']}/100]"
        )
    lines.append("\nSend /jobs to select which to apply to.")
    send_message("\n".join(lines))


# ── Main polling loop ─────────────────────────────────────────────────────────

def run_bot() -> None:
    if not config.TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not set in .env — bot cannot start")
        return
    if not config.TELEGRAM_CHAT_ID:
        logger.error("TELEGRAM_CHAT_ID not set in .env — bot cannot send messages")
        return

    init_db()
    logger.info("Telegram bot starting (long-polling)...")
    send_message(
        "✅ <b>Job Hunt Bot online!</b>\n\n"
        "Send /jobs to see top scored jobs.\nSend /help for all commands."
    )

    offset = 0
    while True:
        try:
            updates = get_updates(offset=offset)
            for update in updates:
                offset = update["update_id"] + 1
                if "message" in update:
                    msg = update["message"]
                    if "text" in msg:
                        handle_command(
                            msg["text"],
                            chat_id=str(msg["chat"]["id"])
                        )
                elif "callback_query" in update:
                    handle_callback(update["callback_query"])
        except Exception as exc:
            logger.error("Bot loop error: %s", exc)
            time.sleep(5)


if __name__ == "__main__":
    run_bot()
