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
