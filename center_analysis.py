import sqlite3
from collections import defaultdict

def get_even_strength_faceoffs(database, game_id):
    conn = sqlite3.connect(database)
    cursor = conn.cursor()

    query = f"""
    SELECT player_id, time
    FROM {game_id}
    WHERE event = 'Faceoff' AND strength = 'Even'
    """
    cursor.execute(query)
    faceoffs = cursor.fetchall()

    conn.close()
    return faceoffs

def calculate_faceoffs_per_minute(faceoffs):
    faceoff_counts = defaultdict(int)
    total_time = 0

    for player_id, time in faceoffs:
        faceoff_counts[player_id] += 1
        total_time += time

    faceoffs_per_minute = {player_id: count / (total_time / 60) for player_id, count in faceoff_counts.items()}
    return faceoffs_per_minute

def get_teammates_faceoffs(database, game_id):
    conn = sqlite3.connect(database)
    cursor = conn.cursor()

    query = f"""
    SELECT winner, loser
    FROM {game_id}
    WHERE event = 'Faceoff' AND strength = 'Even'
    """
    cursor.execute(query)
    faceoff_outcomes = cursor.fetchall()

    teammate_faceoffs = []

    for winner, loser in faceoff_outcomes:
        if winner // 1000000 == loser // 1000000:  # Check if the players belong to the same team
            teammate_faceoffs.append((winner, loser))

    conn.close()
    return teammate_faceoffs

def update_elo_ratings(database, game_id, elo_ratings, min_faceoffs=10):
    faceoff_counts = defaultdict(int)
    teammate_faceoffs = get_teammates_faceoffs(database, game_id)

    for winner, loser in teammate_faceoffs:
        faceoff_counts[winner] += 1
        faceoff_counts[loser] += 1

    significant_players = [player_id for player_id, count in faceoff_counts.items() if count >= min_faceoffs]

    if len(significant_players) <= 4:
        return elo_ratings

    for winner, loser in teammate_faceoffs:
        if winner in significant_players and loser in significant_players:
            winner_elo, loser_elo = elo_ratings[winner], elo_ratings[loser]
            new_winner_elo, new_loser_elo = calculate_elo_change(winner_elo, loser_elo)
            elo_ratings[winner], elo_ratings[loser] = new_winner_elo, new_loser_elo

    return elo_ratings

def calculate_elo_change(winner_elo, loser_elo, k=32):
    prob_winner_wins = 1 / (1 + 10 ** ((loser_elo - winner_elo) / 400))

    new_winner_elo = winner_elo + k * (1 - prob_winner_wins)
    new_loser_elo = loser_elo + k * (0 - (1 - prob_winner_wins))

    return new_winner_elo, new_loser_elo

