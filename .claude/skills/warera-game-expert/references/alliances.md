# Alliances

## Rules `[RULE]`

- A country belongs to **one** alliance. Creating one is a law (`create_alliance` cost 20, upkeep 1 per live config; unit
  unstated `[GAP]`).
- Each member pays **daily paper upkeep**; non-payment suspends the bonus until the next successful payment.
- Members of the same alliance **cannot attack each other**. To attack a member: leave the alliance, break any Defensive Pact
  with that country, and declare war. If not in the same alliance, breaking the pact plus declaring war suffices `[OBS]`.
- A country can't be re-invited while at war with any member.
- Leaving, being kicked or the alliance dissolving → **7 days** without any alliance; rejoining the **same** alliance → **14
  days**; **72 h** automatic non-aggression after the break. `[LIVE]` The 7-day cooldown is **suspended until 2026-10-30 00:00 UTC**
  (`alliance.leaveCooldownDisabledUntil`, seen in the config of 2026-10-26; not announced, most likely so countries can leave
  alliances for the v0.27 government types that forbid them). (Earlier: `alliance.leaveCooldownDisabledUntil` = 2026-09-03 — a
  temporary suspension of the 7-day cooldown that has ended.)
- Announce changes to citizens and immediately align orders and the bot's NAP list.

## Alliance bonus and world development (`bonus.alliance`) `[CONFLICT]`

Guide v0.26.1:

| Parameter | Value |
|---|---|
| Full bonus | +20% |
| Full bonus kept while alliance share of world development ≤ | 10% |
| Reduction per percentage point above | −4 points |
| Floor | −20% |

`bonus = 20 if share ≤ 10 else max(−20, 20 − 4·(share − 10))` → 12% → **+12**, 14% → +4, 15% → **0**, ≥20% → **−20**.

Confirmed by the wiki alliance page (2026-09-03) and battle page (2026-08-28). Live config
`battle.allianceDamagesBonusPercent` = 10 is most likely the legacy value (U-CMB-3, low remaining risk).

**History** `[VERSIONED]` (dated by the admin's articles, U-HIST-3; the codex gives the same dates `[CODEX]`):
1. Flat **+10%** when fighting for an ally, 1 coin/day upkeep, with the bilateral allies list (wiki country page; = config key),
   until **v0.25.0** (2026-06-10).
2. **+10%** up to 15% of world development, −0.5 point per extra 1%, floor 0% (v0.25.0, 2026-06-10).
3. Current: +20% up to 10%, −4 per point, floor −20%, announced in v0.25.5 and **in force from 2026-09-01 00:00 UTC**. To let the
   map rearrange, the 7-day leave cooldown was lifted until 2026-09-03 (`leaveCooldownDisabledUntil`).

The bonus applies only when fighting **for an ally**, never in your own country's battles (I-4).

**How the share is measured** `[OBS]` (`[CODEX]`, 2026-08-27):
- The curve follows **named-alliance membership** (the entity you join and leave), not a country's bilateral allies list. The API
  carries both, and they differ: Germany's allies list covered 4 of its 16 alliance partners. Count members, not allies.
- The share counts **core development** (community-confirmed), so conquering territory doesn't move an alliance's share.

## Laws, leader, chat `[RULE]` — details `[WIKI-ONLY]`

- Create Alliance law: name 3–40 characters + colour; founding country's President becomes leader.
- Joining: the alliance passes **Invite Country**, the target passes **Accept Invite**. Alliance laws (Invite, Kick, Nominate Leader,
  Rename, Change Color, Dissolve) last 24 h and need **> 50% of member presidents**; no enactment cost.
- Private alliance chat for the leader and member presidents/vice presidents. Rankings by development, weekly/total damage, population.
- When the last member leaves, the alliance is **disbanded** permanently (name and date kept; removed from map and rankings).
- **Upkeep**: daily paper = floor(own average development + 50% of the alliance members' average development); members that can't
  pay are **suspended** (no bonus) until they pay. Fanatic Isolationist +50%; Unethical can't join alliances (ethics end with v0.27).
- **From v0.27** `[RULE]` (government types): **Nationalist State** and **Mercenary State** can't be in an alliance (choosing
  either makes the country leave at once); **Federation** pays half alliance upkeep and gets **+5%** when fighting for an ally.

`python scripts/combat_bonus_calculator.py --alliance-share 12 [--as-of DATE]`.

## Strategy `[STRAT-RO]`

- For Romania and allies, a **compact alliance under 10%** of world development can be worth more than a big one.
- Before accepting a member, MoFA computes the alliance's share **after** joining: a member taking it from 9% to 12% turns +20%
  into +12% for **everyone**.
- `[VERSIONED]` With paid travel (v0.26.0 → v0.27.4), small, geographically compact alliances were more effective. Since v0.28
  (2026-11-03) supporting a distant ally costs nothing extra, so the world-development curve is the main limit on alliance size *[Derived]*.
