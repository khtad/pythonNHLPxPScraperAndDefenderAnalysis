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

from typing import Iterable, List, Dict, Any, Sequence

import numpy as np
from scipy import stats as sp_stats
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    brier_score_loss,
    log_loss,
    roc_auc_score,
)


N_BOOTSTRAP_SAMPLES = 10_000
MIN_SHOTS_PER_CELL = 400
COHEN_H_SMALL = 0.2
MIN_TRAIN_SEASONS = 3

CALIBRATION_N_BINS = 10
CALIBRATION_SLOPE_TARGET_LOW = 0.95
CALIBRATION_SLOPE_TARGET_HIGH = 1.05
HOSMER_LEMESHOW_ALPHA = 0.05

_BOOTSTRAP_DEFAULT_SEED = 42
_CALIBRATION_LOGIT_CLIP = 1e-10
VENUE_CORRECTION_MAX_HOME_ICE_ADVANTAGE_REMOVAL = 0.5
_VENUE_CORRECTION_MIN_BASELINE_ADVANTAGE = 1e-9
_VENUE_CORRECTION_LOG_LOSS_TOLERANCE = 1e-12


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
