"""Execute the validation framework notebook and export a scorecard artifact.

Phase 2.5.3 requires an end-to-end run against the live v3 database plus a
committed scorecard artifact. This script standardizes that run so the same
commands can be reused when the database is available.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from database import _MIN_TRAINING_SEASON, _XG_EVENT_SCHEMA_VERSION, ensure_xg_schema

DEFAULT_DATABASE_PATH = PROJECT_ROOT / "data" / "nhl_data.db"
DEFAULT_NOTEBOOK_PATH = PROJECT_ROOT / "notebooks" / "model_validation_framework.ipynb"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "artifacts"
EXECUTED_NOTEBOOK_NAME = "model_validation_framework.executed.ipynb"
SCORECARD_OUTPUT_NAME = "validation_scorecard_latest.md"
SCORECARD_SENTINEL = "VALIDATION SCORECARD"
DEFAULT_EXECUTION_TIMEOUT_SECONDS = 3600
DEFAULT_PROGRESS_INTERVAL_SECONDS = 30.0


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


def _run_command_with_progress(
    cmd: list[str],
    *,
    label: str,
    progress_interval_seconds: float,
    run_started_at: float,
) -> None:
    step_started_at = time.monotonic()
    _progress(f"Starting {label}.", run_started_at)
    process = subprocess.Popen(
        cmd,
        cwd=PROJECT_ROOT,
    )
    next_progress_at = step_started_at + progress_interval_seconds
    while True:
        return_code = process.poll()
        if return_code is not None:
            break

        if (
            progress_interval_seconds > 0
            and time.monotonic() >= next_progress_at
        ):
            step_elapsed = _format_duration(time.monotonic() - step_started_at)
            _progress(f"{label} still running after {step_elapsed}.", run_started_at)
            next_progress_at = time.monotonic() + progress_interval_seconds
        time.sleep(1.0)

    if return_code != 0:
        raise subprocess.CalledProcessError(return_code, cmd)

    step_elapsed = _format_duration(time.monotonic() - step_started_at)
    _progress(f"Finished {label} in {step_elapsed}.", run_started_at)


def _prepare_database(database_path: Path) -> tuple[list[tuple[str | None, int]], int]:
    import sqlite3

    conn = sqlite3.connect(database_path)
    try:
        ensure_xg_schema(conn)
        cursor = conn.cursor()
        cursor.execute(
            """SELECT event_schema_version, COUNT(*)
               FROM shot_events
               GROUP BY event_schema_version
               ORDER BY event_schema_version"""
        )
        version_counts = cursor.fetchall()
        cursor.execute(
            """SELECT COUNT(*)
               FROM shot_events se
               JOIN games g ON se.game_id = g.game_id
               WHERE se.event_schema_version != ?
                 AND g.season >= ?
                 AND se.distance_to_goal IS NOT NULL
                 AND se.angle_to_goal IS NOT NULL
                 AND se.shot_type IS NOT NULL""",
            (_XG_EVENT_SCHEMA_VERSION, _MIN_TRAINING_SEASON),
        )
        stale_training_rows = cursor.fetchone()[0]
    finally:
        conn.close()
    return version_counts, stale_training_rows


def _extract_scorecard_text(executed_notebook_path: Path) -> str:
    with executed_notebook_path.open("r", encoding="utf-8") as f:
        notebook = json.load(f)

    for cell in notebook.get("cells", []):
        if cell.get("cell_type") != "code":
            continue
        for output in cell.get("outputs", []):
            if output.get("output_type") != "stream":
                continue
            text_value = output.get("text", "")
            if isinstance(text_value, list):
                text_value = "".join(text_value)
            if SCORECARD_SENTINEL in text_value:
                return text_value.strip()

    raise ValueError(
        "Could not find a code-cell stream output containing "
        f"{SCORECARD_SENTINEL!r}."
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DATABASE_PATH)
    parser.add_argument("--notebook-path", type=Path, default=DEFAULT_NOTEBOOK_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=DEFAULT_EXECUTION_TIMEOUT_SECONDS,
        help="Notebook execution timeout per cell.",
    )
    parser.add_argument(
        "--progress-interval-seconds",
        type=float,
        default=DEFAULT_PROGRESS_INTERVAL_SECONDS,
        help=(
            "Seconds between progress heartbeats while the notebook is "
            "executing. Use 0 to disable periodic heartbeats."
        ),
    )
    args = parser.parse_args()
    if args.progress_interval_seconds < 0:
        raise ValueError("--progress-interval-seconds must be non-negative.")

    run_started_at = time.monotonic()
    _progress("Starting validation scorecard export.", run_started_at)
    _progress(f"Database path: {args.db_path}", run_started_at)
    _progress(f"Notebook path: {args.notebook_path}", run_started_at)
    _progress(f"Output directory: {args.output_dir}", run_started_at)
    _progress(
        f"Notebook per-cell timeout: {_format_duration(args.timeout_seconds)}.",
        run_started_at,
    )

    if not args.db_path.exists():
        raise FileNotFoundError(
            f"Database not found at {args.db_path}. "
            "Phase 2.5.3 requires the live populated nhl_data.db file."
        )

    if not args.notebook_path.exists():
        raise FileNotFoundError(f"Notebook not found at {args.notebook_path}.")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    executed_notebook_path = args.output_dir / EXECUTED_NOTEBOOK_NAME
    scorecard_output_path = args.output_dir / SCORECARD_OUTPUT_NAME
    _progress("Checking database schema coverage.", run_started_at)
    version_counts, stale_training_rows = _prepare_database(args.db_path)
    current_version_rows = sum(
        count for version, count in version_counts
        if version == _XG_EVENT_SCHEMA_VERSION
    )
    version_summary = ", ".join(
        f"{version or 'NULL'}={count:,}" for version, count in version_counts
    )
    _progress(f"Shot-event schema rows: {version_summary}.", run_started_at)
    _progress(
        f"Current-version rows: {current_version_rows:,}; "
        f"stale training-eligible rows: {stale_training_rows:,}.",
        run_started_at,
    )
    if current_version_rows == 0:
        raise RuntimeError(
            "No shot_events rows are at the current schema version "
            f"{_XG_EVENT_SCHEMA_VERSION!r}. Run current-schema backfill before "
            "exporting the validation scorecard."
        )
    if stale_training_rows:
        raise RuntimeError(
            f"{stale_training_rows:,} training-eligible shot_events rows remain "
            f"below the current schema version {_XG_EVENT_SCHEMA_VERSION!r}. "
            "The validation scorecard would be partial; run current-schema "
            "backfill before exporting it."
        )

    _progress(
        "Executing notebook with nbconvert. This is usually the longest step; "
        "Jupyter output and periodic heartbeats will stream below.",
        run_started_at,
    )
    _run_command_with_progress(
        [
            sys.executable,
            "-m",
            "jupyter",
            "nbconvert",
            "--to",
            "notebook",
            "--execute",
            f"--ExecutePreprocessor.timeout={args.timeout_seconds}",
            str(args.notebook_path),
            "--output",
            EXECUTED_NOTEBOOK_NAME,
            "--output-dir",
            str(args.output_dir),
        ],
        label="notebook execution",
        progress_interval_seconds=args.progress_interval_seconds,
        run_started_at=run_started_at,
    )

    _progress("Extracting scorecard block from executed notebook.", run_started_at)
    scorecard_text = _extract_scorecard_text(executed_notebook_path)
    generated_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    _progress(f"Writing scorecard artifact: {scorecard_output_path}", run_started_at)
    scorecard_output_path.write_text(
        "# Validation Scorecard (Latest Run)\n\n"
        f"Generated: {generated_at}\n\n"
        f"Database: `{args.db_path}`\n\n"
        f"Notebook: `{args.notebook_path}`\n\n"
        f"Current shot-event schema rows: {current_version_rows:,} "
        f"(`{_XG_EVENT_SCHEMA_VERSION}`)\n\n"
        "Source: `scripts/export_validation_scorecard.py` executed the "
        "validation notebook and extracted the scorecard block.\n\n"
        "```text\n"
        f"{scorecard_text}\n"
        "```\n",
        encoding="utf-8",
    )

    _progress(f"Executed notebook written to: {executed_notebook_path}", run_started_at)
    _progress(f"Scorecard artifact written to: {scorecard_output_path}", run_started_at)
    _progress("Validation scorecard export complete.", run_started_at)


if __name__ == "__main__":
    main()
