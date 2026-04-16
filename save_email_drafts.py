"""Save all email drafts to per-application folders after Phase 3."""
from database import init_db, get_pending_jobs
from application_manager import save_email_drafts

init_db()
jobs = get_pending_jobs()
print(f"Saving email drafts for {len(jobs)} jobs...")
for job in jobs:
    try:
        save_email_drafts(job["id"])
    except Exception as e:
        print(f"  SKIP [{job['id']}]: {e}")
print("Done.")
