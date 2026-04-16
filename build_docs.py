"""Build DOCX/PDF application docs for all jobs that have tailored content."""
from database import init_db, get_pending_jobs
from application_manager import build_application_docs

init_db()
jobs = get_pending_jobs()
print(f"Building DOCX/PDF for {len(jobs)} jobs...")
ok = 0
for job in jobs:
    try:
        paths = build_application_docs(job["id"])
        status = "PDF" if paths.get("pdf") else "DOCX"
        print(f"  [{job['id']}] {status} - {job['role']} @ {job['company']}")
        ok += 1
    except Exception as e:
        print(f"  SKIP [{job['id']}]: {e}")

print(f"\nDone. {ok}/{len(jobs)} resume files generated.")
