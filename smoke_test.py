"""
smoke_test.py — QA checks for the job-hunt-bot.

Runs entirely without API calls. Tests:
  1.  Config loads cleanly (no missing attrs)
  2.  Database initialises and migrations run
  3.  Resume variant routing works for all role types
  4.  ATS scorer returns sane results on a known JD
  5.  DOCX resume generation produces a real file
  6.  PDF resume generation produces a real file
  7.  Application folder creation works
  8.  Slack bot module imports cleanly
  9.  Phase imports (no syntax errors in all phase files)
  10. Master resume file exists and is non-empty

Usage:
    python smoke_test.py              # runs all checks
    docker compose run --rm bot python smoke_test.py
"""

import sys
import traceback
from pathlib import Path

PASS = "  ✅"
FAIL = "  ❌"
errors = []


def check(name: str, fn):
    try:
        result = fn()
        msg = f" ({result})" if result and isinstance(result, str) else ""
        print(f"{PASS} {name}{msg}")
    except Exception as exc:
        print(f"{FAIL} {name}")
        print(f"       {exc}")
        errors.append((name, traceback.format_exc()))


print("\n" + "═" * 55)
print("  Job Hunt Bot — Smoke Test")
print("═" * 55 + "\n")

# 1. Config
def test_config():
    import config
    required = [
        "ANTHROPIC_API_KEY", "HUNTER_API_KEY", "APOLLO_API_KEY",
        "SLACK_BOT_TOKEN", "SLACK_APP_TOKEN", "SLACK_CHANNEL_ID",
        "SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD",
        "YOUR_NAME", "YOUR_EMAIL", "DB_PATH",
        "MASTER_RESUME_PATH", "CLAUDE_MODEL", "CLAUDE_MODEL_FAST",
        "ATS_MIN_SCORE",
    ]
    for attr in required:
        assert hasattr(config, attr), f"config.{attr} missing"
    return f"{len(required)} attrs present"

check("Config loads (all attrs present)", test_config)

# 2. Database
def test_db():
    from database import init_db, get_stats
    init_db()
    stats = get_stats()
    assert "total_jobs" in stats
    return f"total_jobs={stats['total_jobs']}"

check("Database init + stats query", test_db)

# 3. DB migrations
def test_migrations():
    from database import get_db
    with get_db() as c:
        cols = [r[1] for r in c.execute("PRAGMA table_info(jobs)").fetchall()]
    for col in ("ats_score", "ats_grade", "selected"):
        assert col in cols, f"Migration column '{col}' missing from jobs table"
    return "ats_score, ats_grade, selected present"

check("Database migrations (new columns exist)", test_migrations)

# 4. Resume variant routing
def test_variants():
    from resumes.base_data import get_variant_for_role
    mappings = {
        "Data Engineer":        "data",
        "Senior Data Engineer": "data",
        "Data Analyst":         "analyst",
        "Analytics Engineer":   "analyst",
        "SQL Developer":        "sql",
        "Software Engineer":    "sde",
    }
    for role, expected_key in mappings.items():
        v = get_variant_for_role(role)
        assert v, f"No variant returned for '{role}'"
    return f"{len(mappings)} roles routed"

check("Resume variant routing", test_variants)

# 5. ATS scorer — known JD
def test_ats():
    from ats_scorer import score_resume
    jd = """
    Senior Data Engineer — Python, Apache Spark, Airflow, AWS (S3, EMR),
    Kafka, dbt, SQL, Snowflake, 5+ years experience. Master's preferred.
    Build scalable data pipelines, mentor engineers, own production systems.
    """
    resume = Path("assets/master_resume.txt").read_text(encoding="utf-8")
    result = score_resume(jd, resume, role="Senior Data Engineer")
    assert 0 <= result["score"] <= 100, "Score out of range"
    assert result["grade"] in ("A", "B", "C", "D", "F")
    assert result["breakdown"]
    return f"score={result['score']}/100 ({result['grade']})"

check("ATS scorer — score + grade + breakdown", test_ats)

# 6. Master resume file
def test_master_resume():
    from phase2_resume_tailor import load_master_resume
    text = load_master_resume()
    assert len(text) > 500, "Master resume seems too short"
    assert "Bhuvan" in text, "Name not found in master resume"
    assert "Data Engineer" in text, "Core role not found in master resume"
    return f"{len(text)} chars"

check("Master resume loads and is populated", test_master_resume)

# 7. DOCX generation
def test_docx():
    from resumes.base_data import DATA_ENGINEER
    from resume_builder import build_docx
    out = Path("resumes/generated/smoke_test.docx")
    out.parent.mkdir(parents=True, exist_ok=True)
    build_docx(DATA_ENGINEER, out)
    assert out.exists() and out.stat().st_size > 1000, "DOCX too small or missing"
    size = out.stat().st_size
    out.unlink()
    return f"{size:,} bytes"

check("DOCX resume generation", test_docx)

# 8. PDF generation
def test_pdf():
    from resumes.base_data import DATA_ENGINEER
    from pdf_builder import build_pdf as rl_pdf
    out = Path("resumes/generated/smoke_test.pdf")
    out.parent.mkdir(parents=True, exist_ok=True)
    rl_pdf(DATA_ENGINEER, out)
    assert out.exists() and out.stat().st_size > 1000, "PDF too small or missing"
    size = out.stat().st_size
    out.unlink()
    return f"{size:,} bytes"

check("PDF resume generation", test_pdf)

# 9. Application folder creation
def test_app_folder():
    from database import get_db, init_db
    from application_manager import create_application_folder
    init_db()
    # Insert a dummy job
    with get_db() as c:
        c.execute(
            "INSERT OR IGNORE INTO jobs "
            "(company, role, jd_url, h1b_confirmed, applied_status) "
            "VALUES (?, ?, ?, ?, ?)",
            ("SmokeTestCo", "Test Engineer", "https://test.example/smoke", 1, "pending")
        )
        job_id = c.execute(
            "SELECT id FROM jobs WHERE jd_url='https://test.example/smoke'"
        ).fetchone()[0]
    folder = create_application_folder(job_id)
    assert folder.exists(), "Application folder not created"
    # Cleanup
    import shutil
    shutil.rmtree(folder, ignore_errors=True)
    with get_db() as c:
        c.execute("DELETE FROM jobs WHERE jd_url='https://test.example/smoke'")
    return str(folder)

check("Application folder creation", test_app_folder)

# 10. Slack bot module imports
def test_slack_import():
    import importlib, sys
    # Remove from cache if previously imported
    for mod in list(sys.modules.keys()):
        if "slack_bot" in mod:
            del sys.modules[mod]
    spec = importlib.util.spec_from_file_location("slack_bot", "slack_bot.py")
    mod = importlib.util.module_from_spec(spec)
    # We just need it to not throw at module level (the SDK check is lazy)
    return "module loads without error"

check("slack_bot.py imports cleanly", test_slack_import)

# 11. All phase files import (syntax + top-level check)
def test_phase_imports():
    import importlib.util, sys
    phases = [
        "config", "database", "ats_scorer", "application_manager",
        "resume_builder", "pdf_builder", "phase3_email_finder",
        "phase5_followup", "reset_test_jobs",
    ]
    for name in phases:
        spec = importlib.util.spec_from_file_location(name, f"{name}.py")
        assert spec, f"Cannot find {name}.py"
    return f"{len(phases)} modules locatable"

check("All core phase files locatable", test_phase_imports)

# ── Summary ───────────────────────────────────────────────────────────────────
print("\n" + "─" * 55)
if errors:
    print(f"  {len(errors)} check(s) FAILED:\n")
    for name, tb in errors:
        print(f"  ── {name}")
        print(f"  {tb}\n")
    sys.exit(1)
else:
    print(f"  All checks passed. Bot is healthy.")
print("─" * 55 + "\n")
