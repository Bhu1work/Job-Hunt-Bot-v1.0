"""
Purge AI-placeholder cold emails from the DB and regenerate them
with the fixed prompts + real resume.

Run:  docker compose run --rm bot python fix_emails.py
"""
import logging
from database import get_db, init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

PLACEHOLDER_MARKERS = [
    "PASTE YOUR FULL RESUME",
    "placeholder text",
    "[SPECIFIC ACHIEVEMENT",
    "[X]",
    "[your",
    "[company]",
    "[specific",
    "[relevant",
    "insert your",
    "I notice",          # Claude's meta-commentary
    "I'll need your",
    "Please paste",
    "Please provide",
    "I'd be happy to help",
    "I couldn't tailor",
    "don't have my resume details",
    "don't have your resume",
    "Paste your resume",
    "fill in the specifics",
    "e.g.,",             # template examples left in
    "I don't have",
    "Acme Corp",         # Claude's hallucinated company when resume was placeholder
    "At [",              # [Company], [Role] etc
]


def is_bad_email(body: str) -> bool:
    if not body:
        return True
    body_lower = body.lower()
    return any(m.lower() in body_lower for m in PLACEHOLDER_MARKERS)


def purge_bad_emails() -> int:
    """Delete outreach rows with placeholder/bad content. Returns count deleted."""
    with get_db() as c:
        rows = c.execute(
            "SELECT id, body, subject FROM outreach WHERE outreach_type='cold_email'"
        ).fetchall()

        bad_ids = [r["id"] for r in rows if is_bad_email(r["body"])]
        if bad_ids:
            c.execute(
                f"DELETE FROM outreach WHERE id IN ({','.join('?' * len(bad_ids))})",
                bad_ids
            )
        logger.info("Purged %d / %d cold emails (bad placeholder content)",
                    len(bad_ids), len(rows))
        return len(bad_ids)


def purge_bad_subjects() -> int:
    """Fix subject lines that start with ] (parser bug). Returns count fixed."""
    with get_db() as c:
        rows = c.execute(
            "SELECT id, subject FROM outreach WHERE subject LIKE '] %'"
        ).fetchall()
        fixed = 0
        for r in rows:
            clean = r["subject"].lstrip("] ").strip()
            c.execute("UPDATE outreach SET subject=? WHERE id=?", (clean, r["id"]))
            fixed += 1
        logger.info("Fixed %d subject lines with leading ]", fixed)
        return fixed


def regenerate_emails(limit: int | None = None) -> int:
    """Regenerate cold emails for all jobs that now have no outreach rows."""
    from phase3_email_finder import run as p3_run
    from database import get_pending_jobs

    # Jobs with contacts but no cold emails left
    with get_db() as c:
        rows = c.execute("""
            SELECT DISTINCT ct.job_id
            FROM contacts ct
            WHERE ct.job_id IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM outreach o
                  WHERE o.job_id = ct.job_id
                    AND o.outreach_type = 'cold_email'
              )
        """).fetchall()

    job_ids = [r[0] for r in rows]
    if limit:
        job_ids = job_ids[:limit]

    logger.info("Regenerating emails for %d jobs...", len(job_ids))
    for jid in job_ids:
        try:
            p3_run(job_id=jid, skip_email_lookup=True)  # skip Hunter/Apollo, just regenerate
        except Exception as e:
            logger.error("Failed job %d: %s", jid, e)
    return len(job_ids)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--regen", action="store_true",
                        help="Also regenerate emails after purge (requires working Claude API)")
    args = parser.parse_args()

    init_db()
    purged = purge_bad_emails()
    fixed  = purge_bad_subjects()
    print(f"\nResult: {purged} bad emails purged, {fixed} subject lines fixed.")

    if purged > 0 and args.regen:
        logger.info("Regenerating cold emails with fixed prompts + real resume...")
        try:
            n = regenerate_emails()
            logger.info("Done. Regenerated emails for %d jobs.", n)
        except (SystemExit, Exception) as e:
            logger.error("Regeneration failed (Claude API issue?): %s", e)
            logger.info("Add credits at https://console.anthropic.com/billing then re-run with --regen")
    elif purged > 0:
        logger.info("Emails purged. Once you top up Claude credits, run:")
        logger.info("  docker compose run --rm bot python fix_emails.py --regen")
    else:
        logger.info("No bad emails found. DB is clean.")
