# Resistance, revolts, unrest and civil war

## Resistance `[RULE]`

- The resistance bonus in a revolt depends on bar fill: full bar ≈ **+30% for citizens, +15% for allies** `[LIVE]`.
- Bar size `[LIVE]`: **region development × 100**. Contribution: **10 Health or 10 Energy** → **+2** points for citizens, **+1**
  for non-citizens (min level 15). `python scripts/country_calculator.py resistance-bar --region-dev D --current C`.
- `[OBS]` (guide): new citizens joining during a revolt raise the cap and lower the bonus → avoid recruitment campaigns during a
  revolt `[STRAT-RO]`. (This doesn't follow from the wiki's development-based bar formula; it may act through development.)
- After a revolt: the wiki says resistance is reset; patch v0.17.1 (2025-08-21) says a **lost** revolt halves it `[CONFLICT]`.
- Resistance bonus is halved for non-citizens (v0.17.7) → 30% citizens / 15% allies at full bar. Region max resistance 40 (was 30).
- Government (MoD per wiki) can fund/suppress resistance; parties have a "Finance Local Resistance" motion. **v0.27: a party can
  no longer start a resistance**; pending motions to do it fail at no cost.
- v0.27 government types: **Homeland Front** doubles players' **resistance contributions** in its occupied core regions (UI text
  and client `coreResistanceContributionMultiplier` 2, 2026-10-27 `[LIVE-CLIENT]`); **Mercenary State**'s occupied capital
  revolts on its own at full resistance (as Unethical's did); **Autocracy** builds unrest ×2 as fast. Fanatic Expansionist's double
  resistance and Fanatic Pacifist's bunker copy end with ethics.
- **Adding** resistance doesn't require being in the region `[OBS]`; **fighting** the resistance battle does.
- After a revolt, contribution has a **24 h** cooldown `[LIVE]`. Resistance battle cooldown 24 h `[LIVE]`.
- Resistance can be launched directly from the attack window.
- Fanatic Expansionist occupiers generate **double** resistance in occupied regions; Pacification Centers reduce growth.
- Live config: max resistance 40, contribution min level 15, contribution cost 10 (unit `[GAP]`), plus many growth/decay keys
  with undocumented semantics (`resistanceGrowthPercentMin/Max`, `resistanceDecayPercent`, `resistancePassiveGrowthPercent`, …).
  `[OBS]` A guide of 2026-04-15 (`69dedceec12b0f486f1f2d84`, "RESISTANCE", example Zurich 705/759) reads three of them the way
  their values suggest: an occupied region's bar **grows on its own by 0.1–0.35% per hour**, the rate within that range depending
  on the region's development (direction not stated), and once the region is back with its owner the bar **decays by 0.2% per
  hour**. Those are exactly `resistanceGrowthPercentMin` 0.1, `Max` 0.35 and `resistanceDecayPercent` 0.2, and its bar length
  (development 7.59 → 759) matches `resistanceBarMultiplier` 100. Treat it as an observation, not a confirmed formula: "%" of what
  (bar max or current value) isn't stated, and `resistancePassiveGrowthPercent` 0.08 and the `resistanceGrowthReduction` levels
  stay unexplained. The same guide's "+15% for citizens defending a core region" doesn't match the config (30% citizens / 15% allies
  of the revolting side), and its 40% tax hijack was removed in v0.25.1.

## Resistance Focus `[RULE]`

The government can point citizens at **one** lost region:
- one focus per country, on a previously held region, with a custom text explaining why; setting another replaces it;
- marked on the map; the call appears at the top of the battle list with a card linking to it;
- visible only to the country's own citizens;
- **only a signal**: it doesn't move resistance, change costs or add damage — like a battle order for a battle that hasn't started.

`[STRAT-RO]` Use it when there are no active battles, to concentrate contributions; the text should say why (capital link,
resource, buildings) and when the revolt is planned.

## Revolts, transfer and liberation `[RULE]`

- Revolts were fought from the disputed region (v0.26.0 → v0.27.4); since v0.28 (2026-11-03) fighters hit from anywhere `[VERSIONED]`.
- A country **cannot buy another country's capital** by law (capital transfer impossible).
- A country that doesn't hold its own capital **cannot buy other regions**.
- Transfer/liberation law: 12 h between proposals. Liberation after an owner change: 5-day window, then **24 h bilateral
  non-aggression** after liberation. (Live also has `region.transferDaysCooldown` 5 — semantics `[GAP]`.)

## Unrest and civil war (`unrest.*`) `[RULE][LIVE]`

- **Unrest** = internal political pressure shown as a bar. Citizens raise or lower it: each contribution costs **10 Energy or
  10 Health** and moves the bar 1 point (min level 15 `[LIVE]`).
- When the bar reaches 100%, **any party** (including the ruling one) can pass the **Start Revolution** party motion:

| Element | Value |
|---|---|
| Cost | country development × 10 `[GUIDE]` — live `unrest.battleStartCost` = 100 `[CONFLICT]` (U-POL-3) |
| Motion cooldown | 48 h |
| Battle location | the capital |
| Participants | citizens only |
| After a revolution | unrest contribution locked 72 h |

- **No bounties, no country orders, no bunker** `[VERSIONED]` (v0.26.2, admin article `6accd48eca2ce961eea235ff`, published
  2026-10-14, patched a day or so earlier): bounties can't be placed on a civil war, country orders can't be set on it, and the
  capital's bunker doesn't count for either side. **Before** (guide v0.26.1) the government side got the country order, the bunker
  bonus and any bounty/contract, and the side that started the civil war got none of these. History: `unrest.civil_war`, `bonus.bunker`.
- Not covered by the patch `[GAP]`: MU orders, mercenary contracts, MU HQ. Check the battle tooltip before relying on them.
- *Derived from the patch:* the government's built-in edge (treasury-funded orders and bounties, a bunker in the capital) is
  gone. A civil war is now decided by the raw damage of the citizens on each side, plus whatever the `[GAP]` sources still add.
- If revolutionaries win: government impeached, **borders open 7 days** (citizenship applications auto-accepted), presidential
  elections start immediately. If the government wins: the unrest bar resets to 0.

`[STRAT-RO]` Government: watch the unrest bar like the treasury — steady growth signals an unsolved political problem; the
cost (development × 10) won't deter an organized group; loyal citizens can lower it at the same cost, so an early public call
is cheaper than a battle in the capital (but it consumes Energy/Health needed for economy and combat). Citizens: check
leadership's position before contributing; 7 days of open borders can be exploited by other countries.
