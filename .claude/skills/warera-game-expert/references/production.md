# Production chains and recipes

Machine-readable: [../data/recipes.yaml](../data/recipes.yaml). Guide and live config agree on every recipe `[RULE][LIVE]`.

## Raw resources (PP only)

| Item | PP / unit | Climates `[LIVE]` | Feeds |
|---|---|---|---|
| Iron | 1 | moderate, arid, tropical, polar | Steel |
| Lead | 1 | moderate, arid, polar | Light Ammo, Ammo, Heavy Ammo |
| Mysterious Plant | 1 | tropical | Pill |
| Fish | 40 | polar ("cold climates") | Cooked Fish |
| Livestock | 20 | moderate, tropical | Steak |
| Grain | 1 | moderate, tropical | Bread |
| Petroleum | 1 | moderate, arid, tropical | Oil |
| Limestone | 1 | moderate, arid | Concrete |
| Wood | 1 | moderate, tropical, polar | Paper |

## Processed items

| Item | Recipe per unit | Use |
|---|---|---|
| Steel | 10 PP + 10 Iron | upgrades, bunkers, bases, MUs, crafting |
| Concrete | 10 PP + 10 Limestone | companies, MUs, construction, moves, move home (100) |
| Light Ammo | 1 PP + 1 Lead | +10% attack |
| Ammo | 4 PP + 4 Lead | +20% attack |
| Heavy Ammo | 16 PP + 16 Lead | +40% attack |
| Bread | 10 PP + 10 Grain | +10% max health |
| Steak | 20 PP + 1 Livestock | +15% max health |
| Cooked Fish | 40 PP + 1 Fish | +20% max health |
| Oil | 1 PP + 1 Petroleum | HQ/bunker/base/pacification upkeep; travel fuel (until ~2026-11-10, v0.28) |
| Paper | 1 PP + 1 Wood | laws, orders, motions, treaties, diplomatic upkeep |
| Pill | 200 PP + 200 Mysterious Plant | +60% attack 8 h, then −60% 15.5 h |

**Embodied PP** (recipe + inputs' PP) for vertically integrated producers: steel 20, concrete 20, bread 20, steak 40,
cooked fish 80, pill 400, heavy ammo 32, oil 2, paper 2.

## Map impact on the economy `[OBS]`

`[VERSIONED]` From v0.26.0 oil also had individual demand (2 oil per region of travel not covered by Stamina). At the time of
writing the oil price rose from ~0.18 to ~0.20 — a dated observation, not a current price. Since v0.28 (2026-11-03) fighters
don't travel, and once movement is off (~2026-11-10) no one does: oil keeps only its building upkeep demand (HQ, bunker, base,
pacification center), so expect that travel premium to unwind `[Unverified]`.

## Ambiguity: does bonus output consume inputs? `[CONFLICT]` (U-ECO-1)

The guide's cost/revenue formula charges inputs only on base units, while its max-wage formula implicitly charges inputs on
bonus units too. The calculators default to the conservative model (inputs scale with output) and accept
`--bonus-inputs base|both`. Verify in game by producing a known PP amount with a known bonus and checking input consumption.
