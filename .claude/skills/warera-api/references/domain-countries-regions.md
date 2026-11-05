# Domain: countries, government, regions, upgrades, events

**Solves:** resolving countries by name, diplomacy (allies, wars, NAPs, defensive pacts, alliance), taxes, development, population, treasury, government composition and takeovers, region ownership, deposits, resistance, region and company/MU upgrades, and the world event feed.

Labels: **[spec]** · **[observed 2026-10-03]** · **[project]** · **[assumption]**

---

## `country.getAllCountries`
Input: none. Returns an **array** of ~180 country objects **[observed]**.

List item keys **[observed]**: `_id, name, code, money, taxes{income,market,manager}, income{development,strategicResourcesBonus,employeeIncomeTax,managerIncomeTax,govType,total}, govType?, unrest{barMax,bar,lastContributionAt}, orgs[], allies[], warsWith[], enemy, defensivePacts[], nonAggressionUntil, bordersOpenUntil? (ISO, 6 of 181 countries **[observed 2026-11-02]**), allianceId, rulingParty, coreDevelopment, averageDevelopment, currentDevelopment, currentPopulation, scheme, mapAccent, rankings, updatedAt`.

## `country.getCountryById`
Input: `countryId*` (string, minLength 1) **[spec]**. Returns 404 `"Countries not found."` for an unknown ID **[observed]**.

```jsonc
// observed (Romania, trimmed)
{
  "_id": "6813b6d446e731854c7ac7b6", "name": "Romania", "code": "ro",
  "money": 979.09,
  "taxes": {"income": 9, "market": 0, "manager": 9},   // v0.27: selfWork tax gone, manager tax new
  "income": {"development": 6.26, "strategicResourcesBonus": 10.35, "employeeIncomeTax": 0.76, "managerIncomeTax": 0.69, "govType": 0, "total": 18.06},
  // "govType": "federation" | "plutocracy" | "mercenaryState" | …  (absent = Provisional) [observed 2026-10-26]
  "unrest": {"barMax": 11324, "bar": 55, "lastContributionAt": "…"},
  "allies": ["<countryId>"], "warsWith": ["<countryId>"], "enemy": "<countryId>",
  "defensivePacts": ["<countryId>"],
  "nonAggressionUntil": {"<countryId>": "2026-10-04T10:22:34.661Z"},   // NAP expiry per country
  "allianceId": "<allianceId>", "rulingParty": "<partyId>", "orgs": ["<orgId>"],
  "coreDevelopment": 226.49, "averageDevelopment": 226.51, "currentDevelopment": 226.52,
  "currentPopulation": 166,   // specializedItem removed in v0.27
  "strategicResources": {"resources": {"uranium": …}, "bonuses": {"developmentPercent": 5}}   // v0.27: no productionPercent,
  "rankings": {"countryDamages": {"value": …, "rank": …, "tier": "…"}, "weeklyCountryDamages": {…}, …},
  "currentBattleOrder": "<battleOrderId>", "discordUrl": "https://discord.gg/…", "pinnedArticle": "<articleId>",
  "dates": {"govTypeChangedAt": "2026-10-27T10:38:10.445Z"}   // [observed 2026-11-02]
}
```

Notes:
- `nonAggressionUntil` holds the **game's own NAP timers**. The project keeps its own NAP database (`cogs/commands/naps.py`, `cogs/tasks/monitor_nap.py`), and this field could cross-check it **[assumption: semantics inferred from the name and ISO values]**.
- `averageDevelopment` is used for region upkeep math in `get_region_upgrade_cost.py` **[project]**.

## `government.getByCountryId`
Input: `countryId*` **[spec]**.

```jsonc
{"_id": "…", "country": "<countryId>",
 "president": "<userId>", "vicePresident": "<userId>",
 "minOfForeignAffairs": "<userId>", "minOfEconomy": "<userId>", "minOfDefense": "<userId>",
 "congressMembers": ["<userId>", …],
 "dates": {"announcementCreatedAts": ["iso"], "lastAnnouncementAt": "iso"}}
```
Offices may be absent when vacant **[assumption]**. `takeover_countries.py` checks this.

## `region.getRegionsObject`
Input: none. Returns an **object map** `{regionId: region}` with ~742 entries on 2026-11-02 (~726 before), about 0.9 MB **[observed]**. Filter by `region.country == countryId` for a country's regions (`_iter_country_regions` in `get_region_upgrade_cost.py`).

## `region.getById`
Input: `regionId*` **[spec]**.

```jsonc
{"_id": "…", "name": "Banat & Crișana", "code": "ro-banat-crisana", "mainCity": "Timișoara",
 "country": "<owner countryId>", "initialCountry": "<countryId>", "countryCode": "ro",
 "isCapital": false, "isLinkedToCapital": true, "neighbors": ["<regionId>", …],
 "development": 32.36, "baseDevelopment": 32.36,
 "activeUpgradeLevels": {"bunker": 2, "base": 1},            // pacificationCenter also possible
 "upgradesV2": {"upgrades": {…}, "activeConstructionCount": 0},
 "resistance": 0, "resistanceMax": 3236,
 // "deposit" is gone: 0 of 742 regions had it; gameConfig.region.depositsEnabled = false [observed 2026-11-02]
 "population": 17, "currentPopulation": 24, "residents": 25,
 "biome": "plains", "climate": "moderate", "position": [lon, lat],
 "dates": {"lastOwnershipChangeAt": "iso"}, "lastBattleEndedAt": "iso", "lastRevoltEndedAt": "iso",
 "lastResistanceContributionAt": "iso", "companyCount": 65, "employeeCount": 113, "stats": {"investedMoney": 0}}   // [observed 2026-11-02]
```

- Since v0.27 a region also has `strategicResource` (item code, e.g. `"uranium"`, when it holds one) and the same
  `income{development, strategicResourcesBonus, employeeIncomeTax, managerIncomeTax, govType, total}` block as a country
  **[observed 2026-10-29]**.
- **All `income` fields (region and country) are money per hour.** The client multiplies them by 24 for "Estimated daily
  income" **[client 2026-10-29]**. Since v0.27.2 (2026-10-28): `development` = region development × 2 / 24;
  `strategicResourcesBonus` = the region's initial country's `coreDevelopment` × 2 / 24; `govType` = the government-type
  adjustment on top (e.g. −30% of `development` for a Nationalist State, +100% for a Republic core region) **[observed
  2026-10-29, 40 regions]**. Don't add a day's worth without multiplying by 24.

## `upgrade.getUpgradeByTypeAndEntity`
Inputs **[spec]**: `upgradeType*` ∈ `bunker | base | pacificationCenter` (region), `storage | automatedEngine | breakRoom` (company), `headquarters | dormitories` (MU), plus exactly one of `regionId`, `companyId`, `muId` (the type→entity mapping is **[observed]** from `activeUpgradeLevels` keys).

```jsonc
// region bunker (observed)
{"_id": "…", "region": "<regionId>", "upgradeType": "bunker", "level": 2,
 "status": "active",            // observed: active, disabled
 "investedMoney": 0, "investedConcrete": 0, "investedSteel": 200,
 "dependantUsersCount": 0,
 "lastUpgradeAt": "iso", "lastDowngradeAt": "iso", "statusChangedAt": "iso", "willBeActiveAt": "iso"}
```
For upgrade **costs and per-level effects**, read `gameConfig.getGameConfig().upgradesConfig[type].levels` (see game-config.md).

**No upgrade history** **[observed 2026-10-22]**. The record keeps only the *latest* `lastUpgradeAt` and `lastDowngradeAt`, with no actor and no previous level. No event type covers upgrades: the `eventTypes` enum has none, and guesses such as `upgradeCreated` get a 400. The `upgradeConstruction.*` procedures return empty lists, `actionLog.getPaginated` is session-only, and `upgradesV2.lastConstructions` is stale (July 2025). What you can derive:
- The newer of the two timestamps is an exact one-level change. An upgrade went `level-1 → level` (creation sets `lastUpgradeAt` ≈ `createdAt`, i.e. `0 → 1`); a downgrade went `level+1 → level`.
- The older one only has a bound. An earlier upgrade reached ≥ `level+1`, and an earlier downgrade fell to ≤ `level-1`. Region upgrade and downgrade cooldowns are 8 h each, and gaps under 8 h between the two timestamps occur, so the cooldowns limit each direction separately.
- `status`: `disabled` (1190 of 1376 region records), `active` (138) and `pending` (48). `activeUpgradeLevels` lists **active ones only**, so a region with no `activeUpgradeLevels` can still have records.
- No record has `level` 0, so a building destroyed below level 1 probably leaves no record **[assumption]**.
- Volume: about 195 upgrades and 200 downgrades per week world-wide. All ~2,180 region/type pairs fit in 22 batches of 100.
- `/region_upgrades` (`cogs/commands/region_upgrades.py`) builds its list this way.

## `event.getEventsPaginated`
Inputs **[spec]**: `limit` (1–100, default 10), `cursor`, `countryId`, `eventTypes[]`.

`eventTypes` enum **[spec]**: `warDeclared, peace_agreement, battleOpened, battleEnded, newPresident, regionTransfer, peaceMade, countryMoneyTransfer, depositDiscovered, depositDepleted, systemRevolt, bankruptcy, allianceFormed, allianceBroken, allianceMemberJoined, allianceMemberLeft, allianceMemberExcluded, defensivePactFormed, defensivePactBroken, regionLiberated, strategicResourcesReshuffled, resistanceIncreased, resistanceDecreased, revolutionStarted, revolutionEnded, financedRevolt`.

Item: `{_id, countries:[countryId…], priority: "2", data: {type, …}, createdAt}`. Note that `priority` is a string **[observed]**.

`data` variants **[observed]**:
| type | fields |
|---|---|
| `warDeclared` | `war, attackerCountry, defenderCountry` |
| `battleOpened` / `battleEnded` | `battle, attackerCountry, defenderCountry, attackerRegion, defenderRegion`; `battleEnded` adds `wonBy` (`attacker`/`defender`) |
| `regionTransfer` | `regions[], countries[2], amount`; `countries[0]` gives, `countries[1]` receives **[observed 2026-10-22: matched the current owner]** |
| `systemRevolt` | `attackerCountryId, defenderCountryId, regionId` |
| `financedRevolt` | `battleId, financingPartyId, revoltingCountryId, occupyingCountryId, regionId` |
| `revolutionEnded` | `battleId, countryId, partyId, wonBy` |
| `peaceMade` | `wars[], countries[]` |
| `countryMoneyTransfer` | `money, countries[]` |
| `regionLiberated` | `region, fromCountry, toCountry` |
| `depositDiscovered` | `region, itemCode, bonusPercent, durationDays` |
| `defensivePactFormed` / `defensivePactBroken` | `countries[]` |
| others | not observed; inspect live |

**Rebuilding a region's owner history** **[observed 2026-10-22, last 30 days]**:
- Ownership moves with `battleEnded` won by the attacker (`defenderRegion` goes from `defenderCountry` to `attackerCountry`), with `regionLiberated`, and with `regionTransfer`.
- About a third of ownership changes (165 of 477) have **no event**. In every case the region returned to its `initialCountry`. Only the latest such return is visible, as `region.dates.lastOwnershipChangeAt`.
- A month of these three event types takes about 13 pages of 100.
- `cogs/commands/region_upgrades.py` `ownership_changes` / `owner_candidates` implement it. For a month of upgrade changes they find a single owner for 87%, two candidates for 11% and none for 2%.

**Typical uses:** notify about new wars, peace or presidents involving a country; feed a "world news" channel; detect region loss without polling regions.

---

# Procedures not in the official spec (from the community explorer, verified live 2026-10-03)

Source: `https://warera.realmarijn.nl/api-explorer` **[explorer]**. All work anonymously. Diplomacy, wars, alliances, unrest and contributions are in **domain-politics-diplomacy.md**.

### `region.getAll`
Input: none. Returns an **array** of all ~742 region objects, the same objects as the values of `region.getRegionsObject` **[observed]**. Pick whichever container shape suits you (map by ID or list); the payload is about the same (~0.9 MB).
`upgradesV2.upgrades.<type>` carries construction detail **[observed]**: `{level, status, constructionPoints, investedMoney, isUnderConstruction, constructionStartedAt, constructionEndedAt, statusChangedAt, lastConstructions[]}`.

### `upgradeConstruction.getMapConstructions` / `getRegionConstructions` / `listConstructions`
- `getMapConstructions`: no input. Every in-progress region-upgrade construction on the map.
- `getRegionConstructions`: `regionId*`.
- `listConstructions`: `regionId` **or** `countryId` (without either → **400 `"regionId or countryId is required."`** **[observed]**), `limit`, `cursor`. The explorer says the cursor is the last item's `_id`, and that a non-ObjectId cursor causes a 500 **[explorer]**. Returns `{items: []}`.
- All three returned **empty** arrays live and in the explorer's saved examples, so the **item shape is unknown**. If you need it, call when a construction is running and document it here.

### `gameStat.getWorldDevelopment`
Input: none. Returns a **bare number**, the summed world development (`18238.02`) **[observed]**. Same router as the undocumented `gameStat.getEquipmentAvgByCode`.
