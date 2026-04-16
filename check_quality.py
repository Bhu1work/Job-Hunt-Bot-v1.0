"""Quick quality audit of DB content."""
from database import get_db, init_db
init_db()
with get_db() as c:
    # Cover letter sample
    row = c.execute(
        "SELECT job_id, resume_bullets, cover_letter FROM tailored_docs WHERE job_id=1"
    ).fetchone()
    if row:
        print("=== COVER LETTER (job 1) ===")
        print(row["cover_letter"] or "(empty)")
        print()
        print("=== RESUME BULLETS (job 1, first 1500) ===")
        print((row["resume_bullets"] or "")[:1500])

    # Sample cold email
    rows = c.execute(
        "SELECT subject, body, status "
        "FROM outreach WHERE outreach_type='cold_email' AND job_id=1 LIMIT 3"
    ).fetchall()
    for r in rows:
        print(f"\n=== EMAIL (status={r['status']}) ===")
        print("Subject:", r["subject"])
        print("Body:", (r["body"] or "")[:800])
