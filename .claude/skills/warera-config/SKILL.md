---
name: warera-config
description: Complete reference of every WarEra game limit and constant from gameConfig (mirrors https://warera.realmarijn.nl/game-config, cross-checked against the live API). Use whenever you need or are about to hardcode a WarEra game number or rule — min levels (market, donation, chat, voting, candidacy, articles, contributions, takeover), cooldowns (citizenship, skill reset, MU help, alliance leave, battles, resistance, unrest, government nominations), caps (max energy/hunger, max MUs, MU members, workers, companies, tax, resistance, kits, equipment sets), costs (construction, move, laws, party, orders, merging, rerolls, upgrades, resistance changes), battle rules and bonuses/maluses, upgrade level tables (headquarters, dormitories, bunker, base, pacificationCenter, storage, automatedEngine, breakRoom), item stats and recipes, skill tables, badges, missions, mercenary contracts/auctions/reputation, loot, referral, newspaper, announcements, or the game clock (day rollover, regen, elections, mission resets). Also use when explaining game mechanics or limits to users of the bot.
---

# WarEra game configuration skill

This skill holds **every value on https://warera.realmarijn.nl/game-config**: 28 sections plus the game clock. Each value is mapped to its exact `gameConfig.getGameConfig` path and cross-checked against the live API on 2026-10-04. It also adds the fields the wiki doesn't render, including skills, prestige, item stats and recipes, and upgrade construction and maintenance.

- **Full reference (all values):** [references/config.md](references/config.md)
- **Raw live config:** [references/game-config.snapshot.json](references/game-config.snapshot.json)
- **Drift check:** `python .claude/skills/warera-config/scripts/check_config.py` (`--update` rewrites the snapshot)
- **How to call the API** (session, retries, helpers): the `warera-api` skill. This skill covers *values*; `warera-api` covers *calls*.

## Rules

1. **Don't hardcode when code can read it.** In bot code, fetch `gameConfig.getGameConfig` (no input, no key, ~33 KB, changes rarely) with `warera.game.get_config()` (the client caches it for 1 h and keeps the last good copy), and read the path listed here. If you must hardcode a value, add a comment with its config path, e.g. `# gameConfig: mu.maxOwnedMus`.
2. **Never hardcode dates.** Day rollover, regen, elections and mission resets come from `gameConfig.getDates` (all UTC).
3. **Live beats wiki beats this file.** The wiki's data was stale (from 2026-09-15) when fetched and already differed from live in three places (table below). Before relying on a value for user-facing output, run the drift check or read the live config. If the script reports changes, update `references/config.md`, this file's quick table and the snapshot.
4. **Don't invent units or semantics.** Many keys (`constructionCost`, `createCost`, law `cost`) don't state whether they're money, steel or something else. Say "unit not stated" instead of guessing. Interpretations in the reference are labelled **[assumption]**.
5. **Don't extrapolate tables.** Upgrade levels, skill levels 0–10 and the reroll costs 0–20 are the full lists. Item stat tiers have gaps (e.g. helmet 51–70 doesn't exist). Storage and automatedEngine level 7 cost 680 construction points, which breaks the doubling pattern.

## Wiki vs live differences (2026-10-04)

| Path | Wiki | Live (use this) |
|---|---|---|
| `election.voteMinLevel` | 15 | **20** |
| `election.voteMinDaysSinceCitizenshipChange` | not shown | **7** |
| `law.sendMoneyToCountry` | "—" | `allianceTaxRate` 0.5, `externalTaxRate` 1 |

All other wiki values match live.

## ⚠️ v0.27 drift (live config checked 2026-10-26)

WarEra v0.27 (2026-10-25/26) changed the config, but `references/config.md` and the snapshot still show **pre-v0.27** values. `check_config.py` reports 248 added, 65 removed and 63 changed keys. The snapshot was deliberately not `--update`d, so the drift stays visible until config.md is rewritten. Until then, **live values win** over config.md for these:

- **Skills:** `entrepreneurship` removed and `leadership` added (value = level, 0→10). Energy 30 + 10/level → **100 + 10/level**. Production 10 + 3/level → **30 + 3/level**. Management 4 + 2/level (unlocking at level 10) → **1 + 1/level** (from level 1). The Companies skill now unlocks at level 1 (was 5).
- **breakRoom:** levels 1–3 only, with **1/2/3 employees** for 0/20/80 steel. `dailyHires` is gone. The whole `worker` section (fidelity) is removed.
- **Levels:** `user.marketMinLevel` 7 → **5**. `user.chatMinLevel` and `newspaper.commentMinLevel` were removed: chat is open from level 1 with `user.chatSlowmode`, lifted at 15. `election.candidateMinLevel` 15 → **20**. New `user.featureUnlockLevels` (market 5, mu 5, produceAll / openAllCases / bulkDismantle 7, craft / managerJob / fightSkills 10, party / workforceChart 15) and `user.skillPresets` (3, or 10 with premium).
- **Economy:** `region.depositsEnabled = false`. `region.resourcesBonus`, `region.citizenIncomeTaxPercent` and `regionNotLinkedToCapitalMalusDevelopmentPercent` were removed. New `country.conqueredRegionCoreTaxPercent` 10.
- **Other:** `mercenaryContract.maxBountyWageMultiplier` 6 → `maxBountyPpMultiplier` 9. `mu.helperHealthPerHelp` 1. `citizenshipApplication.newCountryBordersOpenDays` 7. `alliance.leaveCooldownDisabledUntil` 2026-10-30. Items and missions have many added and removed keys (tools, new missions): run the drift check for the full list.

What these values mean for gameplay (employees, managers, government types) is in the `warera-game-expert` skill, which already covers v0.27.

## Quick reference — most-asked limits

| Question | Answer | Path |
|---|---|---|
| Game day / regen | Day rolls at 00:00 UTC; regen every hour on the hour | `getDates.nextDayAt`, `nextRegenAt` |
| Mission resets | daily 00:00 UTC · weekly Mon 00:00 UTC · monthly 1st 00:00 UTC | `getDates.*MissionRegenAt` |
| Elections | Presidential on the 1st of the month; congress: read the date | `getDates.nextPresidentialElectionsAt`, `nextCongressElectionsAt` |
| Max energy / hunger | 100 / 10 (base caps; the energy/hunger skills set the bars) | `user.maxEnergy`, `user.maxHunger` |
| Max construction points | 30 | `user.maxConstructionPoints` |
| Inactive player after | 3 days | `user.isInactiveAfterDays` |
| Min level: donate / market / chat / active citizen / takeover | 5 / **5** (v0.27) / 1 with slow mode until 15 (v0.27) / 10 / 25 | `user.donationMinLevel`, `marketMinLevel`, `chatSlowmode`, `activeCitizenMinLevel`, `canTakeControlAtLevel` |
| Min level: vote / be candidate | **20** / **20** (v0.27; vote also needs ≥7 days since citizenship change) | `election.voteMinLevel`, `candidateMinLevel`, `voteMinDaysSinceCitizenshipChange` |
| Min level: write article / tip / comment | 5 / 5 / none since v0.27 (chat slow mode) | `newspaper.createArticleMinLevel`, `tipMinLevel`, `commentMinLevel` |
| Min level: resistance / unrest / construction contribution | 15 / 15 / 15 | `region.resistanceContributionMinLevel`, `unrest.contributionMinLevel`, `upgrade.constructionContributionMinLevel` |
| Citizenship change cooldown | 30 days | `user.citizenshipDaysCooldown` |
| Skill reset | cooldown 7 days, 0.5 per point | `user.resetSkillDaysCooldown`, `resetSkillsCostPerPoint` |
| Equipment sets / kits | free 1 / 6 · premium 5 / 30 | `user.equipmentSets.*`, `user.kits.*` |
| Prestige | from level 50 | `user.prestige.enabledLevel` |
| Battle format | first to 2 rounds, max 15 rounds, 300 points per round | `battle.roundsToWin`, `maxRounds`, `pointsToWinRound` |
| Damage bonuses | country order +10%, MU order +10%, alliance +10%, enemy +10%, patriotic +20% | `battle.*BonusPercent` |
| Damage maluses | not linked to capital −25%, lost attacking region −25%, occupying your regions −50% | `battle.*MalusPercent` |
| Order costs | country 30, MU 10, generic 40 | `battle.set*OrderMoneyCost` |
| MUs | max 3 owned; members 5→25 (dormitories L1–L5); help every 12h; nationality change every 7 days | `mu.maxOwnedMus`, `upgradesConfig.dormitories`, `mu.helpCooldownHours`, `mu.nationalityChangeCooldownDays` |
| MU HQ attack bonus | +5/10/15/20% at L1–L4 | `upgradesConfig.headquarters` |
| Region bunker / base | +5…25% defense / attack at L1–L5 | `upgradesConfig.bunker`, `upgradesConfig.base` |
| Companies owned | 2 base → 12 at `companies` skill L10 | `skills.companies` |
| Employees per company | **1 → 3** (breakRoom L1–L3, v0.27; was 2 → 10 workers) | `upgradesConfig.breakRoom` |
| Max country tax | 45 | `country.maxTaxAmount` |
| Max region resistance | 40 | `region.maxResistance` |
| Non-aggression | 24h after liberation, 72h after peace | `region.nonAggressionHoursAfter*` |
| Alliance leave cooldown | 7 days | `alliance.leaveCooldownDays` |
| Law vote | 24h, 50% voter ratio | `law.lawVotesDurationHours`, `votersRatioNeeded` |
| Party creation | 150 | `party.createCost` |
| Merging | common 2 → mythic 64 (×2 per rarity) | `mergingCost` |
| Mission reroll | 2 × reroll number (0…40) | `mission.rerollMissionCost` |
| Skill costs | level n costs n points; level 10 total 55 | `skills.*.levels` |

## Section map (`references/config.md`)

| # | Wiki section | Config path |
|---|---|---|
| 1 | 📅 Times & dates | `gameConfig.getDates` |
| 2 | 👤 Player limits (+ prestige) | `user` |
| 3 | ⚔️ Battle | `battle` |
| 4 | 🏢 Organization | `org` |
| 5 | 🏭 Company | `company` |
| 6 | 👷 Worker | `worker` |
| 7 | 🎖️ Military unit | `mu` |
| 8 | 📜 Legislation + cost per law | `law` |
| 9 | 🗳️ Elections | `election` |
| 10 | 🏅 Badges (28) | `badge` |
| 11 | 🔀 Merging costs | `mergingCost` |
| 12 | ⬆️ Upgrades (8 types) | `upgradesConfig` |
| 13 | 🔧 Upgrade settings | `upgrade` |
| 14 | 📦 Items (60) | `items` |
| 15 | 👥 Referral | `referral` |
| 16 | 🗺️ Region (resistance, travel, resources) | `region` |
| 17 | ⚡ Unrest | `unrest` |
| 18 | 🎉 Party | `party` |
| 19 | ⚙️ Alliance | `alliance` |
| 20 | 📰 Newspaper | `newspaper` |
| 21 | 🌍 Country | `country` |
| 22 | 📝 Citizenship | `citizenshipApplication` |
| 23 | 🏛️ Government | `government` |
| 24 | ⚙️ Announcement | `announcement` |
| 25 | 💼 Mercenary contract (+ auction, reputation) | `mercenaryContract` |
| 26 | 🎁 Loot | `loot` |
| 27 | 🎯 Missions (rewards, rerolls) | `mission` |
| 28 | 🎨 Sub-skin reward | `subSkinReward` |
| 29 | Skills (live-only) | `skills` |
