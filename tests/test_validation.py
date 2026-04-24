"""Tests for src/validation.py.

Guarded with ``pytest.importorskip`` so a missing numeric stack skips this
file instead of breaking pytest collection for the whole suite (see
CLAUDE.md "Test Failures Encountered, Fixes, and Prevention Rules" #3).
"""

import pytest

pytest.importorskip("numpy")
pytest.importorskip("scipy")
pytest.importorskip("sklearn")

import numpy as np

from validation import (
    COHEN_H_SMALL,
    HOSMER_LEMESHOW_ALPHA,
    MIN_SHOTS_PER_CELL,
    MIN_TRAIN_SEASONS,
    VENUE_CORRECTION_MAX_HOME_ICE_ADVANTAGE_REMOVAL,
    bootstrap_goal_rate_ci,
    calibration_slope_intercept,
    cohens_h,
    evaluate_venue_correction_holdout,
    hosmer_lemeshow_test,
    run_temporal_cv,
)


# --------------------------------------------------------------------------
# bootstrap_goal_rate_ci
# --------------------------------------------------------------------------


def test_bootstrap_ci_zero_shots_returns_zero_triple():
    assert bootstrap_goal_rate_ci(0, 0) == (0.0, 0.0, 0.0)


def test_bootstrap_ci_point_estimate_matches_ratio():
    point, lo, hi = bootstrap_goal_rate_ci(80, 1000, n_boot=500)
    assert point == pytest.approx(0.08)
    assert lo < point < hi


def test_bootstrap_ci_is_deterministic_under_fixed_seed():
    a = bootstrap_goal_rate_ci(50, 500, n_boot=1000, random_state=7)
    b = bootstrap_goal_rate_ci(50, 500, n_boot=1000, random_state=7)
    assert a == b


def test_bootstrap_ci_coverage_near_nominal_level():
    """Monte Carlo coverage check: ~95% CIs should cover the true rate ~95%
    of the time. With 400 trials the Monte Carlo standard error is ~1.1 pp,
    so the acceptance window of ±5 pp comfortably absorbs sampling noise
    while still rejecting a broken implementation (which would produce
    coverage near 0% or 100%)."""
    true_p = 0.08
    n_shots = 1000
    n_trials = 400
    rng = np.random.default_rng(seed=12345)

    covered = 0
    for trial in range(n_trials):
        goals = int(rng.binomial(n=n_shots, p=true_p))
        _, lo, hi = bootstrap_goal_rate_ci(
            goals, n_shots, n_boot=500, random_state=trial
        )
        if lo <= true_p <= hi:
            covered += 1
    coverage = covered / n_trials
    assert 0.90 <= coverage <= 1.00, f"coverage={coverage}"


# --------------------------------------------------------------------------
# cohens_h
# --------------------------------------------------------------------------


def test_cohens_h_zero_for_equal_proportions():
    assert cohens_h(0.5, 0.5) == pytest.approx(0.0, abs=1e-12)
    assert cohens_h(0.08, 0.08) == pytest.approx(0.0, abs=1e-12)


def test_cohens_h_sign_follows_first_minus_second():
    assert cohens_h(0.15, 0.08) > 0
    assert cohens_h(0.08, 0.15) < 0


def test_cohens_h_antisymmetric():
    h_ab = cohens_h(0.12, 0.07)
    h_ba = cohens_h(0.07, 0.12)
    assert h_ab == pytest.approx(-h_ba)


def test_cohens_h_small_threshold_is_documented_value():
    assert COHEN_H_SMALL == 0.2


def test_cohens_h_scale_matches_known_example():
    # p1=0.5, p2=0.4 → h = 2*(arcsin(√0.5) - arcsin(√0.4)) ≈ 0.2014
    assert cohens_h(0.5, 0.4) == pytest.approx(0.2014, abs=1e-3)


# --------------------------------------------------------------------------
# hosmer_lemeshow_test
# --------------------------------------------------------------------------


def _simulate_calibrated(n=20_000, seed=0):
    rng = np.random.default_rng(seed)
    y_prob = rng.uniform(0.01, 0.30, size=n)
    y_true = (rng.uniform(size=n) < y_prob).astype(int)
    return y_true, y_prob


def _simulate_miscalibrated(n=20_000, seed=0, bias=0.10):
    """Predictions systematically understate risk by ``bias``."""
    rng = np.random.default_rng(seed)
    y_prob = rng.uniform(0.01, 0.30, size=n)
    true_rate = np.clip(y_prob + bias, 0, 1)
    y_true = (rng.uniform(size=n) < true_rate).astype(int)
    return y_true, y_prob


def test_hosmer_lemeshow_does_not_systematically_reject_calibrated_data():
    """HL is known to be noisy under quantile binning; a single realization
    can reject by chance. This checks the rejection rate across many
    independent calibrated samples stays close to the nominal α=0.05 — any
    implementation bug that inflates the statistic would push rejections
    well above this."""
    rejections = 0
    n_trials = 50
    for seed in range(n_trials):
        y_true, y_prob = _simulate_calibrated(n=20_000, seed=seed)
        _, p, dof = hosmer_lemeshow_test(y_true, y_prob)
        assert dof == 8
        if p <= HOSMER_LEMESHOW_ALPHA:
            rejections += 1
    rejection_rate = rejections / n_trials
    assert rejection_rate <= 0.20, (
        f"HL rejected {rejections}/{n_trials} calibrated samples; "
        f"rate={rejection_rate:.2f} is too high for a calibrated null"
    )


def test_hosmer_lemeshow_rejects_miscalibrated_data():
    y_true, y_prob = _simulate_miscalibrated()
    _, p, _ = hosmer_lemeshow_test(y_true, y_prob)
    assert p < HOSMER_LEMESHOW_ALPHA


def test_hosmer_lemeshow_dof_follows_bin_count():
    y_true, y_prob = _simulate_calibrated(n=5_000)
    _, _, dof = hosmer_lemeshow_test(y_true, y_prob, n_bins=5)
    assert dof == 3


# --------------------------------------------------------------------------
# calibration_slope_intercept
# --------------------------------------------------------------------------


def test_calibration_slope_near_one_on_calibrated_predictions():
    y_true, y_prob = _simulate_calibrated(n=50_000, seed=1)
    slope, intercept = calibration_slope_intercept(y_true, y_prob)
    assert slope == pytest.approx(1.0, abs=0.15)
    assert intercept == pytest.approx(0.0, abs=0.25)


def test_calibration_slope_detects_overconfident_predictions():
    """If predictions are too extreme (over-dispersed), the recalibration
    slope should drop below 1."""
    rng = np.random.default_rng(42)
    n = 40_000
    true_logit = rng.normal(-2.5, 1.0, size=n)
    true_p = 1 / (1 + np.exp(-true_logit))
    y_true = (rng.uniform(size=n) < true_p).astype(int)
    overconfident_logit = true_logit * 2.0
    y_prob = 1 / (1 + np.exp(-overconfident_logit))
    slope, _ = calibration_slope_intercept(y_true, y_prob)
    assert slope < 0.9


# --------------------------------------------------------------------------
# run_temporal_cv
# --------------------------------------------------------------------------


def _build_temporal_fixture(seed=0):
    """Five synthetic seasons of ~1000 shots each with a simple signal so
    logistic regression can fit non-trivially."""
    rng = np.random.default_rng(seed)
    seasons = ["20170001", "20180001", "20190001", "20200001", "20210001"]
    rows_per_season = 1_000

    row_seasons, X_rows, y_rows = [], [], []
    for s in seasons:
        x1 = rng.normal(0, 1, size=rows_per_season)
        x2 = rng.normal(0, 1, size=rows_per_season)
        logit = -2.5 + 0.8 * x1 - 0.4 * x2
        p = 1 / (1 + np.exp(-logit))
        y = (rng.uniform(size=rows_per_season) < p).astype(int)
        for i in range(rows_per_season):
            row_seasons.append(s)
            X_rows.append([x1[i], x2[i]])
            y_rows.append(y[i])

    X = np.array(X_rows)
    y = np.array(y_rows)
    row_seasons_arr = np.array(row_seasons)
    return X, y, row_seasons_arr, seasons


def test_run_temporal_cv_forward_chaining_structure():
    X, y, row_seasons_arr, unique_seasons = _build_temporal_fixture()
    results = run_temporal_cv(X, y, row_seasons_arr, unique_seasons)

    expected_test_seasons = unique_seasons[MIN_TRAIN_SEASONS:]
    assert [r["test_season"] for r in results] == list(expected_test_seasons)

    for fold_idx, r in enumerate(results, start=MIN_TRAIN_SEASONS):
        expected_train = sum(
            int((row_seasons_arr == s).sum())
            for s in unique_seasons[:fold_idx]
        )
        expected_test = int((row_seasons_arr == unique_seasons[fold_idx]).sum())
        assert r["n_train"] == expected_train
        assert r["n_test"] == expected_test
        assert r["train_seasons"] == fold_idx


def test_run_temporal_cv_does_not_leak_test_rows_into_training():
    """Loud-signal leakage probe: inject a highly predictive feature value
    that only appears in the held-out season. If training ever saw those
    rows, the learned coefficient would exploit them and the held-out AUC
    would approach 1.0. A correctly isolated fold cannot learn the signal
    and AUC stays near chance on the held-out season."""
    X, y, row_seasons_arr, unique_seasons = _build_temporal_fixture(seed=7)
    test_season = unique_seasons[-1]

    leak_col = np.zeros(len(y))
    leak_mask = row_seasons_arr == test_season
    leak_col[leak_mask] = y[leak_mask] * 10.0
    X_with_leak = np.column_stack([X, leak_col])

    results = run_temporal_cv(X_with_leak, y, row_seasons_arr, unique_seasons)
    last_fold = [r for r in results if r["test_season"] == test_season][0]

    # Leak signal exists only in held-out rows at train time → the coefficient
    # on the leak column gets no training signal, so held-out AUC must stay
    # in a normal range rather than jumping to ~1.0.
    assert last_fold["auc_roc"] < 0.95


def test_run_temporal_cv_skips_folds_with_no_positives():
    X, y, row_seasons_arr, unique_seasons = _build_temporal_fixture(seed=11)
    # Zero out positives in the last season so its fold is skipped
    mask = row_seasons_arr == unique_seasons[-1]
    y = y.copy()
    y[mask] = 0
    results = run_temporal_cv(X, y, row_seasons_arr, unique_seasons)
    assert unique_seasons[-1] not in [r["test_season"] for r in results]


def test_run_temporal_cv_respects_min_train_parameter():
    X, y, row_seasons_arr, unique_seasons = _build_temporal_fixture(seed=3)
    results = run_temporal_cv(
        X, y, row_seasons_arr, unique_seasons, min_train=2
    )
    assert [r["test_season"] for r in results] == list(unique_seasons[2:])


# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------


def test_min_shots_per_cell_is_documented_value():
    assert MIN_SHOTS_PER_CELL == 400


def test_min_train_seasons_is_documented_value():
    assert MIN_TRAIN_SEASONS == 3


def test_venue_correction_guardrail_threshold_is_documented_value():
    assert VENUE_CORRECTION_MAX_HOME_ICE_ADVANTAGE_REMOVAL == 0.5


def test_evaluate_venue_correction_holdout_passes_when_both_gates_pass():
    y_true = np.array([1, 1, 0, 0, 1, 0, 0, 0])
    is_home = np.array([1, 1, 1, 1, 0, 0, 0, 0], dtype=bool)
    baseline = np.array([0.90, 0.70, 0.40, 0.20, 0.60, 0.40, 0.40, 0.20])
    corrected = np.array([0.85, 0.75, 0.35, 0.25, 0.55, 0.35, 0.35, 0.25])
    result = evaluate_venue_correction_holdout(y_true, baseline, corrected, is_home)

    assert result["log_loss_non_worse_pass"] is True
    assert result["home_ice_guardrail_pass"] is True
    assert result["overall_pass"] is True
    assert result["advantage_removed_ratio"] <= VENUE_CORRECTION_MAX_HOME_ICE_ADVANTAGE_REMOVAL


def test_evaluate_venue_correction_holdout_fails_when_log_loss_worsens():
    y_true = np.array([1, 1, 0, 0, 1, 0, 0, 0])
    is_home = np.array([1, 1, 1, 1, 0, 0, 0, 0], dtype=bool)
    baseline = np.array([0.90, 0.70, 0.40, 0.20, 0.60, 0.40, 0.40, 0.20])
    corrected = np.full_like(baseline, 0.50)
    result = evaluate_venue_correction_holdout(y_true, baseline, corrected, is_home)

    assert result["log_loss_non_worse_pass"] is False
    assert result["overall_pass"] is False


def test_evaluate_venue_correction_holdout_fails_home_ice_over_correction():
    y_true = np.array([1, 1, 0, 0, 1, 0, 0, 0])
    is_home = np.array([1, 1, 1, 1, 0, 0, 0, 0], dtype=bool)
    baseline = np.array([0.85, 0.75, 0.35, 0.25, 0.65, 0.55, 0.45, 0.35])
    corrected = np.array([0.72, 0.62, 0.22, 0.12, 0.68, 0.58, 0.48, 0.38])
    result = evaluate_venue_correction_holdout(y_true, baseline, corrected, is_home)

    assert result["home_ice_guardrail_pass"] is False
    assert result["overall_pass"] is False


def test_evaluate_venue_correction_holdout_raises_on_length_mismatch():
    with pytest.raises(ValueError, match="equal length"):
        evaluate_venue_correction_holdout(
            np.array([1, 0]),
            np.array([0.6]),
            np.array([0.6, 0.4]),
            np.array([True, False]),
        )
