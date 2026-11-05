# Markets, trading and cases

## Market mechanics `[RULE]`

- Market access from level 7 `[LIVE]`; **level 5** (trading too) from v0.27 (2026-10-26). v0.27 also gives each listed item its own
  price and shows similar offers to help price it; premium opens **50** cases at once (was 10). Two markets `[WIKI-ONLY]`: the **Trading Market** (raw materials, processed materials, cases
  and elite cases, scrap) and the **Equipment Market** (weapons, helmets, chests, gloves, pants, boots). Config `isTradable: false`
  on gear refers to the trading market only.
- **Market tax** (equipment market): the buyer pays the seller's price plus the **buyer's country** market tax, which goes to the
  buyer's country (set by the Change Tax law). `[OBS]` (`[CODEX]`, 2026-09-09): the listed price **already includes** the buyer's
  tax ("All prices displayed include a 1% market tax from your country"), so the number on the card is what leaves your account,
  and the same item shows a higher price to a citizen of a high-tax country. The seller gets the same either way. The tax follows
  the buyer, not where the good was made, so it plays no part in choosing a production region.
- Orders never match between Family Group members, your own MU, or a country where you are in government `[WIKIPATCH v0.16.0]`.
- Currency: **coins** (also called "btc"; this skill says "money"). **Gems** are premium (cosmetics, supporter plan) and can't be
  bought with coins.
- A cost button you can't afford opens the buy window **pre-filled with exactly the missing quantity** (gems → shop;
  money/items → market). For MU/country/party costs the check uses that entity's inventory and opens the market for its wallet.
- Hovering over money shows a full inventory preview grouped by type and rarity.
- Price limits and anti-boosting rules apply: artificial trades can be sanctioned.

## Trading guidance `[STRAT-RO]`

- Flip margins can be small (1–2%); volume and turnover speed matter more than the percentage.
- Bread, steak and other liquid consumables suit turnover; wide-spread, low-volume items can lock capital.
- **Unrealized profit ≠ cash**: goods sitting in sell orders don't pay for fight consumables until sold.
- Liquidity falls with rarity; at high rarities prices between similar items vary a lot.
- Keep a liquid reserve (~500 money before a respec or for emergencies).
- Diversify stock; don't depend on one product or one bonus region.

## Cases — expected value (F-CASE-EV) `[RULE]` method

`EV = Σ P(drop) × value(drop)` (market or scrap value). Price < EV → opening is profitable **on average** but volatile;
price > EV → selling is usually better. Elite cases have high value — compute separately. No absolute "always open/sell"
rule: recompute with current prices.
`python scripts/economy_calculator.py case-ev --drop name:prob:value ... --case-price P`

`[OBS]` At the time the community guides were written, opening ordinary cases was slightly profitable, but EV minus price was
only ~0.1–0.3 money — selling directly is a perfectly valid choice.

Regular case odds (weapon share `[LIVE]`, rarity `[WIKI-ONLY]`): 30% weapon / 70% equipment; rarity 62 / 30 / 7.1 / 0.85 / 0.04 / 0.01% (common → mythic). Weight each
outcome by the market price of a typical item of that slot/rarity for EV. Elite case odds: community table only, uncommon →
mythic 50 / 32 / 15 / 2.5 / 0.5% `[CODEX]` ([battle-loot.md](battle-loot.md)).

Scrap floor: an unopened regular case is worth ≈ **14.7 scrap** dismantled on average (elite ≈ 70 with the community table). When
the case price sits near 14.7 × scrap price, opening is a variance bet, not an edge `[CODEX]` (mid-2026 observation).

Opening animation: a reel stops on the item won; opening ten spins several reels.

**Wooden cases** are a separate type: they give resources (not equipment), have better odds than a battlefield case, and can
be sold on the market — see [map-and-travel.md](map-and-travel.md). From v0.27 their value depends on rarity (Common 20–40 …
Epic 160–260 PP), so price them by rarity. `[SCHEDULED]` When movement is turned off (~2026-11-10, v0.28) every wooden-case
listing returns to its seller and every wooden-case buy order is refunded; held cases can still be opened.

**v0.27 market effects** `[Derived]`: wages are priced from a **PP value** computed from raw-material trades over the last 7 days, so
raw-material prices now set every employer's payroll. Wages are also a money sink, and the admin has said they will tune money
inflow to avoid deflation. Expect raw-material and payroll costs to move together while that settles. Tools and toolboxes can't
be traded.
