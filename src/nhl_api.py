import time

import requests

from database import PlayerMetadataNotFound

_NHL_API_BASE_URL = "https://api-web.nhle.com/v1"
_GAME_API_MIN_INTERVAL = 2  # seconds between game API calls
_USER_AGENT = "Mozilla/5.0"
_HTTP_OK = 200
_HTTP_NOT_FOUND = 404
_last_game_api_call = 0

_session = requests.Session()
_session.headers.update({"User-Agent": _USER_AGENT})


def _api_get_with_status(url, silent_status_codes=()):
    """Perform a GET request. Returns (parsed_json_or_None, status_code).

    Prints an error for non-200 codes unless the code appears in
    silent_status_codes — used for endpoints where certain responses are
    expected and routine (e.g., 404 for pre-modern player ids on the
    landing endpoint).
    """
    response = _session.get(url)
    if response.status_code != _HTTP_OK:
        if response.status_code not in silent_status_codes:
            print(f"Error fetching {url}. Status code: {response.status_code}")
        return None, response.status_code
    return response.json(), _HTTP_OK


def _api_get(url):
    """Perform a GET request and return parsed JSON, or None on non-200."""
    data, _ = _api_get_with_status(url)
    return data


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


_PLAYER_LANDING_DEFAULT_LOCALE = "default"


def _localized_name(value):
    """Return the default-locale string from an NHL API localized-name field."""
    if isinstance(value, dict):
        return value.get(_PLAYER_LANDING_DEFAULT_LOCALE)
    return value


def _parse_player_landing(data, player_id):
    """Shape a /player/{id}/landing response into a players-table row dict.

    Returns None if the payload is missing the identifier.
    """
    if data is None:
        return None

    resolved_id = data.get("playerId", player_id)
    if resolved_id is None:
        return None

    return {
        "player_id": resolved_id,
        "first_name": _localized_name(data.get("firstName")),
        "last_name": _localized_name(data.get("lastName")),
        "shoots_catches": data.get("shootsCatches"),
        "position": data.get("position"),
        "team_id": data.get("currentTeamId"),
    }


def get_player_metadata(player_id):
    """Fetch a player's landing-endpoint metadata.

    Returns a dict shaped for `_PLAYERS_INSERT_COLUMNS` on success, or None
    on a transient non-404 failure that should be retried later. Raises
    `PlayerMetadataNotFound` on 404 — historical (pre-modern) player ids
    are not indexed by this endpoint, and the 404 is expected routine
    traffic that the backfill caches via `mark_players_metadata_unavailable`
    instead of re-fetching on every run.
    """
    url = f"{_NHL_API_BASE_URL}/player/{player_id}/landing"
    data, status = _api_get_with_status(url, silent_status_codes=(_HTTP_NOT_FOUND,))
    if status == _HTTP_NOT_FOUND:
        raise PlayerMetadataNotFound(player_id)
    return _parse_player_landing(data, player_id)
