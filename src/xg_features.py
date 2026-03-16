"""Pure feature-extraction functions for xG modeling.

Takes NHL API JSON dicts, returns plain dicts. No DB or HTTP.
"""

import math

from database import VALID_MANPOWER_STATES

SHOT_EVENT_TYPE_KEYS = ("shot-on-goal", "goal", "missed-shot", "blocked-shot")
FACEOFF_EVENT_TYPE_KEY = "faceoff"
GOAL_X_COORD = 89.0
GOAL_Y_COORD = 0.0
_REGULATION_PERIOD_LENGTH_SECONDS = 1200
_SITUATION_CODE_LENGTH = 4


def parse_time_remaining(time_str):
    """Parse "MM:SS" string into integer seconds. Returns 0 on failure."""
    if time_str is None:
        return 0
    try:
        parts = time_str.split(":")
        if len(parts) != 2:
            return 0
        return int(parts[0]) * 60 + int(parts[1])
    except (ValueError, AttributeError):
        return 0


def parse_situation_code(code, shooting_team_id, home_team_id):
    """Parse 4-digit situation code into skater counts for shooting/opposing teams.

    Code format: [away_goalie][away_skaters][home_skaters][home_goalie]
    Returns dict with shooting_skaters and opposing_skaters, or None on failure.
    """
    if code is None:
        return None
    code_str = str(code)
    if len(code_str) != _SITUATION_CODE_LENGTH:
        return None
    try:
        away_skaters = int(code_str[1])
        home_skaters = int(code_str[2])
    except (ValueError, IndexError):
        return None

    if shooting_team_id == home_team_id:
        return {"shooting_skaters": home_skaters, "opposing_skaters": away_skaters}
    return {"shooting_skaters": away_skaters, "opposing_skaters": home_skaters}


def classify_manpower_state(shooting, opposing):
    """Classify skater counts into a manpower state string.

    Returns a string like "5v5" or None if the combination is not recognized.
    """
    state = f"{shooting}v{opposing}"
    if state in VALID_MANPOWER_STATES:
        return state
    return None


def classify_score_state(shooting_score, opposing_score):
    """Classify score differential into a score state string."""
    diff = shooting_score - opposing_score
    if diff == 0:
        return "tied"
    if diff == 1:
        return "up1"
    if diff == 2:
        return "up2"
    if diff >= 3:
        return "up3plus"
    if diff == -1:
        return "down1"
    if diff == -2:
        return "down2"
    return "down3plus"


def normalize_coordinates(x, y, shooting_team_id, home_team_id, defending_side):
    """Normalize coordinates so shooting team attacks toward +x.

    Home defends left -> home attacks right (+x), away attacks left (-x).
    Home defends right -> home attacks left (-x), away attacks right (+x).
    If defending_side is missing, returns raw coordinates.
    """
    if defending_side is None:
        return (x, y)

    home_attacks_positive = (defending_side == "left")
    shooting_is_home = (shooting_team_id == home_team_id)

    if shooting_is_home:
        attacks_positive = home_attacks_positive
    else:
        attacks_positive = not home_attacks_positive

    if not attacks_positive:
        return (-x, -y)
    return (x, y)


def compute_distance_to_goal(x, y):
    """Compute distance from (x, y) to the goal at (GOAL_X_COORD, GOAL_Y_COORD)."""
    return math.sqrt((x - GOAL_X_COORD) ** 2 + (y - GOAL_Y_COORD) ** 2)


def compute_angle_to_goal(x, y):
    """Compute angle in degrees from the shot location to the goal.

    0 = directly in front, 90 = along the goal line, >90 = behind the net.
    """
    return math.degrees(math.atan2(abs(y), GOAL_X_COORD - x))


def _track_score(plays, home_team_id, away_team_id):
    """Build parallel list of (home_score, away_score) reflecting pre-event scores.

    Goal events' details contain post-goal scores which update the running tally
    for subsequent events. A goal's own entry reflects the pre-goal score.
    """
    scores = []
    home_score = 0
    away_score = 0

    for play in plays:
        scores.append((home_score, away_score))
        if play.get("typeDescKey") == "goal":
            details = play.get("details", {})
            new_home = details.get("homeScore")
            new_away = details.get("awayScore")
            if new_home is not None:
                home_score = new_home
            if new_away is not None:
                away_score = new_away

    return scores


def extract_shot_events(game_data):
    """Extract shot events from full NHL API game JSON.

    Returns list of dicts matching shot_events table columns
    (excluding shot_event_id and event_schema_version).
    """
    plays = game_data.get("plays", [])
    if not plays:
        return []

    home_team_id = game_data.get("homeTeam", {}).get("id")
    away_team_id = game_data.get("awayTeam", {}).get("id")
    game_id = game_data.get("id")

    scores = _track_score(plays, home_team_id, away_team_id)

    # Track last faceoff per period: {period: (elapsed_seconds, zone_code)}
    last_faceoff = {}

    shot_events = []

    for idx, play in enumerate(plays):
        type_key = play.get("typeDescKey")
        period = play.get("periodDescriptor", {}).get("number")
        time_in_period = play.get("timeInPeriod")
        details = play.get("details", {})

        # Track faceoffs
        if type_key == FACEOFF_EVENT_TYPE_KEY and period is not None:
            fo_elapsed = parse_time_remaining(time_in_period)
            last_faceoff[period] = (fo_elapsed, details.get("zoneCode"))

        if type_key not in SHOT_EVENT_TYPE_KEYS:
            continue

        shooting_team_id = details.get("eventOwnerTeamId")

        if type_key == "goal":
            shooter_id = details.get("scoringPlayerId")
        else:
            shooter_id = details.get("shootingPlayerId")

        goalie_id = details.get("goalieInNetId")
        shot_type = details.get("shotType")
        is_goal = 1 if type_key == "goal" else 0

        x_raw = details.get("xCoord")
        y_raw = details.get("yCoord")
        defending_side = play.get("homeTeamDefendingSide")

        if x_raw is not None and y_raw is not None:
            x_norm, y_norm = normalize_coordinates(
                x_raw, y_raw, shooting_team_id, home_team_id, defending_side
            )
            distance = compute_distance_to_goal(x_norm, y_norm)
            angle = compute_angle_to_goal(x_norm, y_norm)
        else:
            x_norm, y_norm = None, None
            distance = None
            angle = None

        # Time remaining
        time_remaining_str = play.get("timeRemaining")
        time_remaining_seconds = parse_time_remaining(time_remaining_str)

        # Score state (pre-event)
        home_score, away_score = scores[idx]
        if shooting_team_id == home_team_id:
            shooting_score = home_score
            opposing_score = away_score
        else:
            shooting_score = away_score
            opposing_score = home_score
        score_state = classify_score_state(shooting_score, opposing_score)

        # Manpower state
        situation_code = play.get("situationCode")
        if situation_code is not None and shooting_team_id is not None:
            parsed = parse_situation_code(
                situation_code, shooting_team_id, home_team_id
            )
            if parsed is not None:
                manpower_state = classify_manpower_state(
                    parsed["shooting_skaters"], parsed["opposing_skaters"]
                )
            else:
                manpower_state = None
        else:
            manpower_state = None

        # Faceoff context
        elapsed_seconds = parse_time_remaining(time_in_period)
        fo_data = last_faceoff.get(period)
        if fo_data is not None:
            fo_elapsed, faceoff_zone = fo_data
            seconds_since_faceoff = elapsed_seconds - fo_elapsed
        else:
            seconds_since_faceoff = None
            faceoff_zone = None

        event_id = play.get("eventId")

        shot_events.append({
            "game_id": game_id,
            "event_idx": event_id,
            "period": period,
            "time_in_period": time_in_period,
            "time_remaining_seconds": time_remaining_seconds,
            "shot_type": shot_type,
            "x_coord": x_norm,
            "y_coord": y_norm,
            "distance_to_goal": distance,
            "angle_to_goal": angle,
            "is_goal": is_goal,
            "shooting_team_id": shooting_team_id,
            "goalie_id": goalie_id,
            "shooter_id": shooter_id,
            "score_state": score_state,
            "manpower_state": manpower_state,
            "seconds_since_faceoff": seconds_since_faceoff,
            "faceoff_zone_code": faceoff_zone,
        })

    return shot_events
