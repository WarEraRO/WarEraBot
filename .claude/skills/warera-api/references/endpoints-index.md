# Endpoint index (96 live procedures: 37 official + 59 explorer-only, plus 🕵️ client-only; re-checked 2026-10-28 after WarEra v0.27.1 and 2026-11-02 after v0.27.4)

> **v0.27 (2026-10-25) changed the economy API.** The job market (`workOffer.*`, `worker.*`) is gone (see the Economy section), party ethics, deposits and country specialization were removed, and the Entrepreneurship skill was replaced by Leadership. Facts marked before 2026-10-25 about jobs, wages, skills or production bonuses may be stale. Since 2026-10-28 the NPC **employee** queries (`employee.*`, `employeeEvent.*`) answer with an API key (see Employees in the Economy section).

> **2026-11-02 re-check (v0.27.4).** Every indexed procedure answered 200 and the removed `workOffer.*` / `worker.*` still give 404. Response changes are tagged **[observed 2026-11-02]** in their entries: regions lost `deposit`, companies lost `workerCount`, users lost `company` (the job) and `dates.lastCompanyJoinedAt` / `lastHiresAt`, employees lost `region`, `revealed`, `retireAskAt` and `happinessBreakdown.shield`, and `getPaginatedAuctions` without `status` now lists only active auctions. New procedure: 🕵️ `gameStat.getPpMoneyValueByItem`.

Call: `GET https://api2.warera.io/trpc/<procedure>?input=<urlencoded JSON>`, then unwrap `result.data`.
**Inputs:** `*` = required. Exact types and constraints are in `endpoint-inputs.generated.md`; response shapes are in the domain files.
**Project:** names the `warera` client method, or `—` if unused. "🔑" means a key is required (401 without one).
**🧭** = **not in the official spec** (0.17.4-beta). It's documented by the community explorer https://warera.realmarijn.nl/api-explorer and was **verified live on api2.warera.io on 2026-10-03**. These are real, but unofficial: they could change without notice, so flag them in reviews. Explorer param docs aren't always right (see `mercenaryContractAuction`, `alliance.getManyPaginated`, `contribution.*`).
**Search tip:** grep this file for the *noun you need* (e.g. "upkeep", "damage", "price", "citizens", "commander").

---

## Countries, government, regions, events

`country.getAllCountries`
Purpose: All ~180 countries with full country objects.
Use when: resolving a country **name → ID**, building autocomplete, or scanning every country (allies, wars, taxes, development, population, rankings). One call; cache it.
Inputs: none.
Returns: `[{_id, name, code, money, taxes{income, market, manager}, income{development, strategicResourcesBonus, employeeIncomeTax, managerIncomeTax, govType, total}, govType?, allies[], warsWith[], enemy, defensivePacts[], nonAggressionUntil{countryId: iso}, allianceId, rulingParty, averageDevelopment, currentPopulation, rankings, …}]`. Since v0.27: `govType` is the **government type** (`federation`, `plutocracy`, `mercenaryState`, … ; absent = Provisional, 145 of 181 countries), `specializedItem` is gone, and `taxes.manager` / `income` are new **[observed 2026-10-26]**. `bordersOpenUntil` (ISO) is on 6 of 181 countries, mostly dates in the past **[observed 2026-11-02]**; it probably marks a new country's open-borders window (`gameConfig.citizenshipApplication.newCountryBordersOpenDays`, 7) **[assumption]**.
Project: `warera.countries.get_all`, `warera.countries.get_names`.

`country.getCountryById`
Purpose: One country, with a few more fields than the list (`currentBattleOrder`, `discordUrl`, `pinnedArticle`, `strategicResources`, `orgs`, `dates{govTypeChangedAt}` **[observed 2026-11-02]**).
Use when: you already have a country ID and need fresh details. If you already fetched `getAllCountries`, the list item probably has what you need.
Inputs: `countryId*`.
Returns: country object (see domain-countries-regions.md).
Project: `warera.countries.get`.

`government.getByCountryId`
Purpose: Who holds office in a country.
Use when: you need the president, vice-president, ministers (foreign affairs, economy, defense) or congress members, or want to detect a government takeover or an empty government.
Inputs: `countryId*`.
Returns: `{president, vicePresident, minOfForeignAffairs, minOfEconomy, minOfDefense, congressMembers[], dates{lastAnnouncementAt,…}}` (user IDs).
Project: `get_country_government` (takeover_countries).

`region.getRegionsObject`
Purpose: Every region (~742 on 2026-11-02) in one map `{regionId: region}`. The response is about 0.9 MB.
Use when: you need many regions at once: all of a country's regions, upgrade levels, resistance, neighbors, or development. Cache it; don't call it per request in a hot loop.
Inputs: none.
Returns: `{<regionId>: {name, code, country, initialCountry, development, activeUpgradeLevels{bunker,base,pacificationCenter}, resistance, resistanceMax, neighbors[], isCapital, population, residents, companyCount, employeeCount, income{…}, strategicResource, …}}`. No region has `deposit` any more (`gameConfig.region.depositsEnabled: false`) **[observed 2026-11-02]**.
Project: `warera.regions.get_all` (get_region_upgrade_cost).

`region.getById`
Purpose: One region.
Use when: you have one region ID, e.g. a battle's region, and need its name, owner or upgrades.
Inputs: `regionId*`.
Returns: region object (same shape as a map value above).
Project: `warera.regions.get` (battle-order_monitor).

`upgrade.getUpgradeByTypeAndEntity`
Purpose: The full upgrade record for a region, company or MU.
Use when: you need upgrade **status** (`active`, `disabled`, or pending via `willBeActiveAt`), invested materials, or last upgrade/downgrade time. If you only need levels, `activeUpgradeLevels` on the entity is enough (it lists active upgrades only). There is **no upgrade history** anywhere in the API; only the latest upgrade and downgrade times are kept (see the domain file).
Inputs: `upgradeType*` (bunker, base, pacificationCenter, storage, automatedEngine, breakRoom, headquarters, dormitories) plus one of `regionId`, `companyId`, `muId`.
Returns: `{upgradeType, level, status, investedMoney, investedConcrete, investedSteel, willBeActiveAt?, lastUpgradeAt?, lastDowngradeAt?, …}`
Project: `warera.mus.get_upgrades` (mu_readiness), `get_region_upgrades` (region_upgrades).

`event.getEventsPaginated`
Purpose: The world event feed (wars, peace, battles, presidents, region transfers, alliances, revolts, deposits…).
Use when: you want **notifications of game events**, such as "war declared on X", "new president", "region lost", "alliance formed" or "deposit discovered". Prefer it over diffing snapshots of countries or regions yourself.
Inputs: `limit` (≤100), `cursor`, `countryId`, `eventTypes[]` (26 enum values; see the domain file).
Returns: `{items:[{_id, countries[], priority, data{type, …type-specific}, createdAt}], nextCursor}`, newest first.
Project: `get_events(event_types, session, created_after=)` (region_upgrades: owner history of regions).

`region.getAll` 🧭
Purpose: Every region (~742) as an **array** (same objects as `getRegionsObject`).
Use when: you want a list rather than an ID map. Otherwise it's equivalent; don't call both.
Inputs: none.
Returns: `[region]`.
Project: —

`upgradeConstruction.getMapConstructions` / `upgradeConstruction.getRegionConstructions` / `upgradeConstruction.listConstructions` 🧭
Purpose: In-progress region-upgrade construction projects for the whole map, one region, or by region/country (paginated).
Use when: "what is being built right now?" or a construction progress feed.
Inputs: none / `regionId*` / `regionId` or `countryId` (one required, else 400), `limit`, `cursor` (last item `_id`).
Returns: arrays / `{items:[]}`. The **item shape is unknown** (always empty when probed).
Project: —

`gameStat.getWorldDevelopment` 🧭
Purpose: Total world development (sum over all countries).
Use when: computing a country's share of world development.
Inputs: none.
Returns: a bare number (e.g. `18238.02`).
Project: —

## Politics and diplomacy: alliances, wars, parties, elections, unrest 🧭

All 🧭. Details are in domain-politics-diplomacy.md.

`countryDiplomacy.getByCountry` 🧭
Purpose: A country's sworn enemy and defensive pacts, **with bonus % and damage dealt under each**.
Use when: showing or monitoring diplomacy ("who are our pact partners / sworn enemy and how much did they help?"). It's richer than `country.enemy`/`defensivePacts`.
Inputs: `countryId*`.
Returns: `{swornEnemy{enemy, bonusPercent, damagesDealt}, defensivePacts[{partner, bonusPercent, damagesDealt}]}`
Project: —

`war.getById` 🧭
Purpose: One war's scoreboard.
Use when: you have a `warId` (from `battle.war` or a `warDeclared` event) and need won battles/rounds and damage per side, or whether it's active.
Inputs: `warId*`.
Returns: `{isActive, attacker/defender{country, wonBattlesCount, wonRoundsCount, damages}, priority, priorityEndAt, battles[]}`. `battles` was empty, so list a war's battles with `battle.getBattles {warId}`.
Project: —

`alliance.getById` / `alliance.getManyPaginated` 🧭
Purpose: Alliance details (member countries with development, leader, rankings) / all alliances.
Use when: "which countries are in alliance X?" or listing alliances. Get the ID from `country.allianceId`.
Inputs: `allianceId*` / `limit`, `cursor`. The explorer's `page` is **ignored**; use `cursor`.
Returns: `{_id, name, leader(userId), memberCountries[{country, coreDevelopment, averageDevelopment, suspended}], currentDevelopment, rankings, …}` / `{items, nextCursor}`.
Project: —

`country.getUnrestData` 🧭
Purpose: A country's unrest/revolution bar.
Use when: monitoring revolution risk. Lighter than `getCountryById().unrest`, and it adds `isFull` and `isOnRevolutionCooldown`.
Inputs: `countryId*`.
Returns: `{bar, barMax, lastContributionAt, isFull, isOnRevolutionCooldown}`
Project: —

`contribution.getCountryUnrestContributions` / `contribution.getRegionContributions` 🧭
Purpose: Who contributed to a country's unrest / a region's resistance, and how much.
Use when: "who is pushing the revolution?" or "who is building resistance in region X?". The **user object is embedded**, so no follow-up calls are needed.
Inputs: `countryId*` / `regionId*`, `page` (works), `limit` (**ignored**: always 10).
Returns: **page-style** `{results:[{type, user{…full…}, country, region?, amount, resource, createdAt}], count, page, pages, nextPage, limit}`
Project: —

`party.getById` / `party.getManyPaginated` 🧭
Purpose: Political party details (leader, treasurer, council, members) / a country's parties.
Use when: you have `country.rulingParty` or a candidate's party, or want to list a country's parties (`countryId`).
Inputs: `partyId*` / `limit`, `cursor`, `countryId`.
Returns: `{name, country, leader, treasurer, primaryWinner, councilMembers[], members[]}` / `{items, nextCursor}`. Party `ethics` were removed in v0.27 (replaced by the country's `govType`) and are no longer returned **[observed 2026-10-26]**.
Project: —

`election.getElections` / `election.getElection` 🧭
Purpose: Elections for a country (president, congress) or party (primaries), with candidates and **full vote tally**.
Use when: announcing election results or candidates. Read results from the `votes` map; `candidates[].voteCount` was 0.
Inputs: `countryId` **or** `partyId` (one required; with neither you get an **HTTP 500**), `limit` / `electionId*`.
Returns: `{items:[{type(president|partyPrimary|…), status, candidates[{user, party, voteCount, isElected?}], votes{userId: n}, votesCount, electedCandidates[], votesStartAt, votesEndAt}], nextCursor}` / one election.
Project: —

`sanction.getPaginated` 🧭
Purpose: Moderation sanctions (mutes/bans).
Use when: checking whether a player is muted or banned and why.
Inputs: `targetUserId`, `type` (e.g. `MUTE_USER`), `limit`, `cursor`.
Returns: `{items:[{targetUser, data{type, durationInHours, unMuteAt, reason}, createdAt}], nextCursor}`
Project: —

## Users

`user.getUserLite`
Purpose: The public profile of one user: username, country, MU, level, skills (with computed totals), buffs, rankings and military rank.
Use when: you need almost any per-player data, including fight status, health/hunger bars, skill build, last connection, MU membership, buff/debuff timers or attack breakdown (`skills.attack.militaryRankPercent`, `buffsPercent`, `ammoPercent`, `total`). Also answers "when did they pill / when can they pill again", "did they reset skills recently" and "did they ask for MU help today" without storing anything (see domain-users.md).
Inputs: `userId*` (24-hex).
Returns: `{_id, username, country, mu, isActive, militaryRank, leveling{level,totalSkillPoints,availableSkillPoints,…}, skills{<skill>:{level,value,total,currentBarValue?,…}}, dates{lastConnectionAt,lastSkillsResetAt,lastHelpAskedAt,…}, buffs{buffCodes,buffEndAt}|{debuffCodes,debuffEndAt}, rankings, avatarUrl, …}`
Project: `warera.users.get`, `get_fight_status`, `warera.users.find_by_name`.

`user.getUserById`
Purpose: A larger public user object.
Use when: you need fields that the lite version lacks: `region` (residence), `location` (current region), `stats.wealth{companies,items,money,equipments,weapons,total}`, `stats.worksCount`, daily-reward streaks, `missions`, `preferences.locale`, `usernameLower`.
Inputs: `userId*`.
Returns: full user object (see domain-users.md).
Project: —

`user.getUsersByCountry`
Purpose: The citizens of a country, paginated.
Use when: enumerating a country's citizens. Items contain **only `_id` and `createdAt`**, so each one needs a follow-up `getUserLite`. Consider whether a ranking endpoint already gives what you need. **Incomplete:** Romania listed 320 ids and missed a Romanian citizen [observed 2026-10-24].
Inputs: `countryId*`, `limit` (≤100), `cursor`.
Returns: `{items:[{_id, createdAt}], nextCursor}`
Project: `warera.users.get_by_country`.

`search.searchAnything`
Purpose: Global text search.
Use when: you have a **name** and need an ID: a username, MU name, country, region, party or alliance. It's the only name → ID lookup for users.
Inputs: `searchText*`.
Returns: `{userIds[], muIds[], countryIds[], regionIds[], partyIds[], allianceIds[], hasData}` (IDs only). At most 5 fuzzy user matches; quote the text (`"\"Tert\""`) for an exact-phrase search [observed 2026-10-24].
Project: `warera.users.find_by_name` / `warera.users.find_many_by_name` (search quoted, then plain; follow with `getUserLite` and an exact username match).

`inventory.fetchCurrentEquipment`
Purpose: The gear a user currently has equipped.
Use when: you need a player's weapon, ammo type, armor pieces, their rolled stats and durability. Use it for damage calculators, gear audits or broken-gear warnings.
Inputs: `userId*`.
Returns: `{weapon?{code,skills{attack,criticalChance},state,maxState}, ammo?, helmet?, chest?, boots?, gloves?, pants?}`. The object is `{}` if nothing is equipped.
Project: —

`search.searchUsers` / `search.searchMus` 🧭
Purpose: Name search for users only / MUs only.
Use when: name → ID for one entity type. Fuzzy (up to 5 IDs), so you still need an exact-name check via `getUserLite` / `mu.getById`.
Inputs: `searchText*`.
Returns: flat `[id]` arrays.
Project: — (`warera.users.find_by_name` uses `searchAnything`).

`shop.getLastGifts` / `shop.getSubscribedUsers` / `shop.getTopGiftGivers` / `giveaway.getManyPaginated` 🧭
Purpose: Premium gift feed / new Premium subscribers / top gift givers (with `username`) / giveaways with participants and winners.
Use when: community or fun features. Low relevance otherwise.
Inputs: none / none / none / `limit`, `cursor`.
Returns: see domain-users.md.
Project: —

## Battles, rounds, damage, military units, mercenaries

`battle.getBattles`
Purpose: A list of battles, active or historical, with sides, orders, bounty pools and the populated current round.
Use when: you want **all active battles** (`isActive:true`), the battles of a war (`warId`), country (`countryId`) or region (`defenderRegionId`), or bounty/order scanning.
Inputs: `isActive`, `limit` (≤100), `cursor`, `direction`, `filter` (all, yourCountry, yourEnemies), `defenderRegionId`, `warId`, `countryId`.
Returns: `{items:[{_id, war, type(war|resistance), isActive, attacker/defender{country,region,countryOrders[],muOrders[],moneyPool?,moneyPer1kDamages?,bountyEffectiveAt?,wonRoundsCount,…}, currentRound{…populated…}, rounds[], roundsToWin}], nextCursor}`
Project: `warera.battles.get_active`.

`battle.getById`
Purpose: One battle by ID. Here `currentRound` is an ID, not a populated object.
Use when: you have a battle ID (from a link, order or event) and need its sides, war, rounds or active state. **Prefer this over listing active battles and filtering.**
Inputs: `battleId*`.
Returns: battle object.
Project: — (see api-opportunities.md: battle-order_monitor filters the full list instead).

`battle.getLiveBattleData`
Purpose: A compact live scoreboard for one battle.
Use when: you need current or specific-round damage and points, the next tick, or country orders, and want a small payload. Good for polling.
Inputs: `battleId*`, `roundNumber`.
Returns: `{battle{isActive, attackerCountryOrders[], defenderCountryOrders[], roundIds[], roundHistory[], attackerMoneyPer1kDamages, defenderMoneyPer1kDamages, attackerMoneyPool, defenderMoneyPool, attackerBountyEffectiveAt, defenderBountyEffectiveAt} (**[observed 2026-11-02]**: the bounty per side), round{roundId, attackerDamages, defenderDamages, attackerPoints, defenderPoints, actualTickPoints, nextTickAt, isActive}}`
Project: —

`round.getById`
Purpose: One round with both sides' damage, points and last 5 hits.
Use when: inspecting a specific (possibly finished) round.
Inputs: `roundId*`.
Returns: `{_id, battle, number, isActive, attacker/defender{country,damages,points,hitCount,lastHits[]}, live{ticksCount,actualTickPoints,nextTickAt}}`
Project: —

`round.getLastHits`
Purpose: The most recent hits in a round, per side, with full weapon and equipment snapshots.
Use when: building a live hit feed or seeing who is hitting right now and with what gear. Not suitable for totals; use battleRanking for that.
Inputs: `roundId*`.
Returns: `{attacker:[hit], defender:[hit]}`, where hit = `{user, mu, damages, isCriticalHit, isMissed, hitAt, weapon{code,skills}, equipments[], ammo}`.
Project: —

`battleRanking.getRanking`
Purpose: Damage, ground-points or money leaderboards **per battle, round or war**, by user, country or MU.
Use when: "top damage dealers in battle X", "which MU did most damage this war", "country damage split", "who earned bounty money". **Never sum hits yourself.**
Inputs: `dataType*` (damage, points, money), `type*` (user, country, mu), `side*` (attacker, defender, merged), plus one of `battleId`, `roundId`, `warId`; `limit` (≤100), `cursor`.
Returns: `{items:[{user|country|mu, value, rank}], nextCursor, itemCount}`
Project: —

`battleOrder.getByBattle`
Purpose: Active battle orders, both country and MU, for one side of a battle.
Use when: you need who set the order, its `priority` and (if you're entitled) its `text`/`rank`. Text and rank are blank or 0 unless the caller is a citizen of the ordering country or a member of the ordering MU **[spec]**.
Inputs: `battleId*`, `side*` (attacker, defender).
Returns: `[{_id, country, user, battle, side, sideCountry, text, priority("low" observed), rank, isActive, createdAt}]`. Only country orders have been observed; the shape of MU orders is **unknown**.
Project: —

`battleLootSummary.getByBattleAndUser`
Purpose: One user's loot and performance in one battle.
Use when: you need a player's cases, hits, total damage, or bounty/contract money from a battle. Returns 404 if the user didn't fight in it.
Inputs: `battleId*`, `userId*`.
Returns: `{case1Count, case2Count, toolboxCount, hits, totalDmg, poolLoot[], totalMoneyFromBounty, totalMoneyFromContract}` (`toolboxCount` **[observed 2026-11-02]**)
Project: —

`mu.getById`
Purpose: One military unit.
Use when: you need an MU's name, country, owner, **commanders/managers**, members, level, monthly damage, upgrades or rankings.
Inputs: `muId*`.
Returns: `{_id, name, user(owner), country, region, roles{managers[],commanders[]}, members[], leveling{level,monthlyDamages}, activeUpgradeLevels, mercenaryReputation, rankings, avatarUrl}`
Project: `warera.mus.get`.

`mu.getManyPaginated`
Purpose: Military units, paginated, with filters.
Use when: listing all MUs, finding the MU a user belongs to (`memberId`) or owns (`userId`), or searching MUs by name (`search`).
Inputs: `limit` (≤100), `cursor`, `memberId`, `userId`, `search`.
Returns: `{items:[mu], nextCursor}`
Project: `warera.mus.get_all` (all pages), `request_military_units` (raw; unused).

`muMember.getByMu` 🧭
Purpose: Every member of an MU with **weekly, monthly and total damage and help counters**.
Use when: MU activity reports, "who isn't fighting/helping", or ranking members inside an MU. One call instead of one per member.
Inputs: `muId*`.
Returns: `[{user, totalDamagesCount, monthlyDamagesCount, weeklyDamagesCount, totalHelpCount, monthlyHelpCount, weeklyHelpCount, createdAt}]`
Project: —

`mercenaryContractAuction.getPaginatedAuctions`
Purpose: Mercenary contract auctions.
Use when: listing open, won or expired mercenary contracts, optionally for one country or battle.
Inputs: `countryId`, `battleId`, `status` (active, won, expiredNoBids, expiredBattle, expiredRound, cancelled, terminated), `cursor`, `limit` (≤50).
Returns: `{items:[{country, forCountry, forCountrySide, battle, round?, roundNumber?, budget, minimumDamage, currentPerK, currentPayout, bids[], currentWinner?, status, expiresAt, professionalsOnly}], nextCursor}`. Sorted by `createdAt` descending. **Without `status` it returned `[]`** while `won` and `expiredNoBids` auctions existed, so the default is effectively `active` **[observed 2026-11-02]**: always pass `status`.
⚠️ The explorer also lists `page`, `forCountry`, `forCountrySide`, `professionalsOnly`, `sortBy` and `sortOrder`. **All of them are silently ignored** live, so filter and sort locally. `countryId` does filter.
Project: `warera.contracts.get_active_auctions` (status=active), `warera.contracts.get_won_since`.

## Economy: market, companies, jobs, transactions

`itemTrading.getPrices`
Purpose: The current market price of **every** tradable item in one map.
Use when: you need any item price, such as oil for upkeep cost, food or ammo for damage-cost estimates, or cases. **Takes no input**; extra keys are ignored.
Inputs: none.
Returns: `{<itemCode>: number}` (e.g. `{"bread":1.91,"oil":0.19,…}`).
Project: `warera.market.get_prices` (returns the raw envelope, not `result.data`), and raw batched calls in damage.py.

`tradingOrder.getTopOrders`
Purpose: The best buy and sell orders (order book) for one item.
Use when: you need market depth, the best bid/ask, or available quantity, which a single average price doesn't give you.
Inputs: `itemCode*`, `limit` (≤100).
Returns: `{buyOrders:[{user,itemCode,quantity,price,offerAt}], sellOrders:[{…,country}]}`
Project: —

`itemOffer.getById`
Purpose: One item-market offer.
Use when: you have an item offer ID and need its details. Response shape **unknown** (not observed).
Inputs: `itemOfferId*`.
Returns: unknown.
Project: —

`company.getCompanies`
Purpose: Company IDs, paginated, optionally for one owner.
Use when: listing a user's companies (`userId`). Items are **ID strings only**; follow with `company.getById`.
Inputs: `userId`, `perPage` (≤100), `cursor`.
Returns: `{items:[companyId], nextCursor}`
Project: `warera.companies.get_owned_by` (/progression).

`company.getById`
Purpose: One company.
Use when: you need a company's item produced, region, owner, production, upgrades (employee cap = `breakRoom` level) or estimated value.
Inputs: `companyId*`.
Returns: `{_id, user, region, itemCode, name, production, activeUpgradeLevels{storage,automatedEngine,breakRoom}, estimatedValue, isFull, freeMoves, movedUpAt?, …}`. No `workerCount`; older companies still carry a stale pre-v0.27 `workers[]` (old player jobs), so ignore it **[observed 2026-11-02]**.
Project: `warera.companies.get_owned_by` (/progression).

> **❌ Removed in WarEra v0.27 (2026-10-25), 404 `No procedure found` [observed 2026-10-26]:** `worker.getWorkers`, `worker.getTotalWorkersCount`, `workOffer.getWorkOffersPaginated`, `workOffer.getById`, `workOffer.getWorkOfferByCompanyId`, 🧭 `workOffer.getWageStats`, 🧭 `work.getStatsByWorker`, 🧭 `work.getStatsByWorkerAndCompany`. The player job market is gone: companies now run on NPC **employees** (`employee.*`, see Employees below) and the only way to work for another player is as a **manager** (`managerOffer.*` / `manager.*` below). The explorer still lists the removed procedures; don't trust it for them.

`managerOffer.getManyPaginated` 🧭 (in the explorer since 2026-10-28)
Purpose: The **manager job market** (v0.27): one manager offer per company.
Use when: "best manager job", "which companies hire managers", pay per Management point. Replaces the old work-offer listing. The offer's `company` id feeds `employee.getCompanyRoster` (what the job would manage).
Inputs: `limit` (1–100, default 10 **[explorer]**), `cursor`, `regionId`, `countryId`, `profile` **[client]**. `countryId` (Romania) returned no items while the unfiltered list had offers **[observed 2026-10-26]**, so verify what each filter matches before relying on it.
Returns: `{items:[{_id, company, user(owner), region, rateManagement(pay per Management point per hour), maxHourlyWage, minManagement?, citizenship?, text?(owner's ad text), createdAt, updatedAt}], nextCursor}` **[observed 2026-10-28]**. v0.27.1 divided manager wages by 10, so pay values from before 2026-10-27 are 10× too high.
Project: —

`managerOffer.getWageStats` 🧭 (in the explorer since 2026-10-28)
Purpose: The allowed manager pay range and the best offer.
Use when: "is this manager pay legal?" or "what's the best manager rate?". Pay is clamped to 80–120% of the average **[admin patch notes v0.27]**.
Inputs: `{}` or none. No key needed. Returns: `{allowedRange{min, max, average, source}, topOffer, topEligibleOffer}`, e.g. `{"min":0.0864,"max":0.1296,"average":0.108,"source":"market"}`, `topOffer: 0.1287` **[observed 2026-10-28]**. `topEligibleOffer` is `null` for an API key (no logged-in player).
Project: —

`managerOffer.getByCompanyId` / `manager.getByCompanyId` 🕵️
Purpose: A company's open manager offer / its current manager contract.
Inputs: `companyId*`. Returns: the object, or `null` when there is none **[observed 2026-10-26]**. The contract is `{_id, user(manager), company, employer, rateManagement, maxHourlyWage, accrued, unpaidHours, totalEarned, hiredAt, lockedUntil, lastAccruedAt, …}` **[observed 2026-10-28]**, plus computed `managementLevel, hourlyWage, productionBonusPercent, isInactive, canEndAt, hasPendingRateReduction` **[observed 2026-11-02]**. Project: —

### Employees (v0.27 NPC workforce) 🧭🔑

Announced as **API-token endpoints** in a post shared on 2026-10-28; all of them answered the bot key that day and give **401 `API token required`** without one **[observed 2026-10-28]**. Until 2026-10-26 they answered 403. None is in the official spec; the explorer added all ten by 2026-11-02, so they are 🧭. Except where noted they read **any** company or employee, not only the key owner's. Field meanings and the employee object are in domain-economy.md → Employees.

> **"My" = the API key's owner.** `getMyEmployees`, `getMyWorkforceSummary`, `employeeEvent.getMine` and `getPendingCount` describe the WarEra account that owns `WARERA_API_KEY`, not the Discord user who ran a command. Don't build per-member features on them.

`employee.getCompanyRoster` 🧭🔑
Purpose: A company's employees, each with its production and wage estimate, **plus** the company's hourly totals.
Use when: "who works in company X", "what does company X produce and pay per hour", scouting a company behind a manager offer. One call instead of `getCompanyEmployees` + `getCompanyEstimate`.
Inputs: `companyId*`. An unknown id gives **404 `Companies not found.`**
Returns: `{employees:[employee], hourly:{itemCode, production, toolboxes, wageCost, managerCost, cap, engineMultiplier}}` (`itemCode` **[observed 2026-11-02]**, `engineMultiplier` since v0.27.4). A company with no employees gives `{employees: [], hourly: {… 0, cap}}` **[observed 2026-10-28]**.
Project: —

`employee.getCompanyEmployees` 🧭🔑
Purpose: Only the `employees` array of `getCompanyRoster`. The game client doesn't call it **[client 2026-10-28]**.
Inputs: `companyId*`. Returns: `[employee]` **[observed 2026-10-28]**. Project: —

`employee.getCompanyEstimate` 🧭🔑
Purpose: Only a company's hourly totals. The game client doesn't call it **[client 2026-10-28]**.
Use when: you need production or labour cost for many companies and not the employees.
Inputs: `companyId*`. Returns: `{itemCode, production, toolboxes, wageCost, managerCost, cap, engineMultiplier}` per hour **[observed 2026-11-02]**; `cap` is the employee capacity (breakRoom level) **[observed 2026-10-28]**. Project: —

`employee.getManagerPointValue` 🧭🔑
Purpose: The hourly production that **one Management point** adds to a company.
Use when: valuing a manager for a company (points × this × `gameStat.getPpMoneyValue` = money per hour), or comparing manager offers. Don't recompute it from employee stats.
Inputs: `companyId*`. Returns: `{productionPerPoint}`, e.g. `0.06` for staffed companies and `0` for a company with no employees **[observed 2026-10-28]**. Project: —

`employee.getById` 🧭🔑
Purpose: One employee, as their company's roster shows them.
Inputs: `employeeId*`. Returns: an employee, or **`null` (200)** for an unknown id **[observed 2026-10-28]**. Project: —

`employee.getMyEmployees` 🧭🔑
Purpose: Every employee the **key owner** has, across all their companies, with estimates.
Inputs: none. Returns: `[employee]` **[observed 2026-10-28]**. Project: —

`employee.getMyWorkforceSummary` 🧭🔑
Purpose: The key owner's whole workforce in one object.
Inputs: none. Returns: `{employeeCount, trainableCount, managerCount, foundToolboxes, production, productionByItem{<itemCode>: perHour}, toolboxesPerHour, wageCost, managerCost}` (per-hour values) **[observed 2026-10-28]**; `productionByItem` **[observed 2026-11-02]**. The client values it with `gameStat.getPpMoneyValueByItem`. Project: —

`employeeEvent.getMine` / `employeeEvent.getPendingCount` 🧭🔑
Purpose: The key owner's pending employee events and unseen auto-picked outcomes / how many events are waiting.
Inputs: none. Returns: `[event]` / a bare number. Only `[]` and `0` have been seen **[observed 2026-10-28, 2026-11-02]**; the event object is presumably the one `getHistory` returns (domain-economy.md) **[assumption]**. Project: —

`employeeEvent.getHistory` 🧭🔑
Purpose: One employee's event story, newest first. The announcement says it is for **your own** employees.
Inputs: `employeeId*`. Returns: `[event]` (shape in domain-economy.md → Employees). An own employee returned its resolved events; a foreign employee and a nonexistent id returned `[]`, so it only works for the key owner's employees **[observed 2026-11-02]**. Project: —

`work.getLastByEmployee` 🧭🔑
Purpose: An employee's latest hourly work entries, newest first.
Use when: an employee's recent hourly production and wage. For daily totals use `work.getStatsByEmployee`.
Inputs: `employeeId*`, `limit` (default 20) **[client + observed]**. Works for any employee. Returns: `[{_id, wage, production, createdAt}]` **[observed 2026-10-28]**. Project: —

`transaction.getPaginatedTransactions` 🔑
Purpose: The transaction ledger, filterable by user, MU, country, party, item and type.
Use when: you need donations, wages, trades, market sales, tips, case openings, crafting or battle loot history. Filter server-side by `countryId`/`muId`/`partyId`; don't fetch per user if a single entity filter can answer the question.
Inputs: `limit` (≤100), `cursor`, `userId`, `muId`, `countryId`, `partyId`, `itemCode`, `transactionType` (one value or an array: applicationFee, trading, itemMarket, wage, donation, articleTip, openCase, craftItem, dismantleItem, battleLoot, countryMoneyTransfer).
Returns: `{items:[{transactionType, money, itemCode?, quantity?, buyerId, sellerId?, buyerCountryId?, sellerCountryId?, buyerMuId?, sellerMuId?, createdAt, …}], nextCursor}` **[explorer example + project]**. `{countryId, transactionType:"donation"}` returns donations **to** that country (`sellerCountryId` = the country, `buyerId` = the donor; 100 of 100) **[observed 2026-11-02]**.
Project: `warera.market.get_user_transactions` (top_user_weekly_donations).

`donation.getManyPaginated` 🧭
Purpose: **Lifetime donation totals per donor** to a country, MU or party, sorted by amount descending.
Use when: "all-time top donors to Romania/MU X". **No key needed.** Each item is a running total per donor, not a single event, so it **can't** give weekly figures by itself.
Inputs: `countryId` / `muId` / `partyId`, `limit` (≤100), `cursor`.
Returns: `{items:[{userId, countryId|muId|partyId, amount, createdAt(first), updatedAt(latest)}], nextCursor}`
Project: —

`donation.getTotalDonations` 🧭
Purpose: Total donated amount and donor count for a country, MU or party.
Use when: you need a headline donation stat in one call.
Inputs: `countryId` / `muId` / `partyId`.
Returns: `{totalAmount, donorCount}`
Project: —

`company.getProductionBonus` 🧭
Purpose: A company's production bonus breakdown.
Use when: you need a company's production bonus. Don't recompute it from deposits.
Inputs: `companyId*`.
Returns: since v0.27 only `{depositBonus, total}`, and every company sampled had `total: 0` **[observed 2026-10-26]**: deposits are turned off, strategic resources no longer boost production, and party ethics are gone. Before v0.27 it also had `strategicBonus, ethicSpecializationBonus, ethicDepositBonus`. The v0.27 production boosts (Management, happiness, tools, time on the same good, +5% in a core region) are **not** in this response.
Project: `warera.companies.get_production_bonuses` (/economy).

`company.getRecommendedRegionIdsByItemCode` 🧭🔑
Purpose: The best regions to produce an item, ranked, with bonus breakdown and tax.
Use when: "where should I build a steel company?". 401 without a key.
Inputs: `itemCode*`, `count`.
Returns: `[{regionId, bonus, strategicBonus, depositBonus, ethicDepositBonus, ethicSpecializationBonus, taxPercent}]` **[explorer example, pre-v0.27]**. Returned `[]` for steel **[observed 2026-10-26]**, as expected now that region production bonuses are gone.
Project: —

`tradingOrder.getPublicOrdersByOwner` 🧭
Purpose: Open market orders of a user, MU, country (treasury) or party, with totals.
Use when: "what is the Romanian treasury buying or selling?" or watching a player's orders.
Inputs: one of `userId`, `muId`, `countryId`, `partyId`.
Returns: `{buyOrders[], sellOrders[], allOrders[], totalBuyMoneyInvested, totalSellMoneyExpected, totalSellQuantities{}}`
Project: —

`gameStat.getPpMoneyValue` 🧭 (in the explorer since 2026-10-28)
Purpose: The money value of **1 production point** (v0.27), from raw-material trades over the last 7 days.
Use when: valuing production, self-work or employee wages. An employee's hourly wage = Production ÷ 4 × this value × their expectation (70–130%) **[admin patch notes v0.27]**. Don't derive it from market prices yourself.
Inputs: **none** (`{}` gives 400 `Expected void`). Returns: a bare number (`0.1019`) **[observed 2026-10-26]**.
Project: —

`gameStat.getPpMoneyValueByItem` 🕵️ (client-only, new by 2026-11-02)
Purpose: The money value of 1 production point **per tradable good** (raw and products; 20 items).
Use when: valuing a company's or employee's output by the good it makes (`productionByItem` × this), as the game's workforce screens do. For one global value use `getPpMoneyValue`.
Inputs: **none**. No key needed. Returns: `{<itemCode>: number}`, e.g. `{"iron": 0.1135, "bread": 0.09, "cookedFish": 0.1062}`; the plain mean equalled `getPpMoneyValue` (0.0991 vs 0.099) **[observed 2026-11-02]**. Details and the client's product formula: domain-economy.md → `gameStat.getPpMoneyValueByItem`.
Project: —

`work.getStatsByUserId` / `work.getStatsByCompany` / `work.getStatsByEmployee` 🧭🔑
Purpose: Daily production and wage history (up to 60 days) for a user, company or employee.
Use when: productivity reports. **401 without a key.** The explorer says Premium is needed for the user and company variants, but `getStatsByUserId` answered with the bot key **[observed 2026-10-26]**. `getStatsByEmployee` is in the explorer since 2026-10-28 and works for any employee id from `employee.*` **[observed 2026-10-28]**; for hourly entries use `work.getLastByEmployee`. `getStatsByWorker` and `getStatsByWorkerAndCompany` were removed in v0.27; `getStatsByEmployee` (`employeeId*`) replaces them **[client]**.
Inputs: `userId*` / `companyId*` / `employeeId*`; `days` (1–60), `timezone` (IANA).
Returns: `[{dailyDate, total, wage, employeeProd, selfWork?, automatedEngine?}]` **[observed 2026-10-26]**; an employee's rows have only `{dailyDate, total, wage, employeeProd}` **[observed 2026-10-28]**.
Project: —

## Rankings, articles, game config

`ranking.getRanking`
Purpose: Global leaderboards: country, user, MU and alliance, all-time and weekly.
Use when: "top players by weekly damage", "richest users", "most active countries", "best MUs", plus tier thresholds. Returns **all entries in one response** (about 14k for user rankings), with no pagination. Filter locally by `country`/`mu`.
Inputs: `rankingType*` (35 values; see the domain file. `countryProductionBonus` was removed in v0.27 and now fails with `invalid_enum_value` **[observed 2026-10-26]**).
Returns: `{type, items:[{user|country|mu|alliance?, country?, mu?, value, rank, tier}], tierValues{bronze…master}}`
Project: `warera.game.get_ranking` (weeklyUserDamages).

`article.getArticlesPaginated`
Purpose: Newspaper articles feed.
Use when: listing latest (`last`), daily, weekly or top articles, or one author's articles (`userId`); filter by `categories` or `languages`. Items include full HTML `content`.
Inputs: `type*` (daily, weekly, top, my, subscriptions, last, saved), `limit` (≤100), `cursor`, `userId`, `categories[]`, `languages[]`, `positiveScoreOnly`. `saved` is the caller's private bookmarks (needs a logged-in player, ignores filters) **[spec]**.
Returns: `{items:[{_id, title, content(html), language, category, author, stats{likes,views,…}, publishedAt, slug}], nextCursor}`
Project: `warera.game.get_articles` (type=last, pages through *everything*; see opportunities).

`article.getArticleById` / `article.getArticleLiteById`
Purpose: One article, either full or only title and stats. The lite version **does not count as a view** **[spec]**.
Use when: resolving an article link. Use lite when you only need the title or stats.
Inputs: `articleId*`.
Returns: article object / `{_id, title, stats}`.
Project: —

`article.getWelcomeArticleByCountryId` 🧭
Purpose: A country's pinned welcome article for new citizens.
Use when: you need the full welcome guide. If you only need its ID or title, `country.pinnedArticle` + `getArticleLiteById` is cheaper.
Inputs: `countryId*`.
Returns: full article object + `welcomeArticleOfCountry`.
Project: —

`poll.getPoll` / `poll.getPollVoters` (official since 2026-10, v0.27)
Purpose: A poll attached to an article, with its results / the players who picked one answer. Votes are public **[admin patch notes v0.27]**.
Use when: reporting a poll's results or listing who voted for an answer.
Inputs: `pollId*` (24-hex) / `pollId*`, `optionId*` (0–9), `limit` (≤100, default 20), `cursor`.
Returns: unknown (no live poll found yet; an unknown id gives 404 `Poll not found` **[observed 2026-10-26]**). Logged-in players also get their own vote and whether they can vote **[spec]**; an API key won't.
Project: —

`article.getPinnedArticles` 🧭 (in the explorer since 2026-10-28)
Purpose: The articles pinned at the top of News, which is where the **admin posts patch notes** (v0.27 was pinned on 2026-10-26).
Use when: checking for a new game version or reading the latest patch notes.
Inputs: none. No key needed. Returns: `[article]` with full HTML `content`, the same keys as `getArticlesPaginated` items **[observed 2026-10-26]**. On 2026-10-28 it held one article, `v0.27.1` (published 2026-10-27), which replaced the v0.27 notes **[observed 2026-10-28]**. Items now carry `pinnedUntil` (ISO; the v0.27.4 notes were pinned until 2026-11-04) **[observed 2026-11-02]**.
Project: —

`gameConfig.getDates`
Purpose: Game clock milestones.
Use when: you need the next day rollover or regen tick, congress or presidential elections, the start of next month, or mission resets. Prefer it over computing schedule times yourself.
Inputs: none.
Returns: `{nextDayAt, previousDayAt, nextRegenAt, nextCongressElectionsAt, nextPresidentialElectionsAt, nextMonthAt, dailyMissionRegenAt, weeklyMissionRegenAt, monthlyMissionRegenAt}`
Project: —

`gameConfig.getGameConfig`
Purpose: All static game rules and constants (~33 KB).
Use when: **before hardcoding any game number**: skill level values and costs, upgrade costs and upkeep scales, item stats and recipes, battle bonuses, loot rates, law and election rules, region resistance, mercenary rules and more. See game-config.md.
Inputs: none.
Returns: `{user, skills, battle, upgradesConfig, items, region, mu, company, law, election, mercenaryContract, loot, …}`
Project: — (several hardcoded copies exist; see opportunities).

---

## Tournaments and other procedures not in the official spec

`tournament.getById`, `tournamentTeam.getById` and `gameStat.getEquipmentAvgByCode` are used by the project. The tournament listing procedures below come from the explorer. All were verified live.

`gameStat.getEquipmentAvgByCode` **[project + observed, NOT in spec]**
Purpose: Average market price for one equipment item code.
Inputs: `{itemCode}`. Returns: a bare number (e.g. `1.38` for `helmet1`).
Project: raw batched URL in `cogs/commands/damage.py:_fetch_gear_prices`. It is unstable and could disappear without notice.

`tournament.getById` **[project + observed, NOT in spec]**
Purpose: One tournament (country or MU).
Use when: a battle has `type: "tournament"` (it then has no `region` and no side `country`; each side has `tournamentTeam` and the battle has `tournament`). `type` tells country tournaments (`"country"`) from MU tournaments (`"mu"`).
Inputs: `{tournamentId*}`. Returns: `{_id, name, description, type(country|mu), status, isActive, startAt, teamCount, teamSize, roundsCount, activeRound, rounds{<n>:{matches[{attacker,defender,…}]}}, registered{countries[],…}, winnerTournamentTeam, …}`.
Project: `warera.tournaments.get` → `cogs/tasks/battle-order_monitor.py`. Unstable; could disappear without notice. Full shape, and which tournament procedures don't exist: domain-battles-military → Tournament battles.

`tournamentTeam.getById` **[project + observed, NOT in spec]**
Purpose: One tournament team (a side in a tournament battle).
Inputs: `{tournamentTeamId*}`. Returns: `{_id, tournament, number, countries[], mus[], users[], participants[], status, totalDamage, damageByEntity{id: dmg}, colorScheme, …}`. Country tournament teams list several countries in `countries` (a coalition, e.g. 9–10) with `mus: []`; MU tournament teams have one MU in `mus` and `countries: []`.
Project: `warera.tournaments.get_team` → `cogs/tasks/battle-order_monitor.py`. Unstable; could disappear without notice.

`tournament.getLastTournament` / `tournament.getManyPaginated` 🧭
Purpose: The most recent tournament / all tournaments newest first (each with its full bracket).
Use when: "is there a tournament now?" or listing past tournaments. Keep `limit` small, because each item carries all rounds and matches.
Inputs: none / `limit` (≤100), `cursor`.
Returns: tournament object / `{items:[tournament], nextCursor}`.
Project: —

`tournamentTeam.getByTournamentId` 🧭
Purpose: **All teams** of a tournament in one array (443 for an MU tournament).
Use when: you need many teams, e.g. to find the team containing a country or MU. One call instead of one `getById` per team.
Inputs: `tournamentId*`.
Returns: `[tournamentTeam]` (same shape as `getById`).
Project: —

---

## 🕵️ Found in the game client only (internal API; neither official nor in the explorer)

> Entries here tagged 🧭 were added to the explorer by 2026-10-28 and are kept here so links still work.

These were extracted from app.warera.io's JavaScript and verified anonymously on 2026-10-03. They're the **least stable** tier, so use them only when nothing official or 🧭 fits. The other 42 session-only queries (403 for API keys, tested with the bot key) and 278 mutations (🚫 never call) are listed in client-discovered.md.

`itemTrading.getItemTrading` 🧭 (in the explorer since 2026-10-28)
Purpose: **30-day daily price history** for one tradable good: avg price, volume, trade count, plus min/max allowed price.
Use when: price trends, charts, volatility alerts, or "is bread expensive today?". Goods only; equipment returns 404.
Inputs: `itemCode*`.
Returns: `{itemCode, minPrice, maxPrice, currentValue, values[{valueAt, avgValue, totalValue, totalQuantity, transactionsCount}]}`
Project: —

`tradingOrder.getTopOrdersPerItemCode` 🧭 (in the explorer since 2026-10-28)
Purpose: Best buy and sell orders for **several items in one call**.
Use when: you'd otherwise call `tradingOrder.getTopOrders` once per item.
Inputs: `itemCodes*[]`, `limit`.
Returns: `{<itemCode>: {buyOrders[], sellOrders[]}}`
Project: —

`battle.getActiveBattlesByCountry` 🕵️
Purpose: IDs of the active battles a country is in.
Use when: "is Romania fighting right now, and where?" without paging all active battles. Follow with `battle.getById`.
Inputs: `countryId*`.
Returns: `["<battleId>"]`
Project: —

`mercenaryContractAuction.getActiveAuctions` 🕵️
Purpose: Mercenary auctions, as the game UI lists them.
Use when: you need `status` filtering that the official procedure doesn't apply reliably (here `won` returns only won). Otherwise prefer the official `getPaginatedAuctions`.
Inputs: `countryId`, `battleId`, `status`, `limit`, `cursor`.
Returns: `{items:[auction], nextCursor}`
Project: —

`battle.getViewersCount` 🕵️
Purpose: How many players are watching a battle.
Inputs: `battleId*`. Returns: a bare number (`0` for a live battle with the bot key) **[observed 2026-10-28]**. Project: —

`alliance.getByIds` 🧭 (added to the explorer by 2026-10-26)
Purpose: Several alliances in one call.
Inputs: `ids*[]` (the explorer's `allianceIds` fails with `ids Required` **[observed 2026-10-26]**). Returns: `[alliance]`. Project: —

`upgrade.getMapUpgrades` 🕵️
Purpose: Every region upgrade on the map in one call.
Use when: scanning bunkers, bases or other upgrades across all regions, instead of one `upgrade.getUpgradeByTypeAndEntity` per region.
Inputs: none. Returns: `[{_id, region, upgradeType, level, status(active|pending|disabled)}]` **[observed 2026-10-26]**. Project: —

`mu.getReputationBuyStatus` 🕵️
Purpose: An MU's current mercenary reputation (exact, fractional) and the reputation-purchase price.
Inputs: `muId*`. Returns: `{canBuy, cost, amount, currentReputation}`. Project: —

`gameConfig.getMaxBountyRate` 🧭 (in the explorer since 2026-10-28)
Purpose: Current maximum money per 1k damage allowed for bounties and contracts.
Inputs: none. Returns: a bare number. Project: —

`gameStat.getBadgeStats` / `gameStat.getMilestoneStats` 🕵️
Purpose: How many players hold each badge / reach each milestone tier (count and %).
Inputs: none. Returns: `{<key>: {count, percent}}` / `{<key>: {<tier>: {count, percent}}}`. Project: —

`articleInteraction.getArticleLikers` / `articleInteraction.getArticleTippers` 🕵️
Purpose: Who liked or tipped an article.
Inputs: `articleId*`. Returns: `[{userId, createdAt}]`. Project: —

`assetSale.getLastSkinGifts` 🧭 (in the explorer since 2026-10-28)
Purpose: Recent cosmetic skin gifts.
Inputs: none. No key needed. Returns: the latest few gifts (3 on 2026-10-28), newest first: `[{createdAt, buyer, giftedTo, skins[{key, slot}]}]`, e.g. `skins: [{key: "pumpkinHead", slot: "helmet"}]` **[observed 2026-10-28]**. Project: —

`map.getMapData` 🕵️
Purpose: World map geometry (TopoJSON: 726 regions, countries, meshes), **3.8 MB**.
Use when: rendering a map image. Cache it indefinitely.
Inputs: none. Returns: `{map:{type:"Topology", arcs, transform, objects{regions, countries, …}}, …}`. Project: —
