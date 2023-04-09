import pandas as pd
from nhl_api import player_played_in_game, get_team_schedule
import sqlite3
from sqlite3 import Error

def get_game_data(database, game_id):
    conn = None
    game_data = []

    try:
        conn = sqlite3.connect(database)
    except Error as e:
        print(e)

    if conn is not None:
        cursor = conn.cursor()
        select_query = f"SELECT * FROM {game_id}"

        try:
            cursor.execute(select_query)
            rows = cursor.fetchall()
            column_names = [description[0] for description in cursor.description]

            for row in rows:
                event_data = {column_names[i]: value for i, value in enumerate(row)}
                game_data.append(event_data)

        except Error as e:
            print(e)

        conn.close()

    return game_data

def calculate_score(defenseman, weight_total_ice_time=1, weight_leading_ice_time=0.5, weight_trailing_ice_time=0.5):
    total_ice_time = defenseman["total_ice_time"]
    leading_ice_time = defenseman["leading_ice_time"]
    trailing_ice_time = defenseman["trailing_ice_time"]

    score = (total_ice_time * weight_total_ice_time +
             leading_ice_time * weight_leading_ice_time +
             trailing_ice_time * weight_trailing_ice_time)

    return score

def team_performance(conn, team_id, game_ids, top_defenseman):
    games_with_top_defenseman = 0
    games_without_top_defenseman = 0
    goals_for_with = 0
    goals_against_with = 0
    goals_for_without = 0
    goals_against_without = 0

    # Add new variables to store the new statistics
    unblocked_shots_for_with = 0
    unblocked_shots_for_without = 0
    saves_all_strengths_with = 0
    saves_all_strengths_without = 0
    saves_even_strength_with = 0
    saves_even_strength_without = 0
    saves_penalty_kill_with = 0
    saves_penalty_kill_without = 0

    for game_id in game_ids:
        # Get data for the game
        game_data = get_game_data(conn, game_id)
        team_data = get_team_data(game_data, team_id)

        # Check if the top defenseman is in the lineup
        top_defenseman_in_lineup = top_defenseman in team_data["players"]

        # Update the respective statistics based on the defenseman's presence
        if top_defenseman_in_lineup:
            games_with_top_defenseman += 1
            goals_for_with += team_data["goals_for"]
            goals_against_with += team_data["goals_against"]

            # Update the new statistics
            unblocked_shots_for_with += team_data["unblocked_shots_for"]
            saves_all_strengths_with += team_data["saves_all_strengths"]
            saves_even_strength_with += team_data["saves_even_strength"]
            saves_penalty_kill_with += team_data["saves_penalty_kill"]

        else:
            games_without_top_defenseman += 1
            goals_for_without += team_data["goals_for"]
            goals_against_without += team_data["goals_against"]

            # Update the new statistics
            unblocked_shots_for_without += team_data["unblocked_shots_for"]
            saves_all_strengths_without += team_data["saves_all_strengths"]
            saves_even_strength_without += team_data["saves_even_strength"]
            saves_penalty_kill_without += team_data["saves_penalty_kill"]

    # Calculate the shooting percentage for unblocked shots with and without the top defenseman
    shooting_percentage_with = unblocked_shots_for_with / goals_for_with
    shooting_percentage_without = unblocked_shots_for_without / goals_for_without

    # Calculate the save percentages for different situations with and without the top defenseman
    save_percentage_all_strengths_with = saves_all_strengths_with / (saves_all_strengths_with + goals_against_with)
    save_percentage_all_strengths_without = saves_all_strengths_without / (saves_all_strengths_without + goals_against_without)
    save_percentage_even_strength_with = saves_even_strength_with / (saves_even_strength_with + goals_against_with)
    save_percentage_even_strength_without = saves_even_strength_without / (saves_even_strength_without + goals_against_without)
    save_percentage_penalty_kill_with = saves_penalty_kill_with / (saves_penalty_kill_with + goals_against_with)
    save_percentage_penalty_kill_without = saves_penalty_kill_without / (saves_penalty_kill_without + goals_against_without)

    # Calculate marginal goals scored and conceded per game while missing their best defender
    marginal_goals_scored = (goals_for_without / games_without_top_defenseman) - (goals_for_with / games_with_top_defenseman)
    marginal_goals_conceded = (goals_against_without / games_without_top_defenseman) - (goals_against_with / games_with_top_defenseman)

    # Return the performance summary
    performance_summary = {
        "games_with_top_defenseman": games_with_top_defenseman,
        "games_without_top_defenseman": games_without_top_defenseman,
        "goals_for_with": goals_for_with,
        "goals_against_with": goals_against_with,
        "goals_for_without": goals_for_without,
        "goals_against_without": goals_against_without,
        "shooting_percentage_with": shooting_percentage_with,
        "shooting_percentage_without": shooting_percentage_without,
        "save_percentage_all_strengths_with": save_percentage_all_strengths_with,
        "save_percentage_all_strengths_without": save_percentage_all_strengths_without,
        "save_percentage_even_strength_with": save_percentage_even_strength_with,
        "save_percentage_even_strength_without": save_percentage_even_strength_without,
        "save_percentage_penalty_kill_with": save_percentage_penalty_kill_with,
        "save_percentage_penalty_kill_without": save_percentage_penalty_kill_without,
        "marginal_goals_scored": marginal_goals_scored,
        "marginal_goals_conceded": marginal_goals_conceded,
    }

    return performance_summary

def get_team_data(game_data, team_id):
    goals_for = 0
    goals_against = 0

    for event in game_data:
        if event["event"] == "GOAL":
            if event["description"].find(f"for {team_id}") != -1:
                goals_for += 1
            elif event["description"].find(f"against {team_id}") != -1:
                goals_against += 1

    unblocked_shots_against_count = unblocked_shots_against(game_data, team_id)
    unblocked_shots_for_count = unblocked_shots_for(game_data, team_id)

    team_data = {
        "team_id": team_id,
        "goals_for": goals_for,
        "goals_against": goals_against,
        "unblocked_shots_against": unblocked_shots_against_count,
        "unblocked_shots_for": unblocked_shots_for_count,
    }

    return team_data

def unblocked_shots_against(game_data, team_id):
    unblocked_shots = 0

    for event in game_data:
        if event["event"] in ("SHOT", "MISS", "GOAL"):
            # Check if the event is against the specified team
            if event["description"].find(f"against {team_id}") != -1:
                unblocked_shots += 1

    return unblocked_shots

def unblocked_shots_for(game_data, team_id):
    unblocked_shots = 0

    for event in game_data:
        if event["event"] in ("SHOT", "MISS", "GOAL"):
            # Check if the event is for the specified team
            if event["description"].find(f"for {team_id}") != -1:
                unblocked_shots += 1

    return unblocked_shots