import requests

def get_game_ids_for_date(date):
    url = f"https://statsapi.web.nhl.com/api/v1/schedule?date={date}"
    response = requests.get(url)

    if response.status_code != 200:
        error_message = f"Error fetching game data for {date}. Status code: {response.status_code}"
        print(error_message)
        return []

    data = response.json()

    if data["dates"]:
        game_ids = [game["gamePk"] for game in data["dates"][0]["games"]]
        return game_ids
    else:
        print(f"No games found for date {date}")
        return []

def get_play_by_play_data(game_id):
    url = f"https://statsapi.web.nhl.com/api/v1/game/{game_id}/feed/live"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        error_message = f"Error fetching play-by-play data for game {game_id}. Status code: {response.status_code}"
        print(error_message)
        return None

    data_json = response.json()
    play_by_play_data = data_json.get("liveData", {}).get("plays", {}).get("allPlays", [])

    data = []
    for play in play_by_play_data:
        event = {
            "period": play.get("about", {}).get("period"),
            "time": play.get("about", {}).get("periodTime"),
            "event": play.get("result", {}).get("event"),
            "description": play.get("result", {}).get("description")
        }
        data.append(event)
    return data