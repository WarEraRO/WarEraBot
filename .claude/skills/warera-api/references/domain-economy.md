# Domain: economy (market prices, order book, companies, managers, transactions)

**Solves:** item prices, market depth, cost estimates (upkeep in oil, food or ammo cost of fighting), company lookup and ownership, the job market and wages, and transaction history (donations, wages, trades, tips, loot).

Labels: **[spec]** · **[observed 2026-10-03]** · **[project]** · **[assumption]**

---

## `itemTrading.getPrices`
Input: **none** **[spec]**. Unknown input keys are ignored **[observed]**.
Returns a flat map `{itemCode: price}` covering every tradable item (24 on 2026-10-03) **[observed]**:
```json
{"cookedFish": 8.88, "heavyAmmo": 3.39, "steel": 1.79, "bread": 1.92, "grain": 0.078, "limestone": 0.088,
 "coca": 0.082, "concrete": 1.75, "oil": 0.195, "case1": 3.73, "lightAmmo": 0.23, "steak": 3.98,
 "livestock": 1.55, "cocain": 39.02, "lead": 0.10, "fish": 3.85, "petroleum": 0.092, "ammo": 0.82,
 "iron": 0.094, "scraps": 0.24, "case2": 24.4, "wood": 0.099, "paper": 0.21, "woodenCase": 6.6}
```
- Equipment and weapons are **not** in this map. The project gets equipment averages from the undocumented `gameStat.getEquipmentAvgByCode` **[project]**.
- What the price represents (last trade, average, or best ask) is **not documented**.
- `warera.market.get_prices()` returns the **raw envelope** `{"result":{"data":{…}}}` rather than `result.data`, unlike the other helpers. `get_region_upgrade_cost._extract_oil_price` copes with that by walking nested dicts **[project]**.

## `tradingOrder.getTopOrders`
Inputs: `itemCode*`, `limit` (int, 1–100, default 10) **[spec]**.
```json
{"buyOrders":  [{"_id": "…", "user": "<userId>", "itemCode": "bread", "quantity": 3, "price": 1.909, "offerAt": "iso", "type": "buy"}],
 "sellOrders": [{"_id": "…", "user": "<userId>", "country": "<countryId>", "itemCode": "bread", "quantity": 180, "price": 1.921, "offerAt": "iso", "type": "sell"}]}
```
Use it for the best bid/ask and depth. Item codes are the same as `gameConfig.items` keys.

## `itemOffer.getById`
Input: `itemOfferId*` **[spec]**. Response shape and auth requirement are **unknown**: no ID source was found without a key. Probably item-market (equipment) offers **[assumption]**.

## Companies

### `company.getCompanies`
Inputs: `userId` (owner filter), `perPage` (1–100, default 10; note it's `perPage`, **not `limit`**), `cursor` **[spec]**.
Returns `{items: ["<companyId>", …], nextCursor}`, **bare ID strings** **[observed]**.

### `company.getById`
Input: `companyId*`.
```json
{"_id": "…", "user": "<ownerId>", "region": "<regionId>", "itemCode": "cookedFish", "name": "…",
 "production": 6.255, "isFull": false, "concreteInvested": 400, "freeMoves": 0,
 "activeUpgradeLevels": {"storage": 3, "automatedEngine": 6, "breakRoom": 1},
 "estimatedValue": 1859.08, "createdAt": "iso", "updatedAt": "iso", "movedUpAt": "iso"}
```
Company rules (construction cost growth, move/change costs, deposit bonus) are in `gameConfig.company`. Since v0.27 `getById` has no `workerCount` and `gameConfig.worker` is gone (confirmed on 13 companies **[observed 2026-11-02]**; companies created before v0.27 may still carry a stale `workers[{user, wage, joinedAt}]` from the old job market and an `upgradesV2`: ignore both). `freeMoves` is new; employee capacity is the `breakRoom` upgrade level (`gameConfig.upgradesConfig.breakRoom.levels[n].stats.maxWorkers`: 1/2/3) **[observed 2026-10-26]**.
- **No active/disabled flag** on `getById` **[observed 2026-11-01]**. Companies above the owner's Companies limit (`user.skills.companies.value`, e.g. 13 at level 10 with 1 Prestige) are deactivated at random (warera-game-expert companies.md), so active = `min(owned, limit)` and disabled = `owned − limit` **[derived]**. Which ones are disabled can't be read.
- `activeUpgradeLevels.automatedEngine` counts active levels only; the config's AE levels start at 1.

## Workers, work offers (job market) ❌ removed in v0.27

WarEra v0.27 (2026-10-25) removed the player job market. `worker.getWorkers`, `worker.getTotalWorkersCount`, `workOffer.getWorkOffersPaginated`, `workOffer.getById` and `workOffer.getWorkOfferByCompanyId` now return **404 `No procedure found`** **[observed 2026-10-26]**. Companies run on NPC **employees** (see Employees below; the `employee.*` queries answered 403 for API keys on 2026-10-26 and work since 2026-10-28), and the only way to work for another player is as a **manager**.

Old shapes, for reading historical data only: a work offer was `{_id, company, user, region, quantity, initialQuantity, wage, wageAfterTax, minEnergy, minProduction, createdAt, updatedAt}`; a worker was `{user, company, employer, wage, previousWage, fidelity, joinedAt, …}`.

## Managers (v0.27) 🕵️

From the game client, verified live with the bot key **[observed 2026-10-26]**. Not in the official spec; `getManyPaginated` and `getWageStats` were added to the explorer by 2026-10-28. Treat them as unstable. **v0.27.1 (2026-10-27) divided manager wages by 10**, so the examples dated 2026-10-26 below are 10× today's scale.

### `managerOffer.getManyPaginated`
Inputs **[client]**: `limit`, `cursor`, `regionId`, `countryId`, `profile`. `{"countryId": <Romania>}` returned no items while the unfiltered list had offers, so check what a filter matches before relying on it.
```json
{"items": [{"_id": "…", "company": "<companyId>", "user": "<ownerId>", "region": "<regionId>",
  "rateManagement": 0.2779, "maxHourlyWage": 3.0569, "minManagement": 3,
  "citizenship": "<countryId>", "text": "<owner's ad text>", "createdAt": "iso", "updatedAt": "iso"}],
 "nextCursor": "…"}
```
`minManagement`, `citizenship` and `text` are absent when the offer has none **[observed 2026-10-28]**. Patch notes: one manager job per company; the owner sets the pay per Management point; applying hires at once; pay stays within 80–120% of the average manager pay; the country takes a manager tax (`country.taxes.manager`).

### `managerOffer.getWageStats`
Input `{}` or none; no key needed. Returned `{"allowedRange": {"min": 1.019, "max": 3.057, "average": 2.038, "source": "bootstrap"}, "topOffer": 3.0569, "topEligibleOffer": null}` on 2026-10-26 and, after v0.27.1, `{"allowedRange": {"min": 0.086409, "max": 0.129613, "average": 0.108011, "source": "market"}, "topOffer": 0.1287, "topEligibleOffer": null}` **[observed 2026-10-28]**. `source` went from `bootstrap` to `market` once real offers existed. `topEligibleOffer` needs a logged-in player.

### `managerOffer.getByCompanyId` / `manager.getByCompanyId`
Input `companyId*`. A company's open manager offer / current manager contract, or `null`. A contract **[observed 2026-10-28]**:
```json
{"_id": "…", "user": "<managerId>", "company": "<companyId>", "employer": "<ownerId>",
 "rateManagement": 0.009688, "maxHourlyWage": 0.106568, "accrued": 0.116256, "unpaidHours": 0,
 "totalEarned": 5.164, "hiredAt": "iso", "lockedUntil": "iso", "lastAccruedAt": "iso", "createdAt": "iso", "updatedAt": "iso",
 "managementLevel": 6, "hourlyWage": 0.080255, "productionBonusPercent": 14, "isInactive": false,
 "canEndAt": "iso", "hasPendingRateReduction": false}   // computed fields [observed 2026-11-02]
```

### `gameStat.getPpMoneyValue`
**No input** (`{}` fails with `Expected void`). Returns the money value of 1 production point as a bare number (`0.1019`). The game computes it from raw-material trades over the last 7 days, and employee wages are Production ÷ 4 × this value × the employee's expectation (70–130%) **[admin patch notes v0.27]**.

### `gameStat.getPpMoneyValueByItem` 🕵️
**No input**, no key needed. Returns `{<itemCode>: money per production point}` for the 20 tradable goods (raw and products), e.g. `{"iron": 0.1135, "grain": 0.0754, "bread": 0.09, "steel": 0.1037}`; their plain mean equalled `getPpMoneyValue` (0.0991 vs 0.099) **[observed 2026-11-02]**. It is new in the client by 2026-11-02 and not in the spec or the explorer (client-discovered.md G).
- Raw goods were within ~3% of market price ÷ `productionPoints` (iron 0.1135 vs 0.1116); products were about half of it (bread 0.09 vs 0.174), so the basis isn't the plain market price **[observed 2026-11-02; basis unknown]**.
- The client's `priceOf(item)` **[client 2026-11-02]**: for a raw good it is this value. For a product with `productionNeeds` it is `(v[item] × f(item) − Σ qty × v[input] × f(input)) / productionPoints(item)`, where `f` is a client helper that wasn't traced. A missing item falls back to `getPpMoneyValue`. The workforce screen's daily profit is `(Σ productionByItem[item] × priceOf(item) − wageCost − managerCost) × 24`.

## Employees (v0.27 NPC workforce) 🧭🔑

Ten queries, announced as **API-token endpoints** in a post shared on 2026-10-28, and officially in the v0.27.2 patch notes
(admin article `6ae2608f707baf45eebf26c5`, 2026-10-28: "API tokens can now read your employees and their events"). All of them answered the bot key that day; without a key they give **401 `API token required`** **[observed 2026-10-28]**. They are not in the official spec; the explorer added all ten by 2026-11-02; the game client calls all of them except `getCompanyEmployees` and `getCompanyEstimate` **[client 2026-10-28]**. Mutations on these routers (`employee.hire`, `fire`, `pickTraining`, `employeeEvent.resolve`, …) are listed in client-discovered.md: never call them.

| Procedure | Input | Returns **[observed 2026-10-28]** |
|---|---|---|
| `employee.getCompanyRoster` | `companyId*` | `{employees:[employee], hourly}`; unknown id → 404 `Companies not found.` `hourly` = `{itemCode, production, toolboxes, wageCost, managerCost, cap, engineMultiplier}` **[observed 2026-11-02]** |
| `employee.getCompanyEmployees` | `companyId*` | `[employee]` (the roster without `hourly`) |
| `employee.getCompanyEstimate` | `companyId*` | `hourly` only: `{itemCode, production, toolboxes, wageCost, managerCost, cap, engineMultiplier}` |
| `employee.getManagerPointValue` | `companyId*` | `{productionPerPoint}`: hourly production per Management point (0.06 staffed, 0 empty) |
| `employee.getById` | `employeeId*` | `employee`, or `null` for an unknown id |
| `employee.getMyEmployees` | none | `[employee]` of the **key owner**, all companies |
| `employee.getMyWorkforceSummary` | none | `{employeeCount, trainableCount, managerCount, foundToolboxes, production, productionByItem{<itemCode>: perHour}, toolboxesPerHour, wageCost, managerCost}` of the **key owner** (`productionByItem` **[observed 2026-11-02]**) |
| `employeeEvent.getMine` | none | `[event]` of the **key owner**: pending events and unseen auto-picked outcomes. Only `[]` seen (2026-10-28, 2026-11-02); presumably the event object below |
| `employeeEvent.getPendingCount` | none | bare number (`0`) |
| `employeeEvent.getHistory` | `employeeId*` | `[event]`, newest first, for the **key owner's** employees only: a foreign employee and a nonexistent id gave `[]` **[observed 2026-11-02]**. Event object below |

- **Any company or employee is readable**, not only the key owner's: a foreign company's roster, `getById` and `work.getLastByEmployee` returned full data, and no foreign employee sampled had hidden stats or traits **[observed 2026-10-28]**.
- **"My" means the WarEra account that owns `WARERA_API_KEY`**, not the Discord user running a command.
- `hourly` values are per hour; `cap` is the company's employee capacity (breakRoom level, max 3). `wageCost` is the employees' wages and `managerCost` the manager's pay.
- Related: `work.getLastByEmployee {employeeId*, limit}` (hourly entries `[{_id, wage, production, createdAt}]`, default 20) and `work.getStatsByEmployee` (daily totals) below; `gameStat.getPpMoneyValue` to turn production into money.

Employee object (roster item, `getById`, `getMyEmployees`; all three have the same keys) **[observed 2026-10-28, re-checked 2026-11-02 on 40 employees]**:
```json
{"_id": "…", "owner": "<userId>", "company": "<companyId>",   // "region" gone [observed 2026-11-02]
 "name": "…", "gender": "female", "age": 37, "nationality": "<countryId>",
 "base":     {"production": 1, "luck": 5, "responsibility": 4},
 "trained":  {"production": 0, "luck": 3, "responsibility": 0},
 // "revealed" (top level and on traits/contributions) gone [observed 2026-11-02]
 "traits": [{"code": "laborer"}, {"code": "…", "arg": …}, …],
 "potential": 3, "potentialMax": 7,
 "wage": 0.02027, "wageExpectation": 0.835,
 "estimate": {"production": 1.33, "wage": 0.02027},
 "breakdown": {"production": {"base": 1, "trained": 0,
                 "contributions": [{"code": "laborer", "delta": 3},
                                   {"code": "specialization", "delta": 3, "percent": true}],
                 "total": 4},
               "luck": {…}, "responsibility": {…}},
 "productionBonus": {"total": 33, "contributions": [{"source": "management", "percent": 8},
                     {"source": "manager", "percent": 12}, {"source": "happiness", "percent": 10},
                     {"source": "specialization", "percent": 3}]},
 "happinessBreakdown": {"base": 50, "contributions": [{"reason": "managerCare", "delta": 5, "until": "iso"}],
                        "mitigated": 0, "value": 60, "quitChance": 0},   // "shield" gone [observed 2026-11-02]
 "specializations": {"iron": 3}, "lastSpecializedDay": "2026-10-28",
 "careBoosts": ["iso", …],
 "trainingsPerDay": 1, "trainingsToday": 1, "lastTrainedAt": "iso",
 "trainingHistory": [{"card": "wildCard", "rarity": "uncommon",
                      "outcome": {"stat": "luck", "statGain": 1, "gained": [{"code": "climber", "revealed": true}]},
                      "pickedAt": "iso"}],
 "retireInDays": 26, "lastAgedDay": "2026-11-02", "companyDisabled": false,
 "wageNegotiated": 0.1, "lastMovedAt": "iso", "lastEventAt": "iso",
 "eventModifiers": [{"code": "foundToolbox", "kind": "happiness", "delta": 10, "until": "iso"}],
 "coworkerFiredAts": ["iso"], "trainerSessionsUsed": 2, "trainerSessionsUsedAt": "iso",
 "charmLuck": [{"amount": 6, "until": "iso"}],
 "tool": "<toolItemId>", "toolStatus": {"rolledPercent": 10, "bonusPercent": 10, "isUsable": true, "isBroken": false},
 "toolItem": {"_id": "…", "owner": "<userId>", "employee": "<employeeId>", "code": "pickaxe2", "skills": {"production": 10},
              "state": 79.2, "maxState": 100, "createdAt": "iso", "updatedAt": "iso"},
 "createdAt": "iso", "updatedAt": "iso", "__v": 0}
```
- **Changed by 2026-11-02 (v0.27.3/v0.27.4)** **[observed 2026-11-02, 37 own + 3 foreign employees]**: `region`, the `revealed` flags (top level, traits, breakdown contributions; stored `trainingHistory[].outcome.gained[]` still carries `revealed: true`), `happinessBreakdown.shield` and `retireAskAt` are gone; `retireInDays` (16–45 in the sample) replaces `retireAskAt`. Traits may carry an `arg`. The fields from `wageNegotiated` down are optional: `wageNegotiated` (30 of 37, a fraction such as 0.1–0.3, presumably the negotiated wage cut **[assumption]**), `lastMovedAt` / `lastEventAt` / `eventModifiers` (about half), `careBoosts` (21), `tool` + `toolStatus` + `toolItem` (12, the equipped tool; `toolItem.code` is a `gameConfig.items` tool such as `pickaxe1`–`6`), `charmLuck` (5), `trainerSessionsUsed(At)` (2), `coworkerFiredAts` (1). `base.responsibility` is still returned although v0.27.4 hid it in the UI.
- `eventModifiers[].kind` is `happiness` or `production`; codes seen: `armNotes, badHoroscope, coffeeMachine, compliment, foundToolbox, friendshipBlooming, generalCoo, lunchThief, plasticPlant, sameHaircut, sandwichDiscovery, suggestionBox, thermostatWar, warStories`. New `productionBonus` sources: `event, handy, loner, tool`; new happiness reasons: `comicCoworker, event, responsibility`.

Employee event (`employeeEvent.getHistory` item) **[observed 2026-11-02]**:
```json
{"_id": "…", "owner": "<userId>", "code": "foundToolbox", "status": "resolved", "participants": ["<employeeId>"],
 "cast": [{"employee": "<employeeId>", "name": "…", "gender": "male", "nationality": "<countryId>", "company": "<companyId>"}],
 "params": {"itemCode": "petroleum", "wage": 0.142362, "toolFamily": "pickaxe"},
 "options": [{"costs": []}, {"costs": []}], "defaultOption": 1, "expiresAt": "iso", "resolvedAt": "iso",
 "outcome": {"option": 1, "band": "success", "auto": false,
             "applied": [{"type": "happiness", "employee": "<employeeId>", "delta": 10, "until": "iso"}]},
 "createdAt": "iso", "updatedAt": "iso"}
```
Only `foundToolbox` was seen in history; `params` and `options[].costs` vary by event code **[assumption]**.
- `wage` is hourly; `wageExpectation` is the 70–130% multiplier from the patch notes. `estimate` is per hour.
- **Trap: `base.<stat>` is the rolled base plus training**, not the rolled base; the rolled base is `breakdown.<stat>.base`
  (`base` = `breakdown.base + trained` in all 486 stat checks of 162 employees) **[observed 2026-11-02]**. Flat trait/coworker
  Production sits in `breakdown.production.contributions[]` (entries without `percent`).
- Paid wage identity: `wage = (breakdown.production.base + trained) / 4 × gameStat.getPpMoneyValue × wageExpectation`, trait
  Production excluded (all 162 employees, also after v0.27.4's note claiming otherwise) **[observed 2026-11-02]**.
- Added by v0.27.4: `lastAgedDay` (UTC date of the last ageing; age rises once per day worked or trained), `companyDisabled`;
  roster `hourly.engineMultiplier` (2 with a lone Talks to Machines employee, 1 otherwise) **[observed 2026-11-02]**.
- In one sample `estimate.production` = `breakdown.production.total` ÷ 4 × (1 + `productionBonus.total`/100) (4 ÷ 4 × 1.33 = 1.33) **[observed, one sample: verify before relying on it]**. Use `estimate` rather than recomputing it.
- `specializations` maps an item code to consecutive days on that good, which feeds the `specialization` bonus **[observed + patch notes]**.
- Codes seen on 2026-10-28 (the lists are probably incomplete): trait codes `anchor, bandOfBrothers, burnout, claustrophobe, climber, cosmopolitan, creatureOfHabit, flightRisk, foreman, gambler, handy, homesick, improviser, laborer, loner, luckyCharm, modest, oldFriends, patriot, quickStudy, recruiter, rival, salvager, sociable, specialist, statist, taxShy, trainer, veteran`; `productionBonus` sources `bandOfBrothers, gambler, happiness, improviser, management, manager, oldFriends, sociable, specialization`; happiness reasons `managerCare, recentlyMoved, trait`.

## Transactions 🔑

### `transaction.getPaginatedTransactions`
Requires a key **[observed 401]**. Inputs **[spec]**: `limit` (int 1–100, default 10), `cursor`, `userId`, `muId`, `countryId`, `partyId`, `itemCode`, `transactionType` (a single value **or an array**).

`transactionType` enum **[spec]**: `applicationFee, trading, itemMarket, wage, donation, articleTip, openCase, craftItem, dismantleItem, battleLoot, countryMoneyTransfer`.

Item **[explorer saved example 2026-09-26, trading]**: `{"_id", "transactionType": "trading", "money": 100.608, "itemCode": "ammo", "quantity": 131, "sellerId": "<userId>", "buyerId": "<userId>", "offerCreatedAt": "iso", "createdAt": "iso"}`. Trades also carry `buyerCountryId` / `sellerCountryId` when a side is a country treasury, and a donation **to a country** is `{transactionType: "donation", money, buyerId: <donor userId>, sellerCountryId: <countryId>}` **[observed 2026-11-02]**. The project reads `transactionType`, `buyerId` (payer for donations), `money` and `createdAt` **[project]**. Fields for other types, such as donation recipients, are **unknown**.

Country treasury ledger **[observed 2026-11-04, Romania, `countryId` filter]**:
- `countryMoneyTransfer`: `{money, sellerCountryId, buyerCountryId, createdAt}`; **`sellerCountryId` is the sender**, `buyerCountryId` the receiver (matched a government article's "1,500 → Israel" rows). The filter returns both directions.
- `trading` with `buyerCountryId` = the country: treasury **purchases** (`buyerId` = the official who bought; 957 since the 1st, ~280/day). Items with only `sellerCountryId` = the country also appear (273); whether that is a treasury sale or the seller's citizenship is **[assumption, unverified]**.
- Treasury balance = `country.getAllCountries` item `money`. Treasury **inventory** (`inventory.getById {countryId}`) answers 403 "API tokens cannot access this endpoint" for the bot key.

MU ledger **[observed 2026-10-04, with key]**: `{muId}` filters to transactions touching that MU. A donation **to** an MU is `{transactionType: "donation", money, buyerId: <donor userId>, sellerMuId: <muId>}`. MU market trades carry `buyerMuId` (MU bought; `buyerId` = the member who placed it) and/or `sellerMuId` (MU sold). `transactionType` as an **array** (`["donation","trading"]`) works. `muId` + `battleLoot` returned nothing: bounty and contract money is not in the MU ledger (use `battleRanking dataType: money`).

Notes:
- **No date-range filter** in the spec. To get "this week", paginate newest-first and stop once `createdAt < start`. Today's `warera.market.get_user_transactions` reads every page of a user's full history **[project]**. Newest-first ordering was **[observed 2026-10-04]** for `muId` queries (`warera.market.get_mu_transactions` stops at the first older item).
- Entity filters exist (`countryId`, `muId`, `partyId`). **`countryId` + `donation` returns donations to that country**: 100 of 100 items had `sellerCountryId` = the country and the donor in `buyerId` **[observed 2026-11-02, Romania]**. It does not list citizens' donations to MUs, parties or other countries. Unfiltered `countryId` returned the treasury's trades (`buyerCountryId`/`sellerCountryId`) and donations. See api-opportunities.md A7.

---

# Procedures not in the official spec (from the community explorer, verified live 2026-10-03)

Source: `https://warera.realmarijn.nl/api-explorer` **[explorer]**. Flag them as unofficial in code reviews.

## Donations

### `donation.getManyPaginated`
Inputs: `muId`, `countryId`, `partyId` (scope; all optional), `limit` (1–100, default 10), `cursor` **[explorer]**. The `countryId` and `muId` filters were observed working.
```json
{"items": [{"_id": "…", "userId": "<donor userId>", "countryId": "<countryId>", "muId": null, "partyId": null,
            "amount": 55065, "createdAt": "2026-02-11T…", "updatedAt": "2026-09-26T…"}],
 "nextCursor": "…"}
```
- **Each item is a running lifetime total per donor and target, not one donation event.** `createdAt` is the first donation, `updatedAt` the latest, and items are sorted by `amount` descending **[observed]**.
- So it answers "all-time top donors to country, MU or party" in one paginated call. It **can't** answer "donations this week" on its own. For weekly windows you need `transaction.getPaginatedTransactions` 🔑, or a diff of two snapshots of this list.
- No key needed, unlike transactions.

### `donation.getTotalDonations`
Inputs: `muId`, `countryId`, `partyId` (optional). Returns `{"totalAmount": 661252.06, "donorCount": 446}` **[observed]**. Called with no scope it returned `{0, 0}`.

## Companies (extra)

### `company.getProductionBonus`
Input: `companyId*`. Since v0.27 it returns only `{"depositBonus": 0, "total": 0}` (percent), and all 10 companies sampled had `total: 0` **[observed 2026-10-26]**: deposits are off, strategic resources no longer boost production, and party ethics are gone. Before v0.27 it was `{strategicBonus, depositBonus, ethicSpecializationBonus, ethicDepositBonus, total}`. The v0.27 boosts (Management +2%/point up to +22%, manager up to +22%, happiness ±1%/point from 50, tools +3% to +65%, +1%/day on the same good up to +20%, +5% in a core region of your country) are **not** in this response **[admin patch notes v0.27]**.

### `company.getRecommendedRegionIdsByItemCode` 🔑
Inputs: `itemCode*` (any item code; the explorer lists 59), `count` **[explorer]**. **401 without a key** **[observed]**.
Explorer example (saved 2026-09-16): `[{"regionId": "…", "bonus": 20, "strategicBonus": 20, "depositBonus": 0, "ethicDepositBonus": 0, "ethicSpecializationBonus": 0, "taxPercent": 6}, …5]`. It's the best regions to produce an item, with the bonus breakdown and tax. Since v0.27 it returned `[]` for `steel` **[observed 2026-10-26]**.

## Market (extra)

### `tradingOrder.getPublicOrdersByOwner`
Inputs: one of `userId`, `muId`, `countryId`, `partyId` **[explorer]**.
```jsonc
{"buyOrders": [{"_id", "user", "country", "itemCode", "quantity", "price", "offerAt", "type": "buy"}],
 "sellOrders": [],
 "allOrders": [ …buy + sell… ],
 "totalBuyMoneyInvested": 3286.16, "totalSellMoneyExpected": 0, "totalSellQuantities": {"<itemCode>": qty}}
```
Use it for open market orders of a country treasury, an MU or a player (e.g. "what is Romania's treasury buying?").

## Work stats (extra)

`workOffer.getWageStats` was removed in v0.27 (404 **[observed 2026-10-26]**); see Managers above for `managerOffer.getWageStats`.

### `work.getLastByEmployee` 🔑
Inputs: `employeeId*`, `limit` (default 20) **[client + observed]**. An employee's latest hourly work entries, newest first: `[{"_id": "…", "wage": 0.02027, "production": 1.4, "createdAt": "iso"}, …]` **[observed 2026-10-28]**. Works for any employee. In the explorer since 2026-10-28.

### `work.getStatsByUserId` / `work.getStatsByCompany` / `work.getStatsByEmployee` 🔑
Inputs: `userId*` / `companyId*` / `employeeId*`, plus `days` (1–60, default 30) and `timezone` (IANA, buckets the days) **[explorer + client]**. `getStatsByWorker` and `getStatsByWorkerAndCompany` were removed in v0.27 (404); `getStatsByEmployee` replaces them **[client]**.
- **401 without a key** **[observed]**. The explorer says Premium is required, but `getStatsByUserId` answered with the bot key **[observed 2026-10-26]**. `getStatsByEmployee` (in the explorer since 2026-10-28) returns `[{dailyDate, total, wage, employeeProd}]` per day **[observed 2026-10-28]**.
- `employeeProd` and `total` are **production points**, not money: an employee at about 1.2 production per hour (`work.getLastByEmployee`) showed about 29 per full day **[observed 2026-11-01]**. Coins = production points × `gameStat.getPpMoneyValue` (0.0997 that day), which is the game's own valuation. `dailyDate` is the UTC game day.
- An employee's `createdAt` is the hire time: a roster sample was created 2026-10-29 and trained from that day **[observed 2026-11-01]**. `retireAskAt` (when they will ask to retire) was gone by 2026-11-02; read `retireInDays` instead **[observed 2026-11-02]**.
- `getStatsByUserId` returns a daily series `[{"dailyDate": "2026-10-26", "total": 1295.9, "wage": 3.818, "employeeProd": 47.9, "selfWork": 448, "automatedEngine": 800}, …]`; `getStatsByCompany` items carry only the parts that apply (e.g. `{dailyDate, total, automatedEngine}`) **[observed 2026-10-26]**.
