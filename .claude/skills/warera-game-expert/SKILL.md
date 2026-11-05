---
name: warera-game-expert
description: Domain expert and reasoning system for the browser game WarEra - version-aware mechanics, formulas, calculators, and Romanian community strategy/policy, kept separate from game rules. Use for any WarEra gameplay question or decision - economy (companies, employees and managers, production, wages, taxes, market, crafting, cases), combat (skills, builds, equipment, pills, battles, damage bonuses, orders, loot, bounties, mercenary contracts), progression (missions, milestones, Prestige, respec), map/travel, military units, tournaments, regions, resistance, unrest, diplomacy (alliances, pacts, Main Enemy, NAPs), government and government types, elections, proxies, account rules - and whenever interpreting WarEra game data, API or script output, computing profitability, break-even or bonus totals, or asking what a mechanic was on a given date or patch. Not for generic economics, gaming or programming questions unrelated to WarEra. For writing API-calling code use warera-api; for raw gameConfig constants use warera-config.
---

# WarEra game expert

A maintained knowledge-and-reasoning layer for WarEra. It separates **what the game does** (mechanics),
**what the Romanian community recommends** (strategy/policy), and **what is true right now** (live state),
and keeps the history of every changed value.

- Built from *Ghidul Complet al Jucătorului Român WarEra [v0.26.1]* (2026-09-30), cross-checked against the live `gameConfig`
  (sibling skill `warera-config`, mirrored at warera.realmarijn.nl; re-checked 2026-10-05). Gaps filled from **warera.wiki**, which is
  **outdated**: wiki facts are kept only when the config or guide agrees, otherwise labelled `[WIKI-ONLY]`. The wiki's transcribed
  official patch notes (v0.0.2 → v0.17.7, to 2025-10-04) and the in-game official articles (v0.15.0 → v0.27, all read 2026-10-25; v0.27.1 read 2026-10-27)
  provide dated history; **a newer patch overrides an older one where they overlap**. See [references/source-map.md](references/source-map.md).
- Enriched 2026-10-26 from the **UNIKHORNE codex** (warera.unikhorne.dev/codex, a third-party rules aggregator, `[CODEX]`) and
  checked against the **live v0.27 client bundle** (`[LIVE-CLIENT]`, read the same day).
- Employees deepened 2026-10-26 from **ten community v0.27 guides** (`V027_GUIDES`: Piraterer, Elereo, Wodkabouter, fish and
  others; dev-server screenshots → `[OBS]`, advice → `[STRAT-EXT]`). Each was checked against the live client's event
  definitions and in-game English text (`LIVECLIENT_V027_TEXT`), which settled the production-bonus stacking (additive), the
  training-card odds, the tool → goods map and the retirement event. Conflicts: G27-1 … 10 in unresolved-mechanics.md.
- Audited 2026-10-27 against **all 666 English Guide articles** (`GUIDE_ARTICLES`; about a quarter slop, 136 historical only, 21
  integrated; per-article ledger: [guide-articles-ledger.md](references/guide-articles-ledger.md)), the **v0.27.1** patch
  (`PATCH_0_27_1`), the live client of that evening (`LIVECLIENT_V0271`: government-type table verified) and the game's English
  UI catalog (`TRANSLATION_EN`, vatoutou/warera-translation: current labels, see [ui-guide.md](references/ui-guide.md)).
  Guide conflicts: G-ART-1 … 7 in unresolved-mechanics.md.
- **v0.27.2** (`PATCH_0_27_2`, 2026-10-28) integrated 2026-10-29 and checked against the live config, client and API
  (`LIVECFG_V0272`, `LIVEAPI_20261029`).
- **v0.27.3** (`PATCH_0_27_3`, 2026-10-29) integrated 2026-10-30 and checked against the live client, config and 60 rosters
  (`LIVECLIENT_V0273`, `LIVEAPI_20261030`).
- **Silent patch of 2026-10-31** (no article; reported by community article `6ae682c7470184738824c070`, `SILENT_20261031`)
  integrated 2026-11-01 and confirmed by the live client, UI catalog history and 60 rosters (`LIVECLIENT_20261101`, `LIVEAPI_20261101`).
- **v0.27.4** (`PATCH_0_27_4`, 2026-11-02) integrated the same day and checked against the live client, config, UI catalog and 70
  rosters (`LIVECLIENT_V0274`, `LIVEAPI_20261102`).
- **v0.28** (`PATCH_0_28`, 2026-11-03) integrated 2026-11-04 and checked against the live config, client, UI catalog and region
  graph (`LIVECLIENT_V028`, `LIVEAPI_20261104`). Its second step (movement off) is scheduled for about 2026-11-10.
- Versioned values: [data/mechanics.yaml](data/mechanics.yaml) (149 mechanic IDs with history, sources, confidence, conflicts);
  patch event log: [data/patch-history.yaml](data/patch-history.yaml).

## Sibling skills (same repo)

| Need | Use |
|---|---|
| Write/review code that fetches WarEra data | `warera-api` |
| A raw config constant / exact config path | `warera-config` (live wins over this skill when semantics are clear) |
| How mechanics work, decisions, calculations, history, strategy, policy, interpreting data | **this skill** |

## 1. Authority model — never mix these

Every statement you make must carry one of these authorities (labels used throughout `references/`):

| Label | Authority | Example |
|---|---|---|
| `[RULE]` | Current game mechanic | Patriotic bonus +20% |
| `[RULE~]` | Game mechanic, approximate/qualitative value | Miss deals "about half" damage |
| `[VERSIONED]` | Value changed; history kept in `data/mechanics.yaml` | Vote min level 15 → 20 |
| `[SCHEDULED]` | Announced, not yet effective (needs `effective_from`) | v0.28: movement, Stamina and map wooden cases off ~2026-11-10 |
| `[DEPRECATED]` | Removed/replaced system ([deprecated-mechanics.md](references/deprecated-mechanics.md)) | km-based travel missions |
| `[STRAT-RO]` | Romanian community strategy — advice, not enforced | "Economy first until level 15" |
| `[POLICY-RO]` | Romanian internal policy — leadership decision | Bounty 0.05/1k, budget ~500 |
| `[STRAT-EXT]` | Non-Romanian community guide or calculator — advice, not enforced | BuhDeuce: limestone → concrete → iron → steel |
| `[OBS]` | Community observation/test — useful, not guaranteed | Adding resistance doesn't require being in the region |
| `[LIVE]` | Confirmed by live gameConfig (2026-10-04, re-checked 2026-10-05; v0.27 keys checked 2026-10-26; v0.27.2 keys 2026-10-29) or by values read from the live API with the bot's key | Break Room L1–L3 |
| `[LIVE-CLIENT]` | Read from the live game client bundle (v0.27, 2026-10-26): client-side constants, event definitions and in-game text only | Training-card weights 55/25/13/5/2 |
| `[CODEX]` | UNIKHORNE codex claim (community aggregator, Aug–Oct 2026) not independently verified | Elite case odds 50/32/15/2.5/0.5 |
| `[WIKIPATCH]` | Official patch note (via the wiki), dated — history only | Pill 24 h → 8 h on 2025-10-04 |
| `[WIKI-ONLY]` | Only the outdated warera.wiki says so — unverified, say so | Military rank table |
| `[CONFLICT]` | Sources disagree — see [unresolved-mechanics.md](references/unresolved-mechanics.md) | Alliance bonus 20 (guide) vs 10 (config) |
| `[GAP]` | Not established by any source | Exact damage formula |

Say it explicitly when it matters: *"This is a Romanian community recommendation, not a game restriction."*

## 2. Source priority and conflicts

1. Live game state / UI tooltip supplied by the user or trusted script output (incl. live `gameConfig` / warera.realmarijn.nl)
2. Newer official patch notes → 3. official docs → 4. latest guide (v0.26.1) → 5. older guides → 6. warera.wiki (outdated) and
   historical patch notes (history only) → 7. community estimates

- **Never average or silently merge** conflicting values. Report both, say which wins and why.
- Live config wins only where the key's meaning is unambiguous (e.g. `election.voteMinLevel` = 20). Where a key could be
  legacy/base (e.g. `battle.allianceDamagesBonusPercent` = 10 vs the guide's world-development curve), the mechanic is
  `disputed`: use the working value, **state the conflict**, and recommend checking the in-game tooltip.
- A single live observation (e.g. one region's +38% deposit) overrides the reference **for that calculation only**; it does
  not redefine the global mechanic.

High-impact conflicts to remember (full list: [unresolved-mechanics.md](references/unresolved-mechanics.md)):

> 2026-10-13: three user review passes closed many of these and more (see its "Session tracker", "Resolved with the user" and
> "Settled by the admin's official articles" sections). `data/mechanics.yaml` and the topic references are **not yet synced**
> with them: where they disagree, the unresolved-mechanics.md resolution wins. Pass-3 corrections that topic files still get
> wrong: **Move home** (100 concrete) relocates your home, while a **free trip home** exists every 12 h (U-MAP-1); the
> **alliance bonus** applies only when fighting for an ally, never in your own country's battles (I-4); **strategic
> resources** boost only the specialization item (U-ECO-12). (**Civil wars**, v0.26.2: no bounties, no country orders, no
> bunker bonus. Synced into the registry and topic files on 2026-10-25, CW-1.)
>
> 2026-10-14 (pass 4): the **milestone tier targets** (15 milestones × 20 tiers) are now known, in the "Milestone tier
> targets" table of unresolved-mechanics.md; [milestones.md](references/milestones.md) still calls them `[GAP]`. Per-law
> base paper costs are partly known (U-POL-6b); the impeach laws are incomplete. A Fanatic Pacifist country that revolts
> copies the occupier's bunker bonus (no doubling; not in civil wars). Closed as **permanently unknown**, so don't ask
> again: resistance `passive` 0.08, `define_enemy_country.maintenanceCost` 3 / alliance upkeep 1, and the dates in U-HIST-4.
>
> The game admin's articles (author `6813b758efecdf9bab195068`; fetch with `article.getArticlesPaginated {type:"last", userId}`)
> are the official patch notes and, per the user, the **most trusted source**, newest first. They cover v0.15.0 → v0.26.2
> (v0.26.2 = the untitled civil-war hotfix `6accd48eca2ce961eea235ff`, 2026-10-14). Titles often omit the version, so check
> whether a patch is integrated by article ID and topic, not just version string. **All official articles are ingested**
> (2026-10-25, registry sources `ADMIN_PATCHES` + `PATCH_0_25_1`); every version has a `data/patch-history.yaml` entry except
> v0.19.1 (no article). v0.25.1 exists only as a staff article in category `official` (`6a2d86d5ab0e47773095df00`), so search by
> `categories:["official"]`, not only by the admin's `userId`. **A newer patch overrides an older one where they overlap.**
> Corrected by that pass: break rooms are gone since v0.22.0 (2026-01-09); deposits last 1–5 days since v0.22.0; the ranking loot
> pool is gone since v0.24.1; the resistance tax hijack is gone since v0.25.1 (2026-06-14) until v0.27's 10%; hitting below 10
> Health is possible since v0.22.0.
>
> **v0.27 is live since 2026-10-26** (article `6ade08f7899288ce9f0bfe36`, registry source `PATCH_0_27`; `effective_from`
> 2026-10-26T14:00Z, the announced deploy time). **These are the current rules**: **hired employees** replace the job market
> ([employees-and-wages.md](references/employees-and-wages.md)); **government types** replace party ethics
> ([government-types.md](references/government-types.md)); Entrepreneurship is removed and Energy (100 + 10/level) pays self-work,
> hiring and training; deposits and specialization are off; strategic resources pay income instead of production bonuses; candidacy
> needs level 20; the map has 742 regions. Old → new list: [deprecated-mechanics.md](references/deprecated-mechanics.md). For a
> date before the deploy, answer with the version then in force (`wlib.resolve(id, date)`).
>
> **v0.27.2 (2026-10-28**, article `6ae2608f707baf45eebf26c5`, registry `PATCH_0_27_2`; checked live 2026-10-29): **region
> development income and strategic-resource income doubled** (config multipliers 2: 2 coins per development point per day;
> 2 × the original country's **core** development per resource; government types multiply on top; API income fields are per
> hour), new players start with **100 money** (was 25), and **32 incompatible trait pairs** (was 14) keep training from adding a
> clashing trait (existing clashes stay). Open points: "v0.27.2 ingest" in unresolved-mechanics.md.
>
> **v0.27.3 (2026-10-29**, article `6ae39f39b9d173140341a461`, registry `PATCH_0_27_3`; checked live 2026-10-30): **Leadership is
> merged into Management** (each Management level also moves training-card odds off Common and adds +2 to event checks; Leadership
> points refunded, one more free skill reset; 13 skills, 715 points to max); **Responsibility = +3 happiness per point** (no longer
> a loss shield); candidates show all stats and the wage, every hire has exactly one trait, and a new hire can't be fired for 12 h;
> transfers and firing cost no happiness; Luck counts from the first point in events (Luck × 4 / × 2); **Early bloomer** replaced
> Sprinter; Rehab removes only bad traits; Specialist matches the company's good. Old → new: [deprecated-mechanics.md](references/deprecated-mechanics.md);
> open points: "v0.27.3 ingest" in unresolved-mechanics.md.
>
> **Silent patch (2026-10-31**, no official article; reported by Piraterer's article `6ae682c7470184738824c070`, registry
> `SILENT_20261031`, confirmed live 2026-11-01): **Trainer** gives its coworkers **2 extra training sessions a day, shared** between
> them (one coworker can take both), refilling at 00:00 UTC; it was +1 for every coworker. **Lucky charm** gives +3 Luck to whoever
> works beside it **at 00:00 UTC**, kept until the next reset even after a transfer (API `charmLuck`); it was live for current
> coworkers. The article calls the Trainer change an abuse fix; moving either trait between companies (free since v0.27.3) no
> longer multiplies its effect *[Derived]*. Training hands now show their rarity and each
> card's estimated daily profit; a **Reorganize** workforce tool exists. Found in the same check: the **toolbox chance cap (2%/h) is
> gone since 2026-10-29** (unannounced). Open points: "Silent patch 2026-10-31 ingest" in unresolved-mechanics.md.
>
> **v0.27.4 (2026-11-02**, article `6ae8bb12bcc26a2f5712ec9d`, registry `PATCH_0_27_4`; checked live the same evening): employees
> **age one year per day worked or trained** (not per calendar day); a **disabled company** puts its employees on hold (no work,
> ageing or training); new trait **Talks to Machines** doubles the Automated Engine output while it is the company's only
> employee; **Bully** is a bad trait (53 traits, 36 incompatible pairs); training adds a free **Reroll** card (Uncommon), the
> **Wild card** is Rare and gives +2, and mixed traits are no longer taught; a tool that doesn't fit the new company returns to
> the inventory; employee **events were rebalanced** (most paid answers far cheaper, Van Race ×3, Gambling Debts ×2);
> **crafting unlocks at level 7**; during a **new country's first 14 days** its new citizens can vote at once.
> `[CONFLICT]` The article says trait Production now counts toward the "expected wage", but 82 live employees (4 recalculated
> after the deploy) still pay on base + trained only: keep treating trait Production as unpaid (U-V274-1). Open points:
> "v0.27.4 ingest" in unresolved-mechanics.md.
>
> **v0.28 (2026-11-03**, article `6aea1496b615c31fa0eb4152` "v0.28 (Nuking movement + perf)", registry `PATCH_0_28`; checked live
> 2026-11-04): **you fight in any battle from wherever you are**: no position, Move button or travel cost (config
> `battle.locationGateEnabled` false). Advice in the topic files about launch regions, travel to the front, oil for fighters or
> distant allies and proxies is **history** from that date. **Scheduled ~2026-11-10** ("in 7 days"; confirm with
> `tools/agent-cli gc mapTravel`, all flags true on 11-04): **movement off** (no travel, no Stamina, no free trip home, no wooden
> cases on the map); held wooden cases can still be opened; wooden-case listings and buy orders refunded; the **Cross regions** and
> **Collect wooden cases** milestones disabled (levels saved); travel and wooden-case missions replaced. Also: **Nationalist,
> Statist and Foreman** give happiness directly (Nationalist +11 → **+10**, Statist +6, Foreman +9 per coworker), the 71 removed
> v0.27 links are closed (longest path now **20** regions), battle rankings get an **Alliance** filter, Options became a
> **Settings** window. The last week of movement: [map-and-travel.md](references/map-and-travel.md). Open points: "v0.28 ingest" in
> unresolved-mechanics.md.
>
> **v0.27.1 (2026-10-27**, article `6ae0defd260ab3cd58036d7a`, registry `PATCH_0_27_1`) already changed five v0.27 rules: firing a
> fresh hire is free; employee events can start right after hiring (no 48 h wait); no employee deaths in battles "for now";
> Homesick is fine in the home country's occupied regions; manager wages ÷10 and paid even with no employees. Also: alliance
> leave cooldown reset and off until 2026-10-30, non-bordering map links closed. Every **government-type** value is now
> confirmed by the live client (2026-10-27).
>
> Confirmed on 2026-10-26 by the live config (`LIVECFG_V027`) and client (`LIVECLIENT_V027`): skill ladders (Energy 100 + 10,
> Production 30 + 3, Management 1 + 1, Leadership 0 + 1 (merged into Management by v0.27.3), Companies at level 1), Break Room L1–L3 only, candidacy 20, market and MUs
> at 5, deposits disabled, strategic-resource production bonus and loyalty removed, conquered-region tax share 10%, the 36 tool
> items (+3–6% common … +46–65% mythic), the employee constants and 52 traits, Energy regen 10%/h. Not in the config, so still
> article-only: government-type values, combat-bonus changes, strategic-resource income, starting bag, daily calendar, wooden-case
> odds (the registry flags them "without last_verified"). Unannounced: the bounty cap is now `maxBountyPpMultiplier` 9 (was
> average wage × 6), and the alliance leave cooldown is suspended until 2026-10-30. Open questions: "v0.27 open questions" in
> unresolved-mechanics.md.
>
> The UNIKHORNE codex was ingested the same day; its conflicts are U-CDX-1 … 8 in unresolved-mechanics.md. The one that matters
> most: the codex treats battle bonuses as **separate multipliers capped at +95%**. **2026-10-28 (pass 5) the user confirmed the
> codex**: each bonus is its own factor, the combined product is capped at +95% (+115% in resistance revolts only), floor −100%.
> This **reverses U-CMB-9a** (additive, no cap). Pass 5 also closed many v0.27 employee, skill and government items; see the
> pass-5 session tracker in unresolved-mechanics.md. Topic files, `data/mechanics.yaml`, the calculators and the bot's
> `cogs/commands/damage.py` still use the additive model until synced.

| Topic | Guide v0.26.1 | Live config 2026-10-04 | Working stance |
|---|---|---|---|
| Vote min level | 15 | **20** (+7 days since citizenship change) | 20 (versioned) |
| Inactive after | 4 days | **3 days** (since 2025-05-04) | 3 |
| Country/MU order bonus | Low/Med/High 5/10/15 | single key = 10 (legacy/base) | tiers — confirmed in-game 2026-10-13 |
| Alliance bonus | +20 ≤10% WD, −4/pt, floor −20 | single key = 10 (older model) | curve — confirmed in-game 2026-10-13 |
| Max rounds | 3 (best of three) | maxRounds 15 | best of 3 — confirmed in-game 2026-10-13 (15 never binds) |
| Deposit bonus | random 20–40%, fixed per deposit | depositResourceBonus 30 (fixed value from 2025-08-04) | live region value; else 20–40 range (deposits off from v0.27) |
| Contract auction | step/min 0.05, last-30s +30s | step/min 0.01, 60/60 | config |
| Beginner missions | 100 XP each, set 2000 XP | 50 XP each, set 500 XP | config — user-confirmed 2026-10-13 |
| Takeover limit | 5 days per user (v0.15.0 rule) | cooldown 1 day, min level 25 | config |
| Congress election | candidacy 3rd, vote 4th | getDates: starts the 5th | config |
| Candidacy level | 15 | 15 (outdated wiki: 20); **20** in the live config of 2026-10-26 | **20** since v0.27 (2026-10-26) |

## 3. Time-aware reasoning

- Values live in `data/mechanics.yaml` as a history: `values[]` with `status` (current/disputed/scheduled/historical/deprecated),
  `effective_from`/`effective_to`, `first_observed`, `last_verified`, `source`, `confidence`.
- For "what applied on date D" use `scripts/wlib.py resolve(id, D)` (or reason identically): pick the entry whose window
  contains D; scheduled entries apply only once `effective_from` has passed.
- If an earlier value exists but its dates are unknown, say: *"The sources show this changed but not when; for D the value
  is uncertain."* **Never invent a patch number or date.** The patch log covers every version v0.0.2 → v0.28 except v0.19.1, but
  some values changed with no article (U-HIST-4; see [versioned-mechanics.md](references/versioned-mechanics.md)).
- A newer patch overrides an older one where they overlap: before calling a patch's rule current, check every later patch for
  the same mechanic.
- Patch notes are an event log. Derive the current state from them; don't paste them in as rules.

## 4. Mechanics (reference) vs state (data)

- `references/` + `data/` = **mechanics layer** (how things work).
- Snapshots, API responses, script output = **state layer** (what is true now). Schema: [references/data-model.md](references/data-model.md).
- Validate incoming state before reasoning on it: `python scripts/validate_game_snapshot.py snap.json` — it flags impossible
  and suspicious values and fraction-vs-percent ambiguity, and never corrects silently.
- Canonical percent = percentage points (37 means +37%). If data looks like a fraction (0.37), say so.
- Fields marked `never_assume` (e.g. a company's production bonus, a player's current region, alliance WD share) must be
  supplied or asked for — never defaulted.

## 5. Routing — open only what the question needs

| Question about | Read |
|---|---|
| Overview, glossary, RO→EN terms | [overview.md](references/overview.md), [terminology.md](references/terminology.md) |
| Levels, XP, missions, rerolls, milestones, login/comeback rewards | [progression.md](references/progression.md), [missions.md](references/missions.md), [milestones.md](references/milestones.md), [daily-rewards.md](references/daily-rewards.md) |
| Skills, skill costs, respec, Prestige | [skills-and-respec.md](references/skills-and-respec.md), [prestige.md](references/prestige.md) |
| Energy/Entrepreneurship, companies, upgrades, PP, recipes | [economy.md](references/economy.md), [companies.md](references/companies.md), [production.md](references/production.md), [data/recipes.yaml](data/recipes.yaml) |
| Deposits, specialization, strategic resources, loyalty, wages | [production-bonuses.md](references/production-bonuses.md), [employees-and-wages.md](references/employees-and-wages.md) |
| Employees (v0.27): hiring, stats, traits, wages, happiness, quitting, retirement, training cards and odds, tools, managers, employee profit, hiring/training/skill strategy | [employees-and-wages.md](references/employees-and-wages.md) |
| Employee events (v0.27): the 78 events, check odds, wage-day costs, which events kill, poach, retire or give stats/traits/toolboxes | [employee-events.md](references/employee-events.md) |
| Market, liquidity, cases EV (incl. elite and scrap floor), crafting, scrap, gear wear per hit | [markets-and-trading.md](references/markets-and-trading.md), [crafting-and-scrap.md](references/crafting-and-scrap.md), [equipment.md](references/equipment.md) |
| Position, Stamina, oil, travel, wooden cases | [map-and-travel.md](references/map-and-travel.md) |
| Builds, combat stats, armor/dodge breakpoints, gear | [combat.md](references/combat.md), [combat-stats.md](references/combat-stats.md), [equipment.md](references/equipment.md) |
| Ammo, food, Pill timing | [ammunition-food-pills.md](references/ammunition-food-pills.md) |
| Rounds, ticks, terrain, bonuses, orders, loot | [battle-mechanics.md](references/battle-mechanics.md), [battle-bonuses.md](references/battle-bonuses.md), [battle-orders.md](references/battle-orders.md), [battle-loot.md](references/battle-loot.md) |
| Bounties, mercenary contracts | [bounties.md](references/bounties.md), [mercenary-contracts.md](references/mercenary-contracts.md) |
| Military Units, tournaments | [military-units.md](references/military-units.md), [tournaments.md](references/tournaments.md) |
| Regions, buildings, resistance, revolts, unrest, civil war | [regions-and-buildings.md](references/regions-and-buildings.md), [resistance-and-internal-conflicts.md](references/resistance-and-internal-conflicts.md) |
| Diplomacy, alliances, pacts, Main Enemy, NAPs, economic agreements | [diplomacy.md](references/diplomacy.md), [alliances.md](references/alliances.md), [defensive-pacts.md](references/defensive-pacts.md), [main-enemy.md](references/main-enemy.md) |
| Government, permissions, Congress, laws, elections, citizenship, proxies | [government.md](references/government.md), [congress-and-laws.md](references/congress-and-laws.md), [citizenship.md](references/citizenship.md), [proxies.md](references/proxies.md) |
| Treasury, donations, announcements | [country-treasury-and-donations.md](references/country-treasury-and-donations.md), [announcements.md](references/announcements.md) |
| Parties, ethics (Fanatic …, Unethical; removed in v0.27), party motions | [parties-and-ethics.md](references/parties-and-ethics.md) |
| Government types (v0.27): Republic, Nationalist State, Homeland Front, Federation, Plutocracy, Autocracy, Mercenary State | [government-types.md](references/government-types.md) |
| Multi-accounts, Family Groups, boosting, bots, exploits, chat rules (Rule 7), country funds (Rule 6) | [account-rules-and-security.md](references/account-rules-and-security.md), [proxies.md](references/proxies.md) |
| Discord, TheMachine bot, alert levels, war prep flow | [romanian-community-ops.md](references/romanian-community-ops.md), [strategy-guidelines.md](references/strategy-guidelines.md) |
| Any cooldown/timer | [cooldowns-and-timers.md](references/cooldowns-and-timers.md), [data/cooldowns.yaml](data/cooldowns.yaml) |
| Formulas | [formulas.md](references/formulas.md) |
| Decision patterns | [scenarios.md](references/scenarios.md) |
| History, patch log, deprecations, sources, open questions, maintenance | [versioned-mechanics.md](references/versioned-mechanics.md), [data/patch-history.yaml](data/patch-history.yaml), [deprecated-mechanics.md](references/deprecated-mechanics.md), [source-map.md](references/source-map.md), [unresolved-mechanics.md](references/unresolved-mechanics.md), [update-process.md](references/update-process.md) |
| XP per level, military ranks | [data/progression-values.yaml](data/progression-values.yaml) (`xp_table`), [data/military-ranks.yaml](data/military-ranks.yaml) |
| Script/API data shapes, API field traps (`location` vs `region`, round rankings) | [data-model.md](references/data-model.md), [data/snapshot-schema.yaml](data/snapshot-schema.yaml) |
| Where something is in the game, current button/tab/menu names, old → new labels (v0.26 → v0.27), loading-screen rule texts | [ui-guide.md](references/ui-guide.md) |
| Was guide article X read, and what happened to it (provenance of any community-guide claim) | [guide-articles-ledger.md](references/guide-articles-ledger.md) (large; search it by article ID or title) |

## 6. Scripts (deterministic; run instead of doing arithmetic by hand)

All in `scripts/` (Python 3, PyYAML optional). Run from the skill directory.

| Script | Use |
|---|---|
| `economy_calculator.py product/compare/wage/selfwork/employee/npc/engine/storage/case-ev` | Production value, accounting vs economic profit, profit per PP, max profitable wage, PP/day, case EV. `wage` and `employee` model the **pre-v0.27** job market; for v0.27 `selfwork`, pass the Energy bar as `--entrepreneurship`. **`npc`** = a v0.27 hired employee: output, wage, daily profit, value of a drill / Negotiation / trait Production / Management level, toolboxes, derived quit chance, training-card odds |
| `break_even.py` | Days until a move/product change pays back; compares with deposit time left |
| `combat_bonus_calculator.py [--as-of] [--government TYPE] [--selftest]` | Sum battle bonuses by source, version-aware, alliance curve, −100% floor; `--government` applies v0.27 government-type values |
| `combat_calculator.py mitigation/hp/overflow/pill/cost1k/damage/rank` | Armor/Dodge %, breakpoints, HP per hit, overflow, Pill phase (date-aware), cost per 1k, expected damage per attempt/bar (estimate), military rank |
| `progression_calculator.py level/skill-cost/reroll/prestige/prestige-points/respec/company/seats` | XP → level, Prestige landing level, progression arithmetic |
| `country_calculator.py order-cost/upkeep/initial-dev/resistance-bar/seats` | Paper and development formulas (mostly `[WIKI-ONLY]` estimates) |
| `validate_mechanics.py` | Validate the registry after any edit (run before committing) |
| `validate_game_snapshot.py` | Validate script/API state before analysis |

Scripts encode only sourced formulas. Where the guide is ambiguous they expose a switch (e.g. `--bonus-inputs scaled|base|both`)
instead of guessing.

## 7. How to answer

1. Identify the mechanics involved (open the routed reference, not the whole tree).
2. Take values from live data if supplied, else from `data/mechanics.yaml` for the relevant date; note disputed ones.
3. Calculate (prefer the scripts). Show the formula and inputs briefly.
4. Separate facts `[RULE]`, approximations `[RULE~]`, inferences, and strategy/policy `[STRAT-RO]`/`[POLICY-RO]`.
5. Give the practical consequence and, for decisions, a recommendation.
6. List missing inputs only when they change the result (e.g. "need the deposit's remaining time").
7. Answer just the question — do not dump the manual.

## 8. Anti-hallucination rules

- **Damage per hit is only an estimate**. User-confirmed 2026-10-28 (pass 5): Attack = (skill + weapon + 4 per Precision point
  over 100%) × (1 + ammo) × (1 + Pill) × (1 + rank) × clamp(∏(1 + each battle bonus), 0, 1.95; 2.15 in resistance revolts)
  (U-CDX-1, replacing U-CMB-9a's additive sum); crit = Attack × (1 + crit damage); every hit, crit and miss rolls 90–110%
  (U-CDX-7/7a); a firearm without ammo can't hit (U-CDX-8). Still current: a miss = exactly half of the full Attack, no crit or
  loot (A-3); Armor/Dodge shares are rounded to 2 significant figures (A-12). The bot's reference implementation is
  `cogs/commands/damage.py` (still additive, not yet updated), and `combat_calculator.py damage` is not yet synced with it. Since 2026-10-26 its economics follow
  intel.warera.wiki/builder by user decision (flat pool loot 0.17/1k, iron-valued companies, no work income, Prestige levels;
  see warerabot-dev). Present damage output as an estimate; for build choices point to the SpyWarEra Build Optimizer.
- XP → level uses the wiki XP table, verified against the guide (sums to 86,600; Prestige examples match exactly).
- The codex's "engine-verified" tier reproduces profile Attack totals **outside battle**. It says nothing about how battle
  bonuses combine; the user's pass-5 answer (U-CDX-1), not the engine tier, is what settled the stacking. Its rank table is the same wiki table this skill uses, not a second source.
- **warera.wiki is outdated.** Never state a `[WIKI-ONLY]` fact as settled; when it contradicts the live config or the guide, the
  config or guide wins.
- Don't extrapolate tables (stat tiers have real gaps; reroll costs stop at index 20; Prestige Point costs stop at 1/2/4/8).
- Don't present a Romanian policy (bounty rates, donation %, alert codes, proxy login limit) as a game rule, or the reverse.
- Romanian alert levels ("Cod Galben/Portocaliu") are mentioned in the guide but **not defined** — never invent definitions.
- Market prices in the guide (oil 0.18→0.20, crafting losses, case EV margin) are dated observations, not current prices.
- Unknown semantics of a config key → say "unit/semantics not stated", don't guess (e.g. `region.depleteHourlyPercent`).
- When the user's premise contradicts the sources (e.g. "patch v0.25.5 set X on Sept 1"), say the sources don't contain that
  patch and ask for the patch notes; then follow [update-process.md](references/update-process.md).

## 9. Maintenance

New patch notes, guide editions or config drift → follow [references/update-process.md](references/update-process.md), run
`python scripts/validate_mechanics.py`, and add a CHANGELOG entry. Never overwrite history.
