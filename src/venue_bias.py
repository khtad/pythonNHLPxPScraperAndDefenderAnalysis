"""Venue scorekeeper-bias diagnostics shared by scripts and notebooks."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
from scipy import stats as sp_stats


EVENT_FREQUENCY_GROUP_TRAINING_ATTEMPTS = "training_attempts"
EVENT_FREQUENCY_GROUP_BLOCKED_SHOTS = "blocked_shots"
EVENT_FREQUENCY_GROUP_ALL_ATTEMPTS = "all_attempts"
EVENT_FREQUENCY_GROUPS = (
    EVENT_FREQUENCY_GROUP_TRAINING_ATTEMPTS,
    EVENT_FREQUENCY_GROUP_BLOCKED_SHOTS,
    EVENT_FREQUENCY_GROUP_ALL_ATTEMPTS,
)

EVENT_FREQUENCY_SCOPE_REGULAR_SEASON = "regular_season"
EVENT_FREQUENCY_SCOPE_TRAINING_CONTRACT = "training_contract"
EVENT_FREQUENCY_SCOPES = (
    EVENT_FREQUENCY_SCOPE_REGULAR_SEASON,
    EVENT_FREQUENCY_SCOPE_TRAINING_CONTRACT,
)

PRIMARY_EVENT_FREQUENCY_GROUP = EVENT_FREQUENCY_GROUP_TRAINING_ATTEMPTS
PRIMARY_EVENT_FREQUENCY_SCOPE = EVENT_FREQUENCY_SCOPE_REGULAR_SEASON

EVENT_FREQUENCY_Z_SCORE_THRESHOLD = 2.0
EVENT_FREQUENCY_MIN_GAMES_PLAYED = 20
EVENT_FREQUENCY_MIN_PAIRED_TEAM_SEASONS = 10
EVENT_FREQUENCY_MIN_ABS_COHENS_D = 0.2
EVENT_FREQUENCY_BOOTSTRAP_SAMPLES = 10_000
EVENT_FREQUENCY_BOOTSTRAP_ALPHA = 0.05
EVENT_FREQUENCY_BOOTSTRAP_SEED = 42

VENUE_REGIME_METRIC_DISTANCE = "distance_location"
VENUE_REGIME_METRIC_EVENT_FREQUENCY = "event_frequency"
VENUE_REGIME_RESIDUAL_FIELD = "residual_z_score"
VENUE_REGIME_ROLLING_WINDOW_SEASONS = 3
VENUE_REGIME_CENTERED_WINDOW_RADIUS = 1
VENUE_REGIME_PERSISTENT_MIN_SEASONS = 2
VENUE_REGIME_MAX_ANOMALOUS_POPULATION_SHARE = 0.2

VENUE_REGIME_NOT_FLAGGED = "not_flagged"
VENUE_REGIME_PERSISTENT_BIAS = "persistent_bias"
VENUE_REGIME_TEMPORARY_SUPPORTED = "temporary_supported_regime"
VENUE_REGIME_UNEXPLAINED_OR_CONFOUNDED = "unexplained_or_confounded"
VENUE_REGIME_INSUFFICIENT_EVIDENCE = "insufficient_evidence"
VENUE_REGIME_POPULATION_SHIFT = "population_shift_detected"

ANOMALY_NOT_FLAGGED = "not_flagged"
ANOMALY_CALCULATION_ERROR_SUSPECTED = "calculation_error_suspected"
ANOMALY_REAL_SCOREKEEPER_REGIME_SUPPORTED = "real_scorekeeper_regime_supported"
ANOMALY_HOCKEY_CONTEXT_CONFOUNDED = "hockey_context_confounded"
ANOMALY_INSUFFICIENT_EVIDENCE = "insufficient_evidence"

KNOWN_SCOREKEEPER_REGIME_NOTES = {
    "Madison Square Garden": "Known historical generous scorekeeper candidate.",
    "BB&T Center": "Florida known generous scorekeeper candidate.",
    "BankAtlantic Center": "Florida known generous scorekeeper candidate.",
    "Amerant Bank Arena": "Florida known generous scorekeeper candidate.",
    "FLA Live Arena": "Florida known generous scorekeeper candidate.",
    "Bridgestone Arena": "Nashville known generous scorekeeper candidate.",
    "Gaylord Entertainment Center": "Nashville known generous scorekeeper candidate.",
    "Sommet Center": "Nashville known generous scorekeeper candidate.",
    "Nashville Arena": "Nashville known generous scorekeeper candidate.",
}


def compute_event_frequency_diagnostics(
    game_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Return per venue-season event-frequency diagnostics.

    ``game_rows`` must contain one row per game/event-group/scope with these
    fields: game_type_scope, event_group, season, venue_name, game_id,
    event_count, home_event_count, and away_event_count.
    """
    grouped: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for row in game_rows:
        venue_name = str(row["venue_name"])
        key = (
            str(row["game_type_scope"]),
            str(row["event_group"]),
            str(row["season"]),
            venue_name,
        )
        accumulator = grouped.setdefault(
            key,
            {
                "game_ids": set(),
                "event_count": 0,
                "home_event_count": 0,
                "away_event_count": 0,
            },
        )
        accumulator["game_ids"].add(row["game_id"])
        accumulator["event_count"] += int(row.get("event_count") or 0)
        accumulator["home_event_count"] += int(row.get("home_event_count") or 0)
        accumulator["away_event_count"] += int(row.get("away_event_count") or 0)

    diagnostics: list[dict[str, Any]] = []
    for (scope, event_group, season, venue_name), values in grouped.items():
        games_played = len(values["game_ids"])
        event_count = int(values["event_count"])
        events_per_game = event_count / games_played if games_played else np.nan
        diagnostics.append(
            {
                "game_type_scope": scope,
                "event_group": event_group,
                "season": season,
                "venue_name": venue_name,
                "games_played": int(games_played),
                "event_count": event_count,
                "events_per_game": float(events_per_game),
                "home_event_count": int(values["home_event_count"]),
                "away_event_count": int(values["away_event_count"]),
                "league_events_per_game_mean": None,
                "league_events_per_game_stddev": None,
                "frequency_z_score": None,
                "sample_adequate": bool(games_played >= EVENT_FREQUENCY_MIN_GAMES_PLAYED),
            }
        )

    baselines: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    for row in diagnostics:
        if row["sample_adequate"] and np.isfinite(row["events_per_game"]):
            baselines[
                (row["game_type_scope"], row["event_group"], row["season"])
            ].append(row["events_per_game"])

    for row in diagnostics:
        values = np.asarray(
            baselines[(row["game_type_scope"], row["event_group"], row["season"])],
            dtype=float,
        )
        if len(values) < 2:
            continue
        league_mean = float(values.mean())
        league_std = float(values.std())
        row["league_events_per_game_mean"] = league_mean
        row["league_events_per_game_stddev"] = league_std
        if league_std > 0 and np.isfinite(row["events_per_game"]):
            row["frequency_z_score"] = float(
                (row["events_per_game"] - league_mean) / league_std
            )

    return sorted(
        diagnostics,
        key=lambda item: (
            item["game_type_scope"],
            item["event_group"],
            item["season"],
            item["venue_name"],
        ),
    )


def compute_paired_away_frequency_comparisons(
    game_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Compare visiting-team event rates at a venue against elsewhere.

    Each comparison controls for visitor team-season by pairing the visiting
    team's rate at the venue with that same team's away-game rate at other
    venues in the same season.
    """
    rows_by_slice: dict[tuple[str, str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in game_rows:
        rows_by_slice[
            (str(row["game_type_scope"]), str(row["event_group"]), str(row["season"]))
        ].append(row)

    comparisons: list[dict[str, Any]] = []
    for (scope, event_group, season), rows in rows_by_slice.items():
        venues = sorted({str(row["venue_name"]) for row in rows})
        for venue_name in venues:
            at_venue: dict[int, list[int]] = defaultdict(lambda: [0, 0])
            elsewhere: dict[int, list[int]] = defaultdict(lambda: [0, 0])
            for row in rows:
                away_team_id = int(row["away_team_id"])
                target = at_venue if str(row["venue_name"]) == venue_name else elsewhere
                target[away_team_id][0] += int(row.get("away_event_count") or 0)
                target[away_team_id][1] += 1

            diffs = []
            for away_team_id, at_values in at_venue.items():
                elsewhere_values = elsewhere.get(away_team_id)
                if not elsewhere_values:
                    continue
                if at_values[1] <= 0 or elsewhere_values[1] <= 0:
                    continue
                at_rate = at_values[0] / at_values[1]
                elsewhere_rate = elsewhere_values[0] / elsewhere_values[1]
                diffs.append(at_rate - elsewhere_rate)

            summary = _summarize_paired_diffs(diffs)
            comparisons.append(
                {
                    "game_type_scope": scope,
                    "event_group": event_group,
                    "season": season,
                    "venue_name": venue_name,
                    **summary,
                }
            )

    return sorted(
        comparisons,
        key=lambda item: (
            item["game_type_scope"],
            item["event_group"],
            item["season"],
            item["venue_name"],
        ),
    )


def annotate_event_frequency_anomalies(
    diagnostics: Sequence[Mapping[str, Any]],
    paired_comparisons: Sequence[Mapping[str, Any]],
    z_score_threshold: float = EVENT_FREQUENCY_Z_SCORE_THRESHOLD,
) -> list[dict[str, Any]]:
    """Add anomaly classification and paired-comparison evidence to diagnostics."""
    comparison_lookup = {
        _diagnostic_key(row): row for row in paired_comparisons
    }
    annotated: list[dict[str, Any]] = []
    for row in diagnostics:
        item = dict(row)
        comparison = dict(comparison_lookup.get(_diagnostic_key(row), {}))
        item.update(_prefixed_comparison_fields(comparison))
        known_note = KNOWN_SCOREKEEPER_REGIME_NOTES.get(str(row["venue_name"]), "")
        item["known_scorekeeper_prior"] = bool(known_note)
        item["known_scorekeeper_prior_note"] = known_note
        item["candidate_anomaly"] = _is_candidate_frequency_anomaly(
            item.get("frequency_z_score"),
            z_score_threshold,
        )
        item["anomaly_classification"] = _classify_event_frequency_anomaly(item)
        annotated.append(item)
    return annotated


def primary_event_frequency_residual_z_scores(
    annotated_diagnostics: Sequence[Mapping[str, Any]],
) -> dict[str, float]:
    """Return sample-adequate z-scores for the primary frequency gate."""
    result: dict[str, float] = {}
    for row in annotated_diagnostics:
        if row["game_type_scope"] != PRIMARY_EVENT_FREQUENCY_SCOPE:
            continue
        if row["event_group"] != PRIMARY_EVENT_FREQUENCY_GROUP:
            continue
        if not row.get("sample_adequate"):
            continue
        z_score = row.get("frequency_z_score")
        if z_score is None or not np.isfinite(float(z_score)):
            continue
        result[f"{row['season']}:{row['venue_name']}"] = float(z_score)
    return result


def residual_z_score_rows(
    residual_z_scores: Mapping[str, float],
    metric_name: str,
) -> list[dict[str, Any]]:
    """Convert ``season:venue`` z-score mappings into regime diagnostic rows."""
    rows: list[dict[str, Any]] = []
    for venue_season, z_score in residual_z_scores.items():
        season, venue_name = _split_venue_season_label(str(venue_season))
        rows.append(
            {
                "metric_name": metric_name,
                "season": season,
                "venue_name": venue_name,
                VENUE_REGIME_RESIDUAL_FIELD: float(z_score),
                "sample_adequate": True,
                "evidence_supports_regime": False,
                "known_scorekeeper_prior": bool(
                    KNOWN_SCOREKEEPER_REGIME_NOTES.get(venue_name, "")
                ),
            }
        )
    return rows


def compute_prior_rolling_bias_estimates(
    residual_rows: Sequence[Mapping[str, Any]],
    value_field: str = VENUE_REGIME_RESIDUAL_FIELD,
    sample_size_field: str | None = None,
    window_seasons: int = VENUE_REGIME_ROLLING_WINDOW_SEASONS,
) -> list[dict[str, Any]]:
    """Add prior-only rolling bias estimates by venue.

    The estimate for season ``t`` only uses earlier rows for the same venue,
    making it safe for production correction policies that cannot see the
    current or future season.
    """
    if window_seasons <= 0:
        raise ValueError("window_seasons must be positive.")

    enriched_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    for venue_name, rows in _rows_grouped_by_venue(residual_rows).items():
        history: list[Mapping[str, Any]] = []
        for row in rows:
            eligible_history = _eligible_bias_rows(history, value_field)
            window_history = eligible_history[-window_seasons:]
            item = dict(row)
            item["prior_rolling_bias"] = _weighted_mean(
                window_history,
                value_field,
                sample_size_field,
            )
            item["prior_rolling_observation_count"] = len(window_history)
            item["prior_rolling_window_seasons"] = window_seasons
            item["prior_rolling_uses_future"] = False
            enriched_by_key[_regime_row_key(item, venue_name)] = item
            history.append(row)
    return _sort_regime_rows(enriched_by_key.values())


def compute_centered_rolling_bias_estimates(
    residual_rows: Sequence[Mapping[str, Any]],
    value_field: str = VENUE_REGIME_RESIDUAL_FIELD,
    sample_size_field: str | None = None,
    window_radius: int = VENUE_REGIME_CENTERED_WINDOW_RADIUS,
) -> list[dict[str, Any]]:
    """Add centered rolling bias estimates for exploratory diagnostics.

    Centered estimates can use surrounding future seasons and must not feed a
    production correction. They are useful for identifying temporary historical
    regimes that later return toward baseline.
    """
    if window_radius < 0:
        raise ValueError("window_radius must be non-negative.")

    enriched_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    for venue_name, rows in _rows_grouped_by_venue(residual_rows).items():
        for index, row in enumerate(rows):
            window_start = max(0, index - window_radius)
            window_end = min(len(rows), index + window_radius + 1)
            window_rows = _eligible_bias_rows(
                rows[window_start:window_end],
                value_field,
            )
            item = dict(row)
            item["centered_rolling_bias"] = _weighted_mean(
                window_rows,
                value_field,
                sample_size_field,
            )
            item["centered_rolling_observation_count"] = len(window_rows)
            item["centered_rolling_window_radius"] = window_radius
            item["centered_rolling_uses_future"] = window_end > index + 1
            enriched_by_key[_regime_row_key(item, venue_name)] = item
    return _sort_regime_rows(enriched_by_key.values())


def classify_rolling_venue_regimes(
    residual_rows: Sequence[Mapping[str, Any]],
    z_score_threshold: float = EVENT_FREQUENCY_Z_SCORE_THRESHOLD,
    max_population_anomaly_share: float = (
        VENUE_REGIME_MAX_ANOMALOUS_POPULATION_SHARE
    ),
    persistent_min_seasons: int = VENUE_REGIME_PERSISTENT_MIN_SEASONS,
) -> list[dict[str, Any]]:
    """Classify venue-season residuals into rolling scorer-regime labels."""
    if z_score_threshold <= 0:
        raise ValueError("z_score_threshold must be positive.")
    if persistent_min_seasons <= 0:
        raise ValueError("persistent_min_seasons must be positive.")

    prior_rows = compute_prior_rolling_bias_estimates(residual_rows)
    rows = compute_centered_rolling_bias_estimates(prior_rows)
    population_shares = _population_anomaly_shares(rows, z_score_threshold)
    directional_counts = _prior_directional_candidate_counts(
        rows,
        z_score_threshold,
    )

    classified: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        z_score = _finite_float_or_none(item.get(VENUE_REGIME_RESIDUAL_FIELD))
        candidate = bool(
            z_score is not None and abs(z_score) >= z_score_threshold
        )
        sample_adequate = bool(item.get("sample_adequate", True))
        population_share = population_shares.get(str(item["season"]))
        same_direction_count = directional_counts.get(_regime_row_key(item), 0)

        item["candidate_regime"] = candidate
        item["population_anomaly_share"] = population_share
        item["max_allowed_population_anomaly_share"] = (
            max_population_anomaly_share
        )
        item["same_direction_candidate_seasons"] = same_direction_count
        item["regime_classification"] = _classify_regime_row(
            item,
            z_score,
            candidate,
            sample_adequate,
            population_share,
            max_population_anomaly_share,
            persistent_min_seasons,
            same_direction_count,
        )
        classified.append(item)
    return _sort_regime_rows(classified)


def primary_event_frequency_regime_diagnostics(
    annotated_diagnostics: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Return rolling-regime diagnostics for the primary frequency gate."""
    rows: list[dict[str, Any]] = []
    for row in annotated_diagnostics:
        if row["game_type_scope"] != PRIMARY_EVENT_FREQUENCY_SCOPE:
            continue
        if row["event_group"] != PRIMARY_EVENT_FREQUENCY_GROUP:
            continue
        if not row.get("sample_adequate"):
            continue
        z_score = _finite_float_or_none(row.get("frequency_z_score"))
        if z_score is None:
            continue
        rows.append(
            {
                "metric_name": VENUE_REGIME_METRIC_EVENT_FREQUENCY,
                "season": str(row["season"]),
                "venue_name": str(row["venue_name"]),
                VENUE_REGIME_RESIDUAL_FIELD: z_score,
                "sample_adequate": bool(row.get("sample_adequate")),
                "evidence_supports_regime": bool(
                    row.get("anomaly_classification")
                    == ANOMALY_REAL_SCOREKEEPER_REGIME_SUPPORTED
                ),
                "known_scorekeeper_prior": bool(
                    row.get("known_scorekeeper_prior", False)
                ),
                "anomaly_classification": row.get("anomaly_classification"),
                "paired_mean_diff_per_game": row.get("paired_mean_diff_per_game"),
                "paired_bootstrap_ci_low": row.get("paired_bootstrap_ci_low"),
                "paired_bootstrap_ci_high": row.get("paired_bootstrap_ci_high"),
                "paired_cohens_d": row.get("paired_cohens_d"),
            }
        )
    return classify_rolling_venue_regimes(rows)


def summarize_venue_regime_counts(
    regime_diagnostics: Sequence[Mapping[str, Any]],
) -> dict[str, int]:
    """Count regime classifications for a diagnostic row set."""
    counts = {
        VENUE_REGIME_NOT_FLAGGED: 0,
        VENUE_REGIME_PERSISTENT_BIAS: 0,
        VENUE_REGIME_TEMPORARY_SUPPORTED: 0,
        VENUE_REGIME_UNEXPLAINED_OR_CONFOUNDED: 0,
        VENUE_REGIME_INSUFFICIENT_EVIDENCE: 0,
        VENUE_REGIME_POPULATION_SHIFT: 0,
    }
    for row in regime_diagnostics:
        label = str(row.get("regime_classification", VENUE_REGIME_NOT_FLAGGED))
        counts[label] = counts.get(label, 0) + 1
    return counts


def top_venue_regime_diagnostics(
    regime_diagnostics: Sequence[Mapping[str, Any]],
    limit: int = 10,
    candidates_only: bool = True,
) -> list[dict[str, Any]]:
    """Return the largest rolling-regime residuals for artifact display."""
    rows = [
        dict(row)
        for row in regime_diagnostics
        if _finite_float_or_none(row.get(VENUE_REGIME_RESIDUAL_FIELD)) is not None
        and (not candidates_only or row.get("candidate_regime"))
    ]
    rows.sort(
        key=lambda row: abs(float(row[VENUE_REGIME_RESIDUAL_FIELD])),
        reverse=True,
    )
    return [
        {
            "metric_name": row.get("metric_name", "unspecified"),
            "season": row["season"],
            "venue_name": row["venue_name"],
            VENUE_REGIME_RESIDUAL_FIELD: row[VENUE_REGIME_RESIDUAL_FIELD],
            "regime_classification": row.get(
                "regime_classification",
                VENUE_REGIME_NOT_FLAGGED,
            ),
            "prior_rolling_bias": row.get("prior_rolling_bias"),
            "centered_rolling_bias": row.get("centered_rolling_bias"),
            "centered_rolling_uses_future": row.get(
                "centered_rolling_uses_future",
                False,
            ),
            "population_anomaly_share": row.get("population_anomaly_share"),
            "same_direction_candidate_seasons": row.get(
                "same_direction_candidate_seasons",
                0,
            ),
            "evidence_supports_regime": row.get(
                "evidence_supports_regime",
                False,
            ),
            "known_scorekeeper_prior": row.get(
                "known_scorekeeper_prior",
                False,
            ),
        }
        for row in rows[:limit]
    ]


def top_event_frequency_anomalies(
    annotated_diagnostics: Sequence[Mapping[str, Any]],
    limit: int = 10,
    candidates_only: bool = True,
) -> list[dict[str, Any]]:
    """Return the largest event-frequency residuals for artifact display."""
    rows = [
        dict(row)
        for row in annotated_diagnostics
        if row.get("frequency_z_score") is not None
        and np.isfinite(float(row["frequency_z_score"]))
        and (not candidates_only or row.get("candidate_anomaly"))
    ]
    rows.sort(key=lambda row: abs(float(row["frequency_z_score"])), reverse=True)
    return [
        {
            "game_type_scope": row["game_type_scope"],
            "event_group": row["event_group"],
            "season": row["season"],
            "venue_name": row["venue_name"],
            "games_played": row["games_played"],
            "event_count": row["event_count"],
            "events_per_game": row["events_per_game"],
            "frequency_z_score": row["frequency_z_score"],
            "paired_away_team_seasons": row.get("paired_away_team_seasons", 0),
            "paired_mean_diff_per_game": row.get("paired_mean_diff_per_game"),
            "paired_bootstrap_ci_low": row.get("paired_bootstrap_ci_low"),
            "paired_bootstrap_ci_high": row.get("paired_bootstrap_ci_high"),
            "paired_wilcoxon_p_value": row.get("paired_wilcoxon_p_value"),
            "paired_cohens_d": row.get("paired_cohens_d"),
            "paired_sample_adequate": row.get("paired_sample_adequate", False),
            "known_scorekeeper_prior": row.get("known_scorekeeper_prior", False),
            "anomaly_classification": row["anomaly_classification"],
        }
        for row in rows[:limit]
    ]


def _summarize_paired_diffs(diffs: Iterable[float]) -> dict[str, Any]:
    diff_array = np.asarray(list(diffs), dtype=float)
    diff_array = diff_array[np.isfinite(diff_array)]
    n_pairs = int(len(diff_array))
    if n_pairs == 0:
        return {
            "paired_away_team_seasons": 0,
            "paired_mean_diff_per_game": None,
            "paired_bootstrap_ci_low": None,
            "paired_bootstrap_ci_high": None,
            "paired_wilcoxon_p_value": None,
            "paired_cohens_d": None,
            "paired_sample_adequate": False,
        }

    mean_diff = float(diff_array.mean())
    ci_low, ci_high = _bootstrap_mean_ci(diff_array)
    p_value = None
    if n_pairs >= 2 and not np.allclose(diff_array, 0.0):
        p_value = float(sp_stats.wilcoxon(diff_array).pvalue)

    cohens_d = 0.0
    if n_pairs >= 2:
        stddev = float(diff_array.std(ddof=1))
        if stddev > 0:
            cohens_d = mean_diff / stddev

    return {
        "paired_away_team_seasons": n_pairs,
        "paired_mean_diff_per_game": mean_diff,
        "paired_bootstrap_ci_low": ci_low,
        "paired_bootstrap_ci_high": ci_high,
        "paired_wilcoxon_p_value": p_value,
        "paired_cohens_d": float(cohens_d),
        "paired_sample_adequate": bool(
            n_pairs >= EVENT_FREQUENCY_MIN_PAIRED_TEAM_SEASONS
        ),
    }


def _bootstrap_mean_ci(values: np.ndarray) -> tuple[float, float]:
    if len(values) == 1:
        only_value = float(values[0])
        return only_value, only_value
    rng = np.random.default_rng(seed=EVENT_FREQUENCY_BOOTSTRAP_SEED)
    samples = rng.choice(
        values,
        size=(EVENT_FREQUENCY_BOOTSTRAP_SAMPLES, len(values)),
        replace=True,
    )
    means = samples.mean(axis=1)
    return (
        float(np.percentile(means, 100 * EVENT_FREQUENCY_BOOTSTRAP_ALPHA / 2)),
        float(np.percentile(means, 100 * (1 - EVENT_FREQUENCY_BOOTSTRAP_ALPHA / 2))),
    )


def _diagnostic_key(row: Mapping[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(row["game_type_scope"]),
        str(row["event_group"]),
        str(row["season"]),
        str(row["venue_name"]),
    )


def _prefixed_comparison_fields(comparison: Mapping[str, Any]) -> dict[str, Any]:
    if not comparison:
        return {
            "paired_away_team_seasons": 0,
            "paired_mean_diff_per_game": None,
            "paired_bootstrap_ci_low": None,
            "paired_bootstrap_ci_high": None,
            "paired_wilcoxon_p_value": None,
            "paired_cohens_d": None,
            "paired_sample_adequate": False,
        }
    return {
        "paired_away_team_seasons": comparison["paired_away_team_seasons"],
        "paired_mean_diff_per_game": comparison["paired_mean_diff_per_game"],
        "paired_bootstrap_ci_low": comparison["paired_bootstrap_ci_low"],
        "paired_bootstrap_ci_high": comparison["paired_bootstrap_ci_high"],
        "paired_wilcoxon_p_value": comparison["paired_wilcoxon_p_value"],
        "paired_cohens_d": comparison["paired_cohens_d"],
        "paired_sample_adequate": comparison["paired_sample_adequate"],
    }


def _is_candidate_frequency_anomaly(
    z_score: Any,
    z_score_threshold: float,
) -> bool:
    if z_score is None:
        return False
    z_score_float = float(z_score)
    return bool(np.isfinite(z_score_float) and abs(z_score_float) > z_score_threshold)


def _classify_event_frequency_anomaly(row: Mapping[str, Any]) -> str:
    if not row["candidate_anomaly"]:
        return ANOMALY_NOT_FLAGGED
    z_score = row.get("frequency_z_score")
    if z_score is None or not np.isfinite(float(z_score)):
        return ANOMALY_CALCULATION_ERROR_SUSPECTED
    if row["games_played"] <= 0 or row["event_count"] < 0:
        return ANOMALY_CALCULATION_ERROR_SUSPECTED
    if not row["sample_adequate"] or not row["paired_sample_adequate"]:
        return ANOMALY_INSUFFICIENT_EVIDENCE
    if _paired_evidence_supports_z_score(row):
        return ANOMALY_REAL_SCOREKEEPER_REGIME_SUPPORTED
    return ANOMALY_HOCKEY_CONTEXT_CONFOUNDED


def _paired_evidence_supports_z_score(row: Mapping[str, Any]) -> bool:
    ci_low = row.get("paired_bootstrap_ci_low")
    ci_high = row.get("paired_bootstrap_ci_high")
    cohens_d = row.get("paired_cohens_d")
    z_score = float(row["frequency_z_score"])
    if ci_low is None or ci_high is None or cohens_d is None:
        return False
    if abs(float(cohens_d)) < EVENT_FREQUENCY_MIN_ABS_COHENS_D:
        return False
    if z_score > 0:
        return bool(float(ci_low) > 0)
    return bool(float(ci_high) < 0)


def _split_venue_season_label(label: str) -> tuple[str, str]:
    if ":" not in label:
        raise ValueError("Residual labels must use the 'season:venue' format.")
    season, venue_name = label.split(":", 1)
    return season, venue_name


def _rows_grouped_by_venue(
    residual_rows: Sequence[Mapping[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in residual_rows:
        grouped[str(row["venue_name"])].append(dict(row))
    for rows in grouped.values():
        rows.sort(key=lambda item: str(item["season"]))
    return grouped


def _sort_regime_rows(
    rows: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    return sorted(
        [dict(row) for row in rows],
        key=lambda item: (
            str(item.get("metric_name", "")),
            str(item["season"]),
            str(item["venue_name"]),
        ),
    )


def _regime_row_key(
    row: Mapping[str, Any],
    venue_name: str | None = None,
) -> tuple[str, str, str]:
    return (
        str(row.get("metric_name", "")),
        str(row["season"]),
        str(venue_name if venue_name is not None else row["venue_name"]),
    )


def _eligible_bias_rows(
    rows: Sequence[Mapping[str, Any]],
    value_field: str,
) -> list[Mapping[str, Any]]:
    return [
        row
        for row in rows
        if bool(row.get("sample_adequate", True))
        and _finite_float_or_none(row.get(value_field)) is not None
    ]


def _weighted_mean(
    rows: Sequence[Mapping[str, Any]],
    value_field: str,
    sample_size_field: str | None,
) -> float | None:
    if not rows:
        return None
    values = np.asarray([float(row[value_field]) for row in rows], dtype=float)
    if sample_size_field is None:
        return float(values.mean())

    weights = np.asarray(
        [
            max(float(row.get(sample_size_field) or 0.0), 0.0)
            for row in rows
        ],
        dtype=float,
    )
    if float(weights.sum()) <= 0.0:
        return float(values.mean())
    return float(np.average(values, weights=weights))


def _population_anomaly_shares(
    rows: Sequence[Mapping[str, Any]],
    z_score_threshold: float,
) -> dict[str, float]:
    counts_by_season: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for row in rows:
        if not bool(row.get("sample_adequate", True)):
            continue
        z_score = _finite_float_or_none(row.get(VENUE_REGIME_RESIDUAL_FIELD))
        if z_score is None:
            continue
        counts = counts_by_season[str(row["season"])]
        counts[0] += 1
        if abs(z_score) >= z_score_threshold:
            counts[1] += 1
    return {
        season: anomaly_count / total_count
        for season, (total_count, anomaly_count) in counts_by_season.items()
        if total_count > 0
    }


def _prior_directional_candidate_counts(
    rows: Sequence[Mapping[str, Any]],
    z_score_threshold: float,
) -> dict[tuple[str, str, str], int]:
    """Count same-direction nearby candidates without using future seasons."""
    counts: dict[tuple[str, str, str], int] = {}
    for venue_name, venue_rows in _rows_grouped_by_venue(rows).items():
        for row in venue_rows:
            z_score = _finite_float_or_none(row.get(VENUE_REGIME_RESIDUAL_FIELD))
            if z_score is None:
                counts[_regime_row_key(row, venue_name)] = 0
                continue
            season_year = _season_start_year(str(row["season"]))
            local_count = 0
            for neighbor in venue_rows:
                neighbor_year = _season_start_year(str(neighbor["season"]))
                if neighbor_year > season_year:
                    continue
                if season_year - neighbor_year > VENUE_REGIME_CENTERED_WINDOW_RADIUS:
                    continue
                if not bool(neighbor.get("sample_adequate", True)):
                    continue
                neighbor_z_score = _finite_float_or_none(
                    neighbor.get(VENUE_REGIME_RESIDUAL_FIELD)
                )
                if neighbor_z_score is None:
                    continue
                if abs(neighbor_z_score) < z_score_threshold:
                    continue
                if _direction(neighbor_z_score) != _direction(z_score):
                    continue
                local_count += 1
            counts[_regime_row_key(row, venue_name)] = local_count
    return counts


def _classify_regime_row(
    row: Mapping[str, Any],
    z_score: float | None,
    candidate: bool,
    sample_adequate: bool,
    population_share: float | None,
    max_population_anomaly_share: float,
    persistent_min_seasons: int,
    same_direction_count: int,
) -> str:
    if not candidate:
        return VENUE_REGIME_NOT_FLAGGED
    if z_score is None:
        return VENUE_REGIME_UNEXPLAINED_OR_CONFOUNDED
    if not sample_adequate:
        return VENUE_REGIME_INSUFFICIENT_EVIDENCE
    if (
        population_share is not None
        and population_share > max_population_anomaly_share
    ):
        return VENUE_REGIME_POPULATION_SHIFT
    if same_direction_count >= persistent_min_seasons:
        return VENUE_REGIME_PERSISTENT_BIAS
    if bool(row.get("evidence_supports_regime", False)):
        return VENUE_REGIME_TEMPORARY_SUPPORTED
    return VENUE_REGIME_UNEXPLAINED_OR_CONFOUNDED


def _finite_float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    value_float = float(value)
    if not np.isfinite(value_float):
        return None
    return value_float


def _direction(value: float) -> int:
    if value >= 0.0:
        return 1
    return -1


def _season_start_year(season: str) -> int:
    return int(str(season)[:4])
