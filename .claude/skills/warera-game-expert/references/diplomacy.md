# Diplomacy overview

| Instrument | In-game? | Effect | Reference |
|---|---|---|---|
| Alliance | yes | up to +20% (can be negative) damage; members can't attack each other; daily paper upkeep | [alliances.md](alliances.md) |
| Defensive Pact | yes, bilateral | +1%/day up to +10% defending the partner | [defensive-pacts.md](defensive-pacts.md) |
| Main Enemy | yes, unilateral | +1%/day up to +10% vs that country | [main-enemy.md](main-enemy.md) |
| Automatic non-aggression windows | yes | no war declaration for a period | below |
| NAP | **no — community agreement** | contractual non-aggression, monitored by Discord bot | below |
| International economic agreement | no — community agreement | tax refunds/subsidies for moving economy | below |

## Automatic non-aggression windows `[RULE]`

| Trigger | Duration |
|---|---|
| Liberation of a region | 24 h, bilateral (neither side can declare war) `[LIVE]` |
| Peace | 72 h `[LIVE]` |
| Alliance break-up | 72 h |

## NAPs `[POLICY-RO]` (not a game object)

A NAP is a diplomatic agreement between countries/alliances not to attack and usually not to support hostile actions. Romania
keeps the list on Discord; TheMachine's `monitor_nap` job checks national and MU orders against it hourly.

| Typical clause | Recommended content |
|---|---|
| Non-aggression | no direct damage between parties; no deliberately created fronts |
| Non-interference | no funding revolts, destabilization or indirect support for hostile attacks |
| New members / exits | does protection continue after leaving the alliance; how new members are added |
| Duration / termination | fixed term or auto-renewal; prior notice, e.g. 7 days |
| Penalties | compensation per 1,000 damage, escalation for repeat, payment deadline |
| Transfers | no money to the direct adversary during the fight and for a period after |
| Advance notice | notice before actions that may indirectly affect the other party |

`[POLICY-RO]` Check `/nap list`, `/diplomacy` and #monitorul-oficial before farming loot; report accidental damage immediately
(hiding it worsens the incident); on expiry/termination, announce to citizens and the alliance **before** orders change.

## International economic agreements `[POLICY-RO]`

Some countries offer reductions, tax refunds or other benefits to attract companies, production and workers. A good agreement
is measurable and verifiable:

| Element | Define |
|---|---|
| Object | companies, products, number of workers, regions |
| Duration | minimum period, exit conditions |
| Benefit | % of tax refunded, bonus or subsidy |
| Calculation method | tax base, period, prices, exclusions |
| Audit | tool used, data access, report frequency |
| Payment | calendar, currency/items, responsible person |
| Political risk | what happens if taxes, government, bonus, deposit or region ownership change |
| Approvals | MoE, MoFA, President and, if needed, Congress |

Don't move the economy on verbal promises. Document in the diplomatic channel; publish periodic reports. Because deposit
bonuses vary (20–40%), the agreement must name the specific deposit it relies on. *From v0.27 deposits are off and employees in your
own country's core regions get +5%, and taxes now cost employee happiness: agreements that bring companies abroad have to offset
both, which makes them harder to justify `[Derived]`.*

## Bot commands `[POLICY-RO tool]`

`/diplomacy [country]`, `/update_diplomacy`, `/add_diplomacy`, `/remove_diplomacy`, `/delete_diplomacy`, `/nap add|remove|list`
— see [romanian-community-ops.md](romanian-community-ops.md).
