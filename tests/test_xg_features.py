import math

import pytest

from xg_features import (
    SHOT_EVENT_TYPE_KEYS,
    FACEOFF_EVENT_TYPE_KEY,
    GOAL_X_COORD,
    GOAL_Y_COORD,
    _REGULATION_PERIOD_LENGTH_SECONDS,
    _SITUATION_CODE_LENGTH,
    _FACEOFF_RECENCY_BINS,
    _FACEOFF_RECENCY_STEADY_STATE,
    _POST_FACEOFF_WINDOW_SECONDS,
    _EARTH_RADIUS_KM,
    parse_time_remaining,
    parse_situation_code,
    classify_manpower_state,
    classify_score_state,
    normalize_coordinates,
    compute_distance_to_goal,
    compute_angle_to_goal,
    extract_shot_events,
    _track_score,
    classify_faceoff_recency,
    faceoff_zone_recency_interaction,
    is_post_faceoff_window,
    extract_game_metadata,
    compute_rest_days,
    is_back_to_back,
    haversine_distance,
    compute_timezone_delta,
)


# ── Constants ──────────────────────────────────────────────────────────


def test_shot_event_type_keys_contains_expected_types():
    assert "shot-on-goal" in SHOT_EVENT_TYPE_KEYS
    assert "goal" in SHOT_EVENT_TYPE_KEYS
    assert "missed-shot" in SHOT_EVENT_TYPE_KEYS
    assert "blocked-shot" in SHOT_EVENT_TYPE_KEYS


def test_faceoff_event_type_key():
    assert FACEOFF_EVENT_TYPE_KEY == "faceoff"


def test_goal_coordinates():
    assert GOAL_X_COORD == 89.0
    assert GOAL_Y_COORD == 0.0


def test_regulation_period_length():
    assert _REGULATION_PERIOD_LENGTH_SECONDS == 1200


def test_situation_code_length():
    assert _SITUATION_CODE_LENGTH == 4


# ── parse_time_remaining ──────────────────────────────────────────────


def test_parse_time_remaining_normal():
    assert parse_time_remaining("19:52") == 1192


def test_parse_time_remaining_zero():
    assert parse_time_remaining("00:00") == 0


def test_parse_time_remaining_full_period():
    assert parse_time_remaining("20:00") == 1200


def test_parse_time_remaining_none():
    assert parse_time_remaining(None) == 0


def test_parse_time_remaining_malformed():
    assert parse_time_remaining("invalid") == 0


def test_parse_time_remaining_extra_colons():
    assert parse_time_remaining("1:2:3") == 0


# ── parse_situation_code ──────────────────────────────────────────────


def test_parse_situation_code_even_strength_home():
    result = parse_situation_code("1551", shooting_team_id=10, home_team_id=10)
    assert result == {"shooting_skaters": 5, "opposing_skaters": 5}


def test_parse_situation_code_even_strength_away():
    result = parse_situation_code("1551", shooting_team_id=20, home_team_id=10)
    assert result == {"shooting_skaters": 5, "opposing_skaters": 5}


def test_parse_situation_code_short_handed():
    # home has 4, away has 5
    result = parse_situation_code("1541", shooting_team_id=10, home_team_id=10)
    assert result == {"shooting_skaters": 4, "opposing_skaters": 5}


def test_parse_situation_code_power_play_away():
    result = parse_situation_code("1541", shooting_team_id=20, home_team_id=10)
    assert result == {"shooting_skaters": 5, "opposing_skaters": 4}


def test_parse_situation_code_pulled_goalie():
    # away_goalie=0, away_skaters=6, home_skaters=5, home_goalie=1
    result = parse_situation_code("0651", shooting_team_id=20, home_team_id=10)
    assert result == {"shooting_skaters": 6, "opposing_skaters": 5}


def test_parse_situation_code_none():
    assert parse_situation_code(None, 10, 10) is None


def test_parse_situation_code_wrong_length():
    assert parse_situation_code("155", 10, 10) is None
    assert parse_situation_code("15510", 10, 10) is None


# ── classify_manpower_state ───────────────────────────────────────────


def test_classify_manpower_state_5v5():
    assert classify_manpower_state(5, 5) == "5v5"


def test_classify_manpower_state_5v4():
    assert classify_manpower_state(5, 4) == "5v4"


def test_classify_manpower_state_4v5():
    assert classify_manpower_state(4, 5) == "4v5"


def test_classify_manpower_state_6v5():
    assert classify_manpower_state(6, 5) == "6v5"


def test_classify_manpower_state_3v3():
    assert classify_manpower_state(3, 3) == "3v3"


def test_classify_manpower_state_invalid():
    assert classify_manpower_state(7, 5) is None


def test_classify_manpower_state_invalid_zero():
    assert classify_manpower_state(0, 0) is None


# ── classify_score_state ──────────────────────────────────────────────


def test_classify_score_state_tied():
    assert classify_score_state(2, 2) == "tied"


def test_classify_score_state_tied_zero():
    assert classify_score_state(0, 0) == "tied"


def test_classify_score_state_up1():
    assert classify_score_state(3, 2) == "up1"


def test_classify_score_state_up2():
    assert classify_score_state(4, 2) == "up2"


def test_classify_score_state_up3plus():
    assert classify_score_state(5, 2) == "up3plus"


def test_classify_score_state_up3plus_large():
    assert classify_score_state(10, 1) == "up3plus"


def test_classify_score_state_down1():
    assert classify_score_state(2, 3) == "down1"


def test_classify_score_state_down2():
    assert classify_score_state(2, 4) == "down2"


def test_classify_score_state_down3plus():
    assert classify_score_state(1, 5) == "down3plus"


# ── normalize_coordinates ─────────────────────────────────────────────


def test_normalize_coords_home_defends_left_home_shoots():
    # Home defends left -> home attacks right (+x) -> no flip
    x, y = normalize_coordinates(70, 10, shooting_team_id=10, home_team_id=10,
                                 defending_side="left")
    assert (x, y) == (70, 10)


def test_normalize_coords_home_defends_left_away_shoots():
    # Home defends left -> away attacks left (-x) -> flip
    x, y = normalize_coordinates(70, 10, shooting_team_id=20, home_team_id=10,
                                 defending_side="left")
    assert (x, y) == (-70, -10)


def test_normalize_coords_home_defends_right_home_shoots():
    # Home defends right -> home attacks left (-x) -> flip
    x, y = normalize_coordinates(70, 10, shooting_team_id=10, home_team_id=10,
                                 defending_side="right")
    assert (x, y) == (-70, -10)


def test_normalize_coords_home_defends_right_away_shoots():
    # Home defends right -> away attacks right (+x) -> no flip
    x, y = normalize_coordinates(70, 10, shooting_team_id=20, home_team_id=10,
                                 defending_side="right")
    assert (x, y) == (70, 10)


def test_normalize_coords_missing_defending_side_positive_x():
    # Shot already in positive-x half → no flip needed
    x, y = normalize_coordinates(70, 10, shooting_team_id=10, home_team_id=10,
                                 defending_side=None)
    assert (x, y) == (70, 10)


def test_normalize_coords_missing_defending_side_negative_x():
    # Shot in negative-x half → flip so distance-to-goal uses correct end
    x, y = normalize_coordinates(-70, 10, shooting_team_id=10, home_team_id=10,
                                 defending_side=None)
    assert (x, y) == (70, -10)


def test_normalize_coords_missing_defending_side_zero_x():
    # Shot at center ice → no flip (x=0 is not < 0)
    x, y = normalize_coordinates(0, 5, shooting_team_id=10, home_team_id=10,
                                 defending_side=None)
    assert (x, y) == (0, 5)


# ── compute_distance_to_goal ──────────────────────────────────────────


def test_compute_distance_at_goal():
    assert compute_distance_to_goal(GOAL_X_COORD, GOAL_Y_COORD) == 0.0


def test_compute_distance_straight_on():
    # (50, 0) -> sqrt((50-89)^2 + 0) = 39.0
    assert abs(compute_distance_to_goal(50, 0) - 39.0) < 0.01


def test_compute_distance_angled():
    # (69, 20) -> sqrt(20^2 + 20^2) = sqrt(800)
    expected = math.sqrt(800)
    assert abs(compute_distance_to_goal(69, 20) - expected) < 0.01


def test_compute_distance_behind_net():
    # (95, 0) -> sqrt((95-89)^2) = 6.0
    assert abs(compute_distance_to_goal(95, 0) - 6.0) < 0.01


# ── compute_angle_to_goal ─────────────────────────────────────────────


def test_compute_angle_center():
    # (0, 0) -> atan2(0, 89) = 0 degrees
    assert abs(compute_angle_to_goal(0, 0) - 0.0) < 0.01


def test_compute_angle_angled():
    # (49, 40) -> atan2(40, 40) = 45 degrees
    assert abs(compute_angle_to_goal(49, 40) - 45.0) < 0.01


def test_compute_angle_along_goal_line():
    # (89, 10) -> atan2(10, 0) = 90 degrees
    assert abs(compute_angle_to_goal(GOAL_X_COORD, 10) - 90.0) < 0.01


def test_compute_angle_behind_net():
    # (95, 5) -> atan2(5, -6) > 90 degrees
    angle = compute_angle_to_goal(95, 5)
    assert angle > 90.0


def test_compute_angle_negative_y():
    # (49, -40) -> atan2(40, 40) = 45 degrees (abs(y) used)
    assert abs(compute_angle_to_goal(49, -40) - 45.0) < 0.01


# ── _track_score ──────────────────────────────────────────────────────


def test_track_score_pre_event_scores():
    plays = [
        {"typeDescKey": "faceoff"},
        {"typeDescKey": "shot-on-goal"},
        {"typeDescKey": "goal", "details": {"homeScore": 1, "awayScore": 0}},
        {"typeDescKey": "shot-on-goal"},
        {"typeDescKey": "goal", "details": {"homeScore": 1, "awayScore": 1}},
    ]
    scores = _track_score(plays, home_team_id=10, away_team_id=20)
    assert scores[0] == (0, 0)  # faceoff
    assert scores[1] == (0, 0)  # shot before any goal
    assert scores[2] == (0, 0)  # goal (pre-event, no leakage)
    assert scores[3] == (1, 0)  # shot after first goal
    assert scores[4] == (1, 0)  # second goal (pre-event)


def test_track_score_no_leakage_on_goal():
    plays = [
        {"typeDescKey": "goal", "details": {"homeScore": 1, "awayScore": 0}},
    ]
    scores = _track_score(plays, home_team_id=10, away_team_id=20)
    assert scores[0] == (0, 0)


def test_track_score_empty_plays():
    assert _track_score([], 10, 20) == []


def test_track_score_no_goals():
    plays = [
        {"typeDescKey": "faceoff"},
        {"typeDescKey": "shot-on-goal"},
    ]
    scores = _track_score(plays, 10, 20)
    assert scores == [(0, 0), (0, 0)]


def test_track_score_missing_details():
    plays = [
        {"typeDescKey": "goal"},  # no details
        {"typeDescKey": "shot-on-goal"},
    ]
    scores = _track_score(plays, 10, 20)
    assert scores[0] == (0, 0)
    assert scores[1] == (0, 0)  # score didn't update because details missing


# ── extract_shot_events ───────────────────────────────────────────────


def test_extract_shot_events_empty_plays():
    game_data = {
        "plays": [],
        "homeTeam": {"id": 10},
        "awayTeam": {"id": 20},
        "id": 2023020001,
    }
    assert extract_shot_events(game_data) == []


def test_extract_shot_events_no_plays_key():
    game_data = {"homeTeam": {"id": 10}, "awayTeam": {"id": 20}, "id": 1}
    assert extract_shot_events(game_data) == []


def test_extract_shot_events_comprehensive():
    """Multi-period game with goals, faceoffs, score tracking, and coord flipping."""
    game_data = {
        "id": 2024020001,
        "homeTeam": {"id": 10},
        "awayTeam": {"id": 20},
        "plays": [
            # Period 1: home defends left
            {
                "eventId": 1,
                "typeDescKey": "faceoff",
                "periodDescriptor": {"number": 1},
                "timeInPeriod": "00:00",
                "timeRemaining": "20:00",
                "situationCode": "1551",
                "homeTeamDefendingSide": "left",
                "details": {"zoneCode": "N"},
            },
            {
                "eventId": 10,
                "typeDescKey": "shot-on-goal",
                "periodDescriptor": {"number": 1},
                "timeInPeriod": "01:00",
                "timeRemaining": "19:00",
                "situationCode": "1551",
                "homeTeamDefendingSide": "left",
                "details": {
                    "xCoord": 70, "yCoord": 10,
                    "shotType": "wrist",
                    "shootingPlayerId": 100,
                    "goalieInNetId": 200,
                    "eventOwnerTeamId": 10,
                },
            },
            {
                "eventId": 20,
                "typeDescKey": "goal",
                "periodDescriptor": {"number": 1},
                "timeInPeriod": "05:00",
                "timeRemaining": "15:00",
                "situationCode": "1551",
                "homeTeamDefendingSide": "left",
                "details": {
                    "xCoord": -80, "yCoord": -5,
                    "shotType": "snap",
                    "scoringPlayerId": 300,
                    "goalieInNetId": 201,
                    "eventOwnerTeamId": 20,
                    "homeScore": 0, "awayScore": 1,
                },
            },
            # Period 2: home defends right (sides switch)
            {
                "eventId": 30,
                "typeDescKey": "faceoff",
                "periodDescriptor": {"number": 2},
                "timeInPeriod": "00:00",
                "timeRemaining": "20:00",
                "situationCode": "1551",
                "homeTeamDefendingSide": "right",
                "details": {"zoneCode": "O"},
            },
            {
                "eventId": 40,
                "typeDescKey": "shot-on-goal",
                "periodDescriptor": {"number": 2},
                "timeInPeriod": "02:00",
                "timeRemaining": "18:00",
                "situationCode": "1551",
                "homeTeamDefendingSide": "right",
                "details": {
                    "xCoord": -75, "yCoord": 15,
                    "shotType": "slap",
                    "shootingPlayerId": 101,
                    "goalieInNetId": 200,
                    "eventOwnerTeamId": 10,
                },
            },
        ],
    }

    events = extract_shot_events(game_data)
    assert len(events) == 3

    # Period 1, home shot: home defends left, attacks right (+x), no flip
    shot1 = events[0]
    assert shot1["game_id"] == 2024020001
    assert shot1["event_idx"] == 10
    assert shot1["period"] == 1
    assert shot1["is_goal"] == 0
    assert shot1["shooting_team_id"] == 10
    assert shot1["shooter_id"] == 100
    assert shot1["goalie_id"] == 200
    assert shot1["shot_type"] == "wrist"
    assert shot1["score_state"] == "tied"  # 0-0
    assert shot1["manpower_state"] == "5v5"
    assert shot1["x_coord"] == 70  # no flip
    assert shot1["y_coord"] == 10
    assert shot1["seconds_since_faceoff"] == 60  # 01:00 - 00:00
    assert shot1["faceoff_zone_code"] == "N"

    # Period 1, away goal: away attacks left (-x), flip to +x
    goal = events[1]
    assert goal["is_goal"] == 1
    assert goal["shooting_team_id"] == 20
    assert goal["shooter_id"] == 300
    assert goal["x_coord"] == 80   # flipped from -80
    assert goal["y_coord"] == 5    # flipped from -5
    assert goal["score_state"] == "tied"  # pre-goal: 0-0
    assert goal["seconds_since_faceoff"] == 300  # 05:00 - 00:00

    # Period 2, home shot: home defends right, attacks left (-x), flip to +x
    shot2 = events[2]
    assert shot2["x_coord"] == 75   # flipped from -75
    assert shot2["y_coord"] == -15  # flipped from 15
    assert shot2["score_state"] == "down1"  # home trailing 0-1
    assert shot2["seconds_since_faceoff"] == 120  # 02:00 - 00:00
    assert shot2["faceoff_zone_code"] == "O"


def test_extract_shot_events_no_faceoff_context():
    """Shot without preceding faceoff has None faceoff fields."""
    game_data = {
        "id": 1,
        "homeTeam": {"id": 10},
        "awayTeam": {"id": 20},
        "plays": [
            {
                "eventId": 5,
                "typeDescKey": "shot-on-goal",
                "periodDescriptor": {"number": 1},
                "timeInPeriod": "10:00",
                "timeRemaining": "10:00",
                "situationCode": "1551",
                "homeTeamDefendingSide": "left",
                "details": {
                    "xCoord": 70, "yCoord": 0,
                    "shotType": "wrist",
                    "shootingPlayerId": 100,
                    "goalieInNetId": 200,
                    "eventOwnerTeamId": 10,
                },
            },
        ],
    }

    events = extract_shot_events(game_data)
    assert len(events) == 1
    assert events[0]["seconds_since_faceoff"] is None
    assert events[0]["faceoff_zone_code"] is None


def test_extract_shot_events_missing_coords():
    """Shot with missing coordinates gets None for coord-derived fields."""
    game_data = {
        "id": 1,
        "homeTeam": {"id": 10},
        "awayTeam": {"id": 20},
        "plays": [
            {
                "eventId": 5,
                "typeDescKey": "shot-on-goal",
                "periodDescriptor": {"number": 1},
                "timeInPeriod": "10:00",
                "timeRemaining": "10:00",
                "situationCode": "1551",
                "homeTeamDefendingSide": "left",
                "details": {
                    "shotType": "wrist",
                    "shootingPlayerId": 100,
                    "eventOwnerTeamId": 10,
                },
            },
        ],
    }

    events = extract_shot_events(game_data)
    assert len(events) == 1
    assert events[0]["x_coord"] is None
    assert events[0]["y_coord"] is None
    assert events[0]["distance_to_goal"] is None
    assert events[0]["angle_to_goal"] is None


def test_extract_shot_events_blocked_shot():
    """Blocked shots are included and use shootingPlayerId."""
    game_data = {
        "id": 1,
        "homeTeam": {"id": 10},
        "awayTeam": {"id": 20},
        "plays": [
            {
                "eventId": 5,
                "typeDescKey": "blocked-shot",
                "periodDescriptor": {"number": 1},
                "timeInPeriod": "03:00",
                "timeRemaining": "17:00",
                "situationCode": "1551",
                "homeTeamDefendingSide": "left",
                "details": {
                    "xCoord": 60, "yCoord": 5,
                    "shotType": "wrist",
                    "shootingPlayerId": 100,
                    "eventOwnerTeamId": 10,
                },
            },
        ],
    }

    events = extract_shot_events(game_data)
    assert len(events) == 1
    assert events[0]["is_goal"] == 0
    assert events[0]["shot_event_type"] == "blocked-shot"
    assert events[0]["shooter_id"] == 100
    assert events[0]["goalie_id"] is None  # no goalie for blocked shots


def test_extract_shot_events_skips_non_shot_events():
    """Only shot event types are extracted."""
    game_data = {
        "id": 1,
        "homeTeam": {"id": 10},
        "awayTeam": {"id": 20},
        "plays": [
            {
                "eventId": 1,
                "typeDescKey": "faceoff",
                "periodDescriptor": {"number": 1},
                "timeInPeriod": "00:00",
                "timeRemaining": "20:00",
                "details": {},
            },
            {
                "eventId": 2,
                "typeDescKey": "stoppage",
                "periodDescriptor": {"number": 1},
                "timeInPeriod": "05:00",
                "timeRemaining": "15:00",
                "details": {},
            },
            {
                "eventId": 3,
                "typeDescKey": "hit",
                "periodDescriptor": {"number": 1},
                "timeInPeriod": "06:00",
                "timeRemaining": "14:00",
                "details": {},
            },
        ],
    }

    assert extract_shot_events(game_data) == []


# ── Phase 2, Area 3: faceoff recency constants ──────────────────────


def test_faceoff_recency_bins_is_tuple():
    assert isinstance(_FACEOFF_RECENCY_BINS, tuple)
    assert len(_FACEOFF_RECENCY_BINS) > 0


def test_faceoff_recency_steady_state_label():
    assert _FACEOFF_RECENCY_STEADY_STATE == "steady_state"


def test_post_faceoff_window_seconds_is_positive():
    assert _POST_FACEOFF_WINDOW_SECONDS > 0


def test_earth_radius_km():
    assert abs(_EARTH_RADIUS_KM - 6371.0) < 1.0


# ── Phase 2, Area 3: classify_faceoff_recency ───────────────────────


def test_classify_faceoff_recency_immediate():
    assert classify_faceoff_recency(0) == "immediate"
    assert classify_faceoff_recency(3) == "immediate"
    assert classify_faceoff_recency(5) == "immediate"


def test_classify_faceoff_recency_early():
    assert classify_faceoff_recency(6) == "early"
    assert classify_faceoff_recency(10) == "early"
    assert classify_faceoff_recency(15) == "early"


def test_classify_faceoff_recency_mid():
    assert classify_faceoff_recency(16) == "mid"
    assert classify_faceoff_recency(25) == "mid"
    assert classify_faceoff_recency(30) == "mid"


def test_classify_faceoff_recency_late():
    assert classify_faceoff_recency(31) == "late"
    assert classify_faceoff_recency(45) == "late"
    assert classify_faceoff_recency(60) == "late"


def test_classify_faceoff_recency_steady_state():
    assert classify_faceoff_recency(61) == "steady_state"
    assert classify_faceoff_recency(120) == "steady_state"
    assert classify_faceoff_recency(999) == "steady_state"


def test_classify_faceoff_recency_none():
    assert classify_faceoff_recency(None) is None


def test_classify_faceoff_recency_negative():
    assert classify_faceoff_recency(-1) is None
    assert classify_faceoff_recency(-100) is None


# ── Phase 2, Area 3: faceoff_zone_recency_interaction ────────────────


def test_faceoff_zone_recency_interaction_normal():
    assert faceoff_zone_recency_interaction("O", "immediate") == "O_immediate"
    assert faceoff_zone_recency_interaction("D", "late") == "D_late"
    assert faceoff_zone_recency_interaction("N", "steady_state") == "N_steady_state"


def test_faceoff_zone_recency_interaction_none_zone():
    assert faceoff_zone_recency_interaction(None, "immediate") is None


def test_faceoff_zone_recency_interaction_none_recency():
    assert faceoff_zone_recency_interaction("O", None) is None


def test_faceoff_zone_recency_interaction_both_none():
    assert faceoff_zone_recency_interaction(None, None) is None


# ── Phase 2, Area 3: is_post_faceoff_window ─────────────────────────


def test_is_post_faceoff_window_within():
    assert is_post_faceoff_window(0) == 1
    assert is_post_faceoff_window(5) == 1
    assert is_post_faceoff_window(10) == 1


def test_is_post_faceoff_window_outside():
    assert is_post_faceoff_window(11) == 0
    assert is_post_faceoff_window(60) == 0


def test_is_post_faceoff_window_custom_window():
    assert is_post_faceoff_window(15, window_seconds=20) == 1
    assert is_post_faceoff_window(25, window_seconds=20) == 0


def test_is_post_faceoff_window_none():
    assert is_post_faceoff_window(None) is None


def test_is_post_faceoff_window_negative():
    assert is_post_faceoff_window(-1) is None


# ── Phase 2: extract_game_metadata ──────────────────────────────────


def test_extract_game_metadata_full():
    game_data = {
        "id": 2024020001,
        "gameDate": "2024-10-08",
        "season": 20242025,
        "homeTeam": {
            "id": 10,
            "abbrev": "TOR",
            "placeName": {"default": "Toronto"},
        },
        "awayTeam": {
            "id": 8,
            "abbrev": "MTL",
            "placeName": {"default": "Montréal"},
        },
        "venue": {"default": "Scotiabank Arena"},
        "venueLocation": {"default": "Toronto, ON"},
        "venueUTCOffset": "-05:00",
        "plays": [],
    }
    meta = extract_game_metadata(game_data)
    assert meta["game_id"] == 2024020001
    assert meta["game_date"] == "2024-10-08"
    assert meta["season"] == 20242025
    assert meta["home_team_id"] == 10
    assert meta["home_team_abbrev"] == "TOR"
    assert meta["home_team_name"] == "Toronto"
    assert meta["away_team_id"] == 8
    assert meta["away_team_abbrev"] == "MTL"
    assert meta["away_team_name"] == "Montréal"
    assert meta["venue_name"] == "Scotiabank Arena"
    assert meta["venue_city"] == "Toronto, ON"
    assert meta["venue_utc_offset"] == "-05:00"


def test_extract_game_metadata_missing_id():
    assert extract_game_metadata({"homeTeam": {}, "awayTeam": {}}) is None


def test_extract_game_metadata_minimal():
    meta = extract_game_metadata({"id": 1})
    assert meta["game_id"] == 1
    assert meta["game_date"] is None
    assert meta["venue_name"] is None


# ── Phase 2, Area 1: compute_rest_days ──────────────────────────────


def test_compute_rest_days_normal():
    assert compute_rest_days("2024-10-10", "2024-10-08") == 2


def test_compute_rest_days_back_to_back():
    assert compute_rest_days("2024-10-09", "2024-10-08") == 1


def test_compute_rest_days_none_inputs():
    assert compute_rest_days(None, "2024-10-08") is None
    assert compute_rest_days("2024-10-10", None) is None


# ── Phase 2, Area 1: is_back_to_back ────────────────────────────────


def test_is_back_to_back_true():
    assert is_back_to_back(1) == 1


def test_is_back_to_back_false():
    assert is_back_to_back(2) == 0
    assert is_back_to_back(0) == 0


def test_is_back_to_back_none():
    assert is_back_to_back(None) is None


# ── Phase 2, Area 1: haversine_distance ─────────────────────────────


def test_haversine_distance_same_point():
    assert haversine_distance(40.0, -74.0, 40.0, -74.0) == 0.0


def test_haversine_distance_known_cities():
    # New York to Los Angeles: ~3944 km
    dist = haversine_distance(40.7128, -74.0060, 34.0522, -118.2437)
    assert 3900 < dist < 4000


def test_haversine_distance_short():
    # Toronto to Montreal: ~504 km
    dist = haversine_distance(43.6532, -79.3832, 45.5017, -73.5673)
    assert 480 < dist < 520


# ── Phase 2, Area 1: compute_timezone_delta ─────────────────────────


def test_compute_timezone_delta_same():
    assert compute_timezone_delta(-5, -5) == 0


def test_compute_timezone_delta_east_to_west():
    # Away team at -5 (EST) traveling to -8 (PST)
    assert compute_timezone_delta(-5, -8) == -3


def test_compute_timezone_delta_west_to_east():
    # Away team at -8 (PST) traveling to -5 (EST)
    assert compute_timezone_delta(-8, -5) == 3


def test_compute_timezone_delta_none():
    assert compute_timezone_delta(None, -5) is None
    assert compute_timezone_delta(-5, None) is None
