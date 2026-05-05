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
    "distance_residual_venue_z_scores",
    "event_frequency_residual_venue_z_scores",
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
        payload["distance_residual_venue_z_scores"],
        payload["event_frequency_residual_venue_z_scores"],
        distance_regime_diagnostics=payload.get("distance_regime_diagnostics"),
        event_frequency_regime_diagnostics=payload.get(
            "event_frequency_regime_diagnostics"
        ),
    )
    metadata_fields = (
        "correction_method",
        "training_snapshot",
        "notes",
        "event_frequency_top_anomalies",
        "event_frequency_candidate_count",
        "event_frequency_supported_count",
        "event_frequency_primary_scope",
        "event_frequency_primary_group",
        "distance_top_regime_diagnostics",
        "distance_top_paired_diagnostics",
        "distance_location_candidate_count",
        "distance_location_supported_count",
        "event_frequency_top_regime_diagnostics",
    )
    for metadata_field in metadata_fields:
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
        f"| Distance/location residual z-scores | "
        f"{_format_gate(metrics['distance_residual_z_score_pass'])} | "
        f"{_format_residual_gate_metric(metrics, 'distance')} |\n"
        f"| Event-frequency residual z-scores | "
        f"{_format_gate(metrics['event_frequency_residual_z_score_pass'])} | "
        f"{_format_residual_gate_metric(metrics, 'event_frequency')} |\n\n"
        "## Summary Metrics\n\n"
        f"- Overall pass: {_format_gate(metrics['overall_pass'])}\n"
        f"- Holdout rows: {metrics['n_rows']:,}\n"
        f"- Distance residual venue-seasons evaluated: "
        f"{metrics['n_distance_residual_venues']:,}\n"
        f"- Distance residual gate mode: "
        f"`{metrics.get('distance_residual_gate_mode', 'max_z')}`\n"
        f"- Distance blocking regimes: "
        f"{metrics.get('distance_blocking_regime_count', 0):,}\n"
        f"- Distance supported regimes: "
        f"{metrics.get('distance_supported_regime_count', 0):,}\n"
        f"- Event-frequency residual venue-seasons evaluated: "
        f"{metrics['n_event_frequency_residual_venues']:,}\n"
        f"- Event-frequency residual gate mode: "
        f"`{metrics.get('event_frequency_residual_gate_mode', 'max_z')}`\n"
        f"- Event-frequency blocking regimes: "
        f"{metrics.get('event_frequency_blocking_regime_count', 0):,}\n"
        f"- Event-frequency supported regimes: "
        f"{metrics.get('event_frequency_supported_regime_count', 0):,}\n"
        f"- Baseline log loss: {metrics['baseline_log_loss']:.6f}\n"
        f"- Corrected log loss: {metrics['corrected_log_loss']:.6f}\n"
        f"- Baseline home advantage: {metrics['baseline_home_advantage']:.6f}\n"
        f"- Corrected home advantage: {metrics['corrected_home_advantage']:.6f}\n"
        f"- Worst distance/location residual: "
        f"`{metrics['worst_distance_residual_venue']}`\n"
        f"- Worst event-frequency residual: "
        f"`{metrics['worst_event_frequency_residual_venue']}`\n"
        f"{_format_venue_regime_diagnostics(metrics)}"
        f"{_format_distance_location_paired_diagnostics(metrics)}"
        f"{_format_event_frequency_anomalies(metrics)}"
        f"{_format_notes(notes)}"
    )


def _format_gate(passed: bool) -> str:
    return "PASS" if passed else "FAIL"


def _format_residual_gate_metric(metrics: dict[str, Any], prefix: str) -> str:
    if prefix == "distance":
        max_abs_key = "max_abs_distance_residual_z_score"
        max_allowed_key = "max_allowed_abs_distance_residual_z_score"
        blocking_key = "distance_blocking_regime_count"
        supported_key = "distance_supported_regime_count"
        mode_key = "distance_residual_gate_mode"
    else:
        max_abs_key = "max_abs_event_frequency_z_score"
        max_allowed_key = "max_allowed_abs_event_frequency_z_score"
        blocking_key = "event_frequency_blocking_regime_count"
        supported_key = "event_frequency_supported_regime_count"
        mode_key = "event_frequency_residual_gate_mode"

    if metrics.get(mode_key) == "regime_aware":
        return (
            f"blocking regimes = {metrics.get(blocking_key, 0):,}, "
            f"supported regimes = {metrics.get(supported_key, 0):,}, "
            f"max abs(z) = {metrics[max_abs_key]:.3f}, "
            f"limit < {metrics[max_allowed_key]:.3f}"
        )
    return (
        f"max abs(z) = {metrics[max_abs_key]:.3f}, "
        f"limit < {metrics[max_allowed_key]:.3f}"
    )


def _format_notes(notes: str) -> str:
    if not notes:
        return ""
    return f"\n## Notes\n\n{notes}\n"


def _format_venue_regime_diagnostics(metrics: dict[str, Any]) -> str:
    distance_rows = metrics.get("distance_top_regime_diagnostics") or []
    frequency_rows = metrics.get("event_frequency_top_regime_diagnostics") or []
    if not distance_rows and not frequency_rows:
        return ""

    lines = [
        "\n## Rolling Venue-Regime Diagnostics\n",
        "",
        "| Metric | Venue-season | z | Classification | Prior roll | "
        "Centered roll | Population anomaly share | Evidence | Known prior |",
        "|--------|--------------|---|----------------|------------|"
        "---------------|--------------------------|----------|-------------|",
    ]
    for row in [*distance_rows, *frequency_rows]:
        evidence = "YES" if row.get("evidence_supports_regime") else "NO"
        known_prior = "YES" if row.get("known_scorekeeper_prior") else "NO"
        lines.append(
            f"| `{row.get('metric_name', 'unspecified')}` | "
            f"`{row['season']}:{row['venue_name']}` | "
            f"{float(row['residual_z_score']):.3f} | "
            f"`{row['regime_classification']}` | "
            f"{_format_optional_float(row.get('prior_rolling_bias'))} | "
            f"{_format_optional_float(row.get('centered_rolling_bias'))} | "
            f"{_format_optional_float(row.get('population_anomaly_share'))} | "
            f"{evidence} | {known_prior} |"
        )
    return "\n".join(lines) + "\n"


def _format_event_frequency_anomalies(metrics: dict[str, Any]) -> str:
    top_anomalies = metrics.get("event_frequency_top_anomalies") or []
    primary_scope = metrics.get("event_frequency_primary_scope", "unspecified")
    primary_group = metrics.get("event_frequency_primary_group", "unspecified")
    candidate_count = metrics.get("event_frequency_candidate_count", 0)
    supported_count = metrics.get("event_frequency_supported_count", 0)
    text = (
        "\n## Event-Frequency Diagnostics\n\n"
        f"Primary frequency gate: sample-adequate `{primary_scope}:{primary_group}`\n\n"
        f"- Candidate frequency anomalies: {candidate_count:,}\n"
        f"- Supported real-scorekeeper regimes: {supported_count:,}\n"
    )
    if not top_anomalies:
        return text + "\nNo event-frequency anomalies exceeded the reporting threshold.\n"

    lines = [
        "",
        "| Scope | Group | Venue-season | z | Events/game | Paired diff/game | "
        "95% CI | d | Classification | Known prior |",
        "|-------|-------|--------------|---|-------------|------------------|"
        "--------|---|----------------|-------------|",
    ]
    for row in top_anomalies:
        ci_text = (
            f"[{_format_optional_float(row.get('paired_bootstrap_ci_low'))}, "
            f"{_format_optional_float(row.get('paired_bootstrap_ci_high'))}]"
        )
        known_prior = "YES" if row.get("known_scorekeeper_prior") else "NO"
        lines.append(
            f"| `{row['game_type_scope']}` | `{row['event_group']}` | "
            f"`{row['season']}:{row['venue_name']}` | "
            f"{float(row['frequency_z_score']):.3f} | "
            f"{float(row['events_per_game']):.2f} | "
            f"{_format_optional_float(row.get('paired_mean_diff_per_game'))} | "
            f"{ci_text} | {_format_optional_float(row.get('paired_cohens_d'))} | "
            f"`{row['anomaly_classification']}` | {known_prior} |"
        )
    return text + "\n".join(lines) + "\n"


def _format_distance_location_paired_diagnostics(metrics: dict[str, Any]) -> str:
    top_rows = metrics.get("distance_top_paired_diagnostics") or []
    candidate_count = metrics.get("distance_location_candidate_count", 0)
    supported_count = metrics.get("distance_location_supported_count", 0)
    text = (
        "\n## Distance-Location Paired Diagnostics\n\n"
        "- Primary distance gate: venue-season corrected-distance residuals "
        "with visiting-team paired evidence stratified by shot type and manpower state.\n\n"
        f"- Candidate distance residuals: {candidate_count:,}\n"
        f"- Supported paired distance regimes: {supported_count:,}\n"
    )
    if not top_rows:
        return text + "\nNo distance-location paired diagnostics exceeded the reporting threshold.\n"

    lines = [
        "",
        "| Venue-season | z | Paired diff | 95% CI | d | Pairs | Evidence | "
        "Evidence classification | Regime classification |",
        "|--------------|---|-------------|--------|---|-------|----------|"
        "-------------------------|-----------------------|",
    ]
    for row in top_rows:
        ci_text = (
            f"[{_format_optional_float(row.get('paired_bootstrap_ci_low'))}, "
            f"{_format_optional_float(row.get('paired_bootstrap_ci_high'))}]"
        )
        evidence = "YES" if row.get("evidence_supports_regime") else "NO"
        lines.append(
            f"| `{row['season']}:{row['venue_name']}` | "
            f"{float(row['residual_z_score']):.3f} | "
            f"{_format_optional_float(row.get('paired_mean_diff_distance'))} | "
            f"{ci_text} | {_format_optional_float(row.get('paired_cohens_d'))} | "
            f"{int(row.get('paired_away_team_seasons', 0)):,} | "
            f"{evidence} | "
            f"`{row.get('distance_location_evidence_classification', 'n/a')}` | "
            f"`{row.get('regime_classification', 'n/a')}` |"
        )
    return text + "\n".join(lines) + "\n"


def _format_optional_float(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.3f}"


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
    distance_residual_count = _len_if_available(
        payload.get("distance_residual_venue_z_scores", [])
    )
    frequency_residual_count = _len_if_available(
        payload.get("event_frequency_residual_venue_z_scores", [])
    )
    _progress(
        "Payload summary: "
        f"holdout rows={y_true_rows if y_true_rows is not None else 'unknown'}, "
        "distance residuals="
        f"{distance_residual_count if distance_residual_count is not None else 'unknown'}, "
        "frequency residuals="
        f"{frequency_residual_count if frequency_residual_count is not None else 'unknown'}.",
        run_started_at,
    )

    _progress("Evaluating venue-correction acceptance gates.", run_started_at)
    metrics = evaluate_payload(payload)
    _progress(
        "Gate results: "
        f"log_loss={_format_gate(metrics['log_loss_non_worse_pass'])}, "
        f"home_ice={_format_gate(metrics['home_ice_guardrail_pass'])}, "
        f"distance_z={_format_gate(metrics['distance_residual_z_score_pass'])}, "
        "frequency_z="
        f"{_format_gate(metrics['event_frequency_residual_z_score_pass'])}, "
        f"overall={_format_gate(metrics['overall_pass'])}.",
        run_started_at,
    )
    _progress(
        "Worst residuals: "
        f"distance={metrics['worst_distance_residual_venue']} "
        f"(max abs(z)={metrics['max_abs_distance_residual_z_score']:.3f}), "
        f"frequency={metrics['worst_event_frequency_residual_venue']} "
        f"(max abs(z)={metrics['max_abs_event_frequency_z_score']:.3f}).",
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
