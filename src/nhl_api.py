import time

import requests

_NHL_API_BASE_URL = "https://api-web.nhle.com/v1"
_GAME_API_MIN_INTERVAL = 2  # seconds between game API calls
_last_game_api_call = 0

def get_game_ids_for_date(date):
    date_str = str(date)
    url = f"{_NHL_API_BASE_URL}/schedule/{date_str}"
    response = requests.get(url)

    if response.status_code != 200:
        print(f"Error fetching game data for {date_str}. Status code: {response.status_code}")
        return []

    data = response.json()

    for week_entry in data.get("gameWeek", []):
        if week_entry["date"] == date_str:
            return [game["id"] for game in week_entry["games"]]

    print(f"No games found for date {date_str}")
    return []

def get_weekly_schedule(date):
    """Fetch a full week of schedule data in one API call.

    Returns (schedule_by_date, next_start_date) where schedule_by_date
    maps "YYYY-MM-DD" strings to lists of game IDs, and next_start_date
    is the date string for the next week (or None if unavailable).
    """
    date_str = str(date)
    url = f"{_NHL_API_BASE_URL}/schedule/{date_str}"
    response = requests.get(url)

    if response.status_code != 200:
        print(f"Error fetching schedule for {date_str}. Status code: {response.status_code}")
        return {}, None

    data = response.json()
    game_week = data.get("gameWeek", [])

    if not game_week:
        return {}, None

    schedule = {}
    for week_entry in game_week:
        schedule[week_entry["date"]] = [game["id"] for game in week_entry["games"]]

    next_start_date = data.get("nextStartDate")
    return schedule, next_start_date

def get_play_by_play_data(game_id):
    global _last_game_api_call
    elapsed = time.monotonic() - _last_game_api_call
    if elapsed < _GAME_API_MIN_INTERVAL:
        wait = _GAME_API_MIN_INTERVAL - elapsed
        print(f"Rate limiting: waiting {wait:.1f}s before next game API call")
        time.sleep(wait)

    url = f"{_NHL_API_BASE_URL}/gamecenter/{game_id}/play-by-play"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    _last_game_api_call = time.monotonic()

    if response.status_code != 200:
        print(f"Error fetching play-by-play data for game {game_id}. Status code: {response.status_code}")
        return None

    data_json = response.json()
    play_by_play_data = data_json.get("plays", [])

    data = []
    for play in play_by_play_data:
        event_type = play.get("typeDescKey")
        event = {
            "period": play.get("periodDescriptor", {}).get("number"),
            "time": play.get("timeInPeriod"),
            "event": event_type,
            "description": event_type,
        }
        data.append(event)
    return data
