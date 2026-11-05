# Player progression

## Levels and XP

- Level cap **50** `[RULE][LIVE]` (`progression.level_cap`). Reaching level 50 requires **86,600 total XP** `[RULE]`.
- **XP table** (from the wiki, **verified against the guide**: sums exactly to 86,600 and reproduces the Prestige examples; data/progression-values.yaml#xp_table): XP needed to go from the previous level —
  L2–4: 100 each · L5–7: 200 · L8: 300 · L9: 400 · L10: 500 · L11–24: 600 → 1,900 (+100 per level) · L25–30: 2,000 · L31–40: 2,500 ·
  L41–50: 3,000. Cumulative: L10 = 2,100 · L15 = 6,100 · L20 = 12,600 · L25 = 21,600 · L30 = 31,600 · L40 = 56,600 · L50 = 86,600.
  `python scripts/progression_calculator.py level --total-xp X`.
- Total skill points = **4 × level** (4 at level 1) — see [skills-and-respec.md](skills-and-respec.md). Maxing every skill costs 715 points (13 × 55) since v0.27.3; 770 (14 × 55) before.
- Lifetime XP is tracked separately from current XP; Prestige does not erase it.

## XP sources

| Source | XP | Reference |
|---|---|---|
| Beginner missions (one-time) | per mission 50 `[LIVE]` / 100 `[GUIDE]` `[CONFLICT]`; set bonus 500 `[LIVE]` / 2,000 `[GUIDE]` | [missions.md](missions.md) |
| Daily missions | 10 each, +100 set bonus at 7/10 → max 200/day | [missions.md](missions.md) |
| Weekly missions | 50 each, +500 at 7/10 → max 1,000/week | |
| Monthly missions | 100 each, +1,000 at 7/10 → max 2,000/month | |
| Milestones | 10 × tier, capped at 100 (partial data) | [milestones.md](milestones.md) |
| Daily login | 10 per day | [daily-rewards.md](daily-rewards.md) |
| Comeback reward | 150 / 400 / 800 | [daily-rewards.md](daily-rewards.md) |
| Prestige bonus | +50% (+10 pp per further Prestige), off while at level 50 | [prestige.md](prestige.md) |
| Live-only config keys | `user.xpPerAction` = 10, `user.dailyXp` = 100 — semantics not documented `[GAP]` | |

**The repeatable XP clock** *Derived* (reproduces the codex's figure `[CODEX]`): daily 200 + weekly 1,000/7 + monthly
2,000 × 12/365 + calendar 10 ≈ **418.6 XP/day** at full claims. From zero that is ~207 days to level 50 (86,600 XP); one-time
sources (beginner missions, v0.27 guides, milestone tiers, comeback rewards) shorten it but aren't a rate. Before v0.25.5 (weekly
10 × 30 + 300, no monthly set) the clock was ~286 XP/day. A community census of 15,920 accounts (2026-08-18, before the monthly set)
found no other repeatable XP source `[CODEX]`.

History: a **double XP and double regen weekend** ran on 2025-08-16/17 (admin announcement, 2025-08-10), so XP and level data from
that weekend aren't typical.

## The Progression menu `[RULE]`

Two tabs: **Missions** (periodic) and **Milestones** (permanent). Nothing auto-claims:

- a badge counts every completed-but-unclaimed mission, available set reward and claimable Milestone tier;
- the indicator clears only when you claim (claiming on another tab/device clears it everywhere);
- the Progression link opens the tab that has something to claim.

Profiles show two read-only tabs (Missions, Milestones), visible on other players' profiles too, with totals: missions
claimed, Milestone tiers claimed, and XP earned from both. Two leaderboards exist: **Missions collected** and
**Milestone Tiers**.

## Level gates that matter

| Gate | Level | Source |
|---|---|---|
| Donate | 5 | `[LIVE]` |
| Monthly "use pills" mission | 5 | `[GUIDE]` |
| Write article / tip | 5 | `[LIVE]` |
| Market | 7 → **5** from v0.27 (trading too) | `[LIVE]` (v0.27 config) |
| Military units (menu) | **5** from v0.27 | `[LIVE]` (v0.27 config) |
| Premium Produce all, Open all cases, bulk dismantle | **7** from v0.27 | `[LIVE]` (v0.27 config) |
| Chat | 8 → **1** from v0.27, with a slow mode until 15 that loosens at 5 and 10 (commenting too) | `[LIVE]` (v0.27 config) |
| Active citizen | 10 | `[LIVE]` |
| Crafting | 10 from v0.27 → **7** from v0.27.4 (2026-11-02) | `[VERSIONED][LIVE]` (config `featureUnlockLevels.craft`) |
| Manager job market, military skills (menu) | **10** from v0.27 | `[LIVE]` (v0.27 config) |
| Parties, workforce chart | **15** from v0.27 | `[LIVE]` (v0.27 config) |
| Run as candidate | 15 → **20** from v0.27 | `[RULE][LIVE]` (v0.27 config) |
| Vote | **20** `[LIVE][WIKI]` (5 from 2025-05-28; later 15; now 20) + ≥7 days since citizenship change, waived during a new country's first 14 days (v0.27.4) | `[VERSIONED]` |
| Contribute to resistance / unrest / construction | 15 | `[LIVE]` |
| Take control of an empty country | 25 | `[LIVE]` |
| Prestige | 50 | `[RULE][LIVE]` |
| Skill unlocks | see [skills-and-respec.md](skills-and-respec.md) | `[LIVE]` |

v0.27 menus "appear as you level" (`progression.unlock_levels`). Players already in an MU, a party or a job keep access.

## Fresh start (v0.27) `[RULE]`

- Shorter tutorial: **6 guides** (Economy, Gear, Military, Social, Progression, Map), each worth **50 XP and a Case**; skip, resume
  or replay from the Guides tab in Progression; already-done steps count. The Economy guide teaches hiring, the Break Room, staffing a
  second company and training.
- **Starting bag** (`progression.starting_bag`): money 5 → 25 → **100** (`[VERSIONED]`: 25 from v0.27, 100 since v0.27.2,
  2026-10-28), concrete 50 → **100**, oil 20 → **150**. First company always **Iron**, second **Steel** by default.
- New **employee milestones** and missions: see [milestones.md](milestones.md) and [missions.md](missions.md).

> Election note `[OBS]`: Milestone XP stays unclaimed until you press the button, so players can bank XP and jump several
> levels right before an election. Election officials should expect levels to change overnight.

## Inactivity `[CONFLICT]`

A player is "inactive" after **3 days** without login `[LIVE]` (7 → 3 days in v0.15.1, 2025-05-04; the guide's "4 days" matches the
Impeach Congress Member requirement of last login > 4 days instead). Missing days loses mission XP: up to
200/day, 1,000/week, 2,000/month. Country takeover requires inactive government **and** congress — see
[government.md](government.md).

## Referrals and badges `[RULE][LIVE]` (amounts verified against config; badge descriptions `[WIKI-ONLY]`)

- Choose a referrer while at level ≤ 10 (can't change it). New player gets **10 coins**. When the referral reaches level 15 the
  referrer gets a Referrer badge (**20 coins**) plus **10% of all badge income** that referral earns. Every 10 referrals reaching
  level 15 → **Baby Boomer** badge (100 coins).
- 29 badges exist. Money rewards per live config: Battle Hero (top 1 damage in a battle) 10, Round Hero 5, Conqueror/Top of the
  Hill (top 1 terrain in battle/round) 10/5, Hard Worker (work 100 times) 5, Referrer 20, Baby Boomer 100, tournament winners 50.
  President and Government Member badges have a 20-day cooldown. Others: Voter, Congress Member, Vice President, Support/Support
  Gift/Sugar Daddy (supporter plan), Community, Game Supporter, Exploit Finder, Bug Finder, Prestige, Alpha Tester (before
  2025-03-20), Reset Survivor, Founding Father, Giveaway Winner, Popular Article (2% of active population, min score 10), Translator.
- Weekly ranking rewards `[WIKIPATCH v0.17.1, 2025-08-21; may have changed]`: tiers Master (top 1%), Diamond (5%), Platinum (20%),
  Gold (40%), Silver (60%), Bronze; cases by tier for user, MU, country and country-per-citizen weekly damage.
