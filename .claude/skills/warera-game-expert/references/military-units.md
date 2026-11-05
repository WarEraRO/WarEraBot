# Military Units (MU)

Group structure providing its own orders, HQ damage bonus, Health help, internal chat, announcements, contracts and a shared
treasury `[RULE]`.

## Limits (`mu.limits`) `[RULE][LIVE]`

Create up to **3** MUs (cost 300 concrete; config states 300 without unit), but be a **member of only one**. Nationality change
cooldown 7 days. Member cap from Dormitories.

## Roles `[RULE]`

| Role | Rights |
|---|---|
| Owner | orders and their rank, upgrades, market, oil/paper, recruiting, accepting members, kick, promote commanders, contracts, announcements, tournament registration, treasury |
| Commander | most operational functions: orders and rank, market, accepting members, contracts, upgrades, announcements, tournament registration; not all ownership/recruiting actions |
| Member | fights under orders, donates, requests/gives help, contributes to ranking and contracts |

## Upgrades `[RULE][LIVE]`

| Upgrade | Level | Steel | Effect / cost |
|---|---|---|---|
| Headquarters | 1 | 100 | +5% damage; 1 oil/h |
| | 2 | 200 | +10%; 2 oil/h |
| | 3 | 300 | +15%; 5 oil/h |
| | 4 | 600 | +20%; 10 oil/h |
| Dormitories | 1 | free | 5 members |
| | 2 | 200 | 10 |
| | 3 | 300 | 15 |
| | 4 | 400 | 20 |
| | 5 | 500 | 25 |

HQ activates in **3 h + the time until the next hourly regen tick** (3–4 h; config pending 3 h, guide 3–4 h), **switches off automatically when the MU runs out of oil**. Schedule activation
before the war, not after the emergency. `[VERSIONED]` From v0.26.0 members also burned oil on travel; since v0.28 fighting needs no travel and movement ends ~2026-11-10, so
that demand is gone.
Daily HQ oil at L4 = 240 (F-HQ-OIL: `oil/h × hours active`).

## Help `[RULE][LIVE]`

A member can request help every **12 h**; **5** teammates give **2 Health** each (10 total) — since v0.17.6 (2025-09-04); asking again
removes previous asks. From v0.27 the helper also gets **+1 health** per help `[LIVE]` (`mu.helperHealthPerHelp` 1), and MUs appear in the menu at level 5
(members keep access). Free; helpers can help many
members (Milestone "Help __ MU members"). `[STRAT-RO]` Request during the Pill window and before a priority, not in debuff
without orders. `[OBS]` At 100/100 Health, help to 110/100 is cut back to max at the next regen — use the surplus first.

## Orders

Paper scales with members (guide); wiki formula base (5/10/20) × max(1, floor(members / 5)) `[WIKI-ONLY]`; bonuses +5/+10/+15%; own rank list (#1…) separate from the
country's. `[POLICY-RO]` MU orders must copy the national objective.

## Recruitment, location, account `[WIKI-ONLY]`

Owner/commanders post recruitment offers (description, **entry fee** paid on acceptance, minimum level). MU location is set at
creation and is **purely symbolic**. The MU account receives donations, entry fees and trading profit, and pays orders and HQ oil.
More members = more help availability and the same HQ cost spread over more fighters.

## Treasury `[RULE]` / `[STRAT-RO]`

- Income: donations, entry fees, trading, contracts, sales. Main costs: HQ oil, order paper, contract acceptance fee (10%).
- Paying an MU cost checks the **MU inventory**; if short, the market opens for the MU wallet pre-filled with the missing amount.
- Don't put the war chest into illiquid items without members'/commanders' approval.

## Recruiting and administration `[POLICY-RO]`

- Recruit via #mu-enrollment; Discord MU roles are synced by the bot every 3 h; check inactive/mismatched members with `/mu_stray`.
- MU announcements (2/h, 1,000 chars, 24 h): good for mobilizations and tournaments; keep them **short** — long announcements
  push the help buttons down.

## Commander duties and transparency `[POLICY-RO]`

Publish a simple budget: oil stock, paper stock, HQ cost/hour, days of autonomy. Rank MU orders consistent with national #1
and announce the fighting region. After each fight: audit contract payout, donations, oil, paper and HQ state.

Checklist: roster and roles synced, active commanders · oil for the whole HQ window · paper for planned order and upgrade ·
MU order/rank = national priority · members know side, region, round, threshold, timing · contract verified (budget, damage,
duration, fee, reputation, conflict of interest) · loot targets split · short announcement · tournament registration before
Friday 18:00 UTC · post-fight audit.
