from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .config import BASE_URL, HEADERS

log = logging.getLogger(__name__)


def fetch_page(session: requests.Session, url: str) -> BeautifulSoup | None:
    """Fetch a page and return parsed HTML or None on failure."""
    try:
        resp = session.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "lxml")
    except requests.RequestException as exc:
        log.error("Failed to fetch %s: %s", url, exc)
        return None


def strip_or_none(value: str | None) -> str | None:
    if value is None:
        return None

    cleaned = value.strip()
    return cleaned or None


def extract_job_id(job_path: str) -> str | None:
    if not job_path:
        return None

    last_segment = job_path.rstrip("/").rsplit("/", 1)[-1]
    if last_segment.isdigit():
        return last_segment

    match = re.search(r"-(\d+)$", last_segment)
    return match.group(1) if match else None


def parse_jobs(soup: BeautifulSoup) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []

    for anchor in soup.find_all("a", href=re.compile(r"^/jobseekers/job/")):
        job_path = anchor["href"].strip()
        job_id = extract_job_id(job_path)
        if not job_id:
            log.warning("Could not extract job ID from: %s", job_path)
            continue

        if any(job["job_id"] == int(job_id) for job in jobs):
            continue

        title = None
        employment_type = None
        h4_tag = anchor.find("h4", class_="fs-16 fw-700")
        if h4_tag:
            badge = h4_tag.find("span", class_="badge")
            if badge:
                employment_type = strip_or_none(badge.get_text())
                badge.decompose()
            title = strip_or_none(h4_tag.get_text())

        posted_at = None
        p_tag = anchor.find("p", attrs={"data-temp": True})
        if p_tag:
            posted_at = strip_or_none(p_tag["data-temp"])

        rate = None
        dd_tag = anchor.find("dd", class_="col")
        if dd_tag:
            rate = strip_or_none(dd_tag.get_text())

        tags = []
        job_tag_div = anchor.find("div", class_="job-tag")
        if job_tag_div:
            tags = [
                tag
                for tag in (
                    strip_or_none(badge.get_text())
                    for badge in job_tag_div.find_all("a", class_="badge")
                )
                if tag
            ]

        jobs.append(
            {
                "job_url": urljoin(BASE_URL, job_path),
                "job_id": int(job_id),
                "title": title,
                "employment_type": employment_type,
                "posted_at": posted_at,
                "rate": rate,
                "tags": ", ".join(tags) if tags else None,
            }
        )

    return jobs


def max_job_id(jobs: list[dict[str, Any]]) -> int:
    return max(int(job["job_id"]) for job in jobs)


def get_next_page_url(soup: BeautifulSoup) -> str | None:
    next_anchor = soup.find("a", rel=lambda r: r and "next" in r)
    if next_anchor and next_anchor.get("href"):
        href = next_anchor["href"].strip()
        if href.startswith("http"):
            return href
        return urljoin(BASE_URL, href)
    return None
