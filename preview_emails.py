"""
Preview all 3 cold email templates with real data — no API call needed if dry_run=True.
Run: docker compose run --rm bot python preview_emails.py
     docker compose run --rm bot python preview_emails.py --live   (calls Claude)
"""
import argparse
from phase2_resume_tailor import _cold_email_prompt, load_master_resume, generate_cold_email
from database import get_db, init_db, get_job

SAMPLE_JD = """
Senior Data Engineer – We're scaling our data platform fast. 
You'll build and own real-time event pipelines, Kafka + Spark + Airflow stack, 
optimize Snowflake queries, and mentor 2-3 junior engineers. 
5+ years Python, strong dbt, Redshift/Snowflake experience required.
"""

SAMPLE_CONTACTS = [
    {"name": "Jay Raina",      "title": "VP of Engineering",       "contact_type": "hiring_manager", "email": "jay@example.com"},
    {"name": "Sarah Chen",     "title": "Engineering Manager",      "contact_type": "hiring_manager", "email": "sarah@example.com"},
    {"name": "Alex Torres",    "title": "Technical Recruiter",      "contact_type": "hr",             "email": "alex@example.com"},
]

SAMPLE_JOB = {
    "id": 1,
    "company": "SunStrong Management",
    "role": "Senior Data Engineer",
    "description": SAMPLE_JD,
}


def preview_templates(live: bool = False) -> None:
    resume = load_master_resume()
    print(f"\nResume loaded: {len(resume)} chars\n")

    for i, (contact, tmpl) in enumerate(zip(SAMPLE_CONTACTS, [1, 2, 3]), 1):
        print(f"{'='*65}")
        print(f"TEMPLATE {tmpl}  |  To: {contact['name']} ({contact['contact_type']})")
        print(f"{'='*65}")

        if live:
            result = generate_cold_email(SAMPLE_JOB, contact, resume, template_num=tmpl)
            print(f"Subject: {result['subject']}")
            print()
            print(result["body"])
        else:
            # Show the prompt Claude would receive
            prompt = _cold_email_prompt(
                jd=SAMPLE_JD,
                company="SunStrong Management",
                role="Senior Data Engineer",
                contact_name=contact["name"],
                contact_title=contact["title"],
                contact_type=contact["contact_type"],
                master_resume=resume,
                template_num=tmpl,
            )
            print("[DRY RUN — showing prompt Claude would receive]")
            print(prompt[:800])
        print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true",
                        help="Actually call Claude API (uses credits)")
    args = parser.parse_args()

    init_db()
    preview_templates(live=args.live)
    if not args.live:
        print("\nAdd --live to generate real emails (requires Claude credits).")
