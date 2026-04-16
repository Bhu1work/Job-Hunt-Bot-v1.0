"""
reset_all.py — Wipe all data and start completely fresh.

Clears every table (jobs, companies, tailored_docs, contacts, outreach,
activity_log) and resets all auto-increment counters, then immediately
re-seeds the H1B company list so /scrape works straight away.
"""
import sqlite3
import subprocess
import sys

DB_PATH = "data/jobs.db"

TABLES = [
    "outreach",
    "tailored_docs",
    "contacts",
    "activity_log",
    "jobs",
    "companies",
]

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

c.execute("PRAGMA foreign_keys=OFF")
for table in TABLES:
    c.execute(f"DELETE FROM {table}")
    c.execute(f"DELETE FROM sqlite_sequence WHERE name='{table}'")
    print(f"  cleared  {table}")

c.execute("PRAGMA foreign_keys=ON")
conn.commit()
conn.close()

print("\nDatabase wiped. Re-seeding H1B companies...")
import runpy
runpy.run_path("seed_h1b.py", run_name="__main__")
print("\nDone — fresh start ready. Run /scrape in Slack to find new jobs.")
