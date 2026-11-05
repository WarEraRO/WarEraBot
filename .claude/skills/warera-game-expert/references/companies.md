# Companies

> **v0.27 (live since 2026-10-26)**: companies run on hired employees
> ([employees-and-wages.md](employees-and-wages.md)); the Break Room returns with 1–3 employees (3 is the top level in the live
> config); deposits and country specialization are gone (`region.depositsEnabled` false), so location matters only through the
> **+5% core-region** employee bonus and taxes; everyone gets **1 free company move**; changing the product no longer needs an
> empty storage. The Automated Engine and Storage tables didn't change in the live config of 2026-10-26 `[LIVE]`.

## Creation and limit `[RULE][LIVE]`

- Every player gets **one free company producing a random raw resource** on joining (v0.17.1; an older wiki page says grain).
  From v0.27 the first company is **always Iron**, and the guided second company is **Steel** by default.
- The k-th company costs `100 + 50 × (k − 2)` concrete for k ≥ 2 (2nd 100, 3rd 150 … 12th 600).
- Max active companies = **2 + Companies skill level** (0→2, 10→12). The guide's table "skill points needed: 1…10 for
  companies 3…12" is the **Companies skill level**; the cumulative skill-point cost is n(n+1)/2 `[INFER, consistent with LIVE]`.
- Companies above the limit are **deactivated at random, not deleted**, and reactivate automatically when the limit returns;
  you can (de)activate manually.
- `python scripts/progression_calculator.py company --k 7` → 350 concrete, Companies skill 5 (15 points).

`[STRAT-RO]` On a fight build keep ~4–6 active companies: more companies raise passive income but cost economic skill
points, opportunity cost and management time.

## Upgrades `[RULE][LIVE]`

### Automated Engine (passive PP)

| Level | Steel | PP/day (before bonus) |
|---|---|---|
| 1 | free | 24 |
| 2 | 20 | 48 |
| 3 | 40 | 72 |
| 4 | 80 | 96 |
| 5 | 160 | 120 |
| 6 | 320 | 144 |
| 7 | 640 | 168 |

`PP/day = level × 24 × (1 + bonus)`; since v0.27 the engine gets **no production bonus** (U-V27-7, closed by the user), so
`level × 24`. Since v0.27.4 an employee with the **Talks to Machines** trait doubles it while it is the company's only employee
(roster `hourly.engineMultiplier`; [employees-and-wages.md](employees-and-wages.md#after-v0274-derived)). Live config also lists construction points (L7: 680, breaking the doubling pattern —
real, don't "fix") and a 6 h pending duration.

### Storage

| Level | Steel | Capacity (PP) `[LIVE]` |
|---|---|---|
| 1 | free | 200 |
| 2 | 10 | 400 |
| 3 | 20 | 600 |
| 4 | 40 | 800 |
| 5 | 80 | 1,000 |
| 6 | 160 | 1,200 |
| 7 | 320 | 1,400 |

Needed when daily production exceeds capacity (`[STRAT-RO]` level 2 early) or for hiring (`[STRAT-RO]` level 5 for 2
employees). **Full storage stops all production.** `python scripts/economy_calculator.py storage --level L --stored S --daily-pp P`.
From v0.27 a full storage also **lowers employee happiness**.

### Break Room `[VERSIONED]` (`company.break_room_levels`)

| | Until 2026-01-09 `[DEPRECATED]` | 2026-01-09 → v0.27 | From v0.27 `[LIVE]` (config 2026-10-26) |
|---|---|---|---|
| Effect | max player workers / daily hires | **no Break Room** (removed by v0.22.0, steel refunded) | max **employees** |
| Levels | L1 2, L2 4, L3 6, L4 8, L5 10 | — | L1 **1**, L2 **2**, L3 **3** (higher levels not mentioned) |
| Steel | 0 / 10 / 20 / 40 / 80 | — | 0 / **20** / **80** |

The live config still lists the old L1–L5 table (`upgradesConfig.breakRoom`); it's a legacy key until v0.27 reuses it.
Since v0.22.0 the **Management** skill caps the total workers across companies (2 → 12, doubled to 4 → 24 on 2026-01-26;
U-ECO-4). From v0.27 Management gives
+2% employee production per point instead, and daily candidates are fixed at 3 per company.

### Refunds

Downgrade/demolition returns **80%** of invested materials `[RULE][LIVE]` — avoid impulsive decisions.

## Cheapest +1 PP/hour first `[STRAT-EXT]` (pre-v0.27; *WarEra Infrastructure Guide*, 2026-01-17, via `[CODEX]`)

Engine and storage costs double per level while a new company costs only +50 concrete more each time, so the cost-efficient
order is "always buy the cheapest next +1 PP/hour", alternating engine upgrades and new companies. Community stopping points:
**8 companies at engine 6** for fighters, **12 companies at engine 7** for pure economy players. Written for the job-market economy;
from v0.27 also weigh Break Room steel and the employee payroll per company.

## Recommended build order `[STRAT-RO]`

The community infographic (not available as text `[GAP]`) leads to **6 companies with AE 5**. Steel and concrete cost about
the same — don't let one price dictate the upgrade order. Pick industry and location with a good-selling product and a
regional bonus of at least ~30% (industry-dependent). *From v0.27 regional bonuses no longer exist: pick a core region of your
own country (+5% for employees) with a reasonable tax.*

> These build orders predate v0.27. They don't account for Break Room upgrades, employee wages or Energy spent on hiring and
> training, and "don't hire early" was about player wages. Re-check them once v0.27 is live.

`[STRAT-EXT]` BuhDeuce's guide (source BUHDEUCE), "follow blindly":
- **First 4 companies:** limestone → concrete → iron → steel, to be less dependent on the market. Companies 5+ are free choice (ammo or food for war, or more construction items, which "earn the most").
- **Start:** company 1 to AE3 → build #2 → #2 to AE3 → build #3 → companies 1–3 to AE4 → build #4, #5, #6, each to AE4 → all six to AE5.
- **War path:** upgrade the six to AE6 and stop, since companies above a fight build's cap get disabled. The user called it optional, being the minimum for fighters (2026-10-25).
- **Economy path:** build to 10 at AE5 → all to AE6 → #11 and #12 at AE6 → all to AE7. That reaches 12 companies (Companies skill 10) at AE7, both game maximums. The user's goal for the bot is this, by level 50.
- **Also:** an upgrade for a full storage takes priority (a full storage wastes the company). Don't hire employees early.

The bot's `/progression` implements both paths (warerabot-dev skill).

## Move a company / change product `[RULE][LIVE]`

| Action | Cost |
|---|---|
| Move to another region | 5 concrete |
| Change produced item | 5 concrete |
| Both (usual for a product switch) | 10 concrete |

The move window lists recommended regions with the **deposit's remaining time**, the **production bonus**, and the
**employee tax**. Deposit bonuses vary (20–40% per guide), so read the real value on the region page or production tooltip.
Moving a company does **not** move you, and your own travel does not move companies.

**From v0.27** `[RULE]`: deposits are off and strategic resources no longer boost production, so a move can't chase a
bonus. The admin's stated goal is to end the "move your company to the best region" meta: a company does best **at home**
(+5% for employees in your country's core regions, and its taxes fund your country). Everyone gets **1 free company move** to
bring companies home. Employees lose happiness for 7 days when the company moves (−10 in the live client; −5 when an employee
moves between companies; U-CDX-5). The move-company mission is removed.

Decide with break-even ([formulas.md](formulas.md) F-BREAKEVEN): `python scripts/break_even.py ...`. Switch product only
when the deposit expires/bonus drops, the price falls below a competitive base/PP, #economic-orders asks for it, or
break-even is shorter than the expected duration of the new advantage. `[STRAT-RO]` Don't switch on one day's price.
*From v0.27 a product switch also resets the same-good streak (+1%/day, max +20%) `[Derived]`; count that lost bonus in the break-even.*

## Operational rules `[RULE]`

- Press **Produce** regularly; never let storage fill. "Produce all" is a premium (supporter) feature `[WIKIPATCH v0.16.3]`,
  shown from level 7 from v0.27.
- Switching a company from a raw to a finished product requires emptying production first (v0.15.8). **v0.27: changing what a
  company produces no longer needs an empty storage.**
- If the owner can't pay a wage, the employee's work session fails and generates no PP. **v0.27:** wages are hourly and
  automatic; if you can't pay the full hour, nobody works that hour.
- Keep liquidity for wages.
