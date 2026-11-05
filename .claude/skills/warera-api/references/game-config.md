# Domain: game config and game clock

**Solves:** every static game constant (so you don't hardcode it) and the game schedule (day rollover, regen ticks, elections, mission resets).

> **Rule:** before typing a game number into code (a cost, %, threshold, cooldown, skill value, item stat, upkeep scale or battle bonus), look it up here. If it's in `gameConfig.getGameConfig`, read it from the API (cache it, e.g. for 1h or on startup) instead of hardcoding it. If you must hardcode it, cite the config path in a comment.

> **Every value, in full:** the `warera-config` skill ([../../warera-config/references/config.md](../../warera-config/references/config.md)) lists every gameConfig value with its path. This file only maps the sections.

Labels: **[spec]** · **[observed 2026-10-03]** · **[project]** · **[assumption]**

---

## `gameConfig.getDates`
Input: none.
```json
{"previousDayAt": "2026-10-03T00:00:00.000Z", "nextDayAt": "2026-10-04T00:00:00.000Z",
 "nextRegenAt": "2026-10-03T06:00:00.000Z",
 "nextCongressElectionsAt": "2026-10-05T00:00:00.000Z", "nextPresidentialElectionsAt": "2026-11-01T00:00:00.000Z",
 "nextMonthAt": "2026-11-01T00:00:00.000Z",
 "dailyMissionRegenAt": "2026-10-04T00:00:00.000Z", "weeklyMissionRegenAt": "2026-10-05T00:00:00.000Z",
 "monthlyMissionRegenAt": "2026-11-01T00:00:00.000Z"}
```
Use it for "time until next election", "reset at" and "next regen" displays, and to align weekly windows (the project computes its week start locally in `top_user_weekly_donations._week_start`).

## `gameConfig.getGameConfig`
Input: none. ~33 KB, static, cache-friendly. Top-level sections **[observed]** and what they answer:

| Path | Contents (observed examples) |
|---|---|
| `user` | `maxEnergy` 100, `maxHunger` 10, `dailyXp`, **`isInactiveAfterDays` 3**, `marketMinLevel` 5 (v0.27), `featureUnlockLevels{market 5, managerJob 10, mu 5, party 15, produceAll 7, craft 7 (v0.27.4, was 10), openAllCases 7, bulkDismantle 7, workforceChart 15, fightSkills 10}, `chatSlowmode{tiers[], liftedAtLevel 15}` (replaced `chatMinLevel`) **[observed 2026-11-02]**`, `energyCostPerAction` 10, `skillPresets`, `donationMinLevel` 5, `activeCitizenMinLevel` 10, `citizenshipDaysCooldown` 30, `resetSkillsCostPerPoint`, `equipmentSets`, `kits`, `prestige{enabledLevel 50,…}`, `dailyReward` |
| `skills.<skill>.levels["0".."10"]` | `{value, cost, totalCost, unlockAtLevel, isABar?}` for each of `energy, stamina, health, hunger, attack, companies, production, criticalChance, criticalDamages, armor, precision, dodge, lootChance, management, leadership` (v0.27: `entrepreneurship` removed, `leadership` added; energy 100 + 10/level, production 30 + 3/level, management 1 + 1/level, leadership 0 + 1/level **[observed 2026-10-26]**). `armor`/`dodge` have `softCap`. `criticalChance`/`precision` have `skillOverflow`/`skillOverflowValue`. `stamina` has only level 0. Example: attack values 100, 125, 150 … (+25/level), and `totalCost` is the triangular sequence 0, 1, 3, 6, 10 … |
| `battle` | `roundsToWin` 2, `maxRounds` 15, `pointsToWinRound` 300, `tickPoints{"1":1,"100":2,…}`, `healthCost` 10, `countryOrderBonusPercent` 10, `muOrderBonusPercent` 10, `allianceDamagesBonusPercent`, `enemyDamagesBonusPercent`, `patrioticBonusPercent` 20, maluses, `setCountryOrderMoneyCost` 30, `setMuOrderMoneyCost` 10, `hitFor1CaseInPool`, `casesPer1kDamagesInPool`, `rankingsLootPercentPer1kDmg` |
| `upgradesConfig.<type>` | `{levels{"1"..}, canDowngrade, canBeDisabled?, canBeDestroyed?, pendingDurationHours?}`. Region types (`bunker`, `base`): `steelCost`, `constructionPointsCost`, **`maintenanceCostCountryDevScale`** (0.04/0.08/0.16/0.32/0.64), **`minimumMaintenanceCost`**, `stats{defenseBonus|attackBonus}`. `pacificationCenter`: **`maintenanceCostRegionDevScale`** (0.05/0.10/0.20/0.40/0.80), `stats.resistanceGrowthReduction`. Company types: `storage{maxProduction}`, `automatedEngine{dailyProd}`, `breakRoom{maxWorkers}` (v0.27: levels 1/2/3 → 1/2/3 employees for 0/20/80 steel). MU types: `headquarters{maintenanceCost, attackBonus}`, `dormitories{members}` |
| `upgrade` | `refundPercent`, `regionUpgradeCooldownHours`, `regionDowngradeCooldownHours`, `constructionPointsPerContribution`, `constructionContributionMinLevel` |
| `items.<code>` | 97 items on 2026-11-02 (60 before v0.27). `type` ∈ `raw, product, weapon, equipment, case, tool`: 36 employee **tools** (`caliper`, `flask`, `hammer`, `pickaxe`, `sickle`, `skillet` 1–6, common→mythic, `dynamicStats.production` [3,6] … [46,65], not tradable) and the `toolbox` case **[observed 2026-11-02]**. Products: `productionPoints`, `productionNeeds{input: qty}`, `flatStats` (food `healthRegenPercent`: bread 10, steak 15; ammo `percentAttack`: lightAmmo 10), `isConsumable`, `isTradable`. Weapons and equipment: `rarity`, `usage`/slot, `dynamicStats{stat: [min, max]}` (knife attack [21,40], helmet1 criticalDamages [1,15]) |
| `mergingCost` | per rarity: common 2 … mythic 64 |
| `region` | resistance rules, `transferDaysCooldown`, `liberationDaysCooldown`, **`nonAggressionHoursAfterLiberation` 24**, **`nonAggressionHoursAfterPeace` 72**, `depleteHourlyPercent`, `depositsEnabled` false, `developmentIncomeMultiplier` 2, `strategicResourceIncomeMultiplier` 2. Gone: `citizenIncomeTaxPercent`, `resourcesBonus`, `regionNotLinkedToCapitalMalusDevelopmentPercent` **[observed 2026-11-02]** |
| `company` | `constructionCostIncreasePerCompany`, `moveCost`, `changeItemCost`, `depositResourceBonus` 30, `destructionValuePercent` |
| ~~`worker`~~ | removed in v0.27 (was `maxFidelity`, `fidelityProductionBonusPercent`) **[observed 2026-10-26]** |
| `mu` | `constructionCost` 300, `maxOwnedMus` 3, `helpCooldownHours`, `healthPerHelp` 2, `helperHealthPerHelp` 1 (new), `nationalityChangeCooldownDays` |
| `law` | voting thresholds and durations, per-law settings (`create_alliance`, `define_enemy_country`, `sendMoneyToCountry`, …) |
| `election` | `voteMinLevel` 20, `candidateMinLevel` 20 (was 15) **[observed 2026-11-02]**, `voteCitizenshipLockNewCountryMultiplier` 2, durations |
| `government` | cooldowns, `presidentWagePercent`, `memberWagePercent` |
| `unrest` | revolution and unrest bar rules |
| `mercenaryContract` | `auction{minDuration, maxDuration, minPerK, bidStep, maxDamagePerContract,…}`, `acceptanceFeePercent`, `cancellationPenaltyPercent`, `reputation{…}`, `bountyCooldownMinutes`, `maxBountyPpMultiplier` 9 (replaced `maxBountyWageMultiplier` 6) **[observed 2026-11-02]** |
| `loot` | `weaponChancePercent` 30, `damagePerLootItem`, `battleLootDamagePerLootItem` |
| `badge`, `mission`, `referral`, `newspaper`, `alliance`, `party`, `country{maxTaxAmount, conqueredRegionCoreTaxPercent 10}`, `citizenshipApplication{…, newCountryBordersOpenDays 7}`, `announcement`, `org`, `subSkinReward` | misc rules (`newspaper.commentMinLevel` gone) |

### Values the project currently hardcodes that exist here [project vs observed]

| Project constant | Config path |
|---|---|
| `UPKEEP_PCTS` in `cogs/commands/get_region_upgrade_cost.py` | `upgradesConfig.{bunker,base}.levels[n].maintenanceCostCountryDevScale`, `upgradesConfig.pacificationCenter.levels[n].maintenanceCostRegionDevScale` (values identical). The config also has `minimumMaintenanceCost`, which the command ignores; whether upkeep = max(scale×dev, minimum) is an **[assumption]** |
| `_INACTIVE_THRESHOLD_SECONDS = 3*24*3600` in `inactive_players.py`, `mu_stray.py` | `user.isInactiveAfterDays` (3) |
| `SKILL_LEVEL_COST`, `MAX_SKILL_LEVEL` in `damage.py`; `triangular()` in `utils/computational.py` | `skills.<s>.levels[n].totalCost`, number of levels |
| `FOOD[*].health_pct`, `AMMO[*].dmg_bonus` in `damage.py` | `items.<food>.flatStats.healthRegenPercent`, `items.<ammo>.flatStats.percentAttack` |
| `MILITARY_RANK_BONUSES` in `damage.py` | not in config, but `user.getUserLite().skills.attack.militaryRankPercent` returns the computed value per user (rank 97 → 30, which matches the table) |
| `GEAR[*].mods` in `damage.py` | `items.<code>.dynamicStats` gives min/max ranges, not one value. A real player's rolled values come from `inventory.fetchCurrentEquipment` |
