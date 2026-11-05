# Mercenary contracts (reverse auctions for MUs)

A country posts a damage objective and budget; MUs compete by bidding a **lower rate per 1,000 damage** `[RULE]`.

## Auction (`contract.auction`) — live config wins

| Rule | Guide v0.26.1 | Live config 2026-10-04 |
|---|---|---|
| Created by | a country, on a battle and side it is involved in, with budget, minimum damage, duration | — |
| Duration | 5–25 min | 5–25 min (`auction.minDuration/maxDuration`) |
| Bid step | 0.05 / 1k | **0.01** (`bidStep`) |
| Minimum rate | 0.05 / 1k (reaching it can close the auction immediately) | **0.01** (`minPerK`) |
| Anti-sniping | a bid in the last 30 s extends by 30 s | threshold 60, extension 60 (units unstated, likely seconds) |
| Max rate | — | `maxPerKMultiplier` 6 |
| Max damage per contract | — | 10,000,000 |

Current per live config: step 0.01, min 0.01 (reaching it ends the auction at once — wiki), extension 60 with threshold 60
(units unstated; the outdated wiki says "last 30 s → +60 s"). The guide's 0.05 /
30 s figures are outdated or wrong. Contracts are created for a specific **round**. History: max money per 1k 10 → 1 (2025-07-14) →
2 (2025-08-15); now `maxPerKMultiplier` 6 (relative to average wage; after v0.27 removes the job market, which average applies
is open, U-V27-11).

Other auction rules `[RULE]`:
- **Professionals only** option: only MUs with reputation ≥ 5 `[LIVE]`.
- Only MU owners/commanders can bid and manage the contract.
- An MU with a member in the issuing country's government **can't bid** on that auction (conflict of interest).

## MU obligations `[RULE][LIVE]`

- Winner locks an **acceptance fee of 10%** of the budget, returned on completion.
- Damage dealt **for the opposite side is subtracted** from contract progress.
- `[VERSIONED]` Until v0.27.4 members had to reach the battle region, so bids included travel cost; since v0.28 (2026-11-03) they hit from anywhere.
- An MU can hold **one active contract** at a time — commanders should pick the best budget/effort, not the first one.

## Payment `[RULE]`

- Paid at the end, proportional to members' damage; not per hit.
- If the country cancels early it pays the penalty (live: **10%**, `cancellationPenaltyPercent`); realized budget is distributed
  proportionally.
- MU reputation decays **20% per week** toward zero (positive or negative). Success: **+1 per 1,000 coins earned**; failure: **−1 per
  1,000,000 of contract value** `[LIVE]` (`reputation.successPerDollar` / `failurePerDamage`). Negative reputation buy-off (config: cost 200, 1 point per 24 h) — semantics `[GAP]`.
- MU members who took a contract can't collect bounties on that battle.
- v0.27 fix: contracts that reach their target near the **end of a round** now pay out (before, some didn't).

## Checks before accepting `[STRAT-RO]`

Budget, minimum damage, duration, acceptance fee, reputation requirement, conflict of interest, compatibility with the
national order and NAPs, distance to the battle region. A contract on the wrong side of a NAP can cost more diplomatically
than it pays.
