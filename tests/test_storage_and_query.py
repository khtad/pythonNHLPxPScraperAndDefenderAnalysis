import sqlite3

from nhl_pxp.query import NHLPxpQueryService
from nhl_pxp.storage import NHLPxpRepository


def sample_payload():
    return {
        "gameData": {
            "datetime": {"dateTime": "2007-10-03T23:00:00Z"},
            "game": {"season": "20072008", "type": "R"},
            "teams": {
                "home": {"id": 10, "name": "Home Team"},
                "away": {"id": 20, "name": "Away Team"},
            },
        },
        "liveData": {
            "plays": {
                "allPlays": [
                    {
                        "about": {"eventIdx": 1, "period": 1, "periodTime": "00:30"},
                        "result": {"eventTypeId": "SHOT", "description": "Test shot"},
                        "team": {"id": 10, "name": "Home Team"},
                        "players": [{"player": {"id": 1001}}],
                        "coordinates": {"x": 10, "y": 5},
                    },
                    {
                        "about": {"eventIdx": 2, "period": 1, "periodTime": "00:31"},
                        "result": {"eventTypeId": "MISS", "description": "Away miss"},
                        "team": {"id": 20, "name": "Away Team"},
                        "players": [{"player": {"id": 2001}}],
                        "coordinates": {"x": -10, "y": -5},
                    },
                ]
            }
        },
    }


def test_repository_initializes_and_upserts(tmp_path):
    db = tmp_path / "test.db"
    repo = NHLPxpRepository(db)
    repo.initialize_schema()
    repo.upsert_game_and_events(2007020001, sample_payload())

    assert repo.game_exists(2007020001)


def test_repository_upsert_is_idempotent_and_updates_existing_event(tmp_path):
    db = tmp_path / "test.db"
    repo = NHLPxpRepository(db)
    repo.initialize_schema()

    payload = sample_payload()
    repo.upsert_game_and_events(2007020001, payload)
    repo.upsert_game_and_events(2007020001, payload)

    payload["liveData"]["plays"]["allPlays"][0]["result"]["description"] = "Updated shot description"
    repo.upsert_game_and_events(2007020001, payload)

    with sqlite3.connect(db) as conn:
        games_count = conn.execute("SELECT COUNT(*) FROM games WHERE game_id = 2007020001").fetchone()[0]
        events_count = conn.execute("SELECT COUNT(*) FROM events WHERE game_id = 2007020001").fetchone()[0]
        updated_description = conn.execute(
            "SELECT description FROM events WHERE game_id = 2007020001 AND event_idx = 1"
        ).fetchone()[0]

    assert games_count == 1
    assert events_count == 2
    assert updated_description == "Updated shot description"


def test_repository_handles_missing_optional_event_fields(tmp_path):
    db = tmp_path / "test.db"
    repo = NHLPxpRepository(db)
    repo.initialize_schema()

    payload = {
        "gameData": {
            "datetime": {"dateTime": "2007-10-03T23:00:00Z"},
            "game": {"season": "20072008", "type": "R"},
            "teams": {"home": {"id": 1, "name": "A"}, "away": {"id": 2, "name": "B"}},
        },
        "liveData": {
            "plays": {
                "allPlays": [
                    {
                        "about": {"eventIdx": 7, "period": 1, "periodTime": "01:11"},
                        "result": {"eventTypeId": "STOP", "description": "Whistle"},
                    }
                ]
            }
        },
    }

    repo.upsert_game_and_events(2007020009, payload)

    query = NHLPxpQueryService(db)
    events_df = query.events_dataframe(game_id=2007020009)
    row = events_df.iloc[0]

    assert len(events_df) == 1
    assert row["team_id"] is None
    assert row["player_1_id"] is None
    assert row["x_coord"] is None


def test_query_service_returns_filtered_dataframe(tmp_path):
    db = tmp_path / "test.db"
    repo = NHLPxpRepository(db)
    repo.initialize_schema()
    repo.upsert_game_and_events(2007020001, sample_payload())

    query = NHLPxpQueryService(db)
    events_df = query.events_dataframe(game_id=2007020001, event_type="SHOT")

    assert len(events_df) == 1
    assert events_df.iloc[0]["team_id"] == 10


def test_query_service_combined_filters_and_limit(tmp_path):
    db = tmp_path / "test.db"
    repo = NHLPxpRepository(db)
    repo.initialize_schema()
    repo.upsert_game_and_events(2007020001, sample_payload())

    query = NHLPxpQueryService(db)
    events_df = query.events_dataframe(game_id=2007020001, team_id=10, event_type="SHOT", limit=1)

    assert list(events_df["event_idx"]) == [1]


def test_query_service_uses_parameterized_filters(tmp_path):
    db = tmp_path / "test.db"
    repo = NHLPxpRepository(db)
    repo.initialize_schema()
    repo.upsert_game_and_events(2007020001, sample_payload())

    query = NHLPxpQueryService(db)
    events_df = query.events_dataframe(event_type="SHOT' OR 1=1 --")

    assert events_df.empty
