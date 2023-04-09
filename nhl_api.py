import requests
from error_handling import log_error
from bs4 import BeautifulSoup
import json

def get_defensemen(team_id):
    url = f"https://statsapi.web.nhl.com/api/v1/teams/{team_id}/roster"
    response = requests.get(url)
    data = response.json()

    defensemen = []
    for player in data["roster"]:
        if player["position"]["code"] == "D":
            defensemen.append({
                "id": player["person"]["id"],
                "name": player["person"]["fullName"]
            })

    return defensemen

def get_defenseman_stats(player_id, season):
    url = f"https://statsapi.web.nhl.com/api/v1/people/{player_id}/stats?stats=gameLog&season={season}"
    response = requests.get(url)
    data = response.json()

    total_ice_time = 0
    leading_ice_time = 0
    trailing_ice_time = 0

    for game in data["stats"][0]["splits"]:
        total_ice_time += game["timeOnIce"]
        leading_ice_time += game["evenTimeOnIce"] * game["teamStats"]["teamSkaterStats"]["leadingFaceoffWinPercentage"]
        trailing_ice_time += game["evenTimeOnIce"] * game["teamStats"]["teamSkaterStats"]["trailingFaceoffWinPercentage"]

    return {
        "total_ice_time": total_ice_time,
        "leading_ice_time": leading_ice_time,
        "trailing_ice_time": trailing_ice_time
    }

def get_team_schedule(team_id, season):
    url = f"https://statsapi.web.nhl.com/api/v1/schedule?teamId={team_id}&season={season}"
    response = requests.get(url)
    data = response.json()

    games = []
    for date in data["dates"]:
        for game in date["games"]:
            games.append({
                "game_id": game["gamePk"],
                "date": date["date"],
                "result": game["teams"]["home" if game["teams"]["home"]["team"]["id"] == team_id else "away"]["score"] >
                          game["teams"]["away" if game["teams"]["home"]["team"]["id"] == team_id else "home"]["score"]
            })

    return games

def player_played_in_game(player_id, game_id):
    url = f"https://statsapi.web.nhl.com/api/v1/game/{game_id}/boxscore"
    response = requests.get(url)
    data = response.json()

    players = data["teams"]["home"]["players"]
    players.update(data["teams"]["away"]["players"])

    return str(player_id) in players

def get_game_ids_for_date(date):
    url = f"https://statsapi.web.nhl.com/api/v1/schedule?date={date}"
    response = requests.get(url)

    if response.status_code != 200:
        error_message = f"Error fetching game data for {date}. Status code: {response.status_code}"
        print(error_message)
        log_error(error_message)
        return []

    if response.status_code == 200:
        data = json.loads(response.text)

        if data["dates"]:
            game_ids = [game["gamePk"] for game in data["dates"][0]["games"]]
            return game_ids
        else:
            print(f"No games found for date {date}")
            return []

    data = response.json()
    game_ids = [game["gamePk"] for game in data["dates"][0]["games"]]
    return game_ids

def get_play_by_play_data(game_id):
    url = f"https://statsapi.web.nhl.com/api/v1/game/{game_id}/feed/live"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        error_message = f"Error fetching play-by-play data for game {game_id}. Status code: {response.status_code}"
        print(error_message)
        log_error(error_message)
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