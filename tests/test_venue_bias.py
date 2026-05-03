import pytest

pytest.importorskip("numpy")
pytest.importorskip("scipy")

from venue_bias import (
    ANOMALY_HOCKEY_CONTEXT_CONFOUNDED,
    ANOMALY_INSUFFICIENT_EVIDENCE,
    ANOMALY_NOT_FLAGGED,
    ANOMALY_REAL_SCOREKEEPER_REGIME_SUPPORTED,
    EVENT_FREQUENCY_GROUP_BLOCKED_SHOTS,
    EVENT_FREQUENCY_GROUP_TRAINING_ATTEMPTS,
    EVENT_FREQUENCY_SCOPE_REGULAR_SEASON,
    EVENT_FREQUENCY_SCOPE_TRAINING_CONTRACT,
    VENUE_REGIME_METRIC_DISTANCE,
    VENUE_REGIME_PERSISTENT_BIAS,
    VENUE_REGIME_POPULATION_SHIFT,
    VENUE_REGIME_TEMPORARY_SUPPORTED,
    VENUE_REGIME_UNEXPLAINED_OR_CONFOUNDED,
    annotate_event_frequency_anomalies,
    classify_rolling_venue_regimes,
    compute_centered_rolling_bias_estimates,
    compute_event_frequency_diagnostics,
    compute_paired_away_frequency_comparisons,
    compute_prior_rolling_bias_estimates,
    primary_event_frequency_residual_z_scores,
    primary_event_frequency_regime_diagnostics,
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


def _regime_row(
    venue_name,
    season,
    z_score,
    evidence_supports_regime=False,
    sample_adequate=True,
):
    return {
        "metric_name": VENUE_REGIME_METRIC_DISTANCE,
        "season": season,
        "venue_name": venue_name,
        "residual_z_score": z_score,
        "sample_adequate": sample_adequate,
        "evidence_supports_regime": evidence_supports_regime,
    }


def _normal_population_rows(season, excluded_venue):
    return [
        _regime_row(f"Arena {idx}", season, 0.1 * idx)
        for idx in range(5)
        if f"Arena {idx}" != excluded_venue
    ]


def test_prior_rolling_bias_uses_only_past_venue_seasons():
    rows = [
        _regime_row("Arena A", "20102011", 4.0),
        _regime_row("Arena A", "20112012", 0.5),
        _regime_row("Arena A", "20122013", 1.0),
    ]

    enriched = compute_prior_rolling_bias_estimates(rows)
    by_season = {row["season"]: row for row in enriched}

    assert by_season["20102011"]["prior_rolling_bias"] is None
    assert by_season["20112012"]["prior_rolling_bias"] == pytest.approx(4.0)
    assert by_season["20122013"]["prior_rolling_bias"] == pytest.approx(2.25)
    assert by_season["20122013"]["prior_rolling_uses_future"] is False


def test_centered_rolling_bias_marks_future_use_as_diagnostic():
    rows = [
        _regime_row("Arena A", "20102011", 4.0),
        _regime_row("Arena A", "20112012", 0.5),
        _regime_row("Arena A", "20122013", 1.0),
    ]

    enriched = compute_centered_rolling_bias_estimates(rows)
    by_season = {row["season"]: row for row in enriched}

    assert by_season["20102011"]["centered_rolling_uses_future"] is True
    assert by_season["20112012"]["centered_rolling_bias"] == pytest.approx(
        1.833333333
    )
    assert by_season["20122013"]["centered_rolling_uses_future"] is False


def test_rolling_regime_classifier_marks_persistent_bias():
    rows = [
        _regime_row("Arena A", "20102011", 2.5),
        *_normal_population_rows("20102011", "Arena A"),
        _regime_row("Arena A", "20112012", 2.4),
        *_normal_population_rows("20112012", "Arena A"),
    ]

    classified = classify_rolling_venue_regimes(rows)
    arena_rows = [row for row in classified if row["venue_name"] == "Arena A"]

    assert {row["regime_classification"] for row in arena_rows} == {
        VENUE_REGIME_PERSISTENT_BIAS
    }


def test_rolling_regime_classifier_does_not_join_distant_spikes():
    rows = [
        _regime_row("Arena A", "20102011", 2.5),
        *_normal_population_rows("20102011", "Arena A"),
        _regime_row("Arena A", "20152016", 2.4),
        *_normal_population_rows("20152016", "Arena A"),
    ]

    classified = classify_rolling_venue_regimes(rows)
    arena_rows = [row for row in classified if row["venue_name"] == "Arena A"]

    assert {row["regime_classification"] for row in arena_rows} == {
        VENUE_REGIME_UNEXPLAINED_OR_CONFOUNDED
    }


def test_rolling_regime_classifier_marks_supported_temporary_spike():
    rows = [
        _regime_row("Arena A", "20102011", 2.8, evidence_supports_regime=True),
        *_normal_population_rows("20102011", "Arena A"),
    ]

    classified = classify_rolling_venue_regimes(rows)
    arena = [row for row in classified if row["venue_name"] == "Arena A"][0]

    assert arena["regime_classification"] == VENUE_REGIME_TEMPORARY_SUPPORTED
    assert arena["population_anomaly_share"] == pytest.approx(1 / 6)


def test_rolling_regime_classifier_blocks_unexplained_spike():
    rows = [
        _regime_row("Arena A", "20102011", -2.8),
        *_normal_population_rows("20102011", "Arena A"),
    ]

    classified = classify_rolling_venue_regimes(rows)
    arena = [row for row in classified if row["venue_name"] == "Arena A"][0]

    assert arena["regime_classification"] == VENUE_REGIME_UNEXPLAINED_OR_CONFOUNDED


def test_rolling_regime_classifier_flags_population_shift():
    rows = [
        _regime_row("Arena A", "20102011", 2.8, evidence_supports_regime=True),
        _regime_row("Arena B", "20102011", -2.8, evidence_supports_regime=True),
        _regime_row("Arena C", "20102011", 2.9, evidence_supports_regime=True),
        _regime_row("Arena D", "20102011", 0.1),
        _regime_row("Arena E", "20102011", 0.2),
        _regime_row("Arena F", "20102011", 0.3),
    ]

    classified = classify_rolling_venue_regimes(rows)
    candidate_labels = {
        row["venue_name"]: row["regime_classification"]
        for row in classified
        if row["candidate_regime"]
    }

    assert set(candidate_labels.values()) == {VENUE_REGIME_POPULATION_SHIFT}


def test_primary_event_frequency_regime_diagnostics_preserve_paired_evidence():
    annotated = [
        {
            "game_type_scope": EVENT_FREQUENCY_SCOPE_REGULAR_SEASON,
            "event_group": EVENT_FREQUENCY_GROUP_TRAINING_ATTEMPTS,
            "season": "20112012",
            "venue_name": "Madison Square Garden",
            "frequency_z_score": 2.6,
            "sample_adequate": True,
            "known_scorekeeper_prior": True,
            "anomaly_classification": ANOMALY_REAL_SCOREKEEPER_REGIME_SUPPORTED,
        },
        *[
            {
                "game_type_scope": EVENT_FREQUENCY_SCOPE_REGULAR_SEASON,
                "event_group": EVENT_FREQUENCY_GROUP_TRAINING_ATTEMPTS,
                "season": "20112012",
                "venue_name": f"Arena {idx}",
                "frequency_z_score": 0.1 * idx,
                "sample_adequate": True,
                "known_scorekeeper_prior": False,
                "anomaly_classification": ANOMALY_NOT_FLAGGED,
            }
            for idx in range(5)
        ],
    ]

    diagnostics = primary_event_frequency_regime_diagnostics(annotated)
    msg = [
        row for row in diagnostics
        if row["venue_name"] == "Madison Square Garden"
    ][0]

    assert msg["evidence_supports_regime"] is True
    assert msg["regime_classification"] == VENUE_REGIME_TEMPORARY_SUPPORTED


def test_primary_event_frequency_regime_diagnostics_exclude_sample_inadequate_rows():
    annotated = [
        {
            "game_type_scope": EVENT_FREQUENCY_SCOPE_REGULAR_SEASON,
            "event_group": EVENT_FREQUENCY_GROUP_TRAINING_ATTEMPTS,
            "season": "20232024",
            "venue_name": "MetLife Stadium",
            "frequency_z_score": 9.6,
            "sample_adequate": False,
            "known_scorekeeper_prior": False,
            "anomaly_classification": ANOMALY_INSUFFICIENT_EVIDENCE,
        }
    ]

    diagnostics = primary_event_frequency_regime_diagnostics(annotated)

    assert diagnostics == []
