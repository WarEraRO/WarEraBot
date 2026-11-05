# Romanian community operations (Discord, TheMachine, mobilization)

Everything here is `[POLICY-RO]` or `[STRAT-RO]`: community organization, not game mechanics. Channel names can change.

## Why Discord matters

Real-time orders and damage pings; Pill coordination with decisive moments and building activations; travel coordination
(where to stand, when travel is worth it); preventing diplomatic mistakes (NAP tracking, bot violation reports); economic
efficiency (jobs, workers, trade, production bonuses, company-move orders); mentoring; automation; governance history.
> Discord is the operational layer of the game: it syncs dozens of players, reduces consumable waste, prevents treaty breaches,
> distributes bounties and contracts fast, tracks buffs, and links government, MUs and citizens.

## Access and conduct

Read #discord-info; post a screenshot of your in-game profile in #identify-yourself to get roles; one Discord account per game
identity (re-verify via an admin if you switch); respect channel purposes, no spam/flood/abusive mentions; don't leak government,
congress, MU or negotiation content; never damage Romania, allies or NAP-protected partners without explicit authorization.
Operational rule: read the order description and #battle-orders before using a Pill, emptying Health/Hunger, or spending
Stamina/oil on travel (travel stopped mattering for fighting with v0.28, 2026-11-03).

## Server structure (purpose)

| Area | Channels |
|---|---|
| Public | #public-chat, #discord-info, #identify-yourself, #tourists-in-romania, #public-unsafe-chat |
| RO Information Center | #rules, #anunturi-oficiale-warera (official game news), #monitorul-oficial (wars, NAPs, deals, tops, fight/eco coordination), #ghidul-incepatorului, #ghiduri-tools-tutoriale |
| RO MUs | #mu-commanders (role synced by bot), #mu-enrollment, per-MU channels (roles by in-game membership) |
| RO Economy | #economic-orders (urgent: company moves, production, stocks), #business-school, #job-market, #trading-market |
| RO Military | #battle-orders, #coordonare-fighters (fight build only), #strategii-si-scheme (threads per proxy) |
| RO General | #ro-newbie-chat, #ro-chat, #recrutare-jucatori, #editura-romana, #forum-national, #electoral-zone, #dev-server (dev.warera.io) |
| Bots & Automation | #bot-commands, #bounty-monitor and #contract-monitor (fight build only) |
| Political | #government (private), #congress-chamber / #forum-congres, #council |
| Embassies | bilateral diplomatic channels |

## TheMachine slash commands (in #bot-commands)

| Command | Purpose / who |
|---|---|
| `/diplomacy [country]` | country diplomatic sheet or paged list; sensitive fields only for government roles |
| `/update_diplomacy`, `/add_diplomacy`, `/remove_diplomacy`, `/delete_diplomacy` | government: maintain diplomatic records |
| `/nap add`, `/nap remove`, `/nap list` | government: internal NAP list used by the battle monitor |
| `/priority list` | active priorities and descriptions |
| `/priority refresh`, `add link description`, `set n description`, `move a b`, `remove n` | government: manage the bot's priority monitor |
| `/fightstatus [military_unit]` | fighters/MU members: buff/debuff, Health/Hunger, level, online, filters |
| `/country_strays` | citizens located/registered outside the country |
| `/discordless` | Romanian citizens not identified on Discord |
| `/inactive_players` | players inactive > 3 days |
| `/mu_stray` | wrong/missing MU roles, inactive members |
| `/promotions` | beginner promotion eligibility and build/data issues |
| `/top_user_weekly_damages country` | top 10 weekly damage by level bracket |
| `/top_user_weekly_donations country` | top 10 donations since week start |
| `/get_region_upgrade_cost country` | daily oil consumption and market cost of active region upgrades |

Bot `/priority` ≠ in-game order rank (set on the Orders page) — keep them in sync.

## Automated jobs

| Job | Every | Role |
|---|---|---|
| skill_roles | 1 h | add/remove Economy and Fighter roles from in-game skills |
| military_unit_roles | 3 h | sync MU roles with in-game membership |
| commander_roles | 3 h | sync commander role with MU owners/commanders |
| unidentified_members | 6 h | map nicknames to WarEra users; report unidentified |
| takeover_countries | 5 min | flag apparently empty countries (takeover/proxy) |
| buff_monitor | 10 min | warn fighters when the Pill buff is about to expire |
| bounty_monitor | 1 min | track bounties/money pools |
| mercenary_contracts | 1 min | track contract auctions |
| monitor_nap | 1 h | check national and MU orders against NAPs |
| battle-order_monitor | 5 min | detect Romania's orders, update priorities, drop ended battles |
| reddit_monitor | 5 min | new posts on r/RomaniaWarEra |

The bot cuts reaction time but doesn't replace human judgment: confirm the order description, round state, active buildings and
government messages before heavy spending. (Bot implementation: this repository's `cogs/`; job list may differ from the guide.)

## Alert levels

The guide mentions **"Cod Galben/Portocaliu"** (Yellow/Orange code) at T-48h and "Cod Galben/Portocaliu or MU rotation" as respec
triggers. **Their definitions are not in the sources** `[GAP]` — never invent criteria; ask leadership.

## National war-preparation flow

| Time | Government / Congress | MUs | Citizens |
|---|---|---|---|
| T-7 to T-3 days | diplomacy, paper/oil, buildings, budget, laws, fronts; choose launch regions (for adjacency only since v0.28) | audit oil/paper, roster, commanders, possible contracts | save, buy consumables and oil, run the optimizer |
| T-48 h | Yellow/Orange code, #economic-orders, announcements, preliminary priorities, maybe Resistance Focus | activate HQ in time, sync orders | finalize gear and notifications; don't spend Stamina on cases |
| T-12 h | activate buildings, confirm treasury, bounty/contract plan | confirm oil, paper, member schedule | full Health/Hunger (until v0.27.4 also: **move to the battle region**); don't use the Pill early |
| T-1 h | final orders, rank #, descriptions, location; NAP check | MU orders aligned; loot targets split | join voice/chat; confirm Pill window |
| During | monitor ticks, budget, buildings, fronts | coordinate damage, help, contract, reports | hit only per orders; report lack of resources |
| After | report, costs, bounties, lessons | contract distribution, audit, HQ off when not needed | sell/recycle loot, prepare next cycle (incl. travel home) |

## Daily routine for a new player

Discord + verification → claim daily reward → missions (begin/daily/weekly/monthly), claim manually → Energy at best after-tax
job, Entrepreneurship in own companies → keep storage from filling (Produce) → points into economy until 15 → sell rare+ gear and
reinvest → wooden case in Stamina range (until ~2026-11-10, v0.28) → check #economic-orders before moving/switching.
