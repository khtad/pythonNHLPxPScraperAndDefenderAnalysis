# rink_viz.py
#
# Presentation-only module for overlaying NHL shot events on a rink diagram.
# Takes a matplotlib axis + iterable of shot dicts with the column names written
# by src/database.py:insert_shot_events (x_coord, y_coord, is_goal, period).
# Does NOT open database connections.

import numpy as np
import matplotlib.patches as patches


# ── Rink geometry (feet) ────────────────────────────────────────────────────

RINK_HALF_LENGTH = 100.0
RINK_HALF_WIDTH = 42.5
GOAL_X = 89.0
BLUE_LINE_X = 25.0
CREASE_RADIUS = 6.0
FACEOFF_CIRCLE_RADIUS = 15.0
FACEOFF_DOT_X = 69.0
FACEOFF_DOT_Y = 22.0

_CORNER_RADIUS = 28.0
_FACEOFF_DOT_RADIUS = 0.75
_GOAL_NET_DEPTH = 3.0
_GOAL_NET_HALF_HEIGHT = 3.0

_HALF_RINK_XLIM = (-10.0, 105.0)
_FULL_RINK_XLIM = (-105.0, 105.0)
_RINK_YLIM = (-48.0, 48.0)

_BOARD_LW = 1.5
_BLUE_LINE_LW = 2.0
_BLUE_LINE_ALPHA = 0.6
_CENTER_LINE_LW = 1.5
_CENTER_LINE_ALPHA = 0.5
_GOAL_LINE_LW = 1.0
_GOAL_LINE_ALPHA = 0.4
_CREASE_LW = 1.5
_FACEOFF_CIRCLE_LW = 0.8
_FACEOFF_CIRCLE_ALPHA = 0.5


# ── Shot-overlay style ──────────────────────────────────────────────────────

PERIOD_COLORS = {
    1: "#1f77b4",
    2: "#ff7f0e",
    3: "#2ca02c",
    4: "#d62728",
    5: "#9467bd",
}
PERIOD_LABELS = {1: "P1", 2: "P2", 3: "P3", 4: "OT", 5: "SO"}

_UNKNOWN_PERIOD_COLOR = "gray"
_DEFAULT_SHOT_COLOR = "C0"
_DEFAULT_SHOT_ALPHA = 0.6
_DEFAULT_SHOT_SIZE = 30
_DEFAULT_GOAL_MARKER_SIZE = 120
_DEFAULT_GOAL_MARKER = "*"
_DEFAULT_GOAL_EDGE_COLOR = "k"
_DEFAULT_GOAL_EDGE_LW = 0.5
_GOAL_ALPHA = 0.9
_SHOT_ZORDER = 3
_GOAL_ZORDER = 4


# ── Density style ───────────────────────────────────────────────────────────

_HEXBIN_GRIDSIZE = 40
_HEXBIN_MIN_COUNT = 1
_HEXBIN_LOG_SCALE_THRESHOLD = 50_000
_HEATMAP_X_BINS = 40
_HEATMAP_Y_BINS = 17
_KDE_LEVELS = 10
_KDE_BW_ADJUST = 1.0
_DEFAULT_DENSITY_CMAP = "Reds"
_DEFAULT_DENSITY_ALPHA = 0.85

_VALID_DENSITY_METHODS = ("hexbin", "heatmap", "kde")


# ── Rink drawing ────────────────────────────────────────────────────────────

def _apply_common_axis_settings(ax, xlim):
    ax.set_xlim(xlim)
    ax.set_ylim(_RINK_YLIM)
    ax.set_aspect("equal")
    ax.set_xlabel("x (feet)")
    ax.set_ylabel("y (feet)")


def _draw_faceoff_markers(ax, center_x, center_y):
    circle = patches.Circle(
        (center_x, center_y), FACEOFF_CIRCLE_RADIUS,
        fill=False, edgecolor="red",
        lw=_FACEOFF_CIRCLE_LW, alpha=_FACEOFF_CIRCLE_ALPHA,
    )
    ax.add_patch(circle)
    dot = patches.Circle(
        (center_x, center_y), _FACEOFF_DOT_RADIUS,
        fill=True, facecolor="red", edgecolor="red",
    )
    ax.add_patch(dot)


def _draw_crease_and_net(ax, goal_x, attacking_right):
    theta1, theta2 = (270, 90) if attacking_right else (90, 270)
    crease = patches.Arc(
        (goal_x, 0), 2 * CREASE_RADIUS, 2 * CREASE_RADIUS,
        angle=0, theta1=theta1, theta2=theta2,
        color="blue", lw=_CREASE_LW,
    )
    ax.add_patch(crease)
    net_x = goal_x if attacking_right else goal_x - _GOAL_NET_DEPTH
    net = patches.Rectangle(
        (net_x, -_GOAL_NET_HALF_HEIGHT),
        _GOAL_NET_DEPTH, 2 * _GOAL_NET_HALF_HEIGHT,
        fill=False, edgecolor="red", lw=_BOARD_LW,
    )
    ax.add_patch(net)


def draw_half_rink(ax):
    """Draw the attacking half of an NHL rink (x from -5 to 100, goal at +x)."""
    ax.plot([-5, RINK_HALF_LENGTH], [-RINK_HALF_WIDTH, -RINK_HALF_WIDTH],
            "k-", lw=_BOARD_LW)
    ax.plot([-5, RINK_HALF_LENGTH], [RINK_HALF_WIDTH, RINK_HALF_WIDTH],
            "k-", lw=_BOARD_LW)

    for sign_y in (-1, 1):
        cx = RINK_HALF_LENGTH - _CORNER_RADIUS
        cy = sign_y * (RINK_HALF_WIDTH - _CORNER_RADIUS)
        theta1, theta2 = (0, 90) if sign_y > 0 else (270, 360)
        arc = patches.Arc(
            (cx, cy), 2 * _CORNER_RADIUS, 2 * _CORNER_RADIUS,
            angle=0, theta1=theta1, theta2=theta2, color="k", lw=_BOARD_LW,
        )
        ax.add_patch(arc)

    ax.axvline(x=0, color="red", lw=_CENTER_LINE_LW,
               ls="--", alpha=_CENTER_LINE_ALPHA, label="_nolegend_")
    ax.axvline(x=BLUE_LINE_X, color="blue", lw=_BLUE_LINE_LW,
               alpha=_BLUE_LINE_ALPHA, label="_nolegend_")
    ax.axvline(x=GOAL_X, color="red", lw=_GOAL_LINE_LW,
               alpha=_GOAL_LINE_ALPHA, label="_nolegend_")

    _draw_crease_and_net(ax, GOAL_X, attacking_right=True)

    for sign_y in (-1, 1):
        _draw_faceoff_markers(ax, FACEOFF_DOT_X, sign_y * FACEOFF_DOT_Y)

    _apply_common_axis_settings(ax, _HALF_RINK_XLIM)
    return ax


def draw_full_rink(ax):
    """Draw a full NHL rink diagram (x from -100 to 100, goals at both ends)."""
    ax.plot([-RINK_HALF_LENGTH, RINK_HALF_LENGTH],
            [-RINK_HALF_WIDTH, -RINK_HALF_WIDTH], "k-", lw=_BOARD_LW)
    ax.plot([-RINK_HALF_LENGTH, RINK_HALF_LENGTH],
            [RINK_HALF_WIDTH, RINK_HALF_WIDTH], "k-", lw=_BOARD_LW)

    for sign_x in (-1, 1):
        for sign_y in (-1, 1):
            cx = sign_x * (RINK_HALF_LENGTH - _CORNER_RADIUS)
            cy = sign_y * (RINK_HALF_WIDTH - _CORNER_RADIUS)
            if sign_x > 0 and sign_y > 0:
                theta1, theta2 = 0, 90
            elif sign_x > 0 and sign_y < 0:
                theta1, theta2 = 270, 360
            elif sign_x < 0 and sign_y > 0:
                theta1, theta2 = 90, 180
            else:
                theta1, theta2 = 180, 270
            arc = patches.Arc(
                (cx, cy), 2 * _CORNER_RADIUS, 2 * _CORNER_RADIUS,
                angle=0, theta1=theta1, theta2=theta2,
                color="k", lw=_BOARD_LW,
            )
            ax.add_patch(arc)

    ax.axvline(x=0, color="red", lw=_CENTER_LINE_LW, alpha=_CENTER_LINE_ALPHA)
    ax.axvline(x=BLUE_LINE_X, color="blue", lw=_BLUE_LINE_LW, alpha=_BLUE_LINE_ALPHA)
    ax.axvline(x=-BLUE_LINE_X, color="blue", lw=_BLUE_LINE_LW, alpha=_BLUE_LINE_ALPHA)

    for sign_x in (-1, 1):
        goal_x = sign_x * GOAL_X
        ax.axvline(x=goal_x, color="red", lw=_GOAL_LINE_LW, alpha=_GOAL_LINE_ALPHA)
        _draw_crease_and_net(ax, goal_x, attacking_right=(sign_x > 0))
        for sign_y in (-1, 1):
            _draw_faceoff_markers(
                ax, sign_x * FACEOFF_DOT_X, sign_y * FACEOFF_DOT_Y)

    _apply_common_axis_settings(ax, _FULL_RINK_XLIM)
    return ax


# ── Shot scatter ────────────────────────────────────────────────────────────

def _keep_shot(shot):
    return shot.get("x_coord") is not None and shot.get("y_coord") is not None


def _scatter_period_group(ax, period, period_shots, goal_markers, alpha, size):
    color = PERIOD_COLORS.get(period, _UNKNOWN_PERIOD_COLOR)
    label = PERIOD_LABELS.get(period, f"P{period}")

    x_ng, y_ng, x_g, y_g = [], [], [], []
    for s in period_shots:
        if s.get("is_goal"):
            x_g.append(s["x_coord"])
            y_g.append(s["y_coord"])
        else:
            x_ng.append(s["x_coord"])
            y_ng.append(s["y_coord"])

    ax.scatter(x_ng, y_ng, c=color, s=size, alpha=alpha,
               label=label, edgecolors="none", zorder=_SHOT_ZORDER)
    if goal_markers and x_g:
        ax.scatter(x_g, y_g, c=color, s=_DEFAULT_GOAL_MARKER_SIZE,
                   alpha=_GOAL_ALPHA, marker=_DEFAULT_GOAL_MARKER,
                   edgecolors=_DEFAULT_GOAL_EDGE_COLOR,
                   linewidths=_DEFAULT_GOAL_EDGE_LW, zorder=_GOAL_ZORDER)


def plot_shots(ax, shots, color_by="period", goal_markers=True,
               alpha=_DEFAULT_SHOT_ALPHA, size=_DEFAULT_SHOT_SIZE, legend=True):
    """Scatter shots on ax. Filters out shots with missing coords.

    color_by="period" groups by shot["period"] using PERIOD_COLORS.
    color_by=None draws a single series in the default color.
    Goals render as star markers above non-goals when goal_markers=True.
    Does not draw the rink — caller controls the background.
    """
    filtered = [s for s in shots if _keep_shot(s)]

    if color_by == "period":
        periods = sorted({s["period"] for s in filtered if s.get("period") is not None})
        for period in periods:
            period_shots = [s for s in filtered if s.get("period") == period]
            if period_shots:
                _scatter_period_group(
                    ax, period, period_shots, goal_markers, alpha, size)
    elif color_by is None:
        x_ng, y_ng, x_g, y_g = [], [], [], []
        for s in filtered:
            if s.get("is_goal"):
                x_g.append(s["x_coord"])
                y_g.append(s["y_coord"])
            else:
                x_ng.append(s["x_coord"])
                y_ng.append(s["y_coord"])
        ax.scatter(x_ng, y_ng, c=_DEFAULT_SHOT_COLOR, s=size, alpha=alpha,
                   edgecolors="none", zorder=_SHOT_ZORDER)
        if goal_markers and x_g:
            ax.scatter(x_g, y_g, c=_DEFAULT_SHOT_COLOR,
                       s=_DEFAULT_GOAL_MARKER_SIZE, alpha=_GOAL_ALPHA,
                       marker=_DEFAULT_GOAL_MARKER,
                       edgecolors=_DEFAULT_GOAL_EDGE_COLOR,
                       linewidths=_DEFAULT_GOAL_EDGE_LW, zorder=_GOAL_ZORDER)
    else:
        raise ValueError(
            f"Unsupported color_by={color_by!r}; expected 'period' or None")

    if legend and color_by == "period" and filtered:
        ax.legend(loc="upper left", fontsize=8)
    return ax


# ── Density overlays ────────────────────────────────────────────────────────

def _shot_xy_arrays(shots):
    x = np.array([s["x_coord"] for s in shots if _keep_shot(s)], dtype=float)
    y = np.array([s["y_coord"] for s in shots if _keep_shot(s)], dtype=float)
    return x, y


def _extent_from_ax(ax):
    xlim = ax.get_xlim()
    ylim = ax.get_ylim()
    return (xlim[0], xlim[1], ylim[0], ylim[1])


def plot_shot_density(ax, shots, method="hexbin", cmap=_DEFAULT_DENSITY_CMAP,
                      alpha=_DEFAULT_DENSITY_ALPHA, gridsize=_HEXBIN_GRIDSIZE,
                      extent=None, colorbar=True):
    """Overlay a density estimate of shot locations on ax.

    method:
        "hexbin"  — ax.hexbin; fastest and safest at full-dataset scale.
                    Auto-switches to log-count scale above
                    _HEXBIN_LOG_SCALE_THRESHOLD points.
        "heatmap" — np.histogram2d + imshow; rectangular bins.
        "kde"     — seaborn.kdeplot; smooth but slow and may bleed past boards.

    extent: (xmin, xmax, ymin, ymax); if None, inferred from the current
    ax xlim/ylim so density cells align with the rink drawn under ax.
    """
    if method not in _VALID_DENSITY_METHODS:
        raise ValueError(
            f"Invalid method={method!r}; expected one of {_VALID_DENSITY_METHODS}")

    x, y = _shot_xy_arrays(shots)
    if extent is None:
        extent = _extent_from_ax(ax)
    xmin, xmax, ymin, ymax = extent

    if method == "hexbin":
        bins = "log" if len(x) > _HEXBIN_LOG_SCALE_THRESHOLD else None
        mappable = ax.hexbin(
            x, y, gridsize=gridsize, extent=(xmin, xmax, ymin, ymax),
            cmap=cmap, alpha=alpha, mincnt=_HEXBIN_MIN_COUNT, bins=bins,
        )
    elif method == "heatmap":
        hist, _, _ = np.histogram2d(
            x, y, bins=(_HEATMAP_X_BINS, _HEATMAP_Y_BINS),
            range=[[xmin, xmax], [ymin, ymax]],
        )
        mappable = ax.imshow(
            hist.T, origin="lower", extent=(xmin, xmax, ymin, ymax),
            aspect="equal", cmap=cmap, alpha=alpha, interpolation="nearest",
        )
    else:
        import seaborn as sns
        mappable = sns.kdeplot(
            x=x, y=y, ax=ax, fill=True, cmap=cmap, alpha=alpha,
            levels=_KDE_LEVELS, bw_adjust=_KDE_BW_ADJUST,
        )

    if colorbar and method in ("hexbin", "heatmap"):
        ax.figure.colorbar(mappable, ax=ax, shrink=0.7)
    return mappable


# ── Composite convenience ───────────────────────────────────────────────────

def plot_game_shot_chart(ax, shots, *, full_rink=False, color_by="period",
                         goal_markers=True):
    """Draw the rink on ax and scatter the game's shots on top."""
    if full_rink:
        draw_full_rink(ax)
    else:
        draw_half_rink(ax)
    plot_shots(ax, shots, color_by=color_by, goal_markers=goal_markers)
    return ax
