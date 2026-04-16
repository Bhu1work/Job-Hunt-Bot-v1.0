"""
reset_all.py — Wipe all data and start completely fresh.

Clears every table (jobs, companies, tailored_docs, contacts, outreach,
activity_log) and resets all auto-increment counters.
The DB schema (tables) is kept so the app boots normally.
"""
import sqlite3
from pathlib import Path

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

print("\nDone — database wiped. Run /scrape to start fresh.")
