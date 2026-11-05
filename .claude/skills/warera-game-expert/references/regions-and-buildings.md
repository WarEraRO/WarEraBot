# Regions, development and buildings

## Core vs occupied regions `[RULE]`

- **Core regions** are a country's original regions. Revolts recover occupied core regions.
- Fighting for a country occupying one of your core regions → **−50%** damage.
- Player residences are placed on the country's original regions whether or not they are currently held.

## Development `[RULE]`

- Development is a **country** value split evenly across its core regions. It depends on several factors but is basically
  produced by the country's players: more active citizens → more development.
- **Income**: each region yields its country money per day equal to **twice** its development since v0.27.2 (a region with 30
  development → 60 money/day; 30 before) `[VERSIONED]`.
- **Occupation moves development**: the occupier takes the occupied region's development. Two ways to grow it: recruit
  players, conquer regions.
- Development drives daily treasury income (**2 coins per point per day since v0.27.2**, 1 before), the cost of country orders
  and diplomatic upkeep (scale with average development), and Congress seats (via active population). Losing a core region = lost income **and** income for the enemy.
- Regions not linked to the capital earn **−50% development income** (v0.8.0; config `regionNotLinkedToCapitalMalusDevelopmentPercent` 50).
  **v0.27 (2026-10-26): unlinked regions pay their full development income**; the −25% defense malus is not mentioned and stays.
- **v0.27** `[RULE]`: every region shows a **daily income estimate**, with a Daily revenue map mode. Government types change
  development income: Republic ×2 from own regions and nothing from conquered ones, Nationalist State ×0.7, Autocracy ×1.25.
  Conquered regions give the original owner **10% of the income tax** (whether the resistance-based share of development income
  still applies isn't stated `[GAP]`).
- **v0.27.2** `[VERSIONED]` `[LIVE]` (2026-10-28): development income and strategic-resource income **doubled** (config
  multipliers 2). Development itself didn't change, so costs that scale with development (orders, upkeep, resistance bar) are
  untouched *[Derived]*: each development point is now worth twice as much income for the same upkeep. Government-type
  multipliers stack on top (×2 × 0.7 for a Nationalist State, ×2 × 2 for a Republic core region; API sample 2026-10-29).
- Development types `[WIKI-ONLY]`: **Core**, **Current**, and **Average** (midpoint of the two). Average Development drives alliance and
  diplomacy upkeep, region-upgrade upkeep and (per the alliance page) order costs. Initial development of a country =
  `((active citizens × average level) / 20)^0.95` (100 × 25 → ≈ 98). `python scripts/country_calculator.py initial-dev`.
- Conquered regions pay part of their development income to the core country by resistance (30 resistance = 30%) `[WIKIPATCH v0.16.0]`.
- Ethics (until v0.27): Republican +50% development income; Fanatic Republican +150% but only core regions earn.

## Deposits and strategic resources

Deposits give a variable production bonus (20–40% per guide) shown on the region page ([production-bonuses.md](production-bonuses.md)).
**From v0.27** deposits are turned off, and a strategic resource pays **whoever holds it** a daily income equal to the development
of the country it **originally** belonged to (Plutocracy ×1.5); it no longer boosts production or development. **Since v0.27.2**
the income is doubled: **2 × the original country's core development** per day, paid hourly `[LIVE]`. Core, not current: the
original country's conquests don't raise it. The line shows on the region that holds the resource, conquered regions included
`[OBS]` (API sample 2026-10-29).

## Map size (v0.27)

The map grows from 726 to **742 regions**, with a new country (**Maldives**), 16 new regions, renamed regions, moved capitals
(Cyprus → Southern Cyprus, Ghana → Eastern Ghana, Sudan → Khartoum, United States → Virginia), 36 new links and 71 removed links.
Renamed regions keep their owner, development and companies. Details: [map-and-travel.md](map-and-travel.md#map-changes-in-v027).

## Region buildings `[RULE][LIVE]`

| Building | Levels | Effect | Activation | Upkeep |
|---|---|---|---|---|
| Bunker | 1–5 (steel 100/200/300/500/1000) | defense +5…+25%; owner citizens full, allies half (pact partners none `[WIKI-ONLY]`); not counted in civil wars (v0.26.2) | ~12 h | oil: max(minimum 1/2/5/10/25, scale × **country** development) `[LIVE]` |
| Military Base | 1–5 (same costs) | attack +5…+25% for attacks launched from the region; same split | ~12 h | same as bunker `[LIVE]` (the wiki's L5 = 15 is outdated) |
| Pacification Center | 1–5 (same costs) | reduces resistance growth 5…25%; Fanatic Expansionist: +3%/level defending revolts | ~12 h | scales with **region** development |

- Upgrade/downgrade cooldown: **8 h** default (live `upgrade.regionUpgradeCooldownHours`); guide: Expansionist 4 h, Fanatic
  Expansionist 2 h (bases), until v0.27 ends ethics.
- v0.27: a **Homeland Front** country can't have military bases and gets +5% bunker; region upgrades show on the map with their level.
- Buildings can be disabled (fast) and destroyed; active buildings without oil deactivate automatically.
- Construction: contribution min level 15, 10 construction points per contribution, energy cost 10 per construction point `[LIVE]`.
- Refund on downgrade/destroy: 80%.
- TheMachine `/get_region_upgrade_cost country` estimates daily oil and market cost of active region upgrades `[POLICY-RO tool]`.

## Connection to capital `[RULE]`

A region not linked to its capital gives its **defender −25%**. Connection does **not** affect the right to attack.

## Transfers and liberation

See [resistance-and-internal-conflicts.md](resistance-and-internal-conflicts.md#revolts-transfer-and-liberation).
