"""Export a Phase 2.5.4 venue-correction validation scorecard.

This harness is intentionally metrics-input driven so fixture-level scorecard
behavior stays testable without a live database. The DB-specific runner in
``export_venue_correction_validation_from_db.py`` produces live metrics from
SQLite; this script owns the shared acceptance-gate evaluation and artifact
formatting.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
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
DEFAULT_PROGRESS_INTERVAL_SECONDS = 30.0

REQUIRED_PAYLOAD_FIELDS = (
    "y_true",
    "y_prob_baseline",
    "y_prob_corrected",
    "is_home_attempt",
    "residual_venue_z_scores",
)


def _format_duration(seconds: float) -> str:
    total_seconds = max(0, int(round(seconds)))
    minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m {seconds}s"
    if minutes:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def _progress(message: str, run_started_at: float | None = None) -> None:
    timestamp = dt.datetime.now().strftime("%H:%M:%S")
    elapsed = ""
    if run_started_at is not None:
        elapsed = f" elapsed={_format_duration(time.monotonic() - run_started_at)}"
    print(f"[{timestamp}] {message}{elapsed}", flush=True)


def _len_if_available(value: Any) -> int | None:
    try:
        return len(value)
    except TypeError:
        return None


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
        f"max abs(z) = {metrics['max_abs_residual_z_score']:.3f}, "
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
    parser.add_argument(
        "--progress-interval-seconds",
        type=float,
        default=DEFAULT_PROGRESS_INTERVAL_SECONDS,
        help=(
            "Reserved for consistency with other artifact exporters. "
            "Use 0 to suppress the startup heartbeat note."
        ),
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.progress_interval_seconds < 0:
        raise ValueError("--progress-interval-seconds must be non-negative.")

    run_started_at = time.monotonic()
    _progress("Starting venue-correction scorecard export.", run_started_at)
    if args.progress_interval_seconds > 0:
        _progress(
            "This exporter is usually quick; long-running DB metric generation "
            "should happen before this script and provide the metrics JSON.",
            run_started_at,
        )
    _progress(f"Metrics JSON path: {args.metrics_json}", run_started_at)
    _progress(f"Output path: {args.output_path}", run_started_at)

    _progress("Loading metrics payload.", run_started_at)
    payload = load_payload(args.metrics_json)
    y_true_rows = _len_if_available(payload.get("y_true", []))
    residual_count = _len_if_available(payload.get("residual_venue_z_scores", []))
    _progress(
        "Payload summary: "
        f"holdout rows={y_true_rows if y_true_rows is not None else 'unknown'}, "
        f"residual venues={residual_count if residual_count is not None else 'unknown'}.",
        run_started_at,
    )

    _progress("Evaluating venue-correction acceptance gates.", run_started_at)
    metrics = evaluate_payload(payload)
    _progress(
        "Gate results: "
        f"log_loss={_format_gate(metrics['log_loss_non_worse_pass'])}, "
        f"home_ice={_format_gate(metrics['home_ice_guardrail_pass'])}, "
        f"residual_z={_format_gate(metrics['residual_z_score_pass'])}, "
        f"overall={_format_gate(metrics['overall_pass'])}.",
        run_started_at,
    )
    _progress(
        f"Worst residual venue: {metrics['worst_residual_venue']} "
        f"(max abs(z)={metrics['max_abs_residual_z_score']:.3f}).",
        run_started_at,
    )

    _progress("Formatting Markdown scorecard.", run_started_at)
    scorecard = format_scorecard(metrics)

    _progress("Writing venue-correction scorecard artifact.", run_started_at)
    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    args.output_path.write_text(scorecard, encoding="utf-8")
    _progress(f"Venue correction scorecard written to: {args.output_path}", run_started_at)
    _progress("Venue-correction scorecard export complete.", run_started_at)


if __name__ == "__main__":
    main()
