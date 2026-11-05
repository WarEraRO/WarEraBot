# Versioned mechanics — schema and current history

## Why

Patch notes are an **event log**; this skill keeps a **derived state with history** so it can answer both "what is X now?" and
"what was X on date D / in version V?". Values are never overwritten.

## Registry schema (`data/mechanics.yaml`)

```yaml
- id: bonus.alliance                 # stable dotted id; ro.* = strategy/policy, obs.* = observations
  name: Alliance damage bonus
  category: combat_bonus
  authority: game_mechanic           # game_mechanic | community_strategy | romanian_policy | community_observation
  unit: percent
  config_path: battle.allianceDamagesBonusPercent   # optional live config path
  refs: [references/alliances.md]
  values:                            # history, oldest first
    - value: ...                     # scalar, list or map
      status: historical             # current | disputed | scheduled | historical | deprecated
      introduced_in: v0.24.0         # optional game versions
      changed_in: v0.25.5
      deprecated_in: null
      effective_from: "2026-08-01T00:00:00Z"   # optional, UTC; omit if unknown - never guess
      effective_to:   "2026-09-01T00:00:00Z"
      first_observed: "2026-10-04"   # when a value was first seen (not the change date)
      last_verified: "2026-10-04"
      source: [GUIDE, LIVECFG]       # ids from the sources list
      confidence: high               # high | medium | low
      notes: "..."
  conflicts:                         # disagreeing sources (required when status: disputed)
    - {source: LIVECFG, value: 10, note: "..."}
```

Field mapping to the requested concept: `value, unit, status, introduced_in, changed_in, effective_from, deprecated_in,
last_verified, source, confidence, notes` all exist per value entry; `id/name/category` per mechanic.

## Resolution rules (`scripts/wlib.py resolve`)

1. Active entries (`current`, `disputed`) without `effective_from` start where the latest closed historical window ends.
2. `scheduled` entries apply only once `effective_from` has passed — so a change announced for 1 September answers "25 August →
   old value, 5 September → new value".
3. `historical`/`deprecated` entries apply only inside a known window.
4. If an older value exists without dates, any date before the current entry's `first_observed`/`last_verified` is flagged
   **uncertain** instead of silently using today's value.
5. `disputed` values always return a warning listing the alternatives.
6. Validator (`validate_mechanics.py`): one active value per instant, no overlapping windows, scheduled needs a date, unknown
   sources rejected.

## Sources (priority)

| ID | Source | Date | Priority |
|---|---|---|---|
| LIVECFG | live `gameConfig` snapshot (warera-config skill) | 2026-10-04 | 1 (trusted script output) |
| GUIDE | Romanian complete guide v0.26.1 | 2026-09-30 | 4 (latest guide) |
| WIKIPATCH | official patch notes v0.0.2 → v0.17.7 (via warera.wiki) | 2025-10-04 | 2 |
| WIKI | warera.wiki pages (per-page dates) — **outdated**, gap-filler only | 2026-10-05 | 6 |
| WIKICFG | warera.realmarijn.nl game-config (data 2026-09-15) | 2026-09-15 | 5 |
| ADMIN_PATCHES | official articles by the admin, v0.15.0 → v0.26.1 + dated announcements (IDs in `data/patch-history.yaml`) | 2026-09-17 | 2 |
| PATCH_0_25_1 | article `6a2d86d5ab0e47773095df00` "v.0.25.1-beta", by a staff member (no admin article exists for v0.25.1) | 2026-06-14 | 2 |
| PATCH_0_26_2 | admin article `6accd48eca2ce961eea235ff` (civil-war patch; v0.26.2 is the user's label) | 2026-10-14 | 2 |
| PATCH_0_27 | admin article `6ade08f7899288ce9f0bfe36` "v0.27" (deploy announced for 2026-10-26 ~14:00 UTC; publishedAt 2026-10-28) | 2026-10-25 | 2 |
| PATCH_0_27_1 | admin article `6ae0defd260ab3cd58036d7a` "v0.27.1" | 2026-10-27 | 2 |
| PATCH_0_27_2 | admin article `6ae2608f707baf45eebf26c5` "v0.27.2" (income ×2, starting money 100, 32 trait pairs) | 2026-10-28 | 2 |
| LIVECFG_V0272, LIVEAPI_20261029 | live config + client, and a live API sample, after v0.27.2 | 2026-10-29 | 1 |
| PATCH_0_27_3 | admin article `6ae39f39b9d173140341a461` "v0.27.3" (Leadership → Management, Responsibility +3 happiness, hiring and trait changes) | 2026-10-29 | 2 |
| LIVECLIENT_V0273, LIVEAPI_20261030 | live client + config, and a roster sample, after v0.27.3 | 2026-10-30 | 1 |
| SILENT_20261031 | community article `6ae682c7470184738824c070` reporting the silent patch of 2026-10-31 (Trainer, Lucky charm) | 2026-11-01 | 7 |
| LIVECLIENT_20261101, LIVEAPI_20261101 | live client + UI catalog history, and a roster sample, after the silent patch (also dates the toolbox-cap removal to 2026-10-29) | 2026-11-01 | 1 |
| PATCH_0_27_4 | admin article `6ae8bb12bcc26a2f5712ec9d` "v0.27.4 + New skins giveaway" (ageing per worked day, disabled companies on hold, Talks to Machines, training cards, event rebalance, crafting 7, new-country voting) | 2026-11-02 | 2 |
| LIVECLIENT_V0274, LIVEAPI_20261102 | live client + config + UI catalog 4838d69, and 70 rosters, after v0.27.4 (paid wages still exclude trait Production) | 2026-11-02 | 1 |

Patch coverage: **every version from v0.0.2 to v0.27.4 is logged** in `data/patch-history.yaml` (WIKIPATCH to v0.17.7, then the
official in-game articles, read in full 2026-10-25). Only **v0.19.1** has no article. A **newer patch overrides an older one** where
they overlap (user rule 2026-10-25): derive a mechanic's value from the newest entry that touches it, and check later patches before
calling an older patch's rule current (e.g. v0.25.1 turned mission auto-claim on, v0.25.5 turned it off). Some values still changed
with no article (U-HIST-4: Sworn Enemy upkeep ×2 → ×10, vote level 10 → 15 → 20, takeover level 15 → 25, auction step
0.05 → 0.01); those keep an unknown date.

## Known version history (what the sources actually establish)

| Mechanic | Before | Now | When | Evidence |
|---|---|---|---|---|
| `election.vote_min_level` | 15 | **20** (+7 days since citizenship change) | between 2026-09-15 and 2026-10-04 (exact date unknown) | guide + wiki vs live |
| `bonus.patriotic` | none → **10** (2026-02-13, v0.23.0) | **20** | 2026-08-29 (v0.25.5) | admin articles |
| `production.deposit_bonus` | fixed 30 | random 20–40 per deposit | 2026-08-29 (v0.25.5) | admin article + guide |
| `bonus.alliance` | flat +10 → +10 up to 15% WD (2026-06-10, v0.25.0) | WD curve (+20 → −20) | 2026-09-01 (announced in v0.25.5) | admin articles |
| Map/travel | hit any battle from anywhere | position + Stamina/oil travel | 2026-09-16 (v0.26.0); Stamina-then-oil 2026-09-17 (v0.26.1) | admin articles |
| Map/travel (v0.28) | position + Stamina/oil travel | hit from anywhere (2026-11-03); movement, Stamina, map wooden cases, free trip home and the two map milestones off ~2026-11-10 (scheduled) | 2026-11-03 / ~11-10 | admin article `6aea1496b615c31fa0eb4152`, live config |
| Travel missions | measured in km | measured in regions crossed | before v0.26.1 | guide |
| Order list | ordered by age | ranked #1…#99, renumbered | 2026-08-19 (v0.25.3) | admin article |
| Build tool | intel.warera.wiki/builder | SpyWarEra Build Optimizer | before v0.26.1 | guide (tooling, not mechanic) |
| Contract auction step/min | 0.05, last 30 s +30 s (2026-04-25, v0.24.4) | 0.01, 60/60 (live) | after 2026-04-25, date unknown | admin article vs live config |
| Beginner missions | screenshots 14 → 20 missions | 25 missions (level ladder 5/10/15/20/25) | 2026-08-29 (v0.25.5) | admin article + guide screenshots |
| Mission claiming | by hand → auto (2026-06-14, v0.25.1) | by hand again | 2026-08-29 (v0.25.5) | articles |
| Tax hijack by resistance | 1%/point → % of tax and development, max 40% (2026-02-13) | removed | 2026-06-14 (v0.25.1) | article |
| Break Room | L1–L5, 2–10 workers | removed (Management caps workers) | 2026-01-09 (v0.22.0) | admin article |
| Deposits | −0.5%/h of the quantity, every 12 h | 1–5 days, hourly 10% roll | 2026-01-09 (v0.22.0/v0.22.1) | admin articles |
| Alliance leave cooldown | temporarily disabled until 2026-09-03 | 7 days active | 2026-09-03 | live config |
| Civil wars (`unrest.civil_war`, `bonus.bunker`) | government side gets country order, bunker, bounty | no bounties, no country orders, no bunker | 2026-10-14 (publishedAt; patched 10-11..13) | v0.26.2 article |

Dated history from the patch log (resolvable with `--as-of`): Pill (buff 80 → 60 on 2025-12-26, debuff 16 → 15.5 h on 2026-06-14),
deposit bonus (20 → 30 → random 20–40) and duration, unlinked-region malus (−10 → −15 → −25), occupier malus (−30 → −50 on
2026-02-13), respec cost/cooldown, inactivity (7 → 3 days), takeover (cooldown 3 → 5 days, min level 3 → 15), citizenship cooldown
(5 → 30 days), MU help, max tax, congress seats, election calendar, vote and candidacy levels (5/0 → 15 → 10), miss damage, loot
(ranking pool 3 → 2.5% → removed), patriotic, alliance, bunker/base, armor formula, food, bounties, strategic resources,
Management, tax hijack, order costs, civil-war cost, tournaments. Full log: `data/patch-history.yaml`; summary tables in
[deprecated-mechanics.md](deprecated-mechanics.md).

No scheduled changes are pending. **v0.27** went live on 2026-10-26 (`effective_from` **2026-10-26T14:00:00Z**, the article's stated
deploy time; publishedAt 2026-10-28). On 2026-10-26 the live config was checked (`LIVECFG_V027`) and the registry flipped: 41
`scheduled` entries became `current`, 25 closed entries `historical`. 23 of them carry `last_verified` 2026-10-26 because the live
config or client shows the value; the other 18 (government types, combat bonuses by type, strategic-resource income, starting bag,
daily calendar, wooden cases, party rules, taxes …) rest on the article alone, which the validator flags as "active value without
last_verified". Confirm those from tooltips as they come up. Strategic-resource income was verified live on 2026-10-29 (after
v0.27.2 doubled it); the starting bag is still article-only. `bounty.rules` gained an unannounced v0.27 entry (cap now
`maxBountyPpMultiplier` 9).

## Answering historical questions

- "What was the alliance bonus before v0.25.5?" → +10% up to 15% WD, −0.5/pt, floor 0, from v0.25.0 (2026-06-10) until
  2026-09-01 00:00 UTC, when the v0.25.5 curve took over (announced 2026-08-29). Before 2026-06-10: the old flat ally bonus (+10%).
- "What was the Pill debuff on 2025-09-01?" → 24 h (pre-v0.17.7) — a dated answer.
- "What applied on 20 August 2026?" → for mechanics with only undated history, say the value is uncertain; give the current value
  with its verification date.
- "What changed between two versions?" → list entries whose `changed_in`/windows fall between them; today only the table above.
