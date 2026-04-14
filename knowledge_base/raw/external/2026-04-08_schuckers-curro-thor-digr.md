# Schuckers & Curro: THoR and DIGR

> **Source:** Schuckers & Curro, "Total Hockey Rating (THoR)", MIT Sloan Sports Analytics Conference, 2013. Also: Schuckers, "DIGR: A Defense Independent Rating of NHL Goaltenders", MIT Sloan, 2011.
> **Authors:** Michael E. Schuckers (St. Lawrence University / Statistical Sports Consulting), James Curro (Iowa State University)
> **Retrieved:** 2026-04-08
> **Type:** Academic papers — player rating and goaltender evaluation

## THoR (Total Hockey Rating)

### Core Concept

A comprehensive two-way player rating based on every on-ice event recorded by the NHL's RTSS system. Each event is valued by the probability it leads to a goal in the subsequent 20 seconds (NP20 — Net Probability after 20 seconds).

### Model

```
NP20_i = mu + sum(beta_j * x_ij_home) + sum(beta_j * x_ij_away) + gamma * ZS_i + epsilon_i
```

Where:
- `mu` = home-ice advantage effect
- `beta_j` = player j's per-event impact coefficient
- `x_ij` = +1 if player j is on ice for event i (home side), -1 (away side), 0 otherwise
- `gamma` = zone start effect coefficient
- `ZS` = +1 (offensive zone start), 0 (neutral), -1 (defensive)

Fit using **ridge regression** (L2 regularization). Ridge parameter chosen to minimize a novel metric (rho) measuring variability in ratings for traded players relative to overall variability.

### Event Valuation (NP20)

For each event type and ice location, calculated the probability of a goal for each team in the following 20 seconds. Twenty seconds chosen empirically — changes after 20 seconds were not significant.

**Special handling:**
- **Shots and goals** treated identically as "shots" (shooting percentage regresses to mean). Shot value = NP20 + P(goal | shot location, shot type).
- **Shot location probability:** Offensive zone divided into 54 grid cells based on adjusted x,y coordinates. Goal probability calculated per grid cell and per shot type (7 types: wrist, slap, snap, backhand, tip-in, deflection, wraparound).
- **Penalties:** Length in minutes * league-average PP success rate per minute.
- **Turnovers:** Giveaways and takeaways combined into a single "turnover" event to negate known home-rink recording bias.

### Event Types Used

Faceoff (FAC), Hit (HIT), Turnover (TURN = GIVE + TAKE), Blocked Shot (BLOCK), Missed Shot (MISS), Shot on Goal (SHOT), Goal (GOAL), Penalty (PENL).

### Rink Bias Correction

Shot location coordinates adjusted per venue using CDF-based method:
1. Calculate cumulative distribution of shot distances for home vs away teams at each rink
2. Assume all distances differ around the same league average with no net league bias
3. Adjust each shot's distance by matching quantiles to the league-wide distribution
4. Conditioned on shot type (slap vs non-slap)

Notable bias venues: Madison Square Garden had significantly different shot distributions.

### Training Data

- All even-strength events from 2010-11 and 2011-12 NHL regular seasons
- ~300,000 events per season
- Players traded mid-season treated as separate entities per team

### Key Results

- Home-ice advantage: ~0.32 goals per game
- Zone start effect: starting all shifts in offensive zone adds ~0.53 goals per game
- 10 additional offensive zone starts per game = ~5.4 additional goal differential per season
- Ridge parameter of 0.10 yielded rho = 0.12 (traded-player variance = 12% of all-player variance)
- THoR values converted to wins via: (per-event rating) * 80 events/game * 82 games / 6 goals-per-win

### Top Players (2010-12)

- Top forward: Alexander Steen (6.72 wins/season)
- Top defenseman: Kimmo Timonen (5.73 wins/season)
- Finding: forwards more valuable than defensemen at even strength

## DIGR (Defense Independent Goalie Rating)

### Methodology

Creates spatially smoothed save percentage maps using LOESS (locally estimated scatterplot smoothing) in R.

1. For each goaltender, create a smooth spatial map of save probability across the playing surface
2. Evaluate each goaltender against the league-average shot distribution
3. This produces a "defense independent" rating — what the goalie's stats would be facing average shot quality

### Shot Quality Model

Non-parametric spatial smoothing rather than parametric binning. The LOESS approach avoids arbitrary bin boundaries while still capturing location-dependent goal probability.

### Connection to THoR

THoR uses DIGR's shot-location-based goal probabilities as the shot valuation component. DIGR provides the defense-independent baseline; THoR extends this to a full player rating framework.
