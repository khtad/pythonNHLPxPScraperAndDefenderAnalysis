import pytest

pytest.importorskip("numpy")
pytest.importorskip("scipy")

from venue_bias import (
    ANOMALY_HOCKEY_CONTEXT_CONFOUNDED,
    ANOMALY_INSUFFICIENT_EVIDENCE,
    ANOMALY_REAL_SCOREKEEPER_REGIME_SUPPORTED,
    EVENT_FREQUENCY_GROUP_BLOCKED_SHOTS,
    EVENT_FREQUENCY_GROUP_TRAINING_ATTEMPTS,
    EVENT_FREQUENCY_SCOPE_REGULAR_SEASON,
    EVENT_FREQUENCY_SCOPE_TRAINING_CONTRACT,
    annotate_event_frequency_anomalies,
    compute_event_frequency_diagnostics,
    compute_paired_away_frequency_comparisons,
    primary_event_frequency_residual_z_scores,
)


def _game_row(
    venue_name,
    game_id,
    away_team_id,
    event_count,
    away_event_count,
    event_group=EVENT_FREQUENCY_GROUP_TRAINING_ATTEMPTS,
    game_type_scope=EVENT_FREQUENCY_SCOPE_REGULAR_SEASON,
    season="20202021",
):
    return {
        "game_type_scope": game_type_scope,
        "event_group": event_group,
        "season": season,
        "venue_name": venue_name,
        "game_id": game_id,
        "home_team_id": 1000 + game_id,
        "away_team_id": away_team_id,
        "event_count": event_count,
        "home_event_count": event_count - away_event_count,
        "away_event_count": away_event_count,
    }


def test_event_frequency_diagnostics_compute_rates_and_z_scores():
    rows = []
    for idx in range(20):
        rows.append(_game_row("Arena A", idx, idx, 10, 4))
        rows.append(_game_row("Arena B", 100 + idx, idx, 20, 8))
        rows.append(_game_row("Arena C", 200 + idx, idx, 30, 12))

    diagnostics = compute_event_frequency_diagnostics(rows)
    by_venue = {row["venue_name"]: row for row in diagnostics}

    assert by_venue["Arena A"]["events_per_game"] == pytest.approx(10.0)
    assert by_venue["Arena B"]["frequency_z_score"] == pytest.approx(0.0)
    assert by_venue["Arena C"]["frequency_z_score"] == pytest.approx(1.224744871)
    assert by_venue["Arena C"]["sample_adequate"] is True


def test_event_frequency_baseline_excludes_sample_inadequate_venues():
    rows = []
    for idx in range(20):
        rows.append(_game_row("Arena A", idx, idx, 10, 4))
        rows.append(_game_row("Arena B", 100 + idx, idx, 20, 8))
    rows.append(_game_row("Neutral Site", 999, 999, 100, 40))

    diagnostics = compute_event_frequency_diagnostics(rows)
    by_venue = {row["venue_name"]: row for row in diagnostics}

    assert by_venue["Neutral Site"]["sample_adequate"] is False
    assert by_venue["Arena A"]["league_events_per_game_mean"] == pytest.approx(15.0)
    assert by_venue["Arena A"]["league_events_per_game_stddev"] == pytest.approx(5.0)
    assert by_venue["Arena A"]["frequency_z_score"] == pytest.approx(-1.0)
    assert by_venue["Arena B"]["frequency_z_score"] == pytest.approx(1.0)
    assert by_venue["Neutral Site"]["frequency_z_score"] == pytest.approx(17.0)


def test_event_frequency_diagnostics_keep_scope_and_group_separate():
    rows = [
        _game_row(
            "Arena A",
            1,
            10,
            10,
            4,
            event_group=EVENT_FREQUENCY_GROUP_TRAINING_ATTEMPTS,
            game_type_scope=EVENT_FREQUENCY_SCOPE_REGULAR_SEASON,
        ),
        _game_row(
            "Arena A",
            2,
            10,
            3,
            1,
            event_group=EVENT_FREQUENCY_GROUP_BLOCKED_SHOTS,
            game_type_scope=EVENT_FREQUENCY_SCOPE_REGULAR_SEASON,
        ),
        _game_row(
            "Arena A",
            3,
            10,
            8,
            3,
            event_group=EVENT_FREQUENCY_GROUP_TRAINING_ATTEMPTS,
            game_type_scope=EVENT_FREQUENCY_SCOPE_TRAINING_CONTRACT,
        ),
    ]

    diagnostics = compute_event_frequency_diagnostics(rows)
    observed = {
        (row["game_type_scope"], row["event_group"]): row["event_count"]
        for row in diagnostics
    }

    assert observed[
        (EVENT_FREQUENCY_SCOPE_REGULAR_SEASON, EVENT_FREQUENCY_GROUP_TRAINING_ATTEMPTS)
    ] == 10
    assert observed[
        (EVENT_FREQUENCY_SCOPE_REGULAR_SEASON, EVENT_FREQUENCY_GROUP_BLOCKED_SHOTS)
    ] == 3
    assert observed[
        (EVENT_FREQUENCY_SCOPE_TRAINING_CONTRACT, EVENT_FREQUENCY_GROUP_TRAINING_ATTEMPTS)
    ] == 8


def test_paired_away_frequency_comparison_controls_for_visitor_team_season():
    rows = []
    for team_id in range(10, 20):
        rows.append(_game_row("Madison Square Garden", team_id, team_id, 50, 30))
        rows.append(_game_row("Arena B", 100 + team_id, team_id, 35, 20))
        rows.append(_game_row("Arena C", 200 + team_id, team_id, 35, 20))

    comparisons = compute_paired_away_frequency_comparisons(rows)
    msg = [
        row for row in comparisons
        if row["venue_name"] == "Madison Square Garden"
    ][0]

    assert msg["paired_away_team_seasons"] == 10
    assert msg["paired_mean_diff_per_game"] == pytest.approx(10.0)
    assert msg["paired_bootstrap_ci_low"] > 0
    assert msg["paired_sample_adequate"] is True


def test_anomaly_classifier_marks_supported_real_scorekeeper_regime():
    diagnostics = [
        {
            "game_type_scope": EVENT_FREQUENCY_SCOPE_REGULAR_SEASON,
            "event_group": EVENT_FREQUENCY_GROUP_TRAINING_ATTEMPTS,
            "season": "20202021",
            "venue_name": "Madison Square Garden",
            "games_played": 41,
            "event_count": 2500,
            "events_per_game": 60.9,
            "frequency_z_score": 3.2,
            "sample_adequate": True,
        }
    ]
    comparisons = [
        {
            "game_type_scope": EVENT_FREQUENCY_SCOPE_REGULAR_SEASON,
            "event_group": EVENT_FREQUENCY_GROUP_TRAINING_ATTEMPTS,
            "season": "20202021",
            "venue_name": "Madison Square Garden",
            "paired_away_team_seasons": 24,
            "paired_mean_diff_per_game": 4.0,
            "paired_bootstrap_ci_low": 1.0,
            "paired_bootstrap_ci_high": 7.0,
            "paired_wilcoxon_p_value": 0.01,
            "paired_cohens_d": 0.5,
            "paired_sample_adequate": True,
        }
    ]

    annotated = annotate_event_frequency_anomalies(diagnostics, comparisons)

    assert annotated[0]["known_scorekeeper_prior"] is True
    assert annotated[0]["anomaly_classification"] == (
        ANOMALY_REAL_SCOREKEEPER_REGIME_SUPPORTED
    )


def test_anomaly_classifier_marks_insufficient_sample_before_inference():
    diagnostics = [
        {
            "game_type_scope": EVENT_FREQUENCY_SCOPE_REGULAR_SEASON,
            "event_group": EVENT_FREQUENCY_GROUP_TRAINING_ATTEMPTS,
            "season": "20202021",
            "venue_name": "Arena A",
            "games_played": 4,
            "event_count": 300,
            "events_per_game": 75.0,
            "frequency_z_score": 3.2,
            "sample_adequate": False,
        }
    ]

    annotated = annotate_event_frequency_anomalies(diagnostics, [])

    assert annotated[0]["anomaly_classification"] == ANOMALY_INSUFFICIENT_EVIDENCE


def test_anomaly_classifier_marks_context_confounded_when_pairing_disagrees():
    diagnostics = [
        {
            "game_type_scope": EVENT_FREQUENCY_SCOPE_REGULAR_SEASON,
            "event_group": EVENT_FREQUENCY_GROUP_TRAINING_ATTEMPTS,
            "season": "20202021",
            "venue_name": "Arena A",
            "games_played": 41,
            "event_count": 2500,
            "events_per_game": 60.9,
            "frequency_z_score": 3.2,
            "sample_adequate": True,
        }
    ]
    comparisons = [
        {
            "game_type_scope": EVENT_FREQUENCY_SCOPE_REGULAR_SEASON,
            "event_group": EVENT_FREQUENCY_GROUP_TRAINING_ATTEMPTS,
            "season": "20202021",
            "venue_name": "Arena A",
            "paired_away_team_seasons": 24,
            "paired_mean_diff_per_game": 0.1,
            "paired_bootstrap_ci_low": -2.0,
            "paired_bootstrap_ci_high": 2.0,
            "paired_wilcoxon_p_value": 0.82,
            "paired_cohens_d": 0.01,
            "paired_sample_adequate": True,
        }
    ]

    annotated = annotate_event_frequency_anomalies(diagnostics, comparisons)

    assert annotated[0]["anomaly_classification"] == ANOMALY_HOCKEY_CONTEXT_CONFOUNDED


def test_primary_event_frequency_residuals_use_regular_training_attempts_only():
    diagnostics = [
        {
            "game_type_scope": EVENT_FREQUENCY_SCOPE_REGULAR_SEASON,
            "event_group": EVENT_FREQUENCY_GROUP_TRAINING_ATTEMPTS,
            "season": "20202021",
            "venue_name": "Arena A",
            "frequency_z_score": 2.1,
            "sample_adequate": True,
        },
        {
            "game_type_scope": EVENT_FREQUENCY_SCOPE_REGULAR_SEASON,
            "event_group": EVENT_FREQUENCY_GROUP_BLOCKED_SHOTS,
            "season": "20202021",
            "venue_name": "Arena A",
            "frequency_z_score": 9.9,
            "sample_adequate": True,
        },
        {
            "game_type_scope": EVENT_FREQUENCY_SCOPE_REGULAR_SEASON,
            "event_group": EVENT_FREQUENCY_GROUP_TRAINING_ATTEMPTS,
            "season": "20212022",
            "venue_name": "Neutral Site",
            "frequency_z_score": 9.9,
            "sample_adequate": False,
        },
    ]

    residuals = primary_event_frequency_residual_z_scores(diagnostics)

    assert residuals == {"20202021:Arena A": 2.1}
