from database import get_db, init_db
init_db()
with get_db() as c:
    rows = c.execute("SELECT id, status, body FROM outreach WHERE outreach_type='cold_email'").fetchall()
    total = len(rows)
    by_status = {}
    for r in rows:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
    print(f"Total: {total}, By status: {dict(by_status)}")
    
    # Sample good email
    good = [r for r in rows if r["status"] == "sent" and r["body"] and "e.g.," not in r["body"] and "[company]" not in r["body"].lower()]
    if good:
        print(f"\n=== SAMPLE GOOD EMAIL ===")
        print("Body:", good[0]["body"][:500])
    
    # Check for remaining bad emails
    from fix_emails import PLACEHOLDER_MARKERS, is_bad_email
    bad = [r for r in rows if is_bad_email(r["body"] or "")]
    print(f"\nBad emails still in DB: {len(bad)}")
    for r in bad[:5]:
        print(f"  [{r['id']}] status={r['status']}  snippet='{(r['body'] or '')[:60]}'")
