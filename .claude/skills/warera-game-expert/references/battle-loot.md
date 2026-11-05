# Battle loot

Two layers `[RULE]`: instant loot per hit, and item pools distributed by combined rank.

## Instant loot (`loot.instant`) `[RULE]`

- Each **valid** hit has a case chance equal to your **Loot Chance** (skill: 5% at level 0, +2%/level, 25% at 10 `[LIVE]`).
- Elite-case chance = Loot Chance / 100 (20% loot chance → ~0.20% elite case per hit).
- **Missed hits generate nothing** (no case, no elite case) — Precision matters for loot.
- Expected cases per N valid hits = N × lootChance; elite = N × lootChance/100 (F-LOOT). Per **attempt**: lootChance × min(Precision,
  100%). At 25% loot and 100% precision, one case per 4 attempts; at 65% precision, one per ~6.2. Precision above 100% adds nothing
  to loot.
- `[OBS]` (`[CODEX]`, 2026-09-14): the battle's hit counter and loot summary count **landed hits only**. Summed over all 247 and
  282 participants of two battles, the summaries matched each battle's hit count and damage exactly, and cases per counted hit
  matched loot chance (60 players, 2,808 cases).

## Round and battle pools (`loot.pools`) `[RULE][LIVE]`

- Every **200,000** total damage in a round (both sides combined) adds one equipment/weapon item to the **round pool**.
- Every **500,000** damage over the whole battle adds one item to the **battle pool**.
- At the end, items are sorted by estimated value and handed out by **combined rank**: rank 1 gets the most valuable, etc.
- **Cutoff**: a pool has `floor(damage ÷ divisor)` items, so only ranks 1 … item count are paid; everyone below gets nothing from
  that pool. `[OBS]` (`[CODEX]`, 2026-09-16): last paid ranks 327 and 253 in two rounds = their item counts; rank 254 of 2,186
  participants in a 127.6M battle. Six battles (2.9M–127.6M) all had exactly `floor(total ÷ 500k)` battle items.
- **Yield** `[OBS]` (`[CODEX]`, gear prices of 2026-09-16): round pool ~0.082–0.086 money per 1k damage, battle pool ~0.034, so
  **~0.12 per 1k** in all, two thirds of it from the round pool. Mean item value 16.4–17.3 against a drop-table expectation of
  19.0; top-10 ranks took ~0.070 per 1k of the battle pool, the tail ~0.032. Dated prices: recompute before use.
- Why it matters: the items come from **both** sides' damage while the ranking is relative, so a big battle pays well without a
  huge personal share; and a build that raises damage per hit earns here, while the per-hit case channel depends only on hits
  landed and Loot Chance.
- Damage dealt on **both sides** counts toward the combined rank — but switching sides can break orders, contracts and
  diplomacy: never without authorization `[POLICY-RO]`.
- Loot chance above 100% **stacks** (220% → 2 cases + 20% chance of a third) `[WIKIPATCH v0.17.0]`; not restated by the
  v0.24.1 rework `[GAP]`.
- Both layers date from **v0.24.1** (2026-03-30): per-hit case = Loot Chance %, elite case = Loot Chance % / 100, misses loot
  nothing; Loot Chance base 2 → 5 in v0.24.2.
- `[DEPRECATED]` **Ranking loot-chance pool** (v0.17.7 → 2026-03-30): damage in a ranking added loot chance to a pool (3% per
  1k damage, 2.5% from v0.21.0) shared by the top 30% at the end of each round/battle. v0.24.1 replaced it with the item pools
  above; the live key `rankingsLootPercentPer1kDmg` = 1.5 is legacy (`loot.ranking_pool`).
- Still undocumented `[GAP]`: `battle.hitFor1CaseInPool` 20, `battle.casesPer1kDamagesInPool` 1 (probably legacy too).

## Case contents (regular case) — weapon share `[LIVE]`, rarity split `[WIKI-ONLY]`

30% weapon / 70% other equipment (matches `loot.weaponChancePercent` 30). Rarity: Common 62% · Uncommon 30% · Rare 7.1% ·
Epic 0.85% · Legendary 0.04% · Mythic 0.01%. Cases also come from weekly ranking rewards.

**Elite case** `[CODEX]` (community guides: *Complete Game Guide V1* 2026-06-18, *Case Economy* 2026-05-28; not official, not
in the config): same slot roll, rarity Uncommon 50% · Rare 32% · Epic 15% · Legendary 2.5% · Mythic 0.5% (no Common). Sums to 100%.
Treat as a community table until an official source or a large opening sample confirms it.

*Derived* scrap value of an unopened regular case (dismantle yields = craft scrap 6/18/54/162/486/1,458): 0.62×6 + 0.30×18 +
0.071×54 + 0.0085×162 + 0.0004×486 + 0.0001×1,458 ≈ **14.7 scrap**. At mid-2026 prices that sat about at the case's market price
`[CODEX]`, so opening for scrap was a high-variance break-even, not an edge. Elite case, same method with the community table:
0.5×18 + 0.32×54 + 0.15×162 + 0.025×486 + 0.005×1,458 ≈ **70 scrap**.

## Ethical loot tactics `[STRAT-RO]`

- Watch the pool preview and the damage needed for the next rank, not fixed historical thresholds.
  `[OBS]` 2026-10-14 (API, verified): the pool preview is exact. The combined (both-sides) user damage ranking shows,
  per rank, the real pool item that rank would get if the round ended now. For ended rounds, 23 of 23 sampled ranks
  received exactly that item (same item id). Rarity only falls going down the ranking. So "damage to the next rarity"
  is the gap to the last rank holding it, and someone holding the last item of a rarity loses it as soon as one player
  below passes them. Bot: `/loot_targets`.
- Coordinate in the MU who goes for which item; don't outbid teammates for the same item when the country needs damage elsewhere.
- Reuse useful drops; sell overkill items and buy a sufficient cheaper version.
- Splitting activity across two rounds/battles gives more pool chances — only if priorities allow and no costly travel is needed.

## Behaviours that hurt the national objective `[POLICY-RO]`

Hitting the opposite side for pool rank · using Pill and Stamina for loot while a national #1 is active · MU members competing
for the same item · farming in battles involving NAP partners or allies.
