from unittest.mock import Mock, patch

import nhl_api


def _mock_response(status_code, payload):
    response = Mock()
    response.status_code = status_code
    response.json.return_value = payload
    return response


@patch("nhl_api.requests.get")
def test_get_game_ids_for_date_returns_ids_from_schedule_json(mock_get):
    mock_get.return_value = _mock_response(
        200,
        {"dates": [{"games": [{"gamePk": 1}, {"gamePk": 2}, {"gamePk": 3}]}]},
    )

    assert nhl_api.get_game_ids_for_date("2024-01-01") == [1, 2, 3]


@patch("nhl_api.requests.get")
def test_get_game_ids_for_date_returns_empty_list_on_non_200(mock_get):
    mock_get.return_value = _mock_response(500, {})

    assert nhl_api.get_game_ids_for_date("2024-01-01") == []


@patch("nhl_api.requests.get")
def test_get_game_ids_for_date_returns_empty_list_when_dates_empty(mock_get):
    mock_get.return_value = _mock_response(200, {"dates": []})

    assert nhl_api.get_game_ids_for_date("2024-01-01") == []


@patch("nhl_api.requests.get")
@patch("nhl_api.time.sleep")
@patch("nhl_api.time.monotonic", side_effect=[1000, 1001])
def test_get_play_by_play_data_returns_shaped_rows(monotonic_mock, sleep_mock, mock_get):
    nhl_api._last_game_api_call = 0
    mock_get.return_value = _mock_response(
        200,
        {
            "liveData": {
                "plays": {
                    "allPlays": [
                        {
                            "about": {"period": 1, "periodTime": "10:00"},
                            "result": {"event": "SHOT", "description": "Wrist shot"},
                        },
                        {
                            "about": {"period": 2, "periodTime": "05:00"},
                            "result": {"event": "GOAL", "description": "Scored"},
                        },
                    ]
                }
            }
        },
    )

    data = nhl_api.get_play_by_play_data(2023020001)

    assert data == [
        {"period": 1, "time": "10:00", "event": "SHOT", "description": "Wrist shot"},
        {"period": 2, "time": "05:00", "event": "GOAL", "description": "Scored"},
    ]
    sleep_mock.assert_not_called()


@patch("nhl_api.requests.get")
@patch("nhl_api.time.sleep")
@patch("nhl_api.time.monotonic", side_effect=[1000, 1001])
def test_get_play_by_play_data_returns_none_on_non_200(monotonic_mock, sleep_mock, mock_get):
    nhl_api._last_game_api_call = 0
    mock_get.return_value = _mock_response(404, {})

    assert nhl_api.get_play_by_play_data(2023020001) is None


@patch("nhl_api.requests.get")
@patch("nhl_api.time.sleep")
@patch("nhl_api.time.monotonic", side_effect=[1000, 1001])
def test_get_play_by_play_data_returns_empty_list_when_no_plays(monotonic_mock, sleep_mock, mock_get):
    nhl_api._last_game_api_call = 0
    mock_get.return_value = _mock_response(200, {"liveData": {"plays": {"allPlays": []}}})

    assert nhl_api.get_play_by_play_data(2023020001) == []


@patch("nhl_api.requests.get")
@patch("nhl_api.time.sleep")
@patch("nhl_api.time.monotonic", side_effect=[1000, 1001])
def test_get_play_by_play_data_handles_missing_nested_keys(monotonic_mock, sleep_mock, mock_get):
    nhl_api._last_game_api_call = 0
    mock_get.return_value = _mock_response(
        200,
        {
            "liveData": {
                "plays": {
                    "allPlays": [
                        {},
                        {"about": {"period": 3}},
                        {"result": {"event": "STOP"}},
                    ]
                }
            }
        },
    )

    assert nhl_api.get_play_by_play_data(2023020001) == [
        {"period": None, "time": None, "event": None, "description": None},
        {"period": 3, "time": None, "event": None, "description": None},
        {"period": None, "time": None, "event": "STOP", "description": None},
    ]
