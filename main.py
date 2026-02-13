from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta

from nhl_pxp.api import NHLApiClient
from nhl_pxp.query import NHLPxpQueryService
from nhl_pxp.scraper import NHLPxpScraper
from nhl_pxp.storage import NHLPxpRepository


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="NHL PxP scraper and SQLite builder")
    parser.add_argument("--database", default="nhl_pxp.db", help="SQLite database path")
    parser.add_argument("--mode", choices=["backfill", "daily"], default="backfill")
    parser.add_argument("--start-date", default="2007-09-01", help="Backfill start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", default=date.today().isoformat(), help="Backfill end date (YYYY-MM-DD)")
    parser.add_argument("--show-sample", action="store_true", help="Print sample queried rows after scrape")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    repository = NHLPxpRepository(args.database)
    api = NHLApiClient()
    scraper = NHLPxpScraper(api=api, repository=repository)

    if args.mode == "daily":
        target_date = date.today() - timedelta(days=1)
        stats = scraper.run_daily_update(target_date)
    else:
        start = datetime.strptime(args.start_date, "%Y-%m-%d").date()
        end = datetime.strptime(args.end_date, "%Y-%m-%d").date()
        stats = scraper.backfill(start, end)

    print(stats)

    if args.show_sample:
        query = NHLPxpQueryService(args.database)
        print(query.games_dataframe(limit=5))
        print(query.events_dataframe(limit=5))


if __name__ == "__main__":
    main()
