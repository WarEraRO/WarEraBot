# Country treasury and donations

## What the treasury pays for `[RULE]`

Alliance upkeep, Defensive Pacts, Main Enemy, paper for laws and orders, oil for buildings (bunkers, bases, pacification
centers), bounties, contracts and foreign aid. Income: each region yields money/day equal to **twice** its development (since
v0.27.2; equal to it before); taxes; donations.
A seemingly big treasury can vanish fast in a long war.

## Income sources `[RULE]` (development income and donations per guide; tax splits and ethics `[WIKI-ONLY]`)

Region development (1 coin per point per day; **2 since v0.27.2** `[VERSIONED]`, see below) · income tax on wages paid in your
regions (1–45%) · market tax on equipment bought by your citizens · 30% of the taxes your citizens pay when working abroad · donations (citizens only) · region sales · trading.
Ethics: Imperialist +10% / Fanatic Imperialist +30% tax income; Republican +50% / Fanatic Republican +150% development income
(core regions only). Occupied core regions still send part of their income/tax to the core country by resistance.

**From v0.27** `[RULE]` (2026-10-26):
- **Taxes**: income tax on **employee wages** and a new **manager tax** on manager pay; the self-work tax and the foreign-worker
  share (no job market) are gone. Each 1% of income tax costs employees 1 happiness, so a high rate cuts the country's production.
- **Conquered regions** give the original owner **10%** of the income tax. **Unlinked regions** pay full development income.
- **Strategic resources** pay whoever holds them a daily income equal to the development of their original country.
- `[VERSIONED]` **v0.27.2 (2026-10-28) doubled both** `[LIVE]` (config `region.developmentIncomeMultiplier` and
  `strategicResourceIncomeMultiplier`, both 2): a region pays **2 coins per development point per day**, and a strategic
  resource pays **2 × its original country's core development** per day. Both are paid hourly (the API's region `income` fields
  are per hour; the UI multiplies by 24). Government types apply on top: a Republic core region pays 4 per point, a Nationalist
  State region 1.4; a Plutocracy's strategic resource pays 3 × core development `[LIVE]` (API sample 2026-10-29).
- **Government types** replace the ethics above: Republic ×2 development income (own regions only), Nationalist State ×0.7,
  Autocracy ×1.25; Plutocracy ×1.4 payroll and manager taxes (the extra is paid by the game) and ×1.5 strategic resource income,
  but it can't send money to another country. Federation halves alliance and pact upkeep. See [government-types.md](government-types.md).
- *Derived:* the admin wants companies **at home**. Every company moved back raises the home country's wage and manager tax income,
  which is why everyone gets a free move.

## Rules `[RULE]`

- Donation min level 5 `[LIVE]`.
- Sending money between countries `[CONFLICT]`: the guide says a country needs **≥ 10 citizens** (bounties and contracts exempt); the
  wiki says the Transfer Money law needs the **receiving** country to have **5 active eligible law voters**, and patch v0.15.1 said
  5+ possible voters in both countries. Only citizens can donate to their own country.
- Repeated donations of money/resources to an MU or country **to advantage someone** can be treated as **boosting**
  ([account-rules-and-security.md](account-rules-and-security.md)).
- Donation milestone ladder: "Donate __ money to MU or country".

## Donating to the country `[STRAT-RO]` / `[POLICY-RO]`

- Small, steady donations beat big ones that later force you to ask for help.
- Internal example: at 100 money/day income, donating 10/day can be sustainable; adapt to your build and reserves.
- Economy players fund fighters; when they switch to fight they benefit from bounties and infrastructure.
- Use the donation ranking for transparency, not social pressure.

## Donating to an MU — priority order `[POLICY-RO]`

1. Oil for the HQ during the planned window.
2. Paper for orders that multiply every member's damage.
3. Buffer for contract acceptance fees.
Set a predictable voluntary contribution or autonomy target, not chaotic requests before every tick.

## Verification and records `[POLICY-RO]`

Donate only to official entities and verify the destination before transferring. Track with `/top_user_weekly_donations` and
toolbox.warera.wiki Transaction Explorer (filters, CSV/XLSX export, audit).

## When the treasury can't pay (Scenario D) `[POLICY-RO]`

Government publishes the situation and asks for sustainable (not panicked) donations; MoE may sell liquid assets; MoD may use
more efficient contracts or minimum rates; fighters with own resources keep fighting to orders; economy players fund the
treasury and benefit next cycle.
