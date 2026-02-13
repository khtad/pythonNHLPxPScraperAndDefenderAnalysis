from __future__ import annotations

from datetime import date
from typing import Any

import requests

from .rate_limit import GameLogRateLimiter


class NHLApiClient:
    SCHEDULE_URL = "https://statsapi.web.nhl.com/api/v1/schedule"
    GAME_LOG_URL = "https://statsapi.web.nhl.com/api/v1/game/{game_id}/feed/live"

    def __init__(self, session: requests.Session | None = None, limiter: GameLogRateLimiter | None = None) -> None:
        self.session = session or requests.Session()
        self.limiter = limiter or GameLogRateLimiter(interval_seconds=60)

    def get_game_ids_for_date(self, game_date: date) -> list[int]:
        response = self.session.get(
            self.SCHEDULE_URL,
            params={"startDate": game_date.isoformat(), "endDate": game_date.isoformat()},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        game_ids: list[int] = []
        for day in payload.get("dates", []):
            for game in day.get("games", []):
                game_pk = game.get("gamePk")
                if game_pk:
                    game_ids.append(int(game_pk))
        return game_ids

    def get_game_log(self, game_id: int) -> dict[str, Any]:
        self.limiter.wait_for_slot()
        response = self.session.get(self.GAME_LOG_URL.format(game_id=game_id), timeout=30)
        response.raise_for_status()
        return response.json()
