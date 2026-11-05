# Employee events (v0.27)

> Part of the v0.27 employee system ([employees-and-wages.md](employees-and-wages.md)); registry ID `employees.events`.
> The rule summary comes from the admin's v0.27 article `[RULE]`. The constants and event definitions below were read from the
> **live client** on 2026-10-26 `[LIVE-CLIENT]` (`LIVECLIENT_V027_TEXT`: 78 event definitions with pools, weights, cooldowns,
> checks and outcomes). They match Elereo's *Tech Guide: Worker Events Mechanics, Costs & Outcomes* (article
> `6adef089dc5a9c288b3725c8`, dev-server snapshot of 2026-10-25, source `V027_GUIDES`), which names every option. Event
> names are readable versions of the client codes; the in-game titles can differ (the poaching event shows as "A tempting offer",
> the retirement event as "Time to retire", the office romance as "Checking the inventory").
>
> **v0.27.4 (admin article `6ae8bb12bcc26a2f5712ec9d`, 2026-11-02)** rebalanced the events so that "paying in an event is now
> worth it more often than picking a free answer" (work credited to the player Johnny_Sins). Every cost and outcome below is the
> v0.27.4 value, re-read from the live client that evening (`LIVECLIENT_V0274`); the old values come from Elereo's guide and are
> in "v0.27.4 rebalance" below.

## Rules `[RULE]` and constants `[LIVE-CLIENT]`

- 78 events in 8 pools: life 20, cozy 17, social 10, inspiration 9, crisis 8, chain (follow-ups only) 8, world 4, legendary 2.
- About **1 event a day with 3 employees**. The client's rate key `perSqrtEmployee` = 1/√3 suggests about **√n / √3 a day**
  (0.58 with 1 employee, 0.82 with 2, 1 with 3) *Derived*. Max **3 a day** and **3 pending** per owner. The same employee waits
  **24 h** between events, and a crew with no event for **72 h** gets one (pity timer). An event repeated within 7 days is damped
  (×0.35). Pool budgets: social 33, life 32, cozy 30, inspiration 28, crisis 12, world 6, legendary 1.
- `[VERSIONED]` Any employee, **right after hiring**, since v0.27.1 (2026-10-27; client `minHiredHours` 0, and the UI dropped
  "never to someone hired less than … ago"). Under v0.27 (2026-10-26 → 27) only employees hired **≥ 48 h** ago. Either way only
  while the owner logs in at least every **3 days**.
- You have **36 h** to answer (some follow-ups 48 h); then the **default option** is applied. Some defaults hurt (lost happiness,
  output, a bad trait, a follow-up, the employee leaving), so ignoring an event is a choice.
- Individual events also have their own cooldowns (per employee, per owner, or once per employee).
- Since v0.27.3 (fix) an event acts on the tool and coworkers present **when it appeared**, even if you change them before
  answering, so moving a tool or an employee away no longer dodges an outcome.
- An employee with no Potential left falls back to a 15% / 72 h rule (`noPotentialFallback`; meaning not stated `[GAP]`).

### Checks

Each checked option shows its odds before you choose (since v0.27.2 the odds bar reads failures on the left, successes on the
right). An option has a **base** value (35–70 for most) plus modifiers, and the
final chance is clamped to **5–90%**. 10% of successes are **critical** (20% for a Gambler) and 10% of failures are
**critical failures** (20% for a Gambler). A crit has its own outcome list, which doesn't automatically include the ordinary
result's effects; some effects apply **always**, whatever the roll.

| Input | Effect `[LIVE-CLIENT]` |
|---|---|
| Employee's Luck | `[VERSIONED]` **Luck × 4** points on Luck checks, **Luck × 2** on standard checks since v0.27.3 (article: "every point now adds +4% (or +2% on some events)"; client `statPivot` 0). Until v0.27.2: `(Luck − 3) × 4` / `× 2` (in-game tooltip) |
| Owner's Management | **+2 per level** since v0.27.3 (article: "+2% event odds per level"; client `skillPerLevel` 2, shown on the Management skill). Leadership did this until v0.27.3. Which check types it applies to isn't stated `[GAP]` |
| Happiness | `happinessDivisor` 5 (presumably happiness ÷ 5 relative to a pivot) |
| The relevant stat | `statPivot` 0 (3 until v0.27.3), `statPerPoint` 4 |
| Traits | per-option modifiers, e.g. Loyal +15 to convince a retiree, Patriot +10 to volunteer, Flight risk −15 to appeal to loyalty |
| Age | retirement checks lose 5 per year past 65 |

How Management, happiness and the stat combine isn't in the client `[GAP]`; use the odds the game displays. v0.27.3 left the
option bases unchanged (client 2026-10-30: retirement 70, Business Opportunity 40, Locker Hoard 35), so the Luck change alone made
every Luck check 12 points easier for a Luck-3 employee (standard checks 6) *[Derived]*.

### Costs in wage-days

Coin costs and rewards are given in days of **that employee's** wage `[LIVE-CLIENT]`:

```
cost = max(0.01, round(hourly wage × 24 × wage-days, 2))
```

At a 0.10/h wage, 3 wage-days cost 7.20; at 0.50/h, 36. The same event costs a well-paid employee far more. Other costs: Energy
(1, 3 or 5 since v0.27.4; was 5 or 10), a toolbox, company goods, time away (no work and no wage), output penalties, happiness,
and higher wage expectations.

### v0.27.4 rebalance `[VERSIONED]`

The article says "23 paid answers cost less, many less than half" and names only a few. "Before" = Elereo's guide, i.e. the
**dev-server** definitions of 2026-10-25, not a read of the live client before the patch (none was saved); "since" = live client of
2026-11-02. Costs in wage-days unless marked Energy. Rows the article doesn't name are "changed versus the guide" *[Derived]*.

| Event → option | Before | Since 2026-11-02 |
|---|---|---|
| Eureka → fund the idea | 2 | 0.75 |
| Hidden Talent → lessons | 2 | 0.25 |
| Night Classes → paid course · teach yourself | 3 · 5 Energy | 0.45 · **3 Energy** |
| Time to retire → convince them | 5 | 0.75 |
| Letter from Home Promise → keep it | 4 | 1.9 |
| Union Strike → meet the demands | 2 | 1.05 |
| Ladders → fortune teller (can remove Jinx) | 3 | 0.45 |
| Coffee Machine → buy a new one | 2 | 0.35 |
| Green Grapes 1 → 0.55 · Work Anniversary party 1 → 0.6 · Suggestion Box chairs 1 → 0.7 · Snack from Home 1 → 0.4 · Cursed Tool exorcist 1 → 0.3 · War Rationing 1 → 0.3 · Bootcamp sponsor 1 → 0.3 · Birthday Card party 1 → 0.3 · Karaoke all-in 1 → 0.25 · Kitten Posters 1 → 0.25 · Moonlighting 0.5 → 0.15 · Recruiter's Cousin 0.5 → 0.15 · Safety Inspector fee 1 → 0.1 · Sandwich Discovery 1 → 0.1 · Arm Notes notebook 0.5 → 0.1 | | |
| Tattoo → correction | 2 (article; not in Elereo's list) | 0.1 |
| Mentor's Offer → accept · Bootcamp → join | 10 Energy · 5 Energy | **5 Energy · 1 Energy** |
| **Raised, with a better outcome:** Same Haircut → buy a hat | 0.5 (pleased one, upset the other) | 2.3, makes the pair **Old Friends** |
| **Raised:** Stuck Lift → technician | 1 (6 h away) | 2.75, **cures Claustrophobe**, +10 happiness for 3 days, no time away |
| Strange Mood Demand → deliver | 40 raw / 12 product units | "about {demandValue} of the company's good", about **9 money's worth** (article; computed server-side) |
| Same as in the guide | Business Opportunity 2, Gambling Debts 3, Van Race 1, Lottery Ticket 1, Burning Out doctor 3, Stray Cat 1, Romance Trouble dinner 1, Compliment 0.5, Plastic Plant 0.5, toolbox options | |

Counting from that list gives 23 coin cuts plus Tattoo, i.e. 24, and 3 Energy cuts. The article says 23; the old values come from a
dev snapshot, so one of them may already have differed live `[GAP]` (U-V274-4). Letter from Home's paid trip (4) and visit (0.4)
have no "before" in the guide.

Outcomes changed by v0.27.4 `[RULE]` article, `[LIVE-CLIENT]` definitions:
- **Van Race** bet pays **×3** (was ×2). **Gambling Debts** loan returns **×2** (was the stake, ×1), crit ×2.2 (was ×1.2).
- **Night Shift Tinkerer** "use a toolbox": no check any more, always full durability and **+20% output for 5 days** (was a check;
  a failure restored only 30 durability). **Smoking Machine** "use a toolbox" adds +10% for 5 days, and **Cursed Tool**'s exorcist
  also restores full durability (both seen only in the client and the new in-game text "runs better than ever" / "fixed the
  squeak too"; the article doesn't list them).
- **Fairer rolls** ("a better roll never gives less than a worse one"): Time to retire's honor crit now gives the trait
  inheritance **and** the heir's +1 stat; Gerald's crit keeps the +5 company happiness besides +10% for 48 h; Rubber Ducks' sell
  failure pays 0.5 wage-days (was 10 scrap).
- Strange Mood's eligibility text adds "Never in a cocaine company" (UI catalog).

## Events that matter `[LIVE-CLIENT]`

Durations are as the client defines them; "company" = everyone in the company. "Wage ×1.1" multiplies the wage expectation
for good.

| Effect | Event (pool) | Option → outcome |
|---|---|---|
| **Death** | Call to Arms (world) | Volunteer (standard 55, Patriot +10; always 24 h away): success +10 happiness 7 days and **+1 Responsibility**; failure −10 for 5 days; **critical failure: killed**. Default: forbid (−5 for 3 days) |
| **Retirement** | Time to retire (life, guaranteed at 65, then every 10 years of age: 10 days until v0.27.4, presumably 10 aged days since *[Derived]*) | see [employees-and-wages.md](employees-and-wages.md#who-they-are-rule) |
| **Poached** | A tempting offer (crisis; happiness ≤ 45, Production ≥ 6, or Climber; always possible and twice as likely for Flight risk) | Match it: **wage ×1.1**, +15 for 5 days · Appeal (standard 40; Loyal +20, Flight risk −15, Greedy −10): crit gains **Loyal**, failure −15, crit-fail **leaves** · Let them go: they leave, **you get 5 wage-days** · Say nothing (**default**, Luck 70, always −10 for 3 days): failure gains **Flight risk**, crit-fail **leaves** |
| Leaves | Strange Mood Demand (chain, 48 h; never in a cocaine company) | Deliver the goods (about 9 money's worth of the company's good since v0.27.4, was 40 raw or 12 product units; standard 70; Craftsman/Specialist +10, Handy +5; always +20 for 7 days): success **Legendary tool**, failure **Epic tool** · Miss it (**default**, Luck 50): success a **random bad trait**, failure **leaves** |
| Retires with a payout | Lottery Ticket (life, owner cooldown 45 days) | Champagne (1 wage-day, Luck 10): success pays **10 wage-days** and coworkers +10, but the employee **retires** |
| Leaves | Union Strike (chain) | Call the bluff: failure 48 h away, crit-fail **leaves**; default: 24 h away, −5 |
| +stat / +Potential | Golden Hour (legendary; once per employee, owner cooldown 60 days) | Let it flow (default): +1 random stat, +40% for 24 h · Push on (standard 50): +2 random stat and **+1 max Potential**; crit adds a **random good trait**; failure +1 stat; crit-fail +1 stat and **Burnout** |
| +stat | Eureka (inspiration) | Fund the idea (0.75 wage-days, standard 45, Quick study +10): **+1 Production**, crit also +1 max Potential · Experiment (always −50% for 12 h): +5 / +10 specialization days |
| +stat | Hidden Talent (inspiration) | Lessons (0.25 wage-days, standard 50): +1 random stat, crit +1 max Potential |
| +stat / +Potential | Night Classes (life) | Teach yourself (**3 Energy**, standard 60): +1 random stat, crit +1 max Potential · Paid course (0.45 wage-days, standard 55): **+1 / +2 max Potential** |
| +stat (coworker) | Mentor's Offer (social) | Accept (**5 Energy**, standard 60, Mentor +10; mentor always −15% for 24 h): partner **+1 Production**, crit +1 max Potential |
| Traits | Midlife Crisis (life) | Back them: +1 random stat and a bad trait removed; crit also a random good trait; failure −10 for 5 days; crit-fail can reset specialization |
| Traits | Friendship Blooming, Crate Fort, Same Haircut, Soup Debate, Prank War, Thermostat War, Scuffle (social) | can create **Old friends** (+15% together) or, on critical failure, **Nemesis** (−15%); Scuffle mediation can end a Nemesis. Since v0.27.4 Same Haircut's hat (2.3 wage-days) makes the pair Old friends for sure |
| Traits | Checking the inventory (office romance; two coworkers hired ≥ 7 days ago, happiness ≥ 45, at most 15 years apart; at most once per 21 days) | Encourage: **Sweethearts** (+20% together); success schedules Romance Trouble in 14 days, which can end it or create Nemesis |
| Traits | Rival's Secret, Tattoo, Letter from Home Promise | can grant **Loyal** |
| Traits | Burning Out, Lost Resignation, Poaching, Title to Head, Union of One, Enemy Leaflets | can add **Burnout** or **Flight risk**; Burning Out's doctor (3 wage-days) removes Burnout, Lost Resignation's crit removes Flight risk |
| Trait removal | Letter from Home, Ladders, Stuck Lift, Moved Chair | remove Homesick, Jinx, Claustrophobe, Creature of habit (some on a crit only). Since v0.27.4 Stuck Lift's technician (2.75 wage-days) cures Claustrophobe for sure, and Ladders' fortune teller costs 0.45 |
| Wage up | Union of One (negotiate: **×1.05**), Title to Head (raise: **×1.10**), Poaching (match: ×1.10) | permanent wage increases; the expectation can reach 160% |
| Items | Found Toolbox (take it: **+1 toolbox**, but the finder −15 for 5 days) · Locker Hoard (Luck 35: a **wooden case**, crit + a toolbox; or 15 scrap) · Dump Bag (Luck 45: 15 scrap, crit + a toolbox) · Suggestion Box (a wooden case) · Rubber Ducks (sell, standard 45: 1 wage-day, crit 2, failure 0.5 since v0.27.4, was 10 scrap) | |
| Money bets | Business Opportunity (invest 2 wage-days, Luck 40, always +10 for 5 days: success returns ×1.3, crit ×2) · Gambling Debts (lend 3 wage-days, standard 55: success returns **×2** and +10 for 5 days, crit ×2.2; was ×1 / ×1.2 until v0.27.4) · Van Race (1 wage-day, Luck 45: success **×3**, was ×2) · Kid at Work, Karaoke (can pay wage-days) | |
| Tools | Night Shift Tinkerer, Cursed Tool, Smoking Machine, Shortcut, Bad Horoscope, Ladders, Coffee Machine, Kid at Work | restore (+10 … full) or damage (−20 … −40) **tool durability**; some only trigger on a tool worn to ≤ 40 or ≤ 50 durability. Since v0.27.4 a toolbox in Night Shift Tinkerer always gives full durability and +20% for 5 days, in Smoking Machine full durability and +10% for 5 days |
| Output | On Fire (+30% for 24 h), Break Chart (+10% company 48 h, coworkers −10), Sandwich Discovery, Air Raid, Safety Inspector (default **−15% company for 48 h**), Bootcamp, Kittens … | short output buffs or penalties |

Elereo's notes add that a successful check isn't always good (Strange Mood Demand's "missed" option succeeds into a bad trait)
and that a crit-success list can lack a follow-up its success list schedules (office romance).

## Evaluating an event `[Derived]`

Expected cash = Σ (probability × cash return) − cost, using the displayed chance and the crit shares. Example, Business
Opportunity at the base Luck-check value 40% with no modifiers: return = 0.4 × (0.9 × 1.3 + 0.1 × 2) = 0.55 of the stake, so
on average it loses ~45% of the 2 wage-days; it only pays at ≥ ~73% displayed odds. Since v0.27.3 every Luck point adds 4, so a
Luck-3 employee starts at 52% (return 0.71, still a ~29% loss), and Luck alone reaches 73% at Luck 9.

Since v0.27.4 the other two bets pay. **Van Race** (×3, no separate crit list) breaks even at **33%** displayed odds, and its base
alone (Luck check 45) returns 1.35 stakes, or 1.71 at Luck 3. **Gambling Debts** (standard 55; ×2, crit ×2.2) returns
p × (0.9 × 2 + 0.1 × 2.2) = 2.02 p, so it pays from **49.5%**, and the base gives +11% of the 3 wage-days. Cheap options now beat
free answers for small sure gains: a 0.1 wage-day fee (Safety Inspector) avoids −15% company output for 48 h. Weigh the non-cash
parts separately:
permanent stats or Potential (value per day from the training formulas in [employees-and-wages.md](employees-and-wages.md#training-rule-employeestraining)),
traits, time away, output and happiness changes, tool durability, wage-expectation rises, the risk of losing the employee, and
follow-ups.

`[STRAT-EXT]` With a big workforce, Wodkabouter doesn't optimise each event: pick the best option, give happiness to the
employee with the highest Production, keep happiness well above 30 because some events cost happiness unavoidably, and keep
crews at decent happiness since low happiness also worsens event odds. babeuce: gamble on the good ones, but prefer safe options
so training isn't wasted.
