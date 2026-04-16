"""
pdf_builder.py — Generates professional PDF resumes using reportlab.
Called as a fallback when MS Word / LibreOffice is not available.
"""

from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, HRFlowable,
    ListFlowable, ListItem,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY


# ── Colour / font constants ───────────────────────────────────────────────────
ACCENT     = colors.HexColor("#1A569B")
TEXT       = colors.HexColor("#1A1A1A")
LIGHT_GRAY = colors.HexColor("#555555")
FONT_MAIN  = "Helvetica"
FONT_BOLD  = "Helvetica-Bold"
FONT_ITALIC = "Helvetica-Oblique"


# ── Style sheet ───────────────────────────────────────────────────────────────

def _build_styles():
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        name="ResumeName",
        fontName=FONT_BOLD,
        fontSize=20,
        textColor=ACCENT,
        alignment=TA_CENTER,
        spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        name="ResumeContact",
        fontName=FONT_MAIN,
        fontSize=9,
        textColor=LIGHT_GRAY,
        alignment=TA_CENTER,
        spaceAfter=10,
    ))
    styles.add(ParagraphStyle(
        name="SectionHeading",
        fontName=FONT_BOLD,
        fontSize=10.5,
        textColor=ACCENT,
        spaceBefore=12,
        spaceAfter=2,
        borderPadding=(0, 0, 2, 0),
    ))
    styles.add(ParagraphStyle(
        name="Summary",
        fontName=FONT_MAIN,
        fontSize=9.5,
        textColor=TEXT,
        alignment=TA_JUSTIFY,
        spaceAfter=4,
        leading=13,
    ))
    styles.add(ParagraphStyle(
        name="JobTitle",
        fontName=FONT_BOLD,
        fontSize=10,
        textColor=TEXT,
        spaceBefore=8,
        spaceAfter=1,
    ))
    styles.add(ParagraphStyle(
        name="JobMeta",
        fontName=FONT_ITALIC,
        fontSize=9.5,
        textColor=LIGHT_GRAY,
        spaceAfter=2,
    ))
    styles.add(ParagraphStyle(
        name="BulletText",
        fontName=FONT_MAIN,
        fontSize=9.5,
        textColor=TEXT,
        leftIndent=12,
        firstLineIndent=-10,
        spaceBefore=1,
        spaceAfter=1,
        leading=12,
    ))
    styles.add(ParagraphStyle(
        name="SkillLine",
        fontName=FONT_MAIN,
        fontSize=9.5,
        textColor=TEXT,
        spaceBefore=2,
        spaceAfter=2,
        leading=12,
    ))
    styles.add(ParagraphStyle(
        name="EduText",
        fontName=FONT_MAIN,
        fontSize=9.5,
        textColor=TEXT,
        spaceBefore=4,
        spaceAfter=2,
        leading=13,
    ))
    return styles


def _hr(styles) -> list:
    """Thin blue horizontal rule for section separators."""
    return [HRFlowable(width="100%", thickness=0.7, color=ACCENT, spaceAfter=3)]


# ── Section builders ──────────────────────────────────────────────────────────

def _section_heading(title: str, styles) -> list:
    items = [Paragraph(title.upper(), styles["SectionHeading"])]
    items += _hr(styles)
    return items


def _build_story(variant: dict, styles) -> list:
    story = []
    c = variant["contact"]

    # Name
    story.append(Paragraph(c["name"], styles["ResumeName"]))

    # Contact line
    parts = [c.get("location",""), c.get("phone",""), c.get("email",""),
             c.get("linkedin",""), c.get("github","")]
    contact_str = "  |  ".join(p for p in parts if p)
    story.append(Paragraph(contact_str, styles["ResumeContact"]))
    story.append(Spacer(1, 4))

    # Summary
    story += _section_heading("Summary", styles)
    story.append(Paragraph(variant["summary"], styles["Summary"]))

    # Skills
    story += _section_heading("Skills", styles)
    for cat, skill_str in variant["skills"].items():
        story.append(Paragraph(
            f'<b>{cat}:</b> {skill_str}',
            styles["SkillLine"],
        ))

    # Experience
    story += _section_heading("Professional Experience", styles)
    for job in variant["experience"]:
        label = f"  [{job['label']}]" if job.get("label") else ""
        story.append(Paragraph(
            f'{job["title"]}<font color="#555555"><i>    {job["start"]} – {job["end"]}</i></font>',
            styles["JobTitle"],
        ))
        story.append(Paragraph(
            f'{job["company"]} — {job["location"]}{label}',
            styles["JobMeta"],
        ))
        for bullet in job["bullets"]:
            story.append(Paragraph(f"\u2022  {bullet}", styles["BulletText"]))

    # Projects
    if variant.get("projects"):
        story += _section_heading("Projects", styles)
        for proj in variant["projects"]:
            dates = f'  <font color="#555555"><i>({proj["dates"]})</i></font>' if proj.get("dates") else ""
            story.append(Paragraph(f'<b>{proj["title"]}</b>{dates}', styles["JobTitle"]))
            for bullet in proj["bullets"]:
                story.append(Paragraph(f"\u2022  {bullet}", styles["BulletText"]))

    # Education
    story += _section_heading("Education", styles)
    for edu in variant["education"]:
        story.append(Paragraph(
            f'<b>{edu["degree"]}</b><br/>'
            f'{edu["school"]} — {edu["location"]}  |  {edu["date"]}',
            styles["EduText"],
        ))

    # Publications
    if variant.get("publications"):
        story += _section_heading("Publications", styles)
        for pub in variant["publications"]:
            story.append(Paragraph(f"\u2022  {pub}", styles["BulletText"]))

    return story


# ── Public API ────────────────────────────────────────────────────────────────

def build_pdf(variant: dict, output_path: Path) -> Path:
    """
    Build a clean professional PDF from a resume variant dict.
    Returns the path to the saved PDF.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    styles = _build_styles()

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        topMargin=0.55 * inch,
        bottomMargin=0.55 * inch,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
    )

    story = _build_story(variant, styles)
    doc.build(story)
    return output_path


if __name__ == "__main__":
    import sys
    import logging
    logging.basicConfig(level=logging.INFO)
    sys.path.insert(0, ".")
    from resumes.base_data import DATA_ENGINEER, DATA_ANALYST, SQL_ENGINEER, SDE

    variants = {
        "data_engineer": DATA_ENGINEER,
        "data_analyst":  DATA_ANALYST,
        "sql_engineer":  SQL_ENGINEER,
        "sde":           SDE,
    }
    out_dir = Path("resumes/generated")
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, v in variants.items():
        label = name.replace("_", " ").title().replace(" ", "_")
        p = out_dir / f"Bhuvan_Thatthari_{label}.pdf"
        build_pdf(v, p)
        print(f"Built: {p}")
