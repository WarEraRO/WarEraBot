# Battle mechanics

## Rounds `[RULE]`

- A battle is fought between two countries for one region. The first side to win **2 rounds** wins `[LIVE]`.
- Max rounds: guide "3 (best of three)" vs live `battle.maxRounds` = **15** `[CONFLICT]` (U-CMB-1). With 2 wins needed a
  decisive battle ends in ≤3 rounds; 15 suggests rounds can end undecided — undocumented.
- A round is won at **300 terrain points** `[LIVE]`.
- Only **one active battle between two countries** at a time.

## Ticks and terrain `[RULE][LIVE]`

Every **2 minutes** (tick), the side with the larger **damage pool at the end of the tick** gains terrain. Damage pools reset at
the end of each round.

| Terrain already won by **both sides combined** in the round | Terrain gained per tick |
|---|---|
| 0–99 | +1 |
| 100–199 | +2 |
| 200–299 | +3 |
| 300–399 | +4 |
| 400–499 | +5 |
| 500–599 | +6 |

The row is picked by the **combined** total of both sides (closed with the user, U-CMB-2), which is why rows above 300 exist even
though a side wins at 300: a contested round can reach a combined 599 (299 + 300). `[OBS]` Independently, the UNIKHORNE codex's
battle ETA, which feeds the live round state into this combined-total schedule, matches the countdown the game shows to within
minutes `[CODEX]`; keyed on the leader's terrain alone it doesn't. So every round speeds up as it ages, for both sides.

Duration `[RULE~]`: in ideal conditions a round lasts at least **~6 h 10 min** (one side wins every tick: 100 ticks at +1, 50 at
+2, 34 at +3 = 184 ticks ≈ 6 h 8 min) and at most **~8 h 5 min** (guide). The maximum fits the combined model: when the sides split
the ticks evenly, the combined total climbs through every row up to ~599 (100 + 50 + 34 + 25 + 20 + ~17 ≈ 245 ticks ≈ 8 h 10 min)
before either side reaches 300. Hence timing and holding damage for terrain thresholds matter more than uncoordinated damage.

## Launching attacks and positioning `[RULE]`

- An attack goes from a **launch region** to a **target region**. `[VERSIONED]` Since **v0.28 (2026-11-03)** fighters hit from
  anywhere (config `battle.locationGateEnabled` false); from v0.26.0 to v0.27.4 attackers had to stand in the launch region and
  defenders in the target region ([map-and-travel.md](map-and-travel.md)).
- Revolts recover occupied core regions; fought from the disputed region.
- **Any region can attack any region** (guide v0.26.1): adjacency, ownership of neighbours and connection to the capital don't
  matter for the right to attack; capital connection only matters for the defender's −25% malus. `[VERSIONED]` Older wiki pages
  (war 2026-08-24, battle 2026-08-28) still say attacks must come from an adjacent owned region — the pre-map rule.
- Battles need a **war** (Declare War law, one-sided; the initiator gets "priority" for 24 h — meaning undocumented). Battles are
  opened by the President, VP, Minister of Defense or Minister of Foreign Affairs. New countries can't attack or be attacked for 7 days.
- A country can launch several attacks from the same region to different targets.

## Damage rankings `[RULE]`

Each player's damage counts in round and battle rankings, which drive loot-pool distribution ([battle-loot.md](battle-loot.md)).
Your damage shows on battle cards; the battle page's loot summary shows what you got.

## End of round / battle `[RULE]`

Round pool distributed at round end, battle pool at battle end. After a battle in a region there is a **~1 h cooldown**
before that region can be attacked again; the owner may use it as a launch region meanwhile `[LIVE]`.

## Tactics `[STRAT-RO]`

- Damage counts **comparatively at tick end**; you don't need to lead the whole interval.
- Hold damage for the last seconds/minutes if counter-bombs are likely, respecting latency and commanders.
- At 100 and 200 terrain each tick is worth more; consecutive control accelerates.
- Don't overfeed a tick already won if damage can be saved for the next tick or another front.
- Bunker/Base activation ~12 h (deactivation fast); HQ ~3–4 h and burns oil hourly; buildings without oil switch off.
  Don't start a costly attack before the base activates if the objective allows waiting.
- Cutting a region's link to its capital gives the defender −25% and can drastically cut campaign cost.
- Pills, regens, MU help and Stamina are limited: save them for threshold ticks, round ends, building activations and #1
  orders. A fighter already in the region with full stats is worth more at the critical moment than one who hit all day.
