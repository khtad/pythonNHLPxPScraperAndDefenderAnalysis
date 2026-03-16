import time

import requests

_NHL_API_BASE_URL = "https://api-web.nhle.com/v1"
_GAME_API_MIN_INTERVAL = 2  # seconds between game API calls
_USER_AGENT = "Mozilla/5.0"
_last_game_api_call = 0

_session = requests.Session()
_session.headers.update({"User-Agent": _USER_AGENT})


def _api_get(url):
    """Perform a GET request and return parsed JSON, or None on non-200."""
    response = _session.get(url)
    if response.status_code != 200:
        print(f"Error fetching {url}. Status code: {response.status_code}")
        return None
    return response.json()


def get_game_ids_for_date(date):
    schedule, _ = get_weekly_schedule(date)
    return schedule.get(str(date), [])


def get_weekly_schedule(date):
    """Fetch a full week of schedule data in one API call.

    Returns (schedule_by_date, next_start_date) where schedule_by_date
    maps "YYYY-MM-DD" strings to lists of game IDs, and next_start_date
    is the date string for the next week (or None if unavailable).
    """
    date_str = str(date)
    url = f"{_NHL_API_BASE_URL}/schedule/{date_str}"
    data = _api_get(url)

    if data is None:
        return {}, None

    game_week = data.get("gameWeek", [])

    if not game_week:
        return {}, None

    schedule = {
        entry["date"]: [game["id"] for game in entry["games"]]
        for entry in game_week
    }

    next_start_date = data.get("nextStartDate")
    return schedule, next_start_date


def _rate_limited_game_api_get(game_id):
    """Rate-limited GET for a game play-by-play endpoint. Returns parsed JSON or None."""
    global _last_game_api_call
    elapsed = time.monotonic() - _last_game_api_call
    if elapsed < _GAME_API_MIN_INTERVAL:
        wait = _GAME_API_MIN_INTERVAL - elapsed
        print(f"Rate limiting: waiting {wait:.1f}s before next game API call")
        time.sleep(wait)

    url = f"{_NHL_API_BASE_URL}/gamecenter/{game_id}/play-by-play"
    data = _api_get(url)
    _last_game_api_call = time.monotonic()
    return data


def get_full_play_by_play(game_id):
    """Fetch complete play-by-play JSON for a game, or None on failure."""
    return _rate_limited_game_api_get(game_id)


def get_play_by_play_data(game_id):
    data = get_full_play_by_play(game_id)

    if data is None:
        return None

    return [
        {
            "period": play.get("periodDescriptor", {}).get("number"),
            "time": play.get("timeInPeriod"),
            "event": play.get("typeDescKey"),
            "description": play.get("typeDescKey"),
        }
        for play in data.get("plays", [])
    ]
