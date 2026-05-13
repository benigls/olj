from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Iterator
from zoneinfo import ZoneInfo

from .config import (
    ALERT_STATE_NAME,
    ALERT_STATE_TABLE,
    DATASET_NAME,
    MATCH_TAGS,
    MATCH_TITLE_KEYWORDS,
)
from .ingestion import run_ingestion
from .logging_utils import ensure_logging
from .pipeline import get_pipeline
from .telegram import get_secret, send_telegram_message
from .validation import run_preflight_validation

log = logging.getLogger(__name__)
ALERT_TIMEZONE = ZoneInfo("Asia/Manila")


@dataclass(frozen=True)
class AlertJob:
    job_id: int
    title: str
    job_url: str
    tags: str | None
    posted_at: datetime | str | None
    rate: str | None
    employment_type: str | None

def split_tags(tags: str | None) -> list[str]:
    if not tags:
        return []
    return [part.strip() for part in tags.split(",") if part.strip()]


def escape_markdown_v2(value: str) -> str:
    return "".join(
        f"\\{char}" if char in r"_*[]()~`>#+-=|{}.!" else char for char in value
    )


def format_posted_at(value: datetime | str | None) -> str:
    if not value:
        return "Unknown"

    parsed: datetime | None = None

    if isinstance(value, datetime):
        parsed = value
    else:
        raw_value = str(value).strip()

        if raw_value.isdigit():
            timestamp = int(raw_value)
            if timestamp > 9_999_999_999:
                timestamp = timestamp / 1000
            parsed = datetime.fromtimestamp(timestamp, tz=UTC)
        else:
            for date_format in (
                "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%dT%H:%M:%S.%f%z",
                "%Y-%m-%d %H:%M:%S%z",
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
                return raw_value

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)

    parsed = parsed.astimezone(ALERT_TIMEZONE)
    truncated = parsed.replace(minute=0, second=0, microsecond=0)
    return truncated.strftime("%b %-d, %Y %-I:00 %p")

def format_alert(job: AlertJob) -> str:
    title = escape_markdown_v2(job.title or "Untitled job")
    rate = escape_markdown_v2(job.rate or "Not listed")
    employment_type = escape_markdown_v2(job.employment_type or "Any")
    posted_at = escape_markdown_v2(format_posted_at(job.posted_at))
    job_url = escape_markdown_v2(job.job_url)

    return "\n".join(
        [
            f"*[{title}]({job_url})*",
            "",
            f"💰 {rate}",
            f"⌛ {employment_type}",
            f"🗓️ {posted_at}",
        ]
    )


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def normalize_alert_run_at(value: Any) -> str:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC).isoformat()
    if value:
        return str(value)
    return "1970-01-01T00:00:00+00:00"


def build_alert_where_clause() -> str:
    title_filters = [
        f"LOWER(COALESCE(title, '')) LIKE {sql_literal('%' + keyword.lower() + '%')}"
        for keyword in sorted(MATCH_TITLE_KEYWORDS)
    ]
    tag_filters = [
        f"LOWER(COALESCE(tags, '')) LIKE {sql_literal('%' + tag.lower() + '%')}"
        for tag in sorted(MATCH_TAGS)
    ]
    return f"({' OR '.join(title_filters)}) OR ({' OR '.join(tag_filters)})"


def fetch_matching_jobs_since(pipeline: Any, last_alert_run_at: str) -> list[AlertJob]:
    alert_where_clause = build_alert_where_clause()
    with pipeline.sql_client() as client:
        with client.execute_query(
            f"""
            SELECT
                job_id,
                title,
                job_url,
                tags,
                posted_at,
                rate,
                employment_type
            FROM {DATASET_NAME}.job_postings
            WHERE loaded_at > {sql_literal(last_alert_run_at)}
                AND ({alert_where_clause})
            ORDER BY job_id ASC
            """
        ) as cur:
            rows = cur.fetchall()

    jobs: list[AlertJob] = []
    for row in rows:
        jobs.append(
            AlertJob(
                job_id=int(row[0]),
                title=row[1] or "",
                job_url=row[2] or "",
                tags=row[3],
                posted_at=row[4],
                rate=row[5],
                employment_type=row[6],
            )
        )
    return jobs


def get_alert_state(pipeline: Any) -> dict[str, Any]:
    try:
        with pipeline.sql_client() as client:
            with client.execute_query(
                f"""
                SELECT last_alert_run_at, last_matching_job_id
                FROM {DATASET_NAME}.{ALERT_STATE_TABLE}
                WHERE state_name = '{ALERT_STATE_NAME}'
                LIMIT 1
                """
            ) as cur:
                row = cur.fetchone()
    except Exception:
        return {
            "last_alert_run_at": "1970-01-01T00:00:00+00:00",
            "last_matching_job_id": 0,
        }

    if not row:
        return {
            "last_alert_run_at": "1970-01-01T00:00:00+00:00",
            "last_matching_job_id": 0,
        }

    return {
        "last_alert_run_at": normalize_alert_run_at(row[0]),
        "last_matching_job_id": int(row[1] or 0),
    }


@dlt.resource(name=ALERT_STATE_TABLE, write_disposition="replace")
def alert_state_resource(state_row: dict[str, Any]) -> Iterator[dict[str, Any]]:
    yield state_row


def persist_alert_state(
    pipeline: Any, last_alert_run_at: str, last_matching_job_id: int
) -> None:
    state_row = {
        "state_name": ALERT_STATE_NAME,
        "last_alert_run_at": last_alert_run_at,
        "last_matching_job_id": last_matching_job_id,
        "updated_at": datetime.now(UTC).isoformat(),
    }
    pipeline.run(alert_state_resource(state_row))


def run_alerts() -> None:
    ensure_logging()
    run_preflight_validation()
    run_ingestion()

    token = get_secret("telegram_bot_token")
    chat_id = get_secret("telegram_chat_id")

    pipeline = get_pipeline()
    state = get_alert_state(pipeline)
    last_alert_run_at = state["last_alert_run_at"]
    last_matching_job_id = state["last_matching_job_id"]
    current_alert_run_at = datetime.now(UTC).isoformat()

    jobs = fetch_matching_jobs_since(pipeline, last_alert_run_at)
    log.info(
        "Found %s matching job(s) loaded after %s.",
        len(jobs),
        last_alert_run_at,
    )

    for job in jobs:
        send_telegram_message(
            token, chat_id, format_alert(job), parse_mode="MarkdownV2"
        )
        last_matching_job_id = max(last_matching_job_id, job.job_id)
        log.info("Sent Telegram alert for job_id=%s", job.job_id)

    persist_alert_state(pipeline, current_alert_run_at, last_matching_job_id)
    log.info("Updated alert state to last_alert_run_at=%s", current_alert_run_at)
