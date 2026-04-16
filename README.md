# Job Hunt Bot — H1B Edition

Fully automated job application pipeline for Data Engineers targeting H1B-sponsoring companies.

```
LinkedIn / Indeed
      │
      ▼
Phase 1 — Scrape          Finds jobs, filters for H1B-sponsoring companies
      │
      ▼
ATS Scorer                Scores each job 0–100 against your resume (zero API cost)
      │
      ▼
Slack → /jobs             YOU pick which jobs to apply to (saves Claude credits)
      │
      ▼
Phase 2 — Claude Tailor   Tailors resume + cover letter + cold email per job
      │
      ▼
Phase 3 — Email Finder    Hunter.io / Apollo.io finds hiring manager emails
      │
      ▼
Phase 5 — Send Emails     Cold emails sent from your Gmail
      │
      ▼
Phase 4 — Auto-Apply      Playwright fills ATS forms (Greenhouse/Lever/Workday)
      │
      ▼
Phase 5 — Follow-ups      Auto follow-up emails at day 3, 7, 14
```

---

## Prerequisites

- Docker Desktop installed and running
- A Slack workspace (free)
- API keys (see Setup section)

---

## Quick Start

### 1. Clone and configure

```bash
git clone <repo-url>
cd job-hunt-bot
cp .env .env.backup   # keep a backup
```

Edit `.env` — fill in every value (see API Keys section below).

### 2. Build the Docker image

```bash
docker compose build builder
```

### 3. Run the smoke test

```bash
docker compose run --rm bot python smoke_test.py
```

All 11 checks should pass before you proceed.

### 4. Seed H1B companies and reset test data

```bash
# Seed known H1B-sponsoring companies into the DB
docker compose run --rm bot python seed_h1b.py

# If you ran any test applications, wipe them first
docker compose run --rm bot python reset_test_jobs.py --dry-run   # preview
docker compose run --rm bot python reset_test_jobs.py             # apply
```

### 5. Start the Slack bot and follow-up scheduler

```bash
docker compose up -d slack scheduler
docker compose logs slack    # should show "Job Hunt Bot online!"
```

---

## API Keys Setup

### Required

| Key | Where to get it | `.env` variable |
|-----|----------------|-----------------|
| Anthropic (Claude) | [console.anthropic.com](https://console.anthropic.com) | `ANTHROPIC_API_KEY` |
| Hunter.io | [hunter.io/api-keys](https://hunter.io/api-keys) | `HUNTER_API_KEY` |
| Apollo.io | [app.apollo.io → Settings → API](https://app.apollo.io/#/settings/integrations/api) | `APOLLO_API_KEY` |
| Gmail App Password | [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords) | `SMTP_PASSWORD` |
| Slack Bot Token | See Slack Setup below | `SLACK_BOT_TOKEN` |
| Slack App Token | See Slack Setup below | `SLACK_APP_TOKEN` |
| Slack Channel ID | See Slack Setup below | `SLACK_CHANNEL_ID` |

### Optional

| Key | Purpose | `.env` variable |
|-----|---------|-----------------|
| Google Service Account | Google Sheets sync | `GOOGLE_SERVICE_ACCOUNT_JSON` |
| Google Sheets ID | Spreadsheet to sync jobs to | `GOOGLE_SHEETS_SPREADSHEET_ID` |
| Slack Webhook URL | Daily digest (alternative to bot) | `SLACK_WEBHOOK_URL` |

---

## Slack Setup (10 min, one-time)

### 1. Create the app

1. Go to [api.slack.com/apps](https://api.slack.com/apps) → **Create New App** → **From scratch**
2. Name: `Job Hunt Bot` → pick your workspace → **Create App**

### 2. Get your Bot Token (`SLACK_BOT_TOKEN`)

1. Left sidebar → **OAuth & Permissions** → **Bot Token Scopes** → Add:
   - `chat:write`, `commands`, `im:write`, `channels:read`
2. **Install to Workspace** → **Allow**
3. Copy **Bot User OAuth Token** (`xoxb-...`) → paste into `.env`

### 3. Get your App Token (`SLACK_APP_TOKEN`)

1. Left sidebar → **Settings → Socket Mode** → Enable **Socket Mode**
2. Generate a token (name: `socket`, scope: `connections:write`)
3. Copy token (`xapp-...`) → paste into `.env`

### 4. Register Slash Commands

Left sidebar → **Slash Commands** → create each (URL: `https://placeholder.com`):

| Command | Description |
|---------|-------------|
| `/jobs` | Show top ATS-scored jobs to select |
| `/apply` | Run pipeline for selected jobs |
| `/stats` | Stats dashboard |
| `/scrape` | Scrape fresh jobs now |
| `/reset` | Clear current selections |
| `/help` | Show all commands |

### 5. Enable Interactivity

Left sidebar → **Interactivity & Shortcuts** → Enable → URL: `https://placeholder.com`

### 6. Get Channel ID

1. Create `#job-hunt` channel in your Slack workspace
2. Type `/invite @Job Hunt Bot` in the channel
3. Right-click channel name → **Copy Link** → grab the `C...` ID at the end
4. Paste into `.env` as `SLACK_CHANNEL_ID`

---

## Daily Workflow

### Morning (3 steps in Slack)

```
/scrape       → Fetches fresh LinkedIn jobs in background (auto-filters H1B companies)

/jobs         → Shows top 20 ATS-scored jobs with scores
              → Use the dropdown to select 5–8 you want
              → Click "Apply to Selected"

              Bot runs automatically:
                Phase 2: Claude tailors resume + cover letter + cold email per job
                Phase 3: Finds hiring manager emails (Hunter.io / Apollo.io)
                Send:    Cold emails go out from your Gmail
```

### Evening

```
/stats        → Check emails sent, applied count, pending drafts
```

### Background (always running)

```
docker compose up -d scheduler
```
Sends follow-up emails automatically:
- **Day 3** after each application
- **Day 7** — second follow-up
- **Day 14** — final follow-up
- **6 PM daily** — Slack digest of the day's activity

---

## Manual Pipeline Commands

```bash
# Phase 1 — Scrape jobs only
docker compose run --rm bot python main.py --phase 1 --pages 8

# Phase 2 — Tailor resumes for all pending jobs
docker compose run --rm bot python main.py --phase 2

# Phase 2 — Tailor specific jobs
docker compose run --rm bot python main.py --phase 2 --job-ids 42,55,61

# Phase 3 — Find emails only
docker compose run --rm bot python main.py --phase 3

# Phase 4 — Auto-apply (Playwright ATS form filler)
docker compose run --rm bot python main.py --phase 4

# Send cold emails now
docker compose run --rm bot python phase5_followup.py --send-cold

# Send cold emails (limit 10)
docker compose run --rm bot python phase5_followup.py --send-cold --limit 10

# Full pipeline (phases 1→2→3→4 in sequence)
docker compose run --rm bot python main.py --all

# Print stats
docker compose run --rm bot python main.py --stats
```

---

## Utility Scripts

| Script | Purpose |
|--------|---------|
| `smoke_test.py` | Full QA check — run before any real usage |
| `reset_test_jobs.py` | Wipe test applications from DB, start fresh |
| `seed_h1b.py` | Seed known H1B-sponsoring companies into DB |
| `fix_emails.py` | Purge bad AI-generated draft emails |
| `fix_emails.py --regen` | Purge and regenerate all cold email drafts |
| `audit.py --job-id 42` | Review sent applications and emails |
| `audit.py --emails-only` | Review all sent emails |
| `preview_emails.py` | Preview cold email templates dry-run |
| `preview_emails.py --live` | Preview with live Claude call |
| `save_email_drafts.py` | Export email drafts from DB to application folders |

---

## Docker Services

```bash
docker compose up -d slack       # Slack bot (interactive job picker)
docker compose up -d scheduler   # Follow-up daemon (runs 24/7)

docker compose run --rm scraper  # One-off: Phase 1 scrape
docker compose run --rm tailor   # One-off: Phase 2 tailor
docker compose run --rm emailer  # One-off: Phase 3 find emails
docker compose run --rm applier  # One-off: Phase 4 auto-apply

docker compose logs slack        # Watch Slack bot logs
docker compose logs scheduler    # Watch follow-up logs
docker compose down              # Stop all services
```

---

## File Structure

```
job-hunt-bot/
├── .env                     ← API keys + personal info (never commit)
├── Dockerfile               ← Docker image definition
├── docker-compose.yml       ← Service orchestration
├── requirements.txt         ← Python dependencies
│
├── main.py                  ← Pipeline orchestrator (--phase, --all, --stats)
├── config.py                ← Central config, loaded from .env
├── database.py              ← SQLite schema + CRUD helpers
│
├── phase1_scraper.py        ← LinkedIn/Indeed scraper + H1B filter
├── phase2_resume_tailor.py  ← Claude resume tailoring + cover letter + cold email
├── phase3_email_finder.py   ← Hunter.io / Apollo.io email discovery
├── phase4_auto_apply.py     ← Playwright ATS form automation
├── phase5_followup.py       ← Follow-up scheduler + Slack digest + SMTP sender
│
├── ats_scorer.py            ← ATS keyword scorer (0 API calls)
├── slack_bot.py             ← Slack bot (Socket Mode, /jobs, /apply, /stats…)
├── application_manager.py   ← Per-job folder management
├── resume_builder.py        ← DOCX resume generation
├── pdf_builder.py           ← PDF resume generation
│
├── smoke_test.py            ← QA health check (run before production)
├── reset_test_jobs.py       ← Wipe test runs from DB
├── seed_h1b.py              ← Seed H1B-sponsoring companies
├── fix_emails.py            ← Purge / regenerate bad email drafts
├── audit.py                 ← Review sent applications + emails
│
├── assets/
│   └── master_resume.txt    ← Base resume (Claude uses this as input for all tailoring)
├── resumes/
│   ├── base_data.py         ← Structured resume data (4 variants: DE/DA/SQL/SDE)
│   └── generated/           ← Generated base DOCX/PDF files
├── applications/            ← Per-application folders (resume, cover letter, emails)
├── data/
│   └── jobs.db              ← SQLite database
└── logs/
    └── main.log             ← Execution logs
```

---

## Database Schema

| Table | Purpose |
|-------|---------|
| `jobs` | All scraped jobs with status, ATS score, H1B flag |
| `companies` | H1B-confirmed companies with LCA counts |
| `tailored_docs` | Claude-generated resume bullets + cover letters |
| `contacts` | Found emails (hiring managers, HR) |
| `outreach` | Cold emails + follow-ups (draft/sent/replied) |
| `activity_log` | Full audit trail of all bot actions |

---

## How H1B Filtering Works

The H1B filter is **backend-only** — it never appears in outbound emails or cover letters.

1. `seed_h1b.py` pre-loads ~500 known H1B-sponsoring companies into the `companies` table
2. `phase1_scraper.py` cross-references each scraped job's company against this list
3. Only `h1b_confirmed=1` jobs enter the pipeline (ATS scoring, Claude tailoring, email sending)
4. Cold emails and cover letters contain **zero mention** of visa, H1B, sponsorship, or OPT
5. ATS form fields (Greenhouse/Lever/Workday) answer "Yes" to work authorization — which is correct as you are authorized to work on STEM OPT

---

## Cost Breakdown (approximate)

| Service | Usage | Cost |
|---------|-------|------|
| Claude Haiku | Cold emails (~300/run) | ~$0.25 |
| Claude Opus | Resume + cover letter per job | ~$0.10/job |
| Hunter.io | 25 free searches/month | Free tier |
| Apollo.io | 150 free credits/month | Free tier |
| Slack | All features used | Free |
| Docker | Local compute | Free |

**Estimated total per day: ~$1–2** (10 selected jobs × resume + CL + email)

---

## Troubleshooting

**Slack bot not responding to commands**
- Check logs: `docker compose logs slack`
- Ensure Interactivity is enabled in Slack App settings
- Verify `SLACK_APP_TOKEN` starts with `xapp-` (not `xoxb-`)

**Claude API errors**
- `401 Unauthorized` → invalid API key, check `ANTHROPIC_API_KEY` in `.env`
- `429 / credits` → top up at [console.anthropic.com/billing](https://console.anthropic.com/billing)

**No jobs showing in `/jobs`**
- Run `/scrape` first, or: `docker compose run --rm scraper`
- Run `docker compose run --rm bot python seed_h1b.py` if H1B count is 0

**Emails not sending**
- Check `SMTP_PASSWORD` is a Gmail **App Password** (16 chars, no spaces)
- Generate at: [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
- Ensure "Less secure apps" or 2FA + App Password is enabled on your Google account

**Reset test data**
```bash
docker compose run --rm bot python reset_test_jobs.py
```
