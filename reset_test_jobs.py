"""
reset_test_jobs.py — Wipe yesterday's test run, start fresh.

Resets:
  - All jobs applied before today → applied_status = 'pending', selected = 0
  - All outreach rows sent before today → status = 'draft'
  - Clears cold_email / cover_letter tailored docs so they regenerate cleanly

Usage:
  docker compose run --rm bot python reset_test_jobs.py
  docker compose run --rm bot python reset_test_jobs.py --dry-run
"""

import argparse
from datetime import date

from database import get_db, init_db


def reset(dry_run: bool = False) -> None:
    today = date.today().isoformat()  # e.g. "2026-04-15"
    tag = "[DRY-RUN] " if dry_run else ""

    init_db()
    with get_db() as c:
        # ── Jobs reset ────────────────────────────────────────────────────────
        rows = c.execute(
            """
            SELECT id, company, role, applied_status
            FROM jobs
            WHERE applied_status IN ('applied', 'applying', 'failed')
            """,
        ).fetchall()

        print(f"\n{tag}Jobs to reset ({len(rows)} rows):")
        for r in rows:
            print(f"  #{r['id']}  {r['company']} — {r['role']}  [{r['applied_status']}]")

        if not dry_run:
            c.execute(
                """
                UPDATE jobs
                SET applied_status = 'pending',
                    selected        = 0
                WHERE applied_status IN ('applied', 'applying', 'failed')
                """
            )
            # Also clear the 'selected' flag on everything
            c.execute("UPDATE jobs SET selected = 0")

        # ── Outreach reset ───────────────────────────────────────────────────
        out_rows = c.execute(
            """
            SELECT id, job_id, status, sent_at
            FROM outreach
            WHERE status = 'sent'
            """,
        ).fetchall()

        print(f"\n{tag}Outreach rows to reset to 'draft' ({len(out_rows)} rows):")
        for r in out_rows:
            print(f"  outreach #{r['id']}  job_id={r['job_id']}  sent_at={r['sent_at']}")

        if not dry_run:
            c.execute("UPDATE outreach SET status = 'draft' WHERE status = 'sent'")

        # ── Tailored docs: clear cold email body so it regenerates ───────────
        td_rows = c.execute(
            "SELECT COUNT(*) FROM tailored_docs"
        ).fetchone()[0]
        print(f"\n{tag}Tailored docs found: {td_rows} (leaving intact — use fix_emails.py --regen if needed)")

        if not dry_run:
            print("\n✅ Reset complete. All test applications wiped. Run fresh pipeline now.")
        else:
            print("\n[DRY-RUN] Nothing changed. Remove --dry-run to apply.")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Reset test job applications")
    p.add_argument("--dry-run", action="store_true",
                   help="Preview changes without writing to DB")
    args = p.parse_args()
    reset(dry_run=args.dry_run)
