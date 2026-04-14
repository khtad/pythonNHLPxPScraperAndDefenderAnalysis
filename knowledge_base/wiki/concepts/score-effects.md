# Score Effects

> How the current score differential changes team shooting behavior — trailing teams take more but lower-quality shots, leading teams take fewer but higher-quality shots.

<!-- data-version: v2 (coordinate-independent — score effects are measured by shot counts and goal rates, not coordinates) -->
<!-- data-revalidate: No changes needed after v3 backfill. If distance-stratified score effects are added, re-derive from clean data. -->

## Overview

Score effects are one of the most important confounders in hockey analytics. When a team trails, it shifts to a more aggressive offensive posture — forechecking harder, taking riskier shots, and pulling the goalie late in games. When leading, a team plays more conservatively — trapping, blocking shots, and only shooting from high-percentage situations. This behavioral shift means that raw shot metrics (Corsi, Fenwick) systematically overstate trailing-team quality and understate leading-team quality.

For xG modeling, score effects matter because they change the relationship between shot location and goal probability. A shot from the high slot at 5v5 when tied has a different context than the same shot when trailing by 3 goals with 2 minutes left.

## Key Details

### Empirical Patterns

From the project database (all teams, 2007-2026) [1]:

| Score State | Shot Count | Goal Rate | Relative to Tied |
|-------------|----------:|----------:|:-----------------|
| `tied` | 771,724 | 7.04% | baseline |
| `up1` | 347,259 | 7.84% | +11% rate, -55% volume |
| `down1` | 400,664 | 6.58% | -7% rate, -48% volume |
| `up2` | 154,785 | 9.17% | +30% rate |
| `down2` | 191,926 | 6.65% | -6% rate |
| `up3plus` | 103,853 | 8.16% | +16% rate |
| `down3plus` | 129,609 | 6.34% | -10% rate |

The volume asymmetry (more shots when trailing) and quality asymmetry (higher goal rate when leading) are both visible at every differential level [1].

### Mechanisms

1. **Shot selection bias:** Leading teams wait for better opportunities. Trailing teams shoot from worse positions under time pressure.
2. **Defensive posture:** Leading teams commit more players to defense, reducing shot quality against them but also reducing their own shot attempts.
3. **Extra attacker:** In the final minutes when trailing, teams pull their goalie, creating 6v5 situations that inflate both shot volume and goal rate for the trailing team (and empty-net goals for the leader).
4. **Referee effects:** Some evidence suggests penalties are called differently based on score, creating asymmetric power-play opportunities.

### Implications for xG Models

An xG model that ignores score state will:
- **Overestimate** the danger of shots taken when trailing (those shots convert at a lower rate than their location would suggest)
- **Underestimate** the danger of shots taken when leading (those shots convert at a higher rate)

Score state should be included as a feature or interaction term. The `CLAUDE.md` statistical rigor framework requires per-segment calibration checking, including by score state.

## Relevance to This Project

Score state is stored in `shot_events.score_state` (see [Score States](../data/score-states.md)) and is a first-tier xG feature [2]. The classification uses 7 buckets rather than continuous differential, collapsing 3+ goal leads/deficits because behavioral differences plateau beyond that point.

Score effects also affect player evaluation (RAPM): a player who logs most of their ice time while trailing will have inflated shot generation numbers that don't reflect their actual impact. The RAPM model must account for this by including score state in the design matrix [3].

Last verified: 2026-04-06

## Sources

[1] Frequency data — `data/nhl_data.db` shot_events table, see [Score States](../data/score-states.md) for full breakdown
[2] Feature design — `docs/xg_model_components/01_shot_and_state_features.md`
[3] RAPM design — `docs/xg_model_components/06_rapm_on_xg.md`

## Related Pages

- [Score States](../data/score-states.md) — the 7-bucket classification used in the database
- [Expected Goals (xG)](expected-goals-xg.md) — the model that uses score state as a feature
- [Manpower States](../data/manpower-states.md) — another game-state feature that interacts with score effects

## Revision History

- 2026-04-06 — Created. Compiled from score state frequency data and component design docs.
