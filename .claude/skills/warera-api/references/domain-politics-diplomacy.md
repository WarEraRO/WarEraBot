# Domain: politics and diplomacy (alliances, diplomacy, wars, parties, elections, unrest, contributions, sanctions)

**Solves:** alliance membership, sworn enemy and defensive pacts with damage totals, war scores, parties and their members, election candidates and vote tallies, the unrest/revolution bar, who contributed to unrest or resistance, and moderation sanctions.

**None of these procedures are in the official spec (0.17.4-beta).** They're documented by the community explorer `https://warera.realmarijn.nl/api-explorer` and were **verified live on api2.warera.io on 2026-10-03, all anonymous (no key)**. They're stable enough to use, but flag them in code reviews as unofficial, like `gameStat.getEquipmentAvgByCode`.

Labels: **[explorer]** the explorer's docs · **[observed 2026-10-03]** live call · **[project]** · **[assumption]**

---

## Alliances

### `alliance.getById`
Input: `allianceId*` **[explorer]**. Get the ID from `country.allianceId`, or from `search.searchAnything → allianceIds`.
```jsonc
{"_id": "6a2966e8f0f195d344d5158c", "name": "ATLAS", "leader": "<userId>",   // [observed] the same ID is an article author, so it's a user
 "memberCountries": [{"country": "<countryId>", "coreDevelopment": 226.6, "averageDevelopment": 226.59, "suspended": false}, …21],
 "currentDevelopment": 1119.4, "coreDevelopment": 1871.52, "averageDevelopment": 1495.46,
 "rankings": {"allianceDevelopment": {"value", "rank", "tier"}, "allianceWeeklyDamages": {…}, "alliancePopulation": {…}, …},
 "scheme": "blue", "mapAccent": "normal", "avatarUrl": "…", "createdAt": "iso"}
```

### `alliance.getManyPaginated`
Inputs **[explorer]**: `page`, `limit`. **Correction:** `page` is **ignored** (page 1 and page 2 returned the same items), and the response has `nextCursor`. Paginate with **`cursor`** instead; that works **[observed]**. Returns `{items: [alliance], nextCursor}`. Only ~12 alliances exist (see `ranking.getRanking allianceDamages`).

## Diplomacy and war

### `countryDiplomacy.getByCountry`
Input: `countryId*`.
```json
{"swornEnemy": {"enemy": "<countryId>", "bonusPercent": 5, "damagesDealt": 504965},
 "defensivePacts": [{"partner": "<countryId>", "bonusPercent": 7, "damagesDealt": 111108}, …11]}
```
This is the authoritative sworn enemy and defensive pacts **with their current damage bonus and the damage dealt under them**. `country.getCountryById` has only bare `enemy` / `defensivePacts[]` IDs.

### `war.getById`
Input: `warId*` (from `battle.war` or events `warDeclared.war`).
```json
{"_id": "…", "isActive": true,
 "attacker": {"country": "<countryId>", "wonBattlesCount": 1, "wonRoundsCount": 3, "damages": 1253243},
 "defender": {"country": "<countryId>", "wonBattlesCount": 0, "wonRoundsCount": 0, "damages": 236571},
 "battles": [], "priority": "<countryId>", "priorityEndAt": "iso", "createdAt": "iso", "updatedAt": "iso"}
```
- `battles` was `[]` even though `battle.getBattles {warId}` returned 2 battles for this war **[observed]**. List a war's battles with `battle.getBattles {warId}`.
- Per-war damage leaderboards: `battleRanking.getRanking {warId, …}`.
- There's no "list wars" procedure. Use `country.warsWith` and battles' `war` field.

## Unrest and contributions

### `country.getUnrestData`
Input: `countryId*`. Returns `{"bar": 56, "barMax": 11329, "lastContributionAt": "iso", "isFull": false, "isOnRevolutionCooldown": false}` **[observed]**. It's lighter than `country.getCountryById().unrest` and adds `isFull` and `isOnRevolutionCooldown`. Rules are in `gameConfig.unrest`.

### `contribution.getCountryUnrestContributions` / `contribution.getRegionContributions`
Inputs: `countryId*` / `regionId*`, `page`, `limit` **[explorer]**.
**Different pagination style** (page-based, not cursor) **[observed]**:
```jsonc
{"results": [{"_id": "…", "type": "unrest" | "resistance", "user": { /* a fully populated user object, ~35 keys */ },
              "country": "<countryId>", "region": "<regionId>" /* region variant only */,
              "amount": 2, "resource": "health", "createdAt": "iso"}],
 "count": 6018, "limit": 10, "page": 1, "pages": 602, "nextPage": 2}
```
- `page` works. `limit` is **ignored**: pages are always 10 items (`limit: 2` returned 10 and echoed `limit: 10`) **[observed]**.
- `user` is **embedded**, so there's no need for follow-up `getUserLite` calls.

## Parties

### `party.getById`
Input: `partyId*` (from `country.rulingParty`, `election.candidates[].party`, `search.searchAnything → partyIds`).
```jsonc
{"_id": "…", "name": "…", "description": "", "country": "<countryId>", "region": "<regionId>",
 "leader": "<userId>", "treasurer": "<userId>", "primaryWinner": "<userId>",
 "councilMembers": ["<userId>"], "members": ["<userId>", …67],
 "avatarUrl": "…", "createdAt": "iso"}
```

Party `ethics` were removed in v0.27 (2026-10-25); a country's **government type** (`country.govType`) replaces them **[observed 2026-10-26]**.

### `party.getManyPaginated`
Inputs: `limit` (1–100), `cursor`, `countryId` **[explorer; countryId filter observed working]**. Returns `{items: [party], nextCursor}`.

## Elections

### `election.getElections`
Inputs: `countryId` **or** `partyId` (one is required), `limit` (1–100) **[explorer]**. Returns `{items: [election], nextCursor}`.
- With neither filter it returns **HTTP 500** `INTERNAL_SERVER_ERROR "Either countryId or partyId must be provided"`, not a 400 **[observed]**. The client retries 5xx up to 5 attempts with backoff, so always pass a filter.
- `type` values observed: `president` (country) and `partyPrimary` (party). Congress elections presumably exist (the explorer mentions them) **[assumption]**; the value is unknown.

### `election.getElection`
Input: `electionId*`.
```jsonc
{"_id": "…", "country": "<countryId>" /* or "party" for primaries */, "type": "president",
 "status": "finished", "isActive": false,
 "candidates": [{"user": "<userId>", "party": "<partyId>", "voteCount": 0, "isElected"?: true}],
 "votes": {"<candidateUserId>": 43, …},          // the real tally; candidates[].voteCount was 0 here
 "votesCount": 81, "electedCount": 1, "electedCandidates": ["<userId>"],
 "votesStartAt": "iso", "votesEndAt": "iso", "createdAt": "iso"}
```
Read results from **`votes`**: `candidates[].voteCount` was 0 for every candidate in a finished election **[observed]**. List items have the same full shape, so `getElection` is only needed when you already have the ID. Schedule: `gameConfig.getDates` (`nextCongressElectionsAt`, `nextPresidentialElectionsAt`); rules: `gameConfig.election`.

## Moderation

### `sanction.getPaginated`
Inputs: `targetUserId`, `type` (e.g. `MUTE_USER`), `limit` (1–100), `cursor` **[explorer]**.
```json
{"items": [{"_id": "…", "targetUser": "<userId>",
            "data": {"type": "MUTE_USER", "durationInHours": 72, "unMuteAt": "iso", "reason": "Rule 7.3.f"},
            "createdAt": "iso"}],
 "nextCursor": "…"}
```
Other `type` values (bans) aren't enumerated **[explorer says "mutes/bans"]**.
