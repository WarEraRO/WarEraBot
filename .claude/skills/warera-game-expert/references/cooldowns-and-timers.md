# Cooldowns, durations and windows

Machine-readable: [../data/cooldowns.yaml](../data/cooldowns.yaml). Political values are especially patch-sensitive; confirm
in game before a vote. A patch-announced temporary exception (e.g. a lifted cooldown) takes precedence for its stated duration.
**Never compute live timestamps** (resets, elections) — read `gameConfig.getDates`.

## Personal

| Mechanic | Value | Note |
|---|---|---|
| Skill reset | 7 days | `[RULE][LIVE]` |
| Pill buff / debuff | 8 h / 15.5 h | `[RULE][LIVE]` |
| Stamina | +10/h, max 100; removed ~2026-11-10 (v0.28) | `[RULE][LIVE]` |
| Energy/Entrepreneurship regen | 10% of max hourly on the hour | `[LIVE]` |
| Move home | 12 h, 100 concrete; free trip home ends ~2026-11-10 (v0.28) | `[RULE][LIVE]` |
| Wooden case | expires 48 h; max 5 pending; no map spawns from ~2026-11-10 (v0.28) | `[RULE]` |
| Citizenship | 30 days | `[RULE][LIVE]` |
| Vote after citizenship change | 7 days; none during a new country's first 14 days since v0.27.4 (article; config multiplier 2 `[LIVE]`, 14 = 7 × 2 *[Derived]*) | `[LIVE]` `[VERSIONED]` |
| Comeback reward | max 1 per 14 days | `[RULE]` |
| Inactive flag | 3 days (since v0.15.1) | `[RULE][LIVE]`; guide's 4 days = impeach-congress-member login rule |
| Leave a company after joining | 24 h | `[WIKIPATCH v0.17.7]` |
| Article tips | only within 3 days of publication; 1 per tipper/author per 24 h | `[WIKIPATCH v0.17.7]` |

## Military Units

| Mechanic | Value |
|---|---|
| MU help request | 12 h |
| MU nationality change | 7 days |
| HQ activation | 3 h + time to the next hourly tick (3–4 h) |
| MU announcement | 2/h, active 24 h |
| Tournament registration | Mon 00:00 – Fri 18:00 UTC |

## Battle, diplomatic, economic

| Mechanic | Value |
|---|---|
| Battle tick | 2 min |
| Re-attack a region after a battle | 1 h |
| Region building upgrade/downgrade | 8 h (Expansionist 4 h; Fanatic Expansionist 2 h for bases) |
| Bunker / Base / Pacification Center activation | ~12 h |
| Resistance contribution after a revolt | 24 h |
| Bounty activation delay | ~3 min |
| Bounty cancel lock | 60 s after activation |
| Mercenary auction | 5–25 min; bid in the last 30 s extends by 60 s (wiki + config) |
| Declare War priority | 24 h for the initiator |
| New country protection | 7 days (can't attack or be attacked) |
| New deposits spawn | every 12 h; depletion 0.5% of initial quantity per hour (deposits off from v0.27) |
| Strategic resources reshuffle | monthly (not restated by v0.27 `[GAP]`) |
| Country specialization change | 10 days (specialization removed in v0.27) |
| Party ethic change | 14 days (ethics removed in v0.27) |
| Government type change (v0.27) | 30 days after the first pick |
| Employee candidates (v0.27) | 3 per company, new at 00:00 UTC; extra sets 10 Energy, doubling |
| Employee training (v0.27) | 1 draw per employee per day |
| Employee wages / manager pay (v0.27) | hourly |
| Employee events (v0.27) | auto-resolved after 36 h; owner must log in every ≤ 3 days; from hiring on since v0.27.1 (was: only employees hired ≥ 48 h) |
| Employee retirement (v0.27) | asks at age 65, again every 10 years of age; age +1 per day worked or trained since v0.27.4 (per calendar day before), so presumably every 10 aged days *[Derived]* |
| Manager contract lock (v0.27) | 24 h after hiring, both sides |
| Employee happiness hits (v0.27) | coworker fired −5 for 24 h; employee moved −5 / company moved −10 for 7 days, no firing for 24 h (client, U-CDX-5); manager care +5 for 48 h |
| Removed map links (v0.27) | stay open 10 days after the update; v0.27.1 (2026-10-27) closed the links between regions that share no border |
| Alliance leave cooldown (v0.27.1) | reset, and off until 2026-10-30 00:00 UTC; then 7 / 14 days again |
| Defensive Pact proposal | 12 h |
| Leave/kicked from alliance | 7 days with no alliance |
| Rejoin the same alliance | 14 days |

## Electoral and legislative

| Mechanic | Value |
|---|---|
| Region transfer/liberation law | 12 h between proposals |
| Government renomination | 5 days |
| Leave government → run for president elsewhere | none `[OBS]` |
| Country takeover | 1 day cooldown (live); 5 days was the v0.15.0 rule quoted by the guide `[VERSIONED]` |
| Civil war motion | 48 h; unrest locked 72 h after a revolution |
| Law vote | 24 h `[LIVE]` |
| Election phase | 24 h candidacy + 24 h vote |

## Protection and non-aggression

| Mechanic | Value |
|---|---|
| Liberation after owner change | 5 days |
| Non-aggression after liberation | 24 h, bilateral |
| Non-aggression after peace | 72 h |
| Non-aggression after alliance break | 72 h |

## Resets (UTC)

Game day and daily missions 00:00 · weekly missions Monday 00:00 · monthly missions 1st 00:00 · regen every hour on the hour.
