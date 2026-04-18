"""Transactions and absence-ledger scaffolding."""

from dataclasses import dataclass

MIN_GAMES_FOR_RETURN_FROM_INJURY_EVENT = 3


@dataclass(frozen=True)
class PlayerAbsenceSpell:
    player_id: int
    team_id: int
    start_date: str
    end_date: str | None
    reason: str
    source: str | None


def fetch_daily_transactions(day_iso: str) -> list[dict]:
    _ = day_iso
    return []


def derive_return_from_injury_events(absence_spells: list[PlayerAbsenceSpell]) -> list[dict]:
    _ = absence_spells
    return []
