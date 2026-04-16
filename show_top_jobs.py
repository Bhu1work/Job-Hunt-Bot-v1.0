"""Show top 20 ATS-scored jobs. Zero API calls."""
from ats_scorer import score_all_pending_jobs

jobs = score_all_pending_jobs(threshold=80)
print(f"\nJobs scoring 80+: {len(jobs)}\n")
print(f"{'#':>3}  {'Score':>5}  {'Grade':>5}  {'Role':<36} {'Company':<22} {'Missing Top 3'}")
print("-" * 100)
for i, j in enumerate(jobs[:20], 1):
    role    = j["job"]["role"][:35]
    company = j["job"]["company"][:20]
    missing = ", ".join(j["missing_keywords"][:3]) or "—"
    print(f"{i:>3}.  {j['ats_score']:>3}/100  ({j['ats_grade']})  {role:<36} {company:<22} {missing}")
