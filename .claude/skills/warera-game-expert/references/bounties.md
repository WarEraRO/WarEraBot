# Bounties

A bounty is a **public money fund paid for damage**: every eligible player hitting the indicated side earns money
proportional to damage until the budget runs out `[RULE]`.

## Mechanics (`bounty.rules`) `[RULE][LIVE]`

| Rule | Value |
|---|---|
| Activation delay after posting | ~3 min (visible but inactive; damage before activation earns nothing) |
| Cancellation lock | cannot be cancelled for 60 s after activation — also if round 1 ends and round 2 starts in that window `[OBS]` |
| Max rate | until v0.27: average wage × 6. Since v0.27 (2026-10-26) the config key is `maxBountyPpMultiplier` **9** (was `maxBountyWageMultiplier` 6), so the cap follows the **PP value** (most likely 9 × the money value of 1 PP per 1k damage; unit not stated, read the bounty dialog) `[LIVE]`, not in the article (U-V27-11) |
| Government members | may earn from their own country's bounty with a **50%** penalty |
| Active contract holders | can't collect a bounty on the same battle |
| MU reputation | bounties give none and don't reserve damage for one unit |
| Position | `[VERSIONED]` none since v0.28 (2026-11-03): anyone hits from anywhere; before, fighters had to reach the region, so a bounty had to cover travel |
| Min citizens rule | the ≥10-citizen money-transfer limit does **not** apply to bounties/contracts |
| Civil wars | bounties **can't be placed** `[VERSIONED]` (v0.26.2, 2026-10-14; before that the government side could fund one). Contracts not covered `[GAP]` |

Live config: `mercenaryContract.bountyMinActiveCitizens` 0, `nationalBountyMinActiveCitizens` 40, `nationalBountyEnabled` false
— a "national bounty" feature exists in config but is disabled; semantics `[GAP]`.

## Bounties that cannot be paid

Treasury empty (Scenario D) · bounty posted too late and the battle ended during the activation delay.

## Romanian internal policy `[POLICY-RO]` (adjustable by leadership)

| Situation | Recommendation |
|---|---|
| Active players without resources | selective help if treasury allows and the player's build is efficient |
| Strategic battle | announce ≥ ~15 min before when possible; rate and budget scaled to importance |
| General bounty | example: 0.05 / 1k, budget ~500 |
| Announced bombs | at leadership's discretion; must be coordinated and actually serve the objective |
| Emergency | special bonuses/contracts only for critical objectives |

Bounties and contracts must be **announced before activation**: transparency avoids confusion, lets fighters prepare (and
travel) and protects the treasury. A bounty should not cannibalize a contract on the same battle.
