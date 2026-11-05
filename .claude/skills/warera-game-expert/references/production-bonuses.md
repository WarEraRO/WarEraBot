# Production bonuses

## From v0.27 `[RULE]` (2026-10-26 ~14:00 UTC; admin article `6ade08f7899288ce9f0bfe36`)

The admin's stated goal: end the "move your company to the best region" meta, so a company does best at home.

| Old source | From v0.27 |
|---|---|
| Deposits | **turned off** (`production.deposit_bonus`, `production.deposit_depletion`) |
| Country specialization | **removed** (the Set Specialization law goes with it) |
| Party ethics (Fanatic Industrialist / Agrarian) | **removed** with ethics |
| Strategic resources | **no longer boost production or development**; each pays its holder a **daily income equal to the development of the country it originally belonged to** (`country.strategic_resource_income`; Plutocracy ×1.5); **×2 since v0.27.2** (2 × that country's core development per day) |
| Worker loyalty | gone with the job market |

What remains are **employee modifiers** (`employees.production`): owner's Management +2%/point, manager +2%/point (max +22%,
+44% together), happiness ±1%/point from 50, tools +3…+65%, same good +1%/day (max +20%), **+5% in one of your country's core
regions**, and traits. They **add** into one production bonus (in-game "added together" `[LIVE-CLIENT]`; details in
[employees-and-wages.md](employees-and-wages.md)). Whether the Automated Engine and self-work get any bonus after v0.27, and which, isn't stated `[GAP]`;
read the production tooltip. Everything below this section describes the system **until v0.27**.

*Derived consequence:* strategic resources move from an economy lever to a **treasury and war-target** question. A resource
originally from a large country is worth far more to whoever holds its region, so holding or taking such regions matters to the
treasury, not to company placement.

## Until v0.27

The bonus applies to PP from the engine, self-work and employees `[RULE]`. Sources: strategic resources, country
specialization, the ruling party's ethic, and the region's active deposit. **For a specific company always use the live value
(region page / production tooltip / API).**

### Deposits (`production.deposit_bonus`, `production.deposit_depletion`) `[VERSIONED]`

| Source | Statement |
|---|---|
| v0.25.5 (2026-08-29) + guide v0.26.1 `[RULE]` | Bonus drawn **at random between +20% and +40%** when the deposit is discovered; fixed until it runs out; deposits are temporary and appear/disappear; real value on the region page and the company's production tooltip. |
| History | deposit bonus went live v0.7.1 (2024-11-11) at **+20%**, **+30%** from v0.16.12 (2025-08-04), random 20–40% from v0.25.5 (2026-08-29). Config key and wiki company page still say 30 (legacy). |
| Duration `[RULE]` (v0.22.0/v0.22.1, 2026-01-09) | A deposit lasts **1–5 days** (no depleting quantity any more); a discovery is rolled **every hour** with a **10%** chance. Use the move window's remaining time. |
| Old depletion `[VERSIONED]` | v0.17.2 (2025-08-24) → 2026-01-09: −0.5% of the initial quantity per hour, new deposits every 12 h. Config `depleteHourlyPercent` 0.5 is the legacy key of that model. |

Why it matters: a +40% deposit produces 1.40/1.20 ≈ **17% more** than a +20% deposit of the same resource, so a rich deposit
can justify a move. Supplied live value (e.g. API says 38%) → use 38% for that calculation; it does not change the
global rule.

`[STRAT-RO]` Move only if the extra profit recovers the move cost within an acceptable time **and before the deposit expires**
(`scripts/break_even.py --advantage-days`). For processed goods also price the raw input: a big bonus doesn't guarantee
profit if the raw material is expensive.

### Strategic resources (`production.strategic_resource_bonus`) `[RULE][LIVE]`

Types: Lithium, Coal, Diamonds, Uranium, Rare Earths, Gold — randomly placed in core regions and **reshuffled every month**. Bonus
per type by copies: 1st **+5%**, 2nd **+0.5%**, 3rd+ **+0.25%** (each type separate: 2 Lithium = 5.5%). The bonus applies **only to
the country's specialization item** (closed with the user, U-ECO-12; the specialization law of v0.21.0 says the production bonus
"applies only to that item", which the codex also quotes `[CODEX]`). Producing anything else in that country gets nothing from
its strategic resources. The guide's listing of the two as separate sources describes where the number comes from, not its scope.

### Specialization and ethics `[RULE]`

- The country picks a production specialization by law; changing it has a **10-day cooldown**.
- The ruling party's ethic can add **+30%**: **Fanatic Industrialist** for ammo or construction specialization goods (but deposits
  can't spawn in your borders); **Fanatic Agrarian** gives +30% on grain/livestock/fish deposits (only food deposits spawn; no
  specialization). Specialization groups `[WIKI-ONLY]`: raw (wood, limestone, iron), processed (paper, concrete, steel).
- Combined with strategic resources and a deposit, the best available bonus starts around **~60%** `[RULE~]`.
- A company moved into a country that specializes in its product and owns the matching strategic resource can produce
  **50%+ more** than in a neutral region `[RULE~]`.

### Loyalty (employee-side bonus)

+1% per day worked at the same employer, max 10%; applied after work; see
[deprecated-mechanics.md](deprecated-mechanics.md#job-market-and-player-workers-until-v027).

### Total bonus

Sources are **added** (wiki: country + deposit bonuses "added together"; guide `1 + bonus + loyalty`; closed with the user, U-ECO-6).
Prefer the tooltip total. Snapshot field: `company.production_bonus_percent` (never assume).

`[CONFLICT]` U-CDX-2 (history only, both systems are gone since v0.27): the codex reports one in-game reading that fits
**multiplying** country and deposit bonuses: Portugal, iron specialization at +25% plus a +30% iron deposit in Laâyoune-Sakia El
Hamra, shown as **+62.5%** on 2026-08-23 (1.25 × 1.30 = 1.625; adding would give +55%) `[CODEX]`. It also says ethics were added
on top (wiki example: 20% strategic + 30% Fanatic Industrialist = 50%). One observation against a user-confirmed rule: U-ECO-6
stands, but when reconstructing a pre-v0.27 tooltip, check both readings.
