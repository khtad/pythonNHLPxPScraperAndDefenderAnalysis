from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from .api import NHLApiClient
from .storage import NHLPxpRepository


@dataclass
class ScrapeStats:
    dates_scanned: int = 0
    game_ids_found: int = 0
    games_inserted_or_updated: int = 0
    games_skipped_existing: int = 0


class NHLPxpScraper:
    def __init__(self, api: NHLApiClient, repository: NHLPxpRepository) -> None:
        self.api = api
        self.repository = repository

    def backfill(self, start_date: date, end_date: date, skip_existing: bool = True) -> ScrapeStats:
        if end_date < start_date:
            raise ValueError("end_date must be greater than or equal to start_date")

        self.repository.initialize_schema()
        stats = ScrapeStats()
        current = start_date

        while current <= end_date:
            stats.dates_scanned += 1
            game_ids = self.api.get_game_ids_for_date(current)
            stats.game_ids_found += len(game_ids)

            for game_id in game_ids:
                if skip_existing and self.repository.game_exists(game_id):
                    stats.games_skipped_existing += 1
                    continue

                payload = self.api.get_game_log(game_id)
                self.repository.upsert_game_and_events(game_id, payload)
                stats.games_inserted_or_updated += 1

            current += timedelta(days=1)

        return stats

    def run_daily_update(self, target_date: date) -> ScrapeStats:
        return self.backfill(start_date=target_date, end_date=target_date, skip_existing=False)
