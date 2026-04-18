import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pytest

from rink_viz import (
    _FULL_RINK_XLIM,
    _HALF_RINK_XLIM,
    _RINK_YLIM,
    draw_full_rink,
    draw_half_rink,
    plot_game_shot_chart,
    plot_shot_density,
    plot_shots,
)


_EXPECTED_HALF_RINK_PATCHES = 7
_EXPECTED_FULL_RINK_PATCHES = 16


@pytest.fixture
def ax():
    fig, axis = plt.subplots()
    yield axis
    plt.close(fig)


def _make_shot(x, y, period=1, is_goal=False):
    return {"x_coord": x, "y_coord": y, "period": period, "is_goal": 1 if is_goal else 0}


def test_draw_half_rink_adds_patches_and_sets_limits(ax):
    draw_half_rink(ax)
    assert len(ax.patches) >= _EXPECTED_HALF_RINK_PATCHES
    assert ax.get_xlim() == _HALF_RINK_XLIM
    assert ax.get_ylim() == _RINK_YLIM
    assert ax.get_aspect() == 1.0  # matplotlib returns 1.0 for "equal"


def test_draw_full_rink_adds_patches_and_sets_limits(ax):
    draw_full_rink(ax)
    assert len(ax.patches) >= _EXPECTED_FULL_RINK_PATCHES
    assert ax.get_xlim() == _FULL_RINK_XLIM
    assert ax.get_ylim() == _RINK_YLIM
    assert ax.get_aspect() == 1.0


def test_plot_shots_respects_goal_markers_flag(ax):
    shots = [
        _make_shot(60, 10, period=1, is_goal=False),
        _make_shot(80, 0, period=1, is_goal=True),
    ]
    plot_shots(ax, shots, goal_markers=True)
    with_goals = len(ax.collections)
    ax.clear()

    plot_shots(ax, shots, goal_markers=False)
    without_goals = len(ax.collections)

    assert with_goals == without_goals + 1


def test_plot_shots_filters_none_coords(ax):
    shots = [
        _make_shot(60, 10, period=1),
        {"x_coord": None, "y_coord": 5, "period": 1, "is_goal": 0},
        {"x_coord": 70, "y_coord": None, "period": 1, "is_goal": 0},
    ]
    plot_shots(ax, shots, goal_markers=False, legend=False)
    # One period-1 scatter for two valid shots; None-coord shots must be excluded.
    # A failure to filter would raise in matplotlib when drawing.
    assert len(ax.collections) == 1
    assert ax.collections[0].get_offsets().shape[0] == 1


def test_plot_shots_rejects_unsupported_color_by(ax):
    with pytest.raises(ValueError):
        plot_shots(ax, [_make_shot(0, 0)], color_by="shot_type")


def test_plot_shot_density_rejects_bad_method(ax):
    draw_half_rink(ax)
    with pytest.raises(ValueError):
        plot_shot_density(ax, [_make_shot(60, 0)], method="scatter")


def test_plot_shot_density_hexbin_runs(ax):
    draw_half_rink(ax)
    shots = [_make_shot(60 + i % 20, (i % 17) - 8) for i in range(100)]
    mappable = plot_shot_density(ax, shots, method="hexbin", colorbar=False)
    assert mappable is not None


def test_plot_shot_density_heatmap_runs(ax):
    draw_half_rink(ax)
    shots = [_make_shot(60 + i % 20, (i % 17) - 8) for i in range(100)]
    mappable = plot_shot_density(ax, shots, method="heatmap", colorbar=False)
    assert mappable is not None


def test_plot_shot_density_kde_runs_small_sample(ax):
    draw_half_rink(ax)
    shots = [_make_shot(60 + (i % 10), (i % 8) - 4) for i in range(50)]
    mappable = plot_shot_density(ax, shots, method="kde", colorbar=False)
    assert mappable is not None


def test_plot_game_shot_chart_half_rink(ax):
    shots = [_make_shot(80, 5, period=1, is_goal=True)]
    plot_game_shot_chart(ax, shots, full_rink=False)
    assert ax.get_xlim() == _HALF_RINK_XLIM
    assert len(ax.collections) >= 1


def test_plot_game_shot_chart_full_rink(ax):
    shots = [_make_shot(80, 5, period=2, is_goal=False)]
    plot_game_shot_chart(ax, shots, full_rink=True)
    assert ax.get_xlim() == _FULL_RINK_XLIM
    assert len(ax.collections) >= 1
