"""
Utility: Extract plain text from your resume DOCX/PDF → saves to assets/master_resume.txt

Run once:
    python utils/extract_resume.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
DOCX_PATH = ROOT / "Resume" / "Bhuvan DE.docx"
PDF_PATH  = ROOT / "Resume" / "BHUVANSAIDE.pdf"
OUT_PATH  = ROOT / "assets" / "master_resume.txt"


def from_docx(path: Path) -> str:
    try:
        import docx  # python-docx
        doc = docx.Document(str(path))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except ImportError:
        print("Install python-docx:  pip install python-docx")
        sys.exit(1)


def from_pdf(path: Path) -> str:
    try:
        import PyPDF2
        text_parts = []
        with open(path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                text_parts.append(page.extract_text() or "")
        return "\n".join(text_parts)
    except ImportError:
        print("Install PyPDF2:  pip install PyPDF2")
        sys.exit(1)


def main() -> None:
    if DOCX_PATH.exists():
        print(f"Extracting from DOCX: {DOCX_PATH}")
        text = from_docx(DOCX_PATH)
    elif PDF_PATH.exists():
        print(f"Extracting from PDF: {PDF_PATH}")
        text = from_pdf(PDF_PATH)
    else:
        print(f"No resume file found at {DOCX_PATH} or {PDF_PATH}")
        sys.exit(1)

    OUT_PATH.parent.mkdir(exist_ok=True)
    OUT_PATH.write_text(text, encoding="utf-8")
    print(f"Saved {len(text)} chars → {OUT_PATH}")
    print("\nFirst 500 chars preview:")
    print(text[:500])


if __name__ == "__main__":
    main()
