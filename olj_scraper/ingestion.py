from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Any, Iterator
from zoneinfo import ZoneInfo

import dlt
import requests

from .config import DEFAULT_CRAWL_DELAY, START_URL, STATE_LAST_SEEN_JOB_ID
from .parsing import fetch_page, get_next_page_url, max_job_id, parse_jobs
from .pipeline import get_pipeline

log = logging.getLogger(__name__)
SOURCE_TIMEZONE = ZoneInfo("Asia/Manila")


def normalize_posted_at(value: str | None) -> datetime | None:
    if not value:
        return None

    raw_value = value.strip()
    parsed: datetime | None = None

    if raw_value.isdigit():
        timestamp = int(raw_value)
        if timestamp > 9_999_999_999:
            timestamp = timestamp / 1000
        return datetime.fromtimestamp(timestamp, tz=UTC)

    for date_format in (
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%d %H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            parsed = datetime.strptime(raw_value, date_format)
            break
        except ValueError:
            continue

    if not parsed:
        try:
            parsed = datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
        except ValueError:
            log.warning("Could not parse posted_at value: %s", value)
            return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=SOURCE_TIMEZONE)

    return parsed.astimezone(UTC)


@dlt.resource(name="job_postings", write_disposition="merge", primary_key="job_id")
def job_postings_resource(
    initial_last_seen_job_id: int = 0,
) -> Iterator[dict[str, Any]]:
    crawl_delay = DEFAULT_CRAWL_DELAY
    session = requests.Session()
    state = dlt.current.resource_state()
    loaded_at = datetime.now(UTC)
    last_seen_job_id = int(
        state.get(STATE_LAST_SEEN_JOB_ID) or initial_last_seen_job_id or 0
    )
    newest_seen_job_id = last_seen_job_id

    current_url = START_URL
    page_num = 1
    total_jobs = 0
    total_new_jobs = 0

    log.info("Last seen job ID before this run: %s", last_seen_job_id or "none")

    while current_url:
        log.info("Scraping page %s: %s", page_num, current_url)
        soup = fetch_page(session, current_url)

        if soup is None:
            log.error("Aborting pagination due to fetch error.")
            break

        jobs = parse_jobs(soup)
        log.info("  -> Found %s job(s) on page %s", len(jobs), page_num)
        total_jobs += len(jobs)

        for job in jobs:
            job_id = job["job_id"]
            if job_id <= last_seen_job_id:
                continue

            newest_seen_job_id = max(newest_seen_job_id, job_id)
            total_new_jobs += 1
            yield {
                **job,
                "posted_at": normalize_posted_at(job["posted_at"]),
                "loaded_at": loaded_at,
            }

        if not jobs:
            log.info("No jobs found on page %s; stopping pagination.", page_num)
            break

        if max_job_id(jobs) <= last_seen_job_id:
            log.info(
                "Page contains no jobs newer than the last seen job ID; stopping pagination."
            )
            break

        next_url = get_next_page_url(soup)
        if not next_url:
            log.info("No 'next' link found - reached last page (%s).", page_num)
            break

        current_url = next_url
        page_num += 1

        log.info("  Waiting %ss before next page...", crawl_delay)
        time.sleep(crawl_delay)

    if newest_seen_job_id > last_seen_job_id:
        state[STATE_LAST_SEEN_JOB_ID] = newest_seen_job_id
        state["last_successful_run_at"] = datetime.now(UTC).isoformat()

    log.info(
        "Scraping complete. Pages inspected: %s; jobs seen: %s; new jobs collected: %s; newest job ID: %s",
        page_num,
        total_jobs,
        total_new_jobs,
        newest_seen_job_id or "none",
    )


def get_existing_max_job_id(pipeline: Any) -> int:
    try:
        with pipeline.sql_client() as client:
            with client.execute_query(
                "SELECT MAX(CAST(job_id AS BIGINT)) AS max_job_id FROM olj.job_postings"
            ) as cur:
                row = cur.fetchone()
    except Exception as exc:
        log.info("Could not read existing max job_id; starting from scratch: %s", exc)
        return 0

    return int(row[0]) if row and row[0] is not None else 0


def run_ingestion() -> None:
    pipeline = get_pipeline()
    initial_last_seen_job_id = get_existing_max_job_id(pipeline)
    log.info("Starting dlt pipeline...")
    load_info = pipeline.run(job_postings_resource(initial_last_seen_job_id))
    log.info("Load complete:\n%s", load_info)
