import time

import requests

_last_game_api_call = 0
_GAME_API_MIN_INTERVAL = 15  # seconds between game API calls

def get_game_ids_for_date(date):
    date_str = str(date)
    url = f"https://api-web.nhle.com/v1/schedule/{date_str}"
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

def get_play_by_play_data(game_id):
    global _last_game_api_call
    elapsed = time.monotonic() - _last_game_api_call
    if elapsed < _GAME_API_MIN_INTERVAL:
        wait = _GAME_API_MIN_INTERVAL - elapsed
        print(f"Rate limiting: waiting {wait:.1f}s before next game API call")
        time.sleep(wait)

    url = f"https://api-web.nhle.com/v1/gamecenter/{game_id}/play-by-play"
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
