# NHL API Community Documentation

> **Source:** https://github.com/Zmalski/NHL-API-Reference , https://github.com/dword4/nhlapi
> **Authors:** Community contributors (Zmalski, dword4/Drew Hynes, others)
> **Retrieved:** 2026-04-08
> **Type:** Unofficial API documentation

## Base URLs

Two primary NHL API platforms:

1. **Web API (current):** `https://api-web.nhle.com/`
2. **Stats API:** `https://api.nhle.com/stats/rest`

The Web API is the newer platform; the Stats API predates it.

### Legacy API (deprecated)

- **Old Stats API:** `https://statsapi.web.nhl.com/api/v1/`
- Used by many older tools and scripts
- Deprecated in favor of the api-web.nhle.com endpoints

## Key Endpoints

### Play-by-Play (Web API)

- **Endpoint:** `GET /v1/gamecenter/{gameId}/play-by-play`
- Returns shot events and complete game action sequences
- Contains on-ice coordinates for shot/goal events

### Game Landing / Summary

- **Endpoint:** `GET /v1/gamecenter/{gameId}/landing`
- Comprehensive game information and statistics

### Boxscore

- **Endpoint:** `GET /v1/gamecenter/{gameId}/boxscore`
- Player performance metrics and game summaries

### Schedule

- **Current:** `GET /v1/schedule/now`
- **By date:** `GET /v1/schedule/{date}` (YYYY-MM-DD format)
- **Team season:** `GET /v1/club-schedule/{team}/{season}/{gameType}`

## Query Parameters

- `categories` (string, optional) — filter statistics types
- `limit` (integer, optional) — `-1` returns all results

## Response Format

All endpoints return JSON.

## Rate Limiting

No official rate limiting documentation exists. Community experience suggests:
- No hard published rate limits
- Aggressive polling may result in temporary blocks
- Best practice: moderate request frequency, use session reuse

## Field Availability Notes

- The `homeTeamDefendingSide` field was added post-2020; absent for earlier seasons
- Shot coordinates available in play-by-play for SHOT and GOAL events
- Period, time remaining, strength state, and event participants included
- Older API versions had different field structures

## Community Resources

- **Zmalski/NHL-API-Reference** — comprehensive endpoint catalog for the new API
- **dword4/nhlapi** — original community documentation (covers legacy + new APIs)
- **nhl-api-py** (PyPI) — Python wrapper library
