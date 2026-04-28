# Validation Scorecard (Latest Run)

Phase 2.5.3 requires running `notebooks/model_validation_framework.ipynb` against a populated live database at `data/nhl_data.db`.

As of 2026-04-28 in this workspace, `data/nhl_data.db` is present, but the
end-to-end scorecard is still blocked by current-schema coverage:

- `shot_events` rows safely promoted from v4 to v5 via raw game-table event reconstruction: 1,574,298
- `shot_events` rows still at v4 after conservative reconstruction: 546,702
- Training-eligible post-2009 complete-geometry rows still below the current schema version: 507,543

`scripts/export_validation_scorecard.py` now runs schema prep first and refuses
to export a partial scorecard while any training-eligible rows remain stale.
Run the current-schema backfill for the remaining stale games, or extend the
offline raw-table reconstruction with a validated matching strategy, before
publishing live validation metrics.

Use the command below once the live database is current:

```bash
python scripts/export_validation_scorecard.py --db-path data/nhl_data.db
```
