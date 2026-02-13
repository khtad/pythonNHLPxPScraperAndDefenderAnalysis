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
                    }
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


def test_query_service_returns_filtered_dataframe(tmp_path):
    db = tmp_path / "test.db"
    repo = NHLPxpRepository(db)
    repo.initialize_schema()
    repo.upsert_game_and_events(2007020001, sample_payload())

    query = NHLPxpQueryService(db)
    events_df = query.events_dataframe(game_id=2007020001, event_type="SHOT")

    assert len(events_df) == 1
    assert events_df.iloc[0]["team_id"] == 10
