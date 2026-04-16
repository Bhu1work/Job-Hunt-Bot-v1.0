"""SQLite database layer — schema, CRUD helpers, and migrations."""

import sqlite3
import logging
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from config import DB_PATH

logger = logging.getLogger(__name__)


# ── Schema ────────────────────────────────────────────────────────────────────

DDL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS companies (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT    NOT NULL UNIQUE,
    h1b_confirmed   INTEGER NOT NULL DEFAULT 0,   -- 1 = confirmed sponsor
    h1b_source      TEXT,                          -- e.g. "myvisajobs", "manual"
    lca_count       INTEGER DEFAULT 0,
    domain          TEXT,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS jobs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    company         TEXT    NOT NULL,
    role            TEXT    NOT NULL,
    jd_url          TEXT    UNIQUE,
    source          TEXT,                          -- linkedin / indeed / myvisajobs
    location        TEXT,
    description     TEXT,
    h1b_confirmed   INTEGER NOT NULL DEFAULT 0,
    applied_status  TEXT    NOT NULL DEFAULT 'pending',
    -- pending | applied | rejected | interview | offer | declined
    applied_at      TEXT,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS tailored_docs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id          INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    resume_bullets  TEXT,
    cover_letter    TEXT,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS contacts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id          INTEGER REFERENCES jobs(id) ON DELETE SET NULL,
    company         TEXT    NOT NULL,
    name            TEXT,
    title           TEXT,
    email           TEXT,
    source          TEXT,                          -- hunter / apollo / manual
    contact_type    TEXT,                          -- hr / hiring_manager / team_lead / referral
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS outreach (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id          INTEGER REFERENCES jobs(id) ON DELETE CASCADE,
    contact_id      INTEGER REFERENCES contacts(id) ON DELETE CASCADE,
    outreach_type   TEXT    NOT NULL,              -- cold_email / referral_dm / followup
    subject         TEXT,
    body            TEXT,
    sent_at         TEXT,
    status          TEXT    NOT NULL DEFAULT 'draft',
    -- draft | scheduled | sent | replied | bounced
    followup_day    INTEGER,                       -- 3, 7, or 14
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS activity_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    event           TEXT    NOT NULL,
    detail          TEXT,
    job_id          INTEGER,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_jobs_company        ON jobs(company);
CREATE INDEX IF NOT EXISTS idx_jobs_status         ON jobs(applied_status);
CREATE INDEX IF NOT EXISTS idx_jobs_h1b            ON jobs(h1b_confirmed);
CREATE INDEX IF NOT EXISTS idx_contacts_company    ON contacts(company);
CREATE INDEX IF NOT EXISTS idx_outreach_job        ON outreach(job_id);
CREATE INDEX IF NOT EXISTS idx_outreach_status     ON outreach(status);
"""


# ── Connection helpers ────────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def get_db():
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Create tables and indexes if they don't exist yet. Runs safe migrations."""
    with get_db() as conn:
        conn.executescript(DDL)
        # Safe migrations for existing databases
        _migrate(conn)
    logger.info("Database initialised at %s", DB_PATH)


def _migrate(conn: sqlite3.Connection) -> None:
    """Add new columns to existing tables without breaking anything."""
    migrations = [
        ("jobs", "ats_score",       "ALTER TABLE jobs ADD COLUMN ats_score INTEGER DEFAULT 0"),
        ("jobs", "ats_grade",       "ALTER TABLE jobs ADD COLUMN ats_grade TEXT"),
        ("jobs", "selected",        "ALTER TABLE jobs ADD COLUMN selected INTEGER DEFAULT 0"),
    ]
    for table, col, sql in migrations:
        try:
            cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
            if col not in cols:
                conn.execute(sql)
                logger.info("Migration: added column %s.%s", table, col)
        except Exception as exc:
            logger.debug("Migration skip (%s.%s): %s", table, col, exc)


# ── Company helpers ───────────────────────────────────────────────────────────

def upsert_company(name: str, h1b_confirmed: bool = False,
                   h1b_source: str = "", lca_count: int = 0,
                   domain: str = "") -> int:
    sql = """
        INSERT INTO companies (name, h1b_confirmed, h1b_source, lca_count, domain)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(name) DO UPDATE SET
            h1b_confirmed = MAX(h1b_confirmed, excluded.h1b_confirmed),
            lca_count     = MAX(lca_count,     excluded.lca_count),
            h1b_source    = COALESCE(excluded.h1b_source, h1b_source),
            domain        = COALESCE(excluded.domain,     domain)
        RETURNING id
    """
    with get_db() as conn:
        row = conn.execute(sql, (name, int(h1b_confirmed), h1b_source, lca_count, domain)).fetchone()
        return row["id"]


def get_h1b_companies() -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM companies WHERE h1b_confirmed = 1 ORDER BY lca_count DESC"
        ).fetchall()
        return [dict(r) for r in rows]


# ── Job helpers ───────────────────────────────────────────────────────────────

def upsert_job(company: str, role: str, jd_url: str, source: str = "",
               location: str = "", description: str = "",
               h1b_confirmed: bool = False) -> int:
    sql = """
        INSERT INTO jobs (company, role, jd_url, source, location, description, h1b_confirmed)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(jd_url) DO UPDATE SET
            description   = COALESCE(excluded.description, description),
            h1b_confirmed = MAX(h1b_confirmed, excluded.h1b_confirmed),
            updated_at    = datetime('now')
        RETURNING id
    """
    with get_db() as conn:
        row = conn.execute(
            sql, (company, role, jd_url, source, location, description, int(h1b_confirmed))
        ).fetchone()
        return row["id"]


def get_pending_jobs() -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM jobs WHERE applied_status = 'pending' AND h1b_confirmed = 1"
        ).fetchall()
        return [dict(r) for r in rows]


def update_job_status(job_id: int, status: str) -> None:
    with get_db() as conn:
        conn.execute(
            "UPDATE jobs SET applied_status = ?, applied_at = datetime('now'), "
            "updated_at = datetime('now') WHERE id = ?",
            (status, job_id),
        )


def get_job(job_id: int) -> dict | None:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return dict(row) if row else None


# ── Tailored docs helpers ─────────────────────────────────────────────────────

def save_tailored_docs(job_id: int, resume_bullets: str, cover_letter: str) -> int:
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO tailored_docs (job_id, resume_bullets, cover_letter) VALUES (?, ?, ?)",
            (job_id, resume_bullets, cover_letter),
        )
        return cur.lastrowid


def get_tailored_docs(job_id: int) -> dict | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM tailored_docs WHERE job_id = ? ORDER BY created_at DESC LIMIT 1",
            (job_id,),
        ).fetchone()
        return dict(row) if row else None


# ── Contact helpers ───────────────────────────────────────────────────────────

def save_contact(company: str, name: str = "", title: str = "",
                 email: str = "", source: str = "", contact_type: str = "",
                 job_id: int | None = None) -> int:
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO contacts (job_id, company, name, title, email, source, contact_type) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (job_id, company, name, title, email, source, contact_type),
        )
        return cur.lastrowid


def get_contacts_for_job(job_id: int) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM contacts WHERE job_id = ?", (job_id,)
        ).fetchall()
        return [dict(r) for r in rows]


# ── Outreach helpers ──────────────────────────────────────────────────────────

def save_outreach(job_id: int, contact_id: int | None, outreach_type: str,
                  subject: str, body: str, followup_day: int | None = None) -> int:
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO outreach (job_id, contact_id, outreach_type, subject, body, "
            "followup_day) VALUES (?, ?, ?, ?, ?, ?)",
            (job_id, contact_id, outreach_type, subject, body, followup_day),
        )
        return cur.lastrowid


def mark_outreach_sent(outreach_id: int) -> None:
    with get_db() as conn:
        conn.execute(
            "UPDATE outreach SET status = 'sent', sent_at = datetime('now') WHERE id = ?",
            (outreach_id,),
        )


def get_due_followups(day: int) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT o.*, j.company, j.role FROM outreach o "
            "JOIN jobs j ON j.id = o.job_id "
            "WHERE o.outreach_type = 'followup' AND o.followup_day = ? AND o.status = 'draft'",
            (day,),
        ).fetchall()
        return [dict(r) for r in rows]


# ── Activity log ──────────────────────────────────────────────────────────────

def log_event(event: str, detail: str = "", job_id: int | None = None) -> None:
    with get_db() as conn:
        conn.execute(
            "INSERT INTO activity_log (event, detail, job_id) VALUES (?, ?, ?)",
            (event, detail, job_id),
        )


def get_today_activity() -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM activity_log WHERE date(created_at) = date('now') ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


# ── Stats ─────────────────────────────────────────────────────────────────────

def get_stats() -> dict:
    with get_db() as conn:
        total      = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        h1b        = conn.execute("SELECT COUNT(*) FROM jobs WHERE h1b_confirmed=1").fetchone()[0]
        applied    = conn.execute("SELECT COUNT(*) FROM jobs WHERE applied_status='applied'").fetchone()[0]
        interviews = conn.execute("SELECT COUNT(*) FROM jobs WHERE applied_status='interview'").fetchone()[0]
        emails_out = conn.execute("SELECT COUNT(*) FROM outreach WHERE status='sent'").fetchone()[0]
        return {
            "total_jobs": total,
            "h1b_jobs": h1b,
            "applied": applied,
            "interviews": interviews,
            "emails_sent": emails_out,
        }
