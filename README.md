# NHL Play-by-Play Scraper and Database

This project builds a **queryable SQLite database** of NHL play-by-play (PxP) data from NHL.com, starting with the first season where modern PxP data is widely available (2007-08).

## Goals

- Backfill NHL game logs from 2007 onward.
- Respect strict rate limits: **at most one game-log request per minute**.
- Store normalized game/event data in SQLite.
- Provide a Pandas-friendly query layer for analytics and later feature engineering.

## Tech Stack

- Python 3.10+
- Pandas
- Requests
- SQLite
- Pytest

## Project Layout

- `nhl_pxp/api.py`: NHL API client.
- `nhl_pxp/rate_limit.py`: one-request-per-minute limiter.
- `nhl_pxp/storage.py`: SQLite schema + upserts.
- `nhl_pxp/scraper.py`: backfill/update orchestration.
- `nhl_pxp/query.py`: DataFrame query interface.
- `main.py`: CLI entrypoint.
- `tests/`: unit tests.

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py --database nhl_pxp.db --start-date 2007-09-01 --end-date 2007-09-03
```

### Nightly update example

```bash
python main.py --database nhl_pxp.db --mode daily
```

## Notes on Runtime

The initial backfill is intentionally slow due to the required limit of one game-log request per minute. This protects reliability and avoids overloading NHL endpoints.
