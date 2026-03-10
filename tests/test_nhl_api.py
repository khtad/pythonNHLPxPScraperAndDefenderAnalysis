from unittest.mock import Mock, patch

import nhl_api


def _mock_response(status_code, payload):
    response = Mock()
    response.status_code = status_code
    response.json.return_value = payload
    return response


# --- get_game_ids_for_date tests (new NHL API: api-web.nhle.com) ---


@patch("nhl_api.requests.get")
def test_get_game_ids_for_date_returns_ids_from_schedule_json(mock_get):
    mock_get.return_value = _mock_response(
        200,
        {
            "gameWeek": [
                {
                    "date": "2024-01-01",
                    "games": [{"id": 1}, {"id": 2}, {"id": 3}],
                },
                {
                    "date": "2024-01-02",
                    "games": [{"id": 99}],
                },
            ]
        },
    )

    assert nhl_api.get_game_ids_for_date("2024-01-01") == [1, 2, 3]


@patch("nhl_api.requests.get")
def test_get_game_ids_for_date_returns_empty_list_on_non_200(mock_get):
    mock_get.return_value = _mock_response(500, {})

    assert nhl_api.get_game_ids_for_date("2024-01-01") == []


@patch("nhl_api.requests.get")
def test_get_game_ids_for_date_returns_empty_list_when_no_matching_date(mock_get):
    mock_get.return_value = _mock_response(
        200,
        {
            "gameWeek": [
                {
                    "date": "2024-01-02",
                    "games": [{"id": 99}],
                },
            ]
        },
    )

    assert nhl_api.get_game_ids_for_date("2024-01-01") == []


@patch("nhl_api.requests.get")
def test_get_game_ids_for_date_returns_empty_list_when_gameweek_empty(mock_get):
    mock_get.return_value = _mock_response(200, {"gameWeek": []})

    assert nhl_api.get_game_ids_for_date("2024-01-01") == []


@patch("nhl_api.requests.get")
def test_get_game_ids_for_date_accepts_date_object(mock_get):
    """main.py passes datetime.date objects; ensure str conversion works."""
    import datetime

    mock_get.return_value = _mock_response(
        200,
        {
            "gameWeek": [
                {
                    "date": "2024-01-01",
                    "games": [{"id": 10}],
                },
            ]
        },
    )

    assert nhl_api.get_game_ids_for_date(datetime.date(2024, 1, 1)) == [10]


# --- get_play_by_play_data tests (new NHL API: api-web.nhle.com) ---


@patch("nhl_api.requests.get")
@patch("nhl_api.time.sleep")
@patch("nhl_api.time.monotonic", side_effect=[1000, 1001])
def test_get_play_by_play_data_returns_shaped_rows(monotonic_mock, sleep_mock, mock_get):
    nhl_api._last_game_api_call = 0
    mock_get.return_value = _mock_response(
        200,
        {
            "plays": [
                {
                    "periodDescriptor": {"number": 1, "periodType": "REG"},
                    "timeInPeriod": "10:00",
                    "typeDescKey": "shot-on-goal",
                },
                {
                    "periodDescriptor": {"number": 2, "periodType": "REG"},
                    "timeInPeriod": "05:00",
                    "typeDescKey": "goal",
                },
            ]
        },
    )

    data = nhl_api.get_play_by_play_data(2023020001)

    assert data == [
        {"period": 1, "time": "10:00", "event": "shot-on-goal", "description": "shot-on-goal"},
        {"period": 2, "time": "05:00", "event": "goal", "description": "goal"},
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
    mock_get.return_value = _mock_response(200, {"plays": []})

    assert nhl_api.get_play_by_play_data(2023020001) == []


@patch("nhl_api.requests.get")
@patch("nhl_api.time.sleep")
@patch("nhl_api.time.monotonic", side_effect=[1000, 1001])
def test_get_play_by_play_data_handles_missing_nested_keys(monotonic_mock, sleep_mock, mock_get):
    nhl_api._last_game_api_call = 0
    mock_get.return_value = _mock_response(
        200,
        {
            "plays": [
                {},
                {"periodDescriptor": {"number": 3}},
                {"typeDescKey": "stoppage"},
            ]
        },
    )

    assert nhl_api.get_play_by_play_data(2023020001) == [
        {"period": None, "time": None, "event": None, "description": None},
        {"period": 3, "time": None, "event": None, "description": None},
        {"period": None, "time": None, "event": "stoppage", "description": "stoppage"},
    ]


@patch("nhl_api.requests.get")
@patch("nhl_api.time.sleep")
@patch("nhl_api.time.monotonic", side_effect=[5, 10])
def test_get_play_by_play_data_rate_limits_when_called_too_fast(monotonic_mock, sleep_mock, mock_get):
    nhl_api._last_game_api_call = 5  # same as first monotonic() return
    mock_get.return_value = _mock_response(200, {"plays": []})

    nhl_api.get_play_by_play_data(2023020001)

    sleep_mock.assert_called_once()
    wait_time = sleep_mock.call_args[0][0]
    assert wait_time == nhl_api._GAME_API_MIN_INTERVAL
