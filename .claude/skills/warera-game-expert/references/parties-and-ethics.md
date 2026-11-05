# Political parties and ethics

> **v0.27 (live since 2026-10-26): party ethics are removed** and replaced by the country's
> **government type** ([government-types.md](government-types.md)). Parties also **can no longer start a resistance**; pending
> motions to do it fail at no cost. Parties appear in the menu at **level 15** (existing members keep access), and the admin says
> they "will be reworked in the next patches" (menu gate confirmed: `featureUnlockLevels.party` 15). The **Ethics** section below is history `[DEPRECATED]`: use it
> to read older guides, never as a current rule. The article doesn't mention party elections or the Start Revolution motion, so
> those are assumed unchanged `[GAP]`.

Verification legend for this page: `[GUIDE]` confirmed by the Romanian guide v0.26.1; `[LIVE]` confirmed by live config;
`[WIKI-ONLY]` from warera.wiki, which is **outdated** — present these as unverified and check the in-game ethics screen.

## Parties

- Creating a party costs **150** `[LIVE]` (unit not stated; wiki says concrete). The founder picks one of the country's core
  regions as party headquarters, a name and an avatar `[WIKI-ONLY]`.
- The ruling party's ethics apply to the country while **one of its members is President** `[WIKI-ONLY]`; the guide speaks of
  "the ruling party's ethic" `[GUIDE]`.
- Each party has **3 ethic points**: 1 point = the small version of an ethic, 2 points on the same ethic = its **Fanatic** version;
  **Unethical** takes all 3 points `[GUIDE confirms Unethical uses all points; rest WIKI-ONLY]`.
- Ethic change cooldown: **14 days** `[GUIDE]` (Set Party Ethics motion `[WIKI-ONLY]`).
- Party elections each month: council, leader, primary (presidential candidate). Dates: guide 12–13 / 22–23 / 24–25; the outdated
  wiki says 16th / 21st / 27th — use the guide and live dates ([congress-and-laws.md](congress-and-laws.md)).
- Roles `[WIKI-ONLY]`: the leader can kick members and remove council members (not the primary winner); the council votes party
  motions by majority. Motions: Remove Council Member, Launch Council/Leader/Primary Election, Impeach Party Leader,
  **Start Revolution** (civil war, see [resistance-and-internal-conflicts.md](resistance-and-internal-conflicts.md)),
  **Finance Local Resistance**, Set Party Ethics. From v0.27, Set Party Ethics is gone and parties can't start a resistance
  (presumably the Finance Local Resistance motion `[Unverified]`; the article doesn't name the motion).
- Joining a party is a beginner mission `[GUIDE]`.

## Ethics `[DEPRECATED from v0.27]` — rules until 2026-10-26

| Ethic (Fanatic version unless noted) | Effects | Verification |
|---|---|---|
| **Unethical** (3 points) | National orders give **double the priority bonus** (+10/+20/+30%) at **double paper**; no treaties (alliance, Sworn Enemy, Defensive Pact); if the capital is occupied, national orders return to their normal bonus and a full-resistance revolt starts automatically in the capital | `[GUIDE]` bonus/cost/treaties and the capital-occupied +15% case; `[WIKI-ONLY]` the automatic revolt |
| **Fanatic Expansionist** | Military bases can be up/downgraded every **2 h** (instead of 8); +3% per Pacification Center level when defending a revolt in a region you occupy; occupied regions generate **double** resistance | `[GUIDE]` |
| **Fanatic Pacifist** | Orders defending core regions and revolts are **free**; when revolting you **copy the enemy bunker bonus**; no Sworn Enemy | `[GUIDE]` |
| **Isolationist / Fanatic Isolationist** | Sworn Enemy bonus builds faster (+5%/day; wiki: starts at +5%); orders against the Sworn Enemy −50% paper; all treaty upkeep +50% | `[GUIDE]` acceleration; `[WIKI-ONLY]` the rest |
| **Diplomatic / Fanatic Diplomatic** | Defensive Pact upkeep −50%; orders supporting a pact partner −50%; Sworn Enemy upkeep +100% | `[GUIDE]` cheaper pact upkeep; `[WIKI-ONLY]` the rest |
| **Expansionist** (small) | region building cooldown 4 h | `[GUIDE]` (cooldown table) |
| **Fanatic Industrialist** | +30% production for **ammo or construction** specialization goods; deposits can't spawn in your borders | `[GUIDE]` "ethic up to +30% for the specialization"; `[WIKI-ONLY]` name and details |
| **Fanatic Agrarian** | +30% on grain/livestock/fish deposits; only food deposits spawn; no specialization | `[WIKI-ONLY]` |
| **Imperialist / Fanatic Imperialist** | +10% / +30% tax income; Fanatic: no Vice President or ministers, region upgrade upkeep +50% | `[WIKI-ONLY]` |
| **Republican / Fanatic Republican** | +50% / +150% development income; Fanatic: only core regions earn development income | `[WIKI-ONLY]` |

Non-fanatic versions other than those listed are not documented in any source `[GAP]`.

## Strategy `[STRAT-RO]` (pre-v0.27; for government types see [government-types.md](government-types.md))

Fanatic Expansionist suits a country holding foreign territory; Fanatic Pacifist suits one recovering its core regions (free
orders save paper in long revolt campaigns, copying the bunker cancels the occupier's defensive edge) but gives up the Sworn
Enemy +10%. Because an ethic change has a 14-day cooldown and can break treaties, treat it as a strategic decision for the government and
Congress, not a tactical switch.
