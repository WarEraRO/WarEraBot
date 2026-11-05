# Source map — where each piece of knowledge came from

## Sources

| ID | Document | Date / version | Language | Notes |
|---|---|---|---|---|
| GUIDE | *Ghidul Complet al Jucătorului Român WarEra [v0.26.1]*, author Dantenie83, 109 pages | 2026-09-30, game v0.26.1 | Romanian | compiles the big combat guide, patch notes up to v0.26.1, wiki/articles, leadership guide, Romanian combat guide, beginner guide, "War Era Oversimplified"; many screenshots were placeholders ("Image") in the provided PDF |
| LIVECFG | `gameConfig.getGameConfig` / `getDates` snapshot, `.claude/skills/warera-config/references/game-config.snapshot.json` | 2026-10-04 | — | used to confirm/contest guide values |
| WIKICFG | warera.realmarijn.nl/game-config | data 2026-09-15 | — | differences only; re-fetched 2026-10-05 — still the 2026-09-15 data, nothing new |
| PATCH_0_25_0 | Official patch notes "v0.25.0-beta (Alliance rework) (UPDATED)", in-game article `6a282e4c9bbf471e91a3c0a1` | published 2026-06-10 (edited 2026-10-12), game v0.25.0-beta | English | priority 2 but older than GUIDE. Several values later changed (see unresolved-mechanics.md); ingested 2026-10-25 under `ADMIN_PATCHES` |
| USER-2026-10-13 | In-game observations supplied by the user during the queue review | 2026-10-13 | — | priority 1 for the observed values only; see unresolved-mechanics.md "Resolved with the user" |
| ADMIN_ARTICLES | All in-game articles by the game admin (author `6813b758efecdf9bab195068`): official patch notes v0.15.0 → v0.26.1 plus announcements, and v0.26.2 (user-stated label; article `6accd48eca2ce961eea235ff`, no version in its title; CW-1); fetched via `article.getArticlesPaginated {userId}` | 2025-05-01 … 2026-10-14 | English | priority 2; the user's most trusted source (newest first). **All ingested 2026-10-25**: every article in `data/patch-history.yaml` with its ID, registry source `ADMIN_PATCHES` (v0.15.0 → v0.26.1) and `PATCH_0_26_2`. A newer patch overrides an older one where they overlap (user rule 2026-10-25). v0.27 (`6ade08f7899288ce9f0bfe36`, publishedAt 2026-10-28, deploy announced for 2026-10-26 ~14:00 UTC) is ingested as registry source `PATCH_0_27`, all entries `scheduled` (2026-10-25). Fetch procedure and pitfalls: [update-process.md](update-process.md) |
| PATCH_0_27 | Official patch notes "v0.27", in-game article `6ade08f7899288ce9f0bfe36`, 17 sections, read in full with `article.getArticleById` | created 2026-10-25, edited the same day, publishedAt 2026-10-28; deploy announced for 2026-10-26 ~14:00 UTC | English | priority 2; employees replace the job market, government types replace ethics, deposits/specialization removed, strategic resources become income, map 742 regions. Entries were `scheduled` from 2026-10-26T14:00Z (the live config was still pre-v0.27 on 2026-10-25) and **flipped to current on 2026-10-26** after the live config check (`LIVECFG_V027`). Open questions: unresolved-mechanics.md "v0.27 open questions" |
| PATCH_0_25_1 | Official article "v.0.25.1-beta" `6a2d86d5ab0e47773095df00` by staff member `69773c2781af219a70826739`, category `official`, English | published 2026-06-14 | English | priority 2, just below the admin's own articles. The only notes for v0.25.1 (no admin article): missions auto-claim (reverted in v0.25.5), resistance tax hijack removed, 30% foreign-worker tax to the home country, region transfer tax, Pill debuff 15.5 h. Found only through `categories:["official"]`, not the admin's `userId`. The `official` category also holds translations (es, de, pt, tr) and staff announcements; 81 articles on 2026-10-25 |
| WIKIPATCH | Official patch notes v0.0.2 → v0.17.7, transcribed at warera.wiki/en/patch-notes | 2024-04-16 … 2025-10-04 | English | dated event log → `data/patch-history.yaml`; priority 2 |
| BUHDEUCE | "PERFECT ECONOMIC GUIDE" by buhdeuce (Belgian Minister of Economy), in-game article `69998fd7d87267cb1de203d7`, read with `article.getArticleById` | published 2026-02-21 (edited 2026-10-25) | English | `[STRAT-EXT]`; skill order and company build paths (economy vs war); basis of War Era Coach (lundgrenwarera.github.io/warera-coach) and of the bot's `/progression` |
| ECOBUILD | economic-build-warera.netlify.app, income model read from its JS bundle | 2026-10-25 | English | `[STRAT-EXT]` model, not a game rule: coins/day = job + self-work (see skills-and-respec.md); basis of the bot's `/economy` and `SKILL_ORDER` |
| WIKI | warera.wiki (Wiki.js), 66 English gameplay pages; per-page edit dates 2025-07 … 2026-10-05 | fetched 2026-10-05 | English | **outdated** (user-reported, confirmed); priority 6; gap-filler only; 3 skill pages are private (HTTP 403) |
| CODEX | UNIKHORNE *Codex · WarEra rules reference*, warera.unikhorne.dev/codex (operator plays as "Khorne"); read in full from its JSON (`/api/codex`: 62 entries in 7 categories, rank ladder, 21 sub-sources; `/api/codex/patchnotes`: 97 admin articles v0.15.0 → v0.26.0, fetched by the site 2026-09-15) | entries 2026-08-21 … 2026-10-25 (Workforce added for v0.27); read 2026-10-26 | English (German UI) | priority 5, labelled `[CODEX]`. A third-party aggregator with per-claim trust tiers. Its "engine" tier = attack totals of 83+ live profiles, **outside battle only**. Measurements by its operator (Sept 2026) are kept as `[OBS]`; guide-derived claims as `[CODEX]`; strategy as `[STRAT-EXT]`. Rank table and several politics pages copy the wiki, so they aren't independent. Workforce entries read the dev client (0.27.0-beta) and Piraterer's *Employee Training Guide 2.0*. Ingest log below |
| LIVECFG_V027 | Live `gameConfig.getGameConfig` after the v0.27 deploy, diffed against the 2026-10-04 snapshot with `warera-config/scripts/check_config.py` (read-only; snapshot not overwritten) | 2026-10-26 | — | priority 1. 248 keys added, 65 removed, 63 changed. Confirmed the v0.27 skill ladders, Break Room L1–L3, unlock levels, candidacy 20, deposits off, strategic-resource and loyalty keys removed, 10% conquered-region tax, 36 tool items; revealed the bounty cap `maxBountyPpMultiplier` 9 and the alliance leave cooldown suspended until 2026-10-30. Used to flip the registry's v0.27 entries to current |
| LIVECLIENT_V027 | Live game client bundle app.warera.io (`pages/_app-99cff0988b6e9224.js`), public JS, no key | read 2026-10-26 16:52 UTC, game v0.27 | — | priority 1 for the constants it ships, labelled `[LIVE-CLIENT]`: skill ladders, `featureUnlockLevels`, `regenDividedBy`, prestige, employee config, 52 traits, event "storyteller" settings. Confirms the v0.27 deploy. Server-only rules aren't in it |
| LIVECLIENT_V027_TEXT | Live client re-read: `pages/_app-9494af8008d97717.js` (build `6PTFmZmYUI5PuDLhZjvGK`) and its English text catalog (locale chunk 1424, 4,321 strings), public JS, no key | read 2026-10-26 evening, game v0.27 | English | priority 1, labelled `[LIVE-CLIENT]`. Adds what the first read didn't use: the training-card config, the tool → goods map, all 78 event definitions and the in-game wording (production bonus "added together", rarity "rolled once for the whole hand", Responsibility shield, Luck's event terms, manager tax withheld at Collect, firing within 24 h = a reroll, trait conditions) |
| V027_GUIDES | Ten community v0.27 guides (in-game articles, category `guide`), read in full with `article.getArticleById`, embedded screenshots included: Piraterer *Employee Training Guide 2.0* `6ade935e2284d0115d0de773` · Elereo *Technical Guide: NPC Training & All 52 Traits* `6ade7b85adf33aad41ed6352` · Elereo *Tech Guide: Worker Events* `6adef089dc5a9c288b3725c8` (text stops inside event 68) · Wodkabouter *All About NPC Employees* `6adf359bfa3cee34a8361e3b` · fish *v0.27 \| Learn about employees* `6adf6f3ebc8c27e58f5b6230` · Nadim *v0.27 Explained in 5 Minutes* `6adf47abd588e99f30150df0` · Luminous_Valentine *Update Version 0.27 made easy* `6adf6bbf75ae36f14944c42e` · Don_Khorne *WARERA.UNIKHORNE: Workforce* `6adf59c54a260573b7b62945` (the codex's Workforce page) · babeuce *THE PERFECT EMPLOYEE GUIDE* `6adf78a73fb290a6d9ad35a1` · Ali_Soriati infographic `6adf3420916f1f117e17b237` (one image, generic tips) | published 2026-10-25 21:58 … 2026-10-26 16:05 UTC; Elereo's and Piraterer's from the dev-server configuration of 2026-10-25, most screenshots from the 0.27.0 dev server | English (UNIKHORNE also German) | priority 5. Dev-server screenshots → `[OBS]` of the beta; advice → `[STRAT-EXT]`. Each number was checked against `LIVECLIENT_V027_TEXT` where the client has it (conflicts G27-1 … 10 in unresolved-mechanics.md). Strongest new content: the rarity formula (Elereo, confirmed by dev screens), the trait-Production-isn't-paid evidence, the economics tables (Wodkabouter), the trait tier lists, the event catalogue. Nadim's and Luminous's are patch summaries with nothing beyond the admin article |
| PATCH_0_27_1 | Official patch notes "v0.27.1", in-game article `6ae0defd260ab3cd58036d7a` (admin), read in full | created 2026-10-27 17:27, published 17:37, edited 17:55 UTC | English | priority 2. Free firing of fresh hires; events right after hiring; no battle deaths "for now"; Homesick fine in occupied home regions; alliance leave cooldown reset and off until 30 Oct; manager wages ÷10 and paid even with no employees; non-bordering map links closed; market and UI fixes. Found by re-checking the `official` category on 2026-10-27 |
| PATCH_0_27_2 | Official patch notes "v0.27.2", in-game article `6ae2608f707baf45eebf26c5` (admin), read in full 2026-10-29 | created/published 2026-10-28 20:52 UTC | English | priority 2. Development and strategic-resource income ×2; new players start with 100 money (was 25); no contradicting traits on new employees; employees on the map; candidates countdown; country-specific employee names; training cards show before → after; API tokens read employees and events; event odds bar failures left / successes right; iOS long-press fix. Newest `official` article on 2026-10-29 |
| LIVECFG_V0272 | Live `gameConfig.getGameConfig` (check_config.py, read-only) and client `pages/_app-bd1b3e64c9b49e55.js` | read 2026-10-29, game v0.27.2 | — | priority 1, `[LIVE]` / `[LIVE-CLIENT]`. 250 / 65 / 63 keys added / removed / changed vs the 2026-10-04 snapshot (248 / 65 / 63 on 2026-10-26): the two new keys are `region.developmentIncomeMultiplier` 2 and `region.strategicResourceIncomeMultiplier` 2. Client: 32 incompatible trait pairs (was 14) used by the training-card pool; income shown ×24, so API income fields are hourly |
| LIVEAPI_20261029 | Live API sample with the bot's key (read-only): 120 company rosters (261 employees), 40 regions, their owners, all countries | 2026-10-29 | — | priority 1 for the values read. Region `income.development` = development × 2 / 24 everywhere; `strategicResourcesBonus` = original country's **core** development × 2 / 24; government types stack on top. Trait counts per employee 0–5; extra traits explained by training history; two pre-patch clashes kept |
| PATCH_0_27_3 | Official patch notes "v0.27.3", in-game article `6ae39f39b9d173140341a461` (admin, category `official`), read in full 2026-10-30 | created/published 2026-10-29 19:32 UTC (`updatedAt` 2026-10-30 06:45, no "(UPDATED)" in the title) | English | priority 2. Hiring (all stats and wage shown, one trait per hire, Specialist = company good, 12 h fire lock); Leadership merged into Management; free skill reset; Responsibility +3 happiness; free transfers and firing; Luck counts from point 1; Early bloomer replaces Sprinter; Rehab bad-only; profit estimates per good; event participant fix |
| LIVECLIENT_V0273 | Live client `pages/_app-7b600575a3d47dea.js` and `gameConfig.getGameConfig` (check_config.py, read-only), public, no key | read 2026-10-30, game v0.27.3 | — | priority 1, `[LIVE-CLIENT]` / `[LIVE]`. `traitsPerEmployee` 1–1, `fire.hireLockHours` 12, move = company penalty only, `responsibilityHappinessPerPoint` 3, `skills.managementWeightShiftPerLevel`, event `statPivot` 0, Early bloomer trait, 30 incompatible pairs, Rehab bad-only; the config's and client's skill lists have no Leadership (13 point-buyable skills) |
| LIVEAPI_20261030 | Live API sample with the bot's key (read-only): 60 company rosters, 117 employees | 2026-10-30 | — | priority 1 for the values read. All 13 hires after the patch had exactly one trait at hire; no Sprinter or Early bloomer in the sample; both Specialists' goods matched their company's product; happiness breakdown shows "responsibility +9" at Responsibility 3 and a company move as "recentlyMoved −10" for 7 days |
| SILENT_20261031 | Community article "Silent patch notes again? - Trainer abuse fixed, Training shows profit, Reorganize function", in-game article `6ae682c7470184738824c070` (Piraterer, category `news`), 9 screenshots viewed | published 2026-11-01 00:08 UTC (edited 17:09) | English | priority 7 (community report of an unannounced admin patch). Trainer and Lucky charm tooltips, card profit estimate, Reorganize workforce, skin propositions removed. All rules confirmed by the two live sources below |
| LIVECLIENT_20261101 | Live client `pages/_app-dae8b3a034a90613.js` and the English UI catalog history (vatoutou/warera-translation commits ce1acae → 89b0525 → 0ac5360 → 77f0bc4), public, no key | read 2026-11-01 | — | priority 1, `[LIVE-CLIENT]`. Trainer `trainerSessionsPerDay` 2 (pool on the Trainer, UTC-day reset); `luck.charmGraceHours` 1 (new); no `maxToolboxChancePerHour` (toolbox cap gone; catalog dates it 2026-10-29 20:20Z) |
| LIVEAPI_20261101 | Live API sample with the bot's key (read-only): 60 company rosters | 2026-11-01 | — | priority 1 for the values read. `charmLuck {amount 3, until next 00:00 UTC + 1 h}` on Lucky charm coworkers; `trainerSessionsUsed` / `trainerSessionsUsedAt` on Trainers; one coworker trained 3 times in a day |
| PATCH_0_27_4 | Official patch notes "v0.27.4 + New skins giveaway", in-game article `6ae8bb12bcc26a2f5712ec9d` (admin, category `official`), read in full 2026-11-02, both images viewed (skin packs) | created 2026-11-02 16:32, published 16:36, edited 17:54 UTC | English | priority 2. Ageing per day worked or trained; disabled companies on hold; Talks to Machines; Bully bad; Reroll card; Wild card Rare +2; no mixed-trait teaching; tool returns on move; event rebalance (credited to Johnny_Sins); trait-Production wage claim (disputed live); crafting 7; new-country voting; missions-after-break fix; 6 skin packs |
| LIVECLIENT_V0274 | Live client `pages/_app-08814d1f154569f9.js`, `gameConfig.getGameConfig` (read-only) and the English UI catalog (vatoutou/warera-translation 77f0bc4 → 4838d69, 2026-11-02 16:22:50Z) | read 2026-11-02 | — | priority 1, `[LIVE-CLIENT]` / `[LIVE]`. 53 traits (Talks to Machines), Bully negative, 36 pairs; training `wildCardStatGain` 2, Wild card Rare, Reroll Uncommon, `habitRarityByPolarity` positive only; all 78 event definitions; config `featureUnlockLevels.craft` 7 and the new `election.voteCitizenshipLockNewCountryMultiplier` 2. Full employee-constants object in the registry source notes |
| LIVEAPI_20261102 | Live API sample with the bot's key (read-only): 70 company rosters, 162 employees | 2026-11-02 | — | priority 1 for the values read. Paid wage = (rolled base + trained) / 4 × PP 0.099 × expectation for all, trait Production unpaid (82 employees, 4 recalculated after the deploy); new fields `lastAgedDay`, `companyDisabled`; `engineMultiplier` 1 everywhere; `base.production` = base + trained |
| PATCH_0_28 | Official patch notes "v0.28 (Nuking movement + perf)", in-game article `6aea1496b615c31fa0eb4152` (admin, category `official`), read in full 2026-11-04 (no images) | created/published 2026-11-03 17:07, edited 2026-11-04 17:31 UTC | English | priority 2. Fight from anywhere; movement, Stamina, map wooden cases, map milestones and travel missions off "in 7 days" (~2026-11-10); wooden-case listings/orders refunded; Alliance filter in battle rankings; Last Hits rework; Settings window and performance work; Nationalist/Statist/Foreman direct happiness (Nationalist +11 → +10); employee stats panel; v0.27 removed links closed; company-enable training fix |
| LIVECLIENT_V028 | Live client `pages/_app-90d4b44c9f47c314.js`, `gameConfig.getGameConfig` (read-only) and the English UI catalog (vatoutou/warera-translation 4838d69 → 3f60446, 2026-11-03 17:02 UTC) | read 2026-11-04 ~19:30 UTC, game v0.28 | English | priority 1, `[LIVE]` / `[LIVE-CLIENT]`. New config keys `battle.locationGateEnabled` false and `mapTravel` {5 flags, all true}; trait table (Nationalist happiness 10, Statist 6 at tax ≥ 20, Foreman coworkerHappiness 9); event checks 59 standard / 47 Luck; catalog diff +23 / −10 |
| LIVEAPI_20261104 | Live region graph with the bot's key (`region.getRegionsObject`, read-only) | 2026-11-04 | — | priority 1. 742 regions, 1,856 symmetric links, removed v0.27 links gone, longest shortest path 20, 37 regions not linked to their capital |
| LIVECLIENT_V0271 | Live game client bundle `pages/_app-68269fc0817be98a.js` (build `3lr-BW6ZMlv8vlLIWaQ-A`), public JS, no key | read 2026-10-27 ~18:00 UTC, game v0.27.1 | — | priority 1, `[LIVE-CLIENT]`. Confirms v0.27.1's event (`minHiredHours` 0) and firing changes; holds the **government-type modifier table** (every article value matches; Provisional = none), the order-cost function and the wooden-case config (25% / 5 / 48 h, starter cases, PP budgets, one 20-good pool). Still ships `casualtyChance` 0.01 and Homesick's old condition (server-side changes, G-ART-4/5). No battle-bonus cap constant |
| TRANSLATION_EN | vatoutou/warera-translation `en/messages.po` (the game's lingui English catalog), commit `a8060359fca8` | 2026-10-27 17:46 UTC (v0.27.1); history back to 2026-08 | English | priority 3 for UI wording, never alone for mechanics. 4,337 strings with source components → [ui-guide.md](ui-guide.md). Same catalog as `LIVECLIENT_V027_TEXT` (commit `e20fa04b` of 2026-10-26 22:09 has 4,322 strings, the client read 4,321). Dated diffs: `cea816fe` (2026-09-30) → `e20fa04b`: +2,023 / −242 (v0.27 labels, old → new table in ui-guide.md); `e20fa04b` → `a8060359`: +78 / −63 (v0.27.1). Trait names fixed from it (Misandrist, Tax-shy) |
| GUIDE_ARTICLES | **All 666** in-game articles with category `guide` and language `en` (enumerated with the filters, cross-checked against the 1,717-item unfiltered guide category), each fetched in full | published 2025-05-02 … 2026-10-27 | English | priority 5. About a quarter is slop or off-topic (169), many are community pages (107); 136 are historical only (mostly the pre-v0.27 economy); 21 integrated (10 this session + 11 earlier); conflicts G-ART-1 … 7. Per-article review depth, validity and disposition: [guide-articles-ledger.md](guide-articles-ledger.md). Images weren't OCR'd |

### Wiki cross-check against live config (realmarijn mirror / API) and the guide, 2026-10-05

| Wiki claim | Check | Verdict |
|---|---|---|
| Referral: 10 coins new player, badge at level 15, choose referrer ≤ level 10, 10% badge share, badge 20 / Baby Boomer 100 | LIVECFG `referral.*`, `badge.*.reward` | **verified** |
| Case: 30% weapon | LIVECFG `loot.weaponChancePercent` 30 | **verified** (rarity split wiki-only) |
| Party creation 150 | LIVECFG `party.createCost` 150 | **verified** (unit: wiki says concrete) |
| MU help 2 HP × 5, every 12 h | LIVECFG `mu.*` + guide | **verified** |
| Resistance bar = development × 100; citizens +2 | LIVECFG `resistanceBarMultiplier`, `resistanceCitizenBonus` | **verified** |
| Mercenary reputation 1 per 1k coins / 1 per 1M failed | LIVECFG `reputation.*` | **verified** |
| Auction step/min 0.01, +60 s extension | LIVECFG `auction.*` | **verified**; threshold 30 s ✗ (config 60) |
| Order bonus 5/10/15, alliance +20/10%/−4/−20, patriotic 20 | GUIDE | **verified** |
| XP table (sums to 86,600; Prestige → level 25 / 49) | GUIDE totals and examples | **verified** |
| Movement and wooden cases | GUIDE | **verified** |
| Candidacy at level 20 | LIVECFG 15, GUIDE 15 | **outdated/wrong** |
| Base L5 upkeep 15 oil/h | LIVECFG minimum 25, development-scaled | **outdated** |
| Crit example with 59% crit damage | LIVECFG crit-damage skill 100–300% | **outdated scale** |
| Party elections 16th/21st/27th; congress on the 4th | GUIDE 12/22/24; LIVECFG congress 5th | **outdated** |
| Attacks only from adjacent regions | GUIDE (any region, after map update) | **outdated** |
| Deposit bonus fixed 30%, tax hijack 0.5%, free grain company | GUIDE / patch log | **outdated** |
| Flat +10% alliance (country page) | GUIDE curve | **outdated** (kept as history) |
| Management = max workers; rank table; case rarity split; ethics list; paper formulas; Pill uses no Hunger; takeover conditions; law voting details | not in LIVECFG or GUIDE | **unverified — `[WIKI-ONLY]`** |

### Wiki page → skill file (and what it added)

| Wiki page (edited) | Skill file | Added / changed |
|---|---|---|
| patch-notes (2025-10-05) | patch-history.yaml, versioned-mechanics.md, deprecated-mechanics.md | dated history for ~30 mechanics |
| experience-xp (2026-02-01) | progression.md, progression-values.yaml | XP-per-level table (sums to 86,600); older mission values |
| military-rank (2026-01-09) | combat-stats.md, military-ranks.yaml | full rank table |
| combat-stats (2026-07-20), player-stats (2026-07-17) | combat-stats.md | crit/miss formulas, HP floor 1, can't hit < 10 HP, hourly 10% regen |
| battle (2026-08-28), war (2026-08-24) | battle-*.md | order paper formula, HQ any battle, old adjacency rule, resistance bar |
| alliance (2026-09-03), law (2026-10-02), country (2026-08-12) | alliances.md, congress-and-laws.md | alliance laws/upkeep/history, law list and voting |
| defensive-pact (2026-08-03), sworn-enemy (2026-07-17) | defensive-pacts.md, main-enemy.md | multi-pact, free break, building exclusion, upkeep |
| election (2026-10-05), congress (2026-07-18), government (2026-07-23) | congress-and-laws.md, government.md | calendar, level 20 candidacy claim, takeover conditions |
| political-party (2026-07-18) | parties-and-ethics.md | ethics list and party mechanics |
| civil-war (2026-08-10) | resistance-and-internal-conflicts.md | Start Revolution motion, outcomes |
| country-income (2026-08-12), jobs (2026-08-12), company (2026-03-15) | economy files | income sources, 30% foreign tax, wage flow |
| strategic-resources (2026-07-22), region (2026-08-12) | production-bonuses.md | SR types, monthly reshuffle, specialization requirement |
| mercenary-contract (2026-08-09) | mercenary-contracts.md | auction rules confirming live config, reputation formula |
| military-unit (2026-07-24) | military-units.md | MU order paper, applications, HQ activation detail |
| case (2026-07-18), wooden_case (2026-10-01), trading/equipment market, coins | markets-and-trading.md, battle-loot.md | case odds, two markets, market tax |
| movement (2026-10-01) | map-and-travel.md | confirms travel costs |
| prestige, progression (2026-09-11), referrals, badges | prestige.md, progression.md | doubling Prestige cost, referral/badge rewards |
| skills (2026-07-26) | skills-and-respec.md | Management = max workers; 770 points to max |

Wiki pages are community-edited and some keep stale text (company page: deposit 30%, 0.5% tax hijack, free grain company;
country page: flat +10% alliance). Each statement carries the page date; newer authoritative sources win.

### UNIKHORNE codex cross-check (2026-10-26)

Each codex entry was compared with the skill. "Dup" = already in the skill, no change; "new" = added; "conflict" = logged as U-CDX-n
in [unresolved-mechanics.md](unresolved-mechanics.md); "stale" = the codex is behind the skill.

| Codex category (entries) | Result | Skill file(s) changed |
|---|---|---|
| Combat (14): damage per hit, attack chain, precision, crit, armor/dodge, health, food, Pill, loot chance, war spoils, battle bonuses, rank | dup for formulas, overflow, breakpoints, food, Pill 15.5 h, rank table (identical, same wiki origin); **new**: firearm without ammo, crit corroboration (RealMarijn), 90–110% spread lead, derived ceilings, hits-per-Health closed form, landed-hits loot audit, pool cutoff and yield per 1k, API traps; **conflict**: battle-bonus stacking and +95% cap (U-CDX-1) | combat-stats.md, battle-loot.md, formulas.md, data-model.md |
| Progression (7) | dup for XP table, skills, missions, daily/comeback rewards, Prestige rules, referrals; **new**: XP clock 418.6/day, Prestige timing (codex figures re-derived: they are pre-v0.25.5), observed bonus levels on the ladder, v0.27 skill unlocks (verified on the live client) | progression.md, prestige.md, skills-and-respec.md, formulas.md |
| Equipment and cases (8) | dup for slots, stat ranges, crafting costs, 1/3 scrap on break, case odds, v0.27 wooden cases; **new**: wear 1% per hit (measured), elite case table (U-CDX-3), case scrap EV, random-craft slot split, chosen-slot economics, wooden-case quantity rule | equipment.md, crafting-and-scrap.md, markets-and-trading.md, battle-loot.md, data/equipment.yaml, map-and-travel.md |
| Economy (8) | dup for bars, recipes, companies, upgrades, taxes, strategic resources; **new**: ±10% work roll, displayed market price includes tax, pre-v0.27 wage-range history, tax off the worker's pay, cheapest-+1-PP/h build order; **conflict**: country × deposit multiplying (U-CDX-2, history) | economy.md, markets-and-trading.md, deprecated-mechanics.md, companies.md, production-bonuses.md |
| Workforce (7, v0.27) | mostly **new detail**, each number checked against the live client (all matched); article-vs-client conflicts U-CDX-4/5/6 | employees-and-wages.md, skills-and-respec.md, data/mechanics.yaml `employees.*` |
| Warfare (10) | dup for structure, orders, fortifications, MUs, contracts, tournaments, travel; **new**: combined-terrain tick confirmation, `location` vs `region`, free trip home seen in-game, tournament bonus = +25 flat Attack; **stale**: civil war keeps orders/bunker | battle-mechanics.md, map-and-travel.md, tournaments.md |
| Politics (8) | dup for development, paper costs, laws, cooldowns, ethics (history); **new**: alliance share = core development and named membership; **stale**: election level 15, old alliance curve, party election days, SE ×2 upkeep | alliances.md |
| Patch notes (97) | every versioned article already in `data/patch-history.yaml`; **new** from the unversioned admin posts: Rule 6 ruling (2026-02-08), Rule 7 rewrite (2026-01-27), boosting note (2025-09-08), double XP weekend (2025-08-16/17) | proxies.md, account-rules-and-security.md, progression.md, data/patch-history.yaml |

The guide labels its own content as *Regulă de joc* (game rule), *Politică recomandată* (recommended policy), *Observație practică*
(practical observation), and marks gaps as *[DE VERIFICAT]* / *[INFORMAȚIE INCOMPLETĂ]*. This skill maps them to `[RULE]`,
`[POLICY-RO]`/`[STRAT-RO]`, `[OBS]`, `[GAP]`.

## Guide chapter → skill file

| Guide chapter | Skill file(s) |
|---|---|
| Executive summary, How to use | overview.md, strategy-guidelines.md |
| 1–2 Discord, access, conduct | romanian-community-ops.md |
| 3.1–3.8 Account rules, security, reporting | account-rules-and-security.md |
| 3.9 Inactivity | progression.md, government.md |
| 3.10 Country choice at sign-up | citizenship.md |
| 4 Server structure · 5 TheMachine commands · 6 Bot jobs | romanian-community-ops.md |
| 7 In-game announcements, articles | announcements.md |
| 8 Daily routine | romanian-community-ops.md, strategy-guidelines.md |
| 9–11 Progression, missions, milestones | progression.md, missions.md, milestones.md |
| 12 Activity rewards | daily-rewards.md |
| 13 Economy skill plan · 14 Economic bars | skills-and-respec.md, economy.md |
| 15 Companies · 16 Recipes | companies.md, production.md, data/recipes.yaml |
| 17 Bonuses (deposit, strategic, specialization, loyalty, reciprocal hiring) | production-bonuses.md, employees-and-wages.md |
| 18 Profit / max wage · 19 Employees · 20 Break-even | formulas.md, employees-and-wages.md, companies.md |
| 21 Cases, scrap, crafting, trade, liquidity | markets-and-trading.md, crafting-and-scrap.md |
| 22 Economic prep before respec | skills-and-respec.md, combat.md |
| 23 Prestige | prestige.md |
| 24 Map, travel, wooden cases | map-and-travel.md |
| 25 Build philosophy · 26 Respec | combat.md, skills-and-respec.md |
| 27 Combat stats · 28 Equipment, breakpoints | combat-stats.md, equipment.md, data/equipment.yaml |
| 29–30 Ammo, food, Pill | ammunition-food-pills.md |
| 31 7–14 day prep | combat.md |
| 32 Battle mechanics · 35 Tactics | battle-mechanics.md |
| 33 Bonuses, ethics | battle-bonuses.md, data/combat-bonuses.yaml |
| 34 Orders | battle-orders.md |
| 36 Loot | battle-loot.md |
| 37 Bounties · 38 Contracts · 39 Self-financing | bounties.md, mercenary-contracts.md, combat.md |
| 40 MUs | military-units.md |
| 41 Tournaments | tournaments.md |
| 42 Donations | country-treasury-and-donations.md |
| 43 Cooldowns | cooldowns-and-timers.md, data/cooldowns.yaml |
| 44 Proxies | proxies.md |
| 45 NAPs · 46 Alliances, pacts, Main Enemy · 47 Economic agreements | diplomacy.md, alliances.md, defensive-pacts.md, main-enemy.md |
| 48 Regions, resistance, unrest | regions-and-buildings.md, resistance-and-internal-conflicts.md |
| 49 Leadership roles, permissions | government.md |
| 50 Elections, laws, citizenship | congress-and-laws.md, citizenship.md |
| 51 War-prep flow | romanian-community-ops.md |
| 52 Tools · 53–61 Checklists | strategy-guidelines.md (+ topic files) |
| 62 Scenarios A–J | scenarios.md |
| 63 Glossary | terminology.md |
| 64 Conclusion, sources | strategy-guidelines.md, source-map.md |

## Live-config cross-check summary (2026-10-04)

Confirmed (guide = live): skill costs and tables, respec 0.5/point & 7 days, Prestige 65,000 / 50% / +10% / 1 bonus level, daily/
weekly/monthly mission rewards, reroll 2n, company cost +50, move/change 5, refund 80, engine/storage tables, loyalty 1%/10%,
strategic resources 5/0.5/0.25, MU 3 owned / help 12 h / 2 HP / 7-day nationality / HQ & dormitories tables, bunker/base 5–25 & 12 h,
patriotic 20, Main Enemy max 10, maluses −25/−50, resistance 30/15, loot pools 200k/500k, bounty 3 min / ×6 / 50% gov, contract
fee 10% / reputation 5 / decay 20%, 5–25 min auctions, citizenship 30 days, alliance leave 7 days, non-aggression 24/72 h,
announcements 2/h 1,000 chars 24 h, candidate level 15, renomination 5 days, unrest 10 Energy/Health per point, 48 h, 7 days, 72 h.

Contested: see [unresolved-mechanics.md](unresolved-mechanics.md).

Live-only additions used: storage capacities, break room, item stat ranges, climates, skill unlock levels and per-level values,
health cost 10 per hit, level gates (market 7, chat 8, takeover 25, contributions 15), law voting 24 h / 0.5, max tax 45,
cancellation penalty 10%, lost-attacking-region −25%.
