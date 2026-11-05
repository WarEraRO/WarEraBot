# Scenario reasoning patterns

Format per scenario: **Inputs · Relevant mechanics · Decision process · Calculations · Risks · Recommended action · Still needed**.
Scenarios A–J mirror the guide's practical cases; others are reusable patterns built on the same sources.

---

### S1. Level 15 economy player (guide A)
- **Inputs**: level 15, economy build, few companies, limited money.
- **Mechanics**: skill costs, company costs, engine levels, missions, MU help, travel costs.
- **Process**: keep economy build; grow toward 6 companies with AE 5; treat valuable gear as capital (sell rare+); join an MU;
  do missions; contribute minimal damage only to Low orders or for missions.
- **Calc**: next company cost `100 + 50(k−2)`; skill level needed `k − 2`.
- **Risks**: respeccing for one battle; spending oil on pointless trips; hiring too early.
- **Action**: no respec; invest in companies/engines; reroll costly damage missions.
- **Needed**: current companies, engine levels, money, concrete/steel prices.

### S2. Level 30 player preparing a Fight respec, 6 companies and 3,000 money (guide B)
- **Mechanics**: respec cost 0.5/point (30×4 = 120 points → 60 money), 7-day cooldown, consumables, optimizer (travel oil until v0.27.4).
- **Process**: run the optimizer with a conservative bonus; buy 10–14 days of consumables + reserve oil; pick a build near
  0.15–0.20/1k; keep liquid-output companies for cash flow; time the respec with a mobilization code or MU rotation.
- **Calc**: days sustainable = (3,000 − respec − 500 reserve − gear) / net daily cost (level 25+ → 200–400/day indicative).
- **Risks**: bomb build lasting 3 days; respec without national need; (until v0.27.4: forgetting oil for distant fronts).
- **Action**: respec only when national need is confirmed and stock covers ≥7 days.
- **Needed**: optimizer output (daily cost, cost/1k), current consumable prices (front distance only until v0.27.4).

### S3. Choosing between two products
- **Inputs**: base PP/day, bonus per product/location, prices of products and inputs, wage.
- **Mechanics**: F-PROFIT, opportunity cost, liquidity.
- **Process**: compute economic profit per base PP for each (inputs at market value); discount illiquid goods; consider
  switch cost via break-even.
- **Calc**: `economy_calculator.py compare --product a:bonusA --product b:bonusB --price ...`.
- **Risks**: deciding on one day's price; ignoring input opportunity cost; U-ECO-1 model ambiguity (run `--bonus-inputs both`).
- **Action**: switch only if the gap survives both models and break-even < expected advantage duration.
- **Needed**: realistic sell price (volume), deposit time left.

### S4. Moving a company for a deposit bonus (e.g. +37% for 5 concrete) — until v0.27
> From v0.27 (2026-10-26) deposits are off and strategic resources don't boost production: there is no bonus to chase. Use the
> free v0.27 move to bring companies to a **core region of your own country** (+5% employee output, taxes fund your country); weigh
> the region's income tax, which costs employees 1 happiness per 1%, and the −10 happiness for 7 days on moved employees.

- **Inputs**: current bonus, new bonus (live), deposit time left, daily base PP, prices, concrete price.
- **Mechanics**: deposit bonus variable 20–40% (live value wins), move cost 5 concrete, F-BREAKEVEN.
- **Process**: compute old vs new daily economic profit; cost = 5 × concrete price; compare break-even with deposit time left;
  if the product also changes, cost 10 concrete.
- **Calc**: `break_even.py --cost-concrete 5 --concrete-price C --item X --daily-base-pp P --old-bonus O --new-bonus 37 --price ... --advantage-days D`.
- **Risks**: deposit depleting soon; employee tax in the new region; raw input price for processed goods.
- **Action**: move if break-even < remaining deposit time with margin.
- **Needed**: deposit remaining time, current bonus, employee tax there.

### S5b. Is this employee (candidate) worth keeping? — v0.27
- **Inputs**: Production, expectation, traits, age, Potential, Luck, product prices, PP value, owner Management, manager,
  happiness (incl. the tax hit), tool, same-good days, core region.
- **Mechanics**: F-EMPLOYEE-WAGE margin, happiness 50 − tax%, quit below 30, retirement at 65 (+1 year per day worked or trained since v0.27.4), training 1 draw/day
  (10 Energy), toolbox 0.1%/Luck/h ([employees-and-wages.md](employees-and-wages.md)).
- **Process**: margin/hour = (Production/4) × [v × (1 + boosts) − PP_value × expectation × trait]; multiply by worked hours left before
  65 (24 × (65 − age) if every hour of every working day is paid; idle days don't age them since v0.27.4); weigh trainable Potential and Luck (toolboxes) as upside.
- **Risks**: payroll gap (nobody works that hour); high tax pushes happiness toward 30; battles in the region (−5; the 1% death
  risk is off since v0.27.1 "for now"). Bonus parts add (settled 2026-10-26, U-V27-3); only the client's ×-flagged traits are
  open (U-V27-3a).
- **Action**: prefer young, high-Potential, low-expectation candidates; fire or retrain negative-margin employees, remembering
  coworkers lose 5 happiness for 24 h (firing itself is free since v0.27.1). Quick in-game check `[STRAT-EXT]`: compare the
  card's wage chip with its bonus chip (keep if the gap is ≤ 20 points, since specialization adds 1 point a day for 20 days).
- **Needed**: the employee card, current PP value, product net value per PP, tax rate.

### S5. Evaluating a worker salary — until v0.27 (job market)
- **Inputs**: product, prices, bonus, loyalty, offered wage/PP.
- **Mechanics**: F-MAXWAGE, loyalty +1%/day to 10%, after-tax ordering, 0.8–1.2× normal wage band.
- **Calc**: `economy_calculator.py wage ... --offered W`.
- **Risks**: wage above ceiling; balance too low (failed sessions); minimum-wage arrangements viewed as suspicious.
- **Action**: post below the ceiling with a margin; keep wage balance; retain good workers.
- **Needed**: market wage level, tax rate, storage/break-room capacity.

### S6. Comparing two fight builds (guide F)
- **Process**: optimizer for A (more damage, higher daily cost) and B (cheaper per 1k); divide budget by daily cost: if A lasts 5
  days and B 10, B usually yields more total damage over the mobilization; check items (a +2% crit rifle for +5 money may give
  less damage; two cheaper armor pieces may hit the same breakpoint).
- **Calc**: `combat_calculator.py cost1k`, `combat_calculator.py mitigation`.
- **Action**: choose the sustainable variant; reinvest savings in consumables.
- **Needed**: optimizer outputs (damage/day, cost/day), mobilization length.

### S7. Should an Economy player reroll a damage mission?
- **Mechanics**: reroll cost 2 × (k−1) (first free); mission XP 10/50/100; set bonus at 7/10.
- **Process**: estimate the consumables/gear cost of the damage target (fighting in debuff or without order is wasteful); compare
  with the reroll cost and with whether 7/10 is reachable without it.
- **Action**: usually reroll (first one free). Keep it only if the damage happens naturally on an order the player would hit anyway.
- **Needed**: rerolls used this period, the damage target, the player's gear.

### S8. Open or sell a case
- **Calc**: `economy_calculator.py case-ev` with current drop values; compare with case price.
- **Rule**: price < EV → open on average (variance high); else sell. `[OBS]` margin historically only ~0.1–0.3.
- **Needed**: drop table (battle case `[GAP]`; wooden case odds known), current prices.

### S9. Fighting with or without orders
- **Mechanics**: order bonus (+5/10/15, disputed), patriotic +20, NAPs, travel cost.
- **Process**: no order → ask government/MU; check NAPs (`/nap list`), Resistance Focus; compute bonus total; if <~50% and no
  objective, don't spend gear.
- **Action**: don't fight without orders when Romania has direct battles; "Missions only" → minimal damage.

### S10. When to use a Pill
- **Process**: valid order? in the right region? full Health/Hunger? time to return within 8 h? buildings active or activating?
  bounty active? then activate. In debuff: economy, positioning.
- **Calc**: `combat_calculator.py pill --consumed-at ...` for the current phase.
- **Risks**: wasting buff on idle hours (activating before travel was a risk until v0.27.4).

### S11. Loot conflicting with a national objective (guide C)
- **Process**: don't start immediately; check `/diplomacy`, `/nap list`, #battle-orders, ask commanders (round-trip travel
  cost only until v0.27.4); if allowed and no critical front, split targets within the MU; controlled damage; don't burn a Pill for one item unless
  rank probability justifies it.
- **Policy**: never hit the opposite side for pool rank; don't farm while a national #1 is active.

### S12. MU running low on oil
- **Calc**: HQ oil/day = oil_per_hour(L) × 24 (L4 = 240). Days left = stock / that.
- **Process**: HQ switches off without oil (+bonus lost); prioritize oil donations (priority 1), consider downgrading HQ level or
  activating only for planned windows (3 h activation).
- **Needed**: stock, planned windows, oil price.

### S13. Country running low on paper
- **Process**: paper funds orders (×1/×2/×4 by priority), laws, treaties, alliance/pact/enemy upkeep (non-payment suspends alliance
  bonus). Cut Medium/High orders to what multiplies damage most; prefer one High #1 over many orders; consider Pacifist Fanatic
  (free core-defense/revolt orders) only as a strategic ethic choice (14-day cooldown). From v0.27 the analogue is a government
  type: Homeland Front (free orders to defend or retake own regions) or Nationalist State (orders −25%), 30-day cooldown.
- **Needed**: paper stock, daily upkeep, planned orders.

### S14. Country can't afford bounties (guide D)
- Government publishes the situation, asks for sustainable donations; MoE sells liquid assets; MoD uses efficient contracts or
  minimum rates; fighters with resources continue to orders.

### S15. Proxy nearing inactivity
- **Mechanics**: inactive flag 3 days (live; guide 4); takeover needs gov **and** congress inactive; takeover min level 25.
- **Policy**: don't exceed ~70 h offline; rotate leaders (no cooldown to leave gov and run elsewhere `[OBS]`); keep several active
  people in gov/congress.
- **Action**: log in now; delegate; report to Romania's government.

### S16. Suspicious citizenship influx (guide E)
- **Process**: proxy officer reports on Discord at once; don't accept applications until joint decision (only President/VP manage
  them); check elections and positions; suspend treasury transfers until clarified.
- **Goal**: legitimacy and abuse prevention — **not** emptying the treasury before a possible takeover (that is fund abuse).
- **Also**: new citizens during a revolt lower the resistance bonus.

### S17. Alliance becoming too large
- **Calc**: share after joining; `combat_bonus_calculator.py --alliance-share S` (9 → +20, 12 → +12, 15 → 0, 20 → −20).
- **Action**: reject or restructure if a new member pushes share past 10%; note the live-config conflict (U-CMB-3).
- **Needed**: world development totals (live).

### S18. Tournament registration deadline approaching
- **Rules**: closes Friday 18:00 UTC; only President, VP, MoD (or MU owner/commanders) can register; <2 entries → cancelled.
- **Action**: check who is online among authorized roles; register or withdraw before the deadline; announce skill bonus and rarity cap.

### S19. Tournament rarity restriction
- **Rules**: server refuses hits with weapon/ammo/gear above the cap; qualification battles exempt; cap from the first bracket round.
- **Action**: separate compliant set saved; auto-equip checked; ammo rarity checked; optimizer run with allowed gear.

### S20. Level 50 considering Prestige
- **Calc**: `progression_calculator.py prestige --total-xp X --level 50` → XP − 65,000; bonus +50% (first); level after `[GAP]`
  (examples 86,600 → ~25; 150,000 → ~49).
- **Process**: Prestige gives a free respec — best timed with an Eco ↔ Fight switch; check the build still meets cost/1k at the
  lower level; XP bonus is inactive while sitting at 50, so staying capped wastes it.

### S21. Government handover (guide I)
- New government immediately checks treasury, paper/oil stocks, NAPs, alliance, proxies, active orders and their rank, Resistance
  Focus, tournament registrations; requests anything missing from the previous leadership; documents it in a shared channel.
- Remember: only the President nominates; other roles are blocked until appointments.

### S22. Suspected boosting transaction
- **Inputs**: transaction price, market reference price at that time, frequency, counterparties, Family Group status.
- **Process**: compute price ratio; check repetition and one-way value flow; wages outside 0.8–1.2× normal; donations benefiting one
  person. Conclude only "potential boosting, needs admin review"; report with evidence via official channels.

### S23. Shared IP (guide G)
- Register a Family Group in advance with an admin; no gear trades or working for each other; balanced transactions.

### S24. Raising resistance in an occupied region (guide H)
- Government sets a Resistance Focus with reason and planned date; citizens contribute (no need to travel `[OBS]`); avoid recruitment
  campaigns while filling/revolting (cap grows with citizens); fighters hit from anywhere since v0.28 (before: travel to the disputed region).

### S25. Distant front, little oil (guide J) — obsolete since v0.28 (2026-11-03): distance costs fighters nothing
- Ally 14 regions away: full bar → 100 Stamina + 8 oil one way, same back. Compare the ally bonus (no patriotic +20) and battle
  importance with total oil for all fighters plus return. If not critical, let nearby allies cover it and contribute bounties/contracts.
