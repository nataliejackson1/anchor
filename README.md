# Anchor

Anchor is a family operations pipeline that ingests calendar events, normalizes them into a canonical schema, stores structured data in S3 / DuckDB, and uses an LLM-powered agent to generate a weekly family briefing.

It is designed to answer the practical questions that matter to a busy household:

- what is happening this week?
- what is the weather for upcoming events?
- how much drive time is needed before each event?
- what should the family know before the week starts?

## What it does

1. Pulls events from Google Calendar and simple iCal-style exports.
2. Normalizes them into a consistent `CalendarEvent` schema.
3. Writes event data to Parquet and syncs it to DuckDB.
4. Uses tool-backed LLM agents to fetch weather and drive-time data.
5. Produces a human-readable weekly briefing.
6. Emails the briefing to a configured recipient.

## Repository layout

- `agent/` — LLM agent and tool logic
- `delivery/` — email rendering / sending
- `ingestion/` — calendar adapters and source connectors
- `storage/` — S3 and DuckDB sync logic
- `tests/` — project test suite
- `run_pipeline.py` — main entry point
- `config.py` — environment-driven settings

## Local setup

1. Create a virtual environment:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Copy the example environment file and fill in your values:

   ```bash
   cp .env.example .env
   ```

4. Update `.env` with your real secrets and locations.

5. Run the test suite:

   ```bash
   pytest -q
   ```

6. Run the pipeline:

   ```bash
   python run_pipeline.py
   ```

## GitHub Actions

This repo includes a CI workflow in `.github/workflows/ci.yml` that:

- checks out the code
- installs Python dependencies
- runs the tests with pytest
- verifies the project stays healthy on each push and pull request

## Recommended GitHub setup

1. Push this repo to GitHub.
2. Add repository secrets for production values if you want to use real environment variables in GitHub-hosted runners.
3. Keep `.env` local only; do not commit secrets.
4. Use the included example file as a template.

## Notes

- The project is intentionally designed so configuration loads from `.env` when present and falls back to safe defaults when not present.
- Real API calls are isolated behind the tool layer so they can be safely unit tested with mocks.
- Some pipeline steps (S3 uploads, calendar syncing, or email delivery) require valid credentials and network access.

## Quick verification

```bash
source .venv/bin/activate
pytest -q
```