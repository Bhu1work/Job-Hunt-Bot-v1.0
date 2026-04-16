"""
Phase 2 — Claude API: Resume Tailoring + Cover Letter Generation

For every pending H1B-confirmed job in the DB:
  1. Selects the right base resume variant for the role (DE/DA/SQL/SDE)
  2. Sends base resume + JD to Claude
  3. Claude rewrites resume bullets to match JD keywords
  4. Claude generates a cover letter
  5. Saves tailored docs to DB + builds DOCX/PDF in per-application folder

Run:
    python phase2_resume_tailor.py [--job-id 42]
"""

import argparse
import logging
import re
import time
from pathlib import Path

import anthropic

import config
from database import (
    init_db,
    get_pending_jobs,
    get_job,
    save_tailored_docs,
    get_tailored_docs,
    log_event,
)

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)

client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY.strip())


# ── Resume loading ────────────────────────────────────────────────────────────

def load_master_resume() -> str:
    """Load plain-text master resume for use in prompts."""
    path = Path(config.MASTER_RESUME_PATH)
    if path.exists():
        return path.read_text(encoding="utf-8")
    # Fallback: serialise the Data Engineer base variant as text
    from resumes.base_data import DATA_ENGINEER
    return _variant_to_text(DATA_ENGINEER)


def load_base_resume_for_role(role: str) -> str:
    """Return the role-appropriate base resume as plain text for Claude prompts."""
    from resumes.base_data import get_variant_for_role
    variant = get_variant_for_role(role)
    return _variant_to_text(variant)


def _variant_to_text(variant: dict) -> str:
    """Serialise a resume variant dict to readable plain text."""
    lines = []
    c = variant["contact"]
    lines.append(c["name"])
    lines.append(f"{c['location']} | {c['phone']} | {c['email']} | {c['linkedin']}")
    lines.append("")
    lines.append("SUMMARY")
    lines.append(variant["summary"])
    lines.append("")
    lines.append("SKILLS")
    for cat, skills in variant["skills"].items():
        lines.append(f"{cat}: {skills}")
    lines.append("")
    lines.append("EXPERIENCE")
    for job in variant["experience"]:
        lines.append(f"\n{job['title']}  |  {job['company']}  |  {job['start']} – {job['end']}")
        for b in job["bullets"]:
            lines.append(f"• {b}")
    if variant.get("projects"):
        lines.append("\nPROJECTS")
        for p in variant["projects"]:
            lines.append(f"\n{p['title']}  ({p.get('dates','')})")
            for b in p["bullets"]:
                lines.append(f"• {b}")
    lines.append("\nEDUCATION")
    for e in variant["education"]:
        lines.append(f"{e['degree']} — {e['school']} ({e['date']})")
    return "\n".join(lines)


# ── Claude prompt builders ────────────────────────────────────────────────────

def _resume_prompt(jd: str, master_resume: str) -> str:
    return f"""You are an expert technical resume writer and ATS optimization specialist.

## Task
Rewrite the resume bullet points below to closely match the job description's keywords, 
technologies, and impact language. Keep each bullet under 2 lines. Use strong action verbs. 
Quantify impact wherever possible using the existing numbers or reasonable extrapolations.

## Rules
- Only output the rewritten bullet points, grouped by role (same structure as input)
- Do NOT fabricate technologies or achievements not present in the original
- Naturally weave in keywords from the JD
- If a skill in the JD is absent from the resume, note it at the bottom under "GAPS TO ADDRESS"

## Job Description
{jd}

## Master Resume
{master_resume}

## Output Format
Return ONLY:
1. Rewritten bullets (same role groupings)
2. A short "GAPS TO ADDRESS:" section listing skills in the JD not in the resume
"""


def _cover_letter_prompt(jd: str, company: str, role: str,
                          master_resume: str) -> str:
    return f"""You are an expert at writing compelling, personalized cover letters that get interviews.

## Task
Write a concise, high-impact cover letter for the role below. 3-4 paragraphs max.

## Guidelines
- Opening: Hook with a specific detail about {company} or the role (not "I am writing to apply")
- Body paragraph 1: Most relevant experience + quantified impact from resume
- Body paragraph 2: Why {company} specifically (culture, product, mission — infer from JD)
- Closing: Clear call-to-action
- Tone: Confident, direct, professional — not sycophantic
- Length: 250-320 words
- Do NOT mention visa, H1B, sponsorship, work authorization, OPT, or immigration anywhere

## Candidate Info
Name: {config.YOUR_NAME}
Email: {config.YOUR_EMAIL}
LinkedIn: {config.YOUR_LINKEDIN}

## Job Description
Company: {company}
Role: {role}
{jd}

## Resume Summary
{master_resume[:3000]}

## Output
Return ONLY the cover letter body (no subject line, no "Dear Hiring Manager" header needed — 
caller will add those).
"""


def _cold_email_prompt(jd: str, company: str, role: str,
                        contact_name: str, contact_title: str,
                        contact_type: str, master_resume: str,
                        template_num: int = 1) -> str:
    """
    Three ultra-short, punchy cold outreach templates.
    template_num: 1=Trigger+Question  2=Problem+SocialProof  3=Trigger+Focus+Proof
    """
    first_name = contact_name.split()[0] if contact_name and contact_name != "Hiring Team" else "there"

    # Pull a few real resume highlights as shorthand for Claude
    resume_snippet = master_resume[:2000]
    jd_snippet = jd[:600]

    if template_num == 1:
        template_instructions = f"""\
Use TEMPLATE 1 — Trigger + Question.

Structure (follow this EXACTLY, 4 lines total):
Line 1:  "{first_name}, [1 sharp observation about {company} — hiring, growing, launching something]."
Line 2:  "[One focused question about the data/engineering challenge that implies]?"
Line 3:  "I've helped [previous company from resume] [specific outcome with real metric from resume] in [timeframe]. Without [the usual pain that comes with it]."
Line 4:  "Worth a chat?"

Rules:
- Line 3 MUST use a real company name and real metric from the resume (e.g. "Tuttle Publishing" "500K daily records" "35% cost reduction")
- NO "I applied" opener. NO "I hope this finds you well". NO sign-off footer needed — caller adds it.
- Total body: 4 lines, ~50 words max."""

    elif template_num == 2:
        template_instructions = f"""\
Use TEMPLATE 2 — Problem + Social Proof.

Structure:
Line 1:  "Hey {first_name},"
Line 2:  "Most {role} teams I talk to are dealing with two things:"
Line 3:  "[Problem 1 — infer from the JD what they're struggling with]"
Line 4:  "[Problem 2 — second pain point from JD]"
Line 5:  "At [real company from resume] I solved both — [specific result 1 with metric] and [specific result 2 with metric]."
Line 6:  "Open to a quick call?"

Rules:
- Problems must feel real and specific to {company}'s context, not generic.
- Results MUST come from the actual resume numbers (no invented figures).
- Total body: 6 lines, ~60 words max."""

    else:  # template 3
        template_instructions = f"""\
Use TEMPLATE 3 — Trigger + Focus + Social Proof.

Structure:
Line 1:  "Hey {first_name},"
Line 2:  "Given [specific trigger — {company} is hiring/scaling/expanding X], I imagine [key priority, e.g. data reliability / pipeline speed] is top of mind."
Line 3:  "[Previous company from resume] was in the same spot. I [specific outcome with real metric] in [timeframe]."
Line 4:  "Curious if that maps to what you're building?"

Rules:
- Trigger must be specific to {company} (infer from JD or company context).
- Metric MUST be real from resume (e.g. "processed 500K records/day", "cut infra cost 35%").
- Total body: 4 lines, ~55 words max."""

    return f"""You are ghostwriting a cold outreach email FROM {config.YOUR_NAME} to {contact_name} ({contact_title}) at {company}.
Context: {config.YOUR_NAME} just applied for the {role} position.

{template_instructions}

HARD RULES (any violation = rejected output):
1. Output ONLY: one subject line, then the email body. Nothing else.
2. First line format:  subject: <subject under 8 words, specific and human>
3. Then one blank line, then the body.
4. ZERO bracket placeholders like [X], [metric], [company]. Use real names and numbers.
5. Do NOT mention "I applied" or reference the application portal.
6. Do NOT mention visa, H1B, sponsorship, work authorization, or OPT — not even once.
7. End body with exactly:
   Best,
   {config.YOUR_NAME}

=== RESUME FACTS (only use these, no invented numbers) ===
{resume_snippet}

=== JOB / COMPANY CONTEXT ===
{jd_snippet}

Write the email now:"""


# ── Claude API call ───────────────────────────────────────────────────────────

def _call_claude(prompt: str, fast: bool = False) -> str:
    """Call Claude. fast=True uses Haiku (cheaper) for cold emails."""
    model = config.CLAUDE_MODEL_FAST if fast else config.CLAUDE_MODEL
    try:
        message = client.messages.create(
            model=model,
            max_tokens=config.CLAUDE_MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text
    except anthropic.AuthenticationError as exc:
        raise SystemExit(
            "\n" + "─" * 60 + "\n"
            "  Claude API key is invalid or rejected.\n"
            "  Check ANTHROPIC_API_KEY in your .env file.\n"
            "  Get/rotate key at: https://console.anthropic.com\n"
            + "─" * 60
        ) from exc
    except anthropic.PermissionDeniedError as exc:
        raise SystemExit(
            "\n" + "─" * 60 + "\n"
            "  Claude API access denied — credits may be exhausted.\n"
            "  Top up at: https://console.anthropic.com/billing\n"
            + "─" * 60
        ) from exc
    except anthropic.RateLimitError:
        logger.warning("Claude rate limit hit — sleeping 60s then retrying...")
        time.sleep(60)
        return _call_claude(prompt)   # one auto-retry after back-off
    except anthropic.APIStatusError as exc:
        config.check_credit_error(exc, "Claude")
        raise   # not a credit/auth error — propagate


# ── Per-job processing ────────────────────────────────────────────────────────

def process_job(job: dict, master_resume: str | None = None,
                force: bool = False) -> dict:
    """
    Tailor resume + generate cover letter for a single job.
    Uses role-appropriate base variant automatically.
    Builds DOCX/PDF in per-application folder.
    Returns {"resume_bullets": ..., "cover_letter": ...}
    """
    job_id  = job["id"]
    company = job["company"]
    role    = job["role"]
    jd      = job.get("description", "") or f"Role: {role} at {company}"

    # Skip if already done (unless forced)
    if not force:
        existing = get_tailored_docs(job_id)
        if existing:
            logger.info("Job %d (%s @ %s) already tailored — skipping", job_id, role, company)
            return existing

    logger.info("Processing job %d: %s @ %s", job_id, role, company)

    # Use role-appropriate base resume for this job type
    base_resume = load_base_resume_for_role(role)

    # Tailored resume bullets
    resume_prompt  = _resume_prompt(jd, base_resume)
    resume_bullets = _call_claude(resume_prompt)
    logger.info("  ✓ Resume bullets generated (%d chars)", len(resume_bullets))
    time.sleep(0.5)

    # Cover letter
    cl_prompt    = _cover_letter_prompt(jd, company, role, base_resume)
    cover_letter = _call_claude(cl_prompt)
    logger.info("  ✓ Cover letter generated (%d chars)", len(cover_letter))

    # Save tailored content to DB
    save_tailored_docs(job_id, resume_bullets, cover_letter)
    log_event("tailored_docs_saved", f"job_id={job_id} company={company}", job_id=job_id)

    # Build application folder + DOCX/PDF
    try:
        from application_manager import setup_application
        app_folder = setup_application(job_id)
        logger.info("  ✓ Application folder: %s", app_folder)
    except Exception as exc:
        logger.warning("  ⚠ Folder build failed (non-fatal): %s", exc)

    return {"resume_bullets": resume_bullets, "cover_letter": cover_letter}


def generate_cold_email(job: dict, contact: dict, master_resume: str,
                         template_num: int | None = None) -> dict:
    """
    Generate a cold email for a specific contact at the job's company.
    Rotates through 3 punchy templates (Trigger+Q, Problem+Proof, Trigger+Focus+Proof).
    Returns {"subject": ..., "body": ...}
    """
    jd = job.get("description", "") or f"Role: {job['role']} at {job['company']}"

    # Rotate templates by job ID so same contact type gets variety
    if template_num is None:
        template_num = (job.get("id", 1) % 3) + 1   # cycles 1 → 2 → 3 → 1 ...

    prompt = _cold_email_prompt(
        jd=jd,
        company=job["company"],
        role=job["role"],
        contact_name=contact.get("name", "Hiring Team"),
        contact_title=contact.get("title", ""),
        contact_type=contact.get("contact_type", "hr"),
        master_resume=master_resume,
        template_num=template_num,
    )

    raw = _call_claude(prompt, fast=True)   # Haiku is 20x cheaper — enough for cold emails

    subject = ""
    body = raw

    # Parse [subject:] and [body:] markers
    # Handle formats: "[subject:] Text", "[subject]: Text", "Subject: Text"
    if "[subject" in raw.lower() or raw.lower().startswith("subject:"):
        lines = raw.split("\n")
        subj_lines = [l for l in lines if re.match(r"^\[?subject[:\]]+", l.strip(), re.I)]
        body_start = next(
            (i for i, l in enumerate(lines) if re.match(r"^\[?body[:\]]+", l.strip(), re.I)),
            None
        )
        if subj_lines:
            # Strip all leading markers: [subject:], [subject], subject:, ]
            subject = re.sub(r"^\[?subject[:\]]+\s*\]?\s*", "", subj_lines[0].strip(), flags=re.I)
            subject = subject.lstrip("]").strip()
        if body_start is not None:
            body = "\n".join(lines[body_start + 1:]).strip()
        elif subj_lines:
            # Body is everything after the subject line
            subj_idx = lines.index(subj_lines[0])
            body = "\n".join(lines[subj_idx + 1:]).strip()

    # Strip any residual template notes Claude adds at the end (---\n*Note:...)
    body = re.sub(r"\n---\n\*.*$", "", body, flags=re.DOTALL).strip()

    return {"subject": subject, "body": body}


# ── Batch runner ──────────────────────────────────────────────────────────────

def run(job_id: int | None = None, force: bool = False,
        limit: int | None = None) -> None:

    config.validate_keys(require_claude=True)
    init_db()
    master_resume = load_master_resume()

    if job_id:
        job = get_job(job_id)
        if not job:
            logger.error("Job %d not found", job_id)
            return
        jobs = [job]
    else:
        jobs = get_pending_jobs()
        if limit:
            jobs = jobs[:limit]

    logger.info("Processing %d jobs through Claude...", len(jobs))

    success = 0
    for job in jobs:
        try:
            process_job(job, master_resume, force=force)
            success += 1
        except SystemExit:
            raise   # credit/auth errors must propagate — stop the whole pipeline
        except Exception as exc:
            logger.error("Failed job %d (%s): %s", job["id"], job["company"], exc)

    logger.info("Done. %d / %d jobs tailored.", success, len(jobs))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Phase 2 — Claude resume tailor + cover letter")
    parser.add_argument("--job-id", type=int, default=None, help="Process a single job by ID")
    parser.add_argument("--force", action="store_true", help="Re-generate even if docs exist")
    parser.add_argument("--limit", type=int, default=None, help="Cap number of jobs to process")
    args = parser.parse_args()

    run(job_id=args.job_id, force=args.force, limit=args.limit)
