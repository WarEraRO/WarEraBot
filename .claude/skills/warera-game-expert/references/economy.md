# Economy — how value is created

## Economic bars `[VERSIONED]`

**Until v0.27** `[RULE]`:

| Bar | Spent by | Produces |
|---|---|---|
| **Energy** | working as an employee in someone else's company | net wage for you + PP for the employer |
| **Entrepreneurship** | self-work in your own companies | PP with no wage; "no income tax" per the guide, but v0.27 says a self-work tax existed (U-V27-2) |

**From v0.27** `[RULE]` (2026-10-26): **Entrepreneurship is removed** (points refunded) and **Energy** is the only economic
bar: **100 + 10 per level** (was 30 + 10). It pays for **self-work** (10 per action, **30 + 3 per Production level** PP, was 10 + 3),
**hiring** (10), **new candidate sets** (10, doubling) and **training** (10 per draw). The job market is gone, so Energy no longer
earns a wage; the only way to work for another player is a manager job, paid per Management point. The self-work tax is gone.

A third bar, **Stamina**, is only for travel and does not affect production ([map-and-travel.md](map-and-travel.md)); it is
removed with movement about 2026-11-10 (v0.28).

Mechanics `[LIVE]`: each work action spends **10** points of the bar (`economy.bar_cost_per_action`) and yields PP equal to
your **Production** skill value. Bars regenerate **10% of max every hour on the hour (UTC)**, i.e. 2.4 full bars per day —
the origin of the guide's 2.4 factor `[INFER]`. v0.27 doesn't mention regen, but the live v0.27 client still has
`regenDividedBy: 10` (2026-10-26) `[LIVE-CLIENT]`, so 10% per hour holds (U-V27-15). In that client Production is itself a bar
(`isABar`) whose value is the PP of one session.

Each work action rolls **±10%** on the PP produced `[CODEX]` (Economic Skills Mechanics Guide, 2026-06-18); employees' hourly
output rolls the same ±10% `[LIVE-CLIENT]`. Expected values are unaffected; single actions vary.

## Production points (PP)

PP are the unit of production. Sources per company:
1. **Automated Engine** — passive, `level × 24` PP/day before bonuses ([companies.md](companies.md)).
2. **Self-work** — `bar/10 × Production × 2.4 × (1 + bonus)` PP/day; the bar is Entrepreneurship until v0.27, then Energy
   (shared with hiring and training).
3. **Employees** — until v0.27 player workers (each action yields their Production PP; you pay the wage per PP). From v0.27 hired
   employees produce **Production ÷ 4 PP every hour** on their own and are paid an automatic hourly wage
   ([employees-and-wages.md](employees-and-wages.md)).

*Derived (v0.27, regen unchanged):* a level-0 Energy bar of 100 gives 24 self-work actions a day × 30 PP = **720 PP/day** before
bonuses (was 30/10 × 2.4 × 10 = 72 with Entrepreneurship 30 and Production 10). Every hire, reroll or training draw costs one action's worth.

PP are turned into items by the company's recipe ([production.md](production.md)). The **production bonus** of the company's
region/country multiplies output ([production-bonuses.md](production-bonuses.md)); from v0.27 those regional bonuses are gone and
only employee modifiers remain.

Storage caps accumulated PP; **when storage is full, engine, self-work and employees all stop adding PP** `[RULE]`.

## Profit thinking `[RULE]` formulas, `[STRAT-RO]` framing

- Ask "which product gives the highest **net value** in the current context?", not "which has the highest price?".
- Distinguish **accounting cost** (cash paid) from **opportunity cost** (market value of inputs you already own).
  Raw material you produced yourself is **not free**: it could have been sold. Turning 10 iron into 1 steel earns the
  steel price **minus the market value of 10 iron**.
- Use the realistically achievable sale price (conservative for low-volume goods), not the top listed price.
- Formulas: [formulas.md](formulas.md) F-PROFIT, F-BASE-PER-PP, F-MAXWAGE, F-BREAKEVEN.
- Calculators: `scripts/economy_calculator.py`, `scripts/break_even.py`.

## Economic development path `[STRAT-RO]`

1. Points into economic skills until ~level 15 ([skills-and-respec.md](skills-and-respec.md)).
2. Build companies toward **6 companies with Automated Engine level 5** (community "best starting point").
3. Then keep upgrading and, if points allow, add company 7+.
4. Sell rare+ gear you don't use and reinvest in companies, engines/storage and liquidity.
5. Prefer high-volume goods (iron, limestone, steel, concrete) for liquidity.
6. Don't hire employees too early — hire only when you can compute the max profitable wage and fund several salaries.
   *(Pre-v0.27 advice about player wages; from v0.27 use the employee margin formula in employees-and-wages.md.)*
7. Watch #economic-orders before moving or switching production.

Steps 1–3 predate v0.27, which makes Energy the economy skill that matters most (self-work, hiring and training all draw on it)
and removes Entrepreneurship. Re-check the path against the new economy.

## Taxes and country economy

- Job market is sorted by **after-tax** wage; taxes affect offer attractiveness `[RULE]` (until v0.27).
- Country max tax 45 `[LIVE]`. Live-only key `region.citizenIncomeTaxPercent` = 30 = the share of a foreign worker's tax that
  returns home (U-ECO-8; moot from v0.27, when the job market goes).
- **From v0.27** `[RULE]` (`country.taxes`): the **income tax** is taken on employee wages, a new **manager tax** on manager
  pay (it starts at the income tax); Congress votes both; the self-work tax is gone. **Each 1% of income tax costs employees 1
  happiness (−1% output)**, so a high tax now taxes production too. Conquered regions give the original owner **10%** of the
  income tax.
- Each region yields its country money per day equal to its **development** ([regions-and-buildings.md](regions-and-buildings.md)).
  From v0.27 every region shows a **daily income estimate**, and a Daily revenue map mode exists.
- A country needs ≥10 citizens to send/receive money (bounties and contracts excepted) `[RULE]`.
- **v0.27 note from the admin**: employee wages are a new, large **money sink** that grows as employees are trained and companies
  fill up. The admin will adjust how much new money enters the game over the following weeks to avoid deflation, so expect
  further economy changes.
