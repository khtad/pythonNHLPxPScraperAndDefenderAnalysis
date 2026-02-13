from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd


class NHLPxpQueryService:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = str(database_path)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database_path)

    def events_dataframe(
        self,
        game_id: int | None = None,
        team_id: int | None = None,
        event_type: str | None = None,
        limit: int | None = None,
    ) -> pd.DataFrame:
        sql = "SELECT * FROM events WHERE 1=1"
        params: list[object] = []

        if game_id is not None:
            sql += " AND game_id = ?"
            params.append(game_id)
        if team_id is not None:
            sql += " AND team_id = ?"
            params.append(team_id)
        if event_type is not None:
            sql += " AND event_type = ?"
            params.append(event_type)

        sql += " ORDER BY game_id, event_idx"

        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)

        with self._connect() as conn:
            return pd.read_sql_query(sql, conn, params=params)

    def games_dataframe(self, season: str | None = None, limit: int | None = None) -> pd.DataFrame:
        sql = "SELECT * FROM games WHERE 1=1"
        params: list[object] = []

        if season is not None:
            sql += " AND season = ?"
            params.append(season)

        sql += " ORDER BY game_date, game_id"

        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)

        with self._connect() as conn:
            return pd.read_sql_query(sql, conn, params=params)
