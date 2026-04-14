# Arena and Venue Reference

> Static reference data for all 32 current NHL teams plus historical relocations: arena city, timezone UTC offset, and geographic coordinates for travel/rest feature computation.

## Overview

The project maintains a static lookup table mapping NHL team IDs to their arena locations, used primarily for computing travel distance and timezone crossing features in the rest/travel analysis (Phase 2, Component 02). The data covers all 32 current NHL teams plus significant historical relocations (Atlanta Thrashers, original Phoenix Coyotes location) to support analysis of games from 2007 onward.

The reference data is defined in `src/arena_reference.py` as the `ARENA_DATA` dictionary, keyed by integer team ID [1]. Travel distances between arenas are computed using the haversine formula in `xg_features.py` [2].

## Key Details

### Data Fields

| Field | Type | Description |
|-------|------|-------------|
| `city` | string | Arena city name |
| `timezone_utc_offset` | integer | UTC offset in standard time (not DST) |
| `lat` | float | Arena latitude (decimal degrees) |
| `lon` | float | Arena longitude (decimal degrees) |

### Team Coverage

**32 current teams** across 4 divisions, plus 2 historical entries [1]:

| Division | Teams (ID: City) |
|----------|-----------------|
| Atlantic | NJD (1): Newark, NYI (2): Elmont, NYR (3): New York, PHI (4): Philadelphia, PIT (5): Pittsburgh, BOS (6): Boston, BUF (7): Buffalo, MTL (8): Montreal, OTT (9): Ottawa, TOR (10): Toronto |
| Metropolitan | CAR (12): Raleigh, FLA (13): Sunrise, TBL (14): Tampa, WSH (15): Washington, CHI (16): Chicago, DET (17): Detroit |
| Central | NSH (18): Nashville, STL (19): St. Louis, CGY (20): Calgary, COL (21): Denver, EDM (22): Edmonton, VAN (23): Vancouver, DAL (25): Dallas, WPG (52): Winnipeg |
| Pacific | ANA (24): Anaheim, LAK (26): Los Angeles, SJS (28): San Jose, CBJ (29): Columbus, MIN (30): Minneapolis, VGK (54): Las Vegas, SEA (55): Seattle, UTA (59): Salt Lake City |
| Historical | ATL (11): Atlanta (Thrashers, 1999-2011), PHX (27): Glendale (Coyotes original) |

Note: Arizona Coyotes (53): Tempe is listed as a historical entry covering the 2014-2024 period before the franchise relocated to Utah (59) [1].

### Timezone Distribution

| UTC Offset | Count | Teams |
|-----------:|------:|-------|
| -5 (Eastern) | 16 | NJD, NYI, NYR, PHI, PIT, BOS, BUF, MTL, OTT, TOR, CAR, FLA, TBL, WSH, DET, CBJ |
| -6 (Central) | 6 | CHI, NSH, STL, DAL, MIN, WPG |
| -7 (Mountain) | 4 | CGY, COL, EDM, UTA |
| -8 (Pacific) | 6 | VAN, ANA, LAK, SJS, VGK, SEA |

The maximum timezone crossing for a single trip is 3 hours (Eastern to Pacific), which the `compute_timezone_delta()` function reports as the absolute difference between away and home UTC offsets [2].

### Travel Distance Computation

The `haversine_distance()` function in `xg_features.py` computes great-circle distance in kilometers between two lat/lon points [2]:

```
a = sin(dlat/2)^2 + cos(lat1) * cos(lat2) * sin(dlon/2)^2
distance = 2 * R * arcsin(sqrt(a))
```

where R = 6371 km (Earth radius). This is used to compute inter-game travel burden as a feature for the rest/travel model [2].

### Known Limitations

- **DST not modeled:** UTC offsets use standard time only. During summer months (preseason), actual local times differ by 1 hour for non-Arizona teams. The model does not need sub-hour precision, so this is acceptable [1].
- **Arena relocations within a city** (e.g., NYI from Brooklyn to Elmont in 2021) are not tracked. The geographic difference is negligible for travel distance computation.
- **Team ID 53 vs 59:** The Arizona-to-Utah relocation means games from different seasons may reference different team IDs for what is effectively the same franchise.

## Relevance to This Project

Arena data feeds the rest/travel feature pipeline (Phase 2, Component 02). Travel distance and timezone delta are hypothesized to affect player fatigue and performance, particularly in back-to-back situations. The `rest_travel_analysis.ipynb` notebook validates these effects.

The venue metadata (name, city, UTC offset) is also stored per-game in the `games` table via `extract_game_metadata()`, providing a per-game record that accounts for neutral-site games or temporary relocations [3].

Last verified: 2026-04-06

## Sources

[1] Arena reference data — `src/arena_reference.py` (`ARENA_DATA`, `get_arena_info()`)
[2] Travel computation — `src/xg_features.py` (`haversine_distance()`, `compute_timezone_delta()`, `_EARTH_RADIUS_KM`)
[3] Game metadata extraction — `src/xg_features.py` (`extract_game_metadata()`)

## Related Pages

- [NHL API Endpoints](nhl-api-endpoints.md) — how game and venue data is fetched from the API
- [NHL API Shot Events](nhl-api-shot-events.md) — shot events that use team IDs from this reference
- [Rest and Travel Effects](../concepts/rest-travel-effects.md) — how travel distance and timezone crossings affect performance

## Revision History

- 2026-04-06 — Created. Compiled from arena_reference.py and xg_features.py travel computation functions.
