"""Treatment identification and causal design scaffolding."""

WINDOW_GAMES_BEFORE_EVENT = 30
WINDOW_GAMES_AFTER_EVENT = 30
EXCLUSION_WINDOW_GAMES = 5


def build_stacked_did_panel() -> list[dict]:
    return []


def run_synthetic_control_for_event(event_id: str) -> dict:
    _ = event_id
    return {}
