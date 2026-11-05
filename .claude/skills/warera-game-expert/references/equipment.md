# Equipment and rarities

Data: `data/equipment.yaml`.

## Rarities `[RULE]`

| Rarity | Colour | Usage principle `[STRAT-RO]` |
|---|---|---|
| Common | grey | very cheap; economic builds or scrap |
| Uncommon | green | efficient in some slots; check the stat, not just rarity |
| Rare | blue | transition to better builds |
| Epic | purple | often the best cost/performance and liquidity compromise |
| Legendary | yellow | strong, expensive; only when the optimizer justifies it |
| Mythic | red | maximum power, locked capital; not automatically efficient |

Wiki tier names: Basic, Reinforced, Advanced, Elite, Legendary, Mythic (= common … mythic). Gear trades on the **Equipment
Market**. **No level requirements** — anyone can equip any rarity they can afford. Only tournaments may cap rarity ([tournaments.md](tournaments.md)).

## Slots and stats `[RULE][LIVE]`

Weapon (Attack + Crit Chance) · Helmet (Crit Damage) · Chest (Armor) · Pants (Armor) · Gloves (Precision) · Boots (Dodge).
Chest and pants add up: Epic chest + Legendary pants can equal the reverse if totals match.

### Stat ranges by rarity `[LIVE]` (gaps between tiers are real — never interpolate)

| Weapon | Rarity | Attack | Crit % |
|---|---|---|---|
| Knife | common | 21–40 | 1–5 |
| Gun | uncommon | 51–60 | 6–10 |
| Rifle | rare | 71–90 | 11–15 |
| Sniper | epic | 101–130 | 16–20 |
| Tank | legendary | 141–170 | 26–35 |
| Jet | mythic | 221–300 | 41–50 |

| Rarity | Helmet (crit dmg) | Chest / Pants (armor) | Boots (dodge) | Gloves (precision) |
|---|---|---|---|---|
| common | 1–15 | 1–5 | 1–5 | 1–5 |
| uncommon | 16–30 | 6–10 | 6–10 | 6–10 |
| rare | 31–50 | 11–15 | 11–15 | 11–15 |
| epic | 71–90 | 21–30 | 21–25 | 21–25 |
| legendary | 91–110 | 36–50 | 31–40 | 31–40 |
| mythic | 121–150 | 56–70 | 51–60 | 51–60 |

## Durability and real cost

`real cost = market price − scrap value recovered` ([crafting-and-scrap.md](crafting-and-scrap.md)). Broken in battle → 1/3 of
new-item scrap; dismantled early → proportional to remaining durability. Optimizer durability % = copies consumed per cycle.

**Wear per hit** `[OBS]` (`[CODEX]`, controlled run on 2026-09-16, 43 dodge, epic rifle, 164 hits): every item starts at 100% and
loses **1% per hit**. The **weapon** wears on every attempt, misses and dodges included (164 hits → 164% of a rifle); **armour
pieces** wear only on hits you don't dodge (77% lost against ~79 expected undodged hits at 52% dodge). Ammo: one per attempt.
So a weapon lasts 100 attempts, and armour lasts `100 / (1 − dodge share)` attempts. Matches the rule that dodge spares
non-weapon gear (v0.15.12). Auto-equip (default on since v0.24.6) swaps in your best piece of the same rarity or lower.

`[CODEX]` cost model: wear per hit = item price × 1% (armour × (1 − dodge share)), net of the 1/3 scrap credit at the **scrap**
price, not the item price. Charging full market price overstates the minimum bounty or contract rate worth taking.

## Sets, Quick Equipment, auto-equip `[RULE]`

- Equipment sets switch configurations quickly (free 1 / premium 5 sets; kits 6 / 30 `[LIVE]`).
- Immediate equip and auto-equip can replace broken items with the best of the selected rarity **or lower** — check this
  setting before important battles and tournaments with a rarity cap.
- `[STRAT-RO]` If loot exceeds your needs, sell it and buy a cheaper piece with sufficient stats.

## Beginners and Economy players `[STRAT-RO]`

- Sell blue (Rare) and above early — the money is worth more invested in companies.
- Once you have a few passive companies, use a **knife** and green gear. Knife uses no ammo (incompatible with ammo).
- Avoid the green **gun** early: its ammo is too expensive for early progression.
- Avoid knives under 30 Attack or under 4% crit; do your own cost/efficiency check — knife prices vary a lot.
- Sell scrap and buy green items with max stats: usually only ~0.1–0.2 money more, often nearly twice as efficient `[OBS]`.

## Advanced valuation `[OBS]`

Goal: maximize **damage per money spent**. Example: a level-40 epic player choosing between two rifles: the one costing ~5
money more with +2% crit gave similar or lower damage for that build. Same with helmets/gloves: +2% Crit Damage (88→90%) can
be worth less than +1–2% Precision at the same price. See [combat-stats.md](combat-stats.md) for equivalences and breakpoints.
