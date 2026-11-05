# Evaluation — the 20 acceptance questions

Expected reasoning per question, verified against the skill on 2026-10-05. "Answerable" = the skill can answer from its sources;
"Partial" = answer with stated gaps; "No" = must say the information is missing.

| # | Question | Status | Expected answer (short) | Where |
|---|---|---|---|---|
| 1 | Is moving my company to a region with a +37% deposit worth 5 concrete? | Answerable with inputs | Cost = 5 × concrete price. Daily gain = economic profit at +37% − at current bonus (same base PP; inputs at market value). Break-even = cost / gain; worth it only if < deposit time left. Needs: current bonus, base PP/day, product & input prices, concrete price, deposit remaining time, employee tax. `break_even.py`. | companies.md, formulas F-BREAKEVEN, S4 |
| 2 | Which of two products has the better profit per PP? | Answerable with prices | Economic profit per base PP incl. input opportunity cost; run both input models (U-ECO-1); discount illiquid goods. `economy_calculator.py compare`. | formulas F-PROFIT, S3 |
| 3 | Should an Economy player reroll this damage mission? | Answerable | Usually yes: first reroll free, then 2×(k−1); damage costs consumables/gear, often in debuff or without orders. Keep only if damage comes naturally on an order. | missions.md, S7 |
| 4 | What happens when I Prestige at level 50? | Answerable | −65,000 XP (not reset), +50% XP bonus (P1; inactive at 50), 1 Prestige Point, free full respec, Prestige badge; landing level from the XP table (86,600 → 25; 150,000 → 49). | prestige.md |
| 5 | Prestige Points for repeated upgrades of the same skill? | Answerable | Doubling: 1, 2, 4, 8, 16 … (n levels = 2^n − 1). Reset refunds them. | prestige.md |
| 6 | Order rank #1 vs High priority? | Answerable | Rank = display order (what to fight first), no bonus/cost effect; priority = bonus (+5/10/15, disputed vs config 10) and paper ×1/×2/×4. A red #3 out-bonuses a green #1. | battle-orders.md |
| 7 | Can an MU Commander register an MU for a tournament? | Answerable | Yes — owner and commanders register/withdraw MUs while registration is open (Mon 00:00 – Fri 18:00 UTC). | tournaments.md |
| 8 | Does the tournament rarity cap apply to qualification battles? | Answerable | No — qualifiers are exempt; the cap applies from the first bracket round; server refuses over-cap weapon/ammo/gear hits. | tournaments.md |
| 9 | Alliance bonus at 12% world development under the current formula? | Answerable | 20 − 4×(12−10) = **+12%** (guide + wiki agree); config key 10 is an older model — mention briefly. | alliances.md |
| 10 | What formula applied before September 1, 2026? | Answerable | +10% up to 15% WD, −0.5/pt, floor 0 (v0.25.0, from 2026-06-10); the current curve took over 2026-09-01 00:00 UTC (announced in v0.25.5). Before 2026-06-10: the flat ally bonus +10%. `--as-of` resolves it. Dated answers exist for other mechanics (e.g. Pill before 2025-10-04 = 24 h/24 h). | versioned-mechanics.md |
| 11 | Current deposit bonus in this region if the API says 38%? | Answerable | 38% — live state overrides the reference for this calculation (guide range 20–40, config key 30); 38 is within the guide range. Doesn't change the global rule. | production-bonuses.md, data-model.md |
| 12 | Is this salary profitable for the employer? | Answerable with inputs | Max wage/PP = (1 + bonus + loyalty) × (price − input cost)/recipe PP; compare with gross offered wage; mention model ambiguity and balance/tax. `economy_calculator.py wage`. | employees-and-wages.md |
| 13 | Days until this company move breaks even? | Answerable with inputs | days = (concrete × price) / (new − old daily economic profit); check vs deposit time left. | formulas F-BREAKEVEN |
| 14 | Should this player use a Pill now? | Answerable with state | Checklist: valid order and rank, in region, full Health/Hunger, 8 h availability, buildings active/activating, bounty active, contract side, MU help timing; not in debuff phase from a previous Pill (cycle 23.5 h). | ammunition-food-pills.md, S10 |
| 15 | Is this a game rule or a Romanian community policy? | Answerable | Use labels: e.g. "don't fight without orders" = `[STRAT-RO]`; "+15% High order" = `[RULE]` (disputed value); "bounty 0.05/1k, budget 500" = `[POLICY-RO]`; NAPs = community agreements, not game objects; alert codes undefined. | SKILL.md §1 |
| 16 | Is this transaction potentially boosting? | Answerable with data | Compare price with the market reference at that time, repetition, one-way value, Family Group/shared IP, wage band 0.8–1.2×, donations favouring one person → "potential boosting, needs admin review", never a verdict. | account-rules-and-security.md, S22 |
| 17 | Data fields needed for company profitability? | Answerable | product, engine level, owner/employee bars and Production, active days, production_bonus_percent (or its components), product/input market prices with timestamps, wage_per_pp, loyalty, storage level and stored PP, employee tax; for moves: deposit_expires_at, concrete price. | data-model.md |
| 18 | Additional data to determine the most efficient battle? | Answerable | Orders (issuer, priority, rank, description), battle sides/type/launch region (player's region & Stamina/oil only until v0.27.4), diplomacy (alliance share, pact/enemy days, NAPs), active buildings, resistance fill, maluses, battle state (round/terrain/pools/tick), bounties/contracts and eligibility, Pill phase, Health/Hunger, consumables, gear. Absolute damage not computable. | data-model.md |
| 19 | Which mechanics are approximate rather than exact? | Answerable | 2.4 self-work factor, damage-per-hit stacking, round duration, ~50–60% best bonus, resistance linearity, milestone XP pattern, stat equivalences, market observations, deposit lifetime; plus everything `[WIKI-ONLY]` (rank table, case rarity split, paper formulas, Management meaning). | unresolved-mechanics.md |
| 20 | What changed between two WarEra versions? | Answerable | `data/patch-history.yaml` lists dated changes for every version v0.0.2 → v0.27.1 (v0.19.1 has no article). Apply them newest first: a later patch overrides an earlier one (e.g. v0.25.1 auto-claim undone by v0.25.5). A few values changed with no article (vote 10→15→20, Sworn Enemy upkeep ×2→×10, auction step 0.05→0.01): give those as undated. | versioned-mechanics.md, deprecated-mechanics.md |

## Regression commands

```
python scripts/validate_mechanics.py
python scripts/combat_bonus_calculator.py --selftest
python scripts/combat_bonus_calculator.py --alliance-share 12            # Q9 -> +12 with DISPUTED warning
python scripts/combat_bonus_calculator.py --alliance-share 12 --as-of 2026-08-25   # Q10 -> uncertainty warning
python scripts/progression_calculator.py prestige-points --levels 4      # Q5 -> 1+2+4+8 = 15
python scripts/economy_calculator.py wage --item steel --bonus 34 --loyalty 5 --price steel=1.8 --price iron=0.12 --offered 0.06
python scripts/break_even.py --cost-concrete 5 --concrete-price 1.6 --item steel --daily-base-pp 300 --old-bonus 20 --new-bonus 37 --price steel=1.8 --price iron=0.12 --advantage-days 3
python scripts/combat_calculator.py mitigation --skill-level 6 --item 29 --item 27   # 92 -> 70%, 3 HP/hit
```
