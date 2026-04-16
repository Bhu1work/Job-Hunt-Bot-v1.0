"""
application_manager.py — Creates and manages per-application folders.

Folder structure:
    applications/
        {COMPANY}_{ROLE}_{JOB_ID}/
            metadata.json          ← job details, status, timestamps
            Resume_{Company}_{Role}.docx
            Resume_{Company}_{Role}.pdf  (if PDF conversion available)
            cover_letter.txt
            jd_snapshot.txt        ← job description at time of apply
            emails/
                hr_cold_email.txt
                hm_cold_email.txt
                followup_day3.txt
                followup_day7.txt
                followup_day14.txt
"""

import json
import logging
import re
import shutil
from datetime import datetime
from pathlib import Path

from database import get_job, get_tailored_docs, get_contacts_for_job, update_job_status, log_event

logger = logging.getLogger(__name__)

APPLICATIONS_DIR = Path("applications")
APPLICATIONS_DIR.mkdir(exist_ok=True)


# ── Folder name helpers ───────────────────────────────────────────────────────

def _safe(text: str, max_len: int = 25) -> str:
    """Sanitise a string for use in a directory name."""
    return re.sub(r"[^\w\-]", "_", text.strip())[:max_len]


def get_app_folder(job: dict) -> Path:
    """Return the application folder Path for a job (creates it if needed)."""
    folder_name = f"{_safe(job['company'])}_{_safe(job['role'])}_{job['id']}"
    path = APPLICATIONS_DIR / folder_name
    path.mkdir(parents=True, exist_ok=True)
    (path / "emails").mkdir(exist_ok=True)
    return path


# ── Metadata ──────────────────────────────────────────────────────────────────

def _write_metadata(folder: Path, job: dict, extra: dict | None = None) -> None:
    meta = {
        "job_id":         job["id"],
        "company":        job["company"],
        "role":           job["role"],
        "jd_url":         job.get("jd_url", ""),
        "source":         job.get("source", ""),
        "location":       job.get("location", ""),
        "h1b_confirmed":  bool(job.get("h1b_confirmed")),
        "applied_status": job.get("applied_status", "pending"),
        "folder":         str(folder),
        "created_at":     datetime.now().isoformat(),
        **(extra or {}),
    }
    (folder / "metadata.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )


def update_metadata(folder: Path, updates: dict) -> None:
    path = folder / "metadata.json"
    if not path.exists():
        return
    meta = json.loads(path.read_text(encoding="utf-8"))
    meta.update(updates)
    meta["updated_at"] = datetime.now().isoformat()
    path.write_text(json.dumps(meta, indent=2), encoding="utf-8")


# ── Per-application setup ─────────────────────────────────────────────────────

def create_application_folder(job_id: int) -> Path:
    """
    Create the full application folder for a job:
      - metadata.json
      - jd_snapshot.txt
      - (resume + cover letter added by build_application_docs)
    Returns the folder Path.
    """
    job = get_job(job_id)
    if not job:
        raise ValueError(f"Job {job_id} not found")

    folder = get_app_folder(job)

    # JD snapshot
    jd = job.get("description", "")
    if jd:
        (folder / "jd_snapshot.txt").write_text(jd, encoding="utf-8")

    _write_metadata(folder, job)
    logger.info("Application folder created: %s", folder)
    return folder


def build_application_docs(job_id: int, folder: Path | None = None) -> dict:
    """
    Generate tailored resume DOCX/PDF + cover letter for a job,
    save everything into the application folder.
    Returns dict with file paths.
    """
    from resume_builder import build_tailored_resume
    from resumes.base_data import get_variant_for_role

    job = get_job(job_id)
    if not job:
        raise ValueError(f"Job {job_id} not found")

    if folder is None:
        folder = get_app_folder(job)

    docs = get_tailored_docs(job_id)
    tailored_bullets = docs["resume_bullets"] if docs else None
    cover_letter     = docs["cover_letter"]   if docs else None

    base_variant = get_variant_for_role(job["role"])

    paths = build_tailored_resume(
        job_id=job_id,
        output_dir=folder,
        tailored_bullets=tailored_bullets,
        cover_letter=cover_letter,
        base_variant=base_variant,
    )

    update_metadata(folder, {"docs": paths})
    log_event("docs_built", f"folder={folder}", job_id=job_id)

    logger.info("Application docs built in %s", folder)
    return paths


def save_email_drafts(job_id: int, folder: Path | None = None) -> None:
    """
    Save all cold email + follow-up drafts to the emails/ subfolder.
    """
    from database import get_db

    job = get_job(job_id)
    if not job:
        return

    if folder is None:
        folder = get_app_folder(job)

    emails_dir = folder / "emails"
    emails_dir.mkdir(exist_ok=True)

    with get_db() as conn:
        rows = conn.execute(
            "SELECT o.*, c.name as contact_name, c.email as contact_email, "
            "c.contact_type, c.title as contact_title "
            "FROM outreach o "
            "LEFT JOIN contacts c ON c.id = o.contact_id "
            "WHERE o.job_id = ?",
            (job_id,),
        ).fetchall()

    for row in rows:
        row = dict(row)
        otype = row.get("outreach_type", "email")
        fday  = row.get("followup_day")
        ctype = row.get("contact_type", "contact")

        if otype == "cold_email":
            fname = f"cold_email_{ctype}.txt"
        elif otype == "followup" and fday:
            fname = f"followup_day{fday}.txt"
        else:
            fname = f"{otype}_{row['id']}.txt"

        content = (
            f"TO: {row.get('contact_email', '')}\n"
            f"CONTACT: {row.get('contact_name', '')} ({row.get('contact_title', '')})\n"
            f"SUBJECT: {row.get('subject', '')}\n"
            f"STATUS: {row.get('status', 'draft')}\n"
            f"{'='*60}\n\n"
            f"{row.get('body', '')}"
        )
        (emails_dir / fname).write_text(content, encoding="utf-8")

    logger.info("Email drafts saved to %s/emails/", folder)


# ── Full application setup pipeline ──────────────────────────────────────────

def setup_application(job_id: int) -> Path:
    """
    Full setup: create folder → build docs → save emails.
    Call this after phase2 (tailoring) and phase3 (email finding) are done.
    Returns application folder path.
    """
    folder = create_application_folder(job_id)
    build_application_docs(job_id, folder)
    save_email_drafts(job_id, folder)
    return folder


def mark_applied(job_id: int, ats: str = "") -> None:
    """Update DB + metadata.json after successful application submission."""
    job = get_job(job_id)
    if not job:
        return
    folder = get_app_folder(job)
    update_metadata(folder, {
        "applied_status": "applied",
        "applied_at":     datetime.now().isoformat(),
        "ats":            ats,
    })
    update_job_status(job_id, "applied")


# ── Status dashboard ──────────────────────────────────────────────────────────

def print_applications_dashboard() -> None:
    """Print a quick overview of all application folders."""
    folders = sorted(APPLICATIONS_DIR.iterdir())
    if not folders:
        print("No applications yet.")
        return

    status_counts: dict[str, int] = {}
    print(f"\n{'='*72}")
    print(f"  {'COMPANY':<28} {'ROLE':<25} {'STATUS':<12} {'DATE'}")
    print(f"{'='*72}")

    for folder in folders:
        if not folder.is_dir():
            continue
        meta_file = folder / "metadata.json"
        if not meta_file.exists():
            continue
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        status = meta.get("applied_status", "pending")
        status_counts[status] = status_counts.get(status, 0) + 1
        date = (meta.get("applied_at") or meta.get("created_at", ""))[:10]
        print(f"  {meta.get('company',''):<28} {meta.get('role',''):<25} "
              f"{status:<12} {date}")

    print(f"{'='*72}")
    print("  " + "  |  ".join(f"{k}: {v}" for k, v in status_counts.items()))
    print(f"{'='*72}\n")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Application folder manager")
    parser.add_argument("--setup", type=int, metavar="JOB_ID",
                        help="Set up application folder for a job")
    parser.add_argument("--dashboard", action="store_true",
                        help="Print applications dashboard")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")

    if args.setup:
        path = setup_application(args.setup)
        print(f"Application folder ready: {path}")
    elif args.dashboard:
        print_applications_dashboard()
    else:
        parser.print_help()
