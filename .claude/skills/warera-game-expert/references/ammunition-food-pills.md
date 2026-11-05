# Ammunition, food and the Pill

## Consumables `[RULE][LIVE]`

| Item | Effect | Notes |
|---|---|---|
| Light Ammo | +10% Attack | cheap hits; needs a compatible weapon |
| Ammo | +20% Attack | damage/cost compromise |
| Heavy Ammo | +40% Attack | priorities and builds where cost is justified; relatively less efficient with good gear `[STRAT-RO]` |
| Bread | +10% of max Health | 1 Hunger |
| Steak | +15% of max Health | 1 Hunger |
| Cooked Fish | +20% of max Health | 1 Hunger; efficient at high max Health |
| Pill | **+60% Attack for 8 h, then −60% for 15.5 h** `[LIVE]` (`items.cocain.flatStats`: `percentAttack`, `buffDurationHours`, `debuffDurationHours`); does not use Hunger `[WIKI-ONLY]` | back to normal ~23.5–24 h after use. History: 24 h/24 h until v0.17.7 (2025-10-04), then 8 h/16 h, now 8 h/15.5 h `[VERSIONED]` |

- The knife cannot use ammo.
- Pill, ammo and military rank bonuses **multiply** in the damage formula `[RULE~]`.
- Food choice: every food costs 1 Hunger regardless of type, so at high max Health the pricier % foods can be more efficient
  per Hunger point — compare **price per Health point restored** (`price / (pct × maxHealth)`).
- Daily needs and reserves come from the optimizer; add 10–20% reserve.
- Wooden cases can drop ammo, food and even Pills (small free supply).

## Pill usage `[STRAT-RO]`

Choose the 8-hour window around **your schedule and Romania's priorities** (e.g. 07–15, 14–22, 18–02, or an overnight
23–07 window).

**Minimal-time variant**
1. Start with full Health and Hunger, **in the region you must fight from**, after checking #battle-orders.
2. Activate the Pill only with a valid order or a clear window.
3. Empty stats according to the order.
4. Return before the buff expires and use stats/regens again.
Two or three logins (~30 min total) can have big impact with good timing.

**Active variant**
- Use 1–4 regens between key moments, avoiding overflow.
- Keep Health/Hunger for decisive ticks, round ends and bunker/base activation.
- Empty everything only on order when critical.
- Use MU help during the buff (10 extra Health → buffed damage).
- A Pill routine has **seven** refills in total; use most regens without missing the strategic moment.

`[VERSIONED]` Until v0.27.4 a common mistake was activating the Pill **before reaching the battle region**. Since v0.28
(2026-11-03) you hit from anywhere, so no travel delays the buff.

**Debuff (15.5 h)**: don't burn expensive gear; do economy, ordered resistance contribution, cheap missions, nearby wooden
cases (until ~2026-11-10), inventory prep; wait for regen before planning the next
window.

Pill phase check: `python scripts/combat_calculator.py pill --consumed-at 2026-10-05T08:00Z [--now ...]`.

## Pre-Pill checklist `[STRAT-RO]`

National/MU order exists, description read, battle rank known · already in the correct region · NAPs/relations respected ·
total bonus justifies the gear (alliance can be negative) · Health and Hunger full · time to return before the 8 h end ·
bunker/base/HQ active or about to activate · bounty active (not still in delay) · MU contract on the right side · MU help
requested at the right moment.
