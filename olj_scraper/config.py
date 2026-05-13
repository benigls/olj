from urllib.parse import urljoin

BASE_URL = "https://www.onlinejobs.ph"
START_PATH = "/jobseekers/jobsearch"
START_URL = urljoin(BASE_URL, START_PATH)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; JobDataBot/1.0; +https://www.onlinejobs.ph)"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

DEFAULT_CRAWL_DELAY = 10

PIPELINE_NAME = "online_jobs_ph"
DATASET_NAME = "olj"
STATE_LAST_SEEN_JOB_ID = "last_seen_job_id"

ALERT_STATE_NAME = "job_alert_cursor"
ALERT_STATE_TABLE = "alert_state"

MATCH_TAGS = {
    "sql",
    "python",
    "data engineering",
    "big data",
}
MATCH_TITLE_KEYWORDS = {
    "data engineer",
    "analytics engineer",
    "data analyst",
    "data scientist",
}

TELEGRAM_API_BASE = "https://api.telegram.org"
TELEGRAM_MAX_MESSAGE_LENGTH = 4096
