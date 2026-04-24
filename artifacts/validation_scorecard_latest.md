# Validation Scorecard (Latest Run)

Phase 2.5.3 requires running `notebooks/model_validation_framework.ipynb` against a populated live database at `data/nhl_data.db`.

As of 2026-04-24 in this container, `data/nhl_data.db` is not present, so the end-to-end run is currently blocked in this environment.

Use the command below once the live database is available:

```bash
python scripts/export_validation_scorecard.py --db-path data/nhl_data.db
```
