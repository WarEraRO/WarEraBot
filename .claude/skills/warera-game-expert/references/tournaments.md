# Country and MU tournaments

Recurring events; only **registered** participants enter the bracket `[RULE]`.

## Calendar and registration (`tournament.schedule`) `[RULE]`

| Element | Rule |
|---|---|
| Frequency | one tournament every two weeks, **alternating MU and Country editions** |
| Registration opens | Monday 00:00 UTC |
| Registration closes | **Friday 18:00 UTC** — bracket drawn, round 1 starts |
| Rest of bracket | played over the weekend |
| Participants | only registered MUs/countries; an unregistered country does not appear at all |
| Location | tournament battles are fought from anywhere (no travel) |

## Who can register / withdraw `[RULE]`

- **MU**: owner and commanders.
- **Country**: any government role with *Register the country for tournaments* — **President, Vice President, Minister of
  Defense**. If the country has **no government at all**, the owner or a commander of an MU of that country can register it.
- **Withdrawal**: possible while registration is open, same permissions.

During registration the page shows a countdown, the edition's **skill bonus** and **max rarity**, the register/withdraw button and
the list of registrants. Tournament cards show edition type and number registered.

## Bracket and cancellation `[RULE]`

- Fewer than **2** registrations at start time → tournament **cancelled** (with notification), not started.
- An MU that registers and then has **no members** is eliminated (no walkover wins).
- "Cancelled" state appears on the tournament page, list and events card.
- `[OBS]` The bracket is cut to a **power of two** with a qualifying round: in the MU edition seen on 2026-05-17 (guide
  `6a09d4b6d31b5748ed0626f2`, "Where is my tournament?"), 770 registered MUs played 258 qualifying battles, so 770 − 258 = 512
  went on and the other 254 MUs went straight to round 2. If your MU "fights in round 2", it drew a bye; refresh the page to see
  its battle. One edition's numbers; the rule is inferred from them, not stated by an official source.
- `[OBS]` A guide of 2026-03-24 (`69c2f50b7dbad462e91c9e39`, "Tournament basic guide") says that in an **MU** tournament only
  MU orders count and in a **country** tournament only country orders. Not confirmed by another source `[Unverified]`. The same
  guide describes registration as automatic, which the registration rules above (2026-09-30 guide) have superseded.

## Rarity cap and qualification `[RULE]`

- The **skill bonus** is flat Attack: **+25 Attack per bonus level**, reported as `skills.attack.tournament` and added to the flat
  part before ammo, Pill and rank multiply `[CODEX]` (its engine reproduces profile Attack totals with it). Not a percentage.
- Each edition announces a skill bonus and a **maximum equipment rarity**. Enforced server-side: a hit with weapon, **ammo** or
  equipment above the cap is **refused**. The check uses the gear you actually hit with — swapping mid-hit doesn't bypass it.
  The cap is shown in the tournament header and registration panel.
- **Qualification battles are exempt** from the rarity cap. The cap applies from the first bracket round, so a rule change
  mid-tournament doesn't invalidate a played qualifier.

`[STRAT-RO]` Build a separate set that respects the cap and save it as a set; disable/check auto-equip so it doesn't pull an
over-cap piece; check ammo rarity too; run the optimizer with the allowed gear and the edition's skill bonus.

## Government checklist `[POLICY-RO]`

Edition type and dates known · registered by an authorized role before Friday 18:00 UTC (if none of President/VP/MoD is
active, the country misses the edition) · skill bonus and max rarity announced (in-game + Discord) · fighters have compliant
gear and ammo · plan for qualifiers (exempt) and weekend rounds · if not participating, withdraw before registration closes.

Winners receive `countryTournamentWinner` / `muTournamentWinner` badges (reward 50, per live config).
