# Missions

Data: `data/progression-values.yaml#missions`, mechanic IDs `missions.*`.

## Sets and rewards `[RULE][LIVE]`

| Set | Missions | XP each | Set bonus (≥7 completed) | Max XP | Resets |
|---|---|---|---|---|---|
| Beginner (one-time) | 25 | 50 `[LIVE]` / 100 `[GUIDE]` `[CONFLICT]` | 500 XP `[LIVE]` / 2,000 XP `[GUIDE]` + 50 money + 5 cases, at 18/25 `[GUIDE]` | — | never |
| Daily | 10 (random) | 10 | 100 XP + 10 money + 1 case | 200 | 00:00 UTC |
| Weekly | 10 (random) | 50 | 500 XP + 30 money + 3 cases | 1,000 | Monday 00:00 UTC |
| Monthly | 10 (random) | 100 | 1,000 XP + 50 money + 5 cases | 2,000 | 1st, 00:00 UTC |

**Mid-period start** `[RULE]`: a set received mid-period starts partially complete (official example: a monthly set
received on 22 August starts at 21/31 of each target). Initial progress stops one step short of completion, so no mission
is born complete. Same for weekly sets.

## Beginner missions `[RULE]`

All 25 are available from level 1, never reroll, never reset; new ones are added to old accounts automatically. Level
ladder: reach level 5 / 10 / 15 / 20 / 25. Others named by the guide: upgrade a company; upgrade skills 5 times; create a
new company; open chat; join an MU; send 1 message; like 1 message; set profile picture; reach military rank 5 / 10 / 20;
join a party; vote in an election; reset your skills; earn any badge; find a job; set your username. (3 of the 25 are not
named in the source `[GAP]`.) From v0.27, "find a job" = take a manager job, which needs level 10; joining a party needs level 15
(the menu appears then); and the v0.27 free skill reset completes "Reset your skills" at no cost `[Derived]`.

`[STRAT-RO]` Do "Reset your skills" when you respec anyway or have a free respec (e.g. after Prestige) — not with a paid
reset just for the mission. "Vote" needs vote eligibility (level 20 live).

## Mission pools (daily / weekly / monthly)

See `data/progression-values.yaml` for the full lists. Notable:
- Damage missions (total, for allies/country, on orders), hit counts, participate in N battles.
- Economy: work for an employer, work in own companies, produce, earn from sales, buy from market, donate, craft, open cases.
- Map: travel to another region N times, collect on the map, **Move somewhere**, **Collect a wooden case** (all periods).
  Travel is counted in regions crossed; km-based missions no longer exist `[DEPRECATED]`. `[SCHEDULED]` v0.28: once movement is
  off (~2026-11-10) these are **replaced by other missions** (which ones isn't stated `[GAP]`, U-V28-6). Until then, one trip to
  a wooden case can serve the travel mission, the case mission and the Cross regions milestone at once *[Derived]*.
- Monthly-only: use 1–3 Pills (by level, from level 5); move a company (costs 5 concrete); eat N steaks.
- **v0.27 changes** `[RULE]` (2026-10-26): new missions **train an employee**, **resolve an event** and **care for an employee**
  (managers); **self-work counts** for the work mission; "Find a job" (beginner) now means **taking a manager job** (manager job
  market from level 10); the **move company mission is gone**. Which pools (daily/weekly/monthly) get the new missions isn't stated `[GAP]`.

## Rerolls `[RULE][LIVE]`

- Any daily/weekly/monthly mission can be replaced (dice button). **First reroll per category per period is free**; the
  k-th costs **2 × (k − 1)** money (config table: index n costs 2n, n = 0…20, i.e. max 40; beyond index 20 unknown).
- A reroll can return the same mission.
- Run `python scripts/progression_calculator.py reroll --done <used> --count <k>`.

## Decision rule `[STRAT-RO]`

Order of work: (1) free or near-free missions → (2) missions completed naturally by your normal play → (3) small,
justified investment → (4) **reroll** missions that are too expensive or don't fit your build.

Reroll when `cost of resources to complete > reroll cost` (often the first, free reroll). Typical Economy-player mistakes:
- eating expensive food or firing expensive ammo just for XP;
- large damage missions in Pill debuff or without an order;
- paying oil for a travel mission when Stamina regenerates anyway (10/h);
- crafting common gear for a mission when the reroll is free.

Example: "Move a company" (monthly) costs 5 concrete — only worth it if the move is justified by a better production
bonus anyway; otherwise compare with a reroll. (Removed in v0.27.)

## Claiming and resets `[RULE]`

- No auto-claim: missions, set rewards and Milestone tiers each have their own claim button (v0.25.5, 2026-08-29). Between
  v0.25.1 (2026-06-14) and v0.25.5 mission XP auto-claimed; v0.25.5 turned that off again (`missions.claiming`).
- At reset the board is regenerated **first**, then the claimed flag is cleared — an unclaimed set bonus of the ended period
  is lost. Before each reset, check: no easy mission left, expensive ones rerolled, everything claimed (incl. the 7/10 bonus).
- Live reset timestamps: `gameConfig.getDates` (daily/weekly/monthly `*MissionRegenAt`).
- v0.27.4 fix (2026-11-02): coming back after a break now lets you generate a **fresh set**; before, the previous set could stay
  stuck with its reward already used, "sometimes for a whole month". Donate missions are tagged on the Country and MU buttons.
  Employees of a disabled company no longer count toward training missions.
