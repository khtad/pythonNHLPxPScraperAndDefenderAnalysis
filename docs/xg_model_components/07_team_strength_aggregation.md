# Component 07: Team Strength via Aggregated Player RAPM

## Scope
Convert player RAPM estimates into team-level strength ratings.

## Deliverables
- Aggregation logic using projected active rosters and deployment weights.
- Team offense and defense estimates from skater RAPM.
- Separate goalie-strength module from save-above-expected residuals.
- Combined team strength vector with trend outputs.

## Validation
- Predictive lift vs team-only baselines.
- Stability/responsiveness tradeoff checks.
- Uncertainty propagation from player to team layers.

## Extension points
- Line-level synergy adjustments.
- Injury and transaction scenario simulation.
