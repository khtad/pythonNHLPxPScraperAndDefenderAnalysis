import math

import numpy as np
import pandas as pd
import pytest

from stats_helpers import VIF_THRESHOLD, compute_vif


def test_orthogonal_inputs_have_vif_near_one():
    rng = np.random.default_rng(0)
    n = 500
    df = pd.DataFrame({
        "a": rng.standard_normal(n),
        "b": rng.standard_normal(n),
        "c": rng.standard_normal(n),
    })
    vif = compute_vif(df)
    for col, value in vif.items():
        assert math.isclose(value, 1.0, abs_tol=0.2), f"{col} VIF={value}"


def test_perfectly_collinear_pair_triggers_infinite_vif():
    rng = np.random.default_rng(1)
    n = 300
    a = rng.standard_normal(n)
    df = pd.DataFrame({
        "a": a,
        "b": rng.standard_normal(n),
        "copy_of_a": a,
    })
    vif = compute_vif(df)
    assert vif["a"] == float("inf")
    assert vif["copy_of_a"] == float("inf")


def test_highly_but_not_perfectly_collinear_pair_exceeds_threshold():
    rng = np.random.default_rng(2)
    n = 400
    a = rng.standard_normal(n)
    df = pd.DataFrame({
        "a": a,
        "near_a": a + 0.01 * rng.standard_normal(n),
        "independent": rng.standard_normal(n),
    })
    vif = compute_vif(df)
    assert vif["a"] > VIF_THRESHOLD
    assert vif["near_a"] > VIF_THRESHOLD
    assert math.isclose(vif["independent"], 1.0, abs_tol=0.2)


def test_constant_column_returns_infinity():
    df = pd.DataFrame({
        "a": np.arange(100, dtype=float),
        "const": np.ones(100),
    })
    vif = compute_vif(df)
    assert vif["const"] == float("inf")


def test_rejects_single_column():
    df = pd.DataFrame({"only": [1.0, 2.0, 3.0]})
    with pytest.raises(ValueError):
        compute_vif(df)


def test_drops_nan_rows():
    df = pd.DataFrame({
        "a": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, float("nan"), 10.0],
        "b": [2.0, 1.5, 2.1, 3.3, 4.8, 5.2, 6.9, 7.1, 9.0, 9.9],
        "c": [0.1, 0.3, float("nan"), 0.7, 0.2, 0.5, 0.8, 0.6, 0.9, 0.4],
    })
    vif = compute_vif(df)
    assert all(math.isfinite(v) for v in vif.values())
