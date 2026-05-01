"""Backfill NHL shift-chart data into shift-derived tables."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from database import DATABASE_PATH
from shift_population import backfill_shift_data, format_shift_population_summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Populate shifts, on-ice intervals, and shot-event on-ice slots."
    )
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument(
        "--all",
        action="store_true",
        help="Backfill all games with shot events that are missing current shift data.",
    )
    selection.add_argument(
        "--game-id",
        type=int,
        help="Backfill one specific NHL game id.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of missing games to process with --all.",
    )
    parser.add_argument(
        "--database-path",
        default=DATABASE_PATH,
        help="SQLite database path. Defaults to data/nhl_data.db.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.limit is not None and args.game_id is not None:
        parser.error("--limit can only be used with --all.")

    result = backfill_shift_data(
        database_path=args.database_path,
        all_games=args.all,
        limit=args.limit,
        game_id=args.game_id,
    )
    print(format_shift_population_summary(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
