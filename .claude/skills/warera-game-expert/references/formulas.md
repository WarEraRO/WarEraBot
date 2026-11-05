# Formulas

Each entry: **ID · variables/units · prerequisites · formula · example · assumptions · exactness · version**.
Percentages are percentage points unless written as fractions (`b = bonus/100`). "Exact" means stated by a source as a rule;
"approx." means the source gives it as an approximation; "inference" means derived by this skill and must be labelled.
Version: "v0.26.1" = guide; "live 2026-10-04" = config snapshot. Scripts implementing each formula are named.

---

## Economy

### F-ENGINE — Automated Engine output
- Vars: `L` engine level 1–7; `b` production bonus (fraction). Output PP/day.
- Formula: `PP/day = L × 24 × (1 + b)`
- Example: L5, +30% → 120 × 1.3 = **156 PP/day**.
- Exactness: exact (guide + live `upgradesConfig.automatedEngine.dailyProd`). Version: v0.26.1, live 2026-10-04.
- Since v0.27, `b` = 0 for the engine (U-V27-7, closed). Since v0.27.4 × 2 while a **Talks to Machines** employee is the company's
  only employee (client `engineOutputMultiplier` 2; not yet observed on a roster).
- Script: `economy_calculator.py engine`.

### F-SELFWORK — self-work output
- Vars: `E` max Entrepreneurship (bar) until v0.27, max **Energy** from v0.27; `P` Production skill value (PP per action; v0.27:
  30 + 3/level), `b`.
- v0.27: Energy also pays hiring, candidate rerolls and training, so subtract those actions; regen unchanged (`regenDividedBy` 10, live 2026-10-26).
  Example: Energy 200, P 60, no bonus → 20 × 60 × 2.4 = **2,880 PP/day** with nothing else spent.
- Formula: `PP/day = E/10 × P × 2.4 × (1 + b)`
- Example: E 80, P 40, +30% → 8 × 40 × 2.4 × 1.3 = **998.4 PP/day**.
- Assumptions: 2.4 ≈ max daily refills (guide). Derivation `[INFER]`: regen 10% of max per hour × 24 h = 2.4 bars; 10 points per
  action. Requires logging in often enough that the bar never sits full. No wage, no income tax.
- Exactness: approximate (guide calls 2.4 an approximation). Script: `economy_calculator.py selfwork`.

### F-EMPLOYEE-PP — employee output for the employer `[VERSIONED]`
- Until v0.27 (player workers): `base PP/day = Energy/10 × 2.4 × P` (employer then applies own bonus and loyalty). Inference from
  the same regen rules. Script: `economy_calculator.py employee` (models only this).
- From v0.27 (hired employees): `PP/hour = Production / 4 × (1 + Σ bonus%) × random 0.9–1.1`, so `6 × Production × (1 + Σ bonus%)`
  PP/day on average. Production = base + trained + trait/coworker Production. Bonus parts: Management, manager, happiness
  (±1 per point from 50), tool, same-good streak, core region, traits (`employees.production`). They **add** ("added together",
  in-game text `[LIVE-CLIENT]`); only the client's multiplier-flagged traits are unconfirmed (U-V27-3a). The daily figure assumes
  every hour is worked and paid. Script: `economy_calculator.py npc` (also wage, profit, marginal values, quit chance, card odds).

### F-EMPLOYEE-EVENTS — employee event rate (v0.27) *Derived* from `[LIVE-CLIENT]` keys
- `events/day ≈ min(3, √n / √3)` for n eligible employees (key `perSqrtEmployee` = 1/√3): 0.58, 0.82, 1.0 for 1, 2, 3. The client
  names the key, not the formula; treat the square-root reading as an inference.

### F-EMPLOYEE-WAGE — automatic employee wage (v0.27)
- `wage/hour = (paid Production / 4) × PP_value × expectation × trait modifier`; paid Production = base + trained only (trait
  Production is unpaid, `[OBS]` in several dev tooltips and on 82 live employees on 2026-11-02, against v0.27.4's note that it
  now counts toward the "expected wage": `[CONFLICT]` U-V274-1); PP_value from 7-day raw-material trades (0.1 with none); expectation
  0.70–1.30 at hire, Negotiation lowers it (floor 0.70), events raise it (ceiling 1.60); Greedy 1.2, Modest 0.85. Exact (article,
  client).
- Profit per day `[Derived]`: `6 × [v × Production × (1 + Σ bonus) − PP_value × paid Production × expectation × trait]`, where `v`
  = the product's net value per PP (≈ PP_value for raw goods; F-BASE-PER-PP for processed goods). Break-even for a raw good
  without trait Production: `1 + Σ bonus = expectation × trait`. Tax treatment `[GAP]` (U-V27-4).
- Marginal values per day, in PP-value units `[Derived]`: +1 trained Production `6 (1 + B − E)`; +1 trait Production `6 (1 + B)`;
  Negotiation −x `6 × paid Production × x`; +y% bonus `6 × Production × y`; owner Management level `0.12 × Σ Production`;
  +1 Responsibility (v0.27.3) `0.18 × Production` while happiness < 100.
- Happiness from tax and Responsibility `[VERSIONED]`: since v0.27.3 `happiness = 50 + 3 × Responsibility − employee tax %` before
  other effects (Loyal halves the loss); v0.27 → v0.27.2: `50 − employee tax % × (1 − 0.1 × Responsibility)`. Output bonus
  `happiness − 50` percentage points.

### F-EMPLOYEE-QUIT — quit chance (v0.27) *Derived*
- `quit chance per hour = 5% × (T − happiness) / T` below T = 30 (50 for Flight risk); `within 24 h = 1 − (1 − p)^24`. Fits the
  client's `quitChanceMax` 0.05 and a dev tooltip (Flight risk at 44 → 0.6%/h). Not stated by the game as a formula.

### F-TRAINING-RARITY — training-card rarity (v0.27) `[LIVE-CLIENT]`
- Weights with M = Management level (Leadership level until v0.27.3), K = employee Luck: Common `max(0, 55 − 2M − K)`, Uncommon
  `25 + M + 0.5K`, Rare `13 + 0.6M + 0.3K`, Epic `5 + 0.3M + 0.15K`, Legendary `2 + 0.1M + 0.05K`; share = weight ÷ total (100
  until Common hits 0).
  One rarity per hand. Constants from the client; the "move off Common" form from the in-game text and Elereo's guide, matching
  two dev screens exactly.

### F-EVENT-COST — wage-day costs (v0.27) `[LIVE-CLIENT]`
- `cost = max(0.01, round(hourly wage × 24 × wage-days, 2))`, using the wage of the employee in the event.

### F-STORAGE-FILL
- Formula: `hours_to_full = (capacity − stored) / (PP_per_day / 24)`; capacity = 200 × storage level (L1–L7) `[LIVE]`.
- Exact capacities; assumes uniform production. Script: `economy_calculator.py storage`.

### F-PROFIT — production economics (guide 18) `[CONFLICT U-ECO-1]`
- Vars: `B` base PP spent; `R` recipe PP per unit; `w` wage per PP; `q_i` input i per unit; `c_i` market price of input i;
  `p` sale price; `b` bonus.
- Base units `u = B / R`; output `u × (1 + b)`.
- Guide formula (model **base**): `Cost = B × w + u × Σ q_i c_i`; `Revenue = u × (1 + b) × p`; `Profit = Revenue − Cost`.
- Model **scaled** (consistent with F-MAXWAGE): inputs consumed for every output unit: `Cost = B × w + u (1 + b) Σ q_i c_i`.
- Accounting vs opportunity cost: if inputs are self-produced, cash cost of inputs is 0 but the **economic** cost still uses
  market prices (a raw material you produced is not free).
- Example (steel, B 500, +34%, iron 0.12, steel 1.80, w 0, own iron): u = 50, output 67, revenue 120.6; accounting profit 120.6;
  economic profit **40.2** (scaled: 670 iron × 0.12 = 80.4) or **60.6** (base: 500 iron = 60.0).
- Exactness: formula exact per guide; which model the game uses is unresolved. Script: `economy_calculator.py product|compare`.

### F-BASE-PER-PP and F-MAXWAGE — maximum profitable wage (guide 18) — F-MAXWAGE applies only until v0.27 (no owner-set wages after)
- `Base/PP = (p − Σ q_i c_i) / R`
- `MaxWage/PP = (1 + b + loyalty) × Base/PP` (fractions). Offer is profitable if posted gross wage/PP < MaxWage/PP.
- Example: steel 1.80, iron 0.12 → Base/PP = (1.80 − 1.20)/10 = 0.06; +34% bonus, 5% loyalty → **0.0834**.
- Note: this formula scales input cost with bonus (model scaled). Model base gives `((1+b+l)·p − Σ q_i c_i)/R`.
- Script: `economy_calculator.py wage`.

### F-BREAKEVEN — company move / product change (guide 20.3)
- `days = switch_cost_money / (new_daily_profit − old_daily_profit)`; switch cost = concrete × concrete market price (+ any
  lost production). Move 5 concrete, product change 5, both 10.
- Decision: worth it only if `days < remaining advantage` (deposit time left / horizon). If daily gain ≤ 0 it never pays.
- Example: 5 concrete at 1.6 = 8; gain 3.06/day → **2.6 days**; deposit expires in 3 days → marginally worth it.
- Exact (arithmetic). Script: `break_even.py`.

### F-DEPOSIT-RATIO (until v0.27; deposits off after)
- Relative output between two bonuses: `(1 + b_new) / (1 + b_old)`; e.g. 1.40/1.20 = **1.167** (+17%). Exact arithmetic.

### F-EMBODIED-PP
- `embodied = R + Σ q_i × R_i` (PP of a processed unit including its inputs' PP). Steel 20, pill 400, cooked fish 80. Exact.

### F-CASE-EV — expected value (guide 21.1)
- `EV = Σ P(drop_k) × value_k` (market or scrap value). Open if `price < EV` (on average; high variance). Exact method; drop
  tables for battle cases `[GAP]`. Script: `economy_calculator.py case-ev`.
- Scrap floor: `Σ P(rarity) × craft_scrap(rarity)` → regular case ≈ **14.7** scrap; elite ≈ **70** with the community rarity table
  `[CODEX]`. Exact arithmetic; the rarity tables are `[WIKI-ONLY]` / `[CODEX]`.

### F-WOODEN-QTY — wooden case contents (v0.27) *Derived* (`[CODEX]` method)
- `quantity = max(1, floor(budget / item_PP))`, budget drawn from the rarity's range (20–40 / 40–70 / 80–130 / 160–260 PP), item_PP
  = the item's recipe PP from `data/recipes.yaml` (raw 1, livestock 20, fish 40, concrete/steel/bread 10, light ammo/oil/paper 1,
  ammo 4, heavy ammo 16, steak 20, cooked fish 40, Pill 200). It reproduces the codex's ranges: ammo 20–32, concrete 4–7, steak and cooked fish 4–6, heavy ammo
  10–16, livestock 1–2, fish and Pill 1. Mean budget ≈ 51 PP per case. Not stated by an official source; confirm against openings.

### F-ITEM-COST — real cost of an item (guide 28.2)
- `real cost = market price − value of scrap recovered`; broken in battle → recovered = scrap_new / 3; dismantled → scrap_new ×
  durability%. Exact.

### F-FOOD-COST-PER-HP
- `cost per Health = price / (heal_pct × max_health)` (1 Hunger per item regardless). Exact arithmetic from sourced effects.

---

## Progression

### F-SKILL-COST
- Level n costs n points; `total(0→n) = n(n+1)/2`; `cost(a→b) = Σ_{k=a+1..b} k`. Exact (guide + live). 4 points per player level.
- Script: `progression_calculator.py skill-cost`.

### F-SKILL-VALUE
- `value(level) = base + step × level` (table in [skills-and-respec.md](skills-and-respec.md)). Exact for live snapshot.

### F-COMPANY-COST
- k-th company: `0` if k = 1, else `100 + 50 × (k − 2)` concrete; needs Companies skill level `k − 2`. Exact.

### F-RESPEC
- `cost = 0.5 × allocated skill points` (≈ 2 × level when all points are allocated). Exact (live). Cooldown 7 days.

### F-REROLL
- k-th reroll in a category within a period: `2 × (k − 1)`; table defined for index 0…20 (max 40). Exact (live table).

### F-MISSION-XP-MAX
- Per period: `10 × xp_each + set_xp` → daily 200, weekly 1,000, monthly 2,000. Exact.

### F-XP-CLOCK — repeatable XP per day *Derived*
- `200 + 1,000/7 + 2,000 × 12/365 + 10 (calendar) ≈ 418.6 XP/day` at full claims (since v0.25.5; ~286 before). Days per Prestige
  Point = 65,000 / (418.6 × multiplier): 155 banked at level 50, 104 / 97 / 91 after the 1st / 2nd / 3rd Prestige (assumes the
  Prestige bonus applies to mission XP). See [prestige.md](prestige.md).

### F-PRESTIGE-XP
- `XP_after = XP_total − 65,000`; level after = F-XP-LEVEL(XP_after). 86,600 → 21,600 → **level 25**; 150,000 → 85,000 → **49**.

### F-XP-LEVEL
- Level = highest L with cumulative_xp(L) ≤ total XP (wiki table in `data/progression-values.yaml`; L50 = 86,600). Skill points = 4 × L.
- Script: `progression_calculator.py level`. Exact (wiki table, consistent with the guide's 86,600 and Prestige examples).

### F-PRESTIGE-BONUS
- `XP bonus % = 50 + 10 × (p − 1)` for Prestige level p ≥ 1; inactive at level 50. Exact.

### F-PRESTIGE-POINTS
- k-th bonus level on the same skill costs `2^(k−1)` points (1, 2, 4, 8, …; total for n levels `2^n − 1`). Exact (guide + wiki).

---

## Combat

### F-MITIGATION — Armor/Dodge (guide 27, 28.6)
- `pct = round_to_2_significant_figures( T / (T + 40) )`, T = skill points (Armor 6/level, Dodge 4/level) + items.
- Example: T 92 → 0.6970 → **70%**; T 188 → **82%**; T 48 → **55%**.
- Exactness: exact formula with rounding verified for armor; assumed for dodge. Script: `combat_calculator.py mitigation`.

### F-HP-PER-HIT
- `HP per hit = 10 × (1 − armor%) = 10 × 40 / (armor + 40)`; expected with dodge `× (1 − dodge%)`; hits per bar = Health / that.
  The wiki's `max(1, …)` minimum is `[WIKI-ONLY]`. Hitting below 10 Health is possible since v0.22.0, depending on armor `[GAP]`.
- Exact (wiki + config `battle.healthCost` 10; matches guide 70% → 3, 82% → 1.8). Script: `combat_calculator.py hp`.
- Closed form for hits per Health point *Derived* (unrounded shares, above the 1-HP floor; same as the codex's): with A and D the
  armor and dodge **points**, `hits per Health = (A + 40)(D + 40) / 16,000 = 0.1 + (A + D)/400 + A·D/16,000`. The cross term is why
  armor and dodge reinforce each other. With the 2-significant-figure rounding (A-12) use the table instead.

### F-DAMAGE — expected damage per attempted hit
- Vars: A Attack (skill + weapon; +4 per precision point over 100%), P precision (≤1), C crit chance (≤1; overflow → +4 CD per point),
  CD crit damage (fraction), ammo a (0.1/0.2/0.4), Pill p (+0.6 buff / −0.6 debuff), rank r, battle bonus total B.
- `E = A (1 + a)(1 + p) × [ (1 − P)·0.5 + P·(1 + C·CD) ] × (1 + r) × max(0, 1 + B)`
- Example (wiki): A 276, P 0.69, C 0.24, CD 0.59, no multipliers → crit hit 439, **E ≈ 260**.
- Exactness: hit outcomes exact (wiki, patch v0.16.5); the multiplier chain is an inference from the guide ("Pill, ammo and rank
  multiply") — calibrate. Script: `combat_calculator.py damage`.

### F-RANK
- Rank bonus = row of `data/military-ranks.yaml` with the highest total_damage ≤ lifetime damage. Exact (wiki table). Script: `combat_calculator.py rank`.

### F-OVERFLOW
- `extra Attack = 4 × max(0, precision% − 100)`; `extra Crit Damage = 4 × max(0, critChance% − 100)`. Exact (guide + live).

### F-PILL-PHASE
- t = hours since Pill: `0 ≤ t < 8` buff (+60%), `8 ≤ t < 23.5` debuff (−60%), else none. Exact durations.

### F-COST-1K
- `cost/1k = (total consumable + gear-durability + travel costs − value recovered from cases/scrap/loot) / damage × 1000`.
  Community target 0.15–0.20 `[STRAT-RO]` (bounty income excluded). Script: `combat_calculator.py cost1k`.

### F-SUSTAIN-DAYS
- `days = budget / net daily cost`. Compare builds by total damage over the mobilization window, not damage per day.

### F-LOOT
- Expected cases = valid hits × lootChance; elite cases = valid hits × lootChance/100; misses give nothing. Exact (guide).
- Per attempt: `cases = lootChance × min(1, precision)`. Exact consequence of the rule.
- Pool items: round `floor(round_damage_total / 200,000)`, battle `floor(battle_damage_total / 500,000)` (both sides). Exact.
  Only ranks ≤ item count are paid `[OBS]`. Yield per 1k damage ≈ item value × (1/200 + 1/500) ≈ 0.007 × item value (≈ 0.12 at
  ~17 per item, Sept 2026 `[CODEX]`).

### F-TRAVEL
- Valid 2026-09-17 → ~2026-11-10 (movement off with v0.28); since 2026-11-03 fighting needs no travel.
- `oil = 2 × max(0, regions − floor(stamina / 10))`; Stamina used = 10 × min(regions, floor(stamina/10)). Exact.
- Example: 60 Stamina, 8 regions → 4 oil.

### F-TICK — terrain per tick and round length
- Terrain gain per won tick by the **combined** terrain of both sides (U-CMB-2): 0–99 → 1, 100–199 → 2, 200–299 → 3 … 500–599 → 6.
  Minimum ticks to 300 (one side wins every tick) = 100 + 50 + 34 = 184 → ≥ 6 h 8 min (guide ~6 h 10 min); evenly split ≈ 245 ticks
  ≈ 8 h 10 min (guide "at most ~8 h 5 min"). Exact table; round-length figures approx. `[CODEX]`'s battle ETA uses the same
  combined schedule and matches the game's countdown.

### F-HQ-OIL
- `oil = oil_per_hour(level) × hours active` (1/2/5/10 per hour for L1–L4). Exact.

---

## Battle bonuses

### F-BONUS-SUM
- `total = max(−100, Σ applicable sources)`. Sources and conditions: [battle-bonuses.md](battle-bonuses.md). Additivity per guide
  33.1 tables. Pill/ammo/rank are separate multipliers. Script: `combat_bonus_calculator.py` (version-aware).

### F-ALLIANCE `[CONFLICT U-CMB-3]`
- `s` = alliance share of world development (%): `bonus = 20 if s ≤ 10 else max(−20, 20 − 4 (s − 10))`.
- Examples: 12 → +12; 14 → +4; 15 → 0; ≥20 → −20.
- Version: guide v0.26.1; live config single value 10 disagrees; earlier model unknown.

### F-DAYS-BONUS — Defensive Pact / Sworn (Main) Enemy
- `bonus = min(start + full_days × rate, 10)`; start = rate = 1 (Sworn Enemy with Fanatic Isolationist: 5 and 5). Pact reaches 10 after
  9 days. Exact (guide + wiki).
- v0.27 government types: Nationalist State Sworn Enemy start 5, rate 5, **max 15**; Federation pact rate 2 (max assumed 10).

### F-RESISTANCE-BONUS
- `bonus = fill% × (30 for citizens | 15 for allies)` — "proportional to the bar" `[RULE~]` (linearity assumed).

### F-BUILDING-ALLY
- Allies get half of base/bunker: `5 × L / 2`. Exact rule; guide's allied-defense table contradicts it once (U-CMB-4).

---

## Politics

### F-SEATS
- `seats = clamp(ceil(active/20) + 2, 5, 50)`. 130 → 9; 73 → 6; 40 → 5. Exact. Scripts: `progression_calculator.py seats`, `country_calculator.py seats`.

### F-ORDER-PAPER
- `paper = base(Low 5, Medium 10, High 20) × max(1, floor(n / 5))`, n = active citizens (country) or members (MU); Unethical ×2;
  Fanatic Pacifist core/revolt 0; Diplomatic/Isolationist −50% in their cases. Wiki examples: 60 and 80. `country_calculator.py order-cost`.
  `[CONFLICT]` the guide says country cost scales with average development.
  v0.27 replaces the ethic modifiers with government-type ones: Republic ×1.25, Nationalist State ×0.75, Mercenary State ×2,
  Federation ×0.5 on allies' battles, Homeland Front 0 for defending/retaking own regions and ×2 for attacks outside them.

### F-TREATY-UPKEEP `[WIKI, low confidence]`
- Sworn Enemy `floor(AvgDev/10) × 10`/day; Defensive Pact `floor(AvgDev/10) × 5`/day each (pact page: `floor(AvgDev/10)`); alliance
  `floor(AvgDev + 0.5 × alliance members' AvgDev)`/day. Isolationist ×1.5; Diplomatic pacts ×0.5, Sworn Enemy ×2. `country_calculator.py upkeep`.

### F-INIT-DEV
- `initial development = ((active citizens × average level) / 20)^0.95` (wiki; 100 × 25 → 98.2, wiki rounds to 98.3).

### F-DEV-INCOME `[LIVE]` (v0.27.2, 2026-10-28; `country.development`, `country.strategic_resource_income`)
- Region: `daily income = region development × 2 × government multiplier` (Republic 2 core / 0 conquered, Autocracy 1.25,
  Nationalist State 0.7, others 1); paid hourly as `/ 24`. Before v0.27.2 the factor 2 was 1.
- Strategic resource: `daily income = core development of its original country × 2 × (1.5 if the holder is a Plutocracy)`.
- Verified on 40 regions and 9 countries with the live API (2026-10-29): the region `income` fields are per hour and match to
  4 decimals. Example: Solomon Islands region, development 83.24, Nationalist State: 83.24 × 2 / 24 = 6.9367/h development,
  govType line −30% = −2.0810/h.

### F-RESISTANCE-BAR
- `bar = region development × 100`; each contribution (10 Health or Energy) adds 2 (citizen) or 1 (non-citizen); bonus = 30% × fill
  (allies half). `country_calculator.py resistance-bar`.

### F-DEPOSIT-LIFETIME `[INFER]`
- Depletion 0.5% of initial quantity per hour → ≤ 200 h from full if linear. Prefer the move window's remaining time.

---

## Not available — do not invent

v0.27: who bears the employee tax on wages · what the client's multiplier flag does on traits · the full event-check formula
(only the Luck term is known) · the trait-slot cap · the base odds of keeping a retiree beyond the shown check ·
Exact stacking order of damage multipliers · per-hit RNG spread · elite-case drop table · resistance growth/decay formulas (passive
growth, decay keys) · civil-war cost unit (dev × 10 vs 100) · per-law paper costs · meaning of Declare War "priority".
