# Defensive Pacts

`[RULE]` (`bonus.defensive_pact`)

- **Bilateral**: requires proposal + acceptance, paid in paper. Proposal cooldown **12 h**.
- Bonus starts at **+1%** and grows **+1% per day** up to **+10%**.
- Applies when **defending the partner's territory**; in revolts, to the side recovering its homeland. **Not** a universal
  bonus for every battle of the partner.
- A country can hold **several** pacts at once; breaking one is **free** (Break Defensive Pact law).
- Reaches +10% after 9 days (start +1%, +1%/day) — consistent with the guide's +1%/day.
- Pact partners that aren't allies get **no** bunker/base bonus when defending the partner `[WIKI-ONLY]`.
- Daily paper upkeep: `floor(average development / 10) × 5` per pact (wiki country page) — the wiki pact page says
  `floor(average development / 10)` `[CONFLICT]`. Fanatic Diplomatic −50%; Fanatic Isolationist +50%; Unethical can't have pacts.
- To attack a pact partner, break the pact first (and leave the shared alliance, if any) and declare war.
- **From v0.27** `[RULE]` (government types replace ethics): **Federation** pays half pact upkeep and its pact bonus grows
  **+2%/day** (max not restated, assumed 10 → reached after 5 days `[Derived]`); **Mercenary State** can't have pacts (choosing it drops
  them at once). The ethics modifiers above end with v0.27.

Formula: `pact bonus = min(1 + full days active, 10)` (F-DAYS-BONUS).
`python scripts/combat_bonus_calculator.py --pact-days 6 --ally`.
