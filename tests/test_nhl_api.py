import datetime
from unittest.mock import Mock, patch

import nhl_api


def _mock_response(status_code, payload):
    response = Mock()
    response.status_code = status_code
    response.json.return_value = payload
    return response


# --- get_game_ids_for_date tests (new NHL API: api-web.nhle.com) ---


@patch.object(nhl_api._session, "get")
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


@patch.object(nhl_api._session, "get")
def test_get_game_ids_for_date_returns_empty_list_on_non_200(mock_get):
    mock_get.return_value = _mock_response(500, {})

    assert nhl_api.get_game_ids_for_date("2024-01-01") == []


@patch.object(nhl_api._session, "get")
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


@patch.object(nhl_api._session, "get")
def test_get_game_ids_for_date_returns_empty_list_when_gameweek_empty(mock_get):
    mock_get.return_value = _mock_response(200, {"gameWeek": []})

    assert nhl_api.get_game_ids_for_date("2024-01-01") == []


@patch.object(nhl_api._session, "get")
def test_get_game_ids_for_date_accepts_date_object(mock_get):
    """main.py passes datetime.date objects; ensure str conversion works."""
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


# --- get_weekly_schedule tests ---


@patch.object(nhl_api._session, "get")
def test_get_weekly_schedule_returns_all_dates_and_game_ids(mock_get):
    mock_get.return_value = _mock_response(
        200,
        {
            "gameWeek": [
                {"date": "2024-01-01", "games": [{"id": 101}, {"id": 102}]},
                {"date": "2024-01-02", "games": [{"id": 201}]},
                {"date": "2024-01-03", "games": []},
            ],
            "nextStartDate": "2024-01-08",
        },
    )

    schedule, next_date = nhl_api.get_weekly_schedule("2024-01-01")

    assert schedule == {
        "2024-01-01": [101, 102],
        "2024-01-02": [201],
        "2024-01-03": [],
    }
    assert next_date == "2024-01-08"


@patch.object(nhl_api._session, "get")
def test_get_weekly_schedule_returns_next_start_date_for_pagination(mock_get):
    mock_get.return_value = _mock_response(
        200,
        {
            "gameWeek": [
                {"date": "2024-03-01", "games": [{"id": 1}]},
            ],
            "nextStartDate": "2024-03-08",
        },
    )

    _, next_date = nhl_api.get_weekly_schedule("2024-03-01")
    assert next_date == "2024-03-08"


@patch.object(nhl_api._session, "get")
def test_get_weekly_schedule_returns_none_next_date_when_missing(mock_get):
    """At the end of available data, nextStartDate may be absent."""
    mock_get.return_value = _mock_response(
        200,
        {
            "gameWeek": [
                {"date": "2026-03-10", "games": []},
            ],
        },
    )

    schedule, next_date = nhl_api.get_weekly_schedule("2026-03-10")
    assert next_date is None
    assert schedule == {"2026-03-10": []}


@patch.object(nhl_api._session, "get")
def test_get_weekly_schedule_returns_empty_on_non_200(mock_get):
    mock_get.return_value = _mock_response(500, {})

    schedule, next_date = nhl_api.get_weekly_schedule("2024-01-01")

    assert schedule == {}
    assert next_date is None


@patch.object(nhl_api._session, "get")
def test_get_weekly_schedule_returns_empty_when_gameweek_missing(mock_get):
    mock_get.return_value = _mock_response(200, {})

    schedule, next_date = nhl_api.get_weekly_schedule("2024-01-01")

    assert schedule == {}
    assert next_date is None


@patch.object(nhl_api._session, "get")
def test_get_weekly_schedule_accepts_date_object(mock_get):
    mock_get.return_value = _mock_response(
        200,
        {
            "gameWeek": [
                {"date": "2024-01-01", "games": [{"id": 5}]},
            ],
            "nextStartDate": "2024-01-08",
        },
    )

    schedule, _ = nhl_api.get_weekly_schedule(datetime.date(2024, 1, 1))

    assert schedule == {"2024-01-01": [5]}
    # Verify the URL was built with a string date, not a date object
    called_url = mock_get.call_args[0][0]
    assert "2024-01-01" in called_url


@patch.object(nhl_api._session, "get")
def test_get_weekly_schedule_makes_single_api_call(mock_get):
    """A weekly fetch should make exactly one HTTP request."""
    mock_get.return_value = _mock_response(
        200,
        {
            "gameWeek": [
                {"date": "2024-01-01", "games": [{"id": 1}]},
                {"date": "2024-01-02", "games": [{"id": 2}]},
                {"date": "2024-01-03", "games": [{"id": 3}]},
                {"date": "2024-01-04", "games": [{"id": 4}]},
                {"date": "2024-01-05", "games": [{"id": 5}]},
                {"date": "2024-01-06", "games": [{"id": 6}]},
                {"date": "2024-01-07", "games": [{"id": 7}]},
            ],
            "nextStartDate": "2024-01-08",
        },
    )

    schedule, _ = nhl_api.get_weekly_schedule("2024-01-01")

    assert len(schedule) == 7
    assert mock_get.call_count == 1


# --- get_play_by_play_data tests (new NHL API: api-web.nhle.com) ---


@patch.object(nhl_api._session, "get")
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


@patch.object(nhl_api._session, "get")
@patch("nhl_api.time.sleep")
@patch("nhl_api.time.monotonic", side_effect=[1000, 1001])
def test_get_play_by_play_data_returns_none_on_non_200(monotonic_mock, sleep_mock, mock_get):
    nhl_api._last_game_api_call = 0
    mock_get.return_value = _mock_response(404, {})

    assert nhl_api.get_play_by_play_data(2023020001) is None


@patch.object(nhl_api._session, "get")
@patch("nhl_api.time.sleep")
@patch("nhl_api.time.monotonic", side_effect=[1000, 1001])
def test_get_play_by_play_data_returns_empty_list_when_no_plays(monotonic_mock, sleep_mock, mock_get):
    nhl_api._last_game_api_call = 0
    mock_get.return_value = _mock_response(200, {"plays": []})

    assert nhl_api.get_play_by_play_data(2023020001) == []


@patch.object(nhl_api._session, "get")
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


# --- rate limiting tests ---


def test_rate_limit_interval_is_two_seconds():
    """Verify the rate limit was reduced from 15s to 2s."""
    assert nhl_api._GAME_API_MIN_INTERVAL == 2


@patch.object(nhl_api._session, "get")
@patch("nhl_api.time.sleep")
@patch("nhl_api.time.monotonic", side_effect=[5, 10])
def test_get_play_by_play_data_rate_limits_when_called_too_fast(monotonic_mock, sleep_mock, mock_get):
    nhl_api._last_game_api_call = 5  # same as first monotonic() return
    mock_get.return_value = _mock_response(200, {"plays": []})

    nhl_api.get_play_by_play_data(2023020001)

    sleep_mock.assert_called_once()
    wait_time = sleep_mock.call_args[0][0]
    assert wait_time == nhl_api._GAME_API_MIN_INTERVAL


@patch.object(nhl_api._session, "get")
@patch("nhl_api.time.sleep")
@patch("nhl_api.time.monotonic", side_effect=[100, 200])
def test_get_play_by_play_data_skips_sleep_when_enough_time_elapsed(monotonic_mock, sleep_mock, mock_get):
    nhl_api._last_game_api_call = 0  # long ago
    mock_get.return_value = _mock_response(200, {"plays": []})

    nhl_api.get_play_by_play_data(2023020001)

    sleep_mock.assert_not_called()
