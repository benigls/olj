from olj_scraper.ingestion import run_ingestion
from olj_scraper.logging_utils import ensure_logging


if __name__ == "__main__":
    ensure_logging()
    run_ingestion()
