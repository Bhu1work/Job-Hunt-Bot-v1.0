"""
Audit tool — reads all sent applications: cover letter, resume bullets, cold emails.
Run: docker compose run --rm bot python audit.py [--job-id N] [--full]
"""
import argparse
from database import get_db, init_db

def show_job(job_id: int, full: bool = False) -> None:
    with get_db() as c:
        job = c.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not job:
            print(f"Job {job_id} not found")
            return
        
        docs = c.execute(
            "SELECT * FROM tailored_docs WHERE job_id=?", (job_id,)
        ).fetchone()
        
        emails = c.execute(
            "SELECT o.*, ct.name as contact_name, ct.email as contact_email, "
            "ct.contact_type "
            "FROM outreach o "
            "JOIN contacts ct ON ct.id = o.contact_id "
            "WHERE o.job_id=? AND o.outreach_type='cold_email'",
            (job_id,),
        ).fetchall()

    print(f"\n{'='*70}")
    print(f"JOB {job_id}: {job['role']} @ {job['company']}")
    print(f"URL: {job['jd_url']}")
    print(f"H1B: {bool(job['h1b_confirmed'])}  |  Status: {job['applied_status']}")
    print(f"{'='*70}")

    if docs:
        if full or True:
            print("\n--- COVER LETTER ---")
            print(docs['cover_letter'] or "(empty)")
            print("\n--- RESUME BULLETS (first 1200 chars) ---")
            print((docs['resume_bullets'] or "(empty)")[:1200 if not full else 99999])
    else:
        print("  (no tailored docs in DB)")

    if emails:
        print(f"\n--- COLD EMAILS SENT ({len(emails)}) ---")
        for e in emails:
            status = dict(e).get('status', '?')
            print(f"\n  To: {e['contact_name']} <{e['contact_email']}> [{e['contact_type']}]")
            print(f"  Status: {status}")
            print(f"  Subject: {e['subject']}")
            print(f"  Body:\n    " + (e['body'] or '').replace('\n', '\n    ')[:800 if not full else 99999])
    else:
        print("\n  (no cold emails for this job)")


def main():
    parser = argparse.ArgumentParser(description="Audit sent applications")
    parser.add_argument("--job-id", type=int, help="Show specific job")
    parser.add_argument("--full", action="store_true", help="Show full text")
    parser.add_argument("--emails-only", action="store_true", help="Show sent emails only")
    parser.add_argument("--limit", type=int, default=5, help="Number of jobs to show")
    args = parser.parse_args()

    init_db()
    with get_db() as c:
        if args.emails_only:
            rows = c.execute(
                "SELECT o.job_id, o.subject, o.body, o.status, "
                "ct.name, ct.email, j.role, j.company "
                "FROM outreach o "
                "JOIN contacts ct ON ct.id=o.contact_id "
                "JOIN jobs j ON j.id=o.job_id "
                "WHERE o.outreach_type='cold_email' "
                "ORDER BY o.id DESC LIMIT ?", (args.limit * 10,)
            ).fetchall()
            print(f"\n=== COLD EMAILS ({len(rows)}) ===")
            for r in rows:
                print(f"\n[job {r['job_id']}] {r['role']} @ {r['company']}")
                print(f"  To: {r['name']} <{r['email']}> | Status: {r['status']}")
                print(f"  Subject: {r['subject']}")
                print(f"  ---\n  " + (r['body'] or '')[:600].replace('\n', '\n  '))
            return

        if args.job_id:
            show_job(args.job_id, full=args.full)
            return

        # Show all applied jobs
        jobs = c.execute(
            "SELECT id, role, company, applied_status FROM jobs "
            "WHERE h1b_confirmed=1 ORDER BY id LIMIT ?", (args.limit,)
        ).fetchall()
        print(f"\n{'='*70}")
        print(f" APPLICATIONS SUMMARY ({len(jobs)} shown)")
        print(f"{'='*70}")
        for j in jobs:
            print(f"  [{j['id']:4d}] {j['role'][:40]:40s} @ {j['company'][:25]:25s} [{j['applied_status']}]")
        
        print(f"\nTo inspect a specific job: python audit.py --job-id N --full")
        print(f"To see all emails:          python audit.py --emails-only --limit 30")


if __name__ == "__main__":
    main()
