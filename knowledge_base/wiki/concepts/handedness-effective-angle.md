# Handedness and Effective Angle

> How a shooter's stick hand determines which goal posts are accessible from a given ice position, making the geometric angle to goal an incomplete measure of shot quality.

<!-- data-version: v2 -->
<!-- data-revalidate: After v3 backfill, the y_coord sign used for off-wing classification depends on correct coordinate normalization. Re-verify off-wing classification logic against v3 data. Phase 2.5.1 populated players.shoots_catches; the is_off_wing column and the geometric effective-angle calculation remain unimplemented. -->

## Overview

The current `angle_to_goal` feature measures the geometric angle from the shot location to the center of the net. It treats all shooters identically, but a shooter's handedness fundamentally determines which parts of the goal are accessible from a given position. A right-handed shooter on the right wing (y > 0 in normalized coordinates) has their forehand facing the net with full post-to-post access. The same shooter on the left wing must either shoot backhand or reach across their body, seeing a narrower effective goal window.

This means `angle_to_goal` alone overstates shot quality for off-wing shots and understates it for natural-side shots, particularly for backhands and wrist shots at sharp angles.

## Key Details

### Handedness Convention

In normalized coordinates (shooting team attacks toward +x) [1]:

| Hand | Forehand Side | Natural Wing (y sign) | Off-Wing (y sign) |
|------|:------------:|:--------------------:|:-----------------:|
| Right (R) | Right side | y > 0 | y < 0 |
| Left (L) | Left side | y < 0 | y > 0 |

### Off-Wing Classification

A shooter is "off-wing" when their stick side does not match the side of the ice they're shooting from [1]:

- R-handed at y < 0: off-wing (forehand faces away from net)
- L-handed at y > 0: off-wing
- y = 0 (center): classified as natural side (effect is symmetric)

The effect is strongest at sharp angles near the goal line and diminishes with distance (from far out, the angle difference between forehand and backhand reach is negligible).

### Planned Effective Angle Feature

The component design describes a two-phase approach [1]:

**Phase B1 — Off-wing flag:**
- Populate `players.shoots_catches` from the NHL player metadata API
- Add `is_off_wing` column to `shot_events`
- Create interaction features: `is_off_wing x shot_type` and `is_off_wing x angle_to_goal`

**Phase B2 — Geometric effective angle:**
- Compute post-to-post angle: the angle subtended by the full 6-foot goal (posts at (89, +3) and (89, -3)) from the shot location
- Adjust by handedness and shot type:
  - Forehand from natural side: full post-to-post angle
  - Forehand from off-wing: reduced (near-post only)
  - Backhand from natural side: reduced (limited far-post reach)
  - Backhand from off-wing: somewhat better than natural-side backhand (reaching across body)
  - Deflections, tips, bat, cradle, poke: full angle (handedness irrelevant)

### Current Implementation Status

| Item | Status |
|------|--------|
| `players.shoots_catches` column | **Populated** via `backfill_player_metadata` (roadmap Phase 2.5.1) [2] |
| Player metadata API endpoint | **Implemented** as `get_player_metadata()` (`/v1/player/{id}/landing`) [3] |
| `is_off_wing` classification | **Not implemented** |
| Effective angle calculation | **Not implemented** |

The dimension table is now in place; the off-wing flag and effective-angle calculation remain Phase B features, gated on Phase D (model training) confirming a significant interaction with shot type and angle [1].

### Coordinate Normalization Dependency

Off-wing classification depends on the sign of y_coord in normalized coordinates. If normalization is wrong (as in the v2 bug for pre-2020 data), off-wing classification will also be wrong. This feature should only be implemented after the v3 backfill is complete.

## Relevance to This Project

Handedness features are designed in `docs/xg_model_components/09_handedness_and_effective_angle.md` [1]. The data prerequisites — a player metadata API endpoint and a populated `players` dimension table — landed in roadmap Phase 2.5.1 [2][3]. Remaining work: adding the `is_off_wing` column to `shot_events` (version bump) and the geometric effective-angle calculation.

The expected impact is strongest for high-angle shots (>45 degrees) where the forehand/backhand distinction matters most. At small angles (<20 degrees from center), all shooters see roughly the same net exposure regardless of handedness.

Last verified: 2026-04-06

## Sources

[1] Component design — `docs/xg_model_components/09_handedness_and_effective_angle.md`
[2] Player metadata pipeline — `src/database.py` (`upsert_player`, `upsert_players`, `backfill_player_metadata`, `populate_player_game_stats`)
[3] NHL API client — `src/nhl_api.py` (`get_player_metadata`, `_parse_player_landing`)

## Related Pages

- [Coordinate System and Normalization](../data/coordinate-system-and-normalization.md) — the y_coord sign that determines off-wing classification
- [Shot Type Taxonomy](../data/shot-type-taxonomy.md) — shot types that interact with handedness (backhand especially)
- [Expected Goals (xG)](expected-goals-xg.md) — the model that will use handedness features

## Revision History

- 2026-04-20 — Updated implementation status: `players.shoots_catches` now populated and the player-landing endpoint is implemented (roadmap Phase 2.5.1). The `is_off_wing` column and effective-angle calculation remain unimplemented.
- 2026-04-06 — Created. Compiled from component 09 design doc. All features are planned, not yet implemented.
