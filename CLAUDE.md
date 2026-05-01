# CLAUDE.md

> **Note for non-Claude agents:** [`AGENTS.md`](./AGENTS.md) points here. This file is the authoritative source of project rules for every agent and model. If you are reading `AGENTS.md` first, continue here.

## Project Overview

NHL Play-by-Play (PXP) scraper with a normalized player analytics schema. Raw events are scraped and stored per game, then aggregated into player/game fact and feature tables.

## Repository Structure

```
├── data/                           # Database storage directory (created at runtime)
│   └── nhl_data.db                 # SQLite database (not checked in)
├── src/
│   ├── main.py                     # Entry point; scrape loop iterating dates from 2007-10-03 to today
│   ├── nhl_api.py                  # NHL Stats API client (schedule + live feed endpoints)
│   └── database.py                 # SQLite operations for raw and normalized player schema
├── tests/
│   ├── conftest.py                 # Pytest import path setup (adds src/ to sys.path)
│   ├── test_database.py            # DB schema + data quality unit tests
│   └── test_nhl_api.py             # API parsing/error-path unit tests
├── docs/
│   ├── xg_model_roadmap.md         # xG model development roadmap (main plan)
│   └── xg_model_components/        # Detailed component design docs
├── knowledge_base/                 # LLM Knowledge Base (domain knowledge wiki)
│   ├── SCHEMA.md                   # Wiki governance: article format, workflows, conventions
│   ├── index.md                    # Content catalog (updated on every ingest)
│   ├── log.md                      # Append-only chronological operations log
│   ├── raw/                        # Immutable source documents (external + project refs)
│   └── wiki/                       # LLM-maintained articles (concepts, methods, data, models)
├── README.md                       # Project documentation
└── requirements.txt                # Dependencies
```

## Knowledge Base

The `knowledge_base/` directory contains a structured domain-knowledge wiki for NHL analytics concepts, methods, and data sources, following the [Karpathy LLM Knowledge Base](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) architecture. It is governed by `knowledge_base/SCHEMA.md`.

**Relationship to other project documents:**
- The wiki is complementary to `docs/` (implementation planning) and does not replace it.
- `docs/` answers "how are we going to build this?" — the wiki answers "what is this concept and why does it matter?"
- Wiki articles may reference `docs/`, `notebooks/`, and `src/` but the direction is wiki → project, not the reverse.

**When to consult the wiki:**
- Before making model design decisions, check relevant concept and method articles for domain context.
- When adding a new feature or analysis, check whether the wiki has an article on the underlying concept.

**Wiki maintenance operations** (ingest, lint) follow the workflows specified in `knowledge_base/SCHEMA.md` and must be logged in `knowledge_base/log.md`.

## Database Path Constants

Defined in `database.py` and imported by `main.py`:

- `DATABASE_DIR` — absolute path to the `data/` directory at project root
- `DATABASE_FILENAME` — `"nhl_data.db"`
- `DATABASE_PATH` — full absolute path: `data/nhl_data.db`

`main.main()` ensures `DATABASE_DIR` exists via `os.makedirs` before connecting.

## Architecture & Data Flow

```
main.main()
  → nhl_api.get_weekly_schedule(date)
  → nhl_api.get_play_by_play_data(game_id)
  → database.create_table(conn, game_id)                  # raw game_<id>
  → database.insert_data(conn, game_id, data)             # raw events

player-schema bootstrap
  → database.ensure_player_database_schema(conn)
     → create_core_dimension_tables(conn)                 # players/games/teams
     → create_player_game_stats_table(conn)               # one row per player+game
     → create_player_game_features_table(conn)            # rolling materialized features
```

## Player Schema Details

- `players(player_id PRIMARY KEY, first_name, last_name, shoots_catches, position, team_id)`
- `games(game_id PRIMARY KEY, game_date, season, home_team_id, away_team_id)`
- `teams(team_id PRIMARY KEY, team_abbrev, team_name)`
- `player_game_stats(..., PRIMARY KEY(player_id, game_id))`
  - Includes `position_group`, `toi_seconds`, counting stats, and xG placeholders
  - Indexes:
    - `idx_player_game_stats_game_id`
    - `idx_player_game_stats_position_group_game_id`
- `player_game_features(..., PRIMARY KEY(player_id, game_id))`
  - Includes rolling/rank placeholders and `feature_set_version`

## Data Quality Validation

`validate_player_game_stats_quality(conn, max_toi_seconds=3600)` checks:

- duplicate `(player_id, game_id)` rows
- negative TOI
- TOI above a configurable maximum
- invalid `position_group` outside `{F, D, G}`

## Testing Notes

- Framework: `pytest` + in-memory SQLite + request mocks
- The player-schema tests are written in phase style (dimensions, fact table, features, validation)
- **How to run tests**: Use `python3 -m venv /tmp/test-venv && /tmp/test-venv/bin/pip install -q pytest requests && /tmp/test-venv/bin/python -m pytest -q --ignore=tests/test_rink_viz.py --ignore=tests/test_stats_helpers.py` (or reuse the venv if it already exists: `/tmp/test-venv/bin/python -m pytest -q --ignore=tests/test_rink_viz.py --ignore=tests/test_stats_helpers.py`). Do not call `pytest` directly — the system Python does not have pytest installed. The `--ignore` flags are required unless the corresponding optional dependencies have been explicitly installed into the venv (see failures 3 and 5 below); without them, pytest collection fails and zero tests run.
- **Notebook dependencies**: When creating or modifying Jupyter notebooks, automatically install any required packages (e.g., `matplotlib`, `seaborn`, `numpy`, `ipykernel`) into the project virtual environment at `/tmp/test-venv` using `/tmp/test-venv/bin/pip install`. Do not assume packages are already installed — always install before first use.

## Test Failures Encountered, Fixes, and Prevention Rules

1. **Failure:** `ImportError` during pytest collection for newly referenced player-schema functions.
   - **Cause:** Tests were added first (TDD) before implementing the new functions in `database.py`.
   - **Fix:** Implemented missing schema functions:
     - `create_core_dimension_tables`
     - `create_player_game_stats_table`
     - `create_player_game_features_table`
     - `validate_player_game_stats_quality`
     - `ensure_player_database_schema`
   - **Rules to avoid repeat failures of this type:**
     - Add tests first for new behavior, then immediately implement all imported function stubs before running the full suite.
     - Run `pytest -q` after adding new imports to detect collection-time errors early.
     - Keep phase-based function names stable between tests and implementation to avoid naming drift.

2. **Failure:** Notebook analyses pointed at the correct `nhl_data.db`, but analysis tables were empty because the database contained only raw `game_<id>` tables and the scraper skipped those games before backfilling metadata and `shot_events`.
   - **Cause:** The scraper treated `is_game_collected(conn, game_id)` as equivalent to "fully processed", even though derived tables (`games`, `shot_events`, `game_context`, etc.) were still missing. A related catalog-scan bug also matched the `games` dimension table with `LIKE 'game_%'`.
   - **Fix:** Added a shared game-processing state check so a game is only skipped when raw rows, metadata, and derived shot rows all exist; added an explicit idempotent backfill entry point; restricted raw-table scans to names matching `game_<digits>` only.
   - **Rules to avoid repeat failures of this type:**
     - Treat raw ingestion and derived-data population as separate completeness checks. A game is not "done" unless raw rows and all required derived rows for the current pipeline stage exist.
     - Any scraper change that adds a new derived table or feature extraction step must also add or update a backfill path for existing databases. Never assume historical databases can be repaired from future incremental runs alone.
     - Backfill code must be idempotent by construction and by test: rerunning it against an already repaired database must perform no additional inserts and should avoid repeat API fetches for complete games.
     - When scanning `sqlite_master` for raw game tables, never rely on `LIKE 'game_%'` alone. Always filter to the stricter pattern `game_<digits>` so dimension tables such as `games` are never misclassified as raw event tables.
     - Notebook analysis instructions must not treat the presence of a large database file or raw game tables as evidence that analysis tables are populated. Include an explicit refresh/backfill step or note whenever notebooks depend on derived tables.

3. **Failure:** `ModuleNotFoundError: No module named 'matplotlib'` during pytest **collection** of `tests/test_rink_viz.py`, aborting the entire suite before any tests ran (pytest reported `1 error in X.XXs` with zero tests executed).
   - **Cause:** The canonical `/tmp/test-venv` installs only `pytest` and `requests`. `tests/test_rink_viz.py` imports `matplotlib` at module scope, so pytest's collection phase fails on that file and — because collection errors are fatal by default — the whole run is aborted before any other test module is even loaded. Collection errors are not the same as test failures; `0 passed, 1 error` looks superficially like success in a hurried glance but means the suite did not run.
   - **Fix:** Invoke pytest with `--ignore=tests/test_rink_viz.py` unless `matplotlib` has been explicitly installed via `/tmp/test-venv/bin/pip install matplotlib`. Updated the "How to run tests" canonical command above to include the flag.
   - **Rules to avoid repeat failures of this type:**
     - The canonical test command in "Testing Notes" is authoritative. Use it verbatim — including `--ignore=tests/test_rink_viz.py` — unless the ignored file's dependencies have been installed for this session.
     - When adding a test file that imports a heavy optional dependency (`matplotlib`, `seaborn`, `ipykernel`, etc.), guard the import at module top with `pytest.importorskip("<name>")` so a missing dependency *skips* that file instead of breaking collection for the whole suite.
     - Before reporting a test run as clean, read the pytest summary line. `N passed` is success; `1 error in X.XXs` (or any non-zero `error` count) means collection failed and no assertions were checked — investigate and re-run, never treat as green.
     - When a venv is reused across sessions, do not assume its installed package set is stable. If a test file's imports depend on non-default packages, either install them defensively before the run or add the file to `--ignore` until they are present.

4. **Failure:** `validate_game_context_quality` undercounted structural rest-day nulls — rows where one team had prior history but the opponent was making its first tracked appearance were classified as data-quality anomalies instead of expected structural nulls, distorting the null-rate diagnostics used for roadmap acceptance checks.
   - **Cause:** The structural-null predicate was a single `NOT EXISTS (... WHERE g2.home_team_id = g.home_team_id OR g2.away_team_id = g.home_team_id OR g2.home_team_id = g.away_team_id OR g2.away_team_id = g.away_team_id)`. By De Morgan's law, `NOT EXISTS (A OR B)` is `NOT A AND NOT B` — so the predicate matched only rows where *both* teams had zero prior games. But `home_rest_days` and `away_rest_days` are null **independently**: either one can be null while the other is populated, which means the row is structurally-null even though the predicate missed it.
   - **Fix:** Replaced the single `NOT EXISTS` with a boolean OR of two `NOT EXISTS` clauses — one scoped to the home team's prior games, one to the away team's prior games. Updated the existing test's assertion from `structural_null_rest_rows == 1` to `== 2` to reflect the correct semantics, and added `test_validate_game_context_quality_counts_partial_structural_null` to lock in coverage for the one-team-debuting-against-veteran case.
   - **Rules to avoid repeat failures of this type:**
     - When counting rows where **any** of several independent nullability conditions hold, OR the predicates at the top level (a boolean OR of separate `NOT EXISTS`/`IS NULL`/`= 0` expressions). Do **not** push the OR down into a single predicate with OR'd sub-conditions inside a `NOT EXISTS` — `NOT EXISTS (A OR B)` means AND, not OR, on the outer result. When in doubt, truth-table the predicate on paper before committing the query.
     - Any validator that separates "structural nulls" from "quality nulls" must have a test that exercises **partial** structural nullability (one affected column, one populated column) in addition to the all-null and all-populated cases. A validator whose only test is the trivial uniform case cannot catch predicate-shape bugs like this one.
     - When a downstream consumer (a roadmap acceptance check, a report, a dashboard) will trust a validator's counts, treat the validator's predicate as a load-bearing expression: review every boolean connector in it for the intended row set, not just the column references.

5. **Failure:** `ModuleNotFoundError: No module named 'numpy'` (then `'pandas'`) during pytest **collection** of `tests/test_stats_helpers.py`, aborting the entire suite.
   - **Cause:** `tests/test_stats_helpers.py` imports `numpy` and `pandas` at module scope. The canonical `/tmp/test-venv` installs only `pytest` and `requests`, so collection fails on that file before any other test module runs.
   - **Fix:** Add `--ignore=tests/test_stats_helpers.py` to the canonical test command. Updated "How to run tests" above to include both ignore flags. Install `numpy` and `pandas` first if tests in that file need to run.
   - **Rules to avoid repeat failures of this type:**
     - The canonical test command is authoritative and must list all `--ignore` flags for files whose dependencies are not in the base venv install. Update it whenever a new such file is added.
     - Any test file that imports `numpy`, `pandas`, `scipy`, or other heavy data-science packages at module scope must either guard with `pytest.importorskip("<name>")` or be added to `--ignore` in the canonical command.

6. **Failure:** `requests.exceptions.ProxyError` during unit tests in `tests/test_main.py` when `main.refresh_player_tables()` attempted live calls to `https://api-web.nhle.com/v1/player/{id}/landing`.
   - **Cause:** `_api_get_with_status` in `src/nhl_api.py` handled non-200 HTTP responses but did not catch transport-layer exceptions (`RequestException`). In the sandbox/proxy environment, those exceptions propagated and failed tests that did not mock player metadata fetches.
   - **Fix:** Wrapped `_session.get(url)` in `try/except requests.RequestException` and returned `(None, 0)` after logging, so callers treat transport failures as retryable transient misses (same behavior as other non-200 failures). Added a regression test `test_get_game_ids_for_date_handles_request_exception`.
   - **Rules to avoid repeat failures of this type:**
     - Every HTTP helper must handle both HTTP status failures **and** transport exceptions. Do not allow raw `RequestException` to bubble out of low-level fetch wrappers.
     - When adding new scraper/backfill steps that perform network calls during `main()` integration tests, ensure the network path is mockable and degrades gracefully to a no-op on transient failures.
     - Add at least one unit test that simulates `requests.RequestException` for each API helper family to lock in retryable behavior.

7. **Failure:** PowerShell inspection commands using `python` and `py -3` failed on the Windows Codex desktop thread (`python` was not on PATH and `py` pointed at an unusable WindowsApps target).
   - **Cause:** The local shell environment did not expose a working Python interpreter directly, and the launcher registration was stale/broken for stdin-driven one-off scripts.
   - **Fix:** Call `load_workspace_dependencies` and invoke the bundled interpreter path it returns (for example `C:\Users\...\dependencies\python\python.exe`) instead of assuming `python` or `py` will work.
   - **Rules to avoid repeat failures of this type:**
     - On Codex desktop Windows threads, do not assume `python` is available on PATH. Verify the interpreter first or use the bundled runtime path from `load_workspace_dependencies`.
     - If a quick inspection/query script needs Python in this environment, prefer the bundled interpreter returned by `load_workspace_dependencies` over `py -3`, especially for stdin-piped scripts.
     - PowerShell does not support bash heredocs such as `python - <<'PY'`. For stdin-driven scripts in PowerShell, use a here-string piped into the bundled interpreter, for example `@' ... '@ | & "<python.exe>" -`.

8. **Failure:** The repository-local Windows venv launcher (`.venv\Scripts\python.exe`) failed with `No Python at '"/usr/bin\python.exe'`.
   - **Cause:** The checked-in `.venv` was created from a WSL/Linux interpreter, so `pyvenv.cfg` points at `/usr/bin/python3.12` and the Windows launcher cannot resolve that home interpreter.
   - **Fix:** Inspect `.venv\pyvenv.cfg` before relying on a repo-local venv on Windows. If `home` or `executable` points at a Unix path, treat the venv as unusable from Windows and use another interpreter or recreate the venv in the current OS.
   - **Rules to avoid repeat failures of this type:**
     - On Windows, do not assume `.venv\Scripts\python.exe` is valid just because the file exists. Check `.venv\pyvenv.cfg` when the workspace may have been shared across WSL/Linux and Windows.
     - If a repo-local venv is cross-OS broken, do not spend time debugging package imports inside it. Switch to a known-good interpreter or recreate the venv for the active platform.

9. **Failure:** Git commands failed with `fatal: detected dubious ownership in repository` on the Windows Codex desktop thread.
   - **Cause:** The current shell user SID did not match the repository owner's SID, so Git's safe-directory protection blocked status/diff commands.
   - **Fix:** If Git metadata is required, add the repository path to Git's safe-directory list after user approval (for example `git config --global --add safe.directory <repo>`). If approval is not available, fall back to direct file inspection for verification.
   - **Rules to avoid repeat failures of this type:**
     - On Windows Codex desktop threads, do not assume Git commands will work even for read-only status checks. If you see a dubious-ownership error, stop relying on Git output until the repo is marked safe.
     - Treat `git config --global --add safe.directory ...` as an environment mutation that needs user approval; do not apply it silently.

10. **Failure:** The Windows bundled Python could run focused tests but the broader suite failed collection with `ModuleNotFoundError` for `requests`, and validation tests skipped because `scipy` was missing.
   - **Cause:** The runtime had `pytest`, `numpy`, and notebook plotting packages installed, but not all packages imported by source modules and validation notebooks. `requirements.txt` listed `requests` but did not list `scipy` or `scikit-learn`, even though `src/validation.py` imports them.
   - **Fix:** Installed the missing runtime packages with `python -m pip install requests scipy scikit-learn` using the bundled interpreter, then added `scipy` and `scikit-learn` to `requirements.txt`.
   - **Rules to avoid repeat failures of this type:**
     - After adding or modifying notebooks or source files that import statistical packages, update `requirements.txt` in the same change.
     - Before reporting the suite as blocked by missing dependencies, run `python -m pip show <package>` against the exact interpreter used for pytest so the missing package set is explicit.
     - Prefer running pytest through the interpreter (`python -m pytest`) rather than relying on script launchers or PATH entries for the Codex bundled runtime.

11. **Failure:** Full pytest runs on the Windows Codex desktop thread failed in `tmp_path` fixture setup with `PermissionError: [WinError 5] Access is denied` for pytest temp directories.
   - **Cause:** Pytest's default temp root under `AppData\Local\Temp` was inaccessible in the sandbox, and workspace-local `--basetemp` directories created by sandboxed runs also became unreadable to later commands.
   - **Fix:** Reran the suite outside the sandbox with explicit ignores for stale inaccessible temp directories and a fresh base temp: `python -m pytest -q --ignore=tests/test_rink_viz.py --ignore=tests/test_stats_helpers.py --ignore=pytest_tmp --ignore=.pytest-tmp --basetemp=pytest_tmp_escalated`, which completed with `342 passed`.
   - **Rules to avoid repeat failures of this type:**
     - If pytest fails before assertions with `PermissionError` under `pytest-of-*` or a workspace `pytest_tmp*` directory, treat it as a test-harness temp-dir issue, not a code failure.
     - Do not leave stale pytest temp directories in the collection tree if they are readable; remove them before rerunning. If they are unreadable, add explicit `--ignore=<dir>` flags so pytest does not try to collect them.
     - Prefer a fresh `--basetemp` value for each rerun after a temp-dir permission failure, and report any generated unreadable temp directories that could not be cleaned up.

## Derived-Data Versioning & Backfill

Each derived table stores a schema version in every row, recording which code version produced it:

| Table | Version constant | Column |
|-------|-----------------|--------|
| `shot_events` | `_XG_EVENT_SCHEMA_VERSION` (database.py) | `event_schema_version` |
| `game_context` | `_GAME_CONTEXT_SCHEMA_VERSION` (database.py) | `context_schema_version` |
| `player_game_features` | `_FEATURE_SET_VERSION` (database.py) | `feature_set_version` |

**How version-aware backfill works:**

1. `_get_game_processing_state()` uses `game_has_current_shot_events()`, which checks both row existence AND `event_schema_version = _XG_EVENT_SCHEMA_VERSION`.
2. If rows exist but at an older version, the game is flagged as needing reprocessing.
3. `_process_game()` deletes stale-version rows via `delete_game_shot_events()` before re-inserting with the current version.
4. Running `backfill_missing_game_data()` automatically detects and replaces all stale rows.

**When to bump a version constant:**

Any change to code that affects the **values** written to a derived table requires a version bump. Examples:
- Changing coordinate normalization, distance/angle calculation, or any feature extraction logic (`xg_features.py`)
- Adding, removing, or redefining a column in a derived table
- Changing how manpower state, score state, or faceoff context is classified
- Fixing a bug in data parsing that changes what gets stored

Changes that do **not** require a version bump:
- Refactoring that doesn't change output values (renaming internal variables, extracting helpers)
- Adding new derived tables (they have their own version constant)
- Changes to raw event ingestion (`create_table`/`insert_data`) — raw tables have no version column

## Statistical Analysis Rigor Requirements

All statistical analyses in this project — whether in notebooks, source code, or design docs — must meet the following minimum rigor framework. Visual inspection and point estimates alone are never sufficient to justify a feature inclusion decision or a data quality conclusion.

### Minimum acceptable framework

1. **Confidence intervals on all reported rates and proportions.** Never report a bare point estimate (e.g., "goal rate = 8.2%"). Always include a 95% bootstrap or Wilson CI. Use `bootstrap_goal_rate_ci()` from the validation framework notebook or equivalent.

2. **Formal hypothesis tests for group comparisons.** When comparing rates across categories (e.g., goal rate by shot type), use chi-squared or Fisher exact tests. Report the test statistic, degrees of freedom, and p-value. A visual difference in a bar chart is not evidence.

3. **Effect sizes to separate statistical from practical significance.** With 100k+ shots, tiny meaningless differences are statistically significant. Always compute an effect size measure (Cohen's h for proportions, Cohen's d for continuous). Apply the decision rule: a feature difference is *practically meaningful* only if |Cohen's h| >= 0.2 AND the comparison is adequately powered.

4. **Sample size adequacy checks.** For stratified analyses, report the number of observations per cell. At the project's ~8% base rate, cells with fewer than 400 shots are underpowered to detect a 50% relative difference at 80% power. Flag underpowered cells explicitly and do not draw conclusions from them.

5. **Train/test separation for any finding that informs model design.** Bin boundaries, thresholds, feature selection decisions, and decay-curve parameters must be validated on held-out data. Use the temporal cross-validation harness (season-block CV) from `model_validation_framework.ipynb`. Findings computed on the full dataset are exploratory only and must be labeled as such.

6. **Calibration analysis for any probability model.** Report reliability diagrams, Hosmer-Lemeshow statistic/p-value as a diagnostic, calibration slope/intercept (target: slope in [0.95, 1.05]), max decile calibration error (target: < 1 percentage point), and expected calibration error (target: < 0.5 percentage points). Calibration must be checked per-segment (even strength, power play, short-handed) separately, with max subgroup calibration error < 3 percentage points. Hosmer-Lemeshow is not a hard pass/fail gate on million-row holdout pools because it rejects practically acceptable calibration at very large sample sizes.

7. **Temporal stability assessment.** Any finding claimed to generalize must be checked across at least 3 held-out seasons. Report linear trend in the metric of interest. AUC drift exceeding 0.02/season signals concept drift and must be documented.

8. **Leakage audit for every feature.** Before including a feature in a model, document: (a) whether it is available at prediction time, (b) whether it encodes post-event information, (c) whether it proxies for a confounder. Features with HIGH confounder risk or AMBIGUOUS temporal availability must be investigated and resolved before model training.

### Reference implementation

The validation framework notebook (`notebooks/model_validation_framework.ipynb`) and its design doc (`docs/xg_model_components/06_model_validation_framework.md`) implement all eight requirements. New analyses should follow the same patterns: named constants for all thresholds, reusable helper functions (`bootstrap_goal_rate_ci`, `cohens_h`, `hosmer_lemeshow_test`, `calibration_slope_intercept`, `practical_calibration_metrics`, `run_temporal_cv`, `run_temporal_cv_with_prior_season_calibration`), and a summary scorecard with explicit pass/fail criteria.

## Pre-Submission Checklist

- **Unreachable code**: Check all control paths in every modified function for unreachable code. Verify that no statements follow unconditional `return`, `raise`, `break`, or `continue` within the same block, and that mutually exclusive conditions (e.g., `!= 200` then `== 200`) don't leave dead code after the final branch.
- **Interface simplicity**: Review all new or modified function signatures and module boundaries. Minimize the number of parameters, avoid unnecessary configuration options, and prefer simple interfaces over flexible ones. If a function can accomplish its job with fewer arguments or a narrower return type, simplify it before submitting.
- **Backfill impact check**: If any modified function changes the values written to a derived table (`shot_events`, `game_context`, `player_game_features`), bump the corresponding version constant in `database.py`. The version-aware backfill will automatically detect stale rows and reprocess them on the next run.

## Development Guardrails

- **Check conceptual PR scope before starting new work**: At the start of any new interaction, evaluate whether the requested work belongs in the same conceptual basket as the changes since the previous pull request. If it does not, stop before making code changes and ask the user how they want to handle the new chunk of work that would need to move through the PR process separately.
- **Knowledge base update is a PR precondition**: Before opening or updating any pull request, complete the `knowledge_base/` update workflow for the current change set. At minimum: update any affected wiki pages, bump `knowledge_base/index.md`'s last-updated line if content changed, and append a dated entry to `knowledge_base/log.md` summarizing the ingest/update. If no knowledge-base content changes are required, explicitly record that determination in the PR notes. Treat this as a tracked work item, not a final-memory check: add a plan/checklist item for "knowledge-base update or explicit no-change note" whenever touching `src/`, `notebooks/`, `docs/`, `artifacts/`, or project governance files.
- **Run the KB preflight before presenting a branch as complete**: Run `python scripts/check_knowledge_base_update.py --base-ref origin/main` before reporting a PR-ready branch. If the script fails, either update `knowledge_base/` and `knowledge_base/log.md`, or rerun with `--no-kb-needed "<reason>"` and carry that exact reason into PR notes. When changing the guardrail script itself, also run `python -m pytest tests/test_knowledge_base_governance.py -q`.
- **Encode remediations as rules**: Every time an error is encountered, diagnosed, and remediated with a new or updated pattern — regardless of whether it is a test failure, a tool-invocation error, a command-line flag mistake, a data quality issue, a schema drift, or a harness/environment misconfiguration — add a rule to `CLAUDE.md` before moving on. Use the "Test Failures Encountered, Fixes, and Prevention Rules" section (numbered-entry format with **Failure**, **Cause**, **Fix**, and **Rules to avoid repeat failures of this type** subsections) for test-suite and runtime failures; use "Development Guardrails" for coding conventions or process patterns that emerge from the fix. Each entry must capture the failure symptom, the root cause, the remediation (including the exact command, flag, or code change), and at least one prevention rule phrased so a future agent can recognize the pattern without re-deriving it. The goal is that the same class of failure never requires rediscovery — if you had to learn it, write it down.
- Keep SQL identifiers validated and quoted when dynamic.
- **Validate all external input used in SQL**: Never interpolate raw strings into SQL — not even for column names. Values must use parameterized queries (`?` placeholders). Identifiers (table/column names) that originate from external input (API responses, user arguments, dict keys) must pass through `_quote_identifier`, which rejects anything that isn't `^\w+$`. If a function accepts a dict and uses its keys as column names, those keys must be validated or drawn from a known-safe allowlist before being spliced into the query string.
- **No `#` comments in or adjacent to SQLite queries**: Do not place a `#` Python comment inside a SQL string literal (even inside triple-quoted SQL), on the line immediately preceding a SQL statement, or on the line immediately following a SQL statement. Security scanners flag `#`-adjacent-to-SQL as a suspicious pattern. Use `--` inside SQL for SQL-level comments, and place any Python `#` explanations at least one blank line away from the SQL call, or refactor the explanation into the surrounding function's docstring.
- Prefer normalized schema additions over duplicating raw event rows.
- Any new player feature should be derivable from `player_game_stats` and materialized into `player_game_features`.
- **No magic numbers or strings**: Never use bare numeric or string literals inline. Always define a descriptively named constant (e.g., `_GAME_API_MIN_INTERVAL = 2`, `NHL_FIRST_GAME_DATE = datetime.date(2007, 10, 3)`) and reference that constant in code and tests.
- **No duplicated logic across functions**: When two functions hit the same endpoint, parse the same structure, or build the same SQL, one must delegate to the other or both must call a shared helper. Never copy-paste a function body with minor variations.
- **Batch SQL operations**: Use `cursor.executemany` for multi-row inserts. Never build and execute the same parameterized query in a Python loop when the query text is identical across iterations. Hoist query construction outside loops.
- **Reuse HTTP connections**: Use `requests.Session` (module-level `_session`) for all HTTP calls to the same host. Never use bare `requests.get()` — it creates a new TCP+TLS connection per call. Mock tests should target `_session.get` via `@patch.object`, not `requests.get`.
- **Minimize round-trips in existence checks**: Prefer a single query with exception handling over multi-step check-then-act patterns (e.g., checking `sqlite_master` then querying the table). Use `SELECT 1 ... LIMIT 1` with `try/except OperationalError`.
- **Single-query catalog scans**: When reading metadata from `sqlite_master`, fetch all needed columns (`name, sql`, etc.) in one query. Never query the catalog in a loop (N+1 pattern).
- **Extract shared schema definitions**: If the same column list or DDL fragment appears in more than one SQL statement (e.g., `create_table` and a migration function), define it as a module-level constant and reference it everywhere.
- **Name parameters after what callers pass**: If every caller passes a game ID, name the parameter `game_id`, not `table_name`. Internal prefixing (e.g., `game_`) should happen inside the function via a helper like `_game_table_name(game_id)`.
- **Idempotent collection tracking**: `mark_date_collected` must only set `completed_at` when `games_collected >= games_found`. Incomplete dates (`completed_at IS NULL`) signal that the scraper should retry. `get_last_collected_date` must check for incomplete dates and return a resume point before the earliest incomplete date, ensuring no game data is permanently skipped.
- **Notebook path setup**: In Jupyter notebooks, never use `os.path.abspath("__file__")` — `"__file__"` is a string literal, not the `__file__` variable, and notebooks don't have `__file__` anyway. Instead, use CWD-based detection to find `src/`:
  ```python
  for _candidate in [os.path.join(os.getcwd(), "src"),
                     os.path.join(os.getcwd(), "..", "src")]:
      _candidate = os.path.abspath(_candidate)
      if os.path.isdir(_candidate) and _candidate not in sys.path:
          sys.path.insert(0, _candidate)
          break
  ```
  This handles both CWD=project root (VS Code default) and CWD=notebooks/.
