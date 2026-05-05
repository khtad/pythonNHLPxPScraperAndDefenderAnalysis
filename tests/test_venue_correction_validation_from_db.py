import importlib.util
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("scipy")
pytest.importorskip("sklearn")


_SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "export_venue_correction_validation_from_db.py"
)
_SPEC = importlib.util.spec_from_file_location(
    "export_venue_correction_validation_from_db", _SCRIPT_PATH
)
exporter = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(exporter)


def test_latest_prior_adjustment_uses_only_past_seasons():
    lookup = {
        "Arena A": [
            ("20102011", 1.5),
            ("20122013", -0.75),
        ]
    }

    assert exporter._latest_prior_adjustment(lookup, "Arena A", "20102011") == 0.0
    assert exporter._latest_prior_adjustment(lookup, "Arena A", "20112012") == 1.5
    assert exporter._latest_prior_adjustment(lookup, "Arena A", "20132014") == -0.75
    assert exporter._latest_prior_adjustment(lookup, "Arena B", "20132014") == 0.0
    assert exporter._latest_prior_adjustment(lookup, None, "20132014") == 0.0


def test_compute_residual_distance_z_scores_by_season_and_venue():
    seasons = np.array(["20202021"] * 6 + ["20212022"] * 2, dtype=object)
    venues = np.array(["A", "A", "B", "B", "C", "C", "A", "A"], dtype=object)
    corrected_distances = np.array([10, 12, 20, 22, 30, 32, 40, 42], dtype=float)

    result = exporter._compute_residual_distance_z_scores(
        seasons,
        venues,
        corrected_distances,
        min_shots=1,
    )

    assert set(result) == {"20202021:A", "20202021:B", "20202021:C"}
    assert result["20202021:A"] == pytest.approx(-1.224744871)
    assert result["20202021:B"] == pytest.approx(0.0)
    assert result["20202021:C"] == pytest.approx(1.224744871)


def test_build_distance_location_shot_rows_uses_in_memory_corrected_distances():
    rows = [
        {
            "season": "20202021",
            "venue_name": "Arena A",
            "shooting_team_id": 12,
            "away_team_id": 12,
            "shot_type": "wrist",
            "manpower_state": "5v5",
            "distance_to_goal": 20.0,
        },
        {
            "season": "20202021",
            "venue_name": "Arena B",
            "shooting_team_id": 13,
            "away_team_id": 13,
            "shot_type": "slap",
            "manpower_state": "5v4",
            "distance_to_goal": 18.0,
        },
    ]

    shot_rows = exporter._build_distance_location_shot_rows(
        rows,
        [17.5, 19.25],
    )

    assert shot_rows == [
        {
            "season": "20202021",
            "venue_name": "Arena A",
            "shooting_team_id": 12,
            "away_team_id": 12,
            "shot_type": "wrist",
            "manpower_state": "5v5",
            "corrected_distance_to_goal": 17.5,
        },
        {
            "season": "20202021",
            "venue_name": "Arena B",
            "shooting_team_id": 13,
            "away_team_id": 13,
            "shot_type": "slap",
            "manpower_state": "5v4",
            "corrected_distance_to_goal": 19.25,
        },
    ]


def test_build_distance_location_shot_rows_requires_aligned_lengths():
    with pytest.raises(ValueError, match="equal length"):
        exporter._build_distance_location_shot_rows([], [12.0])


def test_build_feature_matrix_uses_fixed_shot_type_contract():
    matrix = exporter._build_feature_matrix(
        np.array([12.0, 20.0]),
        np.array([30.0, 40.0]),
        np.array(["deflected", "between-legs"], dtype=object),
    )

    assert matrix.shape == (2, 2 + len(exporter.VALID_SHOT_TYPES))
    assert matrix[0, 0] == pytest.approx(12.0)
    assert matrix[0, 1] == pytest.approx(30.0)
    assert matrix[1, 0] == pytest.approx(20.0)
    assert matrix[1, 1] == pytest.approx(40.0)
    deflected_index = exporter.VALID_SHOT_TYPES.index("deflected")
    between_legs_index = exporter.VALID_SHOT_TYPES.index("between-legs")
    assert matrix[0, 2 + deflected_index] == pytest.approx(1.0)
    assert matrix[1, 2 + between_legs_index] == pytest.approx(1.0)


def test_event_frequency_predicates_define_primary_scope_and_group():
    game_predicate, game_params = exporter._event_frequency_game_predicate(
        exporter.EVENT_FREQUENCY_SCOPE_REGULAR_SEASON
    )
    join_predicate, join_params = exporter._event_frequency_join_predicate(
        exporter.EVENT_FREQUENCY_SCOPE_REGULAR_SEASON,
        exporter.EVENT_FREQUENCY_GROUP_TRAINING_ATTEMPTS,
    )

    assert "substr(CAST(g.game_id AS TEXT), 5, 2) = ?" in game_predicate
    assert game_params == (exporter.REGULAR_SEASON_GAME_TYPE,)
    assert "se.period < ?" in join_predicate
    assert "se.distance_to_goal IS NOT NULL" in join_predicate
    assert exporter._XG_EVENT_SCHEMA_VERSION in join_params
