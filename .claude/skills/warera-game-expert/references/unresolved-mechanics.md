# Unresolved and uncertain mechanics (verification queue)

Status: **C** = sources conflict · **G** = gap (not in any source) · **A** = approximate/inferred · **I** = guide internal
inconsistency. "How to verify" says what evidence would close it. Update this list and `data/mechanics.yaml` together.

## v0.27 open questions (added 2026-10-25; v0.27 live since 2026-10-26, config checked that day)

Source: admin article `6ade08f7899288ce9f0bfe36` (registry `PATCH_0_27`). Almost all can be closed by reading the live config
and the in-game tooltips; ask the user only for what neither shows. The live config of 2026-10-26 (`LIVECFG_V027`) closed
U-V27-6 and part of U-V27-11.

> **2026-10-28 (pass 5):** the user closed U-V27-3a, 4, 7, 8 (remainder), 9, 12, 13 (remainder), 14 (remainder), 16, 19, 21
> and 24, opened U-V27-9a, and deferred 2, 10, 11, 18, 20, 22 and 23; see "Resolved
> with the user (2026-10-28, fifth review pass)". Rows below keep their original wording.

| ID | Question | Status | Working stance / how to verify |
|---|---|---|---|
| U-V27-1 | Deploy date: the text says "tomorrow (26/10) around 14:00 UTC", but `publishedAt` is 2026-10-28T14:14Z | **closed 2026-10-26** | the live client bundle was v0.27 at 16:52 UTC on 2026-10-26 (`LIVECLIENT_V027`), so the deploy happened that day; 14:00Z kept as the announced time. Still to do: the config drift check and the scheduled → current flip |
| U-V27-2 | "The self-work tax is gone" implies self-work was taxed before; the guide says self-work pays no income tax, and no admin article v0.15.0 → v0.26.2 mentions a self-work tax (searched 2026-10-25) | C | history unknown; moot after v0.27 (no self-work tax). Ask the user whether self-work was taxed in v0.26 |
| U-V27-3 | Do the employee production modifiers (Management, manager, happiness, tool, streak, core region, traits) add or multiply? | **closed 2026-10-26** | they **add**: in-game text "Every percent that scales what their Production banks, added together" (`LIVECLIENT_V027_TEXT`); a dev tooltip sums 8 + 16 + 7.3 + 12 + 20 = 63.3% (`V027_GUIDES`). Remainder split off as U-V27-3a |
| U-V27-3a (new) | What does the client's `multiplier: true` flag do on traits (Anchor, Scavenger, Gambler, Tax-shy, Old friends, Nemesis, Sweethearts, gender traits)? Inside the additive sum or applied after it? | G | treat as part of the sum (one dev example, Scavenger −25% inside a −32% total, fits) and flag it; verify on a tooltip of an employee with one of these traits |
| U-V27-4 | Is the income tax on wages added to the owner's cost or withheld from the wage? | G (narrowed 2026-10-26) | in-game it is the "employee tax": "the state collects X% of your employees' wages" and "every point of it costs each employee happiness" (`LIVECLIENT_V027_TEXT`). The **manager** tax is withheld from the manager's pay at Collect. Dev screenshots show payroll = wage × 24 with no tax line (dev tax unknown). Show both readings; read a live payroll entry |
| U-V27-5 | What is a "Management point"? Manager cap +22% = 11 points at 2%, or a table of 2 + 2/level | **closed 2026-10-26** | live client: Management value = 1 + 1/level (11 at level 10); 11 × 2% = 22%. The client key is named `managementBonusPercentPerLevel` (2), but only the per-value-point reading gives 22% |
| U-V27-6 | Break Room levels above 3 | **closed 2026-10-26** | none: `upgradesConfig.breakRoom` has L1–L3 only (1/2/3 employees, steel 0/20/80) |
| U-V27-7 | Do the Automated Engine and self-work get any bonus after deposits/specialization go (core region +5%? Management?) | G | production tooltip; until then, no bonus on engine/self-work |
| U-V27-8 | Government types: Provisional's rules; the law's paper cost; does Mercenary State's "order damage ×2" cover MU orders; Federation pact max; is Homeland Front's "+5% bunker" +5 points; what "×2 resistance in your occupied regions" doubles | **mostly closed 2026-10-27** | live client (`LIVECLIENT_V0271`) + in-game text: Provisional = no modifiers; Mercenary State doubles **national** orders only; Homeland Front doubles players' resistance **contributions** in its occupied core regions; `bunkerBonusDelta` 5 fits "+5 points" (still the calculator's reading). Open: the law's paper cost, Federation's pact max |
| U-V27-9 | Which party motion is removed by "a party can no longer start a resistance" (Finance Local Resistance?), and is Start Revolution (civil war) unaffected? | G | assume Finance Local Resistance removed, Start Revolution kept; check the party motions list |
| U-V27-10 | Does the conquered-region 10% of income tax replace the 1%-per-resistance-point share, and does the development-income share by resistance remain? | G | registry treats 10% as the replacement for tax; development share `[GAP]` |
| U-V27-11 | Bounty max rate (average wage × 6) and contract `maxPerKMultiplier` 6 are tied to the **average wage**. With no job market, what average do they use (employee wages? manager pay?) | **partly closed 2026-10-26** | bounties: the config replaced `maxBountyWageMultiplier` 6 with `maxBountyPpMultiplier` 9, so the bounty cap now follows the PP value (exact formula: read the bounty dialog). Contracts' `maxPerKMultiplier` 6: still open |
| U-V27-12 | Strategic resources: does the monthly reshuffle continue; does "holds" mean owning the region it sits in | G | region page / daily income estimate |
| U-V27-13 | "Military skills at 10": only the menu, or the per-skill unlock levels (1/5/10)? | **partly closed 2026-10-26** | live client has both: a feature gate `featureUnlockLevels.fightSkills` = 10 and per-skill `unlockAtLevel` unchanged for combat (1/5/10); Companies, Management and Leadership unlock at 1. How the gate and the per-skill levels interact in the menu: open (UI) |
| U-V27-14 | Leadership value table; tool bonuses Uncommon–Legendary and tool-type → goods mapping; training-card odds; quit and retirement odds; happiness cap; full-storage and missed-pay happiness penalties | **partly closed 2026-10-26** | live client: Leadership 0 + 1/level; card weights 55/25/13/5/2 plus shifts per Luck and Leadership; quit chance ≤ 5% per check; retirement +5%/year past 65; happiness 0–100; full storage −10; unpaid hour −10 ([employees-and-wages.md](employees-and-wages.md)). Tool bonuses closed by the live config; **tool-type → goods map closed 2026-10-26** (`LIVECLIENT_V027_TEXT`: sickle grain/livestock/coca/wood/fish, pickaxe limestone/iron/lead/petroleum, skillet bread/steak/cooked fish, hammer steel/concrete, flask oil/paper/Pill, caliper the three ammo). **Still open**: durations of the full-storage and unpaid penalties |
| U-V27-15 | Is Energy regen still 10% of max per hour? Every derived Energy figure (720 PP/day at level 0, 2,880 at Energy 200 / Production 60) assumes it | **closed 2026-10-26** | live client `user.regenDividedBy` = 10 |
| U-V27-16 | Does the doubling cost of new candidate sets reset daily? | G | UI. Piraterer's "reroll once or twice, then wait for the next day" implies a daily reset but doesn't say it. (Firing a hire younger than 24 h counted as a reroll until v0.27.1 made firing free, 2026-10-27) |
| U-V27-17 | Is the "1% risk of death" per battle in the region or per hour of battle? | **moot since 2026-10-27** | v0.27.1: no deaths in battles "for now". Reopen if deaths return (G-ART-4); the client still ships `casualtyChance` 0.01 |
| U-V27-18 | Moderation: does the abnormal-wage indicator (0.8×–1.2×) now apply to manager pay? | G | ask moderation / watch rules updates |
| U-V27-19 | New config key `citizenshipApplication.newCountryBordersOpenDays` = 7 (2026-10-26): what is a "new country" here (a revolution winner? a freed country?), and does it replace the civil-war "borders open" period? | G | the skill already says 7 days of open borders after a successful revolution; check the next civil war or liberation |
| U-V27-20 | `region.citizenIncomeTaxPercent` (30% of a foreign worker's tax to the home country) is gone from the config | **closed 2026-10-26** | matches `economy.foreign_work_tax_return` (no player workers since v0.27); whether a foreign **manager's** manager tax is shared stays [GAP] |
| U-V27-21 (new) | In-game happiness text: "Below 30 **from your choices** they can quit" and "If your choices put them here, X%/h chance to quit". Do taxes, battles and event outcomes count as "your choices"? | G | assume every penalty counts (the guides do) and say the text is ambiguous; watch for a walk-out of an employee kept low only by taxes |
| U-V27-22 (new) | Trait slots: New habit "needs a free trait slot", Two new habits "two free slots" (in-game text), but fish writes there's no trait limit. How many slots? | G | cap exists, size `[GAP]`; read it from a New habit card that is withheld, or from an employee with many traits. **Lead 2026-10-29** (`LIVEAPI_20261029`, 261 employees): trait counts 0–5 (73 / 108 / 49 / 22 / 7 / 2), so the cap is **≥ 5** if it exists |
| U-V27-23 (new) | Does moving a Sprinter to another company and back reset its "first 24 h after arrival" +50% (Wodkabouter's daily-swap trick)? | **moot since 2026-10-29** | v0.27.3 replaced Sprinter with Early bloomer, which has no arrival bonus. Was: unverified `[STRAT-EXT]`; the client condition was `recentlyArrived`. Test with one Sprinter; the swap costs −5 happiness for 7 days to the moved employees |
| U-V27-24 (new) | Quit chance between 30 and 0 happiness: is it linear, `5% × (30 − H)/30` (50 for Flight risk)? | A (derived) | fits the 5% cap, a dev tooltip (Flight risk at 44 → 0.6%/h) and Piraterer's table; the game shows the live value in the employee's happiness tooltip |

Downstream (not skill content): the bot's `/economy` (live job offers, Entrepreneurship) and `/progression` (`SKILL_ORDER`, BuhDeuce
paths, "don't hire early") are built on the pre-v0.27 economy; the sibling `warera-config` quick table (Break Room, market/chat/
candidacy levels) will drift once the config updates.

## v0.27.2 ingest (2026-10-29) — open points

Source: admin article `6ae2608f707baf45eebf26c5` (`PATCH_0_27_2`), checked against the live config, client and API the next day
(`LIVECFG_V0272`, `LIVEAPI_20261029`). The income doubling, its stacking with government types and the 32 trait pairs are
settled by those checks; these points are not.

| ID | Question | Status | Where to look |
|---|---|---|---|
| U-V272-1 | "No more contradicting traits **on new employees**": a hire rolls 0–1 traits (`traitsPerEmployee`), so a fresh hire can't hold a pair. Does the rule cover trait-granting **events**, and is the Wild card's random trait drawn only from non-clashing traits (the client only checks that one exists)? | open | an event that grants a trait to an employee with a clashing one; Wild cards on employees with many traits |
| U-V272-2 | Existing clashes: two sampled employees kept Envious + Modest and Loner + Trainer (both from pre-patch Wild cards). Will they be cleaned up later, and can Rehab still remove one of them? (Since v0.27.3 Rehab takes bad traits only: Envious can go, the Loner + Trainer pair can't.) | open (observed kept on 2026-10-29) | the same employees' `traits` later |
| U-V272-3 | Starting money 100 is article-only (server-side, not in config or client) | open, low value | a level-1 account created after 2026-10-28 |
| U-V272-4 | U-V27-10 (development share of conquered regions, deferred): the API shows a conquered region's full doubled development line on the **holder's** side; whether the original owner still gets any of it isn't visible from the region object | lead for U-V27-10 | the original owner's `country.income` vs the sum of its held regions |

## UNIKHORNE codex ingest (2026-10-26) — conflicts and leads

Source: registry `CODEX` (warera.unikhorne.dev/codex, read in full via its JSON API) and `LIVECLIENT_V027`. Where the codex
disagrees with a closed item, the closed item stands unless stronger evidence is named. Its "engine" checks cover profile Attack
totals **outside battle** only.

> **2026-10-28 (pass 5):** U-CDX-1, U-CDX-7 and U-CDX-8 are closed by the user; see "Resolved with the user (2026-10-28, fifth
> review pass)". The rows below keep their original wording for the record.

| ID | Question | Status | Working stance / how to verify |
|---|---|---|---|
| U-CDX-1 | Battle-bonus stacking. Codex: each battle bonus is **its own multiplier**, total **capped at +95%** (+115% in revolts), floored at −100% (cites the Fight Skills guide, the Complete guide, patch notes, a review by RealMarijn). Skill: bonuses **add** into one total, floor −100%, no cap (U-CMB-9a, user-stated + `cogs/commands/damage.py`) | C | keep U-CMB-9a. The guide's own scenario totals (+105 … +125%) exceed a +95% cap, so a cap would contradict them too. Verify: in a battle with ≥ 2 active bonuses, compare one hit (or the tooltip total) with sum versus product; in a +100%+ battle, check whether the tooltip stops at 95. 2026-10-27: four guide articles say the same (G-ART-1), none independent; the live client has no cap constant |
| U-CDX-2 | Pre-v0.27 production bonus stacking: one in-game reading (Portugal, 2026-08-23: +25% specialization × +30% deposit shown as +62.5%) fits **multiplying**; U-ECO-6 says additive | C (history) | keep U-ECO-6; both systems are gone since v0.27. Only matters for reconstructing old tooltips |
| U-CDX-3 | Elite case rarity table 50/32/15/2.5/0.5% (community guides via the codex) | G → community value | use it labelled `[CODEX]`; verify with a large opening sample or an official statement |
| U-CDX-4 | Leadership unlock: article "at level 10" vs live client `unlockAtLevel` 1 | C | the in-game skill screen decides; the client's separate `fightSkills: 10` gate doesn't cover Leadership |
| U-CDX-5 | Moving an employee: article −10 happiness for 7 days vs client −5 (employee move) / −10 (company move) | C | use the client (newer, more specific); confirm on a live move. 2026-10-26 (`V027_GUIDES`): fish and Wodkabouter write −5 for a company move too, but a dev tooltip shows "Moved recently −10, 7 days" without saying which move; the live client text and config still say 5 / 10 |
| U-CDX-6 | Trait count: article 53, live client 52 | C, **moot since v0.27.4** | the client lists every trait; 52 until 2026-11-01, **53** since v0.27.4 added Talks to Machines (which trait the v0.27 article counted is unknown) |
| U-CDX-7 | Per-hit damage spread 90–110% with two ceilings (a 2025 Discord formula) | G | unconfirmed; mean-neutral if real. Verify from a run of identical hits |
| U-CDX-8 | A firearm without ammo counts only up to 40 Attack **and loses its crit chance** (codex engine vs ammo-less profiles) | A | the Attack cap is engine-checked; the crit part rests on the codex. Verify: an ammo-less profile's `criticalChance.total` |

Codex statements that are **stale** against the skill (no action, recorded so nobody re-imports them): civil wars keep country
orders and the bunker (v0.26.2 removed both, CW-1); level 15 to run and vote (vote 20; candidacy 20 from v0.27); its diplomacy
entry's alliance curve (+10% up to 15%; replaced 2026-09-01); party elections 16th/21st/27th (wiki); battles opened by President, VP
and MoD only (the guide adds MoFA); Sworn Enemy upkeep `2 × floor(avg dev / 10)`, measured in-game for a player article the codex
dates 2026-06-10. That confirms ×2 at the v0.25.0 launch (as the registry already has) and adds no later bound to U-HIST-4.

## v0.27 community guides ingest (2026-10-26) — conflicts and resolutions

Source: registry `V027_GUIDES` (ten in-game guides, mostly written from the dev server) checked against `LIVECLIENT_V027_TEXT`
(the live client's constants, event definitions and English text). The client wins where it has the value.

| ID | Conflict | Resolution |
|---|---|---|
| G27-1 | fish: hourly output varies 80–120% | **client ±10%** (`outputVarianceSpread` 0.1); fish's own hourly log (3.70–4.44 around 4.11) fits ±10% |
| G27-2 | codex/Piraterer retirement summary: "the bet costs the crew 5 happiness" | **corrected** from the client's event definition: "Not now" costs the employee −5 for 3 days or retires them; honor and convince as in employees-and-wages.md |
| G27-3 | the skill's own derivation: Leadership/Luck weights "renormalise" (common 46% at Leadership 10) | **corrected**: weights move off Common (in-game text; Elereo's formula; two dev screens match): common 35% at Leadership 10, Luck 0 |
| G27-4 | Luminous: the hire hint can be "the starting wage" | the wage is always on the card; the hint is a stat, Potential or the trait (article, fish, screenshots) |
| G27-5 | Elereo: Recruiter "+1 candidate slot" (per company?) | in-game text: one extra candidate "in the daily shortlist of every company you own"; Piraterer: stackable; client cap +3 |
| G27-6 | fish: no limit on traits | **open** (U-V27-22): the card text needs free trait slots |
| G27-7 | dev manager tooltip: "income tax is withheld" | live text says **manager tax**, withheld at Collect for the company's country; the dev label predates the rename |
| G27-8 | babeuce and Wodkabouter: scrap Legendary/Mythic tools | kept as unverified `[STRAT-EXT]`: no scrap yield per tool rarity is documented |
| G27-9 | babeuce "no points in Production" vs Wodkabouter "Energy : Production 1 : 1" | both kept as strategy: they assume different Energy use (training vs self-work); the 1 : 1 optimum for self-work is derived in skills-and-respec.md |
| G27-10 | Elereo's events article ends inside event 68 (Enemy Leaflets) | filled from the client definition (burn / notepaper (default) / let them read: Luck 60, failure gains Flight risk) |

## Guide-article audit (2026-10-27) — conflicts and leads

Source: registry `GUIDE_ARTICLES` (all 666 English guide articles; per-article results in
[guide-articles-ledger.md](guide-articles-ledger.md)), checked against `PATCH_0_27_1`, `LIVECLIENT_V0271` and `TRANSLATION_EN`.
A guide never overrides a patch note, the live config or the client; where it disagrees, the row says why.
**2026-10-28 (pass 5):** G-ART-1 closed by the user with U-CDX-1 (bonuses multiply, combined cap +95% / +115% in revolts).

| ID | Question | Status | Working stance / how to verify |
|---|---|---|---|
| G-ART-1 | Battle-bonus stacking and a cap (adds to U-CDX-1). Four guides say bonuses multiply and/or cap: Fight Skills Mechanics Guide `6a1b4a095a18ff25e1ca4d94` (2026-05-30, v0.25.0: "multiplicative", "max 105% (135% in revolts)" as the most you can stack), *The Art of WarEra V1* `6a36c1a214c2f5c46ab56f60` (2026-06-20), *War Era Damage Mechanics* `6ad00125783c58de4e335d30` (2026-10-15, the Intel tool's engine: "each one is its own factor … capped at +95% (+115% in revolts)"), and *Keep him or fire him?* `6adfb0879f5bbacb371170b9` (2026-10-27, "no bonus goes above 95%, 115% in a revolt", citing "the game's own code") | C | not independent: the codex cites the first, and the third is the tool engine behind the codex's numbers. No guide shows an in-battle test. The live client (2026-10-27) holds no cap constant; bonus parts come from server battle data. Keep U-CMB-9a; the test in U-CDX-1 still decides |
| G-ART-2 | Party election days. *Political Power: All elections explained* `6a2da1c76bf9ba22d3551f3e` (2026-06-13): party council candidacy 14th / vote 15th, party leader 21st / 22nd, primaries on request. The guide (v0.26.1, 2026-09-30): council 12th/13th, leader 22nd/23rd, presidential candidate 24th/25th | C | keep the newer guide (congress-and-laws.md); `getDates` exposes only presidential and congress dates. v0.27 announced a party rework, so check a party page before relying on either |
| G-ART-3 | A dev-server "Domain" building system: personal Training Grounds (up to +25 Attack, 2,525 concrete), Garage (up to −25% travel cost, 2,020), Cottage (up to +10 Energy, 2,525), Watchtower (Loot chance, 2,525), Scrapyard (scrap bonus, 2,020); regional Airport, Hospital, Power Plant, Tax Office; MU Shooting Range and Stockpile (4,680 steel) — *Stock Up on Concrete Now* `6aa9ae7c078c670dfa6facdc` (2026-09-15, "data from the dev server") | lead | **not live**: none of these names is in the live client or the English catalog of 2026-10-27, and no patch note mentions them. Don't present any of it as a mechanic. Re-check when a patch adds buildings (grep the catalog for "Garage", "Watchtower") |
| G-ART-4 | Employee deaths in battles: v0.27.1 "no more … for now" vs the live client still shipping `employees.battle.casualtyChance` 0.01 and the "Killed: died in a battle fought over the region they worked in" status | C (resolved for now) | the patch note wins (deaths are server-side; the client constant and string are leftovers). Reopen if a later patch or an observed death says otherwise |
| G-ART-5 | Homesick in occupied regions: v0.27.1 says Homesick employees are fine in their country's occupied regions; the client's trait condition is still `OUTSIDE_HOME_COUNTRY` | C (resolved) | the patch note wins (the server decides the condition); the exemption covers the home country's **occupied** regions, not other countries |
| G-ART-6 | Tournament details: only MU orders count in MU tournaments and only country orders in country ones (`69c2f50b7dbad462e91c9e39`, 2026-03-24); the bracket is cut to a power of two with byes (`6a09d4b6d31b5748ed0626f2`, one MU edition, 2026-05-17) | G | recorded in tournaments.md as `[Unverified]` / `[OBS]`; check the orders shown in the next tournament battle and the next bracket |
| G-ART-7 | The Terms of Use of 2026-09-28, as summarised by a player (`6aca745113d6372b785457bc`), ban "use of non-public endpoints" of the public API | G | the summary isn't the source: read the official Terms. If confirmed, the `warera-api` skill's client-only (🕵️) procedures need a policy note; until then the skill reports the claim and doesn't act on it |

Guide claims that are **stale or contradicted** against the skill (no action, recorded so nobody re-imports them): loot rolled once
per battle so splitting hits lowers the odds (`699887fbe1d491834f539687`; loot is rolled per landed hit); armor as a plain
percentage (pre-v0.24.0 guides); Pill 24 h / 24 h or 8 h / 16 h (now 8 h / 15.5 h); weekly missions 30 XP / 300 bonus (now 50 /
500 since v0.25.5); food 10/20/30 HP (percent since v0.24.0); Stamina all-or-nothing travel billing (v0.26.0 only); everything
about the player job market, wage per PP, fidelity, Entrepreneurship, deposits, specialization and party ethics (removed in v0.27);
a 40% resistance tax hijack (removed v0.25.1); automatic tournament registration; texts describing HQ-unlocked "buildings, units
and technologies" or "Barracks", which are another game's mechanics (`694830dfe9ff39564a0a7ab6`, `6a9bb6e941c34849b7a086cd`,
`69ee70f662eb7f7478ccc293`).

## v0.27.3 ingest (2026-10-30) — open points

Source: admin article `6ae39f39b9d173140341a461` (`PATCH_0_27_3`), checked against the live client and config
(`LIVECLIENT_V0273`) and 60 rosters (`LIVEAPI_20261030`). Settled by those checks: one trait per hire, the 12 h fire lock, no
transfer or firing penalty, Responsibility +3 happiness, Management's card-odds shifts (fed the level), event Luck pivot 0, Early
bloomer's numbers, Rehab bad-only, 30 trait pairs, no Leadership skill. Open:

| ID | Question | Status | Where to look |
|---|---|---|---|
| U-V273-1 | Specialist "now matches the good your company makes": were existing Specialists re-pointed, and does the good follow a transfer or a product change? | open (2 of 2 sampled Specialists, both hired before the patch, matched their company) | the trait `arg` of a Specialist before and after a transfer to a company with another good |
| U-V273-2 | Does a company move still lock firing for 24 h? The article covers transfers only; the client's move config lost its lock key | open | the fire button after a company move |
| U-V273-3 | Management's "+2% event odds per level": on every check or only standard ones (Luck × 2 already applies there)? How do Management, happiness (`happinessDivisor` 5) and the stat combine (the old `[GAP]`)? | open | an event's displayed odds at two Management levels |
| U-V273-4 | Candidate cards "show all their stats": base stats only? (Trait Production can't show while the trait is hidden.) If so, the wage gives the exact expectation | open | a hire whose card Production differs from its roster `base` |
| U-V273-5 | Wild card: the shown bad-trait chance (bad ÷ eligible) implies a uniform draw among eligible traits, not by roll weight | A (derived from the client) | compare many Wild card outcomes with ≈28% (no traits; ≈29%, 14 of 48, since v0.27.4) |
| U-V273-6 | Responsibility's +3: capped with happiness at 100? Does it count toward "below 30 from your choices" (U-V27-21)? | open | an employee near 100, or a walk-out at high Responsibility |
## Silent patch 2026-10-31 ingest (2026-11-01) — open points

Sources: community article `6ae682c7470184738824c070` (`SILENT_20261031`), the live client and UI catalog history
(`LIVECLIENT_20261101`) and 60 rosters (`LIVEAPI_20261101`). Settled by those checks: Trainer = 2 shared sessions per Trainer a day
for its coworkers, counted on the Trainer, UTC-day refill; Lucky charm = +3 Luck to coworkers present at 00:00 UTC, stored as
`charmLuck {amount 3, until next reset + 1 h}`, the charm itself excluded; toolbox chance uncapped since 2026-10-29. Open:

| ID | Question | Status | Where to look |
|---|---|---|---|
| U-S1031-1 | `luck.charmGraceHours` 1: the API's `until` is the next reset + 1 h. Is that only an overlap so the Luck never lapses at 00:00, or does a coworker who joins in the first hour after the reset also get the charm? | open | an employee moved in at 00:30 UTC: does it get `charmLuck`? |
| U-S1031-2 | Trainer moved mid-day: the used counter stays on the Trainer, so a spent pool doesn't refill by moving it *[Derived]*. Can the new company's coworkers spend what is left? | open | `trainerSessionsUsed` and a coworker's `trainingsToday` after a transfer |
| U-S1031-3 | Two Lucky charms in one company: does a coworker get +6 (one `charmLuck` with amount 6?) or +3? | open | a roster with two charms |
| U-S1031-4 | Toolbox cap: removed from the client and the UI text on 2026-10-29. Does the server agree (more than 2% per hour at Luck > 20)? | open | toolbox finds of a high-Luck employee over many worked hours |

## v0.28 ingest (2026-11-04) — open points

Sources: admin article `6aea1496b615c31fa0eb4152` (`PATCH_0_28`), the live config, client and UI catalog (`LIVECLIENT_V028`) and
the live region graph (`LIVEAPI_20261104`). Settled by those checks: fighting from anywhere (`battle.locationGateEnabled` false,
Move-to-fight text removed), the `mapTravel` flags (all on until the switch-off), Nationalist +10 / Statist +6 / Foreman +9 as
direct happiness, no event check on Responsibility, the removed v0.27 links closed, longest shortest path 20. Open:

| ID | Question | Status | Where to look |
|---|---|---|---|
| U-V28-1 | When exactly does movement switch off? "In 7 days" from a post at 2026-11-03 17:07Z → about 2026-11-10 17:00Z; the registry uses day precision (2026-11-10T00:00Z) | **scheduled** | `tools/agent-cli gc mapTravel` (flags turn false); then flip the scheduled entries and fix `effective_from` |
| U-V28-2 | After the switch-off, does **Move home** (100 concrete) stay, and does the home region still do anything (position marker, residence on the profile, API `region` field)? | G | the region menu and `user.getUserLite` after 2026-11-10 |
| U-V28-3 | After the switch-off, can wooden cases still be listed or traded, and do new accounts still get the 3 starter cases (client `starterCases`)? | G | the market item page; a new account's inventory |
| U-V28-4 | Does the starting bag keep **150 oil** (`map.starting_oil`) once travel is gone? | G | `progression.starting_bag` in the client / a new account |
| U-V28-5 | Disabled map milestones: can tiers reached but unclaimed still be claimed after the switch-off? "Saved level" implies progress is kept. | G | the Progression page after 2026-11-10 |
| U-V28-6 | Which missions replace the travel / wooden-case missions, and in which pools (daily, weekly, monthly)? | G | mission lists after 2026-11-10 |
| U-V28-7 | With position gone, does the launch region still have to be adjacent to the target (U-CMB-12 ruling), and does `user.location` still change? | G (the adjacency ruling stands until contradicted) | the attack dialog; `user.location` of a few players |

## v0.27.4 ingest (2026-11-02) — open points

Sources: admin article `6ae8bb12bcc26a2f5712ec9d` (`PATCH_0_27_4`), the live client, config and UI catalog (`LIVECLIENT_V0274`) and
70 rosters (`LIVEAPI_20261102`). Settled by those checks: Talks to Machines (client definition), Bully negative, 53 traits / 36
pairs, Wild card Rare +2, Reroll Uncommon, no mixed New habit, crafting 7, the new-country vote key, `lastAgedDay`, the event
definitions. Open:

| ID | Question | Status | Where to look |
|---|---|---|---|
| U-V274-1 | "Production plain stat from traits now counts toward the expected wage": in 82 live employees the paid wage still excludes it, also after cards drawn post-deploy. Does the fix touch only an estimate (card wage change / profit, candidate card), or will wages follow? | **C** (article vs live API; working stance: unpaid) | a hire or trained employee with flat trait Production: wage ÷ (PP × expectation / 4) = base + trained, or + trait? Re-check after the next daily reset |
| U-V274-2 | Strange Mood Demand asks "about {demandValue}" of the company's good, "about 9 money" per the article: fixed 9 money at market price, or wage- or level-based? | G (server-side) | the demand dialog in two companies with different goods |
| U-V274-3 | Talks to Machines' "only employee": does a manager, an employee away on an event, or an unpaid hour break it? Does the doubling need the employee to work that hour? | G | `hourly.engineMultiplier` on a roster with a lone holder, then with a manager |
| U-V274-4 | Event cost cuts: the client vs Elereo's dev list gives 23 cut coin costs plus Tattoo (24); the article says 23 | A (old values from a dev snapshot) | an older live read of the event definitions, if any player saved one |
| U-V274-5 | "Its employees do not age until they work again. Training still ages them." vs "will not work, age or train there": which screen is the first string for, given that disabled companies block training? | G | where the string appears in game |
| U-V274-6 | Ageing per day worked or trained: does a day with one paid hour count as a full year (assumed), do days away on an event count, and is the 10-year retirement re-ask now 10 aged days (assumed) or still 10 calendar days? | G | `lastAgedDay` and `age` of an employee who worked one hour, or was away all day |
| U-V274-7 | Disabled company: do employees on hold keep losing or gaining happiness, keep the Climber drift, or still get events? | G | a roster of a disabled company over a day |

## Session tracker (2026-10-28, fifth review pass)

> `data/mechanics.yaml`, the topic references, [SKILL.md](../SKILL.md), the calculators and the bot's `cogs/commands/damage.py`
> are **not yet synced** with the resolutions below. Where they disagree, this file wins until they are updated.

- **Resolved by the user, pass 5:** U-CDX-1 + G-ART-1 (battle bonuses **multiply**, capped; **reverses U-CMB-9a**), U-CDX-7
  (±10% per-hit spread), U-CDX-7a (new), U-CDX-8 (firearms need ammo), U-CMB-9 crit formula, U-V27-3a, U-V27-4, U-V27-7,
  U-V27-14 (remainder), U-V27-16, U-V27-21, U-V27-24, U-CDX-4, U-V27-13 (remainder), U-V27-8 (remainder), U-V27-9, U-V27-12,
  U-V27-19 (19 IDs closed). See "Resolved with the user (2026-10-28, fifth review pass)".
- **Deferred by the user in pass 5 — ask again next session:** U-V27-22 (trait slots), U-V27-23 (Sprinter swap; moot since v0.27.3), U-CDX-5
  (move penalties; only the company move is left since v0.27.3), U-CDX-6 (trait count), U-V27-10 (development share of conquered regions), U-V27-11 (contracts'
  `maxPerKMultiplier` basis), U-V27-18 (abnormal-wage indicator on manager pay), U-V27-20 (foreign manager tax share),
  U-V27-2 (self-work tax history).
- **New, open (found in pass 5, not asked):** U-V27-9a (cost of starting a resistance battle; does the foreign law path remain?).
- **Not reached in pass 5 (session stopped by the user) — ask next session:** U-LAW-1 and U-PRG-4b (deferred since pass 3/4),
  U-POL-6b remainder (impeach law costs), U-DEV-1a (Core development `× 0.95` vs `^0.95`), CW-1a (MU orders, contracts, MU HQ in
  civil wars), G-ART-2 (party election days after the v0.27 party rework), G-ART-6 (tournament order types, byes), G-ART-7
  (Terms of Use: non-public endpoints), U-CDX-2 (pre-v0.27 production stacking, history), U-CDX-3 (codex elite-case odds: they
  equal the user-supplied U-ECO-7 values; confirm and close), G27-8 (scrap yield per tool rarity).
- **Follow-up maintenance added in pass 5 (not done):** rewrite U-CMB-9a everywhere it is quoted (SKILL.md §2 and §8,
  [battle-bonuses.md](battle-bonuses.md), [formulas.md](formulas.md), `data/mechanics.yaml`, `combat_bonus_calculator.py`,
  `combat_calculator.py damage`) to the multiplied, capped model; update `cogs/commands/damage.py` (bot code: behaviour change,
  needs its own task); drop `[WIKI-ONLY]` from the crit formula; record the ±10% spread and "no ammo = can't hit". Also: mark
  U-CMB-11a's party-motion path historical in [resistance-and-internal-conflicts.md](resistance-and-internal-conflicts.md);
  Leadership at level 1 and combat skills at 10 in [skills-and-respec.md](skills-and-respec.md); the employee items in
  [employees-and-wages.md](employees-and-wages.md) and `economy_calculator.py npc` (tax withheld, quit formula); Federation
  "no pact limit" and the government-type law cost in [government-types.md](government-types.md); then run
  `scripts/validate_mechanics.py`.

## Session tracker (2026-10-14, fourth review pass)

> `data/mechanics.yaml`, the topic references and the calculators are **not yet synced** with the resolutions below. Where they
> disagree, this file wins until they are updated.

- **Resolved by the user, pass 4 (2026-10-14):** U-ETH-4a, U-ETH-4b (new), U-PRG-4a (full milestone schedule), U-PRG-4c (new),
  U-POL-6e (new; reconfirms U-POL-11); closed as **permanently unknown** (don't ask again): U-CMB-11d, U-DIP-5, U-HIST-4.
  **Partly resolved:** U-POL-6b (base costs for 10 laws; the rest stay undocumented). See "Resolved with the user (2026-10-14,
  fourth review pass)".
- **Deferred by the user — ask again next session:** U-LAW-1 (`abusiveLaw*` keys, deferred twice), U-PRG-4b (does a Pill
  count for the "Eat food" milestone?).
- **Incomplete (no answer yet, not deferred):** U-POL-6b remainder: base costs of Impeach President, Impeach Congress Member
  and any law not listed in pass 4.
- **Follow-up maintenance added in pass 4 (not done):** copy the milestone schedule into [milestones.md](milestones.md) and
  `data/progression-values.yaml`, drop its `[GAP]`/`[INFER]` labels; add the per-law base costs to
  [congress-and-laws.md](congress-and-laws.md) with the remaining laws marked incomplete; add the Fanatic Pacifist revolt
  bunker rule to [parties-and-ethics.md](parties-and-ethics.md).

## Session tracker (2026-10-13, third review pass)

> Superseded where pass 4 (above) changed an item's status.

- **Resolved by the user, passes 1–2 (30):** U-ORD-1a, U-ORD-1b, U-DEV-1a, U-DEV-1b, U-POL-3a, U-POL-3b, U-DIP-3a, U-DIP-3b,
  U-CMB-10a, I-2, U-POL-6a, U-POL-11, U-ETH-3, U-POL-10, U-CMB-12, U-ECO-9, U-ECO-10, U-ECO-11, U-POL-1, U-POL-5, U-ECO-6,
  U-ECO-1, I-1, A-2, A-4 (kept), A-5 (relabelled), A-6, A-8/A-9 (kept as dated `[OBS]`), A-11.
- **Resolved by the user, pass 3 (24):** I-3, U-POL-6c (impeachment), U-POL-6d (citizenship), U-ECO-8, U-ETH-4, U-POL-9,
  U-ECO-12, U-PRG-1, U-CMB-9a, A-3, A-12, U-CMB-8, U-ECO-7, U-ECO-7a, U-MAP-1, U-RO-1, I-4, U-CMB-2, A-7 (U-PRG-4 XP),
  U-CMB-11a, U-CMB-11b, U-CMB-11c, A-1, A-10. See "Resolved with the user (2026-10-13, third review pass)".
- **Settled or narrowed by the admin's articles (17):** U-HIST-3 (alliance date), U-HIST-1, U-HIST-2 (located), U-CMB-16,
  U-CMB-13, U-CMB-7, U-PRG-2, U-ECO-2, U-ECO-4, U-PRG-5, U-POL-7, CW-1, ORD-H, GOV-W; narrowed U-CMB-9, U-CMB-10, U-CMB-11.
- **Deferred by the user (4) — ask again next session:** U-POL-6b (per-law base costs: user will list them), U-LAW-1
  (`abusiveLaw*` keys), U-DIP-5 (config SE `maintenanceCost` 3 / alliance upkeep 1), U-HIST-4 (dates of the unannounced
  SE ×2 → ×10, PC +2.5% → +3%, Fanatic Pacifist scope, party-election-day changes).
- **Open:** U-PRG-4a (milestone tier targets: user offered to give them); U-CMB-11d (config resistance `passive` 0.08,
  asked, no answer); U-ETH-4a (does a Fanatic Pacifist revolt still copy the bunker bonus? not asked yet).
- **Follow-up maintenance:** done 2026-10-25: all official articles in `data/patch-history.yaml` and the registry history
  (see CHANGELOG). Not done: sync the remaining topic references; switch calculator default `--bonus-inputs` to `scaled` (U-ECO-1); fix
  [parties-and-ethics.md](parties-and-ethics.md) Isolationist (U-ETH-3). Pass 3 adds: drop `[INFER]` in
  [companies.md](companies.md) (I-3); drop `[WIKI-ONLY]` on the rank table (U-CMB-8), case rarity odds and impeachment rules;
  add elite-case odds to [markets-and-trading.md](markets-and-trading.md) and `case-ev`; rewrite Move home vs free trip home in
  [map-and-travel.md](map-and-travel.md) (U-MAP-1); strategic resources = specialization item only (U-ECO-12); remove alliance
  from own-country bonus examples (I-4); add resistance growth/decay, battle-start costs and the 24 h post-revolt lock to
  [resistance-and-internal-conflicts.md](resistance-and-internal-conflicts.md) (U-CMB-11a); add the citizenship restrictions
  and the hourly-count note to [citizenship.md](citizenship.md); beginner missions = config, unflag (U-PRG-1); party election
  days = guide (U-POL-9). Then run `scripts/validate_mechanics.py`.

## Resolved with the user (2026-10-13 review session)

Each row records the basis the user gave. "In-game" = user-supplied live observation (source priority 1) on 2026-10-13.

| ID | Resolution | Basis |
|---|---|---|
| U-CMB-1 | **Closed.** Best of three: 2 round wins end the battle, so at most 3 rounds. Config `maxRounds` 15 is a cap that never binds in practice. | in-game |
| U-CMB-3 | **Closed.** Curve confirmed: +20% up to a 10% share of world development, then −4% per percentage point above it, **continuous over fractional points**, floor −20%. Example: world 18.03k, alliance 1.91k (10.61%) → +17.55% (displayed share and k-values are rounded). Config `allianceDamagesBonusPercent` 10 = legacy. | in-game UI |
| U-CMB-5 | **Closed.** Order priorities Low/Medium/High = +5/+10/+15% damage (both country and MU orders). Config single key 10 = base/legacy. | in-game (order dialog) |
| U-ORD-1 | **Closed.** Setting or upgrading an order is paid in **paper**. Country order: `max(1, floor(average development / 5)) × p`; MU order: `max(1, floor(members / 5)) × p`; `p` = Low 1 / Medium 2 / High 4. The outdated wiki base 5/10/20 is rejected; config `set*OrderMoneyCost` 30/10/40 = semantics unknown. Upgrade/downgrade: U-ORD-1a/1b. | in-game (multipliers and both base formulas) |
| U-POL-3 | **Closed (formula).** When the unrest bar is full, any political party of the country can vote a motion to start a civil war. Cost = **Core development × 10**; cooldown 48 h. Config `unrest.battleStartCost` 100 = the minimum (U-POL-3b). Paid in paper from the party inventory (U-POL-3a). | in-game; Core confirmed by v0.25.0-beta ("party motions: core development × 10") |
| U-DEV-1 (new) | **Closed.** Development types: **Core** = computed from the country's population and average level, then distributed equally among its core regions; stable and conquest-proof. Used for unrest, government wages and revolution/civil-war cost. **Current** = a region's development, converted to daily money income for the region owner. **Average** = (Core + Current) / 2; used for most costs: battle orders, alliance / Sworn Enemy / Defensive Pact upkeep, laws and upgrade upkeep. Replaces the earlier `[WIKI-ONLY]` description. Formula and aggregation: U-DEV-1a/1b. | in-game UI/tooltips |
| U-DIP-1 | **Closed.** Defensive Pact upkeep = `max(1, floor(average development / 10))` paper per day **per active pact**. The wiki country page's `× 5` is rejected. | official patch notes v0.25.0-beta, effective 2026-06-10 |
| U-DIP-1a | **Closed.** v0.25.0-beta "Alliance rework" = official article `6a282e4c9bbf471e91a3c0a1` (category `official`), `publishedAt` 2026-06-10T15:16:40Z, edited 2026-10-12 (title "(UPDATED)"). Use **effective_from 2026-06-10** (day precision, per user) for its values. | API `article.getArticleById`, user decision |
| U-DIP-2 | **Closed.** Sworn Enemy declaration (`Define enemy country`) = `max(10, round(10 × average development / 10))` = `max(10, round(average development))` paper (base 10 under the general law scaling). Explains the wiki example 14.56 → 15. | in-game; law scaling from v0.25.0-beta |
| U-DIP-3 (new) | **Closed.** Sworn Enemy daily upkeep = `floor(average development / 10) × 10` paper (enemy multiplier 10), then ethics modifiers (e.g. Fanatic Isolationist ×1.5, Fanatic Diplomatic ×2). v0.25.0-beta's `2 × floor(average development / 10)` (min 2) is **historical**: changed after 2026-06-10, date unknown. Minimum and ethics order: U-DIP-3a/3b. | in-game Diplomacy grid |
| U-DIP-4 (new) | **Closed.** Alliance daily upkeep per member = `100% × own average development + 50% × average of the members' average development` paper (min 1, per patch). The patch wording "alliance's total average development" means this mean, not a sum. Rounding (skill uses floor) not re-checked. | in-game UI |
| U-ETH-1 (new) | **Closed.** Fanatic Expansionist Pacification Center bonus = **+3% per level** (guide). v0.25.0-beta's +2.5% is **historical** (changed between 2026-06-10 and 2026-09-30, date unknown). | in-game |
| U-ETH-2 (new) | **Closed.** Expansionist: military bases can be up/downgraded every **4 h**; Fanatic Expansionist every **2 h** (default 8 h). **Military base only**, not every region upgrade (the patch's "region-upgrade cooldown" wording is too broad). | user-stated (basis not specified); consistent with v0.25.0-beta values and the guide's scope |
| U-CMB-4 | **Closed.** Allies defending a region get **half** the bunker bonus (citizens full), as with the military base on attack. The guide's allied-defense total +115% is a guide error; correct total is **+102.5%**. | in-game; v0.25.0-beta balancing note |
| U-ORD-1a | **Closed.** Upgrading an existing order charges only the **difference** in paper: (new multiplier − old multiplier) × base. Example: Low → High = base × (4 − 1) = base × 3. | user-stated (basis not specified) |
| U-ORD-1b (new) | **Closed.** Lowering an order's priority gives **no refund**. Raising it again later is paid again (by U-ORD-1a, the difference from the current priority). | user-stated (basis not specified) |
| U-POL-3a | **Closed.** The civil-war motion (Core development × 10) is paid in **paper from the proposing party's inventory**, as in v0.25.0-beta. | user-confirmed patch value |
| I-2 | **Closed.** Unethical: national orders give double the priority bonus (10/20/30%) at double paper cost; while the capital is occupied the bonus drops back to normal (5/10/15%) and a full-resistance revolt auto-starts on the capital. The guide's +15% = a normal High order. | v0.25.0-beta, user-confirmed as current |
| U-POL-6a | **Closed (voting).** Eligible voters = Congress + President + Vice President. A law ends **early** once Yes or No exceeds 50% of eligible voters. Otherwise, after 24 h, whichever of Yes/No has more votes wins; abstentions and non-votes are ignored; an exact tie = **rejected**. Matches the `[WIKI-ONLY]` description in [congress-and-laws.md](congress-and-laws.md), now user-confirmed. | user-stated |
| U-POL-11 | **Closed.** The country receiving money through "Send money to country" needs **≥ 10 citizens** (guide). The 5-voter rule (wiki/older patch) is not used; config `abusiveLawPossibleVotersNeeded` 5 keeps unknown semantics. Transfer tax: paper, 50% of the amount within your alliance, 100% otherwise; recipient gets the full amount (v0.25.0-beta). | user-stated |
| U-ETH-3 | **Closed.** Non-fanatic (1-point) ethics, current: Isolationist: Sworn Enemy bonus starts at +2%, +2%/day (normal +1%/+1%); Diplomatic: Defensive Pact upkeep ×0.8; Pacifist: orders defending core regions against revolts cost ½; Expansionist: military base up/downgrade every 4 h (U-ETH-2). These replaced the old flat +5% damage bonuses. | v0.25.0-beta, user-confirmed as current |
| U-POL-10 | **Closed.** Minister of Defense: the guide is right: **inventory access, no citizenship handling** (wiki rejected). Officially also: country announcements (v0.25.0-beta) and tournament registration (v0.25.4-beta). | user-stated |
| U-CMB-12 | **Closed.** An attack can only target a region **adjacent** to a region the attacker holds (wiki); the guide's "any region" is wrong. Since v0.26.0 attackers fight from the region the attack was launched from. | user-stated |
| U-ECO-9 | **Closed.** New accounts start with a **random raw-resource company** (guide/patch); the wiki's "grain" is rejected. | user-stated |
| U-ECO-10 | **Closed.** Base Production = **10 PP per work** at Production level 0 (config); the wiki's 12 is rejected. | user-confirmed config |
| U-ECO-11 | **Closed.** Authorized wage band = **±30% of the 24 h average wage** (v0.17.0); since v0.22.0 an out-of-band wage is adjusted instead of firing the worker; employers can lower a wage only 24 h after the worker joined (v0.23.0), and lowering triggers an accept/decline by the worker (v0.22.2). | user-confirmed; v0.17.0 / v0.22.0 / v0.22.2 / v0.23.0 |
| U-POL-1 | **Closed.** "Take control" becomes possible once the President has been inactive **3 days** (same as the config inactivity flag), for players level 25+ with a 1-day cooldown. The guide's 4 days applies to impeaching Congress members, not takeover. | user-stated |
| U-POL-5 | **Closed.** Vote min level = **20** (+7 days since a citizenship change). History: 5 → 15 (2025-12-26) → 10 (2025-12-28) → later 15 (guide) → 20; the dates of the last changes are **unknown** (no admin article). | user decision; v0.21.1/v0.21.2 |
| U-ECO-6 | **Closed.** Company production bonus sources (deposit, specialization, strategic resources, ethics …) are **additive**. Note: worker fidelity (+1%/day worked, max 10%) is applied once a day after work and not counted in wage (v0.22.0). | user-stated |
| U-HIST-1 | **Closed (mostly), from admin articles.** Patriotic: none → +10% (replacing the +15% core self-defense bonus, 2026-02-13) → +20% (2026-08-29). Alliance: old bilateral ally bonus → v0.25.0-beta curve (+10% ≤ 15% share, −0.5/pt, floor 0; 2026-06-10) → today's curve (2026-09-01). Map: position, Stamina and oil travel from v0.26.0 (2026-09-16); stamina-then-oil and 100-concrete Move home from v0.26.1 (2026-09-17). Deposits: quantity-based (~10 h) → 1–5 day duration, hourly discovery (2026-01-09) → 10% hourly discovery chance (2026-01-09, v0.22.1) → variable +20–40% bonus (2026-08-29). Order ranks (#1, #2 …, display only) from v0.25.3 (2026-08-19). | admin articles |
| U-ECO-1 | **Closed.** Bonus units **also consume inputs**: a company producing 10 base + 4 bonus units consumes inputs for all 14. The guide's max-wage formula is right; its profit formula (inputs on base units only) is wrong. Calculators should default `--bonus-inputs` to `scaled`. | user-stated |
| I-1 | **Closed (follows from U-POL-1).** Inactive = 3 days, so the bot's `/inactive_players` "over 3 days" is correct; the guide's 4 days is the Congress-member impeachment rule. | derived from user answer |
| U-POL-3b (new) | **Closed.** Civil-war motion cost = `max(100, Core development × 10)` paper. Config `unrest.battleStartCost` 100 = that minimum (v0.23.0: "min 100"). | user decision, from v0.23.0-beta |
| U-DIP-3a | **Closed.** Sworn Enemy upkeep has a minimum of **10 paper per day**. | user-stated (basis not specified) |
| U-DIP-3b (new) | **Closed.** The minimum applies **after** ethics multipliers: upkeep = `max(10, floor(average development / 10) × 10 × ethics multiplier)`. Example: floor(avg/10) = 0 with Fanatic Isolationist ×1.5 → 10; floor = 1 → 15. | user-stated (basis not specified) |
| U-HIST-3 | **Closed (partly).** Alliance curve: announced in **v0.25.5** (article `6a903fb0125700f0fd4a2c5d`, published 2026-08-29), **effective 2026-09-01 00:00 UTC**. Model before that date = v0.25.0-beta (+10% up to 15% share, −0.5 pt per point, floor 0). Same patch: total damage bonus floored at −100%; alliance cooldown lifted until 2026-09-03 00:00 UTC. Sworn Enemy ×2 → ×10 and Fanatic Expansionist +2.5% → +3%: **no admin article mentions them** (all 100 admin articles scanned 2026-10-13), so these were unannounced changes and their dates stay unknown. | admin articles (user: the admin's articles are the most trusted source) |
| U-DEV-1b | **Closed.** A country's Current development = the **sum** of the development of every region it currently controls, conquered regions included. A region's Current development pays its owner **1 money per point per day**. | user-stated; rate confirmed as seen in game |

## Resolved with the user (2026-10-13, third review pass)

| ID | Resolution | Basis |
|---|---|---|
| I-3 | **Closed.** You get 2 companies by default (0 skill points). Each extra company costs one more Companies skill level, and level n costs **n skill points**: the 3rd company costs 1 point, the 4th 2, … the 12th 10. Cumulative cost for k companies = (k − 2)(k − 1) / 2 points (12 companies = 55). The guide's "skill points needed" column gives the **cost of that step**, not a running total. [companies.md](companies.md)'s n(n+1)/2 reading is right; drop its `[INFER]` label. | user-stated |
| U-POL-6c (impeachment) | **Closed.** Confirms the `[WIKI-ONLY]` text: **Impeach President** removes the whole government, and the seat stays empty until the next election. **Impeach Congress Member** can only target a member whose last login was **more than 4 days** ago. Both are ordinary laws (24 h, U-POL-6a voting). | user-confirmed |
| U-POL-6d (citizenship) | **Closed.** The player applies; only the **President or Vice President** approves or rejects. Approval drops the old citizenship automatically. 30-day change cooldown. **No change is possible while** a Congress candidate, a party-council candidate, a member of a party in the current country, in Congress, or in government. Auto-approval when the country has **≤ 5 citizens** and during the 7 open-border days after a successful revolution. The citizen count behind the ≤ 5 rule is **refreshed hourly, on the hour**, so several players can be auto-approved within one hour before the new count registers. | user-stated |
| U-ECO-8 (foreign-work tax) | **Closed.** When a citizen works in another country, **30%** of the income tax they pay there goes to their **home** country, taken **out of the host country's share** (not charged on top). Config `region.citizenIncomeTaxPercent` 30 = this share (mapping confirmed). | user-confirmed (wiki rule) |
| U-ETH-4 | **Closed.** Fanatic Pacifist: country orders defending **core regions** (against any attack) **and** against revolts are free (guide v0.26.1). v0.25.0-beta's revolt-only scope is **historical** (widened by 2026-09-30, date unknown). The patch's "revolts copy the region's bunker bonus" is still current, civil wars excluded (U-ETH-4a/4b, pass 4). | user-stated |
| U-POL-9 | **Closed.** Monthly party elections follow the guide: council **12–13**, leader **22–23**, primary (presidential nomination) **24–25**. v0.23.0-beta's 14th / 21st / manual primary is **historical** (changed by 2026-09-30, date unknown). The wiki's 16 / 21 / 27 is rejected. | user-stated |
| U-ECO-12 | **Closed.** Strategic resources boost **only the country's specialization item** (wiki scope), not all production. Per strategic resource of a type: 1st **+5%**, 2nd **+0.5%**, 3rd **+0.25%** (v0.21.4 values). Adds to the other production bonuses (U-ECO-6). | user-stated |
| U-PRG-1 | **Closed.** Beginner missions give **50 XP** each and a **500 XP** bonus for the full set (live config). The guide's 100 / 2,000 is wrong or outdated. Drop the flag. | user-stated |
| U-CMB-9a | **Closed.** Battle bonuses (orders, alliance, patriotic, HQ, bunker/base, resistance, Sworn Enemy …) **add into one total**, floored at −100%, which then multiplies the hit: Attack = (skill + weapon + 4 per Precision point over 100%) × (1 + ammo) × (1 + Pill) × (1 + military rank) × max(0, 1 + battle total). The first four factors reproduce the API's `skills.attack.total`. Reference implementation: [cogs/commands/damage.py](../../../../cogs/commands/damage.py) (WIP). | user-stated; bot code |
| A-3 | **Closed.** A miss deals **exactly half** of the full multiplied Attack (after ammo, Pill, rank and battle bonuses), with no crit and no loot. | user-stated; matches damage.py |
| A-12 | **Closed.** Armor and Dodge shares = points / (points + 40), **rounded to 2 significant figures** (e.g. 0.4375 → 0.44). Refines A-2: health per hit = max(1, 10 × (1 − armor share)) × (1 − dodge share) with the rounded shares (as in damage.py). | user-stated |
| U-CMB-8 | **Closed.** The rank table in [data/military-ranks.yaml](../data/military-ranks.yaml) (wiki, 2026-01-09) **matches the in-game ranks modal**. Drop `[WIKI-ONLY]`. For a given player, prefer the API's `skills.attack.militaryRankPercent`. | user-checked in-game |
| U-ECO-7 | **Closed (odds).** Rarity odds, common → mythic. **Case:** 62 / 30 / 7.1 / 0.85 / 0.04 / 0.01% (matches the wiki; drop `[WIKI-ONLY]`). **Elite case:** common 0 (can't drop) / uncommon 50 / rare 32 / epic 15 / legendary 2.5 / mythic 0.5%. Both sum to 100%. Weapon share **30% / equipment 70%** for both cases (config-verified for the regular case; elite = same, U-ECO-7a). | user-supplied (in-game) |
| U-ECO-7a (new) | **Closed.** The elite case uses the same 30% weapon / 70% equipment split. | user-stated |
| U-MAP-1 | **Closed.** Two separate actions. **Free trip home** every **12 h** (config `freeTravelHomeCooldownHours`, current). **Move home** (100 concrete, v0.26.1) **relocates** your home region; it is not a trip, and the next free trip takes you to the new home. The skill's earlier reading of "Move home" as paid travel is wrong. | user-stated |
| U-RO-1 | **Closed (no definition exists).** The Romanian alert codes (Cod Galben / Cod Portocaliu) aren't defined in any source. The skill must **never define them**; refer users to Romanian leadership / Discord announcements. | user-stated |
| I-4 | **Closed.** The alliance bonus (U-CMB-3 curve) applies **only when fighting for an allied country**, not in your own country's battles. The guide's "Attack" example (alliance +20% on one's own attack) is **wrong**: remove that term from its totals. | user-stated |
| U-CMB-2 | **Closed (not an inconsistency).** A round ends as soon as **one side reaches 300** ground points; the other side keeps scoring until then, so a round holds at most 300 + 299 = **599** combined points. The tick table (guide and config `tickPoints`) is looked up by the **combined** points of both sides so far (0–599), so the 300–599 rows are used. | user-stated |
| A-7 / U-PRG-4 (XP) | **Closed (XP).** Milestone XP per tier = **min(10 × tier, 100)** (pattern confirmed). Tier targets supplied in pass 4 (U-PRG-4a). | user-confirmed |
| U-CMB-11a | **Closed (mostly).** Resistance **grows 0.1–0.35% per hour while occupied** (config min 0.1 / max 0.35) and **decays 0.2% per hour while the original owner controls the region**. Bar max scales with region development (× 100, min 100, U-CMB-11). Contribution: 10 energy or 10 health → +1 (citizens of the original country +2). Full bar → a battle can be started by an **original-country party motion**, `max(100, development × 10)` paper, or a **foreign-country law**, `max(200, development × 10 × 2)`. Battle bonus: original citizens up to **30%**, allies up to **15%**, others **0**, scaled linearly by bar fill (10% bar → 3.0% / 1.5%; confirms A-6). Contributions are **disabled during the battle** and for **24 h after a revolt**. The hourly growth is a **random value between 0.1% and 0.35%** (U-CMB-11b). The "development" in both battle-start costs is the **original country's Core development** (U-CMB-11c, closed). Config `passive` 0.08 = permanently unknown (U-CMB-11d, pass 4). | user-stated |
| A-1 | **Closed.** Self-work factor **2.4** is a rule: 24 hourly regens a day × 10% each = 2.4 full bars per day. Relabel `[RULE]`. | user-stated |
| A-10 | **Closed.** Config `mergingCost` is a **dead legacy key** (merging removed in v0.18.0-beta); don't use it for crafting costs. Its match with the specific-crafting steel costs is coincidental or historical; where those costs live in config is not recorded. | user-stated |

## Resolved with the user (2026-10-14, fourth review pass)

| ID | Resolution | Basis |
|---|---|---|
| U-ETH-4a | **Closed.** Fanatic Pacifist revolts **still copy the bunker bonus** (v0.25.0-beta rule is current). **Civil wars are excluded** (consistent with CW-1: no bunker bonus in civil wars). | user-stated |
| U-ETH-4b (new) | **Closed.** The copied bonus goes to the **revolting** Fanatic Pacifist country: it gets the occupier's (enemy's) bunker bonus for that region. If the occupier is **also** Fanatic Pacifist, it gets only its own bunker bonus; the bonus does **not double**. | user-stated |
| U-CMB-11d | **Closed as permanently unknown.** Meaning of config `region.resistancePassiveGrowthPercent` 0.08 is not known to the user or any source. Keep `[GAP]`, never use it in forecasts, don't ask again. Resistance growth stays the random 0.1–0.35%/h of U-CMB-11a. | user: unknown |
| U-PRG-4a | **Closed.** 15 milestones × **20 tiers**; targets in "Milestone tier targets" below. XP per tier = min(10 × tier, 100) (A-7), so tiers 10–20 pay 100 XP each. Matches the 15 ladders in [milestones.md](milestones.md). | user-supplied (in-game) |
| U-PRG-4c (new) | **Closed.** Milestone 3 "Donate x money" counts the **cumulative money donated** (to a military unit or country), not the number of donations. | user-stated |
| U-POL-6b | **Partly closed.** Law base paper costs (formula `max(base, round(base × average development / 10))`): Start presidential election **20**; Set specialization item **50**; Propose / Accept / Break a Defensive Pact **10** each; Set country colour **5** (matches config); Declare war **no cost**; Change taxes **no cost**; Send money to country: **no base cost**, paper = the transfer tax (U-POL-6e). Military base / bunker upgrades are **not laws and cost no paper** (their upkeep is separate, U-DEV-1). Config values still valid: Create alliance 20, Define enemy 10, Leave/Accept alliance 0. **Incomplete:** Impeach President, Impeach Congress Member and every unlisted law; per the user, document only the laws listed here and mark the rest incomplete. | user-supplied |
| U-POL-6e (new) | **Closed (reconfirms U-POL-11).** "Send money to country" paper = **50% of the amount when the recipient is in your alliance, 100% otherwise**; recipient gets the full amount. The user's first wording ("amount / 2") is the alliance case only. | user-confirmed |
| U-DIP-5 | **Closed as permanently unknown.** Config `law.define_enemy_country.maintenanceCost` 3 and `create_alliance` upkeep 1 have unknown semantics. Never use them; Sworn Enemy upkeep = U-DIP-3/3b, alliance upkeep = U-DIP-4. Don't ask again. | user: unknown |
| U-HIST-4 | **Closed as permanently unknown.** No date is known for: Sworn Enemy upkeep ×2 → ×10; Fanatic Expansionist PC +2.5% → +3%; Fanatic Pacifist scope widening; party election days 14th/21st → 12–13/22–23/24–25. Record each as "changed between 2026-06-10 and 2026-09-30 (guide v0.26.1), exact date unknown" (election days: between v0.23.0-beta, 2026-02-13, and 2026-09-30). Don't ask again. | user: unknown |

## Resolved with the user (2026-10-28, fifth review pass)

| ID | Resolution | Basis |
|---|---|---|
| U-CDX-1 / G-ART-1 | **Closed; reverses U-CMB-9a.** Battle bonuses (orders, alliance, patriotic, HQ, bunker/base, resistance, Sworn Enemy …) are each **their own multiplier**. The **combined product** is capped at **+95%**, or **+115% in resistance revolts only** (civil wars use +95%), and still floored at **−100%** (v0.25.5). Attack = (skill + weapon + 4 per Precision point over 100%) × (1 + ammo) × (1 + Pill) × (1 + rank) × clamp(∏(1 + bᵢ), 0, 1.95 or 2.15). The Fight Skills guide's 105% / 135% cap is rejected. U-CMB-9a's additive reading is **historical/wrong** | user-stated (basis not specified); matches the codex and G-ART-1 guides |
| U-CDX-7 | **Closed.** Each hit rolls **90–110%** of its damage (distribution within the range not stated), mean-neutral. **No ceilings**: the codex's "two ceilings" are rejected | user-stated |
| U-CDX-8 | **Closed (corrected).** A firearm **can't be used without ammo**: with a firearm equipped and no ammo you **can't hit at all**. The codex's "counts up to 40 Attack" is the profile display outside battle only, and its "loses its crit chance" is moot | user-stated |
| U-CMB-9 (crit) | **Closed.** A critical hit deals full Attack × (1 + crit damage %), Attack already including ammo, Pill, rank and battle bonuses. Drop `[WIKI-ONLY]` | user-confirmed |
| U-CDX-7a (new) | **Closed.** The 90–110% roll applies to **every hit**: normal hits, crits and misses, after the crit or miss multiplier | user-stated |
| U-V27-4 | **Closed.** The employee tax is **withheld from the wage**: the owner pays the wage, the state takes X% of it, the employee gets the rest. Owner cost = wage (no tax line on top) | user-stated |
| U-V27-3a | **Closed.** Traits flagged `multiplier: true` are added **inside** the employee's single additive production sum, like every other modifier | user-stated; fits the dev Scavenger example |
| U-V27-7 | **Closed.** The Automated Engine and self-work get **no production bonus** since v0.27 | user-stated |
| U-V27-14 (remainder) | **Closed.** Full storage (−10) and missed pay (−10) last **only while the condition lasts**. Missed pay is a **single −10** while any pay is outstanding (not −10 per unpaid hour), removed once paid | user-stated |
| U-V27-16 | **Closed.** The doubling cost of new candidate sets **resets daily** at the day rollover | user-stated |
| U-V27-21 | **Closed.** **Every** happiness penalty counts toward "below 30 from your choices" (taxes, battles and event outcomes included) | user-stated |
| U-V27-24 | **Closed (rule).** Quit chance per hour = 5% × (T − H) / T for happiness H below T, with T = 30 (T = 50 for Flight risk). Relabel from derived to rule | user-confirmed |
| U-CDX-4 | **Closed.** Leadership unlocks at **level 1** (live client); the article's level 10 is wrong; moot since v0.27.3, which merged Leadership into Management | user-stated |
| U-V27-13 (remainder) | **Closed.** The level-10 `fightSkills` gate wins: **no combat skill can be raised before level 10**; the per-skill 1/5/10 unlock levels are leftovers | user-stated |
| U-V27-8 (remainder) | **Closed.** The law that changes the government type costs `max(20, round(20 × average development / 10))` paper (general law formula, base 20). **Federation has no Defensive Pact maximum**: there is no limit | user-supplied |
| U-V27-9 | **Closed.** v0.27 removed the party motion that started a resistance battle (Finance Local Resistance); the civil-war motion (Start Revolution) **stays**. A resistance battle is now started by the **original country's government**. Cost and whether the foreign-country law path remains: U-V27-9a. U-CMB-11a's party-motion path is **historical** from v0.27 | user-stated |
| U-V27-9a (new) | **Open.** Paper cost for the original country's government to start a resistance battle, and whether a foreign country can still start one by law (`max(200, development × 10 × 2)`) | not asked (session ended) |
| U-V27-12 | **Closed.** Strategic resources still **reshuffle monthly**, and a country holds one by **controlling the region it sits in** (conquered regions included) | user-stated |
| U-V27-19 | **Closed.** `newCountryBordersOpenDays` 7 covers a **brand-new country added to the game** (one that didn't exist before). The separate 7 open-border days after a successful revolution (U-POL-6d) **are still current** | user-stated |

### Milestone tier targets (U-PRG-4a, user-supplied 2026-10-14)

Cumulative lifetime counts. K = thousand, M = million, B = billion.

| # | Milestone | Tiers 1–10 | Tiers 11–20 |
|---|---|---|---|
| 1 | Cross regions on the map | 10, 16, 26, 41, 66, 100, 170, 270, 430, 690 | 1,100, 1,800, 2,800, 4,500, 7,200, 12K, 18K, 30K, 47K, 76K |
| 2 | Collect wooden cases on the map | 5, 8, 13, 20, 33, 52, 84, 130, 210, 340 | 550, 880, 1,400, 2,300, 3,600, 5,800, 9,200, 15K, 24K, 38K |
| 3 | Donate money to a military unit or country (total money, U-PRG-4c) | 2, 3, 5, 8, 13, 21, 34, 54, 86, 140 | 220, 350, 560, 900, 1,400, 2,300, 3,700, 5,900, 9,400, 15K |
| 4 | Participate in battles | 2, 3, 5, 8, 13, 21, 34, 54, 86, 140 | 220, 350, 560, 900, 1,400, 2,300, 3,700, 5,900, 9,400, 15K |
| 5 | Deal damage in battles | 200K, 320K, 510K, 820K, 1.3M, 2.1M, 3.4M, 5.4M, 8.6M, 14M | 22M, 35M, 56M, 90M, 140M, 230M, 370M, 590M, 940M, 1.5B |
| 6 | Earn experience in total | 200, 320, 510, 820, 1,300, 2,100, 3,400, 5,400, 8,600, 14K | 22K, 35K, 56K, 90K, 140K, 230K, 370K, 590K, 940K, 1.5M |
| 7 | Contribute to resistance (times) | 2, 3, 5, 8, 13, 21, 34, 54, 86, 140 | 220, 350, 560, 900, 1,400, 2,300, 3,700, 5,900, 9,400, 15K |
| 8 | Open cases / elite cases / wooden cases | 25, 40, 64, 100, 160, 260, 420, 670, 1,100, 1,700 | 2,700, 4,400, 7,000, 11K, 18K, 29K, 46K, 74K, 120K, 190K |
| 9 | Craft (times) | 3, 5, 8, 12, 20, 31, 50, 81, 130, 210 | 330, 530, 840, 1,400, 2,200, 3,500, 5,500, 8,900, 14K, 23K |
| 10 | Loot items on the battlefield | 1, 2, 3, 4, 7, 10, 17, 27, 43, 69 | 110, 180, 280, 450, 720, 1,200, 1,800, 3,000, 4,700, 7,600 |
| 11 | Help military unit members | 5, 8, 13, 20, 33, 52, 84, 130, 210, 340 | 550, 880, 1,400, 2,300, 3,600, 5,800, 9,200, 15K, 24K, 38K |
| 12 | Dismantle items | 20, 32, 51, 82, 130, 210, 340, 540, 860, 1,400 | 2,200, 3,500, 5,600, 9,000, 14K, 23K, 37K, 59K, 94K, 150K |
| 13 | Hit in battles (times) | 100, 160, 260, 410, 660, 1,000, 1,700, 2,700, 4,300, 6,900 | 11K, 18K, 28K, 45K, 72K, 120K, 180K, 300K, 470K, 760K |
| 14 | Loot cases / elite cases in battles | 20, 32, 51, 82, 130, 210, 340, 540, 860, 1,400 | 2,200, 3,500, 5,600, 9,000, 14K, 23K, 37K, 59K, 94K, 150K |
| 15 | Eat food (bread, steak, cooked fish; Pill: U-PRG-4b) | 10, 16, 26, 41, 66, 100, 170, 270, 430, 690 | 1,100, 1,800, 2,800, 4,500, 7,200, 12K, 18K, 30K, 47K, 76K |

## Settled by the admin's official articles (pre-scan 2026-10-13)

Source: all 100 articles by the game admin (user `6813b758efecdf9bab195068`, v0.15.0 → v0.26.1 plus announcements; downloaded via
`article.getArticlesPaginated {userId}`). Per the user these are the **most trusted source**, newest first. Rule agreed with the user:
an item is recorded here when an article settles it and no later source contradicts it; otherwise the user is asked.

| ID | Result | Article (published) |
|---|---|---|
| U-CMB-16 | **Closed.** The "self defense bonus" (+15% when defending a core region) was **removed** and replaced by the patriotic bonus +10% for fighting for your own country; patriotic later raised to **+20%** (effective on release of v0.25.5). | v0.23.0-beta (2026-02-13); v0.25.5 (2026-08-29) |
| U-CMB-13 | **Closed.** When a liberation battle ends, the resistance bar **resets to 0** (supersedes v0.17.1's "a lost revolt halves it"). | v0.23.0-beta (2026-02-13) |
| U-CMB-7 | **Closed.** `lostAttackingRegionMalusPercent` −25: applies when the attacking country **loses the region it is attacking from**. | v0.19.0-beta (2025-10-29) |
| U-PRG-2 | **Closed.** The flat daily reward (config `user.dailyReward`) was **replaced** by the 7-day streak calendar (day 7: 35 money, 10 gems, 3 cases; loops) plus come-back gifts: 3+ days away → 150 XP, 50 money, 2 cases; 7+ → 400 XP, 150 money, 3 cases; 30+ → 800 XP, 400 money, 5 cases; max one per 14 days. Config key = legacy. | v0.25.2-beta (2026-08-19) |
| U-ECO-2 | **Closed.** Deposit bonus: flat +30% → **random +20% to +40%**, drawn at discovery and kept until the deposit runs out; older deposits kept their bonus. Config `depositResourceBonus` 30 = the legacy flat value. Use the region/company tooltip value. | v0.25.5 (2026-08-29) |
| U-ECO-4 | **Closed.** Management = the **maximum number of workers** you can employ (break rooms removed and refunded). Launched as 2 → 12 workers; the admin announced a "temporary ×2" on 2026-01-26; live config today: 4 + 2 per level, max 24. At the limit you can't post work offers or produce until fixed. | v0.22.0-beta (2026-01-09); "hi" (2026-01-26); config 2026-10-04 |
| U-PRG-5 | **Confirmed officially.** Prestige Point stacking cost 1, 2, 4, 8 … (doubling); Prestige removes a fixed 65,000 XP; XP bonus +50% then +10% per extra Prestige, off while at level 50. | v0.25.2-beta (2026-08-19) |
| U-POL-7 | **Closed.** National bounties: introduced (min 20 active citizens), min raised to 50, then **disabled** together with mercenary contracts (contracts later returned as auctions; national bounties did not). Config `nationalBountyEnabled` false (its min 40 differs but is moot while disabled). | v0.24.2-beta (2026-03-31); v0.24.3-beta (2026-04-03) |
| U-HIST-2 | **Closed (ingested 2026-10-25; v0.27.1 added 2026-10-27).** Every official article v0.15.0 → v0.27.1 is in `data/patch-history.yaml` with its ID (registry sources `ADMIN_PATCHES`, `PATCH_0_25_1`). Only v0.19.1 has no article. v0.25.1 exists only as a staff article in category `official` (not by the admin). Newer patches override older ones where they overlap (user rule). | all official articles |
| U-CMB-9 | **Narrowed.** Percent attack modifiers **multiply** (pill ratio × ammo ratio × military rank ratio) instead of adding; Pill bonus 80% → 60% at that patch. Armor/Dodge damage reduction = `total / (total + 40)`. Precision over 100% → +4 attack per overflow point; crit chance over 100% → +4 crit damage per point. How **battle bonuses** (orders, alliance, patriotic …) combine with these is still not stated (U-CMB-9a, deferred). | v0.21.0-beta (2025-12-26); v0.24.0-beta (2026-03-21) |
| U-CMB-10 | **Narrowed.** Loot rework: each hit can drop a case instantly: case chance = Loot Chance skill %, elite-case chance = Loot Chance % / 100 ("Case 2" = elite case, user-confirmed: U-CMB-10a closed); misses can't loot. Round item pool: one equipment/weapon per 200k combined damage; battle pool: one item per 500k; distributed by merged damage rank (rank 1 gets the most valuable). | v0.24.1-beta (2026-03-30) |
| U-CMB-11 | **Narrowed.** Resistance max = region development × 100 (min 100); contribution 10 energy/health → +1 (+2 citizens), level 15+. Growth and Pacification Center reduction are **hourly** (PC: −0.05/−0.10/−0.15/−0.20/−0.25 % per hour at L1–L5). Full-bar bonus 30% citizens / 15% allies. Exact current growth formula still open (config has min 0.1 / max 0.35 / passive 0.08). | v0.23.0-beta (2026-02-13); v0.23.4-beta (2026-03-04) |
| U-POL-5 / U-POL-8 | **History narrowed.** Vote min level 5 → 15 (2025-12-26) → 10 (2025-12-28) → later 15 (guide) / 20 (config); candidacy 0 → 15 → 10 → later 15. The changes to today's values have **no article**, so their dates are unknown. | v0.21.1-beta (2025-12-26); v0.21.2-beta (2025-12-28) |
| U-DEV-1a | **Closed, but re-check (2026-10-25).** Country Core development = `((active population × average level) / 20) × 0.95`, then split equally among core regions. Active population = active citizens of level ≥ 10 (was ≥ 3 until v0.23.4). **Doubt:** the raw v0.20.0 HTML is `((population <em>avgLevel) / 20) </em>* 0.95`. The editor turns a `*…*` pair into `<em>`, and one `*` survives, so the source text most likely had `** 0.95` (a power, as in the wiki and `country_calculator.py`). A `× 0.95` source would leave no `*` at all. The wiki example (100 × 25 → 98.3) fits the power; `× 0.95` gives 118.75. Ask the user which one the game shows. | v0.20.0-beta (2025-12-14); v0.23.4-beta (2026-03-04); user confirmed as current |
| CW-1 (new) | **New rule.** Civil wars: bounties can't be placed on them, country orders can't be set on them, and the bunker bonus doesn't apply. Patched "yesterday" per the post: createdAt 2026-10-12T12:37Z, publishedAt 2026-10-14T12:40Z, so the patch landed 2026-10-11..13; the registry uses publishedAt (2026-10-14). The updatedAt recorded earlier (2026-10-13T14:34Z) read 2026-10-25T15:13Z on re-fetch, as did the other recent admin articles (10-19..10-25), so updatedAt doesn't mark content edits; the three rules are unchanged. **Synced 2026-10-25**: `mechanics.yaml` (`unrest.civil_war`, `bonus.bunker`, source `PATCH_0_26_2`), `patch-history.yaml`, `combat-bonuses.yaml`, and [resistance-and-internal-conflicts.md](resistance-and-internal-conflicts.md), [bounties.md](bounties.md), [battle-orders.md](battle-orders.md), [battle-bonuses.md](battle-bonuses.md), [regions-and-buildings.md](regions-and-buildings.md). **Still open** (CW-1a): MU orders, mercenary contracts and MU HQ in civil wars; the patch doesn't say. The employee update announced "in 1-2 weeks" became v0.27 (article `6ade08f7899288ce9f0bfe36`, publishedAt 2026-10-28), **ingested 2026-10-25 as scheduled** (see "v0.27 open questions"). | **v0.26.2** (user-stated label), article `6accd48eca2ce961eea235ff` "Little update about Civil Wars & Moderation Survey" (2026-10-13/14) |
| ORD-H (new) | **History.** Order costs ×2 (2025-12-15); High order cost ×3 → ×4 Low (2026-02-13); paid in paper from 2026-06-10. | v0.20.1-beta; v0.23.0-beta; v0.25.0-beta |
| GOV-W (new) | **New rule.** Government daily wages: President 3% of country development, other members 1%. 5-day cooldown before a fired/departed member can be re-nominated. | v0.24.1-beta (2026-03-30) |

### Remaining ambiguities (updated 2026-10-14, fourth pass)

Items closed in passes 3 and 4 are in the "Resolved with the user" sections above.

| ID | Open question | Status | Impact |
|---|---|---|---|
| U-POL-6b (remainder) | Base paper cost of Impeach President, Impeach Congress Member and any law not listed in pass 4 | **incomplete**: user named the impeach laws without a cost | mark incomplete; read the cost from the law form |
| U-LAW-1 | Semantics of `law.abusiveLawPossibleVotersNeeded` 5 and `law.abusiveLawsCooldownInDays` 3: which laws are "abusive", and what the numbers gate | **deferred** (twice) | `[GAP]` |
| U-PRG-4b (new) | Does consuming a Pill count toward milestone 15 "Eat food"? | **deferred** | count only bread/steak/cooked fish until confirmed; flag it |
| U-V27-2 | Was self-work taxed in v0.26? | **deferred 2026-10-28** | history only |
| U-V27-10 | Development-income share of a conquered region for the original owner, beside the 10% tax | **deferred 2026-10-28** | `[GAP]` |
| U-V27-11 (remainder) | What contracts' `maxPerKMultiplier` 6 multiplies since the job market went | **deferred 2026-10-28** | contract price cap unknown |
| U-V27-18 | Abnormal-wage indicator (0.8–1.2×) on manager pay | **deferred 2026-10-28** | moderation advice only |
| U-V27-20 (remainder) | Share of a foreign manager's manager tax sent home | **deferred 2026-10-28** | `[GAP]` |
| U-V27-22 | Number of employee trait slots | **deferred 2026-10-28** | cap exists, size `[GAP]`; ≥ 5 seen in the 2026-10-29 API sample |
| U-V27-23 | Sprinter swap resets the 24 h +50% | **deferred 2026-10-28; moot since v0.27.3** (Sprinter removed) | unverified `[STRAT-EXT]` |
| U-CDX-5 | Move penalty: −5 / −10 (client) vs −5 for both (guides) | **deferred 2026-10-28**; employee moves free since v0.27.3; a company move shows −10 for 7 days in the live API (2026-10-30) | client values |
| U-CDX-6 | Trait count 52 (client) vs 53 (article) | deferred 2026-10-28; **moot since v0.27.4** (client 53) | 53 |
| U-V27-9a (new) | Cost of starting a resistance battle by the original country's government; does the foreign law path remain? | **open (not asked)** | `[GAP]` |

Closed as **permanently unknown** in pass 4 (don't ask again, keep `[GAP]`, never use the keys): U-CMB-11d, U-DIP-5; dates in
U-HIST-4 stay "unknown".

## Narrowed by v0.25.0-beta (official, 2026-06-10) — status updated 2026-10-13

> This patch is older than the guide and several of its values were later changed (U-DIP-3, U-ETH-1, U-HIST-3). Treat values
> found **only** here as official-but-possibly-superseded until reconfirmed.

| ID | What the patch says | Effect on the queue |
|---|---|---|
| I-2 | Unethical: if the capital is occupied, the national order bonus "drops back to normal" | **closed 2026-10-13** (user-confirmed) |
| U-POL-6 | Laws cost paper: `max(base cost, round(base cost × average development / 10))` | voting rules **closed** (U-POL-6a); per-law base costs **partly closed** 2026-10-14 (U-POL-6b; impeach laws incomplete) |
| U-ECO-8 / U-POL-11 | `Send money to country` adds a transfer tax in **paper**: 50% within your alliance, 100% otherwise; recipient gets the full amount | **closed 2026-10-13**: ≥ 10 citizens (U-POL-11) |
| U-ETH-3 (new) | Isolationist (1 point): Sworn Enemy bonus starts at +2%, +2%/day; Diplomatic (1 point): pact upkeep ×0.8; Pacifist (1 point): core-region revolt-defense orders ×½ | **closed 2026-10-13** (user-confirmed); [parties-and-ethics.md](parties-and-ethics.md) still lumps Isolationist with the Fanatic +5%/day and needs fixing |
| U-ETH-4 (new) | Fanatic Pacifist: **revolt-defense** orders free, revolts copy the region's bunker bonus; guide: orders defending core regions **and** revolts are free | **closed 2026-10-13 (pass 3)**: guide scope; bunker copy still current, civil wars excluded (U-ETH-4a/4b, 2026-10-14) |
| — | Upgrades previously `[WIKI-ONLY]`: alliance laws (24 h, >50% presidents, free), 7-day/14-day cooldowns, soft-disband, Unethical auto-revolt, Fanatic Diplomatic/Isolationist effects, Imperialist/Republican effects, ethics change cooldown 2 weeks, allied base/bunker half | now official (2026-06-10) |
| — | One-off migration on release: alliances removed, sworn enemies set to max 10%, paper grants (country 20 × core dev, party with ethics 400, MU 20 × active members) | history only |

## Resolved or narrowed by the wiki ingest (2026-10-05)

> The wiki is outdated (user note, confirmed by cross-check). Items "resolved" only by the wiki are marked wiki-only.

| ID | Result |
|---|---|
| U-CMB-5 order tiers | **Resolved** (guide + wiki agree; config 10 = base/legacy); confirmed in-game 2026-10-13 |
| U-CMB-3 alliance | **Narrowed** (guide + wiki agree; config 10 matches older models); closed in-game 2026-10-13 |
| U-CMB-9 damage formula | **Partly**: miss rules confirmed by guide; crit formula wiki-only (old scale); pill × ammo × rank multiply (v0.21.0); battle bonuses sum then multiply, closed 2026-10-13 (U-CMB-9a) |
| U-CMB-8 rank table | Wiki table (2026-01-09) in data/military-ranks.yaml; **matches in-game**, closed 2026-10-13 |
| U-PRG-3 XP table | **Resolved**: progression-values.yaml#xp_table (sums to 86,600) |
| U-PRG-5 Prestige cost | **Resolved**: doubling continues (wiki; official in v0.25.2-beta) |
| U-ECO-4 Management | **Resolved officially** 2026-10-13: max workers (v0.22.0-beta; config 4 → 24) |
| U-ECO-3 deposit depletion | **Resolved**: 0.5% of initial quantity per hour (v0.17.2) |
| U-ECO-5 gear tradability | **Resolved**: separate Equipment Market |
| U-ECO-7 case drops | **Resolved** 2026-10-13: case and elite-case rarity odds user-supplied; 30/70 weapon split for both |
| U-ECO-8 taxes | **Resolved** 2026-10-13: 30% of a foreign worker's tax returns home, out of the host's share (user). Corrected 2026-10-25: the resistance hijack (1%/point, then max 40% by bar fill) was **removed by v0.25.1** (2026-06-14), which introduced the 30% share; v0.27 gives the original owner 10% of a conquered region's income tax |
| U-CMB-6 HQ on defense | **Resolved**: HQ applies in any battle |
| U-CMB-10 loot keys | **Partly**: weaponChancePercent 30 = case weapon share; rankingsLootPercentPer1kDmg = ranking loot pool, **legacy since v0.24.1** (2026-03-30, pool removed; 2026-10-25) |
| U-CMB-11 resistance | **Partly**: bar = region development × 100; +2 citizen / +1 non-citizen |
| U-CON-1 auction | **Resolved**: 0.01 step/min, last 30 s → +60 s (config + wiki); guide outdated |
| U-ORD-1 order costs | **Open** at ingest: guide (paper ×1/×2/×4; country ∝ average development, MU ∝ members) wins; wiki base 5/10/20 × floor(n/5) wiki-only. Closed 2026-10-13 (see top) |
| U-POL-1 inactivity | **Resolved**: 3 days since 2025-05-04; guide's 4 days = impeach rule |
| U-POL-2 takeover | **Resolved**: 5 days was the v0.15.0 rule; now 1 day, level 25 |
| U-POL-4 congress date | **Resolved by live config**: congress starts on the 5th |
| U-POL-6 law quorum | **Resolved** 2026-10-13 (U-POL-6a, user-confirmed); per-law costs deferred (U-POL-6b) |
| U-PRG-2 daily reward | **Explained**: config dailyReward = the pre-calendar daily reward (money 3 → 5 → 10 in 2025); calendar since v0.25.2-beta (2026-08-19) |
| U-HIST-2 patch notes | **Resolved** 2026-10-25: v0.0.2 → v0.27 all ingested (v0.19.1 has no article); v0.27.1 added 2026-10-27 |

## New conflicts found in the wiki ingest

| ID | Topic | Sources | Stance |
|---|---|---|---|
| U-POL-8 | Candidate min level | config 15 + guide 15 vs outdated wiki 20 | **15** (closed) |
| U-POL-9 | Party election dates | guide 12–13/22–23/24–25 vs outdated wiki 16/21/27 vs official v0.23.0 14th/21st | **closed 2026-10-13 (pass 3)**: guide |
| U-ECO-12 | Strategic resources only for the specialization item | outdated wiki only; guide lists sources separately; v0.21.4 calls them global | **closed 2026-10-13 (pass 3)**: specialization item only, +5 / +0.5 / +0.25% |
| U-POL-10 | MoD permissions | wiki: citizenship apps + fund/suppress resistance, no inventory; guide: inventory, no citizenship | **closed 2026-10-13**: guide (user) |
| U-POL-11 | Money transfer requirement | guide ≥10 citizens vs wiki/patch: 5 eligible law voters | **closed 2026-10-13**: ≥ 10 citizens (user) |
| U-DIP-1 | Defensive Pact upkeep | wiki country page `floor(dev/10)×5` vs pact page `floor(dev/10)` | **closed 2026-10-13**: `max(1, floor(avg/10))` per active pact (patch v0.25.0-beta) |
| U-DIP-2 | Sworn Enemy enactment | wiki `base 10 × average development`, but its example (14.56 → 15) doesn't match | **closed 2026-10-13**: `max(10, round(avg dev))` (in-game) |
| U-CMB-12 | Attack origin | wiki (Aug 2026): adjacent region only; guide (Sep 2026): any region | **closed 2026-10-13**: adjacent only (user) |
| U-CMB-13 | Resistance after revolt | wiki: reset; patch v0.17.1: a lost revolt halves it | **closed 2026-10-13**: reset to 0 (v0.23.0) |
| U-CMB-14 | Base L5 oil upkeep | outdated wiki/patch 15/h vs config minimum 25 | **config** (closed) |
| U-CMB-15 | Auction extension threshold | outdated wiki 30 s vs config 60 | **config** (closed) |
| U-ECO-9 | Starting company | guide/patch: random raw vs wiki company page: grain | **closed 2026-10-13**: random raw (user) |
| U-ECO-10 | Base Production per work | wiki company page: 12 PP per session with no skill points vs config Production level 0 = 10 | **closed 2026-10-13**: 10 (user) |
| U-ECO-11 | Wage band ±30% of 24 h average (v0.17.0) | not reconfirmed since | **closed 2026-10-13**: still ±30% / 24 h (user) |
| U-CMB-16 | +15% when defending own core region (v0.15.15) | absent from all later sources and config | **closed 2026-10-13**: removed in v0.23.0 (2026-02-13) |

## Conflicts between the guide (v0.26.1) and live config (2026-10-04) — original list (see above for resolutions)

| ID | Topic | Guide | Live config | Working stance | How to verify |
|---|---|---|---|---|---|
| U-CMB-5 | Country/MU order bonus (`bonus.country_order`, `bonus.mu_order`) | Low/Med/High 5/10/15 | single `countryOrderBonusPercent`/`muOrderBonusPercent` = 10 | **closed 2026-10-13**: tiers (in-game) | — |
| U-CMB-3 | Alliance bonus (`bonus.alliance`) | +20 ≤10% WD, −4/pt, floor −20 | `allianceDamagesBonusPercent` = 10 | **closed 2026-10-13**: curve (in-game) | — |
| U-CMB-1 | Max rounds (`battle.max_rounds`) | 3 (best of three) | `maxRounds` = 15 | **closed 2026-10-13**: best of 3 (in-game) | — |
| U-POL-1 | Inactivity threshold (`progression.inactive_after_days`) | 4 days (incl. takeover) | `isInactiveAfterDays` = 3 | **closed 2026-10-13**: 3 days, takeover too (user) | — |
| U-POL-2 | Takeover limit (`government.takeover`) | "5 days per user" | `takeControlCooldownInDays` = 1, min level 25 | live | patch notes / UI |
| U-POL-3 | Civil war start cost (`unrest.civil_war_cost`) | development × 10 | `battleStartCost` = 100 | **closed 2026-10-13**: `max(100, Core development × 10)` paper (in-game + U-POL-3b) | — |
| U-POL-4 | Congress election date (`election.calendar`) | candidacy 3rd, vote 4th | `nextCongressElectionsAt` = 5th 00:00 UTC | read `getDates` | next cycle timestamps |
| U-CON-1 | Contract auction step/min/extension (`contract.auction`) | 0.05 / 0.05 / last 30 s → +30 s | 0.01 / 0.01 / 60 / 60 | live (newer) | auction UI |
| U-ORD-1 | Order cost currency/base (`bonus.order_paper_multiplier`) | paper, ×1/×2/×4, scales with dev/members | `set*OrderMoneyCost` 30/10/40 (money?) | **closed 2026-10-13**: paper, base `max(1, floor(x/5))` × 1/2/4 (in-game) | upgrade = difference, downgrade no refund (U-ORD-1a/1b) |
| U-PRG-1 | Beginner mission XP (`missions.beginner.*`) | 100 each; 2,000 set bonus at 18/25 | 50 each; 500 set bonus | **closed 2026-10-13 (pass 3)**: config, unflagged | — |
| U-PRG-2 | Daily reward (`rewards.daily_login_calendar`) | 7-day calendar (10 XP, 5–35 money…) | `user.dailyReward` = 50 XP, 10 money, 1 case | **closed 2026-10-13**: calendar (v0.25.2-beta); config key legacy | — |
| U-ECO-2 | Deposit bonus (`production.deposit_bonus`) | random 20–40%, fixed per deposit | `depositResourceBonus` = 30 | **closed 2026-10-13**: random 20–40 per deposit (v0.25.5); config 30 = legacy flat | — |
| U-POL-5 | Vote min level (`election.vote_min_level`) | 15 | 20 (+7 days) | **closed 2026-10-13**: **20**; change date unknown (no article) | — |

## Gaps (not in any source)

| ID | Missing | Impact |
|---|---|---|
| U-CMB-9 | Damage-per-hit formula (attack, crit, precision, multipliers) — narrowed 2026-10-13 (see articles section); stacking deferred | no exact damage; use the optimizer |
| U-CMB-8 | Military rank bonus table (only "+25% at high ranks" example) — **closed 2026-10-13 (pass 3)**: wiki table matches in-game | — |
| U-PRG-3 | XP required per level (only level 50 = 86,600) | can't map XP → level; Prestige landing level unknown |
| U-PRG-4 | Milestone tier targets; XP for tiers 1–5 and 8 — XP closed 2026-10-13: min(10 × tier, 100); **targets closed 2026-10-14** (U-PRG-4a, 15 × 20 tiers); Pill in "Eat food" deferred (U-PRG-4b) | — |
| U-PRG-5 | Prestige Point cost beyond the 4th stacked level | 2^(k−1) is inference |
| U-ECO-4 | Effect of the Management skill — **closed 2026-10-13**: max workers | — |
| U-ECO-3 | Deposit depletion (`depleteHourlyPercent` 0.5) meaning | **closed 2026-10-25**: legacy key of the v0.17.2 quantity model; since v0.22.0 deposits last 1–5 days. Use the move window's remaining time |
| U-ECO-6 | How production bonus sources combine — **closed 2026-10-13**: additive (user) | — |
| U-ECO-5 | Gear tradability: config `isTradable: false` for weapons/equipment while the guide talks of selling gear | liquidity of gear uncertain |
| U-ECO-7 | Battle-case and elite-case drop tables — **closed 2026-10-13 (pass 3)**: odds user-supplied | — |
| U-ECO-8 | `region.citizenIncomeTaxPercent` 30, `law.sendMoneyToCountry` tax rates — **closed 2026-10-13 (pass 3)**: foreign-work share confirmed; transfer tax closed in U-POL-11 | — |
| U-CMB-6 | Whether MU HQ (`attackBonus`) applies when defending | guide tables apply it to defense too |
| U-CMB-7 | `lostAttackingRegionMalusPercent` −25 trigger — **closed 2026-10-13**: losing the region you attack from (v0.19.0) | — |
| U-CMB-10 | Loot config keys `weaponChancePercent`, `hitFor1CaseInPool`, `casesPer1kDamagesInPool`, `rankingsLootPercentPer1kDmg` | narrowed 2026-10-13 by v0.24.1-beta (see articles section) |
| U-CMB-11 | Resistance growth/decay formulas (many `region.resistance*` keys) — **closed 2026-10-13 (pass 3)**: random 0.1–0.35%/h growth, 0.2%/h decay (U-CMB-11a); `passive` 0.08 permanently unknown (U-CMB-11d, 2026-10-14) | bar fill forecast = range only |
| U-POL-6 | Law quorum (`votersRatioNeeded` 0.5 of what?), impeachment, paper cost per law, citizenship application procedure | voting closed (U-POL-6a); impeachment (U-POL-6c) and citizenship (U-POL-6d) closed 2026-10-13; per-law costs partly closed 2026-10-14 (U-POL-6b) |
| U-POL-7 | National bounty feature (`nationalBountyEnabled` false, min 40 active citizens) | **closed 2026-10-13**: disabled since v0.24.3-beta; ignore until enabled |
| U-MAP-1 | "free travel home" (`freeTravelHomeCooldownHours` 12) vs paid Move home | **closed 2026-10-13 (pass 3)**: free trip home every 12 h; Move home (100 concrete) relocates home |
| U-RO-1 | Definitions of Romanian alert codes (Galben/Portocaliu; "Code Red" not mentioned) | **closed 2026-10-13 (pass 3)**: no definition exists; never invent one |
| U-HIST-1 | Previous patriotic value, previous alliance model, dates of map/deposit/order-rank changes | **closed 2026-10-13** mostly (see U-HIST-1 above); SE ×10 and PC +3% dates unknown |
| U-HIST-2 | Any official patch notes (v0.25.x, v0.26.x) | all located 2026-10-13; ingested into `data/patch-history.yaml` 2026-10-25 |

## Approximations and inferences (usable, but label them)

| ID | Item | Basis | Status (2026-10-13) |
|---|---|---|---|
| A-1 | Self-work factor 2.4 | guide calls it approximate; matches hourly 10% regen | **closed** (pass 3): rule, 24 regens × 10% (user) |
| A-2 | Health per hit = 10 × (1 − armor%) | config `healthCost` 10 + guide examples | **closed**: exact, armor% = armor / (armor + 40) (v0.24.0-beta), so health per hit = 10 × 40 / (armor + 40) (user) |
| A-3 | Miss deals "about half" damage | guide | **closed** (pass 3): exactly ½ of the full multiplied Attack, no crit/loot (user) |
| A-4 | Round lasts ≥ ~6 h 10 min, ≤ ~8 h 5 min ideally | guide | **kept** as approximation (user); the battle header shows a round ETA since v0.24.4-beta |
| A-5 | Best total production bonus "starts around 60%"; specialization company can produce "50%+ more" | guide | **relabelled `[STRAT-RO]`** rule of thumb (user) |
| A-6 | Resistance bonus proportional to fill (linear assumed) | guide "scales proportionally" | **closed**: linear: full bonus (30% citizens / 15% allies) × fill fraction (user) |
| A-7 | Milestone XP = min(10 × tier, 100) | pattern from 3 data points | **closed** (pass 3): pattern confirmed (user) |
| A-8 | Stat equivalences (5 Attack = 1.2% Precision = 1% Crit …) | one player's measurements for specific profiles | **kept as dated `[OBS]`** (user); measurement date unknown, may predate the v0.24.0/v0.24.1 rebalance; use the optimizer for decisions |
| A-9 | Market observations (oil 0.18→0.20, crafting losses, case EV margin) | dated observations | **kept as dated `[OBS]`** (user); prefer live prices |
| A-10 | `mergingCost` = specific-crafting steel | numbers match; merging replaced by dismantle/craft in v0.18.0-beta | **closed** (pass 3): dead legacy key (user) |
| A-11 | HQ activation 3 h (config) vs "3–4 h" (guide) | treat as ~3 h | **closed**: 3 h (config, user) |
| A-12 | Dodge rounding to 2 significant figures | assumed from displayed values | **closed** (pass 3): armor and dodge shares round to 2 s.f. (user) |

## Guide internal inconsistencies

| ID | Inconsistency |
|---|---|
| U-ECO-1 | Profit formula charges inputs only on base units; max-wage formula implies inputs on bonus units too. Calculators expose `--bonus-inputs`. **Closed 2026-10-13**: inputs on all units (user). |
| U-CMB-4 | Bonus table: allied defense counts bunker +25% (full) though allies get half; allied attack/revolt do halve. **Closed 2026-10-13**: half (in-game); correct total +102.5%. |
| U-CMB-2 | Tick table rows for 300–599 terrain although a round ends at 300 (also in config `tickPoints`). **Closed 2026-10-13 (pass 3)**: not an inconsistency; ticks are indexed by both sides' combined points (max 599). |
| I-1 | Inactivity 4 days (3.9) vs bot `/inactive_players` "over 3 days" (5). **Closed 2026-10-13**: 3 days is right (follows from U-POL-1). |
| I-2 | Unethical table: country order shows +15% when the capital is occupied (not one of the 10/20/30 levels). Explained by v0.25.0-beta (bonus returns to normal, so +15% = normal High). **Closed 2026-10-13** (user-confirmed). |
| I-3 | Guide's company table column "skill points needed" is actually the Companies skill level. **Closed 2026-10-13 (pass 3)**: the column is the cost of that step (level n costs n points); 12 companies = 55 points. |
| I-4 | "Attack" scenario includes alliance +20% for one's own attack — applicability of alliance bonus to own battles unclear. **Closed 2026-10-13 (pass 3)**: ally battles only; guide example wrong. |
