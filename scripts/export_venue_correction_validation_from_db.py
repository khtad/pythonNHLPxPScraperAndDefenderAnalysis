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
    BLOCKED_SHOT_EVENT_TYPE,
    GOAL_SHOT_EVENT_TYPE,
    MODEL_TRAINING_GAME_TYPES,
    NON_GOAL_TRAINING_SHOT_EVENT_TYPES,
    REGULAR_SEASON_GAME_TYPE,
    REGULAR_SEASON_SHOOTOUT_PERIOD_MIN,
    VALID_SHOT_EVENT_TYPES,
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
from venue_bias import (  # noqa: E402
    ANOMALY_REAL_SCOREKEEPER_REGIME_SUPPORTED,
    EVENT_FREQUENCY_GROUP_ALL_ATTEMPTS,
    EVENT_FREQUENCY_GROUP_BLOCKED_SHOTS,
    EVENT_FREQUENCY_GROUP_TRAINING_ATTEMPTS,
    EVENT_FREQUENCY_GROUPS,
    EVENT_FREQUENCY_SCOPE_REGULAR_SEASON,
    EVENT_FREQUENCY_SCOPE_TRAINING_CONTRACT,
    EVENT_FREQUENCY_SCOPES,
    PRIMARY_EVENT_FREQUENCY_GROUP,
    PRIMARY_EVENT_FREQUENCY_SCOPE,
    annotate_event_frequency_anomalies,
    compute_event_frequency_diagnostics,
    compute_paired_away_frequency_comparisons,
    primary_event_frequency_residual_z_scores,
    top_event_frequency_anomalies,
)

DEFAULT_DATABASE_PATH = PROJECT_ROOT / "data" / "nhl_data.db"
MIN_RESIDUAL_SHOTS_PER_VENUE_SEASON = 400
EVENT_FREQUENCY_REPORT_LIMIT = 10


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


def load_event_frequency_game_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for game_type_scope in EVENT_FREQUENCY_SCOPES:
        for event_group in EVENT_FREQUENCY_GROUPS:
            rows.extend(
                _load_event_frequency_game_rows_for_slice(
                    conn,
                    game_type_scope,
                    event_group,
                )
            )
    return rows


def _load_event_frequency_game_rows_for_slice(
    conn: sqlite3.Connection,
    game_type_scope: str,
    event_group: str,
) -> list[dict[str, Any]]:
    event_predicate, event_params = _event_frequency_join_predicate(
        game_type_scope,
        event_group,
    )
    game_predicate, game_params = _event_frequency_game_predicate(game_type_scope)
    cursor = conn.cursor()
    cursor.execute(
        f"""SELECT ? AS game_type_scope,
                  ? AS event_group,
                  g.game_id, g.season, g.venue_name,
                  g.home_team_id, g.away_team_id,
                  COUNT(se.shot_event_id) AS event_count,
                  SUM(CASE WHEN se.shooting_team_id = g.home_team_id THEN 1 ELSE 0 END)
                      AS home_event_count,
                  SUM(CASE WHEN se.shooting_team_id = g.away_team_id THEN 1 ELSE 0 END)
                      AS away_event_count
           FROM games g
           LEFT JOIN shot_events se
             ON se.game_id = g.game_id
            {event_predicate}
           WHERE g.season IS NOT NULL
             AND g.season >= ?
             AND g.venue_name IS NOT NULL
             {game_predicate}
           GROUP BY g.game_id, g.season, g.venue_name,
                    g.home_team_id, g.away_team_id
           ORDER BY g.season, g.venue_name, g.game_id""",
        (
            game_type_scope,
            event_group,
            *event_params,
            _MIN_TRAINING_SEASON,
            *game_params,
        ),
    )
    return [dict(row) for row in cursor.fetchall()]


def _event_frequency_game_predicate(game_type_scope: str) -> tuple[str, tuple[Any, ...]]:
    if game_type_scope == EVENT_FREQUENCY_SCOPE_REGULAR_SEASON:
        return "AND substr(CAST(g.game_id AS TEXT), 5, 2) = ?", (
            REGULAR_SEASON_GAME_TYPE,
        )
    if game_type_scope == EVENT_FREQUENCY_SCOPE_TRAINING_CONTRACT:
        placeholders = ", ".join("?" for _ in MODEL_TRAINING_GAME_TYPES)
        return (
            f"AND substr(CAST(g.game_id AS TEXT), 5, 2) IN ({placeholders})",
            tuple(MODEL_TRAINING_GAME_TYPES),
        )
    raise ValueError(f"Unsupported event-frequency scope: {game_type_scope}")


def _event_frequency_join_predicate(
    game_type_scope: str,
    event_group: str,
) -> tuple[str, tuple[Any, ...]]:
    scope_predicate, scope_params = _event_frequency_event_scope_predicate(
        game_type_scope
    )
    group_predicate, group_params = _event_frequency_group_predicate(event_group)
    return (
        f"{scope_predicate} {group_predicate}",
        (*scope_params, *group_params),
    )


def _event_frequency_event_scope_predicate(
    game_type_scope: str,
) -> tuple[str, tuple[Any, ...]]:
    if game_type_scope == EVENT_FREQUENCY_SCOPE_REGULAR_SEASON:
        return "AND se.period < ?", (REGULAR_SEASON_SHOOTOUT_PERIOD_MIN,)
    if game_type_scope == EVENT_FREQUENCY_SCOPE_TRAINING_CONTRACT:
        return (
            """AND NOT (
                   substr(CAST(g.game_id AS TEXT), 5, 2) = ?
                   AND se.period >= ?
               )""",
            (REGULAR_SEASON_GAME_TYPE, REGULAR_SEASON_SHOOTOUT_PERIOD_MIN),
        )
    raise ValueError(f"Unsupported event-frequency scope: {game_type_scope}")


def _event_frequency_group_predicate(
    event_group: str,
) -> tuple[str, tuple[Any, ...]]:
    if event_group == EVENT_FREQUENCY_GROUP_TRAINING_ATTEMPTS:
        return (
            """AND se.event_schema_version = ?
               AND se.distance_to_goal IS NOT NULL
               AND se.angle_to_goal IS NOT NULL
               AND se.shot_type IS NOT NULL
               AND se.manpower_state IS NOT NULL
               AND se.score_state IS NOT NULL
               AND (
                   (se.shot_event_type = ? AND se.is_goal = 1)
                   OR (se.shot_event_type IN (?, ?) AND se.is_goal = 0)
               )""",
            (
                _XG_EVENT_SCHEMA_VERSION,
                GOAL_SHOT_EVENT_TYPE,
                *NON_GOAL_TRAINING_SHOT_EVENT_TYPES,
            ),
        )
    if event_group == EVENT_FREQUENCY_GROUP_BLOCKED_SHOTS:
        return (
            """AND se.event_schema_version = ?
               AND se.shot_event_type = ?
               AND se.is_goal = 0""",
            (_XG_EVENT_SCHEMA_VERSION, BLOCKED_SHOT_EVENT_TYPE),
        )
    if event_group == EVENT_FREQUENCY_GROUP_ALL_ATTEMPTS:
        placeholders = ", ".join("?" for _ in VALID_SHOT_EVENT_TYPES)
        return (
            f"""AND se.event_schema_version = ?
                AND se.shot_event_type IN ({placeholders})""",
            (_XG_EVENT_SCHEMA_VERSION, *VALID_SHOT_EVENT_TYPES),
        )
    raise ValueError(f"Unsupported event-frequency group: {event_group}")


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

    _progress("Loading event-frequency game counts.", run_started_at)
    frequency_game_rows = load_event_frequency_game_rows(conn)
    _progress(
        f"Loaded {len(frequency_game_rows):,} game/group/scope frequency rows.",
        run_started_at,
    )

    _progress("Computing event-frequency diagnostics and paired comparisons.", run_started_at)
    frequency_diagnostics = compute_event_frequency_diagnostics(frequency_game_rows)
    paired_frequency = compute_paired_away_frequency_comparisons(frequency_game_rows)
    annotated_frequency = annotate_event_frequency_anomalies(
        frequency_diagnostics,
        paired_frequency,
    )
    frequency_residual_z_scores = primary_event_frequency_residual_z_scores(
        annotated_frequency
    )
    if not frequency_residual_z_scores:
        raise RuntimeError("No primary event-frequency residual z-scores were produced.")
    frequency_candidates = [
        row for row in annotated_frequency if row.get("candidate_anomaly")
    ]
    supported_frequency_regimes = [
        row for row in frequency_candidates
        if row["anomaly_classification"] == ANOMALY_REAL_SCOREKEEPER_REGIME_SUPPORTED
    ]
    _progress(
        f"Computed {len(frequency_residual_z_scores):,} primary frequency residuals; "
        f"{len(frequency_candidates):,} candidate anomalies, "
        f"{len(supported_frequency_regimes):,} supported real-regime candidates.",
        run_started_at,
    )

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
        frequency_residual_z_scores,
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
        "rows. Distance residual z-scores are venue-season corrected-distance mean "
        "z-scores. Event-frequency residual z-scores use sample-adequate "
        "regular-season training attempts as the primary gate; blocked-shot and "
        "all-attempt frequencies are reported as diagnostics and remain outside "
        "the current shot-level xG training contract."
    )
    metrics["event_frequency_primary_scope"] = PRIMARY_EVENT_FREQUENCY_SCOPE
    metrics["event_frequency_primary_group"] = PRIMARY_EVENT_FREQUENCY_GROUP
    metrics["event_frequency_candidate_count"] = len(frequency_candidates)
    metrics["event_frequency_supported_count"] = len(supported_frequency_regimes)
    metrics["event_frequency_top_anomalies"] = top_event_frequency_anomalies(
        annotated_frequency,
        limit=EVENT_FREQUENCY_REPORT_LIMIT,
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
