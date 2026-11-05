# WarEra game configuration — complete reference

Every section of https://warera.realmarijn.nl/game-config, in the wiki's order, with the matching
`gameConfig.getGameConfig` path for each value so code can read it instead of hardcoding it.

**Sources and labels**
- **[wiki]**: the wiki page (its data was "updated 2026-09-15 22:57:34 UTC" when fetched on 2026-10-04; the site says it refreshes hourly from the API).
- **[live]**: `gameConfig.getGameConfig` / `gameConfig.getDates`, fetched 2026-10-04 ~05:56 UTC. Raw copy: [game-config.snapshot.json](game-config.snapshot.json).
- **[live-only]**: present in the API but not shown on the wiki page.
- **⚠ differs**: the wiki and the live API disagree. **Live wins.**
- **[observed]** / **[assumption]**: same meaning as in the `warera-api` skill.

Where no unit is in the key name (e.g. `constructionCost`), the config doesn't state the unit (money, steel, …). Don't invent one.

---

## 1. 📅 Times & dates — `gameConfig.getDates`

These are moving timestamps, not constants. **Always read them from the API**; never compute them from this table.

| Wiki label | API field | Wiki value (2026-09-15) | Live value (2026-10-04) |
|---|---|---|---|
| Previous day started | `previousDayAt` | Tue 15 Sep 2026 02:00 | 2026-10-04T00:00:00Z |
| Next day starts | `nextDayAt` | Wed 16 Sep 2026 02:00 | 2026-10-05T00:00:00Z |
| Next regen | `nextRegenAt` | Wed 16 Sep 2026 01:00 | 2026-10-04T06:00:00Z |
| Next month starts | `nextMonthAt` | Thu 1 Oct 2026 02:00 | 2026-11-01T00:00:00Z |
| Congress elections | `nextCongressElectionsAt` | Mon 5 Oct 2026 02:00 | 2026-10-05T00:00:00Z |
| Presidential elections | `nextPresidentialElectionsAt` | Thu 1 Oct 2026 02:00 | 2026-11-01T00:00:00Z |
| Daily missions reset | `dailyMissionRegenAt` | Wed 16 Sep 2026 02:00 | 2026-10-05T00:00:00Z |
| Weekly missions reset | `weeklyMissionRegenAt` | Mon 21 Sep 2026 02:00 | 2026-10-05T00:00:00Z |
| monthlyMissionRegenAt (shown raw) | `monthlyMissionRegenAt` | 2026-10-01T00:00:00.000Z | 2026-11-01T00:00:00Z |

Schedule rules derived from these values **[observed]**:
- The wiki shows times in **Europe/Amsterdam (CEST, UTC+2)**; the API returns **UTC**. "02:00" on the wiki = **00:00 UTC**.
- **Game day rolls over at 00:00 UTC**; daily missions reset then too.
- **Regen ticks every hour on the hour (UTC).** At 22:57 UTC the next regen was 23:00 UTC; at 05:56 UTC it was 06:00 UTC.
- **Weekly missions reset Monday 00:00 UTC.** Month and monthly missions roll over on the **1st at 00:00 UTC**.
- **Presidential elections fall on the 1st of the month** (2026-10-01, then 2026-11-01).
- **Congress elections**: both fetches returned 2026-10-05, so the cadence can't be inferred. Read `nextCongressElectionsAt`.

---

## 2. 👤 Player limits — `user`

| Wiki label | API path | Value |
|---|---|---|
| Max energy | `user.maxEnergy` | 100 |
| Max hunger | `user.maxHunger` | 10 |
| Max construction points | `user.maxConstructionPoints` | 30 |
| Daily XP | `user.dailyXp` | 100 |
| Daily reward | `user.dailyReward` | xp: 50, money: 10, case1: 1 |
| Inactive after (days) | `user.isInactiveAfterDays` | 3 |
| Market min. level | `user.marketMinLevel` | 7 |
| Donation min. level | `user.donationMinLevel` | 5 |
| Chat min. level | `user.chatMinLevel` | 8 |
| Active citizen min. level | `user.activeCitizenMinLevel` | 10 |
| Country takeover min. level | `user.canTakeControlAtLevel` | 25 |
| Citizenship cooldown (days) | `user.citizenshipDaysCooldown` | 30 |
| Skill reset cooldown (days) | `user.resetSkillDaysCooldown` | 7 |
| Skill reset cost/point | `user.resetSkillsCostPerPoint` | 0.5 |
| XP per action | `user.xpPerAction` | 10 |
| Energy per action | `user.energyCostPerAction` | 10 |
| Energy per construction point | `user.constructionEnergyCost` | 10 |
| Regen divider | `user.regenDividedBy` | 10 |
| Takeover cooldown (days) | `user.takeControlCooldownInDays` | 1 |
| Equipment sets (free) | `user.equipmentSets.nonPremiumMax` | 1 |
| Equipment sets (premium) | `user.equipmentSets.premiumMax` | 5 |
| Kits (free) | `user.kits.nonPremiumMax` | 6 |
| Kits (premium) | `user.kits.premiumMax` | 30 |

**[live-only] Prestige** — `user.prestige`

| API path | Value |
|---|---|
| `user.prestige.enabled` | true |
| `user.prestige.enabledLevel` | 50 |
| `user.prestige.xpPenalty` | 65000 |
| `user.prestige.xpMultiplierPercent` | 50 |
| `user.prestige.xpMultiplierPerLevelPercent` | 10 |
| `user.prestige.skillBonusLevels` | 1 |

`user.fieldsToPopulate` [live-only] is an internal Mongo projection string, not a game rule.

---

## 3. ⚔️ Battle — `battle`

| API path | Value |
|---|---|
| `battle.roundsToWin` | 2 |
| `battle.maxRounds` | 15 |
| `battle.pointsToWinRound` | 300 |
| `battle.tickPoints` | `{"1":1, "100":2, "200":3, "300":4, "400":5, "500":6}` (threshold → points per tick; config doesn't say what the threshold measures) |
| `battle.healthCost` | 10 |
| `battle.countryOrderBonusPercent` | 10 |
| `battle.muOrderBonusPercent` | 10 |
| `battle.allianceDamagesBonusPercent` | 10 |
| `battle.enemyDamagesBonusPercent` | 10 |
| `battle.regionNotLinkedToCapitalMalusPercent` | -25 |
| `battle.lostAttackingRegionMalusPercent` | -25 |
| `battle.setCountryOrderMoneyCost` | 30 |
| `battle.setMuOrderMoneyCost` | 10 |
| `battle.setOrderMoneyCost` | 40 |
| `battle.patrioticBonusPercent` | 20 |
| `battle.occupyingYourRegionsMalusPercent` | -50 |
| `battle.govMemberBountyRewardPercent` | 50 |
| `battle.hitFor1CaseInPool` | 20 |
| `battle.casesPer1kDamagesInPool` | 1 |
| `battle.rankingsLootPercentPer1kDmg` | 1.5 |

---

## 4. 🏢 Organization — `org`

| API path | Value |
|---|---|
| `org.constructionCost` | 1000 |
| `org.moveCost` | 5 |

## 5. 🏭 Company — `company`

| API path | Value |
|---|---|
| `company.constructionCostIncreasePerCompany` | 50 |
| `company.moveCost` | 5 |
| `company.changeItemCost` | 5 |
| `company.depositResourceBonus` | 30 |
| `company.destructionValuePercent` | 80 |

The max number of companies a player can own comes from the `companies` skill (section 29), not from `company`.

## 6. 👷 Worker — `worker`

| API path | Value |
|---|---|
| `worker.maxFidelity` | 10 |
| `worker.fidelityProductionBonusPercent` | 1 |

## 7. 🎖️ Military unit (MU) — `mu`

| API path | Value |
|---|---|
| `mu.constructionCost` | 300 |
| `mu.moveCost` | 5 |
| `mu.destructionValuePercent` | 80 |
| `mu.maxOwnedMus` | 3 |
| `mu.helpCooldownHours` | 12 |
| `mu.healthPerHelp` | 2 |
| `mu.helpValue` | 2 |
| `mu.nationalityChangeCooldownDays` | 7 |

MU member cap comes from the `dormitories` upgrade (section 12).

---

## 8. 📜 Legislation — `law`

| API path | Value |
|---|---|
| `law.abusiveLawPossibleVotersNeeded` | 5 |
| `law.abusiveLawsCooldownInDays` | 3 |
| `law.lawVotesDurationHours` | 24 |
| `law.votersRatioNeeded` | 0.5 |

**Cost per law** — `law.<lawName>`

| Law | Cost (`.cost`) | Maintenance (`.maintenanceCost`) | Other |
|---|---|---|---|
| `create_alliance` | 20 | 1 | |
| `leave_alliance` | 0 | — | |
| `accept_join_alliance` | 0 | — | |
| `define_enemy_country` | 10 | 3 | |
| `set_color_scheme` | 5 | — | |
| `sendMoneyToCountry` | — | — | **⚠ differs** (wiki shows only "—"): live has `allianceTaxRate` **0.5**, `externalTaxRate` **1** |

## 9. 🗳️ Elections — `election`

| API path | Wiki | Live |
|---|---|---|
| `election.candidateDurationHours` | 24 | 24 |
| `election.electionVoteDurationHours` | 24 | 24 |
| `election.voteMinLevel` | 15 | **20 ⚠ differs** |
| `election.candidateMinLevel` | 15 | 15 |
| `election.voteMinDaysSinceCitizenshipChange` | — | **7** [live-only] |

---

## 10. 🏅 Badges — `badge.<code>`

Columns: `reward`, `availabilities`, `cooldownDays`. The **Preserved** column is `preserveBetweenReset` [live-only] (whether the badge survives a game reset).

| Badge | Reward | Available for | Cooldown (days) | Preserved [live-only] |
|---|---|---|---|---|
| `referral` | 20 | user | — | |
| `foundingFather` | 0 | user | — | ✓ |
| `countryPresident` | 0 | user | 20 | |
| `congressMember` | 0 | user | — | |
| `vicePresident` | 0 | user | 20 | |
| `govMember` | 0 | user | 20 | |
| `battleTop1` | 10 | user | — | |
| `roundTop1` | 5 | user | — | |
| `hardWorker` | 5 | user | — | |
| `battleTerrainTop1` | 10 | user | — | |
| `roundTerrainTop1` | 5 | user | — | |
| `voted` | 0 | user | — | |
| `coffee` | 0 | user | — | ✓ |
| `alphaTester` | 0 | user | — | ✓ |
| `bugFinder` | 0 | user | — | ✓ |
| `resetSurvivor` | 0 | user | — | ✓ |
| `prestige` | 0 | user | — | ✓ |
| `premium` | 0 | user | — | ✓ |
| `staff` | 0 | user | — | ✓ |
| `giftPremium` | 0 | user | — | ✓ |
| `sugarDaddy` | 0 | user | — | ✓ |
| `babyBoomer` | 100 | user | — | ✓ |
| `countryTournamentWinner` | 50 | country, user | — | ✓ |
| `muTournamentWinner` | 50 | mu, user | — | ✓ |
| `giveawayWinner` | 0 | user | — | |
| `popularArticle` | 0 | user | — | ✓ (also `uniqueMetadataKey: "article"`) |
| `translator` | 0 | user | — | ✓ |
| `exploitFinder` | 0 | user | — | ✓ |

28 badges in total.

## 11. 🔀 Merging costs — `mergingCost.<rarity>`

| common | uncommon | rare | epic | legendary | mythic |
|---|---|---|---|---|---|
| 2 | 4 | 8 | 16 | 32 | 64 |

---

## 12. ⬆️ Upgrades — `upgradesConfig.<type>`

Each level lives at `upgradesConfig.<type>.levels["<n>"]` and has `steelCost` and `stats`. Columns marked [live-only] aren't on the wiki.

### headquarters (MU)
Flags: `canBeDisabled` true · `pendingDurationHours` 3 · `canDowngrade` true

| Level | Steel cost | Maintenance (`maintenanceCost`) | Bonuses |
|---|---|---|---|
| 1 | 100 | 1 | attackBonus: 5 |
| 2 | 200 | 2 | attackBonus: 10 |
| 3 | 300 | 5 | attackBonus: 15 |
| 4 | 600 | 10 | attackBonus: 20 |

Max level 4.

### dormitories (MU)
Flags: `canDowngrade` true

| Level | Steel cost | Bonuses |
|---|---|---|
| 1 | 0 | members: 5 |
| 2 | 200 | members: 10 |
| 3 | 300 | members: 15 |
| 4 | 400 | members: 20 |
| 5 | 500 | members: 25 |

Max MU size is 25 members at level 5.

### bunker (region)
Flags: `canDowngrade` true · `pendingDurationHours` 12 · `canBeDisabled` true · `canBeDestroyed` true

| Level | Steel cost | Construction points [live-only] | Maint. country-dev scale [live-only] | Min. maintenance [live-only] | Bonuses |
|---|---|---|---|---|---|
| 1 | 100 | 100 | 0.04 | 1 | defenseBonus: 5 |
| 2 | 200 | 200 | 0.08 | 2 | defenseBonus: 10 |
| 3 | 300 | 300 | 0.16 | 5 | defenseBonus: 15 |
| 4 | 500 | 500 | 0.32 | 10 | defenseBonus: 20 |
| 5 | 1000 | 1000 | 0.64 | 25 | defenseBonus: 25 |

### pacificationCenter (region)
Flags: `canDowngrade` true · `pendingDurationHours` 12 · `canBeDisabled` true · `canBeDestroyed` true

| Level | Steel cost | Construction points [live-only] | Maint. region-dev scale [live-only] | Min. maintenance [live-only] | Bonuses |
|---|---|---|---|---|---|
| 1 | 100 | 100 | 0.05 | 1 | resistanceGrowthReduction: 0.05 |
| 2 | 200 | 200 | 0.10 | 2 | resistanceGrowthReduction: 0.1 |
| 3 | 300 | 300 | 0.20 | 5 | resistanceGrowthReduction: 0.15 |
| 4 | 500 | 500 | 0.40 | 10 | resistanceGrowthReduction: 0.2 |
| 5 | 1000 | 1000 | 0.80 | 25 | resistanceGrowthReduction: 0.25 |

Note: pacificationCenter scales maintenance by **region** development (`maintenanceCostRegionDevScale`); bunker and base scale by **country** development (`maintenanceCostCountryDevScale`).

### base (region)
Flags: `canDowngrade` true · `pendingDurationHours` 12 · `canBeDisabled` true · `canBeDestroyed` true

| Level | Steel cost | Construction points [live-only] | Maint. country-dev scale [live-only] | Min. maintenance [live-only] | Bonuses |
|---|---|---|---|---|---|
| 1 | 100 | 100 | 0.04 | 1 | attackBonus: 5 |
| 2 | 200 | 200 | 0.08 | 2 | attackBonus: 10 |
| 3 | 300 | 300 | 0.16 | 5 | attackBonus: 15 |
| 4 | 500 | 500 | 0.32 | 10 | attackBonus: 20 |
| 5 | 1000 | 1000 | 0.64 | 25 | attackBonus: 25 |

### storage (company)
Flags: `canDowngrade` true · `pendingDurationHours` 6

| Level | Steel cost | Construction points [live-only] | Bonuses |
|---|---|---|---|
| 1 | 0 | 0 | maxProduction: 200 |
| 2 | 10 | 20 | maxProduction: 400 |
| 3 | 20 | 40 | maxProduction: 600 |
| 4 | 40 | 80 | maxProduction: 800 |
| 5 | 80 | 160 | maxProduction: 1000 |
| 6 | 160 | 320 | maxProduction: 1200 |
| 7 | 320 | 680 | maxProduction: 1400 |

Level 7 needs 680 construction points, not the 640 the doubling pattern would suggest. The value is real; don't "fix" it.

### automatedEngine (company)
Flags: `canDowngrade` true · `pendingDurationHours` 6

| Level | Steel cost | Construction points [live-only] | Bonuses |
|---|---|---|---|
| 1 | 0 | 0 | dailyProd: 24 |
| 2 | 20 | 20 | dailyProd: 48 |
| 3 | 40 | 40 | dailyProd: 72 |
| 4 | 80 | 80 | dailyProd: 96 |
| 5 | 160 | 160 | dailyProd: 120 |
| 6 | 320 | 320 | dailyProd: 144 |
| 7 | 640 | 680 | dailyProd: 168 |

### breakRoom (company)
Flags: `canDowngrade` true

| Level | Steel cost | Bonuses |
|---|---|---|
| 1 | 0 | maxWorkers: 2, dailyHires: 2 |
| 2 | 10 | maxWorkers: 4, dailyHires: 4 |
| 3 | 20 | maxWorkers: 6, dailyHires: 6 |
| 4 | 40 | maxWorkers: 8, dailyHires: 8 |
| 5 | 80 | maxWorkers: 10, dailyHires: 10 |

Max 10 workers and 10 daily hires per company at level 5.

## 13. 🔧 Upgrade settings — `upgrade`

| API path | Value |
|---|---|
| `upgrade.refundPercent` | 80 |
| `upgrade.regionUpgradeCooldownHours` | 8 |
| `upgrade.regionDowngradeCooldownHours` | 8 |
| `upgrade.constructionPointsPerContribution` | 10 |
| `upgrade.constructionContributionMinLevel` | 15 |

---

## 14. 📦 Items — `items.<code>`

60 items. The wiki shows Code, Type, Rarity, Production (`productionPoints`), Tradable (`isTradable`) and Climates (`climates`). The **Needs**, **Stats** and **Slot** columns are [live-only].

### Raw resources (`type: raw`, all `isDeposit: true`)

| Code | Rarity | Production | Tradable | Climates |
|---|---|---|---|---|
| `limestone` | common | 1 | ✓ | moderate, arid |
| `grain` | common | 1 | ✓ | moderate, tropical |
| `livestock` | common | 20 | ✓ | moderate, tropical |
| `fish` | common | 40 | ✓ | polar |
| `iron` | common | 1 | ✓ | moderate, arid, tropical, polar |
| `coca` | common | 1 | ✓ | tropical |
| `lead` | common | 1 | ✓ | moderate, arid, polar |
| `petroleum` | common | 1 | ✓ | moderate, arid, tropical |
| `wood` | common | 1 | ✓ | moderate, tropical, polar |

### Products (`type: product`)

| Code | Rarity | Production | Tradable | Needs (`productionNeeds`) [live-only] | Stats (`flatStats`) [live-only] |
|---|---|---|---|---|---|
| `concrete` | uncommon | 10 | ✓ | limestone ×10 | — |
| `steel` | uncommon | 10 | ✓ | iron ×10 | — |
| `bread` | uncommon | 10 | ✓ | grain ×10 | healthRegenPercent 10 · consumable |
| `steak` | rare | 20 | ✓ | livestock ×1 | healthRegenPercent 15 · consumable |
| `cookedFish` | epic | 40 | ✓ | fish ×1 | healthRegenPercent 20 · consumable |
| `lightAmmo` | uncommon | 1 | ✓ | lead ×1 | percentAttack 10 · usage ammo |
| `ammo` | rare | 4 | ✓ | lead ×4 | percentAttack 20 · usage ammo |
| `heavyAmmo` | epic | 16 | ✓ | lead ×16 | percentAttack 40 · usage ammo |
| `cocain` | epic | 200 | ✓ | coca ×200 | percentAttack 60 · buffDurationHours 8 · debuffDurationHours 15.5 |
| `oil` | uncommon | 1 | ✓ | petroleum ×1 | — |
| `paper` | uncommon | 1 | ✓ | wood ×1 | — |
| `scraps` | rare | — | ✓ | — (not produced) | — |

(`cocain` is the game's spelling of the item code.)

### Weapons (`type: weapon`, not tradable, `usage: weapon`)

| Code | Rarity | attack [min, max] [live-only] | criticalChance [min, max] [live-only] |
|---|---|---|---|
| `knife` | common | 21–40 | 1–5 |
| `gun` | uncommon | 51–60 | 6–10 |
| `rifle` | rare | 71–90 | 11–15 |
| `sniper` | epic | 101–130 | 16–20 |
| `tank` | legendary | 141–170 | 26–35 |
| `jet` | mythic | 221–300 | 41–50 |

### Cases (`type: case`, tradable)

| Code | Rarity |
|---|---|
| `case1` | legendary |
| `case2` | mythic |
| `woodenCase` | legendary |

### Equipment (`type: equipment`, not tradable)

Tier N maps to a rarity: 1 common, 2 uncommon, 3 rare, 4 epic, 5 legendary, 6 mythic. Stat ranges (`dynamicStats`) are [live-only].

| Tier (rarity) | `helmetN` criticalDamages | `chestN` armor | `pantsN` armor | `bootsN` dodge | `glovesN` precision |
|---|---|---|---|---|---|
| 1 (common) | 1–15 | 1–5 | 1–5 | 1–5 | 1–5 |
| 2 (uncommon) | 16–30 | 6–10 | 6–10 | 6–10 | 6–10 |
| 3 (rare) | 31–50 | 11–15 | 11–15 | 11–15 | 11–15 |
| 4 (epic) | 71–90 | 21–30 | 21–30 | 21–25 | 21–25 |
| 5 (legendary) | 91–110 | 36–50 | 36–50 | 31–40 | 31–40 |
| 6 (mythic) | 121–150 | 56–70 | 56–70 | 51–60 | 51–60 |

That's 30 equipment items: `helmet1` `helmet2` `helmet3` `helmet4` `helmet5` `helmet6` · `chest1` `chest2` `chest3` `chest4` `chest5` `chest6` · `boots1` `boots2` `boots3` `boots4` `boots5` `boots6` · `gloves1` `gloves2` `gloves3` `gloves4` `gloves5` `gloves6` · `pants1` `pants2` `pants3` `pants4` `pants5` `pants6`. The slot is `usage` (`helmet`, `chest`, `boots`, `gloves`, `pants`). Gaps between tiers (e.g. helmet 51–70) are real; don't interpolate.

---

## 15. 👥 Referral — `referral`

| API path | Value |
|---|---|
| `referral.levelNeededForBadge` | 15 |
| `referral.moneyForBeingReferred` | 10 |
| `referral.lifeTimeBadgeMoneySharePercent` | 10 |
| `referral.canSetReferrerBeforeOrAtLevel` | 10 |

## 16. 🗺️ Region — `region`

| API path | Value |
|---|---|
| `region.maxResistance` | 40 |
| `region.homeMoveConcreteCost` | 100 |
| `region.freeTravelHomeCooldownHours` | 12 |
| `region.citizenIncomeTaxPercent` | 30 |
| `region.minDailyResistance` | 1 |
| `region.maxDailyResistance` | 4 |
| `region.transferDaysCooldown` | 5 |
| `region.liberationDaysCooldown` | 5 |
| `region.nonAggressionHoursAfterLiberation` | 24 |
| `region.nonAggressionHoursAfterPeace` | 72 |
| `region.regionNotLinkedToCapitalMalusDevelopmentPercent` | 50 |
| `region.resourcesBonus` | `{"1": 5, "2": 0.5, "3": 0.25}` |
| `region.depleteHourlyPercent` | 0.5 |
| `region.increaseResistanceCost` | 40 |
| `region.decreaseResistanceCost` | 30 |
| `region.increaseBy` | 5 |
| `region.decreaseBy` | 5 |
| `region.resistanceBarMultiplier` | 100 |
| `region.resistanceDecayPercent` | 0.2 |
| `region.resistanceGrowthPercentMin` | 0.1 |
| `region.resistanceGrowthPercentMax` | 0.35 |
| `region.resistancePassiveGrowthPercent` | 0.08 |
| `region.resistanceContributionCost` | 10 |
| `region.resistanceContributionValue` | 1 |
| `region.resistanceContributionMinLevel` | 15 |
| `region.resistanceCitizenBonus` | 2 |
| `region.resistanceBattleStartCostMultiplier` | 10 |
| `region.resistanceForeignGovCostMultiplier` | 2 |
| `region.battleCooldownHours` | 1 |
| `region.resistanceBattleCooldownHours` | 24 |
| `region.resistanceContributionCooldownAfterRevoltHours` | 24 |
| `region.resistanceCitizenBonusPercent` | 30 |
| `region.resistanceAllyBonusPercent` | 15 |

## 17. ⚡ Unrest — `unrest`

| API path | Value |
|---|---|
| `unrest.barMultiplier` | 50 |
| `unrest.contributionCost` | 10 |
| `unrest.contributionValue` | 1 |
| `unrest.contributionMinLevel` | 15 |
| `unrest.battleStartCost` | 100 |
| `unrest.battleCooldownHours` | 48 |
| `unrest.bordersOpenDays` | 7 |
| `unrest.nominationPeriodHours` | 24 |
| `unrest.contributionCooldownAfterRevolutionHours` | 72 |

## 18. 🎉 Party — `party`

| API path | Value |
|---|---|
| `party.createCost` | 150 |

## 19. ⚙️ Alliance — `alliance`

| API path | Value |
|---|---|
| `alliance.leaveCooldownDays` | 7 |
| `alliance.leaveCooldownDisabledUntil` | 2026-09-03T00:00:00.000Z (in the past, so the 7-day cooldown is active now [assumption]) |

## 20. 📰 Newspaper — `newspaper`

| API path | Value |
|---|---|
| `newspaper.tipValue` | 5 |
| `newspaper.gemTipValue` | 5 |
| `newspaper.publishCost` | 3 |
| `newspaper.createArticleMinLevel` | 5 |
| `newspaper.commentMinLevel` | 8 |
| `newspaper.tipMinLevel` | 5 |

## 21. 🌍 Country — `country`

| API path | Value |
|---|---|
| `country.maxTaxAmount` | 45 |

## 22. 📝 Citizenship — `citizenshipApplication`

| API path | Value |
|---|---|
| `citizenshipApplication.autoApprovalMaxPopulation` | 5 |
| `citizenshipApplication.autoApprovalEnabled` | true |

## 23. 🏛️ Government — `government`

| API path | Value |
|---|---|
| `government.resistanceIncreasedCooldownInHours` | 6 |
| `government.resistanceDecreasedCooldownInHours` | 3 |
| `government.nominationCooldownDays` | 5 |
| `government.presidentWagePercent` | 3 |
| `government.memberWagePercent` | 1 |

## 24. ⚙️ Announcement — `announcement`

| API path | Value |
|---|---|
| `announcement.maxPerHour` | 2 |
| `announcement.durationHours` | 24 |
| `announcement.maxLength` | 1000 |

---

## 25. 💼 Mercenary contract — `mercenaryContract`

| API path | Value |
|---|---|
| `mercenaryContract.enabled` | true |
| `mercenaryContract.bountyMinActiveCitizens` | 0 |
| `mercenaryContract.nationalBountyMinActiveCitizens` | 40 |
| `mercenaryContract.nationalBountyEnabled` | false |
| `mercenaryContract.bountyCooldownMinutes` | 3 |
| `mercenaryContract.maxBountyWageMultiplier` | 6 |
| `mercenaryContract.acceptanceFeePercent` | 10 |
| `mercenaryContract.cancellationPenaltyPercent` | 10 |

**Auction** — `mercenaryContract.auction`

| API path | Value |
|---|---|
| `.auction.minDuration` | 5 |
| `.auction.maxDuration` | 25 |
| `.auction.maxPerKMultiplier` | 6 |
| `.auction.minPerK` | 0.01 |
| `.auction.bidStep` | 0.01 |
| `.auction.timerExtensionThreshold` | 60 |
| `.auction.timerExtensionAmount` | 60 |
| `.auction.maxDamagePerContract` | 10000000 |

**Reputation** — `mercenaryContract.reputation`

| API path | Value |
|---|---|
| `.reputation.professionalsOnlyThreshold` | 5 |
| `.reputation.successPerDollar` | 1000 |
| `.reputation.failurePerDollar` | 1000 |
| `.reputation.failurePerDamage` | 1000000 |
| `.reputation.weeklyDecayPercent` | 20 |
| `.reputation.negativeBuyCost` | 200 |
| `.reputation.negativeBuyAmount` | 1 |
| `.reputation.negativeBuyCooldownHours` | 24 |

## 26. 🎁 Loot — `loot`

| API path | Value |
|---|---|
| `loot.weaponChancePercent` | 30 |
| `loot.damagePerLootItem` | 200000 |
| `loot.battleLootDamagePerLootItem` | 500000 |

## 27. 🎯 Missions — `mission`

**Rewards per mission type** — `mission.reward.<type>`

| Type | XP (`xp`) | XP completed (`xpWhenFinished`) | Cases (`cases`) | Money (`money`) |
|---|---|---|---|---|
| daily | 10 | 100 | 1 | 10 |
| weekly | 50 | 500 | 3 | 30 |
| monthly | 100 | 1000 | 5 | 50 |
| starting | 50 | 500 | 5 | 50 |

**Reroll cost per reroll** — `mission.rerollMissionCost["<n>"]`

The cost is `2 × n` for n = 0…20. The table stops at 20; behaviour past 20 isn't in config.

The config doesn't say how many missions each period hands out, only the rewards and reroll costs **[observed 2026-10-29]**.

| n | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 | 19 | 20 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cost | 0 | 2 | 4 | 6 | 8 | 10 | 12 | 14 | 16 | 18 | 20 | 22 | 24 | 26 | 28 | 30 | 32 | 34 | 36 | 38 | 40 |

## 28. 🎨 Sub-skin reward — `subSkinReward`

| API path | Value |
|---|---|
| `subSkinReward.skinKey` | 1kSubRifle |
| `subSkinReward.deadline` | 2026-05-01T00:00:00.000Z (already past) |

---

## 29. [live-only] Skills — `skills.<skill>.levels["0".."10"]`

The wiki's tagline mentions "skills", but the page renders no skills table, so this section comes from the live API. Every level has `value`, `unlockAtLevel`, `totalCost`, and (from level 1) `cost`.
- **Cost is the same for every skill:** level n costs **n** skill points, and `totalCost` is the triangular number n(n+1)/2: 0, 1, 3, 6, 10, 15, 21, 28, 36, 45, **55** for level 10.
- **Bar** = `isABar: true` on level 0 (a resource bar rather than a flat stat).

| Skill | Unlocks at player level | Lvl 0 | +per level | Lvl 10 | Extras |
|---|---|---|---|---|---|
| `energy` (bar) | 1 | 30 | +10 | 130 | |
| `stamina` (bar) | 1 | 100 | — | — | only level 0 exists |
| `health` (bar) | 5 | 100 | +10 | 200 | |
| `hunger` (bar) | 10 | 4 | +1 | 14 | |
| `attack` | 1 | 100 | +25 | 350 | |
| `companies` | 5 | 2 | +1 | 12 | max companies owned |
| `entrepreneurship` (bar) | 1 | 30 | +5 | 80 | |
| `production` (bar) | 1 | 10 | +3 | 40 | |
| `criticalChance` | 5 | 10 | +5 | 60 | `skillOverflow` → `criticalDamages`, `skillOverflowValue` 4 |
| `criticalDamages` | 10 | 100 | +20 | 300 | |
| `armor` | 5 | 0 | +6 | 60 | `softCap` 40 |
| `precision` | 1 | 50 | +5 | 100 | `skillOverflow` → `attack`, `skillOverflowValue` 4 |
| `dodge` | 10 | 0 | +4 | 40 | `softCap` 40 |
| `lootChance` | 1 | 5 | +2 | 25 | |
| `management` | 10 | 4 | +2 | 24 | |

Every skill grows linearly: value(n) = Lvl 0 + n × step. That holds for all 15 skills in the snapshot. Still read the table from the API.

---

## Wiki ⇄ live differences (as of 2026-10-04)

| Path | Wiki (2026-09-15 data) | Live |
|---|---|---|
| `election.voteMinLevel` | 15 | **20** |
| `election.voteMinDaysSinceCitizenshipChange` | not shown | **7** |
| `law.sendMoneyToCountry` | "—" | `allianceTaxRate` 0.5, `externalTaxRate` 1 |

Fields the wiki doesn't render at all: `user.prestige.*`, `skills.*`, `badge.*.preserveBetweenReset`, `badge.popularArticle.uniqueMetadataKey`, upgrade `constructionPointsCost` / `maintenanceCost*DevScale` / `minimumMaintenanceCost`, and item `productionNeeds` / `flatStats` / `dynamicStats` / `usage` / `skinSlot` / `isDeposit` / `isConsumable`. Every other wiki value matched live exactly.
