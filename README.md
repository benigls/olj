# Online Jobs PH Alerts

Incremental scraper and Telegram alert runner for OnlineJobs.ph job listings backed by Supabase Postgres.

## Run locally

Install dependencies:

```bash
uv sync
```

Create `.dlt/secrets.toml` from the example file and fill in your Telegram and Supabase values. Secrets are read by dlt.

```bash
mkdir -p .dlt
cp .dlt/secrets.toml.example .dlt/secrets.toml
```

Edit `.dlt/secrets.toml` with:

```toml
telegram_bot_token = "your-telegram-bot-token"
telegram_chat_id = "your-telegram-chat-id"

[destination.postgres.credentials]
database = "postgres"
username = "postgres"
password = "your-password"
host = "db.your-project-ref.supabase.co"
port = 5432
sslmode = "require"
```

`job_id` is the primary key for `olj.job_postings`. If the table already exists, run this once in Postgres to enforce it:

```sql
ALTER TABLE olj.job_postings ALTER COLUMN job_id SET NOT NULL;
ALTER TABLE olj.job_postings ADD PRIMARY KEY (job_id);
```

For Telegram DMs, open the bot in Telegram and send `/start` before using your numeric chat id. For groups, add the bot to the group and use the group chat id. For channels, add the bot as an admin and use the channel username or numeric channel id.

Test Telegram delivery without running ingestion:

```bash
uv run python -B -c 'from olj_scraper.alerts import get_secret, send_telegram_message; send_telegram_message(get_secret("telegram_bot_token"), get_secret("telegram_chat_id"), "OLJ test alert")'
```

Run the full alert job:

```bash
uv run python run_alerts.py
```

This will:

1. validate the live HTML structure
2. ingest newly added jobs into Supabase Postgres via dlt
3. query Postgres for newly loaded jobs that match the configured alert rules
4. send matching jobs to Telegram using Markdown formatting

Alert cursor state is stored in the `alert_state` table in the same Postgres database. Alerts are filtered in SQL using `loaded_at > last_alert_run_at`, so the app only evaluates jobs loaded since the previous alert run.

## Manual commands

Validate the parser against the live OnlineJobs.ph search page:

```bash
uv run python validate_ingestion.py
```

Run ingestion without sending alerts:

```bash
uv run python ingest.py
```

## Matching rules

- tags include any of: `sql`, `python`
- or title contains one of:
  - `data engineer`
  - `analytics engineer`
  - `data analyst`
  - `data scientist`

Update the rules in `olj_scraper/config.py`.

## Telegram message format

Alerts are sent as Telegram Markdown:

```text
**[job title](job_url)**

💵 *rate*
⏰ *Full Time/Part Time/Any*
📅 *posted date rounded down to the nearest hour*

<webpage preview>
```

## Docker

Build the container image with:

```bash
docker build -t onlinejobs-alerts .
```

Run the container with your local dlt secrets mounted read-only:

```bash
docker run --rm \
  -v "$PWD/.dlt:/app/.dlt:ro" \
  onlinejobs-alerts
```

The container starts `run_alerts.py` by default. The `.dlt` directory is excluded from the Docker build context so real secrets are only mounted at runtime.
