# Component 09: Shooter Handedness and Effective Goal Exposure Angle

## Motivation

The current `angle_to_goal` feature is purely geometric — it measures the angle from the shot location to the center of the net. It treats all shooters identically regardless of handedness, but a shooter's stick side fundamentally determines which goal posts are accessible from a given location on the ice.

**Core insight:** A right-handed shooter on the right wing (y > 0 in our normalized coordinates) has their forehand facing the net with full post-to-post access. The same shooter on the left wing (y < 0) must either shoot backhand or reach across their body, seeing a narrower effective goal window. The reverse applies for left-handed shooters.

This means `angle_to_goal` alone overstates shot quality for off-wing shots and understates it for natural-side shots, particularly for backhands and wrist shots at sharp angles.

---

## Current State

| Item | Status |
|------|--------|
| `players.shoots_catches` column | Exists in schema, **not populated** |
| Player metadata API endpoint | **Does not exist** in `nhl_api.py` |
| `shot_events.angle_to_goal` | Geometric only, no handedness adjustment |
| Off-wing classification | **Not implemented** |
| Effective angle calculation | **Not implemented** |

---

## Deliverables

### Phase B1: Off-wing flag (ship first, let data validate)

1. **Populate `players.shoots_catches`**
   - Add `get_player_metadata(player_id)` to `nhl_api.py` using the NHL player landing endpoint
   - Add `upsert_player(conn, player_dict)` to `database.py`
   - Backfill: scan `shot_events` for distinct `shooter_id` not in `players` and fetch metadata
   - No `shot_events` version bump (dimension table only)

2. **Add off-wing classification to `shot_events`**
   - New function `classify_off_wing(y_coord, shoots_catches)` in `xg_features.py`:
     - R-handed: natural side is y > 0 (right wing), off-wing is y < 0
     - L-handed: natural side is y < 0 (left wing), off-wing is y > 0
     - Returns 1 (off-wing), 0 (natural side), None if inputs missing
   - New columns in `shot_events`: `shoots_catches TEXT`, `is_off_wing INTEGER`
   - Version bump: `_XG_EVENT_SCHEMA_VERSION` v3 → v4
   - Migration: `_migrate_shot_events_v3_to_v4()`

3. **Feature interaction terms (at training time, not stored)**
   - `is_off_wing × shot_type` (10 terms): off-wing backhand vs natural-side backhand, etc.
   - `is_off_wing × angle_to_goal` (1 term): off-wing amplifies angle penalty
   - Ridge regression discovers the actual effect sizes from data

### Phase B2: Geometric effective goal exposure angle (after data validation)

**Precondition:** Phase D (model training) confirms that `is_off_wing` shows statistically significant interaction with shot type and angle in predicting goals.

1. **Post-to-post angle baseline**
   - NHL goal is 6 feet (72 inches) wide; posts at `(89, +3)` and `(89, -3)` in our coordinate system (feet)
   - `compute_post_to_post_angle(x, y)`: angle subtended by the full 6-foot goal from (x, y)
   - This alone is better than center-of-net angle for all shots

2. **Effective exposure angle by handedness and shot type**
   - `compute_effective_angle(x, y, shoots_catches, shot_type)`:
     - **Forehand-type shots** (wrist, snap, slap) from natural side: full post-to-post angle
     - **Forehand-type shots** from off-wing: reduced angle (near-post only — body blocks far post reach); roughly scale by `near_post_angle / full_angle` ratio
     - **Backhand shots** from natural side: reduced (backhand has limited far-post reach even on natural side)
     - **Backhand shots** from off-wing: counter-intuitively better than natural-side backhand (reaching across body toward far post)
     - **Deflections, tips, bat, cradle, poke**: full post-to-post angle (handedness irrelevant)
   - The scaling factors should be learned from data (Phase D coefficients) rather than hardcoded, but the geometric calculation provides the correct functional form

3. **Schema change:** Add `effective_angle REAL` to `shot_events`, bump version to v5

---

## Implementation Notes

### Coordinate system reminder
After `normalize_coordinates()`, the shooting team always attacks toward +x:
- Goal at `(GOAL_X_COORD=89, GOAL_Y_COORD=0)`
- y > 0 = right side of ice (facing goal)
- y < 0 = left side of ice (facing goal)

### Handedness convention
- R (right): holds stick on right side of body → forehand is on the right → natural forehand shooting from right wing (y > 0)
- L (left): holds stick on left side of body → forehand is on the left → natural forehand shooting from left wing (y < 0)

### Off-wing definition
A shooter is "off-wing" when their stick side does not match the side of the ice they're shooting from:
- R-handed at y < 0 → off-wing (forehand faces away from net on this side)
- L-handed at y > 0 → off-wing
- The effect is strongest at sharp angles (near the goal line) and diminishes with distance

### Edge cases
- `y_coord = 0` (center ice): neither off-wing nor natural — classify as 0 (natural) since the effect is symmetric
- Missing `shoots_catches`: return None for `is_off_wing` and use geometric angle only
- Behind the net (`x > 89`): off-wing classification still applies but effective angle is 0 regardless

---

## Validation

1. **Data sanity:** `SELECT shoots_catches, COUNT(*) FROM players WHERE shoots_catches IS NOT NULL GROUP BY shoots_catches` — expect roughly 50/50 L/R
2. **Off-wing effect:** Compare goal rates by `(is_off_wing, shot_type)` — expect:
   - Backhand goals: lower rate when off-wing=0 (natural side) vs off-wing=1 (counter-intuitive but physically correct — off-wing backhands reach the far post)
   - Wrist/snap goals: lower rate when off-wing=1 (reduced net exposure)
3. **Angle interaction:** Plot `AVG(is_goal)` vs `angle_to_goal` bins, faceted by `is_off_wing` — expect divergence at sharp angles (>45°), convergence at small angles (<20°)
4. **Model improvement:** After Phase D, compare model with and without `is_off_wing` features — expect improvement in log-loss and calibration, particularly for high-angle shots

---

## Extension Points

- **Goalie handedness interaction:** A left-catching goalie (standard) vs right-catching goalie creates asymmetric vulnerability to shooter handedness. Could be a Phase E feature.
- **One-timer detection:** If preceding event was a pass, the "effective" hand for the shot may differ from the player's natural handedness (catching a pass on the off-side forces a one-timer or quick release). Requires sequence context from Phase 4.
- **Shooting hand × distance curves:** Different shot types have different optimal ranges that may interact with handedness. Could emerge from the ridge regression interaction terms without explicit modeling.
