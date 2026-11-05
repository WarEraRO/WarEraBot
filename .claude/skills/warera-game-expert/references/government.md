# Government

> From v0.27 (2026-10-26, `[RULE]`) each country also has a **government type**, chosen by law with a 30-day cooldown, which
> replaces the ruling party's ethic: [government-types.md](government-types.md).

## Roles and responsibilities

| Role | Core responsibilities `[POLICY-RO]` |
|---|---|
| President | vision, appointments, coordinating government, relations with Congress and citizens, diplomacy, crises; can register for tournaments |
| Vice President | internal coordination, replacing ministers, proxies, communication, diplomacy; can register for tournaments |
| Minister of Foreign Affairs (MoFA) | foreign relations, ambassadors, geopolitical monitoring, negotiations, diplomatic records, **alliance share of world development** |
| Minister of Defense (MoD) | strategy, map & travel, buildings, firepower, priorities and order rank, bounties, contracts, Resistance Focus, tournament registration |
| Minister of Economy (MoE) | taxes, treasury, resources, budget, #economic-orders, paper/oil stocks, economic agreements |
| Minister of Internal Affairs (MoIA) | announcements, support, guides, recruitment, mentoring, feedback, internal coordination |
| Congress | laws, oversight, representing citizens, feedback, approving strategic direction |

## In-game permissions `[RULE]` (the President appoints every position)

| Permission | President | Vice President | Defense | Finance (MoE) | Foreign Affairs |
|---|---|---|---|---|---|
| Set orders | ✓ | ✓ | ✓ | — | ✓ |
| Open battle | ✓ | ✓ | ✓ | — | ✓ |
| Manage citizenship applications | ✓ | ✓ | — | — | — |
| Nominate government | ✓ | — | — | — | — |
| Upgrade region | ✓ | ✓ | ✓ | — | — |
| Manage inventory | ✓ | ✓ | ✓ | ✓ | — |
| Manage mercenary contracts | ✓ | ✓ | ✓ | ✓ | — |
| Manage contract proposals | ✓ | ✓ | ✓ | ✓ | — |
| Pin article / message, post announcement | ✓ | ✓ | ✓ | ✓ | ✓ |
| Register country for tournaments | ✓ | ✓ | ✓ | — | — |

`[CONFLICT]` The wiki government page (2026-07-23) differs for the Minister of Defense: it lists *Manage Citizenship Applications* and
*Fund/Suppress Resistance* but **not** *Manage Country Inventory*. The guide (2026-09-30) is newer; verify in the UI when it matters.
Ministers cannot vote on laws; the President and VP vote with Congress `[WIKI-ONLY]`.

Consequences: four roles can set orders/open battles — decide internally **who** does it to avoid contradictory orders and wasted
paper; only President/VP handle citizenship; only the President nominates, so a mandate change blocks other roles until
appointments; tournament registration needs President, VP or MoD active before Friday 18:00 UTC; Finance manages inventory and
contracts but can't set orders, Foreign Affairs can set orders but has no inventory access.

Live config: president wage 3%, member wage 1% (`government.presidentWagePercent`, `memberWagePercent`; base `[GAP]`);
renomination cooldown 5 days; resistance raise/lower cooldowns 6 h / 3 h (`government.resistanceIncreased/DecreasedCooldownInHours`,
semantics `[GAP]`).

## Inactivity and takeover `[RULE]` / `[CONFLICT]`

- **Takeover** `[WIKI-ONLY]` (conditions): possible when the President is inactive and the country has **no ministers and no congress members**
  (inactivity flag: 3 days). Impeaching the President does not open takeover while congress exists. Players in any government must
  resign first; the 30-day citizenship cooldown doesn't apply. The UI warns that abusing it for another country leads to a ban.
- Live: takeover min level **25**, cooldown **1 day**. `[VERSIONED]` The guide's "5 days per user" was the rule from v0.15.0 (2025-05-01).
- Fanatic Imperialist countries can't have a Vice President or ministers (+30% tax income, +50% region upgrade upkeep). Until
  v0.27; from v0.27 an **Autocracy** has **no congress and no ministers** (the President and VP vote laws), and switching to it
  fires the ministers at once ([government-types.md](government-types.md)). *Derived:* with no ministers and no congress, an
  Autocracy may meet the takeover condition as soon as its President is inactive (whether an active VP blocks it isn't stated `[GAP]`).
- `[POLICY-RO]` Keep several active people in government and congress; announce multi-day absences; delegate duties; check
  members' activity periodically; never leave the country without active people in key posts.

## Leadership principles `[POLICY-RO]`

Share relevant diplomatic/military/economic information in a common decision-makers' channel · civil tone, confidentiality,
Romania's interest first · President and VP with complementary hours; in war, military leadership covers night/morning ·
orders with short measurable descriptions, a clear rank and an owner for updates/cancellation · announce absences and delegate
· mandate handover includes channel access, financial and diplomatic status and ongoing commitments.

Checklists (in-battle, handover, pre-tournament): [strategy-guidelines.md](strategy-guidelines.md).
