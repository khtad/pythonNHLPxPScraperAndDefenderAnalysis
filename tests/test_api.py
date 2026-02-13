from datetime import date

from nhl_pxp.api import NHLApiClient


class DummyResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class DummySession:
    def __init__(self, payload):
        self.payload = payload

    def get(self, *args, **kwargs):
        return DummyResponse(self.payload)


def test_get_game_ids_for_date_parses_schedule_payload():
    payload = {
        "dates": [
            {
                "games": [{"gamePk": 2007020001}, {"gamePk": 2007020002}],
            }
        ]
    }
    client = NHLApiClient(session=DummySession(payload))

    game_ids = client.get_game_ids_for_date(date(2007, 10, 3))

    assert game_ids == [2007020001, 2007020002]


def test_get_game_ids_for_date_handles_empty_schedule():
    client = NHLApiClient(session=DummySession({"dates": []}))

    game_ids = client.get_game_ids_for_date(date(2007, 10, 4))

    assert game_ids == []
