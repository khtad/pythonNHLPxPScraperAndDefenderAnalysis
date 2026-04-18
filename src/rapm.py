"""RAPM model scaffolding."""

from dataclasses import dataclass

RAPM_MODEL_VERSION = "v1"


@dataclass(frozen=True)
class RapmRating:
    season: str
    player_id: int
    rapm_off: float
    rapm_def: float
    rapm_off_se: float
    rapm_def_se: float
    model_version: str = RAPM_MODEL_VERSION


def fit_rapm_for_season(season: str) -> list[RapmRating]:
    _ = season
    return []
