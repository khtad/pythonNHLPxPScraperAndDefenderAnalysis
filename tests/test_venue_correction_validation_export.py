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
        "residual_venue_z_scores": {"Arena A": 1.1, "Arena B": -1.8},
    }


def test_evaluate_payload_passes_for_valid_metrics():
    metrics = exporter.evaluate_payload(_passing_payload())

    assert metrics["overall_pass"] is True
    assert metrics["correction_method"] == "distance_mean_shrinkage_v1"
    assert metrics["training_snapshot"] == "synthetic-fixture"
    assert metrics["worst_residual_venue"] == "Arena B"


def test_format_scorecard_includes_gate_summary():
    metrics = exporter.evaluate_payload(_passing_payload())
    text = exporter.format_scorecard(metrics)

    assert "# Venue Correction Validation Scorecard" in text
    assert "Held-out log loss non-worse" in text
    assert "Home-ice over-correction guardrail" in text
    assert "Residual venue z-scores" in text
    assert "Overall pass: PASS" in text
    assert "Arena B" in text


def test_evaluate_payload_rejects_missing_required_field():
    payload = _passing_payload()
    payload.pop("residual_venue_z_scores")

    with pytest.raises(ValueError, match="residual_venue_z_scores"):
        exporter.evaluate_payload(payload)
