# Congress, laws and elections

## Congress seats (F-SEATS) `[RULE]`

```
seats = clamp( ceil(active_population / 20) + 2 , 5 , 50 )
```
130 active → 7 + 2 = **9**; 40 active → 4 → minimum **5**. Computed for the next elections.
`python scripts/progression_calculator.py seats --active 130`.

## Eligibility `[VERSIONED]`

| | Guide v0.26.1 | Live 2026-10-04 |
|---|---|---|
| Vote | level 15 | **level 20**, and ≥ 7 days since citizenship change (wiki agrees); since v0.27.4 no wait for new citizens during a new country's first 14 days |
| Candidacy | level 15 | **15** (re-checked 2026-10-05) — the outdated wiki says 20; ignore. **v0.27 (2026-10-26): level 20**, the same as voting |

Vote history: 5 (v0.15.8, 2025-05-28) → 15 (date unknown) → 20 (observed 2026-10-04). Ties: the candidate who registered first wins.
Beginner mission "Vote in an election" therefore needs level 20 now. Milestone XP banking can push a level up overnight `[OBS]`.

## Election calendar `[CONFLICT]` — always read `gameConfig.getDates`

| Election | Working stance | Source |
|---|---|---|
| Presidential | starts the **1st** (24 h candidacy, 24 h vote) | live getDates + guide |
| Congress | starts the **5th** | live getDates (guide says candidacy 3rd / vote 4th — overridden) |
| Party council | candidacy 12th, vote 13th | guide |
| Party leader | candidacy 22nd, vote 23rd | guide |
| Party presidential candidate | candidacy 24th, vote 25th | guide |

The outdated wiki lists party elections on the 16th/21st/27th and candidacy at level 20 — not used.
History: presidential was on the 4th before v0.15.13 (2025-06-15). Early elections can be called by law (20 coins).
v0.27 fix: an election with **no candidates keeps the current president**. An **Autocracy** has no congress, so its congress
election presumably doesn't run `[Derived]`.

`[POLICY-RO]` Announce candidacies in #electoral-zone before registration day, not in the last hours. Presidential candidates
must first win their party's nomination (24–25 of the previous month).

## Laws `[RULE]` — 24 h and ratio 0.5 `[LIVE]`; voter list, tie rules and law list `[WIKI-ONLY]`

- Voters: the President, the Vice President (one VP vote per law) and Congress members; ministers can't vote. Inactive/banned
  members aren't counted.
- A law stays open **24 h** and needs a **simple majority of all eligible voters** (`votersRatioNeeded` 0.5); with no majority the
  option with most votes wins; a draw denies the law. Example: 5 congress + President + VP = 7 → 4 votes.
- Law list: **Military** — Declare War (one-sided; initiator gets 24 h "priority"), Propose/Accept Peace (then 72 h non-aggression),
  Define Sworn Enemy, Propose/Break Defensive Pact, Remove Enemy. **Economic** — Change Tax (income tax 1–45% on wages paid in your
  regions; market tax on equipment bought by your citizens), Transfer Money (one-sided; receiving country needs 5 active eligible law
  voters; paper pays a transfer tax), Set Specialization Item.
  **v0.27** `[RULE]`: the income tax applies to **employee wages**, plus a new **manager tax** on manager pay (starts at the
  income tax); Congress votes both. Set Specialization Item goes (specialization removed). A new law picks the **government type**
  (30-day cooldown after the first pick). Plutocracies can't send money to another country. In an **Autocracy** only the President
  and VP vote laws. **Political** — Start Presidential/Congress Election (20 coins each),
  Impeach President (removes the whole government; seat empty until the next election), Impeach Congress Member (target's last
  login > 4 days), Create/Leave Alliance, Propose to Buy Region (both countries ≥ 5 eligible active voters; triggers an acceptance
  law), Liberate a Region, Set Welcome Article, Set Country Color, Set Discord Link.
- Region transfer/liberation is blocked while at war with the target (v0.17.6); "Accept region transfer" costs 50 money to enact (v0.17.7).
- Abusive laws: `abusiveLawPossibleVotersNeeded` 5, `abusiveLawsCooldownInDays` 3 `[LIVE]` — semantics `[GAP]`.
- Paper funds laws, orders, motions, treaties and diplomatic upkeep. Known config costs: create alliance 20 (upkeep 1), define
  enemy 10 (upkeep 3), set colour scheme 5, leave/accept alliance 0 — unit unstated.
- Region transfer/liberation law: 12 h between proposals. Specialization law: 10-day change cooldown.
- Sending money to a country: live `law.sendMoneyToCountry` has `allianceTaxRate` 0.5 and `externalTaxRate` 1 (semantics `[GAP]`).
- Party creation costs 150 `[LIVE]`.

`[GAP]` still: paper cost of each individual law; citizenship-application procedure details.
Seats history: fixed 10 → `2 + active/10` (2025-06-15) → `2 + active/20` (2025-06-18) → current clamp with minimum 5. Active
population counts only level ≥ 3 players (v0.16.13).

## Renomination

Re-appointment to government is blocked **5 days** after leaving/dismissal. `[OBS]` Leaving one country's government and
running for president in another has no cooldown.
