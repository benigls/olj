from __future__ import annotations

import requests
from bs4 import BeautifulSoup

from .config import BASE_URL, START_URL
from .parsing import extract_job_id, fetch_page, get_next_page_url, parse_jobs, strip_or_none

MIN_SAMPLE_JOBS = 3

FIXTURE_HTML = """
<a href="/jobseekers/job/calling-all-go-high-level-1600429">
  <h4 class="fs-16 fw-700" data-original-title="" title="">
    Calling All Go High Level Website &amp; Funnel Designers
    <span class="badge full-time mt-md-0">Full Time</span>
  </h4>
  <p data-temp=" 2026-05-07 "></p>
  <dd class="col"> $10/hr </dd>
  <div class="job-tag">
    <a class="badge"> Remote </a>
    <a class="badge">  </a>
  </div>
</a>
"""


def fail(message: str) -> None:
    print(f"[FAIL] {message}")
    raise SystemExit(1)


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def validate_helpers() -> None:
    assert_true(strip_or_none("  hello  ") == "hello", "strip_or_none failed")
    assert_true(strip_or_none("   ") is None, "strip_or_none should return None for blank strings")
    assert_true(
        extract_job_id("/jobseekers/job/Sales-Assistant-1600429") == "1600429",
        "extract_job_id failed on hyphenated job path",
    )
    assert_true(
        extract_job_id("/jobseekers/job/1600429") == "1600429",
        "extract_job_id failed on numeric job path",
    )


def validate_fixture() -> None:
    soup = BeautifulSoup(FIXTURE_HTML, "lxml")
    jobs = parse_jobs(soup)
    assert_true(len(jobs) == 1, "Fixture should parse exactly one job")

    job = jobs[0]
    assert_true(job["job_id"] == 1600429, "Fixture job_id mismatch")
    assert_true(
        job["job_url"]
        == "https://www.onlinejobs.ph/jobseekers/job/calling-all-go-high-level-1600429",
        "Fixture job_url mismatch",
    )
    assert_true(
        job["title"] == "Calling All Go High Level Website & Funnel Designers",
        "Fixture title mismatch",
    )
    assert_true(job["employment_type"] == "Full Time", "Fixture employment_type mismatch")
    assert_true(job["posted_at"] == "2026-05-07", "Fixture posted_at mismatch")
    assert_true(job["rate"] == "$10/hr", "Fixture rate mismatch")
    assert_true(job["tags"] == "Remote", "Fixture tags mismatch")


def validate_live_page(soup: BeautifulSoup) -> None:
    jobs = parse_jobs(soup)
    assert_true(jobs, "No jobs were parsed from the live search page")

    sample_size = min(MIN_SAMPLE_JOBS, len(jobs))
    for index, job in enumerate(jobs[:sample_size], start=1):
        assert_true(job["job_url"].startswith(BASE_URL), f"Job {index}: job_url is not absolute")
        assert_true(isinstance(job["job_id"], int), f"Job {index}: job_id is not an int")
        assert_true(bool(job["title"]), f"Job {index}: title is empty")
        assert_true(job["title"] == job["title"].strip(), f"Job {index}: title has surrounding whitespace")
        if job["employment_type"] is not None:
            assert_true(
                job["employment_type"] == job["employment_type"].strip(),
                f"Job {index}: employment_type has surrounding whitespace",
            )
        if job["posted_at"] is not None:
            assert_true(
                job["posted_at"] == job["posted_at"].strip(),
                f"Job {index}: posted_at has surrounding whitespace",
            )
        if job["rate"] is not None:
            assert_true(job["rate"] == job["rate"].strip(), f"Job {index}: rate has surrounding whitespace")
        if job["tags"] is not None:
            assert_true(
                job["tags"] == job["tags"].strip(),
                f"Job {index}: tags has surrounding whitespace",
            )

    next_url = get_next_page_url(soup)
    if next_url is not None:
        assert_true(next_url.startswith("http"), "next page URL should be absolute")


def run_preflight_validation() -> None:
    print("[INFO] Running scraper preflight validation")
    validate_helpers()
    validate_fixture()

    session = requests.Session()
    soup = fetch_page(session, START_URL)
    if soup is None:
        fail(f"Could not fetch start page: {START_URL}")

    validate_live_page(soup)
    print("[PASS] Validation succeeded")
