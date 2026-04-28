"""Export a Phase 2.5.4 venue-correction validation scorecard.

This harness is intentionally metrics-input driven so it can be built and
tested before the live database finishes backfilling. A later DB-specific
runner can produce the JSON payload; this script owns the acceptance-gate
evaluation and artifact formatting.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from validation import evaluate_venue_correction_scorecard

DEFAULT_OUTPUT_PATH = (
    PROJECT_ROOT / "artifacts" / "venue_correction_validation_latest.md"
)

REQUIRED_PAYLOAD_FIELDS = (
    "y_true",
    "y_prob_baseline",
    "y_prob_corrected",
    "is_home_attempt",
    "residual_venue_z_scores",
)


def load_payload(path: Path) -> dict[str, Any]:
    """Load a JSON validation payload from disk."""
    with path.open("r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError("Metrics payload must be a JSON object.")
    return payload


def evaluate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Evaluate a metrics payload against the venue-correction gates."""
    missing_fields = [
        field for field in REQUIRED_PAYLOAD_FIELDS
        if field not in payload
    ]
    if missing_fields:
        raise ValueError(
            "Metrics payload is missing required fields: "
            + ", ".join(missing_fields)
        )

    metrics = evaluate_venue_correction_scorecard(
        payload["y_true"],
        payload["y_prob_baseline"],
        payload["y_prob_corrected"],
        payload["is_home_attempt"],
        payload["residual_venue_z_scores"],
    )
    for metadata_field in ("correction_method", "training_snapshot", "notes"):
        if metadata_field in payload:
            metrics[metadata_field] = payload[metadata_field]
    return metrics


def format_scorecard(metrics: dict[str, Any]) -> str:
    """Format venue-correction validation metrics as Markdown."""
    generated_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    method = metrics.get("correction_method", "unspecified")
    snapshot = metrics.get("training_snapshot", "unspecified")
    notes = metrics.get("notes", "")

    return (
        "# Venue Correction Validation Scorecard\n\n"
        f"Generated: {generated_at}\n\n"
        f"Correction method: `{method}`\n\n"
        f"Training snapshot: `{snapshot}`\n\n"
        "## Acceptance Gates\n\n"
        "| Gate | Result | Metric |\n"
        "|------|--------|--------|\n"
        f"| Held-out log loss non-worse | "
        f"{_format_gate(metrics['log_loss_non_worse_pass'])} | "
        f"delta = {metrics['log_loss_delta']:.6f} |\n"
        f"| Home-ice over-correction guardrail | "
        f"{_format_gate(metrics['home_ice_guardrail_pass'])} | "
        f"removed = {metrics['advantage_removed_ratio']:.3f}, "
        f"max = {metrics['max_allowed_advantage_removed_ratio']:.3f} |\n"
        f"| Residual venue z-scores | "
        f"{_format_gate(metrics['residual_z_score_pass'])} | "
        f"max |z| = {metrics['max_abs_residual_z_score']:.3f}, "
        f"limit < {metrics['max_allowed_abs_residual_z_score']:.3f} |\n\n"
        "## Summary Metrics\n\n"
        f"- Overall pass: {_format_gate(metrics['overall_pass'])}\n"
        f"- Holdout rows: {metrics['n_rows']:,}\n"
        f"- Venues evaluated: {metrics['n_venues']:,}\n"
        f"- Baseline log loss: {metrics['baseline_log_loss']:.6f}\n"
        f"- Corrected log loss: {metrics['corrected_log_loss']:.6f}\n"
        f"- Baseline home advantage: {metrics['baseline_home_advantage']:.6f}\n"
        f"- Corrected home advantage: {metrics['corrected_home_advantage']:.6f}\n"
        f"- Worst residual venue: `{metrics['worst_residual_venue']}`\n"
        f"{_format_notes(notes)}"
    )


def _format_gate(passed: bool) -> str:
    return "PASS" if passed else "FAIL"


def _format_notes(notes: str) -> str:
    if not notes:
        return ""
    return f"\n## Notes\n\n{notes}\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export the Phase 2.5.4 venue-correction validation scorecard."
    )
    parser.add_argument(
        "--metrics-json",
        type=Path,
        required=True,
        help="Path to a JSON payload containing holdout probabilities and residual z-scores.",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Markdown artifact path to write.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    payload = load_payload(args.metrics_json)
    metrics = evaluate_payload(payload)
    scorecard = format_scorecard(metrics)

    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    args.output_path.write_text(scorecard, encoding="utf-8")
    print(f"Venue correction scorecard written to: {args.output_path}")


if __name__ == "__main__":
    main()
