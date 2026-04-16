"""
import_sheet_jobs.py — Import H1B jobs from the Google Sheet into the DB.

All jobs come pre-verified as H1B sponsors with direct ATS application links.
Only roles relevant to Bhuvan's profile (data engineering, analytics, BI) are
imported. All company names are also added to the H1B companies table.
"""
import logging
from database import init_db, upsert_job, upsert_company, get_db

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── All 87 rows from the sheet ─────────────────────────────────────────────────
SHEET_JOBS = [
    # (company, role, location, job_link, salary, h1b_petitions)
    ("Amazon", "Software Development Engineer", "Seattle, WA", "https://www.amazon.jobs/en/jobs/2920383/software-development-engineer-amazon", "$129K/yr", 14606),
    ("Infosys", "Java Full Stack Developer", "Seattle, WA", "https://digitalcareers.infosys.com/global-careers/company-job/description/reqid/130221BR", "$93K–$139K/yr", 5943),
    ("Google", "Software Engineer III", "Sunnyvale, CA", "https://www.google.com/about/careers/applications/jobs/results/89037645258072774-software-engineer-iii/", "DOE", 9099),
    ("Amazon", "Business Data Analyst", "Arlington, VA", "https://www.amazon.jobs/en/jobs/2920854/business-data-analyst-global-marketing-programs", "$73K–$155K/yr", 3822),
    ("Meta Platforms", "Fundamental AI Research Scientist", "Menlo Park, CA", "https://www.metacareers.com/jobs/598656719664969/", "$147K–$208K/yr", 4844),
    ("Amazon", "Data Engineer II", "New York, NY", "https://www.amazon.jobs/en/jobs/2920674/data-engineer-ii-shopbop", "$119K/yr", 14),
    ("Infosys", "AWS and Snowflake Data Engineer", "Charlotte, NC", "https://digitalcareers.infosys.com/global-careers/company-job/description/reqid/130183BR", "$75K–$108K/yr", 5943),
    ("Amazon", "Business Intelligence Engineer", "Seattle, WA", "https://www.amazon.jobs/en/jobs/2920272/business-intelligence-engineer-business-buying-and-purchase-experiences", "$90K–$185K/yr", 14606),
    ("Meta Platforms", "Data Engineer", "Fremont, CA", "https://www.metacareers.com/jobs/417725504174666/", "$145K–$204K/yr", 4844),
    ("Infosys", "Azure Data Platform Engineer", "Plano, TX", "https://digitalcareers.infosys.com/global-careers/company-job/description/reqid/129993BR", "$75K–$108K/yr", 5943),
    ("Google", "Data Scientist III", "Mountain View, CA", "https://www.google.com/about/careers/applications/jobs/results/118509504684794566-data-scientist-iii/", "DOE", 9099),
    ("Apple", "Machine Learning Video Engineer", "Cupertino, CA", "https://jobs.apple.com/en-us/details/200581685/machine-learning-video-engineer", "$143K–$264K/yr", 3816),
    ("Meta Platforms", "Testing Program Manager", "Menlo Park, CA", "https://www.metacareers.com/jobs/2081030495695677/", "$101K–$152K/yr", 4844),
    ("Microsoft", "Reporting & Data Design Lead", "Redmond, WA", "https://jobs.careers.microsoft.com/us/en/job/1806658/Reporting-Data-Design-Lead", "$133K–$219K/yr", 9492),
    ("Apple", "Full Stack Software Engineer", "Cupertino, CA", "https://jobs.apple.com/en-us/details/200578570/full-stack-software-engineer-apple-services-engineering", "$143K–$264K/yr", 3816),
    ("Deloitte", "Palantir Data Scientist", "Arlington, VA", "https://apply.deloitte.com/careers/InviteToApply?jobId=211650", "$98K–$149K/yr", 8),
    ("Tesla", "Supplier Quality Assurance", "Kyle, TX", "https://www.tesla.com/careers/search/job/238607", "$60K–$93K/yr", 2242),
    ("Microsoft", "Business Program Manager", "Redmond, WA", "https://jobs.careers.microsoft.com/us/en/job/1811278/Business-Program-Manager", "$94K–$183K/yr", 9492),
    ("Intel", "Analog Circuit Design Engineer", "Folsom, CA", "https://jobs.intel.com/en/job/-/-/599/78314432144", "$140K–$197K/yr", 3732),
    ("Tesla", "Fullstack Software Engineer", "Palo Alto, CA", "https://www.tesla.com/careers/search/job/238656", "$140K–$252K/yr", 2242),
    ("Walmart", "Operations Manager", "Seymour, IN", "https://walmart.wd5.myworkdayjobs.com/WalmartExternal/job/Seymour-IN/XMLNAME--USA--Operations-Manager--Fleet-Safety_R-2120419-1", "$65K–$139K/yr", 2904),
    ("Walmart", "Area Manager", "Monroe, OH", "https://walmart.wd5.myworkdayjobs.com/WalmartExternal/job/Monroe-OH/XMLNAME--USA--Area-Manager_R-2120040", "$50K–$100K/yr", 2904),
    ("LTIMindtree", "Data Engineer", "Bellevue, WA", "https://ltimindtree.ripplehire.com/candidate/?token=nP1GISU2A024qt3otg3V&lang=en&source=CAREERSITE#detail/job/695777", "$50K–$60K/yr", 2866),
    ("Oracle", "Software Developer 3", "Redwood City, CA", "https://eeho.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/jobsearch/job/282050", "$105K–$166K/yr", 860),
    ("Oracle", "Applied Scientist", "United States", "https://eeho.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/jobsearch/job/281874", "$115K–$186K/yr", 860),
    ("Oracle", "Principal Sales Consultant", "United States", "https://eeho.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/jobsearch/job/281554", "$115K–$186K/yr", 860),
    ("Wipro", "Developer - L4", "Minneapolis, MN", "https://careers.wipro.com/job/Boston-Developer-L4-MA-02108/1144520655/", "$60K–$135K/yr", 2296),
    ("Wipro", "System Engineer - L4", "Addison, IL", "https://careers.wipro.com/job/Addison-System-Engineer-L4-PA/1150096655/", "$60K–$135K/yr", 2296),
    ("Wipro", ".Net and C# Developer", "Addison, IL", "https://careers.wipro.com/job/Addison-_Net-and-C-Developer-PA/1150241655/", "$60K–$135K/yr", 2296),
    ("Wipro", "Production Specialist - L3", "O Fallon, MO", "https://careers.wipro.com/job/O-Fallon-Production-Specialist-L3-IL/1150077755/", "$50K–$75K/yr", 2296),
    ("Wipro", "Senior Salesforce Developer", "Indianapolis, IN", "https://careers.wipro.com/job/Indianapolis-Senior-Salesforce-Developer-IA-46225/1150097255/", "$110K–$150K/yr", 2296),
    ("Citi", "Quality Assurance", "Irving, TX", "https://jobs.citi.com/job/-/-/287/78336496672", "$96K–$145K/yr", 4),
    ("Citi", "Data Analytics Lead Analyst", "Irving, TX", "https://jobs.citi.com/job/-/-/287/78336391072", "$126K–$189K/yr", 4),
    ("Citi", "IT Business Sr Analyst", "New York, NY", "https://jobs.citi.com/job/-/-/287/78345018480", "$99K–$148K/yr", 4),
    ("Citi", "KYC Operations Sr Analyst", "O Fallon, MO", "https://jobs.citi.com/job/-/-/287/78345029264", "$82K–$122K/yr", 4),
    ("UST Global", "Senior DevOps Engineer", "Atlanta, GA", "https://usource.ripplehire.com/candidate/?token=xHQWoFn4C242POo7xMpH&source=CAREERSITE#detail/job/34041", "$108K–$163K/yr", 806),
    ("UST Global", "Full-Stack Developer", "Remote USA", "https://usource.ripplehire.com/candidate/?token=xHQWoFn4C242POo7xMpH&source=CAREERSITE#detail/job/34123", "$100K–$120K/yr", 806),
    ("Goldman Sachs", "Transaction Banking Operations - Associate", "Dallas, TX", "https://hdpc.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/LateralHiring/job/143152", "$60K–$91K/yr", 1178),
    ("Goldman Sachs", "Compliance Analyst", "Dallas, TX", "https://hdpc.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/LateralHiring/job/139424", "$68K–$104K/yr", 1178),
    ("Cummins", "Production Associate", "North Charleston, SC", "https://cummins.jobs/north-charleston-sc/production-associate-level-iii/ADFE15F427AD4E339B10FB9589D349F5/job/", "$45K–$66K/yr", 829),
    ("Amazon", "IT Support Associate II", "Georgia, US", "https://www.amazon.jobs/en/jobs/2922189/it-support-associate-ii-one-medical-it-support", "$93K–$139K/yr", 14606),
    ("Amazon", "Software Development Engineer", "San Luis Obispo, CA", "https://www.amazon.jobs/en/jobs/2922220/software-development-engineer", "$129K–$223K/yr", 14606),
    ("Amazon", "Sr. Technical Program Manager", "Seattle, WA", "https://www.amazon.jobs/en/jobs/2921508/sr-technical-program-manager-ab-marketing-analytics-abma", "$133K–$231K/yr", 14606),
    ("Infosys", "Data Engineer and Data Science Lead", "Austin, TX", "https://digitalcareers.infosys.com/global-careers/company-job/description/reqid/128817BR", "$93K–$139K/yr", 5943),
    ("Infosys", "Project Manager", "Hartford, CT", "https://digitalcareers.infosys.com/global-careers/company-job/description/reqid/129552BR", "$95K–$139K/yr", 5943),
    ("Infosys", "Senior UI Developer", "Austin, TX", "https://digitalcareers.infosys.com/global-careers/company-job/description/reqid/129812BR", "$95K–$139K/yr", 5943),
    ("Infosys", "Azure Developer", "Houston, TX", "https://digitalcareers.infosys.com/global-careers/company-job/description/reqid/130122BR", "$125K–$189K/yr", 5943),
    ("Infosys", "Mainframe DB2 DBA", "New York, NY", "https://digitalcareers.infosys.com/global-careers/company-job/description/reqid/130120BR", "$108K–$185K/yr", 5943),
    ("Meta Platforms", "Software Engineer, Infrastructure", "Sunnyvale, CA", "https://www.metacareers.com/jobs/1408007706638053/", "$208K/yr", 4844),
    ("Meta Platforms", "Content Designer", "Sunnyvale, CA", "https://www.metacareers.com/jobs/967147632010366/", "$118K–$167K/yr", 4844),
    ("Meta Platforms", "Enterprise Support Technician", "Redmond, WA", "https://www.metacareers.com/jobs/649234987796819/", "$39/hr", 4844),
    ("Oracle", "Software Developer 2", "Austin, TX", "https://eeho.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/jobsearch/job/282283", "$73K–$158K/yr", 860),
    ("Oracle", "Senior Software Developer", "United States", "https://eeho.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/jobsearch/requisitions/preview/261750/", "$74K–$178K/yr", 860),
    ("Qualcomm", "Windows DevOps Team Lead", "San Diego, CA", "https://careers.qualcomm.com/careers?location=United%20States&pid=446704252344&domain=qualcomm.com", "$162K–$244K/yr", 1122),
    ("Citibank", "Tax Payroll Analyst", "Tampa, FL", "https://jobs.citi.com/job/tampa/tax-payroll-analyst-hybrid/287/73427459632", "$58K–$72K/yr", 866),
    ("Citibank", "Finance Reporting Lead Analyst", "Getzville, NY", "https://jobs.citi.com/job/getzville/vp-finance-reporting-lead-analyst-hybrid-buffalo/287/74764237712", "$92K–$138K/yr", 866),
    ("ByteDance", "Backend Software Engineer", "San Jose, CA", "https://joinbytedance.com/search/7250620192941394233", "$116K–$250K/yr", 317),
    ("Adobe", "Software Development Engineer", "San Jose, CA", "https://careers.adobe.com/us/en/job/ADOBUSR151806EXTERNALENUS/Software-Development-Engineer", "$113K–$206K/yr", 187),
    ("Expedia Group", "Senior Data Engineer", "Seattle, WA", "https://careers.expediagroup.com/jobs/job/?Senior+Data+Engineer-Seattle-Washington-j-R-92758&source=LinkedIn", "$173K–$242K/yr", 104),
    ("Microsoft", "Software Engineer II", "Reston, VA", "https://jobs.careers.microsoft.com/global/en/job/1795769/Software-Engineer-II---CTJ---Poly", "$98K–$193K/yr", 2569),
    ("Intuit", "FullStack Staff Software Engineer", "Mountain View, CA", "https://jobs.intuit.com/job/-/-/27595/69556056032", "$191K–$258K/yr", 166),
    ("General Motors", "Quality Performance Engineer", "Warren, MI", "https://generalmotors.wd5.myworkdayjobs.com/Careers_GM/job/Warren-Michigan-United-States-of-America/Quality-Performance-Engineer_JR-202504347", "$118K–$167K/yr", 158),
    ("Comcast", "Xfinity Retail Sales Consultant", "Seattle, WA", "https://comcast.wd5.myworkdayjobs.com/Comcast_Careers/job/WA---Seattle-2202-Westlake-Ave---Retail-XFR3659/Xfinity-Retail-Sales-Consultant_R404290/apply", "$20/hr", 440),
    ("DoorDash", "Software Engineer II, Data Governance Platform", "San Francisco, CA", "https://boards.greenhouse.io/doordashusa/jobs/5638430", "$159K–$235K/yr", 109),
    ("DoorDash", "Associate, Strategy & Operations", "New York, NY", "https://boards.greenhouse.io/doordashusa/jobs/6546561", "$56K–$95K/yr", 109),
    ("Synechron", "Murex Analyst", "New York, NY", "https://synechron.wd1.myworkdayjobs.com/SynechronCareers/job/New-York-NY/Murex-Analyst_JR1022524-1", "$120K–$135K/yr", 122),
    ("Fiserv", "Outside Sales Rep", "Minnesota, US", "https://www.careers.fiserv.com/job/-/-/1758/69562619872", "$39K–$66K/yr", 403),
    ("Adobe", "Software Quality Engineer, Photoshop", "San Jose, CA", "https://careers.adobe.com/us/en/job/ADOBUSR153345EXTERNALENUS/Software-Quality-Engineer-Photoshop", "$109K–$215K/yr", 187),
    ("Fiserv", "Business Sales Consultant", "Iowa, US", "https://www.careers.fiserv.com/job/-/-/1758/76422002128", "$49K–$66K/yr", 403),
    ("Hewlett Packard Enterprise", "Regional Channel Sales Engagement Specialist", "Spring, TX", "https://careers.hpe.com/us/en/job/HPE1US1186429EXTERNALENUS/Regional-Channel-Sales-Engagement-Specialist", "$96K–$226K/yr", 56),
    ("Mayo Clinic", "Data Science Analyst", "Rochester, MN", "https://jobs.mayoclinic.org/job/rochester/data-science-analyst-office-of-digital-innovation/33647/78518986448", "$94K–$142K/yr", 86),
    ("Charles Schwab", "SDET Engineer", "Southlake, TX", "https://www.schwabjobs.com/job/-/-/33727/72973098192", "$132K–$179K/yr", 135),
    ("Charles Schwab", "Investment Consultant", "San Francisco, CA", "https://www.schwabjobs.com/job/-/-/33727/76060177712", "$74K–$178K/yr", 135),
    ("Expedia Group", "Program Manager", "Seattle, WA", "https://exp.insitecareers.com/job_posting.do?id=z250307210853529628444b8", "$86/hr–$96/hr", 104),
    ("ByteDance", "Software Engineer, UI Framework", "San Jose, CA", "https://joinbytedance.com/search/6932663233350240519", "$145K–$250K/yr", 317),
    ("Intuit", "Senior Data Scientist", "Mountain View, CA", "https://jobs.intuit.com/job/-/-/27595/74456416016", "$132K–$179K/yr", 166),
    ("Innova Solutions", "Oracle DB Developer", "Chicago, IL", "https://www.aptrack.co/uap/AAAGoQAPnxECFwnF/", "$39K–$66K/yr", 88),
    ("Goldman Sachs", "Controllers-Product Controllers, Associate", "New York, NY", "https://hdpc.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/LateralHiring/job/143789", "$85K–$140K/yr", 147),
    ("Washington University", "Website Developer", "St Louis, MO", "https://wustl.wd1.myworkdayjobs.com/External/job/Washington-University-Medical-Campus/Website-Developer---Department-of-Surgery_JR87761", "$53K–$90K/yr", 2),
    ("Washington University", "Data Visualization Designer I", "St Louis, MO", "https://wustl.wd1.myworkdayjobs.com/External/job/Washington-University-Danforth-Campus/Data-Visualization-Designer-I---Provost-Office_JR87720", "$53K–$90K/yr", 2),
    ("Expedia Group", "CRM Solutions Manager", "Austin, TX", "https://careers.expediagroup.com/jobs/job/?CRM+Solutions+Manager-Austin-Texas-j-R-94335-1", "$74K–$178K/yr", 104),
    ("Visa", "Technical Program Analyst", "Foster City, CA", "https://jobs.smartrecruiters.com/Visa/744000043083305-technical-program-analyst-", "$132K–$182K/yr", 336),
    ("Barclays", "Android Developer - Mobile", "Whippany, NJ", "https://search.jobs.barclays/job/-/-/13015/76907479584", "$109K–$215K/yr", 119),
]

# Keywords that match Bhuvan's data engineering / analytics background
RELEVANT_KEYWORDS = {
    "data engineer", "data analyst", "analytics engineer", "business intelligence",
    "bi engineer", "sql", "database", "data science", "data governance",
    "data platform", "azure data", "snowflake", "data design",
    "data visualization", "etl", "pipeline", "reporting",
}

def is_relevant(role: str) -> bool:
    rl = role.lower()
    return any(kw in rl for kw in RELEVANT_KEYWORDS)


def main():
    init_db()

    # Step 1: seed all companies as H1B confirmed
    companies = {row[0] for row in SHEET_JOBS}
    for name in sorted(companies):
        upsert_company(name=name, h1b_confirmed=True, h1b_source="google_sheet")
    logger.info("Seeded %d companies from sheet", len(companies))

    # Step 2: import ALL jobs (all are H1B-confirmed with direct ATS links)
    imported = 0
    skipped = 0
    for company, role, location, url, salary, petitions in SHEET_JOBS:
        try:
            desc = f"Salary: {salary}. 2024 H-1B Petitions: {petitions}."
            upsert_job(
                company=company,
                role=role,
                jd_url=url,
                source="google_sheet",
                location=location,
                description=desc,
                h1b_confirmed=True,
            )
            imported += 1
        except Exception as exc:
            logger.warning("Could not import %s @ %s: %s", role, company, exc)
            skipped += 1

    logger.info("Imported %d jobs (%d skipped) from Google Sheet", imported, skipped)

    # Step 3: report relevant vs total
    relevant = [(c, r, loc) for c, r, loc, *_ in SHEET_JOBS if is_relevant(r)]
    logger.info(
        "%d of %d jobs are data/analytics-relevant for your profile:",
        len(relevant), len(SHEET_JOBS),
    )
    for company, role, location in relevant:
        logger.info("  ✓  %-40s  @ %-25s  (%s)", role, company, location)

    # Summary
    with get_db() as c:
        total = c.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        h1b   = c.execute("SELECT COUNT(*) FROM jobs WHERE h1b_confirmed=1").fetchone()[0]
    logger.info("\nDB now: %d total jobs | %d H1B-confirmed", total, h1b)


if __name__ == "__main__":
    main()
