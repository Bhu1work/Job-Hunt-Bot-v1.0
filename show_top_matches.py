"""show_top_matches.py -- ATS score all pending jobs and show top matches."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from ats_scorer import score_all_pending_jobs

results = score_all_pending_jobs(threshold=0)
print(f"Scored {len(results)} jobs\n")
print("-" * 90)
print(f"{'#':>3}  {'Score':>6}  {'Role':<45}  {'Company':<22}  Location")
print("-" * 90)
for i, r in enumerate(results[:25], 1):
    j = r["job"]
    score = r["ats_score"]
    grade = r["ats_grade"]
    role = j["role"][:44]
    company = j["company"][:21]
    loc = j["location"][:28]
    flag = " <-- APPLY" if score >= 80 else ""
    print(f"{i:3}.  {score:3}/100 {grade:<2}  {role:<45}  {company:<22}  {loc}{flag}")
print("-" * 90)
above80 = sum(1 for r in results if r["ats_score"] >= 80)
print(f"\n{above80} jobs score >=80 (ATS-ready to apply)")
