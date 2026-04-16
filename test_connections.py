"""
Live connection test for all configured API keys.
Run:  python test_connections.py
"""

import sys
import smtplib
import requests
from dotenv import load_dotenv

load_dotenv()
import config

PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"

results: list[tuple[str, str, str]] = []   # (service, status, message)


# ── 1. Claude (Anthropic) ─────────────────────────────────────────────────────
def test_claude() -> None:
    if not config.ANTHROPIC_API_KEY.strip():
        results.append(("Claude", SKIP, "ANTHROPIC_API_KEY not set"))
        return
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY.strip())
        msg = client.messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=10,
            messages=[{"role": "user", "content": "Reply with the word CONNECTED only."}],
        )
        reply = msg.content[0].text.strip()
        results.append(("Claude", PASS, f"Model={config.CLAUDE_MODEL}  reply='{reply}'"))
    except Exception as exc:
        err = str(exc)
        if "authentication" in err.lower() or "401" in err:
            results.append(("Claude", FAIL, "API key invalid — check ANTHROPIC_API_KEY"))
        elif "credit" in err.lower() or "402" in err or "billing" in err.lower():
            results.append(("Claude", FAIL, "Credits exhausted — top up at console.anthropic.com/billing"))
        else:
            results.append(("Claude", FAIL, err[:120]))


# ── 2. Hunter.io ──────────────────────────────────────────────────────────────
def test_hunter() -> None:
    if not config.HUNTER_API_KEY.strip():
        results.append(("Hunter.io", SKIP, "HUNTER_API_KEY not set"))
        return
    try:
        resp = requests.get(
            "https://api.hunter.io/v2/account",
            params={"api_key": config.HUNTER_API_KEY},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json().get("data", {})
            plan   = data.get("plan_name", "unknown")
            used   = data.get("requests", {}).get("used", "?")
            total  = data.get("requests", {}).get("available", "?")
            results.append(("Hunter.io", PASS,
                             f"Plan={plan}  requests={used}/{total} used"))
        elif resp.status_code == 401:
            results.append(("Hunter.io", FAIL, "API key invalid — check HUNTER_API_KEY"))
        elif resp.status_code == 402:
            results.append(("Hunter.io", FAIL, "Credits exhausted — upgrade at hunter.io/users/billing"))
        else:
            results.append(("Hunter.io", FAIL, f"HTTP {resp.status_code}"))
    except Exception as exc:
        results.append(("Hunter.io", FAIL, str(exc)[:120]))


# ── 3. Apollo.io ──────────────────────────────────────────────────────────────
def test_apollo() -> None:
    if not config.APOLLO_API_KEY.strip():
        results.append(("Apollo.io", SKIP, "APOLLO_API_KEY not set"))
        return
    try:
        resp = requests.get(
            "https://api.apollo.io/v1/auth/health",
            headers={"X-Api-Key": config.APOLLO_API_KEY, "Cache-Control": "no-cache"},
            timeout=10,
        )
        if resp.status_code == 200:
            results.append(("Apollo.io", PASS, "Auth OK"))
        elif resp.status_code == 401:
            results.append(("Apollo.io", FAIL, "API key invalid — check APOLLO_API_KEY"))
        else:
            # Apollo /health may 404 on some plans; try a minimal people search
            resp2 = requests.post(
                "https://api.apollo.io/v1/mixed_people/search",
                json={"q_organization_domains": "google.com", "page": 1, "per_page": 1},
                headers={"X-Api-Key": config.APOLLO_API_KEY, "Content-Type": "application/json"},
                timeout=10,
            )
            if resp2.status_code in (200, 201):
                results.append(("Apollo.io", PASS, "People search OK"))
            elif resp2.status_code == 401:
                results.append(("Apollo.io", FAIL, "API key invalid — check APOLLO_API_KEY"))
            else:
                results.append(("Apollo.io", FAIL, f"HTTP {resp2.status_code}"))
    except Exception as exc:
        results.append(("Apollo.io", FAIL, str(exc)[:120]))


# ── 4. Gmail SMTP ─────────────────────────────────────────────────────────────
def test_smtp() -> None:
    if not config.SMTP_PASSWORD.strip():
        results.append(("Gmail SMTP", SKIP, "SMTP_PASSWORD not set"))
        return
    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.login(config.SMTP_USER, config.SMTP_PASSWORD)
        results.append(("Gmail SMTP", PASS,
                         f"Login OK as {config.SMTP_USER}"))
    except smtplib.SMTPAuthenticationError:
        results.append(("Gmail SMTP", FAIL,
                         "Auth failed — wrong App Password or 2FA not enabled"))
    except Exception as exc:
        results.append(("Gmail SMTP", FAIL, str(exc)[:120]))


# ── Run & print ───────────────────────────────────────────────────────────────
def main() -> None:
    print("\nTesting API connections...\n")
    test_claude()
    test_hunter()
    test_apollo()
    test_smtp()

    # Print results table
    sep = "-" * 62
    print(sep)
    print(f"  {'SERVICE':<14} {'STATUS':<6}  DETAIL")
    print(sep)
    for service, status, msg in results:
        icon = "OK " if status == PASS else ("--" if status == SKIP else "!! ")
        print(f"  {service:<14} {icon} {status:<4}  {msg}")
    print(sep + "\n")

    failed = [r for r in results if r[1] == FAIL]
    passed = [r for r in results if r[1] == PASS]

    print(f"  {len(passed)} passed  |  {len(failed)} failed  |  "
          f"{len(results)-len(passed)-len(failed)} skipped\n")

    if failed:
        print("Fix the FAIL items above, then re-run: python test_connections.py\n")
        sys.exit(1)
    else:
        print("All configured APIs are working. Ready to run the bot!\n")


if __name__ == "__main__":
    main()
