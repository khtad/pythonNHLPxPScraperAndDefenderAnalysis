"""Generate and export the Phase 2.5.4 venue-correction scorecard from SQLite.

This DB runner builds leakage-safe holdout predictions using only prior-season
venue distance corrections for each shot, then reuses the shared scorecard
formatter from ``export_venue_correction_validation.py``.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sqlite3
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss
from sklearn.preprocessing import OneHotEncoder

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from database import (  # noqa: E402
    GOAL_SHOT_EVENT_TYPE,
    MODEL_TRAINING_GAME_TYPES,
    NON_GOAL_TRAINING_SHOT_EVENT_TYPES,
    REGULAR_SEASON_GAME_TYPE,
    REGULAR_SEASON_SHOOTOUT_PERIOD_MIN,
    VALID_SHOT_TYPES,
    _MIN_TRAINING_SEASON,
    _VENUE_CORRECTION_METHOD,
    _XG_EVENT_SCHEMA_VERSION,
)
from export_venue_correction_validation import (  # noqa: E402
    DEFAULT_OUTPUT_PATH,
    format_scorecard,
)
from validation import MIN_TRAIN_SEASONS, evaluate_venue_correction_scorecard  # noqa: E402

DEFAULT_DATABASE_PATH = PROJECT_ROOT / "data" / "nhl_data.db"
MIN_RESIDUAL_SHOTS_PER_VENUE_SEASON = 400


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


def _connect_readonly(database_path: Path) -> sqlite3.Connection:
    uri = database_path.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _load_training_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    cursor = conn.cursor()
    cursor.execute(
        """SELECT se.is_goal, se.distance_to_goal, se.angle_to_goal,
                  se.shot_type, se.shooting_team_id,
                  g.season, g.venue_name, g.home_team_id
           FROM shot_events se
           JOIN games g ON se.game_id = g.game_id
           WHERE se.event_schema_version = ?
             AND g.season IS NOT NULL
             AND g.season >= ?
             AND substr(CAST(se.game_id AS TEXT), 5, 2) IN (?, ?)
             AND NOT (
                 substr(CAST(se.game_id AS TEXT), 5, 2) = ?
                 AND se.period >= ?
             )
             AND g.venue_name IS NOT NULL
             AND se.distance_to_goal IS NOT NULL
             AND se.angle_to_goal IS NOT NULL
             AND se.shot_type IS NOT NULL
             AND se.manpower_state IS NOT NULL
             AND se.score_state IS NOT NULL
             AND (
                 (se.shot_event_type = ? AND se.is_goal = 1)
                 OR (se.shot_event_type IN (?, ?) AND se.is_goal = 0)
             )
           ORDER BY g.season, se.game_id, se.event_idx""",
        (
            _XG_EVENT_SCHEMA_VERSION,
            _MIN_TRAINING_SEASON,
            *MODEL_TRAINING_GAME_TYPES,
            REGULAR_SEASON_GAME_TYPE,
            REGULAR_SEASON_SHOOTOUT_PERIOD_MIN,
            GOAL_SHOT_EVENT_TYPE,
            *NON_GOAL_TRAINING_SHOT_EVENT_TYPES,
        ),
    )
    return cursor.fetchall()


def _load_prior_correction_lookup(
    conn: sqlite3.Connection,
    correction_method: str,
) -> dict[str, list[tuple[str, float]]]:
    cursor = conn.cursor()
    cursor.execute(
        """SELECT venue_name, season, distance_adjustment
           FROM venue_bias_corrections
           WHERE correction_method = ?
             AND distance_adjustment IS NOT NULL
           ORDER BY venue_name, season""",
        (correction_method,),
    )
    lookup: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for row in cursor.fetchall():
        lookup[str(row["venue_name"])].append(
            (str(row["season"]), float(row["distance_adjustment"]))
        )
    return dict(lookup)


def _latest_prior_adjustment(
    lookup: dict[str, list[tuple[str, float]]],
    venue_name: str | None,
    season: str,
) -> float:
    if not venue_name:
        return 0.0
    prior_values = [
        (prior_season, adjustment)
        for prior_season, adjustment in lookup.get(venue_name, [])
        if prior_season < season
    ]
    if not prior_values:
        return 0.0
    return sorted(prior_values, key=lambda item: item[0])[-1][1]


def _build_feature_matrix(
    distances: np.ndarray,
    angles: np.ndarray,
    shot_types: np.ndarray,
) -> np.ndarray:
    encoder = OneHotEncoder(
        categories=[list(VALID_SHOT_TYPES)],
        sparse_output=False,
        handle_unknown="ignore",
    )
    shot_type_encoded = encoder.fit_transform(shot_types.reshape(-1, 1))
    return np.column_stack([distances, angles, shot_type_encoded])


def _run_parallel_temporal_cv(
    X_baseline: np.ndarray,
    X_corrected: np.ndarray,
    y: np.ndarray,
    row_seasons: np.ndarray,
    unique_seasons: list[str],
    is_home_attempt: np.ndarray,
    run_started_at: float,
) -> tuple[list[int], list[float], list[float], list[bool]]:
    y_true_all: list[int] = []
    baseline_prob_all: list[float] = []
    corrected_prob_all: list[float] = []
    is_home_all: list[bool] = []

    for fold_idx in range(MIN_TRAIN_SEASONS, len(unique_seasons)):
        test_season = unique_seasons[fold_idx]
        train_seasons = set(unique_seasons[:fold_idx])
        train_mask = np.isin(row_seasons, list(train_seasons))
        test_mask = row_seasons == test_season

        y_train = y[train_mask]
        y_test = y[test_mask]
        if len(y_test) == 0 or y_test.sum() == 0:
            _progress(f"Skipping fold {test_season}: no positive test labels.", run_started_at)
            continue

        baseline_model = LogisticRegression(max_iter=1000, solver="lbfgs")
        corrected_model = LogisticRegression(max_iter=1000, solver="lbfgs")
        baseline_model.fit(X_baseline[train_mask], y_train)
        corrected_model.fit(X_corrected[train_mask], y_train)

        baseline_prob = baseline_model.predict_proba(X_baseline[test_mask])[:, 1]
        corrected_prob = corrected_model.predict_proba(X_corrected[test_mask])[:, 1]

        baseline_ll = log_loss(y_test, baseline_prob)
        corrected_ll = log_loss(y_test, corrected_prob)
        _progress(
            f"Fold {test_season}: n_train={len(y_train):,} n_test={len(y_test):,} "
            f"baseline_ll={baseline_ll:.5f} corrected_ll={corrected_ll:.5f} "
            f"delta={corrected_ll - baseline_ll:+.6f}.",
            run_started_at,
        )

        y_true_all.extend(int(value) for value in y_test)
        baseline_prob_all.extend(float(value) for value in baseline_prob)
        corrected_prob_all.extend(float(value) for value in corrected_prob)
        is_home_all.extend(bool(value) for value in is_home_attempt[test_mask])

    return y_true_all, baseline_prob_all, corrected_prob_all, is_home_all


def _compute_residual_distance_z_scores(
    seasons: np.ndarray,
    venues: np.ndarray,
    corrected_distances: np.ndarray,
    min_shots: int = MIN_RESIDUAL_SHOTS_PER_VENUE_SEASON,
) -> dict[str, float]:
    grouped: dict[tuple[str, str], list[float]] = defaultdict(list)
    for season, venue, distance in zip(seasons, venues, corrected_distances):
        grouped[(str(season), str(venue))].append(float(distance))

    result: dict[str, float] = {}
    seasons_seen = sorted({season for season, _ in grouped})
    for season in seasons_seen:
        venue_means = []
        for (group_season, venue), distances in grouped.items():
            if group_season != season or len(distances) < min_shots:
                continue
            venue_means.append((venue, float(np.mean(distances))))

        if len(venue_means) < 2:
            continue

        mean_values = np.array([value for _, value in venue_means], dtype=float)
        league_mean = float(mean_values.mean())
        league_std = float(mean_values.std())
        if league_std <= 0:
            continue

        for venue, venue_mean in venue_means:
            result[f"{season}:{venue}"] = (venue_mean - league_mean) / league_std
    return result


def build_metrics(conn: sqlite3.Connection, correction_method: str) -> dict[str, Any]:
    run_started_at = time.monotonic()
    _progress("Loading training rows.", run_started_at)
    rows = _load_training_rows(conn)
    if not rows:
        raise RuntimeError("No training rows available for venue-correction validation.")
    _progress(f"Loaded {len(rows):,} training rows.", run_started_at)

    _progress("Loading venue correction parameters.", run_started_at)
    correction_lookup = _load_prior_correction_lookup(conn, correction_method)
    _progress(f"Loaded corrections for {len(correction_lookup):,} venues.", run_started_at)

    y = np.array([int(row["is_goal"]) for row in rows], dtype=int)
    distances = np.array([float(row["distance_to_goal"]) for row in rows], dtype=float)
    angles = np.array([float(row["angle_to_goal"]) for row in rows], dtype=float)
    shot_types = np.array([str(row["shot_type"]) for row in rows], dtype=object)
    seasons = np.array([str(row["season"]) for row in rows], dtype=object)
    venues = np.array([str(row["venue_name"]) for row in rows], dtype=object)
    is_home_attempt = np.array(
        [int(row["shooting_team_id"]) == int(row["home_team_id"]) for row in rows],
        dtype=bool,
    )

    adjustments = np.array(
        [
            _latest_prior_adjustment(correction_lookup, str(row["venue_name"]), str(row["season"]))
            for row in rows
        ],
        dtype=float,
    )
    corrected_distances = np.maximum(0.0, distances + adjustments)
    adjusted_rows = int(np.count_nonzero(np.abs(adjustments) > 0))
    _progress(
        f"Applied non-zero prior-season distance adjustments to {adjusted_rows:,} rows.",
        run_started_at,
    )

    _progress("Building baseline and corrected feature matrices.", run_started_at)
    X_baseline = _build_feature_matrix(distances, angles, shot_types)
    X_corrected = _build_feature_matrix(corrected_distances, angles, shot_types)

    unique_seasons = sorted(set(str(season) for season in seasons))
    _progress(
        f"Running temporal CV over {len(unique_seasons):,} seasons "
        f"with min_train={MIN_TRAIN_SEASONS}.",
        run_started_at,
    )
    y_true, baseline_prob, corrected_prob, is_home = _run_parallel_temporal_cv(
        X_baseline,
        X_corrected,
        y,
        seasons,
        unique_seasons,
        is_home_attempt,
        run_started_at,
    )
    if not y_true:
        raise RuntimeError("Temporal CV produced no holdout predictions.")

    residual_z_scores = _compute_residual_distance_z_scores(
        seasons,
        venues,
        corrected_distances,
    )
    if not residual_z_scores:
        raise RuntimeError("No residual venue distance z-scores were produced.")

    _progress(
        f"Evaluating scorecard with {len(y_true):,} holdout predictions and "
        f"{len(residual_z_scores):,} residual venue-season z-scores.",
        run_started_at,
    )
    metrics = evaluate_venue_correction_scorecard(
        y_true,
        baseline_prob,
        corrected_prob,
        is_home,
        residual_z_scores,
    )
    metrics["correction_method"] = f"{correction_method} (latest prior-season only)"
    metrics["training_snapshot"] = (
        f"schema={_XG_EVENT_SCHEMA_VERSION}; seasons={unique_seasons[0]}-{unique_seasons[-1]}; "
        f"rows={len(rows):,}; adjusted_rows={adjusted_rows:,}"
    )
    metrics["notes"] = (
        "Generated from live SQLite data with forward-chaining temporal CV. "
        "Each shot uses the latest venue distance adjustment from a season before "
        "the shot's season; same-season venue corrections are not used for holdout "
        "rows. Residual z-scores are venue-season corrected-distance mean z-scores, "
        "because the implemented correction targets distance bias rather than shot-count bias."
    )
    return metrics


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export the live DB venue-correction validation scorecard."
    )
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DATABASE_PATH)
    parser.add_argument("--output-path", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument(
        "--correction-method",
        default=_VENUE_CORRECTION_METHOD,
        help="Correction method name from venue_bias_corrections.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    run_started_at = time.monotonic()
    _progress("Starting DB-backed venue-correction scorecard export.", run_started_at)
    _progress(f"Database path: {args.db_path}", run_started_at)
    _progress(f"Output path: {args.output_path}", run_started_at)
    _progress(f"Correction method: {args.correction_method}", run_started_at)

    if not args.db_path.exists():
        raise FileNotFoundError(f"Database not found: {args.db_path}")

    with _connect_readonly(args.db_path) as conn:
        metrics = build_metrics(conn, args.correction_method)

    scorecard = format_scorecard(metrics)
    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    args.output_path.write_text(scorecard, encoding="utf-8")
    _progress(
        f"Venue-correction scorecard written to: {args.output_path}",
        run_started_at,
    )
    _progress("DB-backed venue-correction scorecard export complete.", run_started_at)


if __name__ == "__main__":
    main()
