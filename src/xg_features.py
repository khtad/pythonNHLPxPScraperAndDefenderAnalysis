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

# ── Phase 2, Area 3: faceoff recency constants ──────────────────────
# Bin boundaries: (upper_bound_exclusive, label)
# Evaluated in order; first match wins.
_FACEOFF_RECENCY_BINS = (
    (6, "immediate"),    # 0-5s
    (16, "early"),       # 6-15s
    (31, "mid"),         # 16-30s
    (61, "late"),        # 31-60s
)
_FACEOFF_RECENCY_STEADY_STATE = "steady_state"  # 61+s
_POST_FACEOFF_WINDOW_SECONDS = 10

_EARTH_RADIUS_KM = 6371.0


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
    If defending_side is missing, infers attacking direction from the shot's
    x-coordinate: negative x implies the team is shooting toward the -x goal,
    so we flip to keep the convention that shots attack toward +x (GOAL_X_COORD).
    """
    if defending_side is None:
        if x < 0:
            return (-x, -y)
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


# ── Phase 2, Area 3: faceoff recency features ───────────────────────


def classify_faceoff_recency(seconds_since_faceoff):
    """Classify seconds since faceoff into a recency bin.

    Returns one of: "immediate" (0-5s), "early" (6-15s), "mid" (16-30s),
    "late" (31-60s), "steady_state" (61+s), or None for invalid input.
    """
    if seconds_since_faceoff is None or seconds_since_faceoff < 0:
        return None
    for upper_bound, label in _FACEOFF_RECENCY_BINS:
        if seconds_since_faceoff < upper_bound:
            return label
    return _FACEOFF_RECENCY_STEADY_STATE


def faceoff_zone_recency_interaction(zone_code, recency_bin):
    """Create a zone-recency interaction feature string.

    Returns e.g. "O_immediate" or None if either input is None.
    """
    if zone_code is None or recency_bin is None:
        return None
    return f"{zone_code}_{recency_bin}"


def is_post_faceoff_window(seconds_since_faceoff,
                           window_seconds=_POST_FACEOFF_WINDOW_SECONDS):
    """Return 1 if within the post-faceoff window, 0 otherwise, None if unknown."""
    if seconds_since_faceoff is None or seconds_since_faceoff < 0:
        return None
    return 1 if seconds_since_faceoff <= window_seconds else 0


# ── Phase 2: game metadata extraction ───────────────────────────────


def extract_game_metadata(game_data):
    """Extract game-level metadata from NHL API game JSON.

    Returns a dict with game_id, game_date, season, home/away team info,
    and venue metadata, or None if game_id is missing.
    """
    game_id = game_data.get("id")
    if game_id is None:
        return None

    home_team = game_data.get("homeTeam", {})
    away_team = game_data.get("awayTeam", {})

    return {
        "game_id": game_id,
        "game_date": game_data.get("gameDate"),
        "season": game_data.get("season"),
        "home_team_id": home_team.get("id"),
        "home_team_abbrev": home_team.get("abbrev"),
        "home_team_name": home_team.get("placeName", {}).get("default")
                          if isinstance(home_team.get("placeName"), dict)
                          else home_team.get("placeName"),
        "away_team_id": away_team.get("id"),
        "away_team_abbrev": away_team.get("abbrev"),
        "away_team_name": away_team.get("placeName", {}).get("default")
                          if isinstance(away_team.get("placeName"), dict)
                          else away_team.get("placeName"),
        "venue_name": game_data.get("venue", {}).get("default")
                      if isinstance(game_data.get("venue"), dict)
                      else game_data.get("venue"),
        "venue_city": game_data.get("venueLocation", {}).get("default")
                      if isinstance(game_data.get("venueLocation"), dict)
                      else game_data.get("venueLocation"),
        "venue_utc_offset": game_data.get("venueUTCOffset"),
    }


# ── Phase 2, Area 1: rest/travel computation ────────────────────────


def compute_rest_days(game_date_str, prev_game_date_str):
    """Compute rest days between two ISO date strings.

    Returns integer days between games, or None if either date is None.
    """
    if game_date_str is None or prev_game_date_str is None:
        return None
    from datetime import date as _date
    current = _date.fromisoformat(game_date_str)
    previous = _date.fromisoformat(prev_game_date_str)
    return (current - previous).days


def is_back_to_back(rest_days):
    """Return 1 if rest_days indicates a back-to-back (1 day), 0 otherwise, None if unknown."""
    if rest_days is None:
        return None
    return 1 if rest_days == 1 else 0


def haversine_distance(lat1, lon1, lat2, lon2):
    """Compute great-circle distance in km between two lat/lon points."""
    lat1_r, lon1_r = math.radians(lat1), math.radians(lon1)
    lat2_r, lon2_r = math.radians(lat2), math.radians(lon2)

    dlat = lat2_r - lat1_r
    dlon = lon2_r - lon1_r

    a = math.sin(dlat / 2) ** 2 + (
        math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.asin(math.sqrt(a))

    return _EARTH_RADIUS_KM * c


def compute_timezone_delta(away_utc_offset, home_utc_offset):
    """Compute timezone delta in hours (home - away).

    Positive means the away team is traveling east (later timezone).
    Returns None if either offset is None.
    """
    if away_utc_offset is None or home_utc_offset is None:
        return None
    return home_utc_offset - away_utc_offset
