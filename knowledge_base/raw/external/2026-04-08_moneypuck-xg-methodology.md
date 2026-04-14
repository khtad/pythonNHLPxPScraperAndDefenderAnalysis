# MoneyPuck Expected Goals Methodology

> **Source:** https://moneypuck.com/about.htm
> **Author:** Peter Tanner
> **Retrieved:** 2026-04-08
> **Type:** Public xG model documentation

## Algorithm

Gradient boosting (GBM). Chosen over logistic regression based on superior performance with prior-event variables.

## Training Data

- 800,000+ shots, 50,000+ goals
- NHL regular season and playoff games, 2007-2015
- Location data included

## Features (15 variables)

1. Shot distance (from coordinates)
2. Shot angle (from coordinates)
3. Shot type (slap, wrist, backhand, etc.)
4. Time since last event
5. Speed from previous event (distance / elapsed time)
6. Ice location coordinates (x, y)
7. Rebound angle change (angle difference between consecutive shots / time)
8. Preceding event type
9. Opponent skater count
10. Man-advantage situation
11. Powerplay duration
12. Empty net status

(Some features are derived combinations; Tanner counts 15 conceptual features.)

## Key Design Decisions

### Rebound/Rush Handling
No explicit rebound or rush classifier variables. Instead uses "speed" metrics — distance between events divided by elapsed time. For rebounds, measures angle change between consecutive shots over time.

### Flurry Adjustment
Multiple shots in quick succession are discounted: each shot's xG is multiplied by the probability of not scoring on all previous shots in the sequence. This ensures a flurry of shots never exceeds 1.0 combined xG.

### Shooting Talent Adjustment
Bayesian statistics used to estimate individual player shooting skill, producing "shooting talent adjusted" expected goals.

### Created Expected Goals
A derivative metric crediting shot-takers whose attempts generate high-probability rebounds.

## Validation

Top 15% of shots by predicted probability accounted for >50% of actual goals in the 2015-16 out-of-sample season.

## Data Availability

MoneyPuck publishes shot-level data with xG values for public download at moneypuck.com/data.htm.
