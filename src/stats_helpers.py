"""Statistical helpers reusable across notebooks and pipeline code.

Kept intentionally small so Phase 2.5.2 (`src/validation.py`) can land the
larger validation-framework helpers without merge churn.
"""

from __future__ import annotations

import numpy as np

VIF_THRESHOLD = 5.0


def compute_vif(df):
    """Variance Inflation Factor for each numeric column in df.

    Implements VIF_i = 1 / (1 - R^2_i) where R^2_i is the coefficient of
    determination from regressing column i on the remaining columns with
    an intercept. Pure numpy; no statsmodels dependency.

    Rows with any NaN are dropped (listwise deletion) before computation.
    Columns that are constant after dropping NaNs are returned as
    ``float('inf')``. A column perfectly predicted by the others returns
    ``float('inf')`` as well (R^2 == 1).

    Parameters
    ----------
    df : pandas.DataFrame or mapping of column -> 1-D array-like
        Numeric predictors.

    Returns
    -------
    dict[str, float]
        Column name -> VIF.
    """
    columns = list(df.columns) if hasattr(df, "columns") else list(df.keys())
    if len(columns) < 2:
        raise ValueError("compute_vif requires at least 2 columns")

    matrix = np.asarray([np.asarray(df[c], dtype=float) for c in columns]).T
    mask = ~np.any(np.isnan(matrix), axis=1)
    matrix = matrix[mask]
    if matrix.shape[0] < len(columns) + 1:
        raise ValueError(
            "compute_vif requires more non-null rows than columns + 1"
        )

    result = {}
    n_rows = matrix.shape[0]
    for i, col in enumerate(columns):
        y = matrix[:, i]
        others = np.delete(matrix, i, axis=1)
        if np.allclose(y, y[0]):
            result[col] = float("inf")
            continue

        design = np.column_stack([np.ones(n_rows), others])
        coeffs, *_ = np.linalg.lstsq(design, y, rcond=None)
        predicted = design @ coeffs
        ss_res = float(np.sum((y - predicted) ** 2))
        ss_tot = float(np.sum((y - y.mean()) ** 2))
        if ss_tot == 0.0:
            result[col] = float("inf")
            continue
        r_squared = 1.0 - ss_res / ss_tot
        if r_squared >= 1.0:
            result[col] = float("inf")
        else:
            result[col] = 1.0 / (1.0 - r_squared)
    return result
