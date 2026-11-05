# Battle orders and priorities

## Priority level vs rank — the key distinction `[RULE]`

| Concept | What it is | Changes bonus/cost? |
|---|---|---|
| **Priority** Low / Medium / High (green / yellow / red) | strength of the order | **Yes**: +5/+10/+15% `[CONFLICT config 10]`; paper ×1/×2/×4 |
| **Rank** #1, #2, #3 … (up to 99) | display order: which battle leadership wants fought first | **No** — display only |

A red #3 gives more bonus than a green #1, even though leadership wants #1 fought first. Example: #1 is a green defense to
be held above 52%, #2 a red attack — rank says what to watch first; colour says the bonus; description says how to fight.
Country and MU orders are ranked separately (both lists start at 1).

## Costs `[RULE]` / `[CONFLICT]`

- Paid in **paper** from the issuer's inventory; Low ×1, Medium ×2, High ×4 (guide).
- **Country**: scales with the country's **average development** (guide — working stance; exact formula unknown).
- **MU**: scales with **member count** (guide). The wiki formula `base (5/10/20) × max(1, floor(members / 5))` fits this
  (21 members, High = 80 paper) but is `[WIKI-ONLY]`.
- The outdated wiki also gives a country formula by active citizens (`base × max(1, floor(active/5))`) — contradicts the guide;
  `country_calculator.py order-cost` prints it only as an estimate.
- Live config keys `set*OrderMoneyCost` 30/10/40 look like legacy money costs (U-ORD-1).
- An order can be upgraded by paying the difference; deactivating and reactivating costs again.
- Until v0.27: Unethical doubles order cost; Fanatic Pacifist makes core-defense and revolt orders free; Fanatic Diplomatic halves
  orders supporting a pact partner; Fanatic Isolationist halves orders against the Sworn Enemy.
- **From v0.27** `[RULE]` (government types, [government-types.md](government-types.md)): Republic orders +25% · Nationalist
  State −25% · Homeland Front **free** orders to defend or retake its own regions, attack orders outside them ×2 · Federation
  half-price orders on allies' battles · Mercenary State order cost ×2 **and order damage ×2** (normal while its capital is occupied).
  How these stack with the Low/Medium/High multipliers isn't stated `[GAP]`; read the cost shown in the order dialog.
- Who can set orders: country — President, VP, Minister of Defense, Minister of Foreign Affairs; MU — owner and commanders.
- **Civil wars**: country orders can't be set `[VERSIONED]` (v0.26.2, 2026-10-14; before that the government side had one).
  The patch doesn't mention MU orders `[GAP]`. Revolts (resistance battles) are unaffected.
- Country and MU orders **stack** when on the same side.

## Display order `[OBS]` / `[RULE]`

Battle panel: red country order > yellow/green country order > MU orders (any colour) `[OBS]`. In the battle list's
**Orders** section, battles appear in the country/MU's chosen order, not by age `[RULE]` (ordering by age `[DEPRECATED]`).

## Orders page and reordering `[RULE]`

- The **Orders page** lists every order that applies to you (country + MU); open it from the active-orders bar at the bottom;
  the same list is on the government and MU pages.
- Governments with *set orders* permission and MU owners/commanders **drag rows and save** the new order.
- When writing a new order you can choose its position instead of appending.
- *Edit country order* / *Edit MU order* are available from a battle's order menu, even if the existing order is on the other side.
- Removing an order or ending a battle **renumbers automatically** (no gaps like 1, 2, 4).
- TheMachine's `/priority` commands manage the **bot's** monitor list; the in-game rank is set separately on the Orders page —
  keep both in sync `[POLICY-RO]`.

## Reading order descriptions `[POLICY-RO]` vocabulary

| Phrase | Meaning |
|---|---|
| PRIO 1/2/3 | relative order among red battles (now backed by rank #) |
| "Keep >52%" | don't dump all damage; keep the edge needed at tick end |
| "Hold until base/bunker" | wait for building activation to get the better bonus |
| "Bomb at …" | concentrate damage in a window to flip the pool before a tick |
| "Missions only" | minimum needed for missions; don't burn war gear |
| Location | `[VERSIONED]` until v0.27.4 only: which region to fight from and whether travel is part of the plan (since v0.28, 2026-11-03, anyone hits from anywhere) |

## No orders `[STRAT-RO]`

- Citizen: ask government/MU commanders; don't assume any ally battle is allowed; check for a **Resistance Focus**.
- MU commander: check map, relations, buildings and national orders before spending paper (travel distances stopped mattering with v0.28).
- Government: prioritize battles protecting territorial links, strategic resources, regions with active buildings, alliance goals.
- With no strategic objective, coordinate loot farming only in battles that break no NAP and don't hurt allies.

## Conflicting orders `[POLICY-RO]`

National order beats MU order. If the MU order points elsewhere than national #1, ask in the MU channel or #battle-orders
**before** using a Pill or oil. MU commanders must copy the national objective; two MUs with different orders fragment
damage and waste paper.
