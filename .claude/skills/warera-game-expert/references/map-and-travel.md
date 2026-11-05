# Map, position and travel

Introduced with the map update v0.26.0 (2026-09-16). Before it, any battle could be hit from anywhere.

> **v0.28 (2026-11-03**, admin article `6aea1496b615c31fa0eb4152` "v0.28 (Nuking movement + perf)", `PATCH_0_28`; checked live
> 2026-11-04): **you fight in any battle from wherever you are** `[RULE][LIVE]` (config `battle.locationGateEnabled` false; no Move
> button, no travel cost). **About 2026-11-10** ("in 7 days") `[SCHEDULED]`: **movement is turned off** — no travel between
> regions, no Stamina, no wooden cases on the map; wooden cases you hold can still be opened; wooden-case market listings go
> back to their sellers and buy orders are refunded; the **Cross regions** and **Collect wooden cases** milestones are disabled
> (levels saved, "could come back"); travel and wooden-case missions are replaced. The admin: movement "could come back one day,
> only if it has a real purpose". The live config has a `mapTravel` flag block (`movementEnabled`, `travelHomeEnabled`,
> `mapCasesEnabled`, `positionMarkerEnabled`, `staminaBarEnabled`), all `true` on 2026-11-04; when they turn `false` the
> switch-off has happened. Until then the rules below still apply to travel, but **not to fighting**. Everything in this file
> about standing in a battle region is history from 2026-11-03.

## Where you fight from `[VERSIONED]`

| Battle type | v0.26.0 → v0.27.4 (2026-09-16 → 11-02): you had to be in | Since v0.28 (2026-11-03) |
|---|---|---|
| Attack | the region the attack was **launched from** | anywhere |
| Defense | the **attacked** region | anywhere |
| Resistance / revolt | the **disputed** region | anywhere |
| Tournament | anywhere | anywhere |

*History:* until you were in the right region the **Hit** button was replaced by **Move** (cost shown on the button). The
launch region still matters for **which** region can be attacked (adjacency, U-CMB-12), not for where fighters stand
(`war.attack_origin`). The map shows two icons: your **residence (home)** and your **current position** (position marker
behind the `positionMarkerEnabled` flag). New accounts start in a random original region of their country with **20 oil**
(10 regions of travel); from v0.27 (2026-10-26) with **150 oil** (75 regions of oil-paid travel). Whether the starting bag
changes once travel is gone isn't stated `[GAP]` (U-V28-4).

## Stamina and oil (`map.stamina`, `map.oil_per_region`) `[RULE][LIVE]` — until ~2026-11-10 (v0.28)

- Stamina: max 100, +10 per hour, 10 per region crossed → a full bar = 10 regions; regen alone ≈ 24 regions/day.
- When Stamina is short, each uncovered region costs **2 oil**. Stamina pays first, oil covers the rest.
- Any region is reachable from any other; two regions were never more than **19 regions** apart on the v0.26 map; **20** on the live graph since v0.28.
  `[OBS]` 2026-10-14, from the live map graph (`region.neighbors`, 726 regions, connected and symmetric): the longest
  shortest path found was 18. `[VERSIONED]` **Re-measured 2026-11-04** on the v0.28 graph (742 regions, 1,856 links, after the
  71 removed v0.27 links closed): the longest shortest path is now **20** regions, so the "never more than 19" claim no longer
  holds (`map.max_region_distance`, `LIVEAPI_20261104`). The Stamina/oil per region costs are **not** in gameConfig (only
  `region.freeTravelHomeCooldownHours` 12 and `homeMoveConcreteCost` 100 are), so the 10 Stamina / 2 oil come from the guide.

| Distance | Stamina only | Oil only |
|---|---|---|
| 1 | 10 | 2 |
| 5 | 50 | 10 |
| 10 | 100 | 20 |
| 19 | more than a full bar | 38 |

Example: 60 Stamina, 8 regions → 6 by Stamina + 2 × 2 = 4 oil. The return trip is paid again unless the bar refilled.
Formula: `oil = 2 × max(0, regions − floor(stamina/10))` (F-TRAVEL). `[VERSIONED]` Only since **v0.26.1** (2026-09-17); under v0.26.0
one resource paid the whole trip, so a bar just short of the distance paid nothing and the trip was all oil.

Two separate home actions (U-MAP-1, closed with the user 2026-10-13). The **free trip home** ends with movement (~2026-11-10,
flag `travelHomeEnabled`); whether **Move home** stays, and what a home region does without travel, isn't stated `[GAP]` (U-V28-2):
- **Free trip home**: every **12 h** (`region.freeTravelHomeCooldownHours` 12) `[RULE][LIVE]`. `[OBS]` The map menu's "Back to home
  region" entry was seen on 2026-09-15 (`[CODEX]`). No patch note mentions it.
- **Move home**: from a region page's menu, **100 concrete** (`region.homeMoveConcreteCost`, v0.26.1), fixed regardless of distance;
  it **relocates** your residence to that region. It isn't a trip; the next free trip takes you to the new home.

`[OBS]` (`[CODEX]`, 2026-09-16) In the API profile, `location` is where the player **stands** and `region` is the **home** region
(two players checked against the game). Reading `region` as the position prices every trip wrongly. Stamina is
`skills.stamina` (`currentBarValue`, `hourlyBarRegen`). See [data-model.md](data-model.md).

## Wooden cases (`map.wooden_case`) `[RULE]` — no map spawns from ~2026-11-10 (v0.28)

`[SCHEDULED]` v0.28: once movement is off no wooden cases appear on the map; cases already in your inventory **can still be
opened**; every wooden case listed for sale **returns to its seller** and every wooden-case **buy order is refunded**. Whether
wooden cases can still be listed afterwards, and whether new accounts keep the 3 starter cases, isn't stated `[GAP]` (U-V28-3).
The Loot chance skill's "+1% to the hourly wooden case chance" disappears with the cases (its text is behind the
`mapCasesEnabled` flag), leaving only its battle-loot effect.

- One roll per hour: base **25%** chance, plus **1 percentage point per 1% Loot chance** (UI text of the Loot chance skill, `TRANSLATION_EN`
  2026-10-27; client `lootChancePercent` 25 `[LIVE-CLIENT]`), so a 25% Loot chance doubles it to 50%. On success a case appears in a
  random region, visible only to you. New accounts also get **3 starter cases** that last **168 h** (client `starterCases`).
- Max **5 pending**, each expires after **48 h**; while 5 are pending the hourly roll is skipped.
- Claim only while standing in that region (region menu). Map button shows the nearest case and distance; **Move & collect**
  travels and claims in one tap.
- Contents: rarity first — Epic 2% (Cooked Fish, Heavy Ammo, Pill), Rare 13% (Ammo, Steak), Uncommon 20% (Concrete, Steel,
  Bread, Oil, Paper, Light Ammo), Common 65% (Grain, Iron, Wood, Lead, Limestone, Mysterious Plant, Petroleum, Livestock,
  Fish). Quantity from a random **20–80 work-point budget** (cheap goods in big stacks, finished goods in few units) — so two
  cases are worth roughly the same. Quantities: `data/equipment.yaml#wooden_case_drops` (pre-v0.27 budgets).
- **v0.27** `[RULE]` (`map.wooden_case`): rarer cases hold more. Budgets **Common 20–40, Uncommon 40–70, Rare 80–130, Epic
  160–260** PP; odds **60 / 25 / 12 / 3%**. One click collects every wooden case in a region. *Derived:* using range midpoints, the
  expected budget per case rises from 50 to 0.60×30 + 0.25×55 + 0.12×105 + 0.03×210 = **50.65 PP**, almost unchanged on average,
  but the spread is much wider: an Epic case is worth ~7× a Common one. The budgets are confirmed by the live client (2026-10-27)
  `[LIVE-CLIENT]`; the rarity odds are server-side (article only). The client now has **one 20-good pool** for every rarity (all
  the goods above plus Pill), so the per-rarity item lists above are v0.26 history; a v0.27 case of any rarity can presumably hold
  any good `[Derived from the config shape]`. Quantities then follow `max(1, floor(budget / item PP))` (F-WOODEN-QTY, `[CODEX]` method): ammo 20–32, heavy ammo
  10–16, steak and cooked fish 4–6, concrete/steel/bread 4–7, a single Pill (`data/equipment.yaml#wooden_case_drops_v027`). In PP
  every item is worth the same; in money the Pill is by far the best roll.
- Wooden cases can be sold on the market.

`[STRAT-RO]` (written for v0.26–v0.27, when fighting needed position) Collect cases on the way to an ordered battle or within
regenerating Stamina; don't pay oil for an isolated case if its market value is below the round-trip oil cost; don't wander from
the front before an important battle. Since v0.28 there is no front to stand on: only the oil rule still applies.

## The last week of movement (v0.28, 2026-11-03 → ~11-10) *Derived*

Fighting no longer uses Stamina, so for one week Stamina has exactly three uses left: wooden cases, the two map milestones and
travel missions. A trip to a case counts regions for the Cross regions milestone and the travel missions at the same time.
- **Free regions:** a full bar (10 regions) plus 10 Stamina/h × 168 h = **about 178 regions** in 7 days, if the bar is never left
  full (it caps at 100, so travel at least every 10 h). Every region beyond that costs 2 oil.
- **Cross regions milestone** (targets in unresolved-mechanics.md, U-PRG-4a): 100 regions = tier 6, 170 = tier 7, 270 = tier 8,
  430 = tier 9. From zero, free Stamina alone reaches tier 7; tier 8 needs ~92 more regions (~184 oil), tier 9 ~252 more (~504
  oil). Claimed XP per tier is 10 × tier up to 100 (U-PRG-4a). Compare the oil with its
  market price before chasing a tier; only the oil is a real cost.
- **Collect wooden cases milestone:** cases spawn at 25% + 1 point per 1% Loot chance per hour (max 5 pending), so about **42
  (25%) to 84 (50%)** spawn in 168 h, plus up to 5 already waiting, each needing a trip to its region. Targets: 33 = tier 5, 52 =
  tier 6, 84 = tier 7.
- **Wooden cases themselves:** worth about 50.65 PP on average since v0.27 (≈ 5 money at the 2026-11-02 PP value of 0.099,
  dated). Sell before the switch-off if you'd rather have money (listings are returned afterwards), or keep them to open later.
- Claim every milestone tier before the switch-off: whether unclaimed tiers can be claimed afterwards isn't stated (U-V28-5).

## What the map meant `[STRAT-RO]` (community analysis, v0.26–v0.27; history since v0.28)

`[VERSIONED]` Since v0.28 fighters pay nothing to reach a battle, so the advice below about launch regions, front distance,
oil for fighters and distant allies or proxies no longer applies. The community's original concern returns: "without travel
costs, any country could hit anywhere, favouring 1–2 giant alliances". The world-development curve of the alliance bonus
([alliances.md](alliances.md)) is now the main brake on alliance size *[Derived]*. Capital links still decide the −25%
unlinked malus.

Original analysis: without travel costs, any country could hit anywhere, favouring 1–2 giant alliances; paid travel makes wars more local.
- Player: attack only on national orders; decide if travel is worth it for a case/bounty/mission; keep oil.
- Leadership: choose launch regions near most fighters' residences (each extra region costs every fighter 10 Stamina or 2
  oil); a country can launch several attacks from one region (fighters concentrated there support several battles);
  surprise attacks far from defenders' homes force them to pay travel; distant allies are costlier to support → compact
  alliances; re-evaluate distant proxies; **every order must say where fighters must stand**.
- Common mistakes: burning Stamina on cases right before a mobilization; travelling to a battle without an order then paying
  to return; confusing *adding resistance* (no need to be in the region `[OBS]`) with *fighting* a resistance battle (must be there).

## Map changes in v0.27

`[RULE]`, live since 2026-10-26 (admin article `6ade08f7899288ce9f0bfe36`, section 17).
**726 → 742 regions**, a new country (**Maldives**), more detailed borders in South America and Africa. Regions that are only
renamed keep their owner, development and companies. Region upgrades now show on the map with their level, and sea links are
drawn as lines.

- **New regions (16):** Argentina: Córdoba, Catamarca · Brazil: Tocantins · Chile: Magallanes y Antártica Chilena, Rapa Nui ·
  Cyprus: Southern Cyprus (new capital; the old Cyprus region becomes Northern Cyprus) · India: Karnataka, Andhra Pradesh and
  Telangana · Libya: Benghazi · Maldives: Maldives · Peru: Loreto · South Korea: Gangwon · Sudan: Khartoum (new capital, split from
  Northern Sudan), Port Sudan, South-Eastern Sudan · United States: US Pacific Islands.
- **Renamed:** Argentina: Resistencia → Chaco, Ushuaia → Comahue · Brazil: Manaus → Upper Amazon Basin, Belém → Atlantic Amazon,
  Campo Grande → Pantanal, Fortaleza → Paranaíba River Basin, Recife → Borborema Plateau, Salvador → Bahia, Rio de Janeiro → Doce
  River Basin, São Paulo → Rio-São Paulo Axis, Porto Alegre → Brazilian South, Brasília → Central Brazil · Cyprus: Cyprus → Northern
  Cyprus · India: Utkala → East India, Dravida → Tamil Nadu and Kerala, Maratha → Maharashtra, Northeastern India → North East,
  Madhya Pradesh → Rajasthan, Haryana → Madhya Pradesh · Libya: Northwestern → Tripoli, Southwestern → Fezzan, Northeastern →
  Jabal al Akhdar, Southeastern → Kufra · South Korea: Northern → Seoul, Southern → Jeolla and Jeju Island, Eastern → Gyeongsang,
  Western → Chungcheong · Sudan: Nuba Mountains → Kordofan · United States: Northern USA → Midwest, American Atlantic Coast →
  New England, American Pacific Coast → Virginia.
  Careful: the name **Madhya Pradesh** now refers to the former Haryana, and the former Madhya Pradesh is **Rajasthan**.
- **Capitals moved:** Cyprus: Northern Cyprus → Southern Cyprus · Ghana: Northern Ghana → Eastern Ghana · Sudan: Northern Sudan →
  Khartoum · United States: New England → Virginia.
- **New links (36):** Buenos Aires–Comahue, Comahue–Mendoza, Comahue–Santiago, Comahue–Temuco, Posadas–Montevideo,
  Pantanal–Brazilian South, Brazilian South–Eastern Paraguay, Western Costa Rica–Ecuadorian Islands, Eastern Burkina Faso–Northern
  Ghana, Zurich–Bavaria, Faroe Islands–Vestlandet, Hiiu & Saare–Western Finland, Pomerania–Skåne & Halland, Brittany–Azores,
  Cayenne–Azores, Souss-Massa–Madeira, Eastern China–Jeolla and Jeju Island, Kyushu–Gyeongsang, Northern Cyprus–North Lebanon,
  South Lebanon–Damascus, Al Karak–Tabuk, Al Hudud ash Shamaliyah–Al Quassim, East India–Madhya Pradesh, East India–Maharashtra,
  East India–Uttar Pradesh, Gujarat–Madhya Pradesh, Madhya Pradesh–Maharashtra, Kashmir–Rajasthan, Toliara–Sofala,
  Copperbelt–Luapula, Arequipa–Lima, Alaska–Northwestern USA, Hawaii–Southwestern USA, American Great Lakes–Virginia, New
  England–Virginia, Southeastern USA–Virginia.
- **Removed links (71)** stay open for **10 days** after the update, then close. `[VERSIONED]` **Closed by v0.28** (2026-11-03),
  confirmed on the live graph 2026-11-04 (e.g. Patagonia now links only Comahue, Magallanes, Puerto Montt and the Falklands;
  Virginia only Great Lakes, New England and Southeastern USA). Notable groups: Patagonia loses its links to
  Buenos Aires, Mendoza, Santiago and Temuco; Hawaii loses North Island, Antofagasta, Trujillo, Papua, Tohoku and Virginia; Virginia
  loses British Columbia, Baja California, Alaska, Hawaii, Northwestern USA and Southwestern USA; Northern Sudan loses Red Sea Coast,
  Central Eritrea, Red Sea Region, Amhara, Tigray and Afar, Makkah and Upper Nile; Northern Cyprus loses Lower Egypt, Crete, Northern
  District and Beirut; Tamil Nadu and Kerala loses East India, Jaladhi, Maharashtra, Rajasthan and Socotra; Jabal al Akhdar loses
  Fezzan, Kufra and Tripoli. The full list is in the article.
- `[VERSIONED]` **v0.27.1 (2026-10-27)** closed, at once, the links "between regions that don't share a border": Jabal al Akhdar ↔
  New Valley, Ar Riyad ↔ Ha'il, Naxcivan ↔ Eastern Anatolia, Northern Sudan ↔ South-Eastern Sudan, South-Eastern Sudan ↔ Tigray and
  Afar, and "all Virginia weird links" (not listed one by one; read `region.neighbors` for the live graph). Whether these were
  among the 71 or new v0.27 links isn't stated. The same patch added map **order arrows** pointing to battles your country or MU
  ordered, and ordered battles show at a lower zoom level.

*Derived:* links decide both travel cost (regions crossed) and capital links (the −25% unlinked defense malus). For ten days both
the old and new links worked. Since they closed (v0.28), regions whose only path to their capital ran through a removed link may
be unlinked: 37 regions had `isLinkedToCapital` false on 2026-11-04 (no earlier count to compare). Once movement is off, links
matter only for capital links and for which regions are adjacent targets.
