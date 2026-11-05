# Domain: battles, rounds, damage rankings, orders, loot, military units, mercenaries

**Solves:** active battle scanning, battle and round state, tournament battles (country vs MU tournaments, team composition), live scoreboards, bounty pools, battle orders (country and MU), damage, ground or money leaderboards per battle, round or war, per-user loot, MU details, commanders and members, and mercenary contract auctions.

Labels: **[spec]** · **[observed 2026-10-03]** · **[project]** · **[assumption]**

---

## Battle object

Common to `battle.getBattles` items and `battle.getById` **[observed]**:

```jsonc
{
  "_id": "<battleId>", "war": "<warId>",
  "type": "war",                       // observed: war, resistance, tournament (see "Tournament battles")
  "isActive": true, "isBigBattle": true,   // isBigBattle seen on some list items
  "roundsToWin": 2, "rounds": ["<roundId>"], "roundsHistory": [],
  "attacker": {
    "country": "<countryId>", "region": "<regionId>",
    "countryOrders": ["<countryId>"],   // countries that set an order for this side
    "muOrders": ["<muId>"],             // MUs that set an order for this side
    "wonRoundsCount": 0, "damages": 0, "hitCount": 203,
    "moneyPool": 224.48, "moneyPer1kDamages": 0.014, "bountyEffectiveAt": "iso"   // only when a bounty exists
  },
  "defender": { …same… },
  "stats": {"hitCount": 0},
  "currentRound": …,   // getBattles: populated round object; getById: roundId string
  "createdAt": "iso", "updatedAt": "iso"
}
```

- The battle's **region** is `defender.region` for war battles. The project also tries `battle.region` (`battle-order_monitor._region_id`) **[project]**.
- Bounty fields are read by `bounty_monitor.py` and `bounty_alerts.py` **[project]**. Semantics **[observed 2026-10-25, 52 active battles]**:
  - A side that ever had a bounty keeps `bountyEffectiveAt` (and `moneyPer1kDamages`) after its pool runs out, with `moneyPool: 0`. So "bounty active" = `moneyPool > 0` **and** `bountyEffectiveAt`, never `bountyEffectiveAt` alone.
  - A new bounty on the same side changes `bountyEffectiveAt`; `bounty_monitor` uses it as the "new bounty" token.
  - Rates are small: 0.02–0.1 per 1k damage on almost every side (one 0.3). `bounty_monitor`'s `moneyPer1kDamages >= 0.1` filter therefore hides most bounties, which is why `bounty_alerts` has no minimum rate.
  - `battle.getBattles` items and `battle.getById` have the same side keys (`bountyEffectiveAt, country, countryOrders, damages, hitCount, moneyPer1kDamages, moneyPool, muOrders, wonRoundsCount`), so `getById` can stand in for a battle missing from the listing.
  - `moneyPool` is a float with long tails (`1777.1148199999998`); round it for display.
- `countryOrders` and `muOrders` are how the project detects that Romania ordered a battle (`battle-order_monitor.check_orders`) **[project]**.

## Tournament battles

Tournament battles come through `battle.getBattles` and `battle.getById` like any other battle, but with a different shape **[observed 2026-10-03]**:

```jsonc
{
  "_id": "6aa442cde9057902c0b49392",
  "type": "tournament",
  "tournament": "<tournamentId>",          // → tournament.getById
  "tournamentRoundNumber": 1,
  "attacker": {"tournamentTeam": "<teamId>", "countryOrders": [], "muOrders": [], "wonRoundsCount": 2, "damages": 13981771, "hitCount": 9800},
  "defender": {"tournamentTeam": "<teamId>", …same…},
  // NO "war", NO "region", NO side "country"/"region"
  "roundsToWin": 2, "rounds": ["<roundId>"], "roundsHistory": […], "isActive": false, "wonBy": "attacker", "endedAt": "iso"
}
```

- Code that reads `side.country` or a region gets nothing for these battles. Resolve the sides through `tournamentTeam.getById` instead. Before this was handled, `battle-order_monitor` posted "attacker unknown against defender unknown in Unknown region" **[project]**.
- There are two kinds of tournament, distinguished **only** by `tournament.getById → type` **[observed]**:
  - `"country"`: "Country Tournament". Each team is a **coalition of several countries** (9–10 observed), with `mus: []`.
  - `"mu"`: "MU Tournament". Each team is **one MU** (`mus: [muId]`, `countries: []`).
- Countries can appear in `countryOrders` of tournament battles (Romania did, in a country tournament) **[observed]**. The project reports country-tournament orders and ignores MU tournaments **[project]**.
- On 2026-10-03, a scan of recent battles found 15 battles from one country tournament and 442 from one MU tournament **[observed]**.

### `tournament.getById` (undocumented, NOT in spec 0.17.4-beta)
Input: `{tournamentId*}` (`{id}` → 400 `tournamentId Required`) **[observed]**.
```jsonc
{
  "_id": "6a9dfe80b8f1404f17de52e1", "name": "Country Tournament", "description": "Nations compete for glory",
  "type": "country",                 // observed: country, mu
  "status": "ended", "isActive": false, "startAt": "iso",
  "teamCount": 16, "teamSize": 23999, "roundsCount": 4, "activeRound": 4,
  "maxRarity": "legendary", "skillKey": "energy", "autoQualify1stRound": [],
  "registered": {"countries": ["<countryId>", …143], "mus": [], "users": []},
  "rounds": {
    "1": {"roundNumber": 1, "cases": 3, "skillValue": null, "matches": [
      {"matchIndex": 0, "attacker": "<teamId>", "defender": "<teamId>", "battle": "<battleId>", "wonBy": "attacker",
       "isQualificationRound": false, "possibleAttackerTeamIds": ["<teamId>"], "possibleDefenderTeamIds": ["<teamId>"]}
    ]},
    "4": {"roundNumber": 4, "cases": 10, "skillValue": 20, "matches": [ …1 final… ]}
  },
  "winnerTournamentTeam": "<teamId>"
}
```
`rounds.<n>.matches[]` maps every tournament battle to its two teams, so a whole bracket can be read from one call **[observed]**.

### `tournamentTeam.getById` (undocumented, NOT in spec 0.17.4-beta)
Input: `{tournamentTeamId*}` (`{teamId}` or `{id}` → 400 `tournamentTeamId Required`) **[observed]**.
```jsonc
{
  "_id": "6aa442cde9057902c0b4937d", "tournament": "<tournamentId>", "number": 13,
  "countries": ["<countryId>", …10],   // country tournament: the coalition; MU tournament: []
  "mus": [],                            // MU tournament: ["<muId>"]
  "users": [], "participants": ["<userId>", …748],
  "status": "eliminated", "estimatedUsers": 23739, "colorScheme": "amber",
  "totalDamage": 40408295, "damageByEntity": {"<countryId|muId|userId>": 2961294, …},
  "createdAt": "iso", "updatedAt": "iso"
}
```
`damageByEntity` mixes country, MU and user IDs in one map **[observed]**. Team `number` is an index within the tournament; whether the game UI shows it is unknown.

### Listing tournaments and teams (not in official spec; [explorer], verified live 2026-10-03)
- **`tournament.getLastTournament`**: no input. Returns the most recently created or active tournament as a full tournament object, same shape as `getById` (on 2026-10-03 that was the ended "MU Tournament", 443 teams, 9 rounds) **[observed]**.
- **`tournament.getManyPaginated`**: `limit` (1–100, explorer default 3), `cursor`. Returns `{items: [tournament], nextCursor}`, newest first **[observed]**. Each item includes the full `rounds` bracket, so keep `limit` small.
- **`tournamentTeam.getByTournamentId`**: `tournamentId*`. Returns an **array of every team** in one call (443 for the MU tournament), each with the same shape as `tournamentTeam.getById` **[observed]**. Use it instead of one `getById` per team when you need many teams, e.g. to find which team contains a given country or MU.

### Tournament procedure names that do NOT exist
Probed on 2026-10-03, all `404 No procedure found`: `tournament.getTournamentById`, `tournament.getTeams`, `tournament.getTournaments`, `tournament.getActive`. Use the procedures above instead.

## `battle.getBattles`
Inputs **[spec]**: `isActive` (bool), `limit` (1–100, default 10), `cursor`, `direction` (`forward | backward`), `filter` (`all | yourCountry | yourEnemies`; "your" is presumably relative to the authenticated user, **[assumption]** and meaningless anonymously), `defenderRegionId`, `warId`, `countryId`.
Returns `{items: [battle], nextCursor}`. With `isActive: true, limit: 100` there were 24 active battles and no next page **[observed]**.
- **Ended battles** (`isActive: false`) **[observed 2026-10-04]**: sorted by `createdAt` **descending** (not `endedAt`), each with `endedAt` and `wonBy`. About **500 ended battles per week** (5 pages of 100, ~2 s). The longest created→ended gap in 600 battles was 23.3 h, so to get "battles that ended since T" page until `createdAt < T − 2 days` and filter on `endedAt`. Helper: `warera.battles.get_ended_since(created_after)`.
- Scanning MU rankings for a whole week of battles at once costs ~1,000+ calls (2 sides × pages, plus money) against the 100/min rate limit, so collect battles incrementally as they end (hourly) and backfill only what is missing (`military_unit_weekly_report._collect_battles`).

## `battle.getById`
Input: `battleId*` **[spec]**. Returns a battle object where `currentRound` is a **string ID** **[observed]**.

## `battle.getLiveBattleData`
Inputs: `battleId*`, `roundNumber` **[spec]**.
```json
{"battle": {"isActive": true, "attackerCountryOrders": ["…"], "defenderCountryOrders": ["…"], "roundIds": ["…"], "roundHistory": [],
            "attackerMoneyPer1kDamages": 0.05, "defenderMoneyPer1kDamages": 0.04, "attackerMoneyPool": 193.66, "defenderMoneyPool": 209.33,
            "attackerBountyEffectiveAt": "iso", "defenderBountyEffectiveAt": "iso"},
 "round": {"roundId": "…", "isActive": true, "attackerDamages": 73825, "defenderDamages": 73677,
           "attackerPoints": 35, "defenderPoints": 12, "actualTickPoints": 1, "nextTickAt": "iso"}}
```
The `*MoneyPer1kDamages` / `*MoneyPool` / `*BountyEffectiveAt` fields are each side's **bounty** (money per 1k damage, money left, when it took effect) **[observed 2026-11-02]**; `battle.getById` did not return them for the same battle. Round victory is at `gameConfig.battle.pointsToWinRound` (300). Tick points scale by elapsed ticks via `gameConfig.battle.tickPoints` **[observed config]**.

## Round timing (no end time in the API)

No procedure returns when a round or battle will end **[observed: battle.getById, round.getById, battle.getLiveBattleData, battle.getBattles]**. What is available:
- `round.live = {ticksCount, actualTickPoints, nextTickAt}` (also on `battle.getBattles` items, inside `currentRound`), plus `attacker.points` / `defender.points`.
- A **tick happens every 2 minutes** (stated by the user, consistent with 22 ticks in 44 min) and awards its points to **one** side: `attacker.points + defender.points` equals the round's total ground points.
- A round is won at `gameConfig.battle.pointsToWinRound` = 300. A tick is worth `gameConfig.battle.tickPoints` = `{1:1, 100:2, 200:3, 300:4, 400:5, 500:6}`, keyed by the round's **total** ground points (both sides) at that tick (stated by the user).
- So an ETA can only be estimated. The project assumes the leading side wins every remaining tick; an uncontested round is 184 ticks ≈ 6h 8m. Implementation: `military_unit_contract_monitor.ticks_to_win_round` / `_round_eta` **[project]**.

## `round.getById`
Input: `roundId*`.
```jsonc
{"_id": "…", "battle": "<battleId>", "number": 1, "isActive": true,
 "attacker": {"country": "…", "damages": 73825, "points": 35, "hitCount": 203, "lastHits": [hit × 5]},
 "defender": {…},
 "live": {"ticksCount": 47, "actualTickPoints": 1, "nextTickAt": "iso"}}
```

## `round.getLastHits`
Input: `roundId*`. Returns `{attacker: [hit], defender: [hit]}` with 5 per side **[observed]**.
```jsonc
// hit
{"_id": "…", "user": "<userId>", "mu": "<muId>", "damages": 152,
 "isCriticalHit": false, "isMissed": true, "hitAt": "iso",
 "weapon": {"code": "rifle", "skills": {"attack": 76, "criticalChance": 13}, "state": 59, "maxState": 100, …},
 "equipments": [{"type": "equipment", "code": "helmet3", "skills": {"criticalDamages": …}, "state": 43, …}],
 "ammo": "lightAmmo" | null}
```

## `battleRanking.getRanking`
Inputs **[spec]**:
- `dataType*` ∈ `damage | points | money` (damage, ground points, bounty/contract money)
- `type*` ∈ `user | country | mu`
- `side*` ∈ `attacker | defender | merged`
- scope: `battleId` **or** `roundId` **or** `warId` (each optional, minLength 1)
- `limit` (1–100, default 20), `cursor`

```json
{"items": [{"_id": "…", "ranking": "…", "user": "<userId>", "value": 62284, "rank": 1, "createdAt": "…"}],
 "nextCursor": "…", "itemCount": 17}
```
For `type: mu` the entity key is `mu` **[observed 2026-10-04]**. A big battle had 211 MUs (3 pages of 100).
- **`type: user` items carry no `mu` or `country`** (only `user`, `value`, `rank`, timestamps, sometimes `lootItem`) **[observed 2026-11-04, 3 battles, every item]**. So a player's MU *at fight time* is not readable per battle: for per-MU damage over a period sum the battles' `type: mu` rankings (credits the MU the player was in when hitting, every member incl. foreigners); grouping user damage by the current `user.mu` misattributes MU switchers (user decision 2026-11-04, `cogs/tasks/gov_rankings.py`).
- **Volume [observed 2026-11-04]:** ~30-41 battles end per day; a merged user damage ranking has 200-3,800 entries (avg ~1,000). Reading user + MU damage and money rankings for 98 battles took 12 s and ~200 batched requests, so summing a whole month of battles (~1,250) is practical.
- `dataType: money` per MU **includes mercenary contract payouts plus bounty** **[observed]**: e.g. an MU with 8 won contracts (payout 931.74) in a battle had money 1111.06, the rest matching the side's bounty. Free bounty ≈ money − that MU's contract payouts for the battle.
- `dataType: money` per **user** (`type: user`, `side: merged`) is exactly `totalMoneyFromBounty + totalMoneyFromContract` of that player's `battleLootSummary.getByBattleAndUser` **[observed 2026-11-03, every sampled player of 12 battles]**. It lists everyone paid in the battle (69 battles = 28.5k entries, ~1.3 pages per battle), and its items carry **no `country`**, so filter by a known id set. For bounty only, read the summaries of the players you need (`warera.battles.get_loot_summaries_many`, pairs across battles in shared batches; 404 = no hits → None).
- Rankings stay available after the battle ends.
- **Live loot pool preview: `lootItem`** **[observed 2026-10-14, 3 big battles, round and battle scopes]**. Every entry of a `type: user` ranking carries `lootItem`: the pool item that rank would get now (`{_id, code, skills, state, maxState, quantity, lastAcquisitionAt}`), or nothing past the pool's size. Use `side: "merged"`: pool items go by the combined (both sides) rank, and merged values equal the per-side value for one-sided players. Along the merged ranking the item rarity (`gameConfig.items[code].rarity`) never rises going down (0 inversions over 1,183–3,746 entries), and rank 1 gets the most valuable item. This is the only pool view the bot's key can read: `loots.getLoot` and `battleLootSummary.getByBattle` answer 403 "API tokens cannot access this endpoint". The round and battle objects have no pool fields. Pool size grows by one item per `gameConfig.loot.damagePerLootItem` (200,000) round damage and `battleLootDamagePerLootItem` (500,000) battle damage. A big round can hold more items than ranked players (2,231 items, 1,183 players). **Verified against what players received** **[observed 2026-10-14]**: for ended rounds of 3 battles, the `lootItem._id` of 23 sampled ranks (#1–5, #46–48, #96–98) equalled the item `_id` in each player's `battleLootSummary.getByBattleAndUser.poolLoot[].item` (`{item, rank, round, pool: "round"}`), with 23 of 23 matching. Ranks shown with no item received nothing. So `lootItem` is the real pool item: rarity, rolled `skills` and all. During a live round it is what the rank would get if the round ended now. Used by `cogs/commands/loot_targets.py`.

## `battleOrder.getByBattle`
Inputs: `battleId*`, `side*` ∈ `attacker | defender` **[spec]**.
Order `text` and `rank` are only filled in for citizens of the ordering country or members of the ordering MU. Everyone else gets `""` and `0` **[spec]**. Visibility follows the API key's user **[assumption]**.
```json
[{"_id": "…", "country": "<countryId>", "user": "<setter userId>", "battle": "…", "side": "attacker",
  "sideCountry": "<countryId>", "text": "", "priority": "low", "rank": 0, "isActive": true, "createdAt": "iso"}]
```
Other `priority` values are not documented.
- **MU orders [observed 2026-10-04]:** same shape with `mu` instead of `country` (`{_id, mu, user (setter), battle, side, sideCountry, text, priority, rank, isActive, createdAt}`); `priority` seen: `low`, `medium`, `high`. Only **active** orders are returned: an ended battle gives `[]`, and ended battles' `attacker/defender.muOrders` are emptied too (4 of 500 ended battles still had any). To count orders over time, record them while active (the project tried this for the MU weekly report and dropped it as not worth a table). Order costs and bonuses are in `gameConfig.battle` (`countryOrderBonusPercent`, `muOrderBonusPercent`, `setCountryOrderMoneyCost`, …).

## `battleLootSummary.getByBattleAndUser`
Inputs: `battleId*`, `userId*`. Returns 404 `"Battlelootsummaries not found."` if the user has no hits in that battle **[observed]**.
```json
{"user": "…", "battle": "…", "hits": 21, "totalDmg": 9870, "case1Count": 2, "case2Count": 0, "toolboxCount": 0,   // toolboxCount [observed 2026-11-02]
 "poolLoot": [], "totalMoneyFromBounty": 0, "totalMoneyFromContract": 0, "createdAt": "iso", "updatedAt": "iso"}
```

## Military units

### `mu.getById`
Input: `muId*`.
```jsonc
{"_id": "…", "name": "Base Militar FBP", "user": "<ownerId>", "country": "<countryId>", "region": "<regionId>",
 "roles": {"managers": ["<userId>"], "commanders": ["<userId>"]},
 "members": ["<userId>"],                          // [observed] list of user ID strings
 "leveling": {"level": 1, "monthlyDamages": 0},
 "activeUpgradeLevels": {"dormitories": 1},         // also headquarters
 "mercenaryReputation": 0, "avatarUrl": "…", "lastAnnouncementAt": "iso",
 "rankings": {"muWealth": {"value", "rank", "tier"}, …}}
// [observed 2026-10-04] rankings keys: muWeeklyDamages, muDamages, muBounty (cumulative), muTerrain, muWealth, muReputation — each {value, rank, tier}
```
- **`members` ⇔ `user.mu` [observed 2026-10-09]:** for all 212 members of the 13 configured MUs, every ID in `members` had `user.getUserLite.mu` equal to that MU (0 mismatches). So `members` answers "which MU is this player in" without per-user calls.
- **Free spots without the upgrade endpoint [observed 2026-10-23]:** capacity = `gameConfig.upgradesConfig.dormitories.levels[str(activeUpgradeLevels.dormitories)].stats.members` (L1–L5 = 5/10/15/20/25), and members = `len(members)`. All 13 configured MUs (one batched `warera.mus.get_many`) plus `warera.game.get_config` cost 2 requests; all were at dormitories 5. Used by `cogs/events/newbie_welcome.py:open_military_units` **[project]**. `mu_readiness.py` reads the level through `upgrade.getUpgradeByTypeAndEntity` instead, because it also needs status. Whether `activeUpgradeLevels` drops a *disabled* dormitory is unverified **[assumption]**.
- **The owner (`user`) is not necessarily in `members`** (only 5 of 13 owners were). An owner outside the list has `user.mu` pointing at the MU they actually belong to. `roles.managers` usually, but not always, includes the owner.

Used by `commander_roles.py` (`roles.commanders`), `military_unit_roles.py` (`members`, `roles.managers`, batched via `warera.mus.get_many`) and `monitor_nap.py` (`country`, `name`) **[project]**.

### `mu.getManyPaginated`
Inputs: `limit` (1–100, default 20), `cursor`, `memberId`, `userId`, `search` **[spec]**. Returns `{items: [mu], nextCursor}`.
- `memberId` finds the MU(s) a user belongs to. `userId` presumably filters by owner **[assumption]**. `search` matches by name.
- Listing every MU took **17 requests for 1,615 MUs** at `limit: 100` **[observed 2026-10-13]**. To act on one MU picked by name, resolve its id from a cache and call `mu.getById` instead of paging (see `fight_status._fetch_cached_military_unit`) **[project]**.

### `muMember.getByMu` (not in official spec; [explorer], verified live 2026-10-03)
Input: `muId*`. Returns an **array with one record per member**, all members in one call (25 for a full MU) **[observed]**:
```json
[{"_id": "…", "mu": "<muId>", "user": "<userId>",
  "totalDamagesCount": 298278601, "monthlyDamagesCount": 6126103, "weeklyDamagesCount": 17385647,
  "totalHelpCount": 2781, "monthlyHelpCount": 29, "weeklyHelpCount": 62,
  "createdAt": "iso (joined?)", "updatedAt": "iso"}]
```
- This is **per-member damage and help counters for the week, month and all time** in one call. Use it for MU activity reports and "who isn't fighting/helping" checks, instead of one `getUserLite` per member or a filtered global ranking.
- `createdAt` is presumably when the member joined **[assumption]**. Caveat: in Walla most records share `2026-03-20T17:01…`, so records were bulk-created then; `createdAt` only means "joined" for members who joined after that date. The weekly counters reset on Monday 00:00 UTC (`gameConfig.getDates.weeklyMissionRegenAt`) **[observed 2026-10-04: monthly < weekly on Oct 4]**.
- `mu.getById → rankings.muWeeklyDamages.value` (149.65M) was higher than the sum of current members' `weeklyDamagesCount` (142.59M) **[observed]**, presumably because members who left still count. Use the ranking for MU totals. `rankings.muBounty` is cumulative.
- Names aren't included. Resolve them with `user.getUserLite` (only the ones you display).
- **There is no daily counter** (only weekly, monthly, total). A member's damage for *today* needs yesterday's `weeklyDamagesCount` stored, or summing `battleRanking` per round (many paginated calls). When storage is ruled out, use the weekly pace (weekly ÷ days since Monday) as a proxy **[observed 2026-10-06]**.

## `mercenaryContractAuction.getPaginatedAuctions`
Inputs **[spec]**: `countryId`, `battleId`, `status` ∈ `active | won | expiredNoBids | expiredBattle | expiredRound | cancelled | terminated`, `cursor`, `limit` (1–50).
```json
{"items": [{"_id": "…", "country": "<countryId>", "createdBy": "<userId>", "battle": "<battleId>",
            "forCountry": "<countryId>", "forCountrySide": "attacker",
            "minimumDamage": 1008000, "budget": 100.8, "initialPerK": 0.1, "currentPerK": 0.1, "currentPayout": 100.8,
            "duration": 25, "professionalsOnly": false, "expiresAt": "iso", "bids": [], "status": "active"}],
 "nextCursor": "…"}
```
**Always pass `status`:** without it the call returned `{"items": []}` while `won` and `expiredNoBids` auctions existed **[observed 2026-11-02]**. Rules (fees, reputation, auction settings) are in `gameConfig.mercenaryContract`.

**Won contracts** (`status: "won"`) **[observed 2026-10-03]**:
- Extra fields `currentWinner` (**winning MU id**) and `currentWinnerUser` (the MU member who bid). `bids[]` = `{mu, user, perK, payout, bidAt}`. There is no MU filter input, so find an MU's contracts by matching `currentWinner`.
- **Round vs battle contracts:** contracts that carry `round` (roundId) + `roundNumber` are for that round. Contracts without them are for the whole battle. Roughly half of the won contracts had them. This was confirmed by the user from the game, not by the spec.
- **Reverse auction [observed 2026-10-04]:** bids start at `initialPerK` and step down; the **lowest** `perK` wins and becomes `currentPerK` (`payout = perK × minimumDamage/1000`).
- The paid terms are `currentPerK` / `currentPayout` (bidding can lower `perK` below `initialPerK`). `country == forCountry` in all 50 contracts sampled.
- The list is sorted by `createdAt` **descending**, so stop paging at the first contract older than your window. There were ~50 won contracts per 80 minutes. `duration` (auction minutes) ranged 5–25 (`gameConfig.mercenaryContract.auction.minDuration/maxDuration`). "Blitz" is not an API concept.
- Project: `warera.contracts.get_won_since(created_after)` → `cogs/tasks/military_unit_contract_monitor.py`.

**Who fought a won contract and what they earned [observed 2026-10-29, MU Wallachians, 22 won contracts over 10 battles]:** `mercenaryContract.getContracts` and `getById` (the per-contract participant data) answer 403 "API tokens cannot access this endpoint". The bot key can only get this **per battle**:
1. MU name → id: `search.searchAnything {searchText}` → `muIds`.
2. MU's contracts: page `getPaginatedAuctions {status: "won"}` and keep `currentWinner == muId`. The player who took the contract is `currentWinnerUser`.
3. Per member and battle: `battleLootSummary.getByBattleAndUser` (batched; `warera.battles.get_loot_summaries`) → `totalMoneyFromContract`, `totalDmg`, `totalMoneyFromBounty`. Check current `members` plus every `currentWinnerUser`.
- `totalMoneyFromContract` pools **every** contract the player was paid from in that battle, so two contracts in one battle can't be split. `totalDmg` is all of the player's battle damage, contract or not. When the battle's contracts share one `currentPerK`, contract damage = money ÷ perK × 1000 (the members' sum matched the summed `minimumDamage` to within rounding).
- **Is the contract finished?** The sum of members' `totalMoneyFromContract` for the battle equals the summed `currentPayout` once every contract in it is filled. This held even while the battle was still active. In 4 of 10 ended battles the current members' sum fell short, presumably because people who fought it have since left the MU **[assumption]**.
- **`expiredBattle` = never paid, not "completed"** **[observed 2026-11-04, 93 auctions May–Nov, 15 battles checked]**. The battle ended while the auction was still open: 67 of 93 had no winner, and for the 26 with a `currentWinner` the winning MU's members and taker were paid exactly the battle's `won` payouts (e.g. 451.00 won + 90.00 expiredBattle → 451.00 paid), or 0 when the MU had only `expiredBattle` ones. They are rare (about 93 in six months, against about 50 `won` per 3 h) and created late in the battle. A filled contract keeps `status: "won"` forever. So count fulfilled contracts from `won` only (user had first assumed the opposite; the data settled it). `limit` above 50 answers 400 `too_big`.
- With `status: "terminated"`, the scan returned the MU's contracts with `status: "won"` (the same items), so don't trust that filter value without checking each item's `status`.

**Explorer params that do NOT work** **[observed 2026-10-03]**: the community explorer lists `page`, `forCountry`, `forCountrySide`, `professionalsOnly`, `sortBy` (createdAt, expiresAt, budget, minimumDamage, currentPerK, duration) and `sortOrder` (asc, desc). On api2 **all of them are silently ignored**:
- `forCountrySide: "attacker"` still returned both sides.
- `professionalsOnly: true` returned both `true` and `false`.
- Budget asc and desc gave the same order.
- `page: 2` equalled page 1.
- `forCountry: <Romania>` returned other countries' contracts.

Use the spec's `countryId` (it does filter), `battleId`, `status`, `cursor` and `limit`, and filter or sort locally.
