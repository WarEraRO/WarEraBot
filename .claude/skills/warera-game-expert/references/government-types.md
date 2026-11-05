# Government types

> **v0.27 (admin article `6ade08f7899288ce9f0bfe36`, live since 2026-10-26).** Party ethics are gone. Each
> country picks a **government type** that shapes how it fights and earns. `[RULE]` from the article, and **every value below is
> confirmed by the live client** of 2026-10-27 `[LIVE-CLIENT]` (`LIVECLIENT_V0271`, the government-type modifier table; in-game
> wording from `TRANSLATION_EN`). Registry: `government.types`, plus the per-type values in `bonus.patriotic`, `bonus.main_enemy`,
> `bonus.defensive_pact`, `bonus.bunker`. The ethics they replace: [parties-and-ethics.md](parties-and-ethics.md) (history).

## Rules

- Every country **starts as Provisional**: no modifiers at all (client `PROVISIONAL: {}`; UI "No effects", "No government type
  chosen yet") `[LIVE-CLIENT]`.
- Chosen **by law** ("Set government type"). After the first pick, changing it has a **30-day cooldown**
  (`GOV_TYPE_CHANGE_COOLDOWN_DAYS` 30; UI "The government type changed less than 30 days ago"). The law's paper cost isn't stated
  `[GAP]`; voting is the normal Congress law vote (24 h, per [1170b9](guide-articles-ledger.md)) `[OBS]`.
- A new type's limits apply **at once**: the country leaves its alliance, drops pacts or its sworn enemy, or fires its ministers
  if the type requires it.

## The seven types

| Type | Bonuses | Costs and limits |
|---|---|---|
| **Republic** | ×2 development income from **own** regions | **no** development income from conquered regions; orders cost +25% |
| **Nationalist State** | patriotic **30%** (normally 20%); sworn enemy bonus starts at **5%**, grows **5%/day**, max **15%** (normally 1%, 1%/day, 10%); orders −25% | development income ×0.7; **no alliance** |
| **Homeland Front** | **+5% bunker**; **free orders** to defend or retake your own regions; ×2 resistance in your occupied regions | attack orders outside your regions cost ×2; **no military bases** |
| **Federation** | alliance and pact upkeep halved; orders on allies' battles half price; **+5% when fighting for an ally**; pact bonus grows **2%/day** (normally 1%) | patriotic **15%**; **no sworn enemy** |
| **Plutocracy** | payroll and manager taxes ×1.4 (the extra comes from the game, not from players); strategic resource income ×1.5 | patriotic **10%**; **can't send money to another country** |
| **Autocracy** | development income ×1.25 | no congress and no ministers: the President and VP vote laws; unrest builds ×2 as fast |
| **Mercenary State** | order damage ×2 (normal while your capital is occupied) | order cost ×2; no alliance, pacts or sworn enemy; an occupied capital at full resistance revolts on its own |

Settled by the client and its in-game text (2026-10-27) `[LIVE-CLIENT]`:
- **Mercenary State** doubles the **national** (country) order bonus: "National orders give ×2 bonus (normal bonus while the
  capital is occupied)" (`orderBonusMultiplier` 2). MU orders aren't part of it.
- **Homeland Front**'s "×2 resistance" doubles **players' resistance contributions** in its occupied core regions ("Resistance
  contributions ×2 in its occupied core regions", `coreResistanceContributionMultiplier` 2), not the bar's passive growth. Its
  free orders cover "defend, revolt in or retake its core regions" (`coreOrderCostMultiplier` 0 on its own side in a core region).
- **Federation**'s half-price orders cover "allies' **and pact partners'** battles" (`allyOrderCostMultiplier` 0.5).
- **Order cost** multipliers multiply: base × `orderCostMultiplier` × 0 (own side, core region; Homeland Front) × 2 (attacking a
  non-core region; Homeland Front) × 0.5 (supporting an ally; Federation). Only the factors a type sets differ from 1, so a
  Republic order costs ×1.25 everywhere, a Mercenary State order ×2, a Nationalist State order ×0.75.
- Development income: Nationalist State ×0.7 and Autocracy ×1.25 apply to **core and conquered** regions alike; Republic is ×2
  core and ×0 conquered.
- **Since v0.27.2** these multipliers apply **on top of** the global ×2 development and strategic-resource income `[LIVE]` (live
  API, 2026-10-29: the region's `govType` income line is +100% of the doubled development line for a Republic core region,
  −30% for a Nationalist State, +50% of the strategic-resource line for a Plutocracy). Per development point per day: Republic
  core 4, Autocracy 2.5 *[Derived, not sampled]*, Nationalist State 1.4, others 2. Plutocracy strategic resources: 3 × core
  development of the resource's original country.

Still open `[GAP]`: whether Federation's pact max stays 10%; whether "+5% bunker" adds 5 points to the level value (the
calculator assumes so; the client key is `bunkerBonusDelta` 5, which fits); the law's paper cost. The UI also has a "No ministers
(vice president only)" label that no current type uses in the client table (Autocracy removes ministers **and** Congress), so it
may be a leftover of the Fanatic Imperialist ethic.

`python scripts/combat_bonus_calculator.py --government nationalist_state --patriotic --enemy-days 2 --as-of 2026-10-27` applies the
patriotic, sworn-enemy, pact and bunker changes. Federation's +5% for allies and Mercenary State's doubled orders are left to
`--override`.

## Lineage `[Derived]` — useful context, not a rule

Most types carry over an old ethic's identity, which helps when reading older guides: Mercenary State ≈ Unethical (doubled orders,
no treaties, auto-revolt of an occupied capital); Homeland Front ≈ Fanatic Pacifist (free home-defense orders); Federation ≈
Diplomatic (cheap pacts); Nationalist State ≈ Isolationist (faster sworn enemy); Republic ≈ Republican (development income, core
only); Plutocracy ≈ Imperialist (tax income); Autocracy ≈ Fanatic Imperialist (no ministers). The numbers differ; never apply
an old ethic's value to its successor.

## Derived consequences `[Derived]`

- **Patriotic spread**: own-country battles range from +10% (Plutocracy) to +30% (Nationalist State). Against an ally's +20% curve
  (before the size penalty), a Plutocracy's citizens may get more from fighting for an ally than for their own country.
- **Nationalist sworn enemy** reaches its max of 15% after 2 days (5 → 10 → 15), versus 9 days for the normal 10%.
- **Republic** suits a country that holds its cores and conquers little: conquests add no development income, and orders cost more.
  v0.27.2's doubling makes its core bonus worth twice as many coins (4 instead of 2 per point per day).
- **Autocracy** removes Congress, so the F-SEATS formula and congress elections stop mattering. It also removes the ministers who
  could set orders, leaving the President and VP to do it.
- **Plutocracy** pays more when the country's companies pay large wages and manager salaries (taxes ×1.4) and when it holds
  strategic resources from big countries (×1.5 income). It can't fund an ally or a proxy with money transfers.
- **Homeland Front** can't build military bases, and its attack orders cost double outside its own regions: a defensive or
  reconquest posture.
- A type switch is a **treaty event**: choosing Nationalist State, Federation (sworn enemy) or Mercenary State breaks the
  alliance, pacts or sworn enemy it forbids **immediately**, and the 30-day cooldown locks the choice. Coordinate with allies
  before the law passes.

## Where to see it in game

The country page shows the type and an **Estimated daily income** ("Daily income": the sum of the regions the country controls;
market taxes and other income are not included). Hovering it breaks the income down by line, which is the input every
comparison below needs. Region pages show "Est. daily income", "Estimated from current development, rosters, managers and tax
rates. Updated hourly." `[LIVE-CLIENT]` text.

## Strategy `[STRAT-RO]`

No Romanian community guidance exists yet for government types. Treat the choice like the old ethic choice: a strategic decision
for the government and Congress, weighed against alliance membership, the war situation and treasury income, and not a
tactical switch (30-day cooldown).

### Community analysis `[STRAT-EXT]` (guide `6adfb0879f5bbacb371170b9`, 2026-10-27, live data of that morning)

- **Income**: Republic usually pays the most for a country that holds its own cores (example: Germany, Republic +1,040 a day vs
  Plutocracy +730 vs Autocracy +336); conquered land shifts the answer, because Republic gets nothing from it.
- **Plutocracy** grows with the employee and manager tax collected. Switch when that tax passes the break-even against Republic
  for your country (the guide charts it per country; Poland already passed it, and Lithuania, Venezuela and Pakistan earn more
  under Plutocracy thanks to conquests or rich resources). A tax cut moves the break-even later.
- **War**: defending your land → Homeland Front (free orders); attacking abroad → Mercenary State (doubled order bonus at double
  cost); fighting your sworn enemy → Nationalist State (top patriotic and enemy bonus, cheaper orders); helping allies →
  Federation (the only ally bonus, half-price ally orders). Where several reach the bonus ceiling, pick the cheaper orders. The
  guide states a ceiling of 95% (115% in a revolt); this skill doesn't apply a cap (U-CDX-1, still open).
- **Income tax**: each 1% costs every employee 1 happiness and so 1% output; the guide puts the revenue peak at **20–22%** and
  warns against going higher, because employees start quitting (50 − 20 = 30, the quit threshold) *Derived*. 60 countries ran
  3–5% that day.
- **"Tax bank" idea**: allies move companies into one Plutocracy to earn its ×1.4 tax. Moving loses the 5% home-core bonus,
  which only pays off above ~12.5% tax, and a Plutocracy can't send money to other countries, so paying allies back needs a type
  change first (30 days).
