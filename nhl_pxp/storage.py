from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


class NHLPxpRepository:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = str(database_path)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.database_path)
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def initialize_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS games (
                    game_id INTEGER PRIMARY KEY,
                    game_date TEXT,
                    season TEXT,
                    game_type TEXT,
                    home_team_id INTEGER,
                    away_team_id INTEGER,
                    home_team_name TEXT,
                    away_team_name TEXT,
                    raw_json TEXT NOT NULL,
                    inserted_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS events (
                    game_id INTEGER NOT NULL,
                    event_idx INTEGER NOT NULL,
                    period INTEGER,
                    period_time TEXT,
                    event_type TEXT,
                    team_id INTEGER,
                    team_name TEXT,
                    player_1_id INTEGER,
                    player_2_id INTEGER,
                    description TEXT,
                    x_coord REAL,
                    y_coord REAL,
                    raw_json TEXT NOT NULL,
                    PRIMARY KEY (game_id, event_idx),
                    FOREIGN KEY (game_id) REFERENCES games(game_id)
                );

                CREATE INDEX IF NOT EXISTS idx_events_game_id ON events(game_id);
                CREATE INDEX IF NOT EXISTS idx_events_team_id ON events(team_id);
                CREATE INDEX IF NOT EXISTS idx_events_event_type ON events(event_type);
                """
            )

    def game_exists(self, game_id: int) -> bool:
        with self.connect() as conn:
            row = conn.execute("SELECT 1 FROM games WHERE game_id = ?", (game_id,)).fetchone()
            return row is not None

    def upsert_game_and_events(self, game_id: int, payload: dict[str, Any]) -> None:
        game_data = payload.get("gameData", {})
        teams = game_data.get("teams", {})
        live_data = payload.get("liveData", {})
        plays = live_data.get("plays", {}).get("allPlays", [])

        game_row = (
            game_id,
            game_data.get("datetime", {}).get("dateTime", "")[:10],
            game_data.get("game", {}).get("season"),
            game_data.get("game", {}).get("type"),
            teams.get("home", {}).get("id"),
            teams.get("away", {}).get("id"),
            teams.get("home", {}).get("name"),
            teams.get("away", {}).get("name"),
            str(payload),
        )

        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO games (
                    game_id, game_date, season, game_type, home_team_id, away_team_id,
                    home_team_name, away_team_name, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(game_id) DO UPDATE SET
                    game_date=excluded.game_date,
                    season=excluded.season,
                    game_type=excluded.game_type,
                    home_team_id=excluded.home_team_id,
                    away_team_id=excluded.away_team_id,
                    home_team_name=excluded.home_team_name,
                    away_team_name=excluded.away_team_name,
                    raw_json=excluded.raw_json
                """,
                game_row,
            )

            for event in plays:
                players = event.get("players", [])
                player_1_id = players[0]["player"]["id"] if len(players) > 0 and players[0].get("player") else None
                player_2_id = players[1]["player"]["id"] if len(players) > 1 and players[1].get("player") else None
                coords = event.get("coordinates", {})
                team = event.get("team", {})
                result = event.get("result", {})
                about = event.get("about", {})

                conn.execute(
                    """
                    INSERT INTO events (
                        game_id, event_idx, period, period_time, event_type, team_id, team_name,
                        player_1_id, player_2_id, description, x_coord, y_coord, raw_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(game_id, event_idx) DO UPDATE SET
                        period=excluded.period,
                        period_time=excluded.period_time,
                        event_type=excluded.event_type,
                        team_id=excluded.team_id,
                        team_name=excluded.team_name,
                        player_1_id=excluded.player_1_id,
                        player_2_id=excluded.player_2_id,
                        description=excluded.description,
                        x_coord=excluded.x_coord,
                        y_coord=excluded.y_coord,
                        raw_json=excluded.raw_json
                    """,
                    (
                        game_id,
                        about.get("eventIdx"),
                        about.get("period"),
                        about.get("periodTime"),
                        result.get("eventTypeId"),
                        team.get("id"),
                        team.get("name"),
                        player_1_id,
                        player_2_id,
                        result.get("description"),
                        coords.get("x"),
                        coords.get("y"),
                        str(event),
                    ),
                )
