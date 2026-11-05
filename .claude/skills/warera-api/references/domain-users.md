# Domain: users, search, equipment

**Solves:** username → ID, player profile, level, activity and last login, skill build (eco vs fight), health and hunger bars, buffs and debuffs, military rank, MU membership, wealth, equipped gear, and country citizens.

Labels: **[spec]** · **[observed 2026-10-03]** · **[project]** · **[assumption]**

---

## `search.searchAnything`
Input: `searchText*` (minLength 1) **[spec]**.
```json
{"userIds": ["…"], "muIds": [], "countryIds": ["…"], "regionIds": ["…"], "partyIds": [], "allianceIds": [], "hasData": true}
```
- Returns IDs only. The search is fuzzy: "Romania" matched 5 users plus the country and a region **[observed]**.
- There's **no exact username endpoint**. The project's `warera.users.find_by_name(username)` runs search, fetches the hits with one batched `getUserLite` and keeps the exact `username ==` match, then caches name→ID in `warera.users.username_ids` **[project]**. Reuse it.
- **Quote the name for an exact search.** A plain search returns at most 5 users, and short names get crowded out by longer names containing them ("Tert", "Ptm" and "Aladin" each missed their own player). `searchText: "\"Tert\""` acts as a case-insensitive exact phrase: across 257 linked server members it found every player, 250 of them as the only result. `^Tert$` also worked, with more extra results **[observed 2026-10-24; not in the spec]**. `warera.users.find_by_name` and `warera.users.find_many_by_name` search quoted first and fall back to the plain name only when that finds no exact match (`warera/endpoints/users.py` `_quoted`) **[project]**. Keep that fallback: the quoted search can return **no hits** for a real exact username (`"Dantenie83"` → empty, plain `Dantenie83` → the one user) **[observed 2026-10-29]**.

## `user.getUserLite`
Input: `userId*`, which must match `^[a-f\d]{24}$` (400 `"Invalid user id"` otherwise) **[spec+observed]**.

```jsonc
{
  "_id": "…", "username": "…", "country": "<countryId>", "mu": "<muId>",      // mu absent if none
  "isActive": true, "militaryRank": 97, "avatarUrl": "…", "createdAt": "iso",
  "leveling": {"level": 1, "xp": 70, "totalXp": 70, "dailyXpLeft": 100,
               "availableSkillPoints": 4, "spentSkillPoints": 0, "totalSkillPoints": 4,
               "freeReset": 2, "prestige": 0, "prestigeLevel": 0},
  "skills": {
    // bar skills (energy, health, hunger, production, stamina) also have:
    //   currentBarValue, hourlyBarRegen
    "health": {"level": 4, "value": 140, "total": 140, "currentBarValue": 3.1, "hourlyBarRegen": 14,
               "weapon": null, "equipment": null, "overflow": null, "limited": null, "totalAfterSoftCap": null, "prestige": 0},
    "attack": {"level": 8, "value": 300, "weapon": 113, "equipment": null, "overflow": 160,
               "ammoPercent": 10, "buffsPercent": 60, "debuffsPercent": 0, "militaryRankPercent": 30,
               "total": 1311, "limited": null, "totalAfterSoftCap": null, "prestige": 0},
    // also: stamina, energy, hunger, companies, production, criticalChance,
    //       criticalDamages, armor, precision, dodge, lootChance, management, leadership
    // v0.27 (2026-10-25): entrepreneurship removed, leadership added [observed 2026-10-26]
  },
  "dates": {"lastConnectionAt": "iso", "lastWorkAt": "iso", "lastDailyCalendarClaimedAt": "iso",
            "lastSkillsResetAt": "iso", "lastHelpAskedAt": "iso", "lastCitizenshipChangeAt": "iso",
            "lastDailyRewardClaimedAt": "iso", "lastFreeTravelHomeAt": "iso", "lastManagerCareAt": "iso",
            "lastNotificationsCheckAt": "iso", "lastSeenAnnouncementAt": "iso", "lastFiredFromGovAt": "iso",
            "lastTakingControlAt": "iso", "lastComebackClaimedAt": "iso", "missionXpCompensatedAt": "iso", …},
            // keys absent until the action happens. lastCompanyJoinedAt and lastHiresAt are gone (0 of 24 users)
            // and lastWorkOfferApplications is pre-v0.27 [observed 2026-11-02]
  "buffs": {"buffCodes": ["cocain"], "buffEndAt": "iso", "debuffWarningNotifiedAt"?: "iso"}
         | {"debuffCodes": ["cocain"], "debuffEndAt": "iso"},   // absent/null when neither is active [observed 2026-10-06]
  "rankings": {"userWealth": {"value","rank","tier"}, "userLevel": {…}, "userReferrals": {…}, "userMissionsClaimed": {…}},
  "stats": {}, "infos": …, "equippedSkinKeys": …, "skillsExpiration": …, "animatedAvatarUrl": …
}
```
Notes:
- `skills.<s>.total` is the **server-computed effective stat** including weapon, equipment, buffs, ammo and military rank. Prefer it over recomputing **[observed; exact formula not documented]**.
  - **Attack** **[observed 2026-10-15]**: `(value + weapon + equipment + overflow) × (1 + ammoPercent/100) × (1 + buffsPercent/100) × (1 + militaryRankPercent/100)` reproduces `total`. For example, (100 + 29) × 1.3075 = 168.7, and the API gave 169. **Don't apply the military rank (or ammo, or Pill) again on top of `total`.** The battle bonus isn't in it.
  - **Armor/Dodge `totalAfterSoftCap`** is the mitigation **percent**, not a stat. It equals `total / (total + 40)` rounded to 2 significant figures **[observed 2026-10-15]**: armor 22 → 35, dodge 13 → 25. `damage._mitigation(total, 40)` reproduces it.
  - Live damage estimate from these totals and the bars: `cogs/commands/damage.estimate_fight_damage(user, battle_bonus, game_config)` **[project]**.
- **Prestige** **[observed 2026-10-26, 60 top-level players]**:
  - `leveling.prestigeLevel` = the number of Prestiges = the player's Prestige Points; all 60 had 2. `leveling.prestige` was 0 for all of them; its meaning isn't established.
  - `skills.<s>.prestige` = bonus levels on that skill. `value` = the table value at `level + prestige`, also from base 0 (Energy 0+1 = 110) and past 10 with the table's last step (Companies 10+1 = 13; Attack 6+1 = 275; Loot 9+1 = 25).
  - `totalSkillPoints` = level × 4 for all of them.
  - Players put Prestige on Companies, Energy, Production, Leadership, Management and combat skills alike.
- **Damage per day:** no field gives it. Snapshot the all-time `rankings.userDamages.value` at each reset and subtract. It updates within minutes: in a 2-minute window it rose by 24,568 for one player and 3,571 for another, while their `muMember.totalDamagesCount` didn't change **[observed 2026-11-01, 25 members]**. So prefer it over `muMember` counters for near-real-time deltas, and it doesn't depend on MU membership. `cogs/tasks/contests.py` does this **[project]**.
- `warera.game.get_ranking(filter)` takes the `rankingType` **string** (`"userLevel"`), not a dict; a dict gets a 400 **[project]**.
- **Battle damage bonus per player:** not readable with an API key. `battle.getDamageBonuses` is session-only (client-discovered.md §B). Derive only what's visible:
  - patriotic: `user.country` equals the side's `country`;
  - orders: `battleOrder.getByBattle` `priority`, low/medium/high = +5/+10/+15%; the config's 10 is the medium value;
  - MU headquarters: `upgrade.getUpgradeByTypeAndEntity`, active → `gameConfig.upgradesConfig.headquarters.levels[n].stats.attackBonus`.

  Alliance, pacts, sworn enemy, buildings and maluses stay unknown. See `cogs/tasks/loot_alerts.bonus_parts` **[project]**.
- Economy vs fight classification in the project: economy skills are `utils/computational.ECONOMY_SKILLS` = `energy, companies, management, leadership, production` (since v0.27, 2026-10-25: Entrepreneurship was removed; live `gameConfig.skills` keys checked 2026-10-29), and the rest are fight skills. Points spent per skill are `triangular(level)` (`utils/computational.py`) **[project]**. The same cost table is in `gameConfig.skills.<s>.levels[n].totalCost`. Use `utils/computational.is_economy_build(user)` (economy + unspent points > 50% of total; `None` without points) instead of re-implementing it; `skill_roles.py` and `military_unit_daily_report.py` use it. `promotions.py` and `utils/api.fight_status_from_user` keep their own loops but import `ECONOMY_SKILLS` (their private copies still had `entrepreneurship` until 2026-10-29), so a skill change is edited only in `utils/computational.py`; grep for skill-name lists before assuming it is the only copy **[project]**.
- **Pill phase without storing anything** **[observed 2026-10-06, 23 MU members]**: the pill's item code is `cocain` (in `buffCodes`/`debuffCodes`). `buffs` holds *either* the buff *or* the debuff, never both. Durations come from `gameConfig.items.cocain.flatStats.buffDurationHours` (8) / `debuffDurationHours` (15.5), so read them rather than hardcoding. Then:
  - buff active → pilled at `buffEndAt − buff`; next pill possible at `buffEndAt + debuff`
  - debuff active → pilled at `debuffEndAt − debuff − buff`; next pill possible at `debuffEndAt`
  - neither → a pill can be taken now (the time of the last pill is unknown)
  Checked for consistency: derived pill times matched members' `lastConnectionAt`. `get_fight_status` and `buff_monitor.py` read only the end-time keys.
- Other activity questions answered by `dates` alone: skill reset in the last N hours (`lastSkillsResetAt`; next reset after `gameConfig.user.resetSkillDaysCooldown` days), MU help requested today (`lastHelpAskedAt`; cooldown `gameConfig.mu.helpCooldownHours`), offline for a while (`lastConnectionAt`). Bars at their cap: `skills.health|hunger.currentBarValue >= total`.

## `user.getUserById`
Input: `userId*` (no regex) **[spec]**. Superset of lite **[observed]**, with these extra fields:
- `region` (residence region), `location` (current region), `usernameLower`, `emailVerified`, `canOnboard`
- `stats`: `{dailyRewardBestStreak, dailyRewardStreak, worksCount, damagesCount, wealth{companies, items, money, equipments, weapons, total}, case1/case2/toolbox{openedCount, byRarity}, woodenCase{openedCount, byItem}, milestoneTiersClaimed, milestoneXpClaimed}`. Some users also have `estimatedWealth`, `estimatedCompanyValues`, `estimatedInventoryValue` (6 of 24), `gemsPurchased`, `damagesRanking` **[observed 2026-11-02]**. Prefer `wealth`, which every user has.
- `missions`: `{claimedCount, totalXpClaimed, claimedAt{starting, daily, weekly, monthly}, rerolledDailyMissions, rerolledWeeklyMissions, rerolledMonthlyMissions}` **[observed 2026-10-29]**. `claimedCount` is **lifetime** and equals `rankings.userMissionsClaimed.value`. `claimedAt.<period>` is the last claim in that period; a daily claim after `gameConfig.getDates.previousDayAt` means the player claimed dailies today. It is probably the all-dailies-finished bonus (`mission.reward.daily.xpWhenFinished`) **[assumption]**. Mission progress and per-day counts are not readable: `mission.getUserMissions` and `getUserMissionsResumee` are 403 for API keys (client-discovered.md F). **Missions completed today** therefore needs a stored snapshot of `claimedCount` at the 00:00 UTC rollover, diffed against the current value **[project, not built]**.
- `company` (the employer's company id) is **gone**: 0 of 24 full users had it on 2026-11-02, matching the end of the job market in v0.27 **[observed 2026-11-02]**. A player works in their own companies or as a manager (`manager.getByCompanyId` per company); there is no per-user "my manager job" field. `party` and `mu` are absent when the player has none. `dates.lastDailyCalendarClaimedAt` is the daily login reward claim; `dates.lastDailyRewardClaimedAt` stopped updating in August 2026 **[observed 2026-10-25, 40 players]**. Used by `/progression`.
- `preferences`: `{locale, autoEquipMode, …}`, `muMaxLevelRewarded`, `finishedTours{military, economic, onboarding}`, `updatedAt`
- Also **[observed 2026-11-02]**: `energyGift{amount, grantedAt, claimedAt}`, `skillVersion`, `availableColorSchemes[]`, `shouldUpdateProfile`, `equipment`, and on some users `orgs`, `discord`, `warning`. `infos` (lite too) = `{isPremium, premiumMonthsCount, colorScheme, banner, font, description, usernameEffect, presidentOf?}`; `presidentOf` is the country id of a sitting president.

Lite included `buffs`, `mu` and `avatarUrl` for an active fighter. **[observed 2026-10-14, 24 MU members]** the full object returned `buffs`, `skills`, `dates`, `leveling` and `mu` identical to lite; only `skillsExpiration`, `infos` and `equippedSkinKeys` were sometimes missing. `stats.wealth.total` equals the sum of its five categories and `rankings.userWealth.value`. The project's "fight wealth" is `total` minus `companies` (`utils/computational.fight_wealth`), tiered GOLD ≥15K, SILVER ≥10K, BRONZE ≥5K, IRON below.

## `user.getUsersByCountry`
Inputs: `countryId*`, `limit` (1–100, default 10), `cursor` **[spec]**.
Returns `{items: [{_id, createdAt}], nextCursor}`, **IDs only** **[observed]**. Order appears to be newest first (cursor encodes a date) **[assumption]**.
Each citizen needs its own `getUserLite` call, which is N+1 and expensive under the ~100 req/min budget. Before writing a per-citizen loop, check whether `ranking.getRanking` (items carry `country`, `user`, `mu`, `value`) already answers the question.

## `inventory.fetchCurrentEquipment`
Input: `userId*` **[spec]**. Returns `{}` when nothing is equipped **[observed]**.
```jsonc
{"weapon": {"_id": "…", "code": "sniper", "skills": {"attack": 113, "criticalChance": 18}, "state": 34, "maxState": 100, "quantity": 1, "lastAcquisitionAt": "iso"},
 "ammo": "lightAmmo",
 "helmet": {"type": "equipment", "code": "helmet5", "skills": {"criticalDamages": 107}, "state": 48, "maxState": 100, …},
 "chest":  {"code": "chest4",  "skills": {"armor": 23}, …},
 "pants":  {"code": "pants4",  "skills": {"armor": 23}, …},
 "boots":  {"code": "boots6",  "skills": {"dodge": 54}, …},
 "gloves": {"code": "gloves6", "skills": {"precision": 55}, …}}
```
`state / maxState` is durability. Slot stat mapping per `gameConfig.items[code].dynamicStats` **[observed]**: helmet → criticalDamages, chest/pants → armor, boots → dodge, gloves → precision, weapon → attack + criticalChance.

---

# Procedures not in the official spec (from the community explorer, verified live 2026-10-03)

Source: `https://warera.realmarijn.nl/api-explorer` **[explorer]**. All work anonymously.

## Targeted search

### `search.searchUsers`
Input: `searchText*`. Returns a **flat array of user IDs** `["<userId>", …]` (max 5 observed) **[observed]**.
- It's fuzzy: `"dan"` returned 5 IDs, while the exact username `"Sunnybunny"` returned just that one ID. Unlike `searchAnything`, it still missed `Tert` unquoted **[observed 2026-10-24]**; the quoted form wasn't tested here.
- It's equivalent to `search.searchAnything().userIds` but without the other entity types. You still need `user.getUserLite` plus an exact `username` match. `warera.users.find_by_name()` in `warera/endpoints/users.py` uses `searchAnything`; switching would only trim the payload.

### `search.searchMus`
Input: `searchText*`. Returns a flat array of MU IDs (5 for `"Legion"`; `[]` when nothing matches) **[observed]**. Alternative: `mu.getManyPaginated {search}` returns full MU objects.

## Premium shop and community (low relevance for this bot)

| Procedure | Input | Returns **[observed]** |
|---|---|---|
| `shop.getLastGifts` | none | `[{_id, giftedBy: userId, recipient: userId, createdAt}]` (3 items) |
| `shop.getSubscribedUsers` | none | `[{_id: userId, subscriptionDate}]` (recently started Premium; 6 items) |
| `shop.getTopGiftGivers` | none | `[{_id: userId, giftCount, username}]` (top 10; note `username` is included) |
| `giveaway.getManyPaginated` | `limit` (1–100), `cursor` | `{items: [{prize: {case1: 150}, winnersQuantity, participants: [userId…8.6k], winners: [userId], startAt, endAt, isActive}], nextCursor}` |
