# Battle damage bonuses and penalties

Bonuses from different sources are **added** (guide 33.1) and the total is floored at **−100%** (no damage below zero). No
cap is documented. Pill, ammo and rank are separate multipliers, not part of this sum. Always prefer the battle tooltip.
`[CONFLICT]` U-CDX-1: the UNIKHORNE codex instead multiplies each battle bonus separately and caps the total at **+95%** (+115% in
revolts). This skill keeps the user-confirmed additive model (U-CMB-9a); the guide's own totals above +95% (e.g. attack +125%)
would also contradict such a cap. If a tooltip ever stops at 95, record it.
Calculator: `python scripts/combat_bonus_calculator.py ... [--as-of DATE] [--override key=tooltip_value]`.

| Source | Value | Condition | Status |
|---|---|---|---|
| Patriotic | **+20%** | your country is one of the two sides (attack, defense, revolt) | `[RULE][LIVE]`; earlier lower value, date `[GAP]`. v0.27: Nationalist State 30, Federation 15, Plutocracy 10 |
| Country order | +5 / +10 / +15% (Low/Med/High) | stacks with MU order on the same side; none in civil wars (can't be set since v0.26.2) | `[RULE]` (guide; wiki agrees); config single key 10 = likely Medium/base |
| MU order | +5 / +10 / +15% | | `[RULE]` (guide; wiki agrees) |
| MU Headquarters | +5 / +10 / +15 / +20% (L1–4) | HQ active (has oil); applies in **any** battle, attack or defense (wiki; consistent with the guide's scenario tables) | `[RULE][LIVE]` |
| Alliance | up to **+20%**, can go **negative to −20%** | depends on alliance share of world development | `[CONFLICT]` config 10 |
| Defensive Pact | +1%/day up to +10% | defending the partner's territory; in revolts, the side recovering its homeland | `[RULE]`; v0.27: Federation +2%/day; none for Mercenary State |
| Main (Sworn) Enemy | starts +1%, +1%/day, max +10% | attack or defense vs the declared enemy; Isolationist +5%/day (guide); the +5% start is `[WIKI-ONLY]` | `[RULE][LIVE max]`; v0.27: Nationalist State 5 / +5 per day / max 15; none for Federation or Mercenary State |
| Fighting for an ally as a Federation | +5% | v0.27 only | `[RULE]` |
| Resistance | full bar: ~+30% citizens / ~+15% allies | attackers in a revolt; scales with bar fill | `[RULE][LIVE]` |
| Military Base | +5…+25% (L1–5) | attack launched from a region with an active base; owner's citizens full, **allies half** (pact partners none `[WIKI-ONLY]`) | `[RULE][LIVE]` |
| Bunker | +5…+25% (L1–5) | defending a region with an active bunker; owner's citizens full, allies half (pact partners none `[WIKI-ONLY]`); **not in civil wars** | `[RULE][LIVE]`; civil-war exclusion `[VERSIONED]` v0.26.2 (2026-10-14); v0.27: Homeland Front +5% |
| Unethical country order | +10 / +20 / +30% | ethic uses all ethic points, doubles order cost, forbids treaties | `[RULE]` until v0.27; successor: Mercenary State "order damage ×2" |
| Pacification Center (Fanatic Expansionist) | +3% per center level | defending a revolt in a region you occupy | `[RULE]` until v0.27 (no successor) |
| Region not linked to capital (supply line) | **−25%** | you defend such a region | `[RULE][LIVE]`; −10% → −15% (2025-01-27) → −25% (2025-05-25) |
| Fighting for your occupier | **−50%** | you fight for a country occupying ≥1 core region of yours | `[RULE][LIVE]`; was −30% from 2025-08-21 |
| Lost attacking region | −25% | config-only key, condition unknown | `[GAP]` |
| Floor | total ≥ −100% | | `[RULE]` |

## Alliance scaling (F-ALLIANCE) `[CONFLICT]`

```
bonus = +20                         if alliance share of world development ≤ 10%
bonus = max(−20, 20 − 4 × (share − 10))   otherwise
```
12% → +12 · 14% → +4 · 15% → 0 · 17.5% → −10 · ≥20% → −20. An oversized alliance is **penalized**, not just denied a bonus.
Confirmed by the wiki's alliance and battle pages (the battle page carried it by 2026-08-28). Live config
`battle.allianceDamagesBonusPercent` = 10 matches older models and is probably legacy; check the tooltip if it matters.
History (see [alliances.md](alliances.md)): flat +10% → +10% up to 15% WD, −0.5/pt, floor 0 (v0.25.0, 2026-06-10) → current curve
(from 2026-09-01 00:00 UTC, U-HIST-3). The share counts core development of the named alliance's members `[OBS]`.

## Reference totals (guide 33.1)

Assumes High orders, HQ L4, pact/enemy maxed, full resistance, max buildings, alliance at +20:

| Scenario | Total |
|---|---|
| Own revolt | +110% |
| Enemy revolt (you defend your occupation) | +105% |
| Allied revolt | +117.5% |
| Non-allied revolt | +70% |
| Enemy revolt vs non-ally | +60% |
| Defense | +105% |
| Allied defense | +115% (bunker counted full — inconsistency, U-CMB-4) |
| Non-allied defense | +70% |
| Attack | +125% |
| Allied attack | +92.5% |
| Non-allied attack | +60% |

Unethical ethic: own revolt +115% (capital free) / +100% (capital occupied); other battles +65% / +50%. Breakdown and
self-test: `data/combat-bonuses.yaml`, `combat_bonus_calculator.py --selftest`.

## Government types that change combat `[RULE]` (2026-10-26)

Ethics are replaced by government types ([government-types.md](government-types.md)). Combat effects: **Nationalist State**
patriotic 30, sworn enemy 5 → 15 (+5/day), orders −25%, no alliance · **Homeland Front** +5% bunker, free orders to defend or retake
own regions, attack orders outside own regions ×2, no military bases · **Federation** +5% for allies, pact +2/day, half-price orders
on allies' battles, patriotic 15, no sworn enemy · **Plutocracy** patriotic 10 · **Mercenary State** order damage ×2 (normal while
the capital is occupied), order cost ×2, no treaties, an occupied capital at full resistance revolts on its own · **Republic**
orders +25%. Calculator: `combat_bonus_calculator.py --government TYPE --as-of DATE`.

*Derived:* the reference totals below assume patriotic +20 and v0.26 rules. For a Nationalist State, scenarios with patriotic gain
+10 and a maxed sworn enemy gains +5, but any alliance or allied part disappears (no alliance allowed). For a Plutocracy, patriotic
scenarios lose 10. For a Federation, patriotic scenarios lose 5 and the sworn-enemy part disappears.

## Ethics that changed combat `[RULE]` until v0.27

- **Fanatic Expansionist** (offensive, occupation): bases can be upgraded/downgraded every **2 h** instead of 8; +3% per
  Pacification Center level when defending revolts in occupied regions; occupied regions generate **double resistance**.
- **Pacifist Fanatic** (defensive, recovery): battle orders for defending core regions and for revolts are **free** (no paper);
  starting a revolt in enemy-occupied territory **copies the enemy bunker bonus**; **cannot have a Main Enemy**.
- **Fanatic Isolationist**: Sworn Enemy starts at +5%, +5%/day; orders vs the enemy −50% paper; all treaty upkeep +50%.
  **Fanatic Diplomatic**: pact upkeep −50%, orders supporting a pact partner −50%, Sworn Enemy upkeep +100%. **Unethical**: national
  orders give double the priority bonus at double paper; no treaties; if the capital is occupied orders return to normal bonus and a
  full-resistance revolt automatically starts in the capital. Full ethics list: [parties-and-ethics.md](parties-and-ethics.md).
- Ethic change cooldown: 14 days.

`[STRAT-RO]` (pre-v0.27) Fanatic Expansionist suits a country holding foreign territory; Pacifist Fanatic suits one recovering its cores
(free orders save paper in long revolt campaigns; copying the bunker cancels the occupier's defensive edge) at the cost of
the Main Enemy +10%.

## Efficiency heuristic `[STRAT-RO]`

Romanian operational notes consider fights with total bonus below **~50%** usually inefficient — a cost rule, not a ban:
strategic objectives, valuable loot or emergency orders can justify exceptions. The patriotic +20% makes Romania's own
battles relatively more efficient for Romanian fighters than allied ones (from v0.27 that edge depends on the government type:
10–30%).
