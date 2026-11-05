# Changelog

## 2026-11-04 (rev 14) — v0.28: fight from anywhere; movement, Stamina and map wooden cases scheduled off (~2026-11-10)

**Sources** (registry, 33 now): `PATCH_0_28` (priority 2): admin article `6aea1496b615c31fa0eb4152` "v0.28 (Nuking movement +
perf)", published 2026-11-03 17:07 UTC, edited 2026-11-04 17:31, read in full (no images). `LIVECLIENT_V028` (priority 1): live
client `_app-90d4b44c9f47c314.js`, gameConfig (new keys `battle.locationGateEnabled` false, `mapTravel` 5 flags all true) and UI
catalog 4838d69 → 3f60446 (2026-11-03 17:02Z). `LIVEAPI_20261104` (priority 1): live region graph (742 regions, 1,856 links).

**Mechanics changed** (immediate changes at 2026-11-03T00:00Z, the publishedAt day; the "in 7 days" step `scheduled` at
2026-11-10T00:00Z, day precision, U-V28-1):
- `war.attack_origin`: fighters hit any battle from anywhere (was: launch / attacked / disputed region); adjacency ruling kept.
- `map.stamina`, `map.oil_per_region`: scheduled `none` (movement off).
- `map.move_home`: free trip home scheduled `none`; Move home's fate `[GAP]` (confidence low).
- `map.wooden_case`: scheduled: no map spawns; held cases open; listings and buy orders refunded.
- New `milestones.map_ladders`: Cross regions / Collect wooden cases active → scheduled disabled (levels saved).
- `employees.happiness`: Nationalist +10, Statist +6, Foreman +9 as direct happiness (Nationalist was +11 via 2 Responsibility + 5).
- `map.max_region_distance`: 19 → 20 (measured on the live graph after the 71 removed links closed; not announced).

**Corrected**: the v0.26-era advice that fighters must stand in, travel to or pay oil for a battle region (now history in
map-and-travel, battle-mechanics, battle-orders, bounties, mercenary-contracts, combat, ammunition-food-pills, resistance,
proxies, alliances, military-units, production, scenarios S10/S11/S24/S25, strategy-guidelines, romanian-community-ops,
data-model, snapshot-schema, skills-and-respec, evaluation, recipes); "never more than 19 regions apart"; Foreman as a Responsibility source. **Added**: the "last week of movement" planning section (free Stamina ≈ 178
regions in 7 days, milestone tiers and oil per tier, case spawn counts), all *Derived*.
**Queue**: new section "v0.28 ingest" (U-V28-1 … 7).
**Files**: `data/mechanics.yaml` (3 sources, 8 mechanics incl. 1 new ID, registry_as_of 2026-11-04), `data/patch-history.yaml` (entry
`v0.28`, coverage), `data/cooldowns.yaml`, `data/progression-values.yaml` (mission and milestone comments), SKILL.md, references:
map-and-travel, battle-mechanics, battle-orders, bounties, mercenary-contracts, combat, ammunition-food-pills,
resistance-and-internal-conflicts, proxies, alliances, military-units, production, economy, overview, data-model, formulas,
cooldowns-and-timers, markets-and-trading, scenarios, strategy-guidelines, romanian-community-ops, missions, milestones,
employees-and-wages, ui-guide, versioned-mechanics, deprecated-mechanics, source-map, update-process, unresolved-mechanics.
**Downstream** (not changed here): the bot's `/mu_positions` (`cogs/commands/mu_positions.py`) reports who stands in position
and the Stamina/oil to get there; since 2026-11-03 position no longer gates hitting, so its premise is obsolete (and its
Stamina/oil column ends ~11-10). The `warera-config` snapshot lacks `battle.locationGateEnabled` and `mapTravel`. After the
switch-off: flip the scheduled entries (update-process "Feature flags for scheduled switch-offs").
**Validation**: `validate_mechanics.py` 0 errors, 25 warnings (same as before); `wlib.resolve` checked on 2026-11-02 / 11-05 /
11-11 for every changed ID; `combat_bonus_calculator.py --selftest` OK; no script reads the changed IDs.

## 2026-11-02 (rev 13) — v0.27.4: ageing per worked day, disabled companies on hold, Talks to Machines, training cards, event rebalance

**Sources** (registry, 30 now): `PATCH_0_27_4` (priority 2): admin article `6ae8bb12bcc26a2f5712ec9d` "v0.27.4 + New skins
giveaway", published 2026-11-02 16:36 UTC, read in full (images: skin packs). `LIVECLIENT_V0274` (priority 1): live client
`_app-08814d1f154569f9.js`, gameConfig (read-only) and UI catalog 77f0bc4 → 4838d69 (16:22Z). `LIVEAPI_20261102` (priority 1):
70 rosters, 162 employees, PP value 0.099.

**Mechanics changed** (old entries closed at 2026-11-02T00:00Z, the publishedAt day):
- `employees.stats`: age +1 year per day worked or trained (API `lastAgedDay`), none in a disabled company; Talks to Machines
  (engine ×2 as the only employee); Bully bad; 53 traits, weights 359, 36 incompatible pairs.
- `employees.training`: Reroll card (Uncommon), Wild card Rare +2, no mixed New habit, no training in a disabled company.
- `employees.events`: cost rebalance and outcome changes (catalogue in employee-events.md, diffed against Elereo's dev-server list).
- `employees.tools`: a tool that doesn't fit the new company returns to the inventory (article + UI text, confidence medium, no
  last_verified).
- `employees.retention`: convince to stay 0.75 wage-days (was 5); honor crit also gives the heir's +1 stat; re-ask presumably
  every 10 aged days.
- `progression.unlock_levels`: crafting 10 → 7 (key split from manager jobs / military skills).
- New `election.vote_citizenship_lock`: 7-day lock, waived during a new country's first 14 days (config multiplier 2).
- `employees.wage`: **disputed**, conflicts entry: the article's trait-Production wage fix vs 82 live employees still paid on
  base + trained (working value unchanged).

**Corrected**: trait count (52 → 53, U-CDX-6 moot); the trait-Production-unpaid rule now rests on live data, not only dev
tooltips; F-ENGINE and the companies engine table now note that the engine gets no production bonus since v0.27 (U-V27-7 closure,
needed for the Talks to Machines value).
**Queue**: new section "v0.27.4 ingest" (U-V274-1 … 7).
**Files**: `data/mechanics.yaml` (3 sources, 7 mechanics, 1 new ID, engine note, registry_as_of 2026-11-02), `data/patch-history.yaml`
(entry `v0.27.4`, coverage), `data/cooldowns.yaml` (vote row → `election.vote_citizenship_lock`), SKILL.md, references: employees-and-wages, employee-events, deprecated-mechanics, versioned-mechanics,
source-map, unresolved-mechanics, update-process, progression, crafting-and-scrap, citizenship, congress-and-laws,
cooldowns-and-timers, companies, formulas, data-model, missions, scenarios, ui-guide.
**Downstream**: no bot code reads the changed values (grep of `cogs/`, `utils/`, `locales/`). `scripts/economy_calculator.py npc`
defaults the paid Production to the total Production when `--paid-production` is omitted, which overstates wages for employees with
trait Production (pre-existing; not changed while U-V274-1 is open). Sibling skills not edited: `warera-config` (new key
`election.voteCitizenshipLockNewCountryMultiplier`, `featureUnlockLevels.craft` 7) and `warera-api/references/game-config.md`
(still says craft 10).

## 2026-11-01 (rev 12) — silent patch 2026-10-31: Trainer shared sessions, Lucky charm at 00:00 UTC; toolbox cap gone

**Sources** (registry, 27 now): `SILENT_20261031` (priority 7): community article `6ae682c7470184738824c070` by Piraterer,
published 2026-11-01 00:08 UTC, reporting an unannounced admin patch (no official article; official category newest = v0.27.3).
`LIVECLIENT_20261101` (priority 1): live client `_app-dae8b3a034a90613.js` and the UI catalog history (vatoutou/warera-translation
89b0525, 0ac5360, 77f0bc4). `LIVEAPI_20261101` (priority 1): read-only roster sample with the bot key (60 companies).

**Mechanics changed:**
- `employees.training` (closed at 2026-10-31T00:00Z, the deploy day): Trainer = 2 extra sessions a day per Trainer, shared by its
  coworkers, refill 00:00 UTC (client `trainerSessionsPerDay` 2; was `coworkerExtraTrainingsPerDay` +1 each); cards show the hand
  rarity and an estimated profit per day.
- `employees.stats` (closed at 2026-10-31T00:00Z): Lucky charm's +3 Luck is handed out at 00:00 UTC to the coworkers present and
  kept until the next reset (API `charmLuck {amount 3, until reset + 1 h}`; client `luck.charmGraceHours` 1).
- `employees.tools` (closed at 2026-10-29T00:00Z): toolbox chance uncapped (client `maxToolboxChancePerHour` gone; UI catalog
  89b0525 at 20:20Z removed the cap strings). Unannounced and unreported; confidence medium until the server side is seen.

**Queue**: new section "Silent patch 2026-10-31 ingest" (U-S1031-1 … 4).
**Files**: `data/mechanics.yaml` (3 sources, 3 mechanics, registry_as_of 2026-11-01), `data/patch-history.yaml` (entries
`silent-2026-10-31`, `unannounced-2026-10-29`), SKILL.md, references: employees-and-wages, ui-guide, deprecated-mechanics,
versioned-mechanics, source-map, unresolved-mechanics, update-process (how to date a silent patch);
`scripts/economy_calculator.py` (`npc --luck`: toolbox chance no longer capped at 2%).
**Downstream**: no bot code models Trainer, Lucky charm or the toolbox cap (grep of `cogs/`, `utils/`).

## 2026-10-30 (rev 11) — v0.27.3: Leadership merged into Management, Responsibility +3 happiness, hiring and trait changes

**Sources** (registry, 24 now): `PATCH_0_27_3` (priority 2): admin article `6ae39f39b9d173140341a461` "v0.27.3", published
2026-10-29 19:32 UTC, read in full. `LIVECLIENT_V0273` (priority 1): live client `_app-7b600575a3d47dea.js` and config (read-only).
`LIVEAPI_20261030` (priority 1): read-only roster sample with the bot key (60 companies, 117 employees).

**Mechanics changed** (old entries closed at 2026-10-29T00:00Z, the publishedAt day):
- `skills.economy_values`: Leadership merged into Management (each level: card-odds shifts + +2 event odds); 13 skills, 715
  points to max (was 770); one more free reset.
- `employees.hiring`: candidate cards show all stats and the wage; 12 h fire lock for new hires; firing and transfers free.
- `employees.stats`: exactly one trait per hire; Responsibility +3 happiness; Luck counts from point 1 in events; Early bloomer
  replaced Sprinter; Specialist = company good; 30 incompatible pairs.
- `employees.happiness`: no firing or employee-move penalty; Responsibility +3 per point instead of a loss shield.
- `employees.training`: Management replaces Leadership in the rarity formula; Rehab bad-only (Rare); Wild card shows its bad-trait
  chance.
- `employees.events`: Management +2 per level; Luck pivot 0; events lock their tool and coworkers.

**Corrected in prose**: the stale "firing within 24 h (a reroll)" in the Energy budget (free since v0.27.1).
**Queue**: new section "v0.27.3 ingest" (U-V273-1 … 6); U-V27-23 and U-CDX-4 moot; U-CDX-5 narrowed to the company move.
**Files**: `data/mechanics.yaml` (3 sources, 6 mechanics, registry_as_of 2026-10-30), `data/patch-history.yaml`, SKILL.md,
references: employees-and-wages, employee-events, skills-and-respec, progression, formulas, terminology, deprecated-mechanics,
versioned-mechanics, source-map, unresolved-mechanics; `scripts/economy_calculator.py` (`npc --management`, `--leadership` kept as
an alias; new Responsibility marginal value).
**Downstream**: the bot's `/economy` and `/progression` still model the pre-v0.27 economy (unchanged here). `utils/computational.py` still lists `leadership` in `ECONOMY_SKILLS` (harmless: the skill no longer exists; not edited here). The sibling
`warera-config` snapshot is still pre-v0.27.

## 2026-10-29 (rev 10) — v0.27.2: income ×2, starting money 100, 32 incompatible trait pairs

**Sources** (registry, 21 now): `PATCH_0_27_2` (priority 2): admin article `6ae2608f707baf45eebf26c5` "v0.27.2", published
2026-10-28 20:52 UTC, read in full; the newest `official` article on 2026-10-29. `LIVECFG_V0272` (priority 1): live config
(`check_config.py`, read-only, snapshot not overwritten) and client `_app-bd1b3e64c9b49e55.js`. `LIVEAPI_20261029` (priority 1):
read-only API sample with the bot key (120 company rosters / 261 employees, 40 regions, their owners, all countries).

**Mechanics changed** (old entries closed at 2026-10-28T00:00Z, the publishedAt day):
- `country.development`: region income 1 → **2 coins per development point per day** (config `region.developmentIncomeMultiplier`
  2, a new key; the only other new key is the strategic one). Verified on 40 regions: hourly `income.development` = development ×
  2 / 24. Government types multiply on top (Republic core ×2 → 4, Nationalist State ×0.7 → 1.4).
- `country.strategic_resource_income`: ×2 (config `strategicResourceIncomeMultiplier` 2); **refined**: the base is the original
  country's **core** development (9 of 9 countries matched; current and average don't fit). Plutocracy ×1.5 on top (3 × core).
  Now `last_verified`, which removes one validator warning.
- `progression.starting_bag`: money 25 → **100** (article only; still warns "without last_verified", as it should).
- `employees.stats`: incompatible trait pairs 14 → **32** (18 new, including all three of the article's examples), country-specific
  names. `employees.training` notes: card pool filtering and before → after display.

**Findings beyond the article**: the region/country `income` API fields are **per hour** (the client shows ×24); a hire still
rolls 0–1 traits (every extra trait in the sample came from training or a relationship event); two pre-patch clashing pairs were
still present on 2026-10-29; trait counts up to 5 (lead for U-V27-22).

**Queue**: new section "v0.27.2 ingest" in unresolved-mechanics.md (U-V272-1 … 4); U-V27-22 gained a lead (cap ≥ 5).
**Files**: `data/mechanics.yaml` (3 sources, 4 mechanics, registry_as_of 2026-10-29), `data/patch-history.yaml` (v0.27.2 entry,
coverage), SKILL.md, references: employees-and-wages, employee-events, country-treasury-and-donations, regions-and-buildings,
production-bonuses, government-types, progression, deprecated-mechanics, formulas (new F-DEV-INCOME), ui-guide, source-map,
versioned-mechanics, unresolved-mechanics.
**Downstream**: no calculator reads the changed IDs. The sibling `warera-api` skill still says only a community post announced the
`employee.*` API access; v0.27.2 is the official announcement (not edited here), and its income-field docs don't state the hourly
unit. Validator: 0 errors, 24 warnings (25 before).
**Process** (end of session): [update-process.md](references/update-process.md) gained "Verifying a patch against the live
game" (config key-count diff, hourly income ratios, roster trainingHistory) and a quote-balance check, because the wlib subset
parser accepted a broken YAML string. The warera-api skill now states the hourly income unit and the v0.27.2 announcement.

## 2026-10-27 (rev 9) — all 666 English guide articles audited; v0.27.1; government types and UI verified

**Sources** (registry, 18 now): `GUIDE_ARTICLES` (priority 5): every article with category `guide` and language `en`, 666,
enumerated with the API filters and cross-checked against the unfiltered 1,717-item guide category, all fetched in full.
`PATCH_0_27_1` (priority 2): admin article `6ae0defd260ab3cd58036d7a`, published 2026-10-27 17:37 UTC, found by re-checking the
`official` category. `LIVECLIENT_V0271` (priority 1): client `_app-68269fc0817be98a.js`, read ~18:00 UTC. `TRANSLATION_EN`
(priority 3, UI wording only): vatoutou/warera-translation `en/messages.po` @ `a8060359fca8` (2026-10-27 17:46 UTC), with dated
diffs against `cea816fe` (2026-09-30) and `e20fa04b` (2026-10-26 22:09).
**Audit outcome** ([guide-articles-ledger.md](references/guide-articles-ledger.md), new): 21 integrated (10 this session, 11
earlier), 1 pending lead, 136 historical only, 508 excluded (169 no game content or off-topic, 107 community/tools/meta/questions,
165 generic advice, 67 reviewed and covered, duplicated, dated, conflicting or contradicted). Review depth per row: full 28 (+11
earlier), claims 87, claim skim 371, opening skim 169. Images weren't OCR'd.
**v0.27.1** (`data/patch-history.yaml` new entry; registry: new current entries for `employees.hiring` (firing free),
`employees.events` (no 48 h wait), `employees.retention` (no battle deaths "for now"), `employees.managers` (wages ÷10, paid with
no employees); the v0.27 entries closed as historical at 2026-10-27; `alliance.cooldowns` note). Prose: employees-and-wages.md,
employee-events.md, cooldowns-and-timers.md, scenarios.md, map-and-travel.md (closed non-bordering links, order arrows),
deprecated-mechanics.md (new "Changed one day later by v0.27.1" table), SKILL.md banner.
**Verified on the live client**: every government-type value (`government.types` last_verified 2026-10-27; Provisional = no
modifiers; Mercenary State doubles national orders only; Homeland Front doubles resistance contributions in its core regions;
order-cost multipliers combine multiplicatively); wooden-case spawn/cap/expiry, PP budgets, starter cases and one 20-good pool
(`map.wooden_case` last_verified). U-V27-8 mostly closed; U-V27-17 moot.
**New from guides and UI**: resistance growth 0.1–0.35%/h and decay 0.2%/h as observed semantics of the config keys; tournament
bracket byes (`[OBS]`) and an unverified orders rule; the 2026-09-28 Terms of Use as reported by a player (incl. a reported ban on
non-public API endpoints, G-ART-7); post-deploy employee economics, keep-or-fire rule, government-type and tax strategy
(`[STRAT-EXT]`/`[OBS]`, employees-and-wages.md, government-types.md); Loot chance adds +1 point per 1% to the hourly wooden-case
chance; trait UI names corrected (Misandrist, not "Man hater"; Tax-shy).
**New pages**: [ui-guide.md](references/ui-guide.md) (current labels, menus, tabs, loading-screen rule texts, v0.26 → v0.27 and
v0.27.1 label changes, 36 tool names in code order), [guide-articles-ledger.md](references/guide-articles-ledger.md).
**Conflicts**: G-ART-1 … 7 in unresolved-mechanics.md (four more guides for U-CDX-1's cap, party-election days, dev-server
"Domain" buildings not live, battle deaths and Homesick client-vs-patch, tournament details, the reported ToS) plus a stale list.
**Consistency fixes found on the way**: cooldowns-and-timers.md said −10 for every employee move (client: −5 employee / −10
company, U-CDX-5); scenarios.md still called the employee bonus stacking unknown (additive since 2026-10-26).
**Text-only registry edit**: the current `government.types` entry's `default` string "Provisional (effects not described)" now says "no modifiers" (the game value didn't change; the gap was filled). **Not changed**: battle-bonus model (U-CMB-9a stands), every value without newer evidence, scripts. Bot code untouched.
**Checks**: `validate_mechanics.py` 0 errors, 25 warnings (2 closed by `last_verified`, 2 new article-only entries: retention,
managers); `combat_bonus_calculator.py --selftest` OK and `--government homeland_front --as-of 2026-10-27` runs;
`wlib.resolve` returns the v0.27 values on 2026-10-26 and the v0.27.1 values on 2026-10-27; line endings preserved.

## 2026-10-26 (rev 8) — v0.27 community employee guides integrated, checked against the live client text

**Sources**: `V027_GUIDES` (priority 5): ten in-game guides of 2026-10-25/26 by Piraterer, Elereo (2), Wodkabouter, fish, Nadim,
Luminous_Valentine, Don_Khorne (UNIKHORNE), babeuce and Ali_Soriati, read in full with their ~100 embedded screenshots (mostly the
0.27.0 dev server). `LIVECLIENT_V027_TEXT` (priority 1): a second read of the live client (`_app-9494af8008d97717.js`) plus its
English text catalog: training-card config, tool → goods map, all 78 event definitions, in-game wording.
**Settled by the client**: employee production bonuses **add** (U-V27-3 closed; U-V27-3a left for multiplier-flagged traits);
tool-type → goods map (U-V27-14 remainder); rarity rolled once per hand; Leadership/Luck move card weight **off Common**
(corrects the skill's own "renormalise" derivation: 35%, not ~46%, common at Leadership 10); full card catalog (Drill/Intensive
drill, Negotiation, Rehab, Wild card, New habit, Two new habits, Second wind, Clean slate); retirement event options (corrects the
codex's "bet costs the crew"); Responsibility shield 10%/point on losses only; Luck's event-check terms (Luck − 3) × 4 / × 2;
manager tax withheld at Collect; firing within 24 h = a reroll; trait conditions (Prima donna's [GAP] closed).
**From the guides**: trait Production unpaid (several dev tooltips), Negotiation subtracts points, hire-card contents, wage-day event
costs, quit-chance formula (derived, U-V27-24), economics tables (value of drill, Negotiation, trait Production, Management),
trait tier lists, card priorities, skill builds, location/hiring/manager strategy; all labelled `[OBS]` or `[STRAT-EXT]`.
**Files**: employees-and-wages.md (rewritten in place, prior content kept), new employee-events.md, skills-and-respec.md
(v0.27 builds, Energy : Production 1 : 1 derivation), formulas.md (F-EMPLOYEE-QUIT, F-TRAINING-RARITY, F-EVENT-COST; stacking
no longer GAP), production-bonuses.md, companies.md, unresolved-mechanics.md (U-V27-3/4/14/16 updated, U-V27-3a/21/22/23/24 new,
conflicts G27-1 … 10), source-map.md, SKILL.md (provenance, routing, scripts), `data/mechanics.yaml` (2 sources; `employees.*`
values and notes, rev 8). **Script**: `economy_calculator.py npc` (v0.27 employee economics), checked against fish's worked example
(daily profit 10.96 vs the game's 10.97), Wodkabouter's drill table (0.48) and two dev training screens (exact).
**Checks**: `validate_mechanics.py` 0 errors, 25 warnings (unchanged); documentation validator 0 errors on the changed script.

## 2026-10-26 (rev 7) — v0.27 marked live

**Check**: `warera-config/scripts/check_config.py` against the live config (read-only; the warera-config snapshot was not
overwritten): 248 keys added, 65 removed, 63 changed. New registry source `LIVECFG_V027` (priority 1). Together with the client
bundle (`LIVECLIENT_V027`) this confirms the deploy on 2026-10-26; `effective_from` stays at the announced 14:00Z.
**Registry flip**: 41 `scheduled` → `current`, 25 closed entries `current` → `historical` (scripted, then diffed: only status,
source and last_verified lines changed). 23 entries confirmed by the live config/client carry `last_verified` 2026-10-26 and source
`LIVECFG_V027`; the 18 article-only ones (government types, type-specific combat bonuses, strategic-resource income, starting bag,
daily calendar, wooden cases, party rules, taxes, wage band, job lock, ethics income, specialization) are current without
`last_verified`, which the validator reports (25 warnings: 7 old + 18 new). Validator 0 errors; bonus selftest OK; post-deploy
runs of `combat_bonus_calculator.py --as-of 2026-10-27` (plain and with 4 government types) resolve the v0.27 values.
**New from the live config**: Break Room has L1–L3 only (U-V27-6 closed); 36 tool items, six types (caliper, flask, hammer,
pickaxe, sickle, skillet) × six rarities, bonus ranges 3–6 / 7–12 / 13–20 / 21–30 / 31–45 / 46–65% (`employees.tools`); toolbox item
(legendary case, untradable); `mu.helperHealthPerHelp` 1 (v0.27's helper +1 HP); **unannounced**: bounty cap
`maxBountyWageMultiplier` 6 → `maxBountyPpMultiplier` 9 (new `bounty.rules` entry; U-V27-11 partly closed) and the alliance leave
cooldown suspended until 2026-10-30 (`alliance.cooldowns` note); `region.citizenIncomeTaxPercent` removed (U-V27-20);
`citizenshipApplication.newCountryBordersOpenDays` 7 (meaning open, U-V27-19).
**Prose**: every `[SCHEDULED]` / "until confirmed" label in the topic files replaced by `[RULE]`, or `[LIVE]` where the config
shows the value (progression gates, Break Room, crafting level, MU help); banners in SKILL.md, employees-and-wages, government-types,
parties-and-ethics, companies, deprecated-mechanics, overview, map-and-travel, versioned-mechanics, data-model, economy, formulas,
skills-and-respec, bounties, alliances, source-map, unresolved-mechanics; `data/patch-history.yaml` v0.27 note.
**Side note**: Git Bash `sed -i` rewrites CRLF files as LF; files that were CRLF were converted back.

## 2026-10-26 (rev 6) — UNIKHORNE codex ingested; v0.27 constants checked on the live client

**Sources**: `CODEX` (warera.unikhorne.dev/codex, priority 5): 62 entries in 7 categories, rank ladder, 21 sub-sources and a mirror
of 97 admin articles, read in full from its JSON API. `LIVECLIENT_V027` (priority 1): the live app.warera.io client bundle, read
at 16:52 UTC. It was already v0.27, so the deploy is confirmed (U-V27-1). Every Workforce number the codex took from the dev server
matched the live client.
**New labels**: `[LIVE-CLIENT]`, `[CODEX]` (SKILL.md §1).
**Registry** (147 mechanics, 11 sources; statuses unchanged): `skills.economy_values` (Management 1 + 1/level, Leadership 0 + 1/level,
Production a bar, Companies at level 1), `employees.hiring/stats/wage/production/happiness/retention/training/events/tools` (client
constants: card weights and shifts, drill and wage-card sizes, happiness 0–100 and penalties, quit ≤ 5%, storyteller settings,
PP-value fallback 0.1, expectation floor 70% / ceiling 160%) with `last_verified` 2026-10-26.
**Closed**: U-V27-1, U-V27-5, U-V27-15. **Partly closed**: U-V27-13, U-V27-14. **New conflicts/leads**: U-CDX-1 (battle-bonus stacking
and a +95% cap: codex multiplicative vs U-CMB-9a additive; skill unchanged), U-CDX-2 (pre-v0.27 country × deposit multiplying; history),
U-CDX-3 (elite case table, community), U-CDX-4 (Leadership unlock 10 vs 1), U-CDX-5 (employee move −10 vs −5), U-CDX-6 (53 vs 52
traits), U-CDX-7 (90–110% hit spread), U-CDX-8 (no-ammo crit loss). Stale codex claims listed so they aren't re-imported.
**Re-derived**: the codex's Prestige timing (228/152 days) only fits pre-v0.25.5 XP rates; current figures are 155 / 104 / 97 / 91.
**Synced stale topic files** (pre-existing drift the codex exposed): battle-mechanics/formulas (tick table by combined terrain,
U-CMB-2), map-and-travel (free trip home vs Move home, U-MAP-1), production-bonuses (strategic resources only on the specialization
item, U-ECO-12), alliances/battle-bonuses (dated alliance history, U-HIST-3; I-4).
**Prose**: employees-and-wages (full trait table, training and event constants, retirement event, wage base), skills-and-respec,
prestige, progression (XP clock, double-XP weekend), combat-stats (no-ammo firearm, crit corroboration, derived ceilings, hit
spread), equipment (wear 1% per hit), battle-loot (landed-hit audit, pool cutoff and yield, elite table, scrap EV), crafting-and-scrap,
markets-and-trading (displayed price includes tax), economy (±10% roll, regen confirmed), companies (cheapest-+1-PP/h order),
deprecated-mechanics (wage-range history; v0.27 banner), proxies and account-rules (admin's Rule 6 ruling incl. the Bosnia case,
Rule 7, boosting history), tournaments (+25 flat Attack per bonus level), data-model (API field traps), formulas (F-WOODEN-QTY,
F-EMPLOYEE-EVENTS, F-XP-CLOCK, hits-per-Health, scrap floor, per-attempt loot), unresolved-mechanics, source-map, SKILL.md.
**Data**: `data/equipment.yaml` (case and elite odds, scrap EV, `wooden_case_drops_v027`), `data/patch-history.yaml` (4 unversioned admin
posts: Rule 6, Rule 7, boosting note, double-XP weekend; 93 entries).
**Not done (next)**: the post-deploy flip of every `scheduled` v0.27 entry after `check_config.py`; Break Room levels, tool bonuses and
wooden-case odds still need the live config or UI. **Downstream**: none of the calculators read the changed keys
(`grep` of `scripts/*.py` for the edited IDs); `combat_calculator.py damage` still models additive battle bonuses (unchanged).

## 2026-10-25 (rev 5) — all official articles ingested; newer patch overrides older

**Source**: every article of category `official` (81: 55 by the admin, plus translations and staff posts) and every admin
article (101), fetched with `article.getArticlesPaginated` and read in full. New registry sources `ADMIN_PATCHES` (admin, v0.15.0 →
v0.26.1, priority 2) and `PATCH_0_25_1` (v0.25.1 exists only as a staff article, `6a2d86d5ab0e47773095df00`). **User rule:** a newer
version overrides an older one where they overlap; applied throughout.
**Patch log** (`data/patch-history.yaml`, table_version 2): 50 new entries, now 89 in all: v0.15.2, v0.15.9–v0.15.11, v0.16.6–v0.16.11,
v0.17.8 → v0.26.1 and 5 dated announcements (rollback, weekly-missions bug, Management ×2, map links), each with its article ID. Only
v0.19.1 has no article.
**Corrected current values** (marked current, but overridden by a later patch): `company.break_room_levels` (removed by v0.22.0),
`production.deposit_depletion` (1–5 days + hourly 10% roll since v0.22.0/v0.22.1), `loot.ranking_pool` (removed by v0.24.1; config
1.5 is legacy), `economy.occupied_tax_hijack` (removed by v0.25.1 until v0.27), `combat.health_cost_per_hit` (hitting below 10 Health
since v0.22.0, no armor cap since v0.24.0, A-2 formula), `consumables.pill` (buff was 80% until v0.21.0; debuff 15.5 h dated to
v0.25.1), `bonus.order_paper_multiplier` (disputed wiki model → official v0.25.0 formula, U-ORD-1), `unrest.civil_war_cost`
(disputed → max(100, core development × 10) paper), `diplomacy.paper_upkeep` (wiki pact ×5 → official), `production.deposit_bonus`
(disputed → current, v0.25.5), `war.attack_origin` (now disputed with the user's adjacency rule U-CMB-12).
**Dated history added** (formerly "date unknown"): patriotic 0 → 10 → 20, alliance flat → v0.25.0 curve → v0.25.5 curve,
occupier malus, citizenship cooldown, vote/candidacy levels 5/0 → 15 → 10, takeover level 15, strategic resources 3/1/0.5 → 5/0.5/0.25,
Management 2–12 → 4–24, weekly mission XP, armor formula, food, bunker/base (v0.23.4, v0.25.0), bounties, tournaments,
announcements, map entries, lost-attacking-region malus (trigger now known), total floor, loyalty, contracts, non-aggression windows.
**New IDs** (147 mechanics): `missions.claiming` (by hand → auto 2026-06-14 → by hand 2026-08-29), `government.daily_wages`.
**Scripts**: `combat_bonus_calculator.py` no longer crashes for dates before v0.25.5 (no total floor) or before v0.25.0 (bunker/base
level table not stated); `combat_calculator.py` HP notes no longer claim a 90% armor cap or a 10-Health minimum. Selftest 15/15 OK;
validator 0 errors, 19 warnings (12 v0.27-only IDs; 7 history entries whose end no article dates).
**Prose**: deprecated-mechanics (new v0.17.8 → v0.26.1 table; stale rows fixed), versioned-mechanics, production-bonuses, battle-loot,
combat-stats, formulas, companies, employees-and-wages, missions, data-model, source-map, evaluation (Q10, Q20), unresolved-mechanics
(U-HIST-2 closed, U-ECO-3 closed, U-ECO-8 corrected, U-DEV-1a flagged), update-process (fetch the whole `official` category; newest
first; `<em>` star counting), SKILL.md, progression-values.yaml.
**Open, for the user**: U-DEV-1a. The raw v0.20.0 HTML suggests `^0.95` (power), not the recorded `× 0.95`.

## 2026-10-25 (rev 4) — v0.27 ingested as scheduled

**Source**: admin article `6ade08f7899288ce9f0bfe36` "v0.27" (category official), read in full via `article.getArticleById`;
registered as `PATCH_0_27` (priority 2). createdAt 2026-10-25T13:49Z, updatedAt 19:04Z, publishedAt 2026-10-28T14:14Z; the text
announces the deploy for **2026-10-26 ~14:00 UTC**, which is used as `effective_from` (U-V27-1). The live config fetched the same
day was still pre-v0.27 (Break Room 2–10, Entrepreneurship present, no Leadership).
**Registry** (129 → 145 mechanics, 7 sources): scheduled entries closing the old value at 2026-10-26T14:00Z for
`company.break_room_levels`, `production.deposit_bonus`, `production.deposit_depletion`, `production.strategic_resource_bonus`,
`production.specialization_ethic_bonus`, `employees.loyalty`, `economy.foreign_work_tax_return`, `economy.occupied_tax_hijack`,
`economy.wage_band_enforced`, `economy.job_leave_lock`, `skills.management_effect`, `country.income_ethics`, `party.rules`,
`election.candidate_min_level`, `map.starting_oil`, `map.wooden_case`, `region.unlinked_development_malus`, `mu.limits`,
`bonus.patriotic`, `bonus.main_enemy`, `bonus.defensive_pact`, `bonus.unethical_country_order`,
`bonus.fanatic_expansionist_pacification`, `bonus.bunker`, `rewards.daily_login_calendar`. New IDs: `skills.economy_values`,
`employees.{hiring,stats,wage,production,happiness,retention,training,events,managers,tools}`, `government.types`,
`country.strategic_resource_income`, `country.taxes`, `progression.starting_bag`, `progression.unlock_levels`.
**Patch log**: v0.27 entry (22 changes). `cooldowns.yaml` (government type, employee timers, removed links), `progression-values.yaml`
and `combat-bonuses.yaml` annotated.
**Prose**: employees-and-wages.md rewritten for employees/managers/tools with derived economics (old job market moved to
deprecated-mechanics.md); new **government-types.md**; deprecated-mechanics.md (v0.27 old → new table); companies, economy,
production-bonuses, skills-and-respec, parties-and-ethics, government, congress-and-laws, battle-bonuses, battle-orders, alliances,
defensive-pacts, main-enemy, regions-and-buildings, country-treasury-and-donations, resistance-and-internal-conflicts, map-and-travel
(v0.27 map changes), markets-and-trading, crafting-and-scrap, missions, milestones, daily-rewards, progression, military-units,
bounties, mercenary-contracts, cooldowns-and-timers, formulas (F-EMPLOYEE-WAGE, versioned F-SELFWORK/F-EMPLOYEE-PP), scenarios (S5b),
strategy-guidelines, account-rules-and-security, diplomacy, data-model, terminology, overview, versioned-mechanics, source-map,
unresolved-mechanics ("v0.27 open questions" U-V27-1…18), update-process (stated deploy time beats a later publishedAt; post-deploy
flip checklist; illustrative example renamed v0.99.0 to avoid clashing with the real v0.27), SKILL.md (banner, routing, scripts).
**Corrected**: "self-work pays no income tax" now carries the v0.27 contradiction (U-V27-2); SKILL.md no longer says v0.27 is
not ingested.
**Code**: `combat_bonus_calculator.py` gains `--government` (patriotic/sworn enemy/pact/bunker values by government type); it no
longer drops the patriotic bonus or crashes on `--isolationist` once the dict-valued v0.27 entries apply; ethics flags warn after
v0.27; `--selftest` replays the guide scenarios at 2026-10-25 (pre-v0.27 rules) so it keeps passing after the deploy.
**Downstream (not changed)**: the bot's `/economy` and `/progression` (job offers, Entrepreneurship, `SKILL_ORDER`, BuhDeuce paths);
`economy_calculator.py wage/employee` (pre-v0.27 model only); `snapshot-schema.yaml` (deposit and job fields); the sibling
`warera-config` quick table. **After the deploy**: run `check_config.py`, flip scheduled → current/historical, close U-V27 items.

## 2026-10-25 (rev 3) — v0.26.2 civil-war patch synced

**Source**: admin article `6accd48eca2ce961eea235ff` (re-fetched via `article.getArticleById`; full text, three rules unchanged),
registered as `PATCH_0_26_2` (priority 2). Patch landed 2026-10-11..13 ("yesterday"; createdAt 10-12, publishedAt 10-14).
`effective_from` is the publishedAt day, per the user's rule.
**Registry**: `bonus.bunker` and `unrest.civil_war`: old entries closed at 2026-10-14 (historical), new current entries add
`civil_war: not_applied` / `bounties`, `country_orders: not_allowed`, `bunker_bonus: not_applied`. Removed the stale "in civil wars
the government side gets the bunker bonus" from the current value. `registry_as_of` 2026-10-25. 129 mechanics, 6 sources.
**Patch log**: first admin-article entry (v0.26.2) with its own `source`; header and coverage updated.
**Prose**: resistance-and-internal-conflicts.md (old "Asymmetric bonuses" → versioned rule + history + derived consequence),
bounties.md, battle-orders.md, battle-bonuses.md, regions-and-buildings.md, combat-bonuses.yaml (`applies_when`),
versioned-mechanics.md (source + history row), unresolved-mechanics.md (CW-1 synced; CW-1a open: MU orders, contracts and HQ in
civil wars), SKILL.md, source-map.md.
**Also**: the "employee update in 1-2 weeks" became **v0.27** (`6ade08f7899288ce9f0bfe36`, publishedAt 2026-10-28, future-dated
when seen): it is **not ingested**, flagged in SKILL.md, employees-and-wages.md and source-map.md. update-process.md: `updatedAt`
isn't a content-edit signal; future-dated articles exist.
**Downstream**: `combat_bonus_calculator.py` has no civil-war mode. It would still add a bunker or country order if passed one
for a civil war. Not changed (no code edits this pass).
**Maintainer docs**: update-process.md step 5 (how to record a change of scope with no new number) and step 9 (the validator
reads only `mechanics.yaml`; parse other data files with `wlib.load_yaml`; spot-check `resolve` before and after the change);
README layout line for `patch-history.yaml`.

## 2026-10-25 (rev 2) — v0.26.2 label

**Source**: admin article `6accd48eca2ce961eea235ff` ("Little update about Civil Wars & Moderation Survey", 2026-10-14), which
the user calls v0.26.2. Its rules were already recorded as CW-1 but under the title only, so a version grep missed them.
**Changed**: CW-1 row now carries the label, the ID and the list of unsynced topic files; SKILL.md, source-map.md and
update-process.md (version-less titles: check by ID/topic) updated. Registry and topic files **not** synced yet.

## 2026-10-25 — economy guides

**Sources**: BUHDEUCE (in-game article `69998fd7d87267cb1de203d7`) and ECOBUILD (economic-build-warera.netlify.app, model read
from its JS bundle). New label `[STRAT-EXT]` for non-Romanian community advice.
**Added**: BuhDeuce's company paths (economy to 12 at AE7, war path 6 at AE6) in `companies.md`; his skill order, the
calculator's coins/day formula and its non-nested optimum (add-only order within ~2%) in `skills-and-respec.md`; War Era Coach
in the community tools table. Registry unchanged (strategy, not mechanics).

## 2026-10-06 — label fix

`references/ammunition-food-pills.md`: the Pill row's `[WIKI-ONLY]` label sat after both the durations and the Hunger claim, so
the 8 h / 15.5 h durations read as wiki-only. They are `[LIVE]` (`items.cocain.flatStats`, re-read 2026-10-06, and consistent
with live `user.buffs` timers of 23 MU members). Only "does not use Hunger" stays `[WIKI-ONLY]`. Registry unchanged
(`consumables.pill` already had them as current/LIVECFG).

## 2026-10-05 (rev 2) — warera.wiki and realmarijn cross-check

**Sources**: warera.wiki — 66 English gameplay pages (Wiki.js; 3 pages private) plus its transcription of official patch notes
v0.0.2 → v0.17.7; warera.realmarijn.nl/game-config re-fetched (still 2026-09-15 data, identical to the snapshot); live config
re-checked via `warera-config/scripts/check_config.py` (no drift).
**Owner instruction**: warera.wiki is outdated, so a wiki fact is kept only if the config or guide agrees. Wiki added as source
priority 6; wiki-only facts labelled `[WIKI-ONLY]` with low/medium confidence.

**Added**: `data/patch-history.yaml` (dated event log), `data/military-ranks.yaml` (120 ranks, wiki-only), XP table in
`progression-values.yaml` (verified: sums to 86,600; Prestige examples match), `references/parties-and-ethics.md`,
`scripts/country_calculator.py`, `combat_calculator.py damage|rank`, `progression_calculator.py level`, Prestige landing level,
duplicate-key check in `validate_mechanics.py`, open-ended-history handling and tie-break in `wlib.resolve`.

**Registry**: 113 → 129 mechanics, 3 → 5 sources; dated history for the Pill, deposit bonus/depletion, unlinked/occupier maluses,
respec, inactivity, takeover, citizenship, MU help, tax cap, congress seats, election calendar, vote level, miss damage, loot.

**Conflicts closed**: inactivity (3 days), takeover (guide's 5 days = v0.15.0 rule), auction (config), candidate level 15
(config + guide vs wiki 20), congress election on the 5th (config), base upkeep (config), order tiers and alliance curve (guide + wiki).
**Opened / kept**: order paper scaling (guide vs wiki), party election dates (guide vs wiki), strategic resources only for the
specialization (wiki claim), Defensive Pact upkeep formula, MoD permissions, money-transfer requirement, resistance after a revolt.

**Downstream**: none (no bot code uses this skill yet).

## 2026-10-05 — initial version (registry_as_of 2026-10-05)

**Sources ingested**
- GUIDE: *Ghidul Complet al Jucătorului Român WarEra [v0.26.1]* (2026-09-30, Dantenie83), all 64 chapters, reorganized by domain.
- LIVECFG: live `gameConfig` snapshot 2026-10-04 from the `warera-config` skill, used to confirm/contest guide values.

**Created**
- `SKILL.md` with authority model, source priority, time-aware rules, routing, answer style and anti-hallucination rules.
- 53 reference files (domains, formulas, scenarios S1–S25, data model, versioning, deprecations, sources, unresolved, update
  process, evaluation).
- `data/mechanics.yaml` (113 mechanic IDs, 3 sources), `recipes.yaml`, `cooldowns.yaml`, `combat-bonuses.yaml` (15 reference
  scenarios), `progression-values.yaml`, `equipment.yaml`, `snapshot-schema.yaml` (20 entities).
- Scripts: `wlib.py` (YAML loader + as-of resolution), `validate_mechanics.py`, `economy_calculator.py`, `break_even.py`,
  `combat_bonus_calculator.py`, `combat_calculator.py`, `progression_calculator.py`, `validate_game_snapshot.py`.

**Versioned on ingest**
- `election.vote_min_level`: 15 (guide/wiki) → 20 (live), change date unknown.
- `bonus.patriotic`, `bonus.alliance`, `production.deposit_bonus`: earlier values recorded as undated history.

**Conflicts opened** (see references/unresolved-mechanics.md): U-CMB-1, U-CMB-3, U-CMB-5, U-POL-1…U-POL-4, U-CON-1, U-ORD-1,
U-PRG-1, U-PRG-2, U-ECO-2; guide inconsistencies U-ECO-1, U-CMB-2, U-CMB-4, I-1…I-4.

**Verified**
- Mini YAML parser output identical to PyYAML on all data files.
- `combat_bonus_calculator.py --selftest`: 15/15 guide scenarios reproduced (3 via documented overrides for guide irregularities).
- Armor/Dodge formula reproduces every point of the guide's breakpoint table (24–200).

**Downstream**: none yet (no bot code depends on this skill).
