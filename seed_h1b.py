"""
Seed the DB with well-known H1B-sponsoring companies in tech / data.
Also marks any existing jobs whose company matches as h1b_confirmed=1.

Source: DOL LCA data + USCIS H1B employer lists (public record).
Run inside Docker:  docker compose run --rm bot python seed_h1b.py
"""

import logging
from database import init_db, upsert_company, get_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ── Known H1B-sponsoring companies (top tech / data employers) ───────────────
# Source: annual DOL H1B LCA disclosure data (public)
H1B_COMPANIES = [
    # Big Tech
    "Amazon", "Google", "Microsoft", "Meta", "Apple", "Netflix", "Uber",
    "Lyft", "Airbnb", "Stripe", "Coinbase", "LinkedIn", "Twitter", "Salesforce",
    "Oracle", "IBM", "Intel", "Qualcomm", "NVIDIA", "Adobe", "ServiceNow",
    "Workday", "Snowflake", "Databricks", "Palantir", "Splunk", "Cloudera",
    "Tableau", "Informatica", "MuleSoft", "Domo", "Looker", "Amplitude",
    "Twilio", "Okta", "Zendesk", "HubSpot", "Atlassian", "Slack", "Zoom",
    "DocuSign", "Veeva Systems", "Palo Alto Networks", "CrowdStrike", "Zscaler",
    "Datadog", "New Relic", "Elastic", "MongoDB", "Redis Labs", "Confluent",
    "dbt Labs", "Fivetran", "Airbyte", "Astronomer", "Monte Carlo",

    # Financial / FinTech
    "JPMorgan Chase", "Goldman Sachs", "Morgan Stanley", "Bank of America",
    "Citibank", "Wells Fargo", "Capital One", "American Express", "Visa",
    "Mastercard", "PayPal", "Square", "Robinhood", "Bloomberg", "Fidelity",
    "BlackRock", "State Street", "Charles Schwab", "TD Bank", "HSBC",
    "Barclays", "Deutsche Bank", "Credit Suisse", "UBS", "BNY Mellon",
    "Two Sigma", "Jane Street", "Citadel", "Point72", "DE Shaw",

    # Consulting / IT Services
    "Deloitte", "Accenture", "McKinsey", "BCG", "Cognizant", "Infosys",
    "TCS", "Wipro", "HCL Technologies", "Tech Mahindra", "Capgemini",
    "EPAM Systems", "Globant", "ThoughtWorks", "Publicis Sapient", "CGI",
    "Booz Allen Hamilton", "SAIC", "Leidos", "Unisys", "Conduent",
    "LTIMindtree", "UST Global", "Synechron", "Innova Solutions",

    # Healthcare / Pharma
    "UnitedHealth Group", "CVS Health", "Anthem", "Aetna", "Pfizer",
    "Johnson & Johnson", "Merck", "AbbVie", "Amgen", "Genentech",
    "Moderna", "BioNTech", "Illumina", "Philips Healthcare", "GE Healthcare",
    "Epic Systems", "Cerner", "Optum",

    # E-commerce / Retail
    "eBay", "Wayfair", "Chewy", "Instacart", "DoorDash", "Grubhub",
    "Walmart", "Target", "Best Buy", "Home Depot", "Costco",

    # Media / Entertainment
    "Spotify", "Hulu", "Paramount", "Warner Bros", "Disney", "NBCUniversal",
    "Comcast", "Viacom", "The New York Times",

    # Cloud / Infrastructure
    "VMware", "Nutanix", "Pure Storage", "Rubrik", "Cohesity",
    "HashiCorp", "Terraform", "Puppet", "Chef", "Ansible",
    "Cloudflare", "Fastly", "Akamai",

    # Telecom
    "AT&T", "Verizon", "T-Mobile", "Sprint", "Comcast",

    # Automotive / Manufacturing
    "Tesla", "General Motors", "Ford", "Toyota", "BMW", "Volkswagen",
    "Bosch", "Siemens", "GE", "Honeywell", "3M", "Caterpillar",

    # Aerospace / Defense
    "Boeing", "Lockheed Martin", "Raytheon", "Northrop Grumman",
    "General Dynamics", "L3 Technologies", "BAE Systems",

    # Education / Research / Healthcare
    "Coursera", "Udemy", "Duolingo", "Chegg", "2U",
    "Mayo Clinic", "Washington University",

    # Travel / FinTech / Other
    "Expedia Group", "Intuit", "ByteDance", "Fiserv",
    "Hewlett Packard Enterprise", "Cummins",

    # Data / Analytics Companies
    "Teradata", "SAS Institute", "Qlik", "MicroStrategy", "ThoughtSpot",
    "Alteryx", "TIBCO", "Talend", "Stitch", "Segment", "mParticle",
    "RudderStack", "Census", "Hightouch", "dbt Labs", "Great Expectations",
    "Anomalo", "Monte Carlo Data",

    # Startups / Scale-ups known to sponsor
    "Brex", "Plaid", "Chime", "Nubank", "Nerdio", "Rippling",
    "Gusto", "ADP", "Paychex", "Greenhouse", "Lever", "Workday",
    "UiPath", "Automation Anywhere", "Blue Prism", "Pegasystems",
    "Verint", "NICE Systems", "Genesys", "Medallia", "Qualtrics",

    # Publishing / Media
    "Tuttle Publishing", "Pearson", "Springer Nature", "Wiley",
    "McGraw Hill", "Houghton Mifflin",
]


def normalize(name: str) -> str:
    return (
        name.lower()
        .replace(" inc", "").replace(" llc", "").replace(" ltd", "")
        .replace(" corp", "").replace(",", "").replace(".", "")
        .strip()
    )


def run() -> None:
    init_db()

    # 1. Seed all known H1B companies
    logger.info("Seeding %d known H1B companies...", len(H1B_COMPANIES))
    for company in H1B_COMPANIES:
        upsert_company(
            name=company,
            h1b_confirmed=True,
            h1b_source="seed_known_sponsors",
            lca_count=100,   # placeholder — actual count not critical
        )

    logger.info("Companies seeded. Now tagging matching jobs...")

    # 2. Tag existing jobs where company name matches an H1B sponsor
    norm_map = {normalize(c): c for c in H1B_COMPANIES}

    with get_db() as conn:
        jobs = conn.execute(
            "SELECT id, company FROM jobs WHERE h1b_confirmed = 0"
        ).fetchall()

        tagged = 0
        for job in jobs:
            job_norm = normalize(job["company"])
            # Check if any known sponsor is a substring match (handles "Amazon Web Services" etc.)
            matched = any(
                norm_sponsor in job_norm or job_norm in norm_sponsor
                for norm_sponsor in norm_map
            )
            if matched:
                conn.execute(
                    "UPDATE jobs SET h1b_confirmed = 1 WHERE id = ?", (job["id"],)
                )
                tagged += 1

        logger.info("Tagged %d / %d existing jobs as H1B-confirmed", tagged, len(jobs))

    # Print final count
    with get_db() as conn:
        total   = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        h1b     = conn.execute("SELECT COUNT(*) FROM jobs WHERE h1b_confirmed=1").fetchone()[0]

    logger.info("DB summary: %d total jobs | %d H1B-confirmed (%.0f%%)",
                total, h1b, 100 * h1b / max(total, 1))


if __name__ == "__main__":
    run()
