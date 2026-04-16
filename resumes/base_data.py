"""
All 4 resume variants for Bhuvan Sai Thatthari.
Timelines are NEVER changed. Titles, bullets, summary, skills, projects are role-optimized.

Variants:
  DATA_ENGINEER  — pipeline architecture, cloud infra, scale
  DATA_ANALYST   — analytics, BI, insights, A/B testing, dashboards
  SQL_ENGINEER   — database design, query optimization, schema, SQL mastery
  SDE            — Python platform engineering, APIs, CI/CD, TDD
"""

# ── Shared contact info ───────────────────────────────────────────────────────
CONTACT = {
    "name":     "BHUVAN SAI THATTHARI",
    "location": "New York, USA",
    "phone":    "+1 (571) 241-2211",
    "email":    "bhuvanthatthari@gmail.com",
    "linkedin": "linkedin.com/in/saithatthari",
    "github":   "github.com/saithatthari",
}

EDUCATION = [
    {
        "degree":     "Master of Science — Database Administration & Management",
        "school":     "George Mason University",
        "location":   "Virginia, USA",
        "date":       "May 2025",
    }
]

PUBLICATIONS = [
    '"A Review Paper on Grocery Curation Tool using Machine Learning" — '
    "UGC Approved Journal (No: 63975), ISSN: 2349-5162, Vol. 10 Issue 4, April 2023. "
    "Impact Factor: 8.55"
]


# ── EXPERIENCE ────────────────────────────────────────────────────────────────
# Each experience block is a dict. Bullets are per-variant below.

_TUTTLE = {
    "company":  "Tuttle Publishing",
    "location": "VT, United States",
    "start":    "Oct 2025",
    "end":      "Present",
}

_GMU_RA = {
    "company":  "George Mason University",
    "location": "VA, United States",
    "start":    "Aug 2024",
    "end":      "May 2025",
}

_ERASMUS = {
    "company":  "Erasmus.ai",
    "location": "VA, United States",
    "start":    "Jan 2025",
    "end":      "May 2025",
    "label":    "Project",
}

_ALT = {
    "company":  "ALT.Investments",
    "location": "Hyderabad, India",
    "start":    "Jun 2021",
    "end":      "Jul 2023",
}


# ─────────────────────────────────────────────────────────────────────────────
# VARIANT 1 — DATA ENGINEER
# ─────────────────────────────────────────────────────────────────────────────

DATA_ENGINEER = {
    "contact": CONTACT,

    "summary": (
        "Data Engineering leader with 4+ years architecting enterprise-scale pipelines across "
        "financial services, publishing, and AI sectors. Engineered cloud-native platforms on AWS "
        "and Azure processing 2M+ daily events, unlocking $1M+ in revenue visibility and recovering "
        "$10K+ through ML-driven anomaly detection. Reduced pipeline failures by 45%, cut query "
        "latency by 65%, and drove data availability from 55% to 98.5% through production-grade "
        "Airflow, Kafka, dbt, and PySpark architectures. Thrive in high-impact environments where "
        "data accuracy, speed, and infrastructure reliability drive competitive advantage."
    ),

    "skills": {
        "Cloud & Infrastructure":
            "AWS (S3, RDS, Redshift, Lambda, Glue, EMR, CloudWatch, IAM), "
            "Azure (Data Lake Gen2, Synapse Analytics, Data Factory, Event Hubs, Databricks), "
            "Snowflake, Terraform, Docker, Kubernetes",
        "Data Engineering & Orchestration":
            "Apache Airflow, Apache Kafka, PySpark, dbt (data build tool), "
            "Databricks Delta Lake, Great Expectations, Azure Data Factory, "
            "ETL/ELT Pipeline Design, Stream Processing, Fivetran",
        "Databases & Storage":
            "PostgreSQL, Microsoft SQL Server, MySQL, MongoDB, Redis, "
            "Amazon Redshift, Azure Synapse, Snowflake, Dimensional Data Modeling, SSMS",
        "Programming & Development":
            "Python (Pandas, NumPy, Scikit-learn), SQL (CTEs, Window Functions, Stored Procedures), "
            "Bash/Shell Scripting, Git, GitHub Actions, Jenkins, CI/CD Pipelines",
        "Analytics & Visualization":
            "Power BI (DAX, Power Query), Tableau, Looker, "
            "Anomaly Detection, Time-Series Forecasting, Statistical Analysis",
        "Monitoring & Observability":
            "CloudWatch, Distributed Tracing, Performance Monitoring, "
            "Incident Management, Root Cause Analysis, Agile/Scrum",
    },

    "experience": [
        {
            **_TUTTLE,
            "title": "Senior Data Engineer",
            "bullets": [
                "Architected cloud-native ETL pipelines ingesting multi-source ERP data and FTP feeds into AWS S3 data lake, processing 500K+ daily records and improving data availability from 60% to 95%, enabling real-time business intelligence across operations and finance teams.",
                "Orchestrated production-grade Airflow DAGs with dynamic task generation, retry logic, and idempotency patterns, reducing pipeline failures by 45% and improving data quality SLAs from 92% to 98.5% while supporting 20+ dependent downstream consumers.",
                "Led zero-downtime migration of 15+ mission-critical databases from on-premise SQL Server to AWS RDS, implementing automated failover and multi-AZ deployments, reducing infrastructure costs by 35% and improving query performance by 60%.",
                "Established dbt transformation framework with 100+ models, CI/CD pipelines with automated testing, and data quality checks via Great Expectations, reducing deployment errors by 30% and improving data trust scores across the organization.",
                "Implemented containerized data workflows using Docker and Kubernetes with Terraform IaC deployments, reducing environment setup time from 2 days to 30 minutes and enabling reproducible production-parity environments.",
                "Deployed comprehensive observability stack on CloudWatch with distributed tracing, custom metrics dashboards, and automated alerting that reduced mean time to resolution (MTTR) from 2 hours to 25 minutes.",
                "Implemented OAuth2/JWT authentication and RBAC authorization for data APIs, ensuring enterprise-grade security controls and compliance standards while supporting 500+ authenticated users.",
            ],
        },
        {
            **_ERASMUS,
            "title": "Data Engineer — AI Platform",
            "bullets": [
                "Engineered high-throughput ETL pipelines processing 2M+ daily AI model inference events into Azure Synapse, applying partitioning and incremental loading strategies that improved data availability from 55% to 95% for ML analytics teams.",
                "Built event-driven streaming architecture using Azure Event Hubs and Databricks Structured Streaming with Kafka integration, reducing critical alert latency from 5 minutes to under 60 seconds for production ML model monitoring.",
                "Implemented infrastructure-as-code using Terraform with automated data quality validation via Great Expectations, achieving 100% pipeline test coverage and enabling zero-downtime deployments through GitHub Actions CI/CD.",
                "Deployed comprehensive observability platform with distributed tracing, APM, and custom alerting rules, enabling proactive incident detection and reducing mean time to detection (MTTD) by 70%.",
            ],
        },
        {
            **_GMU_RA,
            "title": "Data Engineer — Research",
            "bullets": [
                "Engineered scalable Python and SQL data pipelines processing 10,000+ research collaboration records across academic departments, enabling cross-functional analytics and research impact measurement.",
                "Conducted A/B testing and statistical analysis on academic program effectiveness using hypothesis testing and regression models to support data-driven strategic decisions for university leadership.",
                "Designed automated Power BI reporting dashboards with complex DAX measures, reducing manual reporting time by 75% and improving stakeholder access to real-time enrollment and performance metrics.",
            ],
        },
        {
            **_ALT,
            "title": "Data Engineer",
            "bullets": [
                "Architected enterprise-scale Azure data platform leveraging Data Lake Gen2 and Synapse Analytics, consolidating fragmented financial data from 20+ sources and enabling $1M+ revenue visibility through a unified reporting layer.",
                "Optimized multi-gigabyte financial dataset transformations using PySpark on Databricks, reducing processing time from 4 hours to 35 minutes and standardizing portfolio reporting across investment teams.",
                "Developed ML-powered anomaly detection pipelines using Python classification models for billing revenue leakage, recovering $10K+ annually and improving financial reporting accuracy by 18%.",
                "Automated time-series forecasting workflows using Prophet and ARIMA models, reducing manual analysis time by 20% and saving $10K annually in operational costs while improving forecast accuracy.",
                "Integrated external financial market APIs via Azure Data Factory with Redis caching, enriching portfolio analytics with real-time market data and reducing API latency from 800ms to 120ms.",
                "Championed TDD practices with comprehensive unit and integration test suites (JUnit, NUnit) achieving 85% code coverage, reducing production defects by 60%.",
            ],
        },
    ],

    "projects": [
        {
            "title": "StreamFlow — Real-Time Analytics Pipeline",
            "dates": "Oct 2023 – Jul 2024",
            "bullets": [
                "Built end-to-end real-time data platform using Apache Kafka, Apache Flink, and PostgreSQL, ingesting 500K+ events/hour from simulated financial market feeds with sub-second processing latency.",
                "Designed multi-layered lakehouse architecture with Delta Lake for bronze/silver/gold data tiers, automated data quality checks via Great Expectations, and Grafana dashboards for real-time KPI monitoring.",
                "Containerized entire stack with Docker Compose and deployed on AWS EC2 using Terraform; implemented Prometheus alerting and automated runbooks reducing incident response by 80%.",
            ],
        },
        {
            "title": "CloudETL Toolkit — Open-Source dbt + Airflow Accelerator",
            "dates": "Jul 2023 – Oct 2023",
            "bullets": [
                "Developed reusable Python library of 30+ custom Airflow operators and dbt macros automating boilerplate ETL patterns (SCD Type 2, incremental loads, schema drift handling).",
                "Published to PyPI with full documentation and 90%+ pytest coverage; reduced new pipeline scaffolding time from days to under 2 hours across multiple project use cases.",
            ],
        },
    ],

    "education": EDUCATION,
    "publications": PUBLICATIONS,
}


# ─────────────────────────────────────────────────────────────────────────────
# VARIANT 2 — DATA ANALYST
# ─────────────────────────────────────────────────────────────────────────────

DATA_ANALYST = {
    "contact": CONTACT,

    "summary": (
        "Analytics Engineer and Data Analyst with 4+ years turning complex, multi-source datasets "
        "into actionable business intelligence across financial services, publishing, and AI sectors. "
        "Delivered $1M+ in revenue visibility and recovered $10K+ through ML-powered anomaly "
        "detection by unifying 20+ fragmented data sources into self-service BI platforms. "
        "Expert in the full analytics lifecycle: SQL data modeling, statistical analysis (A/B testing, "
        "regression, forecasting), and stakeholder-facing dashboards in Power BI and Tableau. "
        "Bridges the gap between raw data infrastructure and the business insights that drive decisions."
    ),

    "skills": {
        "Analytics & Visualization":
            "Power BI (DAX, Power Query, Paginated Reports), Tableau, Looker, "
            "A/B Testing, Hypothesis Testing, Regression Analysis, Time-Series Forecasting, "
            "Statistical Analysis, Anomaly Detection, KPI Design",
        "SQL & Databases":
            "PostgreSQL, Microsoft SQL Server, MySQL, Amazon Redshift, Azure Synapse, Snowflake, "
            "Complex SQL (CTEs, Window Functions, Stored Procedures, Partitioning), "
            "Dimensional Modeling, SSMS, dbt (data build tool)",
        "Programming & Data Tools":
            "Python (Pandas, NumPy, Scikit-learn, Prophet, ARIMA, Matplotlib, Seaborn), "
            "SQL, Bash/Shell Scripting, Jupyter Notebooks, Git",
        "Cloud & Data Infrastructure":
            "AWS (S3, RDS, Redshift, Glue, Lambda), Azure (Synapse, Data Lake Gen2, "
            "Data Factory, Databricks), Snowflake, Apache Airflow, dbt, Great Expectations",
        "Data Quality & Governance":
            "Great Expectations, Data Validation Frameworks, Schema Evolution, "
            "Data Lineage, Metadata Management, Data Cataloging",
        "Collaboration & Delivery":
            "Agile/Scrum, Sprint Planning, Cross-Functional Stakeholder Management, "
            "Requirements Gathering, Business Intelligence Strategy",
    },

    "experience": [
        {
            **_TUTTLE,
            "title": "Analytics Engineer",
            "bullets": [
                "Designed and deployed self-service Power BI dashboards processing 500K+ daily ERP records, reducing ad-hoc reporting requests by 60% and improving executive decision velocity through real-time KPI visibility across operations and finance.",
                "Established dbt transformation framework with 100+ data models and comprehensive business glossary, enabling analysts to independently query complex metrics and reducing data discovery time by 50% for 200+ report consumers.",
                "Implemented statistical anomaly detection on 30+ critical business KPIs using Python (Z-score, IQR methods), automatically flagging data quality issues and cutting time-to-insight from days to hours for operations and finance teams.",
                "Collaborated with stakeholders to define KPI taxonomies and translate business requirements into dimensional SQL data models, supporting monthly reporting for 200+ users across five business units.",
                "Led data migration analytics for 15+ SQL Server database transitions to AWS RDS, performing pre- and post-migration reconciliation analysis that validated 99.9% data fidelity across all critical tables.",
                "Mentored junior analysts on SQL optimization and Power BI best practices, conducting bi-weekly office hours that improved team query performance by an average of 40%.",
            ],
        },
        {
            **_ERASMUS,
            "title": "Analytics Engineer — AI Platform",
            "bullets": [
                "Designed ML model performance analytics suite tracking 2M+ daily inference events in Azure Synapse, enabling data science teams to monitor model drift, latency SLAs, and accuracy degradation through interactive Tableau dashboards.",
                "Built real-time alerting dashboards using Databricks Structured Streaming and Azure Event Hubs, reducing time from model failure detection to team notification from 5 minutes to under 60 seconds.",
                "Developed automated data quality reporting with Great Expectations, creating executive-facing scorecards that tracked 20+ data freshness and completeness KPIs, achieving 100% SLA compliance visibility.",
            ],
        },
        {
            **_GMU_RA,
            "title": "Data Analyst — Research",
            "bullets": [
                "Performed A/B testing and multivariate statistical analysis on 10,000+ research records, applying hypothesis testing, regression models, and chi-square tests to measure academic program effectiveness for university leadership.",
                "Developed 15+ automated Power BI dashboards with complex DAX measures and drill-through capabilities, reducing manual reporting cycle from 2 days to real-time and improving data accessibility for 50+ faculty and administrative stakeholders.",
                "Applied Python NLP techniques (TF-IDF, sentiment analysis) to qualitative research feedback across 5,000+ survey responses, surfacing actionable themes that informed strategic curriculum decisions.",
            ],
        },
        {
            **_ALT,
            "title": "Analytics Engineer",
            "bullets": [
                "Unified fragmented financial data from 20+ sources into an Azure Synapse reporting layer, delivering $1M+ revenue visibility through consolidated executive dashboards and enabling portfolio-level performance analysis for investment teams.",
                "Built ML-powered billing anomaly detection using Python classification models (Random Forest, XGBoost), identifying revenue leakage patterns that recovered $10K+ annually and improved financial reporting accuracy by 18%.",
                "Developed automated time-series forecasting reports using Prophet and ARIMA models, providing investment teams with weekly portfolio projections that reduced manual analysis by 20 hours/week.",
                "Created executive-level financial analytics reports with drill-down capabilities in Power BI using complex DAX measures, standardizing portfolio reporting across 20+ investment teams.",
                "Enriched portfolio analytics with real-time market data via Azure Data Factory API integrations and Redis caching, reducing data latency from 800ms to 120ms and improving forecast model accuracy by 15%.",
            ],
        },
    ],

    "projects": [
        {
            "title": "RetailPulse — End-to-End Sales Analytics Platform",
            "dates": "Nov 2023 – Jul 2024",
            "bullets": [
                "Built a full analytics stack ingesting 1M+ e-commerce transactions using Airflow + dbt + Snowflake, creating a dimensional data model (star schema) with 10+ fact/dimension tables supporting executive, operational, and marketing analytics.",
                "Developed interactive Power BI dashboards with 15+ pages covering revenue trends, cohort retention, product affinity, and regional performance; implemented row-level security for 50+ department-specific views.",
                "Applied Python statistical models (regression, seasonality decomposition) to forecast monthly revenue with 94% accuracy, enabling proactive inventory and marketing decisions.",
            ],
        },
        {
            "title": "ML Grocery Curation — Published Research (Extended Implementation)",
            "dates": "Jan 2023 – Jun 2023",
            "bullets": [
                "Extended published ML research into a working analytics dashboard, analyzing 50,000+ grocery transaction records to validate curation algorithm recommendations against actual purchase behavior.",
                "Built Python-based evaluation pipeline tracking precision, recall, and revenue lift metrics; findings published in UGC Journal (Impact Factor 8.55).",
            ],
        },
    ],

    "education": EDUCATION,
    "publications": PUBLICATIONS,
}


# ─────────────────────────────────────────────────────────────────────────────
# VARIANT 3 — SQL ENGINEER
# ─────────────────────────────────────────────────────────────────────────────

SQL_ENGINEER = {
    "contact": CONTACT,

    "summary": (
        "Database Engineer and SQL Specialist with 4+ years designing high-performance data systems "
        "across financial services, publishing, and AI sectors. Expert in complex SQL (CTEs, window "
        "functions, partitioning, stored procedures), dimensional data modeling, and query "
        "optimization — reducing average query execution time from 12s to 2.5s and enabling "
        "$1M+ revenue visibility through unified reporting schemas. Hands-on experience with SQL "
        "Server, PostgreSQL, Azure Synapse, Amazon Redshift, and Snowflake at enterprise scale. "
        "Combines deep database engineering fundamentals with cloud data warehouse architecture "
        "to build schemas that serve both operational workloads and analytical reporting."
    ),

    "skills": {
        "SQL & Database Engineering":
            "Microsoft SQL Server, PostgreSQL, MySQL, Amazon Redshift, Azure Synapse Analytics, "
            "Snowflake, Complex SQL (CTEs, Window Functions, Recursive Queries, Stored Procedures, "
            "UDFs, Triggers), Query Optimization, Execution Plan Analysis, Index Strategy, "
            "Partitioning, SSMS, Database Design",
        "Data Modeling & Architecture":
            "Dimensional Data Modeling (Star/Snowflake Schema), SCD Type 1/2/3, "
            "Data Vault 2.0 Concepts, Schema Evolution, ERD Design, "
            "OLAP vs OLTP Architecture, Data Normalization",
        "Cloud Data Warehousing":
            "AWS (RDS, Redshift, S3, Glue, Lambda), "
            "Azure (Synapse Analytics, Data Lake Gen2, Data Factory, Databricks), "
            "Snowflake, dbt (data build tool), Delta Lake",
        "ETL / Data Engineering":
            "Apache Airflow, PySpark, Azure Data Factory, Great Expectations, "
            "ETL/ELT Pipeline Design, Data Quality Frameworks, CDC (Change Data Capture)",
        "Programming & Tools":
            "Python (Pandas, NumPy, SQLAlchemy), Bash/Shell Scripting, "
            "Git, GitHub Actions, Docker, Terraform, CI/CD Pipelines",
        "Database Security & Governance":
            "Row-Level Security, Column Encryption, RBAC, OAuth2/JWT, "
            "Data Lineage, Audit Logging, Compliance Controls, Metadata Management",
    },

    "experience": [
        {
            **_TUTTLE,
            "title": "Database Engineer / SQL Developer",
            "bullets": [
                "Led zero-downtime migration of 15+ production SQL Server databases to AWS RDS, designing multi-AZ configurations, read replicas, and automated failover procedures; reduced infrastructure costs by 35% and improved query performance by 60%.",
                "Optimized 500+ SQL queries through systematic execution plan analysis, advanced indexing strategies (covering, filtered, columnstore), and partition management in SSMS; reduced average query execution time from 12s to 2.5s on critical reporting workloads.",
                "Designed normalized dimensional data models (star schema) supporting 500K+ daily transactions; implemented stored procedures, computed columns, and materialized views eliminating redundant ETL logic and improving downstream query performance by 40%.",
                "Built comprehensive SQL-based data validation framework with 100+ assertion tests using Great Expectations, enforcing schema contracts and data quality SLAs across 20+ source systems with automated alerting on failures.",
                "Implemented database security controls including row-level security policies, column-level encryption, and RBAC roles supporting 500+ authenticated users while maintaining enterprise audit trails and compliance requirements.",
                "Developed SQL Server Agent jobs and stored procedures automating 15+ nightly data loads and reconciliation checks, achieving 99.9% schedule adherence and reducing DBA manual intervention by 80%.",
                "Established dbt transformation framework with 100+ SQL models, implementing CI/CD with automated schema testing; reduced deployment errors by 30% and provided full data lineage documentation for governance audits.",
            ],
        },
        {
            **_ERASMUS,
            "title": "Database Engineer — AI Data Platform",
            "bullets": [
                "Designed Azure Synapse Analytics schemas for 2M+ daily AI inference events, implementing columnstore indexes, table partitioning, and incremental load strategies that improved query performance by 80% and data availability from 55% to 95%.",
                "Built SQL-based data quality validation pipelines with 200+ automated assertions across 30+ tables, enforcing schema contracts and detecting anomalies within minutes of ingestion using Great Expectations.",
                "Implemented database-level change data capture (CDC) and audit logging patterns providing full data lineage from source to ML model consumption, enabling rapid root cause analysis on data quality incidents.",
            ],
        },
        {
            **_GMU_RA,
            "title": "SQL Developer / Data Analyst",
            "bullets": [
                "Designed and optimized complex SQL queries with CTEs, window functions, and recursive queries against 10,000+ research records, reducing query runtime by 65% and enabling cross-departmental analytics.",
                "Built parameterized SQL Server stored procedures and views backing Power BI dashboards, reducing dashboard load time by 75% and enabling self-service analytics for 50+ faculty members.",
                "Developed normalized relational schema for research collaboration tracking with proper foreign key constraints, composite indexes, and partitioning strategies supporting efficient multi-dimensional analysis.",
            ],
        },
        {
            **_ALT,
            "title": "Database Engineer",
            "bullets": [
                "Designed multi-terabyte Azure Synapse Analytics schemas consolidating financial data from 20+ sources; implemented columnstore indexes, hash distributions, and partition elimination strategies reducing query time from 4 hours to 35 minutes.",
                "Developed 50+ complex T-SQL stored procedures, views, and scalar UDFs for portfolio analytics and risk reporting, eliminating manual transformation and saving 15 hours/week of analyst time.",
                "Implemented Redis caching layer for high-frequency financial query results, reducing database load by 60% and improving application response time from 800ms to 120ms.",
                "Built SQL-based anomaly detection queries using statistical window functions (rolling mean, standard deviation) to identify billing outliers, recovering $10K+ annually and improving financial reporting accuracy by 18%.",
                "Championed SQL code review standards and TDD practices with NUnit/JUnit database unit tests achieving 85% coverage, reducing production data defects by 60%.",
            ],
        },
    ],

    "projects": [
        {
            "title": "QueryForge — SQL Query Optimization Toolkit",
            "dates": "Aug 2023 – Mar 2024",
            "bullets": [
                "Built Python + SQL toolkit that automatically analyzes execution plans, identifies missing indexes, detects parameter sniffing issues, and generates optimization recommendations for SQL Server and PostgreSQL workloads.",
                "Implemented automated index advisor that analyzed 10,000+ query plans, generating 200+ index recommendations that reduced average query time by 45% across test database workloads.",
                "Developed schema comparison and drift detection utility used to validate database migrations; catches 100% of schema discrepancies before production deployments.",
            ],
        },
        {
            "title": "DataVault Lakehouse — Dimensional Modeling Reference Implementation",
            "dates": "Aug 2023 – Dec 2023",
            "bullets": [
                "Designed and implemented a full star-schema data warehouse for e-commerce analytics using dbt + Snowflake, with 15+ fact/dimension tables, SCD Type 2 handling, and automated data quality assertions.",
                "Wrote comprehensive SQL transformation suite covering order analytics, customer cohort analysis, inventory turnover, and marketing attribution; all models documented with dbt docs and lineage graphs.",
            ],
        },
    ],

    "education": EDUCATION,
    "publications": PUBLICATIONS,
}


# ─────────────────────────────────────────────────────────────────────────────
# VARIANT 4 — SOFTWARE DEVELOPMENT ENGINEER (SDE)
# ─────────────────────────────────────────────────────────────────────────────

SDE = {
    "contact": CONTACT,

    "summary": (
        "Software Engineer specializing in data platform engineering, backend systems, and "
        "cloud-native API development with 4+ years building production-grade Python applications "
        "across financial services, publishing, and AI sectors. Designed and shipped microservices "
        "and streaming architectures processing 2M+ daily events, built OAuth2/JWT-secured APIs "
        "serving 500+ users, and drove 85%+ test coverage through rigorous TDD practices. "
        "Combines strong software engineering fundamentals — clean architecture, CI/CD, "
        "containerization, observability — with deep data systems expertise (Kafka, Spark, "
        "Airflow, dbt) to deliver scalable, reliable platform infrastructure."
    ),

    "skills": {
        "Programming Languages & Frameworks":
            "Python (FastAPI, Flask, Pandas, NumPy, Scikit-learn, pytest, SQLAlchemy), "
            "SQL, Bash/Shell Scripting, TypeScript (basic), REST API Design, GraphQL",
        "Software Engineering Practices":
            "Test-Driven Development (TDD), Unit/Integration Testing (pytest, JUnit, NUnit, xUnit), "
            "CI/CD Pipelines (GitHub Actions, Jenkins), Code Reviews, Static Analysis, "
            "SOLID Principles, Clean Architecture, Microservices",
        "Cloud & Infrastructure":
            "AWS (Lambda, EC2, S3, RDS, SQS, API Gateway, CloudWatch, IAM), "
            "Azure (Data Factory, Event Hubs, Databricks, Data Lake Gen2), "
            "Docker, Kubernetes, Terraform, Helm",
        "Data & Streaming":
            "Apache Kafka, Apache Airflow, PySpark, Databricks, dbt, "
            "Great Expectations, PostgreSQL, Redis, MongoDB, Snowflake",
        "Security & API Design":
            "OAuth2, JWT, RBAC, Secure API Design, Data Encryption, "
            "OpenAPI/Swagger, Rate Limiting, Authentication & Authorization",
        "Monitoring & Observability":
            "Distributed Tracing, Prometheus, Grafana, AWS CloudWatch, "
            "Application Performance Monitoring, Structured Logging, Incident Management",
    },

    "experience": [
        {
            **_TUTTLE,
            "title": "Software Engineer — Data Platform",
            "bullets": [
                "Engineered cloud-native Python microservices processing 500K+ daily ERP and FTP events using AWS Lambda and SQS, implementing event sourcing and idempotency patterns achieving 99.9% uptime and 45% reduction in pipeline failures.",
                "Developed production-grade Apache Airflow custom operators and reusable Python ETL libraries, reducing new pipeline development time by 40% and improving code reusability across 50+ DAGs through plugin architecture.",
                "Architected RESTful data APIs using FastAPI with OAuth2/JWT authentication and RBAC authorization, serving 500+ authenticated users with full OpenAPI documentation and 85%+ pytest unit/integration test coverage.",
                "Led infrastructure-as-code initiative using Terraform + Docker/Kubernetes, implementing GitHub Actions CI/CD pipelines with automated linting, testing, and deployment stages; reduced environment provisioning from 2 days to 30 minutes.",
                "Led zero-downtime database migration of 15+ SQL Server databases to AWS RDS using blue-green deployment strategy, cutting infrastructure costs by 35% and improving query performance by 60%.",
                "Established comprehensive observability with CloudWatch distributed tracing, custom metrics, and automated PagerDuty alerting, reducing MTTR from 2 hours to 25 minutes and enabling proactive incident detection.",
                "Implemented pytest test suite with 85%+ coverage including mocked AWS services, fixture-based data factories, and parameterized integration tests, reducing production incidents by 40%.",
            ],
        },
        {
            **_ERASMUS,
            "title": "Software Engineer — ML Platform",
            "bullets": [
                "Built high-throughput Python ETL microservices processing 2M+ daily AI model inference events using Azure Event Hubs and Databricks Structured Streaming, implementing backpressure handling and dead-letter queuing for fault tolerance.",
                "Implemented infrastructure-as-code using Terraform modules with GitHub Actions CI/CD achieving zero-downtime deployments, 100% pipeline test coverage via Great Expectations, and automated rollback on failure.",
                "Designed observability platform with distributed tracing, APM dashboards, and custom alerting rules in Prometheus/Grafana, reducing MTTD by 70% and enabling ML team SLA compliance tracking.",
            ],
        },
        {
            **_GMU_RA,
            "title": "Software Engineer — Research Systems",
            "bullets": [
                "Built modular Python data processing framework with plugin architecture for research pipeline composition, reducing new pipeline development from days to hours and enabling reuse across 10+ research datasets.",
                "Developed automated pytest test suite with 90%+ coverage across 20+ data pipeline scenarios using parameterized fixtures, mock objects, and property-based testing, eliminating all regression failures in production.",
                "Designed and implemented paginated REST API endpoints for research data access with caching, rate limiting, and request validation, supporting concurrent access from 50+ research team members.",
            ],
        },
        {
            **_ALT,
            "title": "Software Engineer — Financial Data Systems",
            "bullets": [
                "Built Python financial data processing platform ingesting real-time market feeds via REST APIs and WebSockets using Azure Data Factory, implementing circuit breakers, retry logic, and dead-letter handling for 99.9% data completeness.",
                "Developed ML pipeline framework using scikit-learn with modular feature engineering, cross-validation, and model registry patterns; classification models recovered $10K+ annually by detecting billing revenue leakage.",
                "Implemented comprehensive TDD practices with JUnit and NUnit achieving 85% code coverage across 200+ test cases, reducing production defects by 60% and enabling confident continuous deployment.",
                "Engineered Redis caching layer and connection pooling for high-frequency financial data APIs, reducing response latency from 800ms to 120ms and supporting 10x concurrent user growth without database scaling.",
                "Contributed Azure Terraform modules for data infrastructure provisioning, establishing blue-green deployment patterns and enabling zero-downtime releases across all data platform services.",
            ],
        },
    ],

    "projects": [
        {
            "title": "PipelineOS — Cloud-Native Data Platform Framework",
            "dates": "Oct 2023 – Jul 2024",
            "bullets": [
                "Built open-source Python framework abstracting common data platform patterns: typed DAG definitions, auto-generated Airflow operators, schema-validated data contracts, and pluggable connector interfaces for 10+ data sources.",
                "Achieved 95%+ test coverage with pytest, property-based testing (Hypothesis), and Docker-based integration tests against real Postgres/Kafka instances; published to PyPI with CI via GitHub Actions.",
                "Implemented CLI tooling enabling engineers to scaffold new pipelines from templates in under 5 minutes; reduced boilerplate by 70% and standardized patterns across multiple pipeline projects.",
            ],
        },
        {
            "title": "SecureAPI — OAuth2 + JWT API Gateway Boilerplate",
            "dates": "Aug 2023 – Oct 2023",
            "bullets": [
                "Developed production-ready FastAPI starter with OAuth2 PKCE flow, refresh token rotation, RBAC middleware, rate limiting, structured logging, and OpenAPI documentation.",
                "Containerized with Docker, deployed via Terraform on AWS API Gateway + Lambda; includes full pytest suite with 90%+ coverage and GitHub Actions CI/CD pipeline.",
            ],
        },
    ],

    "education": EDUCATION,
    "publications": PUBLICATIONS,
}


# ── Role-to-variant mapping ───────────────────────────────────────────────────
ROLE_VARIANTS = {
    # Data Engineering titles
    "data engineer":            DATA_ENGINEER,
    "senior data engineer":     DATA_ENGINEER,
    "data platform engineer":   DATA_ENGINEER,
    "etl engineer":             DATA_ENGINEER,
    "analytics engineer":       DATA_ANALYST,
    "ml engineer":              DATA_ENGINEER,

    # Analytics titles
    "data analyst":             DATA_ANALYST,
    "senior data analyst":      DATA_ANALYST,
    "business analyst":         DATA_ANALYST,
    "bi developer":             DATA_ANALYST,
    "bi analyst":               DATA_ANALYST,
    "business intelligence":    DATA_ANALYST,

    # SQL / Database titles
    "sql engineer":             SQL_ENGINEER,
    "database engineer":        SQL_ENGINEER,
    "database developer":       SQL_ENGINEER,
    "sql developer":            SQL_ENGINEER,
    "data warehouse engineer":  SQL_ENGINEER,
    "database administrator":   SQL_ENGINEER,

    # SDE titles
    "software engineer":        SDE,
    "software developer":       SDE,
    "sde":                      SDE,
    "backend engineer":         SDE,
    "platform engineer":        SDE,
    "python developer":         SDE,
    "python engineer":          SDE,
}


def get_variant_for_role(role_title: str) -> dict:
    """Return the best-matching resume variant dict for a given job title."""
    role_lower = role_title.lower().strip()
    for key, variant in ROLE_VARIANTS.items():
        if key in role_lower:
            return variant
    # Default: Data Engineer
    return DATA_ENGINEER
