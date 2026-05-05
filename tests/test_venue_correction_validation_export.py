import importlib.util
from pathlib import Path

import pytest

pytest.importorskip("numpy")
pytest.importorskip("scipy")
pytest.importorskip("sklearn")


_SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "export_venue_correction_validation.py"
)
_SPEC = importlib.util.spec_from_file_location(
    "export_venue_correction_validation", _SCRIPT_PATH
)
exporter = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(exporter)


def _passing_payload():
    return {
        "correction_method": "distance_mean_shrinkage_v1",
        "training_snapshot": "synthetic-fixture",
        "notes": "Synthetic test fixture.",
        "y_true": [1, 1, 0, 0, 1, 0, 0, 0],
        "is_home_attempt": [True, True, True, True, False, False, False, False],
        "y_prob_baseline": [0.90, 0.70, 0.40, 0.20, 0.60, 0.40, 0.40, 0.20],
        "y_prob_corrected": [0.85, 0.75, 0.35, 0.25, 0.55, 0.35, 0.35, 0.25],
        "distance_residual_venue_z_scores": {"Arena A": 1.1, "Arena B": -1.8},
        "event_frequency_residual_venue_z_scores": {
            "Arena A": 0.8,
            "Arena B": -1.2,
        },
        "event_frequency_primary_scope": "regular_season",
        "event_frequency_primary_group": "training_attempts",
        "distance_location_candidate_count": 1,
        "distance_location_supported_count": 1,
        "distance_top_paired_diagnostics": [
            {
                "season": "20202021",
                "venue_name": "Arena A",
                "residual_z_score": 2.4,
                "paired_away_team_seasons": 10,
                "paired_mean_diff_distance": 1.2,
                "paired_bootstrap_ci_low": 0.4,
                "paired_bootstrap_ci_high": 2.0,
                "paired_cohens_d": 0.35,
                "evidence_supports_regime": True,
                "distance_location_evidence_classification": (
                    "real_scorekeeper_regime_supported"
                ),
                "regime_classification": "temporary_supported_regime",
            }
        ],
        "event_frequency_candidate_count": 1,
        "event_frequency_supported_count": 0,
        "event_frequency_top_anomalies": [
            {
                "game_type_scope": "regular_season",
                "event_group": "training_attempts",
                "season": "20202021",
                "venue_name": "Arena A",
                "games_played": 41,
                "event_count": 2500,
                "events_per_game": 60.9,
                "frequency_z_score": 2.4,
                "paired_mean_diff_per_game": 0.1,
                "paired_bootstrap_ci_low": -1.0,
                "paired_bootstrap_ci_high": 1.0,
                "paired_cohens_d": 0.01,
                "known_scorekeeper_prior": False,
                "anomaly_classification": "hockey_context_confounded",
            }
        ],
    }


def test_evaluate_payload_passes_for_valid_metrics():
    metrics = exporter.evaluate_payload(_passing_payload())

    assert metrics["overall_pass"] is True
    assert metrics["correction_method"] == "distance_mean_shrinkage_v1"
    assert metrics["training_snapshot"] == "synthetic-fixture"
    assert metrics["worst_distance_residual_venue"] == "Arena B"
    assert metrics["max_abs_distance_residual_z_score"] == pytest.approx(1.8)
    assert metrics["worst_event_frequency_residual_venue"] == "Arena B"
    assert metrics["max_abs_event_frequency_z_score"] == pytest.approx(1.2)


def test_format_scorecard_includes_gate_summary():
    metrics = exporter.evaluate_payload(_passing_payload())
    text = exporter.format_scorecard(metrics)

    assert "# Venue Correction Validation Scorecard" in text
    assert "Held-out log loss non-worse" in text
    assert "Home-ice over-correction guardrail" in text
    assert "Distance/location residual z-scores" in text
    assert "Event-frequency residual z-scores" in text
    assert "max abs(z) = 1.800" in text
    assert "Overall pass: PASS" in text
    assert "Arena B" in text
    assert "Distance-Location Paired Diagnostics" in text
    assert "real_scorekeeper_regime_supported" in text
    assert "Event-Frequency Diagnostics" in text
    assert "hockey_context_confounded" in text


def test_format_scorecard_includes_regime_aware_diagnostics():
    payload = _passing_payload()
    payload["distance_residual_venue_z_scores"] = {
        "20102011:Arena A": 2.4,
        "20102011:Arena B": -1.8,
    }
    payload["distance_regime_diagnostics"] = [
        {
            "metric_name": "distance_location",
            "season": "20102011",
            "venue_name": "Arena A",
            "residual_z_score": 2.4,
            "regime_classification": "temporary_supported_regime",
        }
    ]
    payload["distance_top_regime_diagnostics"] = [
        {
            "metric_name": "distance_location",
            "season": "20102011",
            "venue_name": "Arena A",
            "residual_z_score": 2.4,
            "regime_classification": "temporary_supported_regime",
            "prior_rolling_bias": 1.5,
            "centered_rolling_bias": 0.8,
            "population_anomaly_share": 0.1,
            "evidence_supports_regime": True,
            "known_scorekeeper_prior": True,
        }
    ]

    metrics = exporter.evaluate_payload(payload)
    text = exporter.format_scorecard(metrics)

    assert metrics["distance_residual_z_score_pass"] is True
    assert metrics["distance_residual_gate_mode"] == "regime_aware"
    assert "Rolling Venue-Regime Diagnostics" in text
    assert "blocking regimes = 0" in text
    assert "temporary_supported_regime" in text


def test_evaluate_payload_rejects_missing_required_field():
    payload = _passing_payload()
    payload.pop("event_frequency_residual_venue_z_scores")

    with pytest.raises(ValueError, match="event_frequency_residual_venue_z_scores"):
        exporter.evaluate_payload(payload)
