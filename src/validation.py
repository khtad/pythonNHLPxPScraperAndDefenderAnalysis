"""Statistical validation helpers shared between notebooks and production code.

These helpers implement the minimum rigor framework required by CLAUDE.md
for any analysis that informs a model design decision: bootstrap confidence
intervals, effect sizes, Hosmer-Lemeshow goodness-of-fit, calibration
slope/intercept, and forward-chaining season-block cross-validation.

The canonical entry points are:

- ``bootstrap_goal_rate_ci``
- ``cohens_h``
- ``hosmer_lemeshow_test``
- ``calibration_slope_intercept``
- ``run_temporal_cv``

Numeric constants live at module scope so callers (notebooks, training
scripts, tests) import a single source of truth rather than re-defining
them inline.
"""

from __future__ import annotations

from typing import Iterable, List, Dict, Any, Mapping, Sequence

import numpy as np
from scipy import stats as sp_stats
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    brier_score_loss,
    log_loss,
    roc_auc_score,
)

from venue_bias import (
    VENUE_REGIME_INSUFFICIENT_EVIDENCE,
    VENUE_REGIME_PERSISTENT_BIAS,
    VENUE_REGIME_POPULATION_SHIFT,
    VENUE_REGIME_TEMPORARY_SUPPORTED,
    VENUE_REGIME_UNEXPLAINED_OR_CONFOUNDED,
)


N_BOOTSTRAP_SAMPLES = 10_000
MIN_SHOTS_PER_CELL = 400
COHEN_H_SMALL = 0.2
MIN_TRAIN_SEASONS = 3

CALIBRATION_N_BINS = 10
CALIBRATION_SLOPE_TARGET_LOW = 0.95
CALIBRATION_SLOPE_TARGET_HIGH = 1.05
MAX_DECILE_CALIBRATION_ERROR = 0.01
EXPECTED_CALIBRATION_ERROR_TARGET = 0.005
HOSMER_LEMESHOW_ALPHA = 0.05

_BOOTSTRAP_DEFAULT_SEED = 42
_CALIBRATION_LOGIT_CLIP = 1e-10
VENUE_CORRECTION_MAX_HOME_ICE_ADVANTAGE_REMOVAL = 0.5
VENUE_CORRECTION_MAX_ABS_RESIDUAL_Z_SCORE = 2.0
VENUE_CORRECTION_MAX_ABS_EVENT_FREQUENCY_Z_SCORE = 2.0
_VENUE_CORRECTION_MIN_BASELINE_ADVANTAGE = 1e-9
_VENUE_CORRECTION_LOG_LOSS_TOLERANCE = 1e-12
_VENUE_REGIME_RESIDUAL_Z_SCORE_MATCH_ATOL = 1e-9
_VENUE_REGIME_RESIDUAL_Z_SCORE_MATCH_RTOL = 1e-9
_VENUE_REGIME_GATE_MODE_MAX_Z = "max_z"
_VENUE_REGIME_GATE_MODE_REGIME_AWARE = "regime_aware"
_VENUE_REGIME_NON_BLOCKING_LABELS = {
    VENUE_REGIME_PERSISTENT_BIAS,
    VENUE_REGIME_TEMPORARY_SUPPORTED,
}
_VENUE_REGIME_BLOCKING_LABELS = {
    VENUE_REGIME_UNEXPLAINED_OR_CONFOUNDED,
    VENUE_REGIME_INSUFFICIENT_EVIDENCE,
    VENUE_REGIME_POPULATION_SHIFT,
}


def bootstrap_goal_rate_ci(
    goals: int,
    shots: int,
    n_boot: int = N_BOOTSTRAP_SAMPLES,
    alpha: float = 0.05,
    random_state: int = _BOOTSTRAP_DEFAULT_SEED,
):
    """Bootstrap ``1 - alpha`` CI for a binomial proportion (goal rate).

    Returns ``(point_estimate, ci_lower, ci_upper)``. When ``shots == 0``
    the function returns a zero triple rather than dividing by zero.
    """
    if shots == 0:
        return (0.0, 0.0, 0.0)
    rng = np.random.default_rng(seed=random_state)
    point = goals / shots
    boot_rates = rng.binomial(n=shots, p=point, size=n_boot) / shots
    ci_lower = float(np.percentile(boot_rates, 100 * alpha / 2))
    ci_upper = float(np.percentile(boot_rates, 100 * (1 - alpha / 2)))
    return (point, ci_lower, ci_upper)


def cohens_h(p1: float, p2: float) -> float:
    """Cohen's h effect size for two proportions.

    ``h = 2 * arcsin(sqrt(p1)) - 2 * arcsin(sqrt(p2))``. Conventional
    thresholds: ``|h| < 0.2`` small, ``< 0.5`` medium, ``>= 0.8`` large.
    """
    return 2 * np.arcsin(np.sqrt(p1)) - 2 * np.arcsin(np.sqrt(p2))


def hosmer_lemeshow_test(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    n_bins: int = CALIBRATION_N_BINS,
):
    """Hosmer-Lemeshow goodness-of-fit test.

    Groups predictions into ``n_bins`` quantile bins and compares observed
    vs expected positive/negative counts with a chi-squared statistic.
    Returns ``(statistic, p_value, dof)``. ``dof = n_bins - 2`` is the
    standard HL convention for a logistic model fit on the same data.
    """
    y_true = np.asarray(y_true)
    y_prob = np.asarray(y_prob, dtype=float)

    bin_edges = np.percentile(y_prob, np.linspace(0, 100, n_bins + 1))
    bin_edges[0] = 0.0
    bin_edges[-1] = 1.0
    bin_indices = np.digitize(y_prob, bin_edges) - 1
    bin_indices = np.clip(bin_indices, 0, n_bins - 1)

    hl_stat = 0.0
    for b in range(n_bins):
        mask = bin_indices == b
        n_b = int(mask.sum())
        if n_b == 0:
            continue
        obs_pos = float(y_true[mask].sum())
        exp_pos = float(y_prob[mask].sum())
        obs_neg = n_b - obs_pos
        exp_neg = n_b - exp_pos
        if exp_pos > 0:
            hl_stat += (obs_pos - exp_pos) ** 2 / exp_pos
        if exp_neg > 0:
            hl_stat += (obs_neg - exp_neg) ** 2 / exp_neg

    dof = n_bins - 2
    p_value = float(1 - sp_stats.chi2.cdf(hl_stat, dof))
    return float(hl_stat), p_value, dof


def practical_calibration_metrics(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    n_bins: int = CALIBRATION_N_BINS,
) -> Dict[str, Any]:
    """Return practical quantile-bin calibration error metrics.

    ``max_bin_calibration_error`` is the largest absolute observed-vs-predicted
    rate gap across bins. ``expected_calibration_error`` is the sample-weighted
    average absolute gap. Both are proportions, so ``0.01`` means 1 percentage
    point.
    """
    y_true = np.asarray(y_true)
    y_prob = np.asarray(y_prob, dtype=float)
    if len(y_true) != len(y_prob):
        raise ValueError("y_true and y_prob must have equal length.")
    if len(y_true) == 0:
        raise ValueError("Calibration metrics require at least one row.")
    if np.any(~np.isfinite(y_prob)):
        raise ValueError("Predicted probabilities must be finite.")

    bin_edges = np.percentile(y_prob, np.linspace(0, 100, n_bins + 1))
    bin_edges[0] = 0.0
    bin_edges[-1] = 1.0
    bin_indices = np.digitize(y_prob, bin_edges) - 1
    bin_indices = np.clip(bin_indices, 0, n_bins - 1)

    bins = []
    max_error = 0.0
    expected_error = 0.0
    n_total = len(y_true)
    for bin_idx in range(n_bins):
        mask = bin_indices == bin_idx
        n_bin = int(mask.sum())
        if n_bin == 0:
            continue
        observed_rate = float(y_true[mask].mean())
        predicted_rate = float(y_prob[mask].mean())
        error = abs(observed_rate - predicted_rate)
        max_error = max(max_error, error)
        expected_error += error * (n_bin / n_total)
        bins.append({
            "bin": int(bin_idx),
            "n": n_bin,
            "observed_rate": observed_rate,
            "predicted_rate": predicted_rate,
            "calibration_error": float(error),
        })

    return {
        "n": int(n_total),
        "n_bins": int(n_bins),
        "max_bin_calibration_error": float(max_error),
        "expected_calibration_error": float(expected_error),
        "bins": bins,
    }


def calibration_slope_intercept(
    y_true: np.ndarray,
    y_prob: np.ndarray,
):
    """Calibration slope and intercept via logistic regression of ``y_true``
    on the log-odds of ``y_prob``. Perfect calibration is slope=1, intercept=0.
    Returns ``(slope, intercept)`` as floats.
    """
    y_true = np.asarray(y_true)
    y_prob = np.asarray(y_prob, dtype=float)

    y_prob_clipped = np.clip(y_prob, _CALIBRATION_LOGIT_CLIP, 1 - _CALIBRATION_LOGIT_CLIP)
    log_odds = np.log(y_prob_clipped / (1 - y_prob_clipped))

    cal_model = LogisticRegression(max_iter=1000, solver="lbfgs")
    cal_model.fit(log_odds.reshape(-1, 1), y_true)
    return float(cal_model.coef_[0][0]), float(cal_model.intercept_[0])


def run_temporal_cv(
    X: np.ndarray,
    y: np.ndarray,
    row_seasons_arr: np.ndarray,
    unique_seasons: Sequence,
    min_train: int = MIN_TRAIN_SEASONS,
) -> List[Dict[str, Any]]:
    """Forward-chaining season-block cross validation.

    For each fold ``k >= min_train``, train on seasons ``[0..k)`` and
    evaluate on ``unique_seasons[k]``. Returns one dict per completed fold
    with keys ``test_season``, ``n_train``, ``n_test``, ``train_seasons``,
    ``test_base_rate``, ``auc_roc``, ``log_loss``, ``brier``, ``y_test``,
    ``y_prob``. Folds where the test season has no data or zero positives
    are skipped silently.
    """
    X = np.asarray(X)
    y = np.asarray(y)
    row_seasons_arr = np.asarray(row_seasons_arr)

    results: List[Dict[str, Any]] = []
    for fold_idx in range(min_train, len(unique_seasons)):
        test_season = unique_seasons[fold_idx]
        train_seasons = set(unique_seasons[:fold_idx])

        train_mask = np.isin(row_seasons_arr, list(train_seasons))
        test_mask = row_seasons_arr == test_season

        X_train, y_train = X[train_mask], y[train_mask]
        X_test, y_test = X[test_mask], y[test_mask]

        if len(y_test) == 0 or y_test.sum() == 0:
            continue

        model = LogisticRegression(max_iter=1000, solver="lbfgs")
        model.fit(X_train, y_train)
        y_prob = model.predict_proba(X_test)[:, 1]

        results.append({
            "test_season": test_season,
            "n_train": int(len(y_train)),
            "n_test": int(len(y_test)),
            "train_seasons": len(train_seasons),
            "test_base_rate": float(y_test.mean()),
            "auc_roc": float(roc_auc_score(y_test, y_prob)),
            "log_loss": float(log_loss(y_test, y_prob)),
            "brier": float(brier_score_loss(y_test, y_prob)),
            "y_test": y_test,
            "y_prob": y_prob,
        })
    return results


def _logit_probabilities(y_prob: np.ndarray) -> np.ndarray:
    y_prob = np.asarray(y_prob, dtype=float)
    y_prob_clipped = np.clip(y_prob, _CALIBRATION_LOGIT_CLIP, 1 - _CALIBRATION_LOGIT_CLIP)
    return np.log(y_prob_clipped / (1 - y_prob_clipped))


def run_temporal_cv_with_prior_season_calibration(
    X: np.ndarray,
    y: np.ndarray,
    row_seasons_arr: np.ndarray,
    unique_seasons: Sequence,
    min_train: int = MIN_TRAIN_SEASONS,
) -> List[Dict[str, Any]]:
    """Forward-chaining temporal CV with a fold-safe Platt calibrator.

    For each fold, train the base model on seasons before the immediately
    prior season, fit a one-dimensional logistic calibration model on that
    prior season's base predictions, then evaluate the following season. This
    produces ``train < calibration < test`` ordering and intentionally starts
    one season later than ``run_temporal_cv``.
    """
    X = np.asarray(X)
    y = np.asarray(y)
    row_seasons_arr = np.asarray(row_seasons_arr)

    results: List[Dict[str, Any]] = []
    for fold_idx in range(min_train + 1, len(unique_seasons)):
        test_season = unique_seasons[fold_idx]
        calibration_season = unique_seasons[fold_idx - 1]
        train_seasons = list(unique_seasons[: fold_idx - 1])

        train_mask = np.isin(row_seasons_arr, train_seasons)
        calibration_mask = row_seasons_arr == calibration_season
        test_mask = row_seasons_arr == test_season

        X_train, y_train = X[train_mask], y[train_mask]
        X_calibration, y_calibration = X[calibration_mask], y[calibration_mask]
        X_test, y_test = X[test_mask], y[test_mask]

        if (
            len(y_test) == 0
            or y_test.sum() == 0
            or len(np.unique(y_calibration)) < 2
        ):
            continue

        base_model = LogisticRegression(max_iter=1000, solver="lbfgs")
        base_model.fit(X_train, y_train)

        calibration_prob = base_model.predict_proba(X_calibration)[:, 1]
        test_prob_uncalibrated = base_model.predict_proba(X_test)[:, 1]

        calibrator = LogisticRegression(max_iter=1000, solver="lbfgs")
        calibrator.fit(
            _logit_probabilities(calibration_prob).reshape(-1, 1),
            y_calibration,
        )
        y_prob = calibrator.predict_proba(
            _logit_probabilities(test_prob_uncalibrated).reshape(-1, 1)
        )[:, 1]

        results.append({
            "test_season": test_season,
            "calibration_season": calibration_season,
            "n_train": int(len(y_train)),
            "n_calibration": int(len(y_calibration)),
            "n_test": int(len(y_test)),
            "train_seasons": len(train_seasons),
            "test_base_rate": float(y_test.mean()),
            "auc_roc": float(roc_auc_score(y_test, y_prob)),
            "log_loss": float(log_loss(y_test, y_prob)),
            "brier": float(brier_score_loss(y_test, y_prob)),
            "y_test": y_test,
            "y_prob": y_prob,
            "y_prob_uncalibrated": test_prob_uncalibrated,
        })
    return results


def evaluate_leakage_audit(
    audit_rows: Sequence[Mapping[str, Any]],
    selected_features: Iterable[str],
) -> Dict[str, Any]:
    """Evaluate leakage risk for selected model features only.

    Audit rows for excluded candidate features remain visible as
    ``excluded_pending`` items, but only selected features with ambiguous
    temporal availability or HIGH confounder risk block the scorecard.
    """
    selected = set(selected_features)
    blocking_features = []
    excluded_pending_features = []
    selected_audit = []
    annotated_rows = []

    for row in audit_rows:
        feature = str(row["feature"])
        availability = str(row["available_at_shot_time"])
        confounder_risk = str(row["confounder_risk"])
        annotated = dict(row)
        if feature in selected:
            annotated["selection_status"] = "selected"
            selected_audit.append(annotated)
            if availability == "AMBIGUOUS" or confounder_risk == "HIGH":
                blocking_features.append(feature)
        else:
            requires_resolution = bool(row.get("excluded_pending")) or (
                availability == "AMBIGUOUS"
                or confounder_risk in {"MEDIUM", "HIGH"}
            )
            if availability == "TARGET":
                annotated["selection_status"] = "target_not_feature"
            elif requires_resolution:
                annotated["selection_status"] = "excluded_pending"
                excluded_pending_features.append(feature)
            else:
                annotated["selection_status"] = "excluded_clear"
        annotated_rows.append(annotated)

    missing_selected = sorted(selected - {str(row["feature"]) for row in audit_rows})
    if missing_selected:
        raise ValueError(
            "Selected features are missing leakage-audit rows: "
            + ", ".join(missing_selected)
        )

    return {
        "pass": len(blocking_features) == 0,
        "n_selected": int(len(selected_audit)),
        "n_blocking": int(len(blocking_features)),
        "blocking_features": blocking_features,
        "excluded_pending_features": excluded_pending_features,
        "annotated_rows": annotated_rows,
    }


def evaluate_venue_correction_holdout(
    y_true: np.ndarray,
    y_prob_baseline: np.ndarray,
    y_prob_corrected: np.ndarray,
    is_home_attempt: np.ndarray,
    max_home_ice_advantage_removal: float = (
        VENUE_CORRECTION_MAX_HOME_ICE_ADVANTAGE_REMOVAL
    ),
) -> Dict[str, Any]:
    """Evaluate held-out venue-correction acceptance criteria.

    Returns a metrics dict with two gate booleans:
    - ``log_loss_non_worse_pass``: corrected log-loss is not worse than baseline.
    - ``home_ice_guardrail_pass``: correction removes no more than the configured
      fraction of baseline home-ice predicted goal-rate advantage.
    """
    y_true = np.asarray(y_true)
    y_prob_baseline = np.asarray(y_prob_baseline, dtype=float)
    y_prob_corrected = np.asarray(y_prob_corrected, dtype=float)
    is_home_attempt = np.asarray(is_home_attempt).astype(bool)

    n_rows = len(y_true)
    if not (
        len(y_prob_baseline) == n_rows
        and len(y_prob_corrected) == n_rows
        and len(is_home_attempt) == n_rows
    ):
        raise ValueError("All inputs must have equal length.")

    if n_rows == 0:
        raise ValueError("Inputs must contain at least one row.")

    baseline_log_loss = float(log_loss(y_true, y_prob_baseline))
    corrected_log_loss = float(log_loss(y_true, y_prob_corrected))
    log_loss_delta = corrected_log_loss - baseline_log_loss
    log_loss_non_worse_pass = (
        log_loss_delta <= _VENUE_CORRECTION_LOG_LOSS_TOLERANCE
    )

    home_mask = is_home_attempt
    away_mask = ~is_home_attempt
    if home_mask.sum() == 0 or away_mask.sum() == 0:
        raise ValueError("Both home and away rows are required.")

    baseline_home_rate = float(y_prob_baseline[home_mask].mean())
    baseline_away_rate = float(y_prob_baseline[away_mask].mean())
    corrected_home_rate = float(y_prob_corrected[home_mask].mean())
    corrected_away_rate = float(y_prob_corrected[away_mask].mean())

    baseline_advantage = baseline_home_rate - baseline_away_rate
    corrected_advantage = corrected_home_rate - corrected_away_rate

    if baseline_advantage <= _VENUE_CORRECTION_MIN_BASELINE_ADVANTAGE:
        advantage_removed_ratio = 0.0
    else:
        advantage_removed_ratio = (
            baseline_advantage - corrected_advantage
        ) / baseline_advantage
    home_ice_guardrail_pass = (
        advantage_removed_ratio <= max_home_ice_advantage_removal
    )

    overall_pass = log_loss_non_worse_pass and home_ice_guardrail_pass
    return {
        "n_rows": int(n_rows),
        "baseline_log_loss": baseline_log_loss,
        "corrected_log_loss": corrected_log_loss,
        "log_loss_delta": float(log_loss_delta),
        "log_loss_non_worse_pass": bool(log_loss_non_worse_pass),
        "baseline_home_advantage": float(baseline_advantage),
        "corrected_home_advantage": float(corrected_advantage),
        "advantage_removed_ratio": float(advantage_removed_ratio),
        "max_allowed_advantage_removed_ratio": float(
            max_home_ice_advantage_removal
        ),
        "home_ice_guardrail_pass": bool(home_ice_guardrail_pass),
        "overall_pass": bool(overall_pass),
    }


def evaluate_venue_correction_scorecard(
    y_true: np.ndarray,
    y_prob_baseline: np.ndarray,
    y_prob_corrected: np.ndarray,
    is_home_attempt: np.ndarray,
    distance_residual_venue_z_scores: Mapping[str, float] | Sequence[float],
    event_frequency_residual_venue_z_scores: Mapping[str, float] | Sequence[float],
    distance_regime_diagnostics: Sequence[Mapping[str, Any]] | None = None,
    event_frequency_regime_diagnostics: Sequence[Mapping[str, Any]] | None = None,
    max_home_ice_advantage_removal: float = (
        VENUE_CORRECTION_MAX_HOME_ICE_ADVANTAGE_REMOVAL
    ),
    max_abs_distance_residual_z_score: float = VENUE_CORRECTION_MAX_ABS_RESIDUAL_Z_SCORE,
    max_abs_event_frequency_z_score: float = (
        VENUE_CORRECTION_MAX_ABS_EVENT_FREQUENCY_Z_SCORE
    ),
) -> Dict[str, Any]:
    """Evaluate the Phase 2.5.4 venue-correction scorecard gates.

    Combines the held-out log-loss and home-ice over-correction checks from
    ``evaluate_venue_correction_holdout`` with separate distance/location and
    event-frequency residual z-score gates. Residual z-scores may be either a
    mapping of venue labels to z-scores or a plain sequence.
    """
    holdout = evaluate_venue_correction_holdout(
        y_true,
        y_prob_baseline,
        y_prob_corrected,
        is_home_attempt,
        max_home_ice_advantage_removal=max_home_ice_advantage_removal,
    )
    distance_gate = _evaluate_residual_regime_gate(
        distance_residual_venue_z_scores,
        distance_regime_diagnostics,
        max_abs_distance_residual_z_score,
    )
    frequency_gate = _evaluate_residual_regime_gate(
        event_frequency_residual_venue_z_scores,
        event_frequency_regime_diagnostics,
        max_abs_event_frequency_z_score,
    )

    result = dict(holdout)
    result.update({
        "n_distance_residual_venues": int(distance_gate["n_residual_venues"]),
        "worst_distance_residual_venue": distance_gate["worst_residual_venue"],
        "max_abs_distance_residual_z_score": float(
            distance_gate["max_abs_residual_z_score"]
        ),
        "max_allowed_abs_distance_residual_z_score": float(
            max_abs_distance_residual_z_score
        ),
        "distance_residual_z_score_pass": bool(distance_gate["pass"]),
        "distance_residual_gate_mode": distance_gate["gate_mode"],
        "distance_blocking_regime_count": int(distance_gate["n_blocking_regimes"]),
        "distance_supported_regime_count": int(distance_gate["n_supported_regimes"]),
        "distance_persistent_regime_count": int(distance_gate["n_persistent_regimes"]),
        "distance_temporary_supported_regime_count": int(
            distance_gate["n_temporary_supported_regimes"]
        ),
        "distance_blocking_regimes": distance_gate["blocking_regimes"],
        "n_event_frequency_residual_venues": int(
            frequency_gate["n_residual_venues"]
        ),
        "worst_event_frequency_residual_venue": (
            frequency_gate["worst_residual_venue"]
        ),
        "max_abs_event_frequency_z_score": float(
            frequency_gate["max_abs_residual_z_score"]
        ),
        "max_allowed_abs_event_frequency_z_score": float(
            max_abs_event_frequency_z_score
        ),
        "event_frequency_residual_z_score_pass": bool(
            frequency_gate["pass"]
        ),
        "event_frequency_residual_gate_mode": frequency_gate["gate_mode"],
        "event_frequency_blocking_regime_count": int(
            frequency_gate["n_blocking_regimes"]
        ),
        "event_frequency_supported_regime_count": int(
            frequency_gate["n_supported_regimes"]
        ),
        "event_frequency_persistent_regime_count": int(
            frequency_gate["n_persistent_regimes"]
        ),
        "event_frequency_temporary_supported_regime_count": int(
            frequency_gate["n_temporary_supported_regimes"]
        ),
        "event_frequency_blocking_regimes": frequency_gate["blocking_regimes"],
        "n_venues": int(distance_gate["n_residual_venues"]),
        "worst_residual_venue": distance_gate["worst_residual_venue"],
        "max_abs_residual_z_score": float(distance_gate["max_abs_residual_z_score"]),
        "max_allowed_abs_residual_z_score": float(max_abs_distance_residual_z_score),
        "residual_z_score_pass": bool(distance_gate["pass"]),
        "overall_pass": bool(
            holdout["overall_pass"]
            and distance_gate["pass"]
            and frequency_gate["pass"]
        ),
    })
    return result


def _coerce_residual_z_score_items(
    residual_venue_z_scores: Mapping[str, float] | Sequence[float],
) -> List[tuple[str, float]]:
    """Return labeled residual z-score items, rejecting empty/invalid values."""
    if isinstance(residual_venue_z_scores, Mapping):
        items = [
            (str(venue_name), float(z_score))
            for venue_name, z_score in residual_venue_z_scores.items()
        ]
    else:
        items = [
            (f"venue_{idx}", float(z_score))
            for idx, z_score in enumerate(residual_venue_z_scores)
        ]

    if not items:
        raise ValueError("At least one residual venue z-score is required.")
    if any(not np.isfinite(z_score) for _, z_score in items):
        raise ValueError("Residual venue z-scores must be finite numbers.")
    return items


def _max_abs_residual_z_score_item(
    residual_items: Sequence[tuple[str, float]],
) -> tuple[str, float]:
    return max(residual_items, key=lambda item: abs(item[1]))


def _evaluate_residual_regime_gate(
    residual_z_scores: Mapping[str, float] | Sequence[float],
    regime_diagnostics: Sequence[Mapping[str, Any]] | None,
    max_abs_z_score: float,
) -> Dict[str, Any]:
    residual_items = _coerce_residual_z_score_items(residual_z_scores)
    worst_venue, worst_z_score = _max_abs_residual_z_score_item(residual_items)
    max_abs_observed = abs(worst_z_score)
    if regime_diagnostics is None:
        return {
            "gate_mode": _VENUE_REGIME_GATE_MODE_MAX_Z,
            "pass": bool(max_abs_observed < max_abs_z_score),
            "n_residual_venues": int(len(residual_items)),
            "worst_residual_venue": worst_venue,
            "max_abs_residual_z_score": float(max_abs_observed),
            "n_blocking_regimes": 0,
            "n_supported_regimes": 0,
            "n_persistent_regimes": 0,
            "n_temporary_supported_regimes": 0,
            "blocking_regimes": [],
        }

    regime_rows = [dict(row) for row in regime_diagnostics]
    residual_lookup = dict(residual_items)
    gate_regime_rows = [
        row for row in regime_rows
        if _regime_row_matches_current_residual(row, residual_lookup)
    ]
    missing_candidate_rows = _missing_residual_candidate_regime_rows(
        residual_items,
        gate_regime_rows,
        max_abs_z_score,
    )
    blocking_rows = [
        *_blocking_regime_rows(gate_regime_rows, max_abs_z_score),
        *missing_candidate_rows,
    ]
    return {
        "gate_mode": _VENUE_REGIME_GATE_MODE_REGIME_AWARE,
        "pass": bool(len(blocking_rows) == 0),
        "n_residual_venues": int(len(residual_items)),
        "worst_residual_venue": worst_venue,
        "max_abs_residual_z_score": float(max_abs_observed),
        "n_blocking_regimes": int(len(blocking_rows)),
        "n_supported_regimes": int(
            sum(
                1
                for row in gate_regime_rows
                if row.get("regime_classification")
                in _VENUE_REGIME_NON_BLOCKING_LABELS
                and _is_residual_gate_candidate(row, max_abs_z_score)
            )
        ),
        "n_persistent_regimes": int(
            sum(
                1
                for row in gate_regime_rows
                if row.get("regime_classification") == VENUE_REGIME_PERSISTENT_BIAS
                and _is_residual_gate_candidate(row, max_abs_z_score)
            )
        ),
        "n_temporary_supported_regimes": int(
            sum(
                1
                for row in gate_regime_rows
                if row.get("regime_classification") == VENUE_REGIME_TEMPORARY_SUPPORTED
                and _is_residual_gate_candidate(row, max_abs_z_score)
            )
        ),
        "blocking_regimes": _compact_blocking_regimes(blocking_rows),
    }


def _blocking_regime_rows(
    regime_rows: Sequence[Mapping[str, Any]],
    max_abs_z_score: float,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in regime_rows:
        if not _is_residual_gate_candidate(row, max_abs_z_score):
            continue
        label = row.get("regime_classification")
        if label in _VENUE_REGIME_NON_BLOCKING_LABELS:
            continue
        if label in _VENUE_REGIME_BLOCKING_LABELS or label is not None:
            rows.append(dict(row))
            continue
        rows.append(dict(row))
    rows.sort(
        key=lambda item: abs(float(item.get("residual_z_score", 0.0))),
        reverse=True,
    )
    return rows


def _missing_residual_candidate_regime_rows(
    residual_items: Sequence[tuple[str, float]],
    regime_rows: Sequence[Mapping[str, Any]],
    max_abs_z_score: float,
) -> list[dict[str, Any]]:
    regime_labels = {
        _regime_diagnostic_label(row)
        for row in regime_rows
    }
    missing_rows: list[dict[str, Any]] = []
    for label, z_score in residual_items:
        if abs(z_score) < max_abs_z_score:
            continue
        if label in regime_labels:
            continue
        missing_rows.append(
            _residual_item_to_missing_regime_row(label, z_score)
        )
    return missing_rows


def _is_residual_gate_candidate(
    row: Mapping[str, Any],
    max_abs_z_score: float,
) -> bool:
    z_score = float(row.get("residual_z_score", 0.0))
    return bool(np.isfinite(z_score) and abs(z_score) >= max_abs_z_score)


def _compact_blocking_regimes(
    blocking_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {
            "metric_name": row.get("metric_name", "unspecified"),
            "season": row.get("season"),
            "venue_name": row.get("venue_name"),
            "residual_z_score": float(row.get("residual_z_score", 0.0)),
            "regime_classification": row.get("regime_classification"),
        }
        for row in blocking_rows
    ]


def _regime_diagnostic_label(row: Mapping[str, Any]) -> str:
    return f"{row.get('season')}:{row.get('venue_name')}"


def _regime_row_matches_current_residual(
    row: Mapping[str, Any],
    residual_lookup: Mapping[str, float],
) -> bool:
    label = _regime_diagnostic_label(row)
    if label not in residual_lookup:
        return False
    row_z_score = float(row.get("residual_z_score", np.nan))
    residual_z_score = float(residual_lookup[label])
    return bool(
        np.isfinite(row_z_score)
        and np.isclose(
            row_z_score,
            residual_z_score,
            atol=_VENUE_REGIME_RESIDUAL_Z_SCORE_MATCH_ATOL,
            rtol=_VENUE_REGIME_RESIDUAL_Z_SCORE_MATCH_RTOL,
        )
    )


def _residual_item_to_missing_regime_row(
    label: str,
    z_score: float,
) -> dict[str, Any]:
    if ":" in label:
        season, venue_name = label.split(":", 1)
    else:
        season = None
        venue_name = label
    return {
        "metric_name": "unspecified",
        "season": season,
        "venue_name": venue_name,
        "residual_z_score": float(z_score),
        "regime_classification": VENUE_REGIME_INSUFFICIENT_EVIDENCE,
    }
