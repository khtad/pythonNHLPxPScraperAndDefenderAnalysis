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


def _run_command(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        check=True,
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )


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
    args = parser.parse_args()

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
    version_counts, stale_training_rows = _prepare_database(args.db_path)
    current_version_rows = sum(
        count for version, count in version_counts
        if version == _XG_EVENT_SCHEMA_VERSION
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

    _run_command(
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
        ]
    )

    scorecard_text = _extract_scorecard_text(executed_notebook_path)
    generated_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
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

    print(f"Executed notebook written to: {executed_notebook_path}")
    print(f"Scorecard artifact written to: {scorecard_output_path}")


if __name__ == "__main__":
    main()
