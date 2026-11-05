# Crafting, dismantling and scrap

## Rules `[RULE]` (guide 21.2; data `data/equipment.yaml#crafting`)

- Equipment dismantles into **scrap**; scrap + **steel** craft equipment.
- The scrap needed to craft = the scrap obtained by dismantling the finished item, so **the real crafting cost is the steel**.
- Crafting a **specific** item costs **double** the steel of a random craft.
- Manual dismantling returns scrap proportional to remaining durability (100% → full scrap column).
- An item reaching **0 durability in battle breaks and auto-dismantles for 1/3** of a new item's scrap value.

| Rarity | Scrap to craft | Steel (random) | Steel (specific) | Scrap when broken |
|---|---|---|---|---|
| Common (grey) | 6 | 1 | 2 | 2 |
| Uncommon (green) | 18 | 2 | 4 | 6 |
| Rare (blue) | 54 | 4 | 8 | 18 |
| Epic (purple) | 162 | 8 | 16 | 54 |
| Legendary (yellow) | 486 | 16 | 32 | 162 |
| Mythic (red) | 1,458 | 32 | 64 | 486 |

Live config `mergingCost` = 2/4/8/16/32/64 by rarity — matches the "specific" steel column; mapping plausible, unconfirmed `[INFER]`.

`[VERSIONED]` `[LIVE]`: crafting appears in the menu at **level 7** since v0.27.4 (2026-11-02; level 10 from v0.27); bulk dismantle
is a premium feature from level 7. `[RULE]` (article only) Since v0.27.4 the dismantle filters can select several types and
rarities at once. Employee
**tools** can be dismantled for scrap but never traded (scrap yield per tool rarity `[GAP]`).

**Random craft slot** `[OBS]` (`[CODEX]`, 2,200 crafts by five heavy crafters): weapon ~30%, each of the five armour slots ~14%,
the same 30/70 split as cases.

**Is the chosen slot worth double steel?** `[CODEX]` with September 2026 prices (dated, recompute): the surcharge was priced close
to what choosing gains. A legendary pair of boots gained 23.89 over the random result and cost 27.17 in extra steel; a mythic jet
gained 51.26 against 54.34. It flips only when steel is cheaper than ~1.5–1.6. Mythic random craft cost ~381 (1,458 scrap at 0.222
+ 32 steel at 1.79); average result value: jet 453, boots 440, gloves 380, helmet 370, pants 361, chest 346. So weapon and boots
carry a random mythic craft, gloves break even, the rest lose; a top roll (jet 293 Attack, 47% crit) sold for ~560. Weapon value
barely moves with crit from 41% to 49% and jumps ~19% at 50%.

## Real cost of an item (F-ITEM-COST)

`real cost = market price − value of scrap recovered` — so using an item until it breaks returns only 1/3 of its scrap.
`[STRAT-RO]` Consume gear fully only when you actually fight with it. A looted item you won't use is worth more dismantled
whole (or sold) than broken in battle.

## Strategy `[STRAT-RO]` with `[OBS]` numbers

- Beginners/Economy players: **don't craft Common, Uncommon or Rare** — cases already supply plenty. Observed average loss at
  the time of writing: Common ~1.5, Uncommon ~3, Rare ~5 money (dated; recompute).
- Exception: a crafting mission — crafting one Common may be acceptable; otherwise reroll.
- Epic/Legendary/Mythic random crafting can be profitable on average with a large budget, but variance is high (you need
  capital to absorb bad luck). Epic and Legendary are more liquid than Mythic; a Mythic may show good ROI on paper but lock
  capital. Own steel production improves margins.
- Quick evaluation of case drops: a green item without max stats is worth about its scrap (18) — dismantle immediately;
  always dismantle guns (pistols); helmets with 28%+ are close to max.
