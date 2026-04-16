"""
resume_builder.py — Generates professional DOCX (and optionally PDF) resumes
from the structured data in resumes/base_data.py.

Usage:
    # Generate all 4 base variants
    python resume_builder.py --all

    # Generate one variant
    python resume_builder.py --variant data_engineer

    # Generate a tailored resume for a specific job (merges Claude output)
    from resume_builder import build_tailored_resume
    build_tailored_resume(job_id=42, output_dir="applications/Stripe_DE_42")
"""

import argparse
import copy
import logging
import re
from pathlib import Path
from typing import Any

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.shared import Pt, Inches, RGBColor

import config

logger = logging.getLogger(__name__)

# Output dir for base resume variants
BASE_RESUMES_DIR = Path("resumes/generated")
BASE_RESUMES_DIR.mkdir(parents=True, exist_ok=True)


# ── Colour palette ────────────────────────────────────────────────────────────
ACCENT_COLOR = RGBColor(0x1A, 0x56, 0x9B)   # professional dark blue
TEXT_COLOR   = RGBColor(0x1A, 0x1A, 0x1A)   # near-black


# ── Low-level DOCX helpers ────────────────────────────────────────────────────

def _set_font(run, name: str = "Calibri", size_pt: float = 11,
              bold: bool = False, italic: bool = False,
              color: RGBColor | None = None) -> None:
    run.font.name = name
    run.font.size = Pt(size_pt)
    run.font.bold = bold
    run.font.italic = italic
    if color:
        run.font.color.rgb = color


def _add_bottom_border(paragraph) -> None:
    """Add a thin bottom border to a paragraph (used for section headings)."""
    pPr = paragraph._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "6")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "1A569B")
    pBdr.append(bottom)
    pPr.append(pBdr)


def _set_para_spacing(paragraph, before: int = 0, after: int = 0,
                       line_rule: str = "auto", line: int = 240) -> None:
    pPr = paragraph._p.get_or_add_pPr()
    spacing = OxmlElement("w:spacing")
    spacing.set(qn("w:before"), str(before))
    spacing.set(qn("w:after"),  str(after))
    spacing.set(qn("w:lineRule"), line_rule)
    spacing.set(qn("w:line"),   str(line))
    pPr.append(spacing)


# ── Section builders ──────────────────────────────────────────────────────────

def _add_name_header(doc: Document, contact: dict) -> None:
    """Large centred name + single contact info line."""
    # Name
    name_para = doc.add_paragraph()
    name_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _set_para_spacing(name_para, before=0, after=40)
    run = name_para.add_run(contact["name"])
    _set_font(run, size_pt=20, bold=True, color=ACCENT_COLOR)

    # Contact line
    parts = [
        contact.get("location", ""),
        contact.get("phone", ""),
        contact.get("email", ""),
        contact.get("linkedin", ""),
        contact.get("github", ""),
    ]
    contact_line = "  |  ".join(p for p in parts if p)

    c_para = doc.add_paragraph()
    c_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _set_para_spacing(c_para, before=0, after=60)
    run = c_para.add_run(contact_line)
    _set_font(run, size_pt=9.5, color=TEXT_COLOR)


def _add_section_heading(doc: Document, title: str) -> None:
    p = doc.add_paragraph()
    _set_para_spacing(p, before=120, after=30)
    run = p.add_run(title.upper())
    _set_font(run, size_pt=11, bold=True, color=ACCENT_COLOR)
    _add_bottom_border(p)


def _add_summary(doc: Document, summary: str) -> None:
    _add_section_heading(doc, "Summary")
    p = doc.add_paragraph()
    _set_para_spacing(p, before=20, after=0)
    run = p.add_run(summary)
    _set_font(run, size_pt=10)


def _add_skills(doc: Document, skills: dict) -> None:
    _add_section_heading(doc, "Skills")
    for category, skill_list in skills.items():
        p = doc.add_paragraph()
        _set_para_spacing(p, before=15, after=0, line=220)
        bold_run = p.add_run(f"{category}: ")
        _set_font(bold_run, size_pt=10, bold=True)
        normal_run = p.add_run(skill_list)
        _set_font(normal_run, size_pt=10)


def _add_experience(doc: Document, experience: list) -> None:
    _add_section_heading(doc, "Professional Experience")
    for job in experience:
        # Title + dates on one line, company + location on next
        header = doc.add_paragraph()
        _set_para_spacing(header, before=80, after=0)
        title_run = header.add_run(job["title"])
        _set_font(title_run, size_pt=10.5, bold=True)

        date_str = f"  {job['start']} – {job['end']}"
        # Right-align date via a tab stop (approximate with spaces)
        header.add_run("\t" * 3)
        date_run = header.add_run(date_str)
        _set_font(date_run, size_pt=10, italic=True, color=RGBColor(0x55, 0x55, 0x55))

        sub = doc.add_paragraph()
        _set_para_spacing(sub, before=0, after=0)
        company_run = sub.add_run(
            f"{job['company']}  —  {job['location']}"
            + (f"  [{job.get('label', '')}]" if job.get("label") else "")
        )
        _set_font(company_run, size_pt=10, italic=True)

        for bullet in job["bullets"]:
            bp = doc.add_paragraph(style="List Bullet")
            _set_para_spacing(bp, before=0, after=0, line=220)
            # Indent
            bp.paragraph_format.left_indent  = Inches(0.2)
            bp.paragraph_format.first_line_indent = Inches(-0.15)
            run = bp.add_run(bullet)
            _set_font(run, size_pt=10)


def _add_projects(doc: Document, projects: list) -> None:
    if not projects:
        return
    _add_section_heading(doc, "Projects")
    for proj in projects:
        header = doc.add_paragraph()
        _set_para_spacing(header, before=80, after=0)
        title_run = header.add_run(proj["title"])
        _set_font(title_run, size_pt=10.5, bold=True)
        if proj.get("dates"):
            date_run = header.add_run(f"   ({proj['dates']})")
            _set_font(date_run, size_pt=10, italic=True, color=RGBColor(0x55, 0x55, 0x55))

        for bullet in proj["bullets"]:
            bp = doc.add_paragraph(style="List Bullet")
            _set_para_spacing(bp, before=0, after=0, line=220)
            bp.paragraph_format.left_indent = Inches(0.2)
            bp.paragraph_format.first_line_indent = Inches(-0.15)
            run = bp.add_run(bullet)
            _set_font(run, size_pt=10)


def _add_education(doc: Document, education: list) -> None:
    _add_section_heading(doc, "Education")
    for edu in education:
        p = doc.add_paragraph()
        _set_para_spacing(p, before=40, after=0)
        deg_run = p.add_run(edu["degree"])
        _set_font(deg_run, size_pt=10.5, bold=True)
        p.add_run(f"\n{edu['school']}  —  {edu['location']}  |  {edu['date']}")


def _add_publications(doc: Document, pubs: list) -> None:
    if not pubs:
        return
    _add_section_heading(doc, "Publications")
    for pub in pubs:
        p = doc.add_paragraph(style="List Bullet")
        _set_para_spacing(p, before=10, after=0, line=220)
        run = p.add_run(pub)
        _set_font(run, size_pt=10)


# ── Document assembler ────────────────────────────────────────────────────────

def build_docx(variant: dict, output_path: Path) -> Path:
    """
    Build a professional DOCX resume from a variant dict.
    Returns the path to the saved .docx file.
    """
    doc = Document()

    # Margins
    for section in doc.sections:
        section.top_margin    = Inches(0.55)
        section.bottom_margin = Inches(0.55)
        section.left_margin   = Inches(0.75)
        section.right_margin  = Inches(0.75)

    # Default paragraph style
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(10)

    _add_name_header(doc, variant["contact"])
    _add_summary(doc, variant["summary"])
    _add_skills(doc, variant["skills"])
    _add_experience(doc, variant["experience"])
    _add_projects(doc, variant.get("projects", []))
    _add_education(doc, variant["education"])
    _add_publications(doc, variant.get("publications", []))

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path))
    logger.info("DOCX saved → %s", output_path)
    return output_path


def build_pdf(docx_path: Path, variant: dict | None = None) -> Path | None:
    """
    Convert DOCX to PDF. Tries docx2pdf (MS Word), then LibreOffice,
    then falls back to reportlab direct PDF generation.
    """
    pdf_path = docx_path.with_suffix(".pdf")

    # 1. Try docx2pdf (needs MS Word)
    try:
        from docx2pdf import convert
        convert(str(docx_path), str(pdf_path))
        logger.info("PDF saved (Word) → %s", pdf_path)
        return pdf_path
    except Exception as e1:
        logger.debug("docx2pdf unavailable: %s", e1)

    # 2. Try LibreOffice
    try:
        import subprocess
        result = subprocess.run(
            ["libreoffice", "--headless", "--convert-to", "pdf",
             "--outdir", str(docx_path.parent), str(docx_path)],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            logger.info("PDF saved (LibreOffice) → %s", pdf_path)
            return pdf_path
    except Exception as e2:
        logger.debug("LibreOffice unavailable: %s", e2)

    # 3. Fallback: reportlab direct PDF (no external dependency)
    if variant is not None:
        try:
            from pdf_builder import build_pdf as rl_build
            rl_build(variant, pdf_path)
            logger.info("PDF saved (reportlab) → %s", pdf_path)
            return pdf_path
        except Exception as e3:
            logger.warning("reportlab PDF failed: %s", e3)

    logger.warning("PDF could not be generated for %s", docx_path)
    return None


# ── Tailored resume builder (called by phase2) ────────────────────────────────

def build_tailored_resume(job_id: int, output_dir: str | Path,
                           tailored_bullets: str | None = None,
                           cover_letter: str | None = None,
                           base_variant: dict | None = None) -> dict:
    """
    Build final application resume DOCX/PDF for a specific job.

    If tailored_bullets is provided (Claude output), merge it into the variant.
    Returns dict with paths: {"docx": ..., "pdf": ..., "cover_letter": ...}
    """
    from database import get_job, get_tailored_docs
    from resumes.base_data import get_variant_for_role

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    job = get_job(job_id)
    if not job:
        raise ValueError(f"Job {job_id} not found in DB")

    # Get or load base variant
    if base_variant is None:
        base_variant = get_variant_for_role(job["role"])

    variant = copy.deepcopy(base_variant)

    # Merge Claude-tailored bullets if provided
    if tailored_bullets:
        _merge_tailored_bullets(variant, tailored_bullets)

    # Ensure correct email
    variant["contact"]["email"] = "bhuvanthatthari@gmail.com"

    # Build DOCX
    safe_company = re.sub(r"[^\w\-]", "_", job["company"])[:30]
    safe_role    = re.sub(r"[^\w\-]", "_", job["role"])[:25]
    filename     = f"Resume_{safe_company}_{safe_role}"

    docx_path = output_dir / f"{filename}.docx"
    build_docx(variant, docx_path)

    # Try PDF (passes variant so reportlab fallback works without MS Word)
    pdf_path = build_pdf(docx_path, variant=variant)

    # Save cover letter
    cl_path = None
    if cover_letter:
        cl_path = output_dir / "cover_letter.txt"
        cl_path.write_text(cover_letter, encoding="utf-8")
        logger.info("Cover letter → %s", cl_path)

    return {
        "docx":         str(docx_path),
        "pdf":          str(pdf_path) if pdf_path else None,
        "cover_letter": str(cl_path) if cl_path else None,
    }


def _merge_tailored_bullets(variant: dict, tailored_text: str) -> None:
    """
    Best-effort merge of Claude-generated tailored bullets back into variant.
    Claude output format (from phase2_resume_tailor.py):
      Grouped by role name, each bullet on its own line starting with - or •
    """
    lines = tailored_text.splitlines()
    bullet_lines = [
        l.lstrip("•-– ").strip()
        for l in lines
        if l.strip().startswith(("-", "•", "–")) and len(l.strip()) > 10
    ]

    if not bullet_lines:
        return

    # Distribute bullets across experience entries proportionally
    exp_entries = variant["experience"]
    idx = 0
    for entry in exp_entries:
        orig_count = len(entry["bullets"])
        new_bullets = bullet_lines[idx: idx + orig_count]
        if new_bullets:
            entry["bullets"] = new_bullets
        idx += orig_count
        if idx >= len(bullet_lines):
            break


# ── CLI ───────────────────────────────────────────────────────────────────────

def generate_all_base_resumes() -> None:
    from resumes.base_data import DATA_ENGINEER, DATA_ANALYST, SQL_ENGINEER, SDE

    variants = {
        "data_engineer": DATA_ENGINEER,
        "data_analyst":  DATA_ANALYST,
        "sql_engineer":  SQL_ENGINEER,
        "sde":           SDE,
    }
    for name, variant in variants.items():
        docx_path = BASE_RESUMES_DIR / f"Bhuvan_Thatthari_{name.replace('_', ' ').title().replace(' ', '_')}.docx"
        build_docx(variant, docx_path)
        build_pdf(docx_path, variant=variant)
    print(f"\nAll 4 base resumes saved to {BASE_RESUMES_DIR}/")


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")

    parser = argparse.ArgumentParser(description="Resume DOCX/PDF builder")
    parser.add_argument("--all", action="store_true", help="Generate all 4 base variants")
    parser.add_argument("--variant", choices=["data_engineer", "data_analyst",
                                               "sql_engineer", "sde"],
                        help="Generate a single variant")
    args = parser.parse_args()

    if args.all:
        generate_all_base_resumes()
    elif args.variant:
        from resumes.base_data import DATA_ENGINEER, DATA_ANALYST, SQL_ENGINEER, SDE
        v_map = {"data_engineer": DATA_ENGINEER, "data_analyst": DATA_ANALYST,
                 "sql_engineer": SQL_ENGINEER, "sde": SDE}
        variant = v_map[args.variant]
        out = BASE_RESUMES_DIR / f"Bhuvan_Thatthari_{args.variant}.docx"
        build_docx(variant, out)
        build_pdf(out)
    else:
        parser.print_help()
