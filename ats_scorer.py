"""
ATS (Applicant Tracking System) Keyword Scorer.

Pure keyword matching — zero Claude API calls.
Scores a resume against a job description on a 0-100 scale.

Scoring breakdown:
  - Hard skills / tech stack match   : 40 pts
  - Soft skills / action verbs       : 15 pts
  - Experience level match           : 15 pts
  - Education match                  : 10 pts
  - Quantified achievements present  : 10 pts
  - Job-title keyword match          : 10 pts
  Total possible                     : 100 pts

Usage:
    from ats_scorer import score_resume
    result = score_resume(jd_text, resume_text)
    print(result["score"], result["breakdown"], result["missing_keywords"])
"""

import re
from typing import TypedDict


class ATSResult(TypedDict):
    score: int
    grade: str
    breakdown: dict
    matched_keywords: list
    missing_keywords: list
    recommendation: str


# ── Keyword libraries ─────────────────────────────────────────────────────────

HARD_SKILLS = {
    # Cloud
    "aws", "azure", "gcp", "google cloud", "s3", "ec2", "lambda", "emr",
    "cloud formation", "terraform", "pulumi", "kubernetes", "k8s", "docker",
    "ecs", "eks", "databricks", "snowflake", "redshift", "bigquery", "synapse",
    # Data Engineering
    "spark", "pyspark", "apache spark", "kafka", "flink", "airflow",
    "prefect", "dagster", "luigi", "dbt", "data build tool", "fivetran",
    "glue", "data lake", "data lakehouse", "data warehouse", "etl", "elt",
    "data pipeline", "streaming", "batch processing", "real-time",
    "delta lake", "iceberg", "hudi", "parquet", "avro", "orc",
    # Databases
    "sql", "mysql", "postgresql", "postgres", "oracle", "sql server",
    "mongodb", "cassandra", "dynamodb", "redis", "elasticsearch",
    "hive", "hbase", "clickhouse", "pinot",
    # Programming
    "python", "scala", "java", "go", "golang", "rust", "r", "bash", "shell",
    "pyspark", "pandas", "numpy", "sqlalchemy",
    # Analytics / BI
    "tableau", "power bi", "looker", "metabase", "superset", "grafana",
    "data visualization", "dashboards", "reporting",
    # ML / AI
    "machine learning", "deep learning", "tensorflow", "pytorch", "sklearn",
    "scikit-learn", "mlflow", "feature engineering", "model deployment",
    # DevOps / CI-CD
    "git", "github", "gitlab", "ci/cd", "jenkins", "github actions",
    "devops", "infrastructure as code", "iac",
    # Data Quality
    "great expectations", "data quality", "data validation", "monitoring",
    "observability", "data catalog", "data governance", "lineage",
    # SDE
    "rest api", "restful", "graphql", "microservices", "grpc", "fastapi",
    "django", "flask", "spring boot", "node.js", "react", "typescript",
    "unit testing", "tdd", "pytest", "junit",
}

SOFT_SKILLS = {
    "leadership", "communication", "collaboration", "mentoring", "mentorship",
    "cross-functional", "stakeholder", "problem solving", "analytical",
    "ownership", "initiative", "agile", "scrum", "kanban",
}

STRONG_VERBS = {
    "architected", "designed", "built", "implemented", "developed", "led",
    "drove", "optimized", "reduced", "increased", "improved", "scaled",
    "deployed", "launched", "migrated", "automated", "streamlined",
    "collaborated", "partnered", "delivered", "owned", "managed",
}

EXPERIENCE_LEVEL_KEYWORDS = {
    "junior":      ["junior", "entry level", "entry-level", "associate", "0-2 years", "1 year"],
    "mid":         ["mid", "2-4 years", "3 years", "2+ years", "3+ years"],
    "senior":      ["senior", "5+ years", "4+ years", "sr.", "sr "],
    "staff":       ["staff", "7+ years", "8+ years", "principal", "tech lead"],
    "manager":     ["manager", "director", "head of", "vp ", "lead"],
}

EDUCATION_KEYWORDS = {
    "bachelor": ["bachelor", "bs", "b.s.", "b.e.", "undergraduate"],
    "master":   ["master", "ms", "m.s.", "msc", "m.sc.", "graduate"],
    "phd":      ["phd", "ph.d.", "doctorate"],
    "relevant": ["computer science", "data science", "software engineering",
                 "information systems", "statistics", "mathematics", "engineering"],
}


def _normalize(text: str) -> str:
    return text.lower().replace("-", " ").replace("_", " ")


def _extract_keywords(text: str, keyword_set: set) -> tuple[set, set]:
    """Return (matched, missing) from keyword_set vs text."""
    norm = _normalize(text)
    matched = {kw for kw in keyword_set if kw in norm}
    missing = keyword_set - matched
    return matched, missing


def _count_numbers(text: str) -> int:
    """Count quantified achievements: numbers with % or x or words like 'million', 'billion'."""
    patterns = [
        r'\d+%',           # 45%
        r'\d+x\b',         # 3x
        r'\$\d+',          # $5M
        r'\d+\s*(?:million|billion|thousand|k\b)',  # 50k, 2 million
        r'\d+\+',          # 20+
        r'\d{4,}',         # large numbers like 500000
    ]
    count = 0
    for p in patterns:
        count += len(re.findall(p, text, re.I))
    return count


def score_resume(jd: str, resume: str, role: str = "") -> ATSResult:
    """
    Score resume against job description.
    Returns ATSResult with score 0-100 and detailed breakdown.
    """
    jd_norm = _normalize(jd)
    resume_norm = _normalize(resume)
    breakdown = {}
    matched_all = []
    missing_all = []

    # ── 1. Hard skills (40 pts) ──────────────────────────────────────────────
    jd_hard = {kw for kw in HARD_SKILLS if kw in jd_norm}  # skills JD asks for
    if jd_hard:
        resume_hard = {kw for kw in jd_hard if kw in resume_norm}
        ratio = len(resume_hard) / len(jd_hard)
        hard_score = min(40, int(ratio * 40))
        missing_hard = jd_hard - resume_hard
    else:
        # No specific skills in JD — give partial credit
        hard_score = 25
        resume_hard = set()
        missing_hard = set()

    breakdown["hard_skills"] = {"score": hard_score, "max": 40,
                                 "matched": len(resume_hard), "required": len(jd_hard)}
    matched_all += list(resume_hard)
    missing_all += list(missing_hard)

    # ── 2. Soft skills / action verbs (15 pts) ───────────────────────────────
    soft_matched, _ = _extract_keywords(resume_norm, SOFT_SKILLS)
    verb_matched, _ = _extract_keywords(resume_norm, STRONG_VERBS)
    combined_soft = len(soft_matched) + len(verb_matched)
    soft_score = min(15, int(combined_soft * 1.5))
    breakdown["soft_skills"] = {"score": soft_score, "max": 15,
                                  "matched_soft": len(soft_matched),
                                  "matched_verbs": len(verb_matched)}

    # ── 3. Experience level match (15 pts) ───────────────────────────────────
    exp_score = 0
    for level, kws in EXPERIENCE_LEVEL_KEYWORDS.items():
        jd_has_level = any(kw in jd_norm for kw in kws)
        resume_has_level = any(kw in resume_norm for kw in kws)
        if jd_has_level and resume_has_level:
            exp_score = 15
            break
        elif jd_has_level:
            exp_score = 5  # level mismatch — partial
    if exp_score == 0:
        exp_score = 10  # level not specified in JD — neutral
    breakdown["experience_level"] = {"score": exp_score, "max": 15}

    # ── 4. Education (10 pts) ────────────────────────────────────────────────
    edu_score = 0
    jd_needs_degree = any(kw in jd_norm for kws in EDUCATION_KEYWORDS.values() for kw in kws)
    if jd_needs_degree:
        for level, kws in EDUCATION_KEYWORDS.items():
            if any(kw in jd_norm for kw in kws) and any(kw in resume_norm for kw in kws):
                edu_score = 10 if level in ("master", "phd") else 7
                break
        if edu_score == 0:
            edu_score = 4  # has degree, wrong level
    else:
        edu_score = 8  # education not required — neutral bonus
    breakdown["education"] = {"score": edu_score, "max": 10}

    # ── 5. Quantified achievements (10 pts) ──────────────────────────────────
    num_count = _count_numbers(resume)
    quant_score = min(10, num_count * 2)
    breakdown["quantified_achievements"] = {"score": quant_score, "max": 10,
                                              "count": num_count}

    # ── 6. Job-title keyword match (10 pts) ──────────────────────────────────
    title_score = 0
    if role:
        role_words = set(_normalize(role).split()) - {"at", "the", "a", "an", "and", "or", "for"}
        title_words_in_resume = sum(1 for w in role_words if w in resume_norm)
        title_score = min(10, int((title_words_in_resume / max(len(role_words), 1)) * 10))
    else:
        title_score = 5  # no role provided — neutral
    breakdown["title_match"] = {"score": title_score, "max": 10}

    # ── Final score ───────────────────────────────────────────────────────────
    total = (hard_score + soft_score + exp_score + edu_score
             + quant_score + title_score)
    total = min(100, total)

    if total >= 85:
        grade = "A"
    elif total >= 75:
        grade = "B"
    elif total >= 65:
        grade = "C"
    elif total >= 50:
        grade = "D"
    else:
        grade = "F"

    # Recommendation
    if total >= 80:
        rec = "Strong match — apply immediately."
    elif total >= 65:
        rec = "Good match — minor gaps. Worth applying."
    elif total >= 50:
        rec = "Moderate match — address gaps before applying."
    else:
        rec = "Weak match — significant skill gaps."

    return ATSResult(
        score=total,
        grade=grade,
        breakdown=breakdown,
        matched_keywords=sorted(matched_all)[:20],
        missing_keywords=sorted(missing_all)[:15],
        recommendation=rec,
    )


def score_all_pending_jobs(threshold: int = 80) -> list[dict]:
    """
    Score all pending H1B-confirmed jobs against the master resume.
    Returns sorted list of {job, ats_score, ats_result} for jobs >= threshold.
    """
    from database import get_pending_jobs, get_db, init_db
    from phase2_resume_tailor import load_master_resume, load_base_resume_for_role

    init_db()
    jobs = get_pending_jobs()
    resume_master = load_master_resume()
    results = []

    for job in jobs:
        jd = job.get("description") or f"Role: {job['role']} at {job['company']}"
        resume = load_base_resume_for_role(job["role"])
        result = score_resume(jd, resume, role=job["role"])

        # Also save score + grade to DB
        with get_db() as c:
            c.execute(
                "UPDATE jobs SET ats_score=?, ats_grade=? WHERE id=?",
                (result["score"], result["grade"], job["id"])
            )

        if result["score"] >= threshold:
            results.append({
                "job": dict(job),
                "ats_score": result["score"],
                "ats_grade": result["grade"],
                "missing_keywords": result["missing_keywords"][:5],
                "recommendation": result["recommendation"],
            })

    # Sort by score descending
    results.sort(key=lambda x: x["ats_score"], reverse=True)
    return results


if __name__ == "__main__":
    import sys
    from database import init_db
    from phase2_resume_tailor import load_master_resume, load_base_resume_for_role

    # Quick self-test
    jd_sample = """
    Senior Data Engineer — We need someone with 5+ years of Python, Apache Spark, 
    Airflow, AWS (S3, EMR, Glue), Kafka, dbt, SQL, and Snowflake experience. 
    You will architect scalable data pipelines, mentor junior engineers, and 
    deliver quantified business impact. Master's degree preferred.
    """
    resume_sample = load_master_resume()
    result = score_resume(jd_sample, resume_sample, role="Senior Data Engineer")
    print(f"Score: {result['score']}/100 ({result['grade']})")
    print(f"Recommendation: {result['recommendation']}")
    print(f"Matched: {result['matched_keywords'][:10]}")
    print(f"Missing: {result['missing_keywords'][:10]}")
    print(f"Breakdown: {result['breakdown']}")
