"""
main.py — Job Hunt Bot Orchestrator

Runs all phases in sequence, or selectively by flag.

Usage:
    python main.py --all                  # Full pipeline (day-1 blitz)
    python main.py --phase 1              # Scrape only
    python main.py --phase 2              # Tailor resumes only
    python main.py --phase 3              # Find emails only
    python main.py --phase 4              # Auto-apply only
    python main.py --phase 5 --daemon     # Start follow-up scheduler
    python main.py --stats                # Print current stats
    python main.py --gaps                 # Print email gaps report
    python main.py --referrals --company "Stripe" --role "Software Engineer"
"""

import argparse
import logging
import sys
import time

import config
from database import init_db, get_stats, log_event

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/main.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


def banner() -> None:
    print("""
╔══════════════════════════════════════════════════════╗
║           JOB HUNT BOT  —  H1B Edition              ║
║  Scrape → Tailor → Email → Apply → Follow Up        ║
╚══════════════════════════════════════════════════════╝
""")


def print_stats() -> None:
    stats = get_stats()
    print("\n── Current Stats ──────────────────────────────────")
    print(f"  Total jobs found   : {stats['total_jobs']}")
    print(f"  H1B confirmed      : {stats['h1b_jobs']}")
    print(f"  Applied            : {stats['applied']}")
    print(f"  Interviews         : {stats['interviews']}")
    print(f"  Emails sent        : {stats['emails_sent']}")
    print("────────────────────────────────────────────────────\n")


def run_phase1(args) -> None:
    logger.info("━━━ PHASE 1: Scraping jobs + H1B filter ━━━")
    from phase1_scraper import run as p1_run
    p1_run(
        field=args.field or config.YOUR_FIELD,
        location=args.location or "United States",
        pages=args.pages,
        fetch_descriptions=args.fetch_descriptions,
    )


def _parse_job_ids(args) -> list[int] | None:
    """Return list of job IDs from --job-ids arg, or None if not set."""
    if getattr(args, "job_ids", ""):
        return [int(x.strip()) for x in args.job_ids.split(",") if x.strip()]
    return None


def run_phase2(args) -> None:
    logger.info("━━━ PHASE 2: Tailoring resumes + cover letters ━━━")
    from phase2_resume_tailor import run as p2_run
    job_ids = _parse_job_ids(args)
    if job_ids:
        # Process each selected job individually
        logger.info("Processing %d selected jobs", len(job_ids))
        for jid in job_ids:
            p2_run(job_id=jid, force=getattr(args, "force", False))
    else:
        p2_run(
            job_id=args.job_id,
            force=getattr(args, "force", False),
            limit=args.limit,
        )


def run_phase3(args) -> None:
    logger.info("━━━ PHASE 3: Finding emails ━━━")
    from phase3_email_finder import run as p3_run
    p3_run(
        job_id=args.job_id,
        limit=args.limit,
    )


def run_phase4(args) -> None:
    logger.info("━━━ PHASE 4: Auto-applying ━━━")
    from phase4_auto_apply import run as p4_run
    p4_run(
        job_id=args.job_id,
        dry_run=getattr(args, "dry_run", False),
        limit=args.limit,
    )


def run_phase5(args) -> None:
    logger.info("━━━ PHASE 5: Follow-up scheduler ━━━")
    from phase5_followup import run_daemon, run_now
    if getattr(args, "daemon", False):
        run_daemon()
    else:
        run_now()


def run_all(args) -> None:
    """Full day-1 blitz pipeline."""
    banner()
    # Validate ALL keys upfront before spending time scraping
    config.validate_keys(require_claude=True, require_hunter=True, require_smtp=True)
    init_db()
    log_event("pipeline_start", f"field={args.field} location={args.location}")
    t0 = time.time()

    run_phase1(args)
    print_stats()

    run_phase2(args)
    run_phase3(args)
    run_phase4(args)

    elapsed = time.time() - t0
    log_event("pipeline_complete", f"elapsed={elapsed:.0f}s")
    logger.info("Pipeline complete in %.0fs", elapsed)
    print_stats()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Job Hunt Bot — H1B Edition",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Mode flags
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--all", action="store_true", help="Run full pipeline")
    group.add_argument("--phase", type=str,
                       help="Phase to run: 1, 2, 3, 4, 5  or  '2,3,send' for Telegram flow")
    group.add_argument("--stats", action="store_true", help="Print stats and exit")
    group.add_argument("--gaps", action="store_true",
                       help="Print companies with no email found")
    group.add_argument("--referrals", action="store_true",
                       help="Generate referral DMs for a company")
    group.add_argument("--dashboard", action="store_true",
                       help="Show all application folders and statuses")
    group.add_argument("--build-resumes", action="store_true",
                       help="Regenerate all 4 base resume DOCX+PDF files")
    group.add_argument("--send-emails", action="store_true",
                       help="Send all pending cold email drafts via Gmail")

    # Shared options
    parser.add_argument("--field", type=str, default="", help="Job field / title keyword")
    parser.add_argument("--location", type=str, default="United States")
    parser.add_argument("--pages", type=int, default=5, help="Pages per scrape source")
    parser.add_argument("--limit", type=int, default=None, help="Max jobs to process")
    parser.add_argument("--job-id", type=int, default=None, help="Single job ID")
    parser.add_argument("--job-ids", type=str, default="",
                        help="Comma-separated job IDs (from Slack selection)")
    parser.add_argument("--fetch-descriptions", action="store_true")
    parser.add_argument("--dry-run", action="store_true",
                        help="Phase 4: fill forms but don't submit")
    parser.add_argument("--daemon", action="store_true",
                        help="Phase 5: run as background scheduler")
    parser.add_argument("--force", action="store_true",
                        help="Phase 2: regenerate even if docs exist")
    parser.add_argument("--company", type=str, default="",
                        help="Company name for --referrals")
    parser.add_argument("--role", type=str, default="",
                        help="Role for --referrals")
    parser.add_argument("--ats-threshold", type=int, default=80,
                        help="Min ATS score to process (default 80)")

    args = parser.parse_args()

    init_db()
    banner()

    if args.stats:
        print_stats()

    elif args.dashboard:
        from application_manager import print_applications_dashboard
        print_applications_dashboard()

    elif args.build_resumes:
        from resume_builder import generate_all_base_resumes
        generate_all_base_resumes()

    elif args.send_emails:
        from phase5_followup import send_all_pending_cold_emails
        n = send_all_pending_cold_emails()
        print(f"Sent {n} cold emails from bhuvanthatthari@gmail.com")

    elif args.gaps:
        from phase3_email_finder import print_gap_report
        print_gap_report()

    elif args.referrals:
        if not args.company:
            parser.error("--company is required with --referrals")
        from phase4_auto_apply import print_referral_dms
        print_referral_dms(args.company, args.role or config.YOUR_FIELD)

    elif args.all:
        run_all(args)

    elif args.phase:
        phases = [p.strip() for p in args.phase.split(",")]
        for phase in phases:
            if phase == "1":
                run_phase1(args)
            elif phase == "2":
                run_phase2(args)
            elif phase == "3":
                run_phase3(args)
            elif phase == "4":
                run_phase4(args)
            elif phase == "5":
                run_phase5(args)
            elif phase == "send":
                # Send cold emails for selected/processed jobs
                from phase5_followup import send_all_pending_cold_emails
                job_ids = _parse_job_ids(args)
                if job_ids:
                    from phase5_followup import send_cold_emails_for_job
                    total = sum(send_cold_emails_for_job(jid) for jid in job_ids)
                else:
                    total = send_all_pending_cold_emails()
                logger.info("Sent %d cold emails", total)
                # Notify Slack if configured
                if config.SLACK_BOT_TOKEN and total > 0:
                    from slack_bot import send_message
                    send_message(f"✅ Sent *{total}* cold emails from {config.YOUR_EMAIL}")
            else:
                logger.warning("Unknown phase: %s", phase)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
