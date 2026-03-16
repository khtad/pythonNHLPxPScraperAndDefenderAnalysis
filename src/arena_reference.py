"""Static arena reference data for NHL teams.

Maps team_id to arena city, timezone UTC offset, latitude, and longitude.
Covers all 32 current teams plus significant historical relocations.
Source: public arena location data.
"""

# UTC offsets use standard time (not DST). The model should not need
# sub-hour precision; these are integer hour offsets.
#
# Format: team_id -> {city, timezone_utc_offset, lat, lon}

ARENA_DATA = {
    # ── Atlantic Division ────────────────────────────────────────────
    1:  {"city": "Newark",        "timezone_utc_offset": -5, "lat": 40.7334, "lon": -74.1713},   # NJD
    2:  {"city": "Elmont",        "timezone_utc_offset": -5, "lat": 40.7178, "lon": -73.7255},   # NYI
    3:  {"city": "New York",      "timezone_utc_offset": -5, "lat": 40.7505, "lon": -73.9934},   # NYR
    4:  {"city": "Philadelphia",  "timezone_utc_offset": -5, "lat": 39.9012, "lon": -75.1720},   # PHI
    5:  {"city": "Pittsburgh",    "timezone_utc_offset": -5, "lat": 40.4393, "lon": -79.9891},   # PIT
    6:  {"city": "Boston",        "timezone_utc_offset": -5, "lat": 42.3662, "lon": -71.0621},   # BOS
    7:  {"city": "Buffalo",       "timezone_utc_offset": -5, "lat": 42.8750, "lon": -78.8764},   # BUF
    8:  {"city": "Montreal",      "timezone_utc_offset": -5, "lat": 45.4961, "lon": -73.5693},   # MTL
    9:  {"city": "Ottawa",        "timezone_utc_offset": -5, "lat": 45.2969, "lon": -75.9272},   # OTT
    10: {"city": "Toronto",       "timezone_utc_offset": -5, "lat": 43.6435, "lon": -79.3791},   # TOR
    # ── Metropolitan Division ────────────────────────────────────────
    12: {"city": "Raleigh",       "timezone_utc_offset": -5, "lat": 35.8033, "lon": -78.7220},   # CAR
    13: {"city": "Sunrise",       "timezone_utc_offset": -5, "lat": 26.1584, "lon": -80.3256},   # FLA
    14: {"city": "Tampa",         "timezone_utc_offset": -5, "lat": 27.9427, "lon": -82.4519},   # TBL
    15: {"city": "Washington",    "timezone_utc_offset": -5, "lat": 38.8981, "lon": -77.0209},   # WSH
    16: {"city": "Chicago",       "timezone_utc_offset": -6, "lat": 41.8807, "lon": -87.6742},   # CHI
    17: {"city": "Detroit",       "timezone_utc_offset": -5, "lat": 42.3411, "lon": -83.0555},   # DET
    # ── Central Division ─────────────────────────────────────────────
    18: {"city": "Nashville",     "timezone_utc_offset": -6, "lat": 36.1592, "lon": -86.7785},   # NSH
    19: {"city": "St. Louis",     "timezone_utc_offset": -6, "lat": 38.6268, "lon": -90.2027},   # STL
    20: {"city": "Calgary",       "timezone_utc_offset": -7, "lat": 51.0375, "lon": -114.0519},  # CGY
    21: {"city": "Denver",        "timezone_utc_offset": -7, "lat": 39.7487, "lon": -105.0077},  # COL
    22: {"city": "Edmonton",      "timezone_utc_offset": -7, "lat": 53.5469, "lon": -113.4981},  # EDM
    23: {"city": "Vancouver",     "timezone_utc_offset": -8, "lat": 49.2778, "lon": -123.1089},  # VAN
    24: {"city": "Anaheim",       "timezone_utc_offset": -8, "lat": 33.8078, "lon": -117.8765},  # ANA
    25: {"city": "Dallas",        "timezone_utc_offset": -6, "lat": 32.7905, "lon": -96.8103},   # DAL
    26: {"city": "Los Angeles",   "timezone_utc_offset": -8, "lat": 34.0430, "lon": -118.2673},  # LAK
    # ── Pacific Division ─────────────────────────────────────────────
    28: {"city": "San Jose",      "timezone_utc_offset": -8, "lat": 37.3326, "lon": -121.9011},  # SJS
    29: {"city": "Columbus",      "timezone_utc_offset": -5, "lat": 39.9692, "lon": -83.0061},   # CBJ
    30: {"city": "Minneapolis",   "timezone_utc_offset": -6, "lat": 44.9795, "lon": -93.2760},   # MIN
    52: {"city": "Winnipeg",      "timezone_utc_offset": -6, "lat": 49.8929, "lon": -97.1435},   # WPG
    53: {"city": "Tempe",         "timezone_utc_offset": -7, "lat": 33.4255, "lon": -111.9400},   # ARI (2014-2024)
    54: {"city": "Las Vegas",     "timezone_utc_offset": -8, "lat": 36.1029, "lon": -115.1785},   # VGK
    55: {"city": "Seattle",       "timezone_utc_offset": -8, "lat": 47.6221, "lon": -122.3540},   # SEA
    59: {"city": "Salt Lake City","timezone_utc_offset": -7, "lat": 40.7683, "lon": -111.9011},   # UTA

    # ── Historical relocations ───────────────────────────────────────
    # Atlanta Thrashers (1999-2011, became WPG)
    11: {"city": "Atlanta",       "timezone_utc_offset": -5, "lat": 33.7573, "lon": -84.3963},   # ATL
    # Hartford Whalers (pre-1997, became CAR) — included for completeness
    27: {"city": "Glendale",      "timezone_utc_offset": -7, "lat": 33.5317, "lon": -112.2611},   # PHX/ARI (original)
}


def get_arena_info(team_id):
    """Return arena info dict for a team_id, or None if not found."""
    return ARENA_DATA.get(team_id)
