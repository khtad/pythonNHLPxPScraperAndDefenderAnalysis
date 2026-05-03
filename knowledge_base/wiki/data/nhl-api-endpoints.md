# NHL API Endpoints

> The NHL Web API and Stats REST endpoints used by this project: schedule, play-by-play, player landing, and shift charts; their response structure, rate limiting, and known field availability gaps by era.

## Overview

This project fetches game, schedule, and player metadata from the NHL Web API (`api-web.nhle.com/v1`) and shift-chart rows from the separate NHL Stats REST API (`api.nhle.com/stats/rest`). These public JSON APIs require no authentication but are rate-limited. Four endpoints are used: the weekly schedule endpoint to discover game IDs, the play-by-play endpoint to fetch detailed event data for each game, the player landing endpoint to resolve per-player metadata (handedness, position, team), and the shift charts endpoint to recover on-ice player intervals.

The API client is implemented in `src/nhl_api.py` using a module-level `requests.Session` for connection reuse, with a configurable minimum interval between game API calls to respect rate limits [1].

## Key Details

### Schedule Endpoint

| Property | Value |
|----------|-------|
| URL pattern | `https://api-web.nhle.com/v1/schedule/{YYYY-MM-DD}` |
| Method | GET |
| Response key | `gameWeek` — array of date entries, each containing a `games` array |
| Game ID field | `games[].id` — integer game identifier (e.g., `2025021044`) |
| Next page | `nextStartDate` — date string for pagination to the next week |
| Rate limiting | Not separately rate-limited in practice [1] |

The schedule endpoint returns a full week of games in a single call. The scraper iterates by week using `nextStartDate` for pagination, starting from `NHL_FIRST_GAME_DATE` (2007-10-03) [1][2].

**Game ID format:** The 10-digit game ID encodes season and game type: `SSSSTTNNNN` where `SSSS` is the season start year, `TT` is the game type (01=preseason, 02=regular, 03=playoffs), and `NNNN` is the game number within that type.

### Play-by-Play Endpoint

| Property | Value |
|----------|-------|
| URL pattern | `https://api-web.nhle.com/v1/gamecenter/{game_id}/play-by-play` |
| Method | GET |
| Response keys | `plays`, `homeTeam`, `awayTeam`, `id`, `gameDate`, `season`, `venue` |
| Rate limit | 2-second minimum interval between calls (`_GAME_API_MIN_INTERVAL`) [1] |

The play-by-play response contains the full event stream for a game. Key fields per play:

| Field | Path | Description |
|-------|------|-------------|
| Event type | `plays[].typeDescKey` | Event identifier (e.g., `shot-on-goal`, `goal`, `faceoff`) |
| Period | `plays[].periodDescriptor.number` | Period number (1-5+) |
| Time | `plays[].timeInPeriod` | Elapsed time in period ("MM:SS") |
| Coordinates | `plays[].details.xCoord`, `plays[].details.yCoord` | Shot location on rink surface |
| Defending side | `plays[].homeTeamDefendingSide` | Which end the home team defends (`"left"` or `"right"`) |
| Situation code | `plays[].situationCode` | 4-digit string encoding goalies and skater counts |
| Shooting team | `plays[].details.eventOwnerTeamId` | Team ID of the event owner |
| Shooter | `plays[].details.shootingPlayerId` or `scoringPlayerId` | Player who took the shot |
| Shot type | `plays[].details.shotType` | Shot technique (see [Shot Type Taxonomy](shot-type-taxonomy.md)) |
| Scores | `plays[].details.homeScore`, `awayScore` | Post-event scores (on goal events only) |

### Player Landing Endpoint

| Property | Value |
|----------|-------|
| URL pattern | `https://api-web.nhle.com/v1/player/{player_id}/landing` |
| Method | GET |
| Response keys | `playerId`, `firstName`, `lastName`, `shootsCatches`, `position`, `currentTeamId`, plus career-stats blocks not used by this project |
| Rate limit | Not separately rate-limited; only called for ids missing from the `players` dimension [1] |

Per-player fields consumed by the scraper:

| Field | Path | Description |
|-------|------|-------------|
| Player id | `playerId` | NHL identifier (e.g., `8478402` for Connor McDavid) |
| First name | `firstName.default` | Locale-keyed; project reads the `"default"` entry |
| Last name | `lastName.default` | Locale-keyed; project reads the `"default"` entry |
| Handedness | `shootsCatches` | `"L"` / `"R"` — shooting hand for skaters, catching hand for goalies |
| Position | `position` | Raw NHL code: `C`, `L`, `R`, `D`, `G` |
| Team id | `currentTeamId` | Current team, or null for unsigned/retired players |

These are parsed by `_parse_player_landing()` and written by `upsert_player()` / `upsert_players()` in `src/database.py`. The backfill entry point (`backfill_player_metadata`) fetches only ids that appear as `shooter_id` or `goalie_id` in `shot_events` but are missing from the `players` table, so one run reaches every participating player without re-fetching known rows [5].

### Shift Charts Endpoint

| Property | Value |
|----------|-------|
| URL pattern | `https://api.nhle.com/stats/rest/en/shiftcharts?cayenneExp=gameId={game_id}` |
| Method | GET |
| Response key | `data` — array of player shift rows |
| Consumed fields | `playerId`, `teamId`, `period`, `startTime`, `endTime`, optional `duration`, optional position fields |
| Rate limit | Uses the shared `_api_get()` session path; no separate rate limiter is implemented [6] |

The shift charts response is normalized by `parse_shift_rows()` into `ShiftRecord` values, then `src/shift_population.py` persists rows into `shifts`, builds `on_ice_intervals`, and updates shot-event on-ice slot columns. Team side is inferred by comparing shift `teamId` with the `games.home_team_id` / `games.away_team_id` row; position is read from the shift payload when present and falls back to the `players.position` dimension when needed [6].

### Field Availability by Era

Not all fields are available for all seasons. This is the most significant data quality issue for historical analysis [3].

| Field | Available | Missing | Impact |
|-------|-----------|---------|--------|
| `homeTeamDefendingSide` | 2019-2020 onward | Pre-2020 (returns `None`) | Coordinate normalization falls back to sign-based heuristic. See [Coordinate System and Normalization](coordinate-system-and-normalization.md). |
| `xCoord` / `yCoord` | All seasons | Occasionally missing on individual events | Rows stored with NULL coordinates; excluded from location-based features |
| `situationCode` | All seasons | Occasionally missing | Manpower state stored as NULL |
| `shotType` | All seasons | Rarely missing | Required field; events without it are still recorded |

### Community Documentation

The NHL does not publish official API documentation. Two community-maintained references provide the most complete endpoint catalogs [4]:

- **Zmalski/NHL-API-Reference** (GitHub) — comprehensive catalog for the current `api-web.nhle.com` Web API and `api.nhle.com/stats/rest` Stats REST API
- **dword4/nhlapi** (GitHub/GitLab) — the original community documentation, covering both the legacy `statsapi.web.nhl.com` and the current API

A legacy API base URL (`https://statsapi.web.nhl.com/api/v1/`) was used by many older tools. It has been deprecated in favor of `api-web.nhle.com`. The Stats API (`https://api.nhle.com/stats/rest`) provides aggregate statistics and is a separate platform from the play-by-play Web API.

### Rate Limiting and Error Handling

- The client enforces a 2-second minimum interval between play-by-play requests via `_rate_limited_game_api_get()` [1].
- Non-200 responses return `None`, and the caller skips the game.
- Transport-layer failures (`requests.RequestException`, e.g., transient proxy/connectivity errors) are caught in `_api_get_with_status()` and treated as retryable misses instead of hard crashes [1].
- The `requests.Session` is configured with a `User-Agent` header (`"Mozilla/5.0"`) [1].
- Connection reuse via the session avoids TCP+TLS overhead per request, per the `CLAUDE.md` guardrail requiring `requests.Session` over bare `requests.get()`.

## Relevance to This Project

These four endpoints are the sole data source for the entire project. The scraper in `main.py` iterates through every week from 2007-10-03 to the present, fetching game IDs via the Web API schedule endpoint and full event data via the Web API play-by-play endpoint [2]. The Web API player landing endpoint is called after each scraper/backfill pass for every shooter/goalie not yet resolved. The Stats REST shift charts endpoint powers `shifts`, `on_ice_intervals`, and the `shot_events.home_on_ice_*` / `away_on_ice_*` slot columns [6]. All derived tables (`shot_events`, `games`, `game_context`, `players`, `player_game_stats`, `shifts`, `on_ice_intervals`) are populated from these endpoints [5][6].

The `homeTeamDefendingSide` era gap is the project's most significant data quality issue, affecting ~1.3M shots (see [Coordinate System and Normalization](coordinate-system-and-normalization.md) for full details).

Last verified: 2026-05-02

## Sources

[1] API client implementation — `src/nhl_api.py` (`_NHL_API_BASE_URL`, `_GAME_API_MIN_INTERVAL`, `get_weekly_schedule()`, `get_full_play_by_play()`, `_rate_limited_game_api_get()`, `get_player_metadata()`, `_parse_player_landing()`)
[2] Scraper entry point — `src/main.py` (`main()`, `NHL_FIRST_GAME_DATE`, `refresh_player_tables()`)
[3] Shot distance diagnostic — `knowledge_base/raw/project/2026-04-06_shot-distance-diagnostic.md`
[4] Community API documentation — `knowledge_base/raw/external/2026-04-08_nhl-api-community-documentation.md`
[5] Player metadata pipeline — `src/database.py` (`upsert_player()`, `upsert_players()`, `get_missing_player_ids()`, `backfill_player_metadata()`, `populate_player_game_stats()`)
[6] Shift population pipeline — `src/shifts.py` (`fetch_shift_rows_for_game()`, `parse_shift_rows()`), `src/shift_population.py` (`populate_shift_data_for_game()`, `backfill_shift_data()`)

## Related Pages

- [NHL API Shot Events](nhl-api-shot-events.md) — how play-by-play data is extracted into the shot_events table
- [Coordinate System and Normalization](coordinate-system-and-normalization.md) — how coordinates from the API are normalized, including the era gap
- [Arena and Venue Reference](arena-venue-reference.md) — static team/arena data used alongside API venue metadata

## Revision History

- 2026-05-02 — Corrected shift charts URL from the Web API gamecenter path to the Stats REST `shiftcharts?cayenneExp=gameId=...` endpoint.
- 2026-05-01 — Added shift charts endpoint and shift-table population pipeline references.
- 2026-04-24 — Added transport-exception handling note for `_api_get_with_status()` and refreshed verification date.
- 2026-04-20 — Added player landing endpoint section (roadmap Phase 2.5.1: player metadata pipeline).
- 2026-04-08 — Added community documentation references (Zmalski, dword4) and legacy API note.
- 2026-04-06 — Created. Compiled from nhl_api.py, main.py, and API response inspection.
