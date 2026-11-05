# API opportunities

Two kinds of entries: (A) places where the project derives, duplicates or over-fetches something the API gives more directly, and (B) useful endpoints the project doesn't use yet. **Nothing here has been changed in code.** Raise the relevant item with the user before touching that area.

Labels: **[observed]** verified live 2026-10-03 · **[assumption]** needs verification.

---

## A. Existing code that could use a more direct API path

### A1. `battle-order_monitor.add_priority_from_link` lists all active battles to find one ID
`cogs/tasks/battle-order_monitor.py:137-142` calls `warera.battles.get_active()` (all pages) and then `next(... == battle_id)`.
**Better:** `battle.getById {battleId}`, one small call. It returns `isActive` and the same `attacker`/`defender` side objects **[observed]**. Note that `currentRound` is an ID there, not populated. Use `battle.getLiveBattleData` if live score is needed.

### A2. Region upkeep percentages are hardcoded and the minimum upkeep is ignored
`cogs/commands/get_region_upgrade_cost.py` `UPKEEP_PCTS` exactly duplicates `gameConfig.getGameConfig().upgradesConfig.<type>.levels[n].maintenanceCost{Country|Region}DevScale` **[observed]**. The config also defines `minimumMaintenanceCost` (1, 2, 5, 10, 25 per level), which the command ignores. If upkeep = max(scale × dev, minimum) **[assumption]**, low-development regions are under-reported. Reading the config removes the duplication and stays correct after balance patches.

### A3. `damage.py` duplicates game constants and per-user computed values
- `MILITARY_RANK_BONUSES` table → `user.getUserLite().skills.attack.militaryRankPercent` is already computed per user (rank 97 → 30, which matches) **[observed]**. `damage.py` already fetches this user via `warera.users.find_by_name()`.
- `FOOD[*].health_pct` and `AMMO[*].dmg_bonus` → `gameConfig.items.<code>.flatStats.healthRegenPercent` / `percentAttack` (10/15/20 and 10/20/40, identical) **[observed]**.
- `SKILL_LEVEL_COST`, `MAX_SKILL_LEVEL` → `gameConfig.skills.<s>.levels[n].totalCost`.
- `GEAR[*].mods` (fixed stat per tier) → the player's **actual** rolled gear is in `inventory.fetchCurrentEquipment {userId}`, and item stat ranges are in `gameConfig.items.<code>.dynamicStats` **[observed]**.
- The user's effective stats are in `skills.<s>.total` (with weapon, equipment, buffs, ammo and rank applied). Check whether the calculator could start from these instead of rebuilding them **[observed fields; formula undocumented]**.

### A4. `damage.py:_fetch_market_prices` sends N identical requests
It batches `itemTrading.getPrices` once per `ITEM_CODES` entry with `{"itemCode": …}`. The procedure **takes no input**; the key is ignored and every call returns the full price map **[observed]**. The code only reads `data[0]`. **Better:** one plain `warera.market.get_prices()` call (then unwrap `result.data`).

### A5. `damage.py` depends on an undocumented procedure
`gameStat.getEquipmentAvgByCode` isn't in the spec. Keep the hardcoded fallback. **No documented replacement exists:** `tradingOrder.getTopOrders {itemCode:"helmet3"}` returns empty `buyOrders`/`sellOrders` **[observed]**, so equipment probably trades through item offers (`itemOffer.*`, which has no list endpoint) **[assumption]**. If this procedure breaks, tell the user; don't invent a substitute.

### A6. `warera.game.get_articles` drains every page of articles every 5 minutes — **done 2026-10-12** (`max_items`)
`warera.game.get_articles` loops `nextCursor` until exhausted, and `article_mention.py` reads only the first 100 (`ARTICLE_LIMIT`). **Better:** a single `article.getArticlesPaginated {type:"last", limit:100}` call, since the feed is newest first **[observed]**. This is the largest avoidable request volume in the bot against the ~100 req/min budget.

### A7. Weekly donations: one call per citizen, each draining the full history
`top_user_weekly_donations.py` calls `warera.market.get_user_transactions(user, "donation")` for every citizen, and each call paginates the user's entire donation history.
- Cheap fix that stays on the same endpoint: stop paginating once `createdAt < week_start`. **Done 2026-10-12** (`warera.market.get_user_transactions(created_after=…)`); newest-first order verified live across pages for 4 users.
- Possibly much better: `transaction.getPaginatedTransactions {countryId, transactionType:"donation"}`, a single stream filtered server-side, grouped locally by `buyerId`. **Verified 2026-11-02:** `countryId` matches donations **to** the country (`sellerCountryId` = the country, donor in `buyerId`; 100 of 100), not transactions by its citizens. It replaces the per-citizen loop only if the report counts donations to the country treasury; donations to MUs, parties or other countries won't appear.

- **Doesn't solve it:** 🧭 `donation.getManyPaginated {countryId}` (no key, one paginated call) returns **lifetime cumulative totals per donor**, not individual donations **[observed]**. So it can't produce *weekly* numbers directly. Options:
  - snapshot it at week start and diff the totals per `userId` at query time (2 calls instead of N+1, but it needs storage);
  - offer an **all-time** top-donors view straight from it;
  - keep the transaction approach for exact weekly windows.

### A8. Country names fetched one at a time — `bounty_monitor` and `mercenary_contracts` now batch them (`warera.countries.get_many`, 2026-10-12)
`bounty_monitor.py:96`, `mercenary_contracts.py:54` and `battle-order_monitor._country_name` call `country.getCountryById` just to get `name`. One cached `country.getAllCountries` call gives every name **[observed]**, and several of these cogs already fetch it.

### A9. Inactivity threshold hardcoded
`inactive_players.py` and `mu_stray.py` use `3 * 24 * 3600`, which equals `gameConfig.user.isInactiveAfterDays` (3) **[observed]**. `user.getUserLite().isActive` is also returned. Whether it matches the 3-day rule is **[assumption]**.

### A10. NAP data kept locally
The bot stores NAPs in its own DB (`naps.py`, `monitor_nap.py`). `country.nonAggressionUntil {countryId: iso}` exposes the game's own non-aggression timers **[observed]**. These may be game-enforced post-peace or post-liberation NAPs (`gameConfig.region.nonAggressionHoursAfterPeace` 72h, `…AfterLiberation` 24h) rather than diplomatic NAPs **[assumption]**. They could still be used to annotate or validate.

---

## B. Useful endpoints the project doesn't use

| Endpoint | Ideas for this bot |
|---|---|
| `event.getEventsPaginated` | A "world news" or Romania alerts channel: `warDeclared`, `battleOpened`, `regionTransfer`/`regionLiberated`, `newPresident`, `allianceFormed`/`Broken`, `defensivePactFormed`/`Broken`, `revolutionStarted`, `depositDiscovered`. Filter with `countryId` and `eventTypes`. It replaces snapshot-diffing. |
| `battleRanking.getRanking` | Top damage dealers or MUs per battle, round or war; "Romanian contribution in war X"; bounty money earned (`dataType:"money"`). Never sum hits manually. |
| `battleOrder.getByBattle` | Read order priority and setter directly. Text and rank are visible only to the ordering country's citizens or MU members, presumably based on the API key's user **[assumption]**. Complements `battle-order_monitor`, which currently uses only `countryOrders` IDs. |
| `battle.getLiveBattleData` | Lightweight live scoreboard and next-tick countdown for a battle embed, cheaper than `getBattles`. |
| `battleLootSummary.getByBattleAndUser` | "/loot <battle> <player>": cases, hits, damage, bounty and contract earnings. |
| `inventory.fetchCurrentEquipment` | Gear audit, low-durability warnings (`state/maxState`), feeding real gear into the damage calculator. |
| `gameConfig.getGameConfig` | Single source of all constants (see A2, A3, A9). |
| `gameConfig.getDates` | Election countdowns and "next day/regen" messages; aligning weekly windows. |
| `user.getUserById` | Wealth breakdown (`stats.wealth`), current `location` vs residence `region`, `worksCount`. |
| `upgrade.getUpgradeByTypeAndEntity` | Upgrade status (`active`/`disabled`/pending `willBeActiveAt`) for region defense reports. |
| `tradingOrder.getTopOrders` | Market depth and best bid/ask alerts. |
| `company.getCompanies` + `company.getById` | Player company portfolio, production and estimated value. |
| `article.getArticleLiteById` | Resolve article links without inflating view counts. |
| `mu.getManyPaginated {memberId}` | Find a user's MU in one call; `getUserLite().mu` already gives it too. |
| `round.getLastHits` | Live hit feed with gear snapshots. |

### 🧭 Explorer-only procedures (not in official spec, verified live 2026-10-03)

| Endpoint | Ideas for this bot |
|---|---|
| `muMember.getByMu` | **MU activity report** in one call: weekly, monthly and total damage and help per member. Flag inactive members for the MU-role cogs (`military_unit_roles.py`, `commander_roles.py`), instead of one `getUserLite` per member. (Plain MU membership doesn't need it: `mu.getById.members` already lists it, which `military_unit_roles.py` uses since 2026-10-09.) |
| `countryDiplomacy.getByCountry` | `/diplomacy`: Romania's sworn enemy and defensive pacts with bonus % and damage each partner dealt. Complements the local NAP DB (`naps.py`, `diplomacy.py`). |
| `war.getById` | War scoreboard (battles and rounds won, damage per side) for `battle-order_monitor` posts or a `/war` command. |
| `election.getElections {countryId}` | Announce Romanian election candidates and results (tally in `votes`). Pair with `gameConfig.getDates.nextPresidentialElectionsAt`. Alongside `takeover_countries.py`. |
| `country.getUnrestData` + `contribution.getCountryUnrestContributions` | Revolution-risk alerts and "who is contributing to unrest". The contributor's user object is embedded. |
| `contribution.getRegionContributions` | Who is building resistance in occupied Romanian regions. |
| `donation.getManyPaginated` / `donation.getTotalDonations` | All-time top donors, and headline totals for country or MU (see A7). |
| `tradingOrder.getPublicOrdersByOwner {countryId}` | Watch the Romanian treasury's open market orders. |
| `managerOffer.getManyPaginated` / `managerOffer.getWageStats` 🧭 | v0.27 manager job board and legal pay range (replaces the removed `workOffer.*` job market). |
| `employee.getCompanyRoster` / `employee.getManagerPointValue` 🧭🔑 | Rank manager offers by what the job actually manages: the company's hourly production and labour cost, and the production one Management point adds. Also lets `/economy` value a company's employees from live data. |
| `gameStat.getPpMoneyValue` 🧭 | Money value of 1 production point, for self-work and employee-wage math. |
| `article.getPinnedArticles` 🧭 | Detect a new game version: the admin pins the patch notes. |
| `alliance.getById` | Alliance roster with each member country's development (Romania: `country.allianceId`). |
| `tournament.getLastTournament` / `tournamentTeam.getByTournamentId` | Tournament status and bracket; find the team containing a country or MU in one call. `battle-order_monitor` currently resolves teams one at a time via `getById` (cached; fine for its needs). |
| `party.getById` / `party.getManyPaginated {countryId}` | Ruling party (`country.rulingParty`) leadership and members. |
| `upgradeConstruction.*` | Construction progress feed (shape unknown until something is under construction). |
