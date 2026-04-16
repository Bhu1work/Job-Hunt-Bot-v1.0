"""Central configuration — loads .env and exposes typed settings."""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
ASSETS_DIR = BASE_DIR / "assets"
LOGS_DIR = BASE_DIR / "logs"
CREDENTIALS_DIR = BASE_DIR / "credentials"

for _d in (DATA_DIR, ASSETS_DIR, LOGS_DIR, CREDENTIALS_DIR):
    _d.mkdir(exist_ok=True)

DB_PATH = os.getenv("DB_PATH", str(DATA_DIR / "jobs.db"))
MASTER_RESUME_PATH = os.getenv("MASTER_RESUME_PATH", str(ASSETS_DIR / "master_resume.txt"))
RESUME_PDF_PATH = os.getenv("RESUME_PDF_PATH", str(ASSETS_DIR / "resume.pdf"))

# ── API Keys ─────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
HUNTER_API_KEY = os.getenv("HUNTER_API_KEY", "")
APOLLO_API_KEY = os.getenv("APOLLO_API_KEY", "")

# ── LinkedIn ─────────────────────────────────────────────────────────────────
LINKEDIN_EMAIL = os.getenv("LINKEDIN_EMAIL", "")
LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASSWORD", "")

# ── Google Sheets ─────────────────────────────────────────────────────────────
GOOGLE_SHEETS_SPREADSHEET_ID = os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID", "")
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv(
    "GOOGLE_SERVICE_ACCOUNT_JSON",
    str(CREDENTIALS_DIR / "google_service_account.json"),
)

# ── Slack ─────────────────────────────────────────────────────────────────────
SLACK_BOT_TOKEN   = os.getenv("SLACK_BOT_TOKEN",   "")   # xoxb-...
SLACK_APP_TOKEN   = os.getenv("SLACK_APP_TOKEN",   "")   # xapp-... (Socket Mode)
SLACK_CHANNEL_ID  = os.getenv("SLACK_CHANNEL_ID",  "")   # C... (channel ID, not name)
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")   # optional incoming webhook

# ── SMTP ──────────────────────────────────────────────────────────────────────
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")

# ── Personal info ─────────────────────────────────────────────────────────────
YOUR_NAME         = os.getenv("YOUR_NAME",         "Bhuvan Sai Thatthari")
YOUR_EMAIL        = os.getenv("YOUR_EMAIL",         "bhuvanthatthari@gmail.com")
YOUR_PHONE        = os.getenv("YOUR_PHONE",         "+1 (571) 241-2211")
YOUR_LINKEDIN     = os.getenv("YOUR_LINKEDIN",      "linkedin.com/in/saithatthari")
YOUR_GITHUB       = os.getenv("YOUR_GITHUB",        "github.com/saithatthari")
YOUR_FIELD        = os.getenv("YOUR_FIELD",         "Data Engineering")
YOUR_VISA_STATUS  = os.getenv("YOUR_VISA_STATUS",   "Requires H1B Sponsorship")
YOUR_LOCATION     = os.getenv("YOUR_LOCATION",      "New York, USA")

# ── Claude model selection ────────────────────────────────────────────────────
# Use haiku for cheap tasks (cold emails, scoring), sonnet/opus for resumes
CLAUDE_MODEL        = os.getenv("CLAUDE_MODEL",        "claude-opus-4-5")
CLAUDE_MODEL_FAST   = os.getenv("CLAUDE_MODEL_FAST",   "claude-haiku-4-5")

# ATS minimum score (0-100) to include a job in the pipeline
ATS_MIN_SCORE       = int(os.getenv("ATS_MIN_SCORE", "80"))

# ── Scrape filters ────────────────────────────────────────────────────────────
# Only return jobs posted within N hours (e.g. 4). 0 = no filter.
SCRAPE_HOURS_FRESH     = int(os.getenv("SCRAPE_HOURS_FRESH", "4"))
# Only return mid-level positions (Associate / Mid-Senior on LinkedIn)
SCRAPE_MID_LEVEL_ONLY  = os.getenv("SCRAPE_MID_LEVEL_ONLY", "true").lower() == "true"

# ── Scraping targets ──────────────────────────────────────────────────────────
SEARCH_KEYWORDS: list[str] = [
    "Data Engineer",
    "Senior Data Engineer",
    "Data Analyst",
    "Analytics Engineer",
    "SQL Engineer",
    "Database Engineer",
    "Software Engineer Data",
    "Python Data Engineer",
]

SEARCH_LOCATIONS: list[str] = [
    "United States",
    "New York, NY",
    "Remote",
    "San Francisco, CA",
    "Seattle, WA",
    "Austin, TX",
    "Chicago, IL",
]

# ── SMTP (for follow-up emails + cold emails) ─────────────────────────────────
# Set SMTP_USER and SMTP_PASSWORD in .env
# For Gmail: use App Password (myaccount.google.com/apppasswords)
APPLICATION_EMAIL = "bhuvanthatthari@gmail.com"   # email used on ALL applications

# ── Follow-up schedule (days after apply) ────────────────────────────────────
FOLLOWUP_DAYS: list[int] = [3, 7, 14]

CLAUDE_MAX_TOKENS = 4096


# ── API key validation ────────────────────────────────────────────────────────

class APIKeyError(SystemExit):
    """Raised when a required API key is missing or invalid."""


def validate_keys(
    require_claude: bool = False,
    require_hunter: bool = False,
    require_apollo: bool = False,
    require_smtp: bool = False,
) -> None:
    """
    Validate that required API keys are present before a phase runs.
    Raises APIKeyError with a human-readable message and fix instructions.
    Call at the top of each phase's run() function.
    """
    errors: list[str] = []

    if require_claude and not ANTHROPIC_API_KEY.strip():
        errors.append(
            "ANTHROPIC_API_KEY is missing.\n"
            "  Get it at: https://console.anthropic.com\n"
            "  Add to .env:  ANTHROPIC_API_KEY=sk-ant-..."
        )

    if require_hunter and not HUNTER_API_KEY.strip():
        errors.append(
            "HUNTER_API_KEY is missing.\n"
            "  Get it at: https://hunter.io/api-keys\n"
            "  Add to .env:  HUNTER_API_KEY=..."
        )

    if require_apollo and not APOLLO_API_KEY.strip():
        errors.append(
            "APOLLO_API_KEY is missing.\n"
            "  Get it at: https://app.apollo.io/#/settings/integrations/api\n"
            "  Add to .env:  APOLLO_API_KEY=..."
        )

    if require_smtp and not SMTP_PASSWORD.strip():
        errors.append(
            "SMTP_PASSWORD is missing — needed to send emails.\n"
            "  Generate a Gmail App Password at: https://myaccount.google.com/apppasswords\n"
            "  Add to .env:  SMTP_PASSWORD=xxxx xxxx xxxx xxxx"
        )

    if errors:
        divider = "\n" + "─" * 60 + "\n"
        msg = (
            divider
            + "  JOB HUNT BOT — API KEY ERROR\n"
            + divider
            + "\n".join(f"  {i+1}. {e}" for i, e in enumerate(errors))
            + divider
        )
        raise APIKeyError(msg)


def check_credit_error(exc: Exception, service: str) -> None:
    """
    Inspect a caught exception and raise a clear SystemExit if it's a
    credit-exhaustion or auth error. Otherwise re-raises the original exception.

    Usage:
        except Exception as e:
            check_credit_error(e, "Claude")
            raise   # not a credit/auth error — re-raise normally
    """
    msg = str(exc).lower()
    service_links = {
        "claude":   "https://console.anthropic.com/billing",
        "hunter":   "https://hunter.io/users/billing",
        "apollo":   "https://app.apollo.io/#/settings/billing",
    }
    link = service_links.get(service.lower(), "")

    # Credit / quota exhausted signals
    credit_signals = [
        "credit", "quota", "insufficient", "billing",
        "usage limit", "rate limit", "402", "payment",
        "overloaded", "capacity",
    ]
    # Auth / invalid key signals
    auth_signals = [
        "authentication", "unauthorized", "invalid api key",
        "invalid x-api-key", "403", "401", "forbidden",
        "permission denied",
    ]

    if any(s in msg for s in credit_signals):
        raise SystemExit(
            f"\n{'─'*60}\n"
            f"  {service} credits exhausted or quota reached.\n"
            f"  Top up or upgrade at: {link}\n"
            f"{'─'*60}"
        )

    if any(s in msg for s in auth_signals):
        raise SystemExit(
            f"\n{'─'*60}\n"
            f"  {service} API key is invalid or rejected.\n"
            f"  Check the key in your .env file.\n"
            f"  Get a new key at: {link}\n"
            f"{'─'*60}"
        )
