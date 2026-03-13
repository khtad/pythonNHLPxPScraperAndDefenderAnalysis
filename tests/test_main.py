import datetime
import sqlite3
from unittest.mock import patch, MagicMock

import main
from database import (
    create_connection, create_collection_log_table,
    mark_date_collected,
)


def _in_memory_conn():
    conn = sqlite3.connect(":memory:")
    create_collection_log_table(conn)
    return conn


def _patch_datetime(end_date):
    """Return a mock datetime module that delegates real operations to datetime."""
    mock_dt = MagicMock()
    mock_dt.date.today.return_value = end_date
    mock_dt.date.side_effect = lambda *args, **kw: datetime.date(*args, **kw)
    mock_dt.date.fromisoformat = datetime.date.fromisoformat
    mock_dt.timedelta = datetime.timedelta
    return mock_dt


@patch("main.get_play_by_play_data")
@patch("main.get_weekly_schedule")
@patch("main.deduplicate_existing_tables")
@patch("main.create_connection")
def test_main_uses_weekly_schedule_instead_of_daily(
    mock_conn, mock_dedup, mock_weekly, mock_pbp,
):
    """main() should call get_weekly_schedule, not get_game_ids_for_date."""
    conn = _in_memory_conn()
    mock_conn.return_value = conn

    mock_weekly.return_value = (
        {"2007-10-03": [2007020001]},
        None,
    )
    mock_pbp.return_value = [{"period": 1, "time": "00:00", "event": "goal", "description": "goal"}]

    with patch("main.datetime", _patch_datetime(datetime.date(2007, 10, 5))):
        main.main()

    mock_weekly.assert_called()
    mock_pbp.assert_called_once_with(2007020001)


@patch("main.get_play_by_play_data")
@patch("main.get_weekly_schedule")
@patch("main.deduplicate_existing_tables")
@patch("main.create_connection")
def test_main_advances_by_next_start_date(
    mock_conn, mock_dedup, mock_weekly, mock_pbp,
):
    """main() should paginate using nextStartDate from the API."""
    conn = _in_memory_conn()
    mock_conn.return_value = conn

    mock_weekly.side_effect = [
        ({"2007-10-03": [1], "2007-10-04": [2]}, "2007-10-08"),
        ({"2007-10-08": [3]}, None),
    ]
    mock_pbp.return_value = [{"period": 1, "time": "00:00", "event": "x", "description": "x"}]

    with patch("main.datetime", _patch_datetime(datetime.date(2007, 10, 10))):
        main.main()

    assert mock_weekly.call_count == 2
    assert mock_pbp.call_count == 3


@patch("main.get_play_by_play_data")
@patch("main.get_weekly_schedule")
@patch("main.deduplicate_existing_tables")
@patch("main.create_connection")
def test_main_skips_dates_outside_range(
    mock_conn, mock_dedup, mock_weekly, mock_pbp,
):
    """Dates in gameWeek that fall outside start_date..end_date should be skipped."""
    conn = _in_memory_conn()
    mock_conn.return_value = conn

    mock_weekly.return_value = (
        {
            "2007-10-03": [1],
            "2007-10-04": [2],
            "2007-10-05": [3],  # past end_date
        },
        None,
    )
    mock_pbp.return_value = [{"period": 1, "time": "00:00", "event": "x", "description": "x"}]

    with patch("main.datetime", _patch_datetime(datetime.date(2007, 10, 4))):
        main.main()

    assert mock_pbp.call_count == 2


@patch("main.mark_date_collected")
@patch("main.get_play_by_play_data")
@patch("main.get_weekly_schedule")
@patch("main.deduplicate_existing_tables")
@patch("main.create_connection")
def test_main_marks_each_date_collected(
    mock_conn, mock_dedup, mock_weekly, mock_pbp, mock_mark,
):
    """Each date in the week should get its own collection log entry."""
    conn = _in_memory_conn()
    mock_conn.return_value = conn

    mock_weekly.return_value = (
        {
            "2007-10-03": [1, 2],
            "2007-10-04": [3],
        },
        None,
    )
    mock_pbp.return_value = [{"period": 1, "time": "00:00", "event": "x", "description": "x"}]

    with patch("main.datetime", _patch_datetime(datetime.date(2007, 10, 5))):
        main.main()

    marked_dates = [call_args[0][1] for call_args in mock_mark.call_args_list]
    assert "2007-10-03" in marked_dates
    assert "2007-10-04" in marked_dates
    assert len(marked_dates) == 2


@patch("main.get_play_by_play_data")
@patch("main.get_weekly_schedule")
@patch("main.deduplicate_existing_tables")
@patch("main.create_connection")
def test_main_stops_when_next_start_date_is_none(
    mock_conn, mock_dedup, mock_weekly, mock_pbp,
):
    """When the API returns no nextStartDate, the loop should end."""
    conn = _in_memory_conn()
    mock_conn.return_value = conn

    mock_weekly.return_value = ({"2007-10-03": []}, None)

    with patch("main.datetime", _patch_datetime(datetime.date(2007, 10, 10))):
        main.main()

    assert mock_weekly.call_count == 1
    mock_pbp.assert_not_called()


@patch("main.get_play_by_play_data")
@patch("main.get_weekly_schedule")
@patch("main.deduplicate_existing_tables")
@patch("main.create_connection")
def test_main_resumes_from_last_collected_date(
    mock_conn, mock_dedup, mock_weekly, mock_pbp,
):
    """When resuming, the first weekly schedule call should start after the last collected date."""
    conn = _in_memory_conn()
    mark_date_collected(conn, "2007-10-03", 2, 2)
    mock_conn.return_value = conn

    mock_weekly.return_value = (
        {
            "2007-10-04": [10],
            "2007-10-05": [11],
        },
        None,
    )
    mock_pbp.return_value = [{"period": 1, "time": "00:00", "event": "x", "description": "x"}]

    with patch("main.datetime", _patch_datetime(datetime.date(2007, 10, 6))):
        main.main()

    called_date = mock_weekly.call_args[0][0]
    assert str(called_date) == "2007-10-04"


@patch("main.get_play_by_play_data")
@patch("main.get_weekly_schedule")
@patch("main.deduplicate_existing_tables")
@patch("main.create_connection")
def test_main_resumes_from_incomplete_date(
    mock_conn, mock_dedup, mock_weekly, mock_pbp,
):
    """When an incomplete date exists, main() should resume from that date."""
    conn = _in_memory_conn()
    mark_date_collected(conn, "2007-10-03", 2, 2)  # complete
    mark_date_collected(conn, "2007-10-04", 2, 1)  # incomplete
    mark_date_collected(conn, "2007-10-05", 1, 1)  # complete
    mock_conn.return_value = conn

    mock_weekly.return_value = (
        {
            "2007-10-04": [20, 21],
            "2007-10-05": [22],
        },
        None,
    )
    mock_pbp.return_value = [{"period": 1, "time": "00:00", "event": "x", "description": "x"}]

    with patch("main.datetime", _patch_datetime(datetime.date(2007, 10, 6))):
        main.main()

    called_date = mock_weekly.call_args[0][0]
    assert str(called_date) == "2007-10-04"
