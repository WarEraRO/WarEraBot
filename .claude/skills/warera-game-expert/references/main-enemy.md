# Main Enemy

`[RULE]` (`bonus.main_enemy`; config calls it "enemy", law `define_enemy_country`)

- **Unilateral** declaration against one country; bonus in **attack and defense** against that country.
- Called **Sworn Enemy** in the game/wiki. Starts at +1%, +1% per day, max **+10%**. **Fanatic Isolationist**: starts at +5%, +5% per day.
- Paper: enactment `base 10 × average development` (wiki example inconsistent); daily upkeep `floor(average development / 10) × 10`
  `[WIKI, low confidence]`. Fanatic Diplomatic +100% upkeep; Fanatic Isolationist +50% upkeep but orders against the enemy −50%.
  Declaring a new enemy replaces the old one; the **Remove Enemy** law is one-sided and free.
- **Pacifist Fanatic** countries cannot have a Main Enemy.
- **From v0.27** `[RULE]` (government types replace ethics): **Nationalist State** starts at **+5%**, grows **+5%/day**, max
  **+15%** (reached after 2 days); **Federation** and **Mercenary State** can't have a sworn enemy (choosing either drops it at once).
  The Isolationist/Diplomatic modifiers above end with v0.27.

Formula: `enemy bonus = min(start + days × rate, 10)`, start/rate 1 (5/5 with Fanatic Isolationist) (F-DAYS-BONUS).
`python scripts/combat_bonus_calculator.py --enemy-days 4 [--isolationist]`.
