# Employees, managers and wages

> **v0.27 (admin article `6ade08f7899288ce9f0bfe36`, live since 2026-10-26)** removed the job market. Companies run on **hired
> employees** (game characters with stats), and players can work for another player only as a **manager**. The rules below are
> current `[RULE]`. The old system (player workers, owner-set wages, loyalty, F-MAXWAGE) is in
> [deprecated-mechanics.md](deprecated-mechanics.md#job-market-and-player-workers-until-v027).
> Registry IDs: `employees.*`, `company.break_room_levels`, `skills.economy_values`, `country.taxes`.
>
> **v0.27.1 (admin article `6ae0defd260ab3cd58036d7a`, 2026-10-27)** changed five things below, each marked `[VERSIONED]` with
> the v0.27 rule kept as history: firing a fresh hire is free; events can start right after hiring (no 48 h wait); no employee
> deaths in battles "for now"; Homesick employees are fine in their country's occupied regions; manager wages were divided by 10
> and managers are paid even in a company with no employees. The live client of the same evening (`LIVECLIENT_V0271`) confirms
> the first two.
>
> **v0.27.2 (admin article `6ae2608f707baf45eebf26c5`, 2026-10-28)**: no more contradicting traits (the incompatible-pair list
> grew from 14 to 32, see Traits); employee names match their country; the hiring window counts down to the 00:00 UTC refresh;
> training cards show before → after; the map can show where employees work; API tokens can read your employees and their events.
>
> **v0.27.3 (admin article `6ae39f39b9d173140341a461`, 2026-10-29)** reworked hiring and three stats, each marked `[VERSIONED]`
> below with the older rule kept as history: candidates show all stats and the wage (trait and Potential stay hidden); every hire
> has exactly one trait; Specialist matches the company's good; a new hire can't be fired for 12 h; **Leadership merged into
> Management** (training-card odds and +2 event odds per level; Leadership points refunded, plus one more free skill reset);
> **Responsibility gives +3 happiness per point** instead of shielding losses; transfers and firing cost no happiness; every Luck
> point counts in events; **Early bloomer** replaced Sprinter; Rehab removes bad traits only; the Wild card shows its bad-trait
> chance; in-game profit estimates use the produced good's PP value; an event acts on the tool and coworkers present when it
> appeared. The live client and config of 2026-10-30 (`LIVECLIENT_V0273`) and a roster sample (`LIVEAPI_20261030`) confirm every
> rule they can show.
>
> **v0.27.4 (admin article `6ae8bb12bcc26a2f5712ec9d`, 2026-11-02)**, each marked `[VERSIONED]` below: age goes up one year per
> **day worked or trained**, not per calendar day; a **disabled company** puts its employees on hold (no work, ageing or training);
> new trait **Talks to Machines**; **Bully** is a bad trait; training gets a free **Reroll** card, the **Wild card** is Rare and gives
> +2, and mixed traits are no longer taught; a tool that doesn't fit the new company goes back to your inventory; employee events
> were rebalanced ([employee-events.md](employee-events.md#v0274-rebalance-versioned)). The article also says trait Production
> now counts toward the "expected wage", but live wages still pay base + trained only (`[CONFLICT]`, see Wages). Checked against
> the live client, config and UI catalog (`LIVECLIENT_V0274`) and 70 rosters (`LIVEAPI_20261102`) the same evening.
>
> Numbers marked `[LIVE-CLIENT]` were read from the live client bundle on 2026-10-26 (`LIVECLIENT_V027`, and the in-game English
> text of a later build the same evening, `LIVECLIENT_V027_TEXT`). They match the dev-server values the UNIKHORNE codex reported
> the day before. `[LIVE]` ones come from the live config of the same day (`LIVECFG_V027`: Break Room L1–L3, tool items). Toolbox
> odds come from the article only. `[CODEX]` marks claims from the codex's other sources.
>
> **Community guides (source `V027_GUIDES`, ten in-game articles of 2026-10-25/26, see [source-map.md](source-map.md)).**
> `[OBS]` marks what their **dev-server screenshots** show (Piraterer, fish, Wodkabouter). The dev server ran the 0.27.0 beta
> before the deploy, so these are observations of the beta, not the live game. `[STRAT-EXT]` marks their advice. Where a guide
> and the live client disagree, the client wins. Events have their own page: [employee-events.md](employee-events.md).

Why the admin changed it: 70% of players had no workers, most players who hired lost money, and a player-worker market made
every new bonus risky. *Goal: "less routine, more reward".*

## Hiring `[RULE]`

- Each company gets **3 new candidates every day at 00:00 UTC**; since v0.27.2 the hiring window shows a countdown to that
  refresh. `[VERSIONED]` Since v0.27.3 (2026-10-29) a card shows **all three stats and the wage**; the trait and the Training
  Potential show only once hired. *History (v0.27 → v0.27.2):* each card showed **one hint** (one stat, one trait, or the Potential).
  Candidates' names match their nationality: every country has its own name list since v0.27.2.
  - `[OBS]` Every card also shows the **age, gender, nationality and daily wage**, and whether the candidate has a trait at
    all (a "?" badge, which tells nothing since v0.27.3 because every hire has one) without naming it. Some guides say the hint can be "the wage"; that's the always-visible wage line, not
    the hint.
  - *Derived:* the wage line gives away the paid Production × expectation: `daily wage ÷ (6 × PP_value)`. Wodkabouter's example:
    at a PP value of 0.1, a 2.36/day candidate is most likely Production 4 at −1.7% expectation. Greedy/Modest blur it. Since
    v0.27.3 the card shows Production too, so the **expectation can be read before hiring**: `daily wage ÷ (6 × PP_value ×
    Production)`, Greedy/Modest included. That assumes the card's Production is the paid (base) one, not yet confirmed `[GAP]`.
- **Hiring costs 10 Energy and no money** `[LIVE-CLIENT]`. A new set of candidates ("Reroll all") costs 10 Energy the first time,
  then **doubles** each time (10, 20, 40, 80, 160 …). Whether that resets daily isn't stated `[GAP]` (U-V27-16).
- `[VERSIONED]` **Firing is free**, also for a fresh hire, since v0.27.1 (2026-10-27): the client dropped
  `fire.rerollWithinHours` and the "counts as a reroll" text `[LIVE-CLIENT]`. Since v0.27.3 (2026-10-29) firing costs coworkers
  **no happiness** (was −5 for 24 h), and a **new hire can't be fired for 12 h** (client `fire.hireLockHours` 12) `[LIVE-CLIENT]`.
  *History (v0.27, 2026-10-26 → 27):* firing someone hired less than 24 h ago counted as a reroll at the current reroll price.
- **Break Room** (company upgrade) sets the max employees: L1 **1** (every company starts here), L2 **2** (20 steel), L3 **3**
  (80 steel). There is no level above 3: the live config lists L1–L3 only `[LIVE]` (U-V27-6). This replaces the Management-based worker cap (the old Break Room with
  2–10 workers was already removed in v0.22.0, 2026-01-09).
  - *Derived:* the ceiling is 3 × your active companies (2 + Companies level): **36** employees at Companies 10, **39** with the
    Prestige company (Companies 11 = 13, [prestige.md](prestige.md)). Only **active** companies work (fish).
- **Self-work** still works in your own companies, for **10 Energy** per action.
- You can **move** employees between your companies, or swap two of them; with premium you can also **rename** them `[RULE]`.
  `[VERSIONED]` Since v0.27.3 a move or swap is **free**, and you can fire right after it `[LIVE-CLIENT]` (the client keeps only
  the company-move penalty). *History (v0.27 → v0.27.2):* −5 happiness for 7 days, and no firing for 24 h.
- A **Recruiter** employee adds 1 candidate to the daily shortlist of **every company you own** `[LIVE-CLIENT]` text; Recruiters
  stack up to **3 extra** slots (`maxExtraCandidateSlots`).
- **1 free company move for everyone** (article, section 12), meant to bring companies home. Piraterer's guide reads it as one
  free move **per company** `[CODEX]`/`[OBS]`. Whether the free move spares the crew the company-move happiness hit is unknown `[GAP]`.

## Who they are `[RULE]`

| Property | Rule |
|---|---|
| Stats | **Production** (how much they make), **Luck** (what they find), **Responsibility** (happiness: +3 per point since v0.27.3). Some guides call Responsibility "Discipline" |
| Starting stats | each 1–4, all equally likely |
| Traits | **53** since v0.27.4, which added Talks to Machines (the live client had 52 until then, against the v0.27 article's 53: U-CDX-6). `[VERSIONED]` **Exactly 1 trait at hire** since v0.27.3 (`traitsPerEmployee` 1–1; all 13 hires in the 2026-10-30 sample had one); before, a 50% chance of 1, otherwise none. Training and events can add more. Full table below |
| Training Potential | 3–10 at hire (training draws); training can raise the maximum to **15** `[LIVE-CLIENT]`. Shown as "used / max" (e.g. 2/9 = 7 draws left) `[OBS]` |
| Age | starts 18–45. `[VERSIONED]` Since v0.27.4 **+1 year per day worked or trained**, at most once per UTC day (API `lastAgedDay`; a pause icon shows on anyone who hasn't worked or trained today: "Not aging: no work or training today"), and nobody ages in a disabled company. *History (v0.27 → v0.27.3):* +1 year per calendar day (at the daily reset `[OBS]`) |
| Gender, nationality | fixed; they matter for traits (Girl power, Nationalist, Cosmopolitan …) and some events |
| Retirement | asks to retire at **65**, then again every **10 years of age** if kept (client `repeatDays` 10 × `yearsPerDay` 1: 10 calendar days until v0.27.4, 10 days worked or trained since *[Derived]*); each year past 65 takes 5% off the odds of keeping them |

`[LIVE-CLIENT]` stat effects, from the in-game text:
- **Production** is the only stat that makes output. The shown Production is a sum: base + training + Production from traits
  and coworkers (e.g. base 1, training +1, Specialist +3, Cosmopolitan +4, a coworker's Mentor +2 = 11; `[OBS]` tooltip).
- `[VERSIONED]` **Responsibility** gives **+3 happiness per point** since v0.27.3 (client `responsibilityHappinessPerPoint` 3;
  the API's happiness breakdown shows "responsibility +9" at 3 points). Through happiness that is **+3% output per point** until
  happiness reaches 100 *[Derived]*, and it doesn't raise the wage. *History (v0.27 → v0.27.2):* a "morale shield" that cancelled
  10% of every happiness **loss** per point (100% at 10), never touched gains and didn't raise output by itself.
- **Luck** never makes output. Each point is a 0.1% chance per worked hour to find a toolbox (`[VERSIONED]` no cap since
  2026-10-29, unannounced; was 2%), tilts training draws
  toward rarer cards, and moves event odds. `[VERSIONED]` Since v0.27.3 **every point counts**: **Luck × 4** points on Luck checks
  and **Luck × 2** on the others (client `statPivot` 0, `statPerPoint` 4, `luckPerPoint` 2). *History:* `(Luck − 3) × 4` and
  `× 2`, so the first 3 points did nothing.

**Retirement event** `[LIVE-CLIENT]` (event definition; also seen on the dev server): three answers.

| Answer | Check | Outcomes |
|---|---|---|
| Honor their career | Luck, base 70 | they retire either way; coworkers +10 happiness for 5 days; success: a coworker gets +1 to a random stat (free, no Potential used); critical success: a coworker inherits one of their **good traits** and, since v0.27.4, also gets the +1 stat ("teaches a coworker one last trick, and leaves something behind") |
| Convince them to stay | costs **0.75 days of their wage** (5 until v0.27.4); standard check, base 65, Loyal +15, −5 per year past 65 | success: +10 happiness for 7 days; failure: −10 for 5 days (they stay either way); critical failure: they retire |
| Not now, ask again later (**default** if ignored) | Luck, base 70, −5 per year past 65 | success: −5 happiness for 3 days; failure: they retire |

The "10 more years" in the answers means the next ask, 10 days later (since v0.27.4 presumably 10 aged days, i.e. days worked or trained *[Derived]*, U-V274-6). The
codex's earlier summary ("the bet costs the crew 5 happiness") was wrong: the −5 hits the employee. A hire aged 45 works 20 days
before the first question; since v0.27.4 days off don't count.
`[STRAT-EXT]` Wodkabouter: convince them once, then honor them to pass on a stat or trait. Piraterer: "Not now" is a fair bet
with high Luck.

### Traits `[LIVE-CLIENT]` (52 read 2026-10-26; 53 since v0.27.4, read 2026-11-02)

Roll weight in brackets (higher = more common at hire; 0 = only from an event). "×" = the client flags the effect as a
multiplier. In-game names (English catalog, `TRANSLATION_EN` 2026-10-27) capitalise each word: Prima Donna, Old Friends, Girl
Power, Band of Brothers, Quick Study, Creature of Habit, Diamond in the Rough, Late Bloomer, Worn Out, Flight Risk, Lucky Charm,
**Tax-shy** and **Misandrist** (earlier drafts of this page said "Man hater"). Since v0.27.1 each trait's tooltip is a
condition → effect table ("Sole employee: +100%"); the numbers didn't change. Conditions in quotes are the in-game wording.
**Incompatible pairs** `[VERSIONED]` `[LIVE-CLIENT]` (2026-10-30). v0.27.2: "No more contradicting traits on new employees".
On 2026-10-30 the client listed **30 pairs** an employee shouldn't hold together (**36** since v0.27.4, see the last bullet): the 32 of v0.27.2 below, minus the three Sprinter pairs that
v0.27.3 removed with the trait, plus **Early bloomer/Late bloomer**:

- **14 since v0.27** (client 2026-10-26): Handy/Improviser, Loner/Sociable, Cosmopolitan/Xenophobe, Comic/Bully,
  Craftsman/Laborer, Expat/Homesick, Statist/Tax-shy, Sprinter/Creature of habit, Sprinter/Veteran, Diamond in the rough/Burnout,
  Greedy/Modest, Flight risk/Anchor, Lucky charm/Jinx, Scavenger/Handy.
- **18 added by v0.27.2**: Nationalist/Cosmopolitan, Loyal/Flight risk, Late bloomer/Worn out, Veteran/Burnout,
  Sprinter/Diamond in the rough, Foreman/Bully, Mentor/Bully, Prima donna/Modest, Climber/Modest, Envious/Modest, Patriot/Expat,
  Xenophobe/Expat, Stockpiler/Claustrophobe, Loner/Comic, Loner/Foreman, Loner/Mentor, Loner/Trainer, Loner/Lucky charm.
- **6 added by v0.27.4** with the new trait (client 2026-11-02), so **36 pairs** now: Talks to Machines with Sociable, Comic,
  Foreman, Mentor, Trainer and Lucky charm (the same coworker traits that clash with Loner; Loner + Talks to Machines is allowed).

A hire still rolls at most one trait, so in practice the list filters the traits **added later**: training's New habit and Wild card
(see Training) *[Derived]*. Whether trait-granting events respect it is unknown `[GAP]`. **Existing clashes stay**: on
2026-10-29 two employees still held Envious + Modest and Loner + Trainer, both from Wild cards drawn before the patch `[OBS]`
(live API sample of 261 employees). *Derived:* a Loner with Mentor, Foreman, Trainer or Lucky charm was always self-defeating,
because those traits act on coworkers and Loner's bonus needs none.

| Group | Traits |
|---|---|
| Tools | **Handy** +40% "holding any tool", nothing bare-handed (5) · **Improviser** +25% without a tool (5) |
| Coworkers | **Loner** +100% and +5 happiness as "sole employee", nothing once a coworker joins (5) · **Sociable** +25% per coworker, max +50%, −10 happiness alone (10) · **Nationalist** +10 happiness when "half or more coworkers share their nationality"; `[VERSIONED]` since v0.28 (2026-11-03) given directly, on its own happiness line (was +2 Responsibility and +5 = +11) (10) · **Xenophobe** −2 Production, −5 happiness with a foreign coworker (10) · **Cosmopolitan** +2 Production "per foreign nationality on the roster", max +4 (10) · **Comic** −1 own Production, +10 coworkers' happiness (10) · **Mentor** "every coworker weaker than them" +2 Production, −1 own (2) · **Foreman** +9 happiness to every coworker, nothing for themselves; `[VERSIONED]` since v0.28 given directly (was +3 Responsibility each, the same +9) (5) · **Rival** +3 Production when "somebody out-produces them", −1 at the top of the roster (5) · **Prima donna** +20% when "paid more than every coworker", otherwise −10 happiness, nothing alone (5) · **Bully** +2 own Production, −10 coworkers' happiness; `[VERSIONED]` a **bad** trait since v0.27.4 (client polarity negative, was mixed), so Rehab and Clean slate can remove it and the Wild card's bad-trait chance counts it (5) · **Envious** −5 happiness per better-paid coworker, max −10 (10) · **Old friends** +15% with their partner × (2) · **Nemesis** −15% with their partner × (2) · **Sweethearts** +20% with their partner × (0, office-romance event only) · **Girl power** / **Band of brothers** +15% per female / male coworker, max +30% × (5 each) · **Misandrist** / **Misogynist** −15% per male / female coworker, max −30% × (5 each) |
| Work | **Specialist** +3 Production and +5 happiness on its good, which since v0.27.3 is **the good the company makes**, also when trained `[VERSIONED]` (before: a randomly rolled good; what happens after a transfer or a product change `[GAP]`) (10) · **Craftsman** +3 Production on products and weapons, −1 on raw resources (10) · **Laborer** +3 on raw resources, −1 on anything manufactured (10) · **Quick study** each day worked counts double toward specialization; cap stays +20% (10) · **Stockpiler** ignores the full-storage penalty (10) · **Claustrophobe** −20% while storage level ≤ 2 (5) · **Talks to Machines** (new in v0.27.4) "Automated engine output x2 when working alone": doubles the company's Automated Engine output while it is the company's only employee (client: condition `SOLE_EMPLOYEE`, effect `engineOutputMultiplier` 2; rosters show the result as `hourly.engineMultiplier`, which was 1 in all 70 companies sampled on 2026-11-02, none with this trait, so the doubling isn't yet observed live `[GAP]`) (5) |
| Career | **Early bloomer** (v0.27.3; replaced Sprinter, existing Sprinters switched automatically) +6 Production until 40, then −2 per 10 years, gone at 60, so +6 below 40, +4 at 40–49, +2 at 50–59 *[Derived]* from client `peakDelta` 6, `delta` −2, `ageAbove` 30, `capDelta` −6 (5) · *Sprinter* (v0.27 → v0.27.2) +50% in the first 24 h after arrival · **Veteran** +20% "after 30 days in the same company; a transfer resets it" (5) · **Creature of habit** −30% for 3 days after a transfer (10) · **Diamond in the rough** +1 to one stat every 10 days in the same company, max +4 (2) · **Burnout** −1 to every stat every 20 days in the same company, max −3 (2) · **Late bloomer** +2 Production per 10 years above 40, max +6 (5) · **Worn out** −2 Production per 10 years above 50, max −6 (10) |
| Geography | **Patriot** +2 Production, +10 happiness in a core region of their homeland (10) · **Homesick** −2 Production, −10 happiness outside the home country; since v0.27.1 **not** in the home country's occupied regions `[VERSIONED]` (the client's condition still reads "outside home country", so the exemption is server-side) (10) · **Expat** +2 Production outside the home country (10) |
| Politics | **Tax-shy** −1% per 1% employee tax, max −30% × (10) · **Statist** +6 happiness when employee tax ≥ 20%; `[VERSIONED]` since v0.28 given directly (was +2 Responsibility, the same +6) (10) |
| Wages | **Greedy** "expects 20% more pay than the market rate" (10) · **Modest** "asks for 15% less" (10) · **Climber** wage expectation +2% per week since creation (10) |
| Retention | **Loyal** halves happiness penalties (5) · **Flight risk** "starts looking for the door at 50 happiness, not 30" (10) · **Anchor** never walks out; below 30 happiness produces half × (5) |
| Loot | **Scavenger** ×2 toolbox chance, −25% output × (2; `[VERSIONED]` no cap since 2026-10-29, was "and twice its cap", up to 4%/h) · **Salvager** keeps finding toolboxes while the storage is full and nobody works (5) · **Gambler** +3 Luck, −15% output, twice as many event crits and crit-fails × (10) · **Lucky charm** +3 Luck to every coworker, not themselves (5). `[VERSIONED]` Since the silent patch of 2026-10-31: "given at 00:00 UTC to whoever works beside them then, and kept until the next reset, even if someone changes company" (API `charmLuck {amount 3, until}`, until = next reset + 1 h); before, it counted for whoever was beside it at the moment · **Jinx** −2 Luck to coworkers (10) |
| Support | **Recruiter** +1 candidate a day in every company you own (2) · **Trainer** `[VERSIONED]` since the silent patch of 2026-10-31: "gives coworkers 2 extra training sessions a day, shared between them", refilling at 00:00 UTC; not themselves; one coworker can take both, and several Trainers' pools add (was: every coworker could train twice a day) (5) |

Trait Production (e.g. Specialist +3) raises output but **not the wage** (see Wages). Rival and Mentor compare **base + trained**
Production, so training a Rival past its coworkers turns +3 into −1 (Wodkabouter) `[STRAT-EXT]`. *Derived* (assuming the hire
roll is weighted by these numbers): the weights sum to **359** since v0.27.4 (354 + Talks to Machines' 5; v0.27.3 left 354, as
Early bloomer took Sprinter's 5), so each weight-10 trait is ~2.9% of trait-holders (of 349 per gender) (~1.4% of all candidates before v0.27.3, the
same share since every hire has one), and Scavenger, Recruiter, Mentor, Old friends, Nemesis, Diamond in the rough and Burnout
(weight 2) ~0.57%. Bad traits carry about **34%** of the weight and mixed ones ~20% (gender-filtered, 349 per gender; 33% and 22% of
344 before Bully turned bad in v0.27.4), so about a third of hires start with a bad trait, up from about a sixth before v0.27.3
*[Derived]*.

**Trait slots.** The New habit card "needs a free trait slot" and Two new habits "needs two free slots" `[LIVE-CLIENT]` text, so
an employee's trait count is capped. The cap isn't in the client `[GAP]`; fish's "no limit" (U-V27-22) contradicts the card text.

`[STRAT-EXT]` Trait rankings. Both guides put **flat Production traits** first, because that output is unpaid.

| Guide | Best | Good | Fine |
|---|---|---|---|
| Piraterer (tier list, dev server) | Handy, Cosmopolitan, Late bloomer, Craftsman, Laborer, Sociable, Specialist, Lucky charm, Recruiter | Girl power, Band of brothers, Rival, Prima donna, Diamond in the rough, Mentor, Patriot, Expat, Modest, Trainer, Gambler | Improviser, Nationalist, Comic, Loner, Quick study, Veteran, Statist (only at ≥ 20% tax), Loyal, Scavenger, Foreman, Bully |
| Wodkabouter | Sociable, Handy, Cosmopolitan, Craftsman/Laborer, Sprinter, Expat, Specialist, Lucky charm | Late bloomer, Girl power/Band of brothers, Diamond in the rough, Patriot, Modest, Rival, Recruiter, Trainer, Foreman, Mentor | Prima donna, Nationalist, Loyal, Veteran |

Both lists predate v0.27.3. Wodkabouter's Sprinter is gone; Early bloomer is a flat, unpaid +6 Production for hires under 40,
so it belongs with the flat-Production traits at the top *[Derived]*. Neither list knows Talks to Machines (v0.27.4), and
Piraterer's "fine" Bully is a bad trait since v0.27.4. Flat trait Production is still unpaid on the live API (2026-11-02), so the
"unpaid output" argument holds for now (U-V274-1). Happiness traits gained: Statist is +6 happiness (+6% output),
Nationalist +10 (+11 from v0.27.3 to v0.27.4) and Foreman +9 for each coworker. Since v0.28 these are direct happiness, not
Responsibility points, so an employee's shown Responsibility (Personal morale) is only rolled + trained points; no event check
reads Responsibility, so nothing else changed `[LIVE-CLIENT]`.

Wodkabouter's break-evens at an 80% production bonus: **Comic** pays off when the coworkers' Production sums to ≥ 18;
**Bully** (+2 own, −10 to each coworker, 2 Responsibility) pays off while the coworkers' Production stays under ~45, but raises
the quit and bad-event risk. *History (Sprinter removed in v0.27.3):* moving a Sprinter to another company and back daily
re-triggered the +50% at the cost of −5 happiness for the moved employees. That relies on "arrival" counting moves, which isn't confirmed `[GAP]`.

## Wages `[RULE]` (`employees.wage`)

The employee sets the wage, not you. It's paid **automatically every hour**.

```
PP_value     = money value of 1 production point, from raw-material market trades over the last 7 days
hourly wage  = (paid Production / 4) × PP_value × expectation × trait modifier
paid Production = base + trained Production (never trait or coworker Production)
expectation  = 1 + rolled −30% … +30% (per employee);  Greedy × 1.2, Modest × 0.85
daily wage   = paid Production × 6 × PP_value × expectation
```
- In game this is "**Wage expectation**: how much more or less than the market rate they ask for the same stats. It sets the
  wage they are paid" `[LIVE-CLIENT]`. The card shows the expectation as a signed percent (−22.7%, +9.7% …).
- Training Production raises the wage; a **Negotiation** card lowers it "for good". `[OBS]` It subtracts percentage points: −10%
  turned +9.7% into −0.3% (daily wage 6.42 → 5.83).
- `[LIVE-CLIENT]` With no raw-material trades to price a PP, the game uses **0.1**. Expectation spread 0.3 (70–130%). Training
  can push it down to **70%** at the lowest; events can push it up to **160%**. **Climber** drifts it +2% a week. `[OBS]` The
  shown expectation can sit below −30% once Modest is folded in (−39.7% for a Modest employee).
- **Trait Production isn't paid** `[OBS]`, seen in several dev-server tooltips and confirmed live on 2026-11-02 (`LIVEAPI_20261102`):
  in all 82 sampled employees with flat trait Production, the stored wage equals (base + trained) / 4 × PP value 0.099 ×
  expectation to three decimals, including 4 whose wage was recalculated by a card drawn after the v0.27.4 deploy (the API's
  `base.production` is base + trained; the rolled base is `breakdown.production.base`). fish: an employee with output Production 11
  (base 1 + training 1 + 9 from traits) was paid on 2: 2/4 × 0.1228 × 0.773 = 0.0474/h. Another with 11 (4 + 6 + 1 net from
  traits) was paid on 10. The two produced almost the same, but the wages differed 4×. Piraterer: two employees both came to
  0.788 money per paid Production point per day.
- `[CONFLICT]` v0.27.4 (article): "A bug didn't count the production stat given by traits in the expected wage calculation.
  Fixed: Production plain stat from traits now counts toward the expected wage." The live wages above say the **paid** wage
  didn't change. Possible readings: the fix touches only an estimate (a training card's wage change and daily profit, "Higher
  production also raises the wage they ask", or the candidate card), or it reaches wages later. Working stance: paid Production =
  base + trained (live evidence, priority 1) until a wage shows otherwise (U-V274-1). If it ever applies, flat trait Production
  becomes paid like trained Production and the margin formulas below lose their trait-Production term.
- **If you can't pay the full hour, nobody works that hour**, and missed pay lowers happiness.
- Wages are a **money sink**: the money leaves the game. The country takes the **employee tax** (the article's "income tax"):
  "the state collects X% of your employees' wages" `[LIVE-CLIENT]`. Whether the owner pays it on top of the wage isn't settled
  `[GAP]` (U-V27-4); the dev screenshots show payroll = wage × 24 with no tax line.
- Employees **away** because of an event neither work nor get paid `[LIVE-CLIENT]`.

## Production and happiness `[RULE]` (`employees.production`, `employees.happiness`)

Employees produce on their own **every hour**:

```
hourly PP = (Production / 4) × (1 + production bonus) × random 0.9 … 1.1
Production = base + trained + trait/coworker Production
production bonus = sum of the percentages below
```

The bonus parts **add**: "Every percent that scales what their Production banks, added together" `[LIVE-CLIENT]` text, closing
U-V27-3. `[OBS]` dev tooltip: Management +8, Manager +16, Happiness +7.3, Tool +12, Specialization +20 = **+63.3%**.

| Modifier | Value |
|---|---|
| Owner's **Management** skill | +2% per point (1 point + 1 per level) |
| Hired **manager** | +2% per their Management point, max +22%; owner + manager max **+44%** together |
| **Happiness** | ±1% per point away from 50: **+50% at 100, −50% at 0** `[LIVE-CLIENT]` |
| **Tool** | rolled within its rarity: +3–6% (Common) … +46–65% (Mythic); only for its own goods (see Tools) |
| Same good (specialization) | +1% per day producing it, max +20%; kept per good, so switching back resumes the old figure `[OBS]` |
| Company in one of your country's **core regions** | +5% (for every employee, whatever their nationality) |
| Traits | see the trait table above |

- Each hour's output rolls **±10%** `[LIVE-CLIENT]` (`outputVarianceSpread` 0.1). fish's text says 80–120%, but his own "last
  works" list (3.70 … 4.44 around an expected 4.11) fits ±10%.
- The client flags some trait effects as multipliers (× in the table). One dev example (Scavenger −25% inside a −32% total
  with happiness 34) fits them being in the same sum. Not settled for every × trait `[GAP]` (U-V27-3a).
- A **disabled** company produces nothing; its manager earns nothing until it is re-enabled `[LIVE-CLIENT]`. `[VERSIONED]` Since
  v0.27.4 it puts its employees **on hold**: they "will not work, age or train there" (company badge "Paused: nobody works, ages or
  trains here"), drop out of the "to train" list and the training missions, and the game warns before you move or swap someone
  into it. Whether employees on hold keep
  wage expectations drifting, lose happiness or can still get events isn't stated `[GAP]`; no hour is worked, so no wage hour is due
  *[Derived]*. Full storage stops work too, and with it the toolbox rolls (except Salvager).
- *Worked example* `[OBS]` (fish, dev): Production 11, bonus +49.3% → 11/4 × 1.493 = 4.11 PP/h = 98.6 PP/day; at a PP value
  of 0.1228 that is 12.11 money a day against a 1.14 wage, so the game shows a daily profit of 10.97.

**Happiness** `[LIVE-CLIENT]` runs **0–100** and starts at 50. Lowered by: full storage **−10**, an unpaid wage hour **−10**,
**taxes (−1 per 1% employee tax)**, company moves, battles. Specific hits: moving the **company** **−10** for 7 days (API
2026-10-30: "recentlyMoved −10" with a 7-day end date after a company move) · a battle in their region −5. `[VERSIONED]` Since
v0.27.3 firing someone and moving (or swapping) employees between your companies cost **no happiness**. *History (v0.27 →
v0.27.2):* firing gave each coworker −5 for 24 h, an employee move −5 for 7 days, and a moved employee couldn't be fired for 24 h.
Whether a company move still locks firing isn't stated `[GAP]`. `[VERSIONED]` **No deaths in battles** since v0.27.1, "for now"; under v0.27
(2026-10-26 → 27) each battle carried a 1% risk of death, and the client still ships `casualtyChance` 0.01 and the "Killed"
status text, so check the next patch before calling it gone for good (G-ART-4). A manager's daily care gives one employee +5 for 48 h;
repeated care stacks. Traits and events add their own (Patriot +10, Prima donna −10 …).

`[VERSIONED]` **Responsibility** adds **+3 per point** since v0.27.3, and **Loyal** still halves every penalty. Live API 2026-10-30:
base 50 + Responsibility 3 (+9) − employee tax 3 − company move 10 = 46. *History (v0.27 → v0.27.2):* Responsibility cancelled
10% of each loss per point; `[OBS]` dev tooltips: tax −10 and a recent move −10 with Responsibility 3 → shielded +6 → 36 → −14%
output; Patriot +10, tax −10, Responsibility 4 → shielded +4 → 54 (under v0.27.3 the same employees would sit at 39 and 62
*[Derived]*). U-CDX-5: the article says a moved employee loses 10, the client 5 per employee move and 10 per company move (the
employee-move part is moot since v0.27.3). fish
and Wodkabouter wrote −5 for a company move, but a dev tooltip shows "Moved recently −10, 7 days" (move type unknown). The client
stands. How long the full-storage and unpaid penalties last isn't in the client `[GAP]`.

**Quitting**: below **30** happiness an employee may walk out each hour, likelier the unhappier they are, **at most 5% per
hour at 0** `[LIVE-CLIENT]`. They leave without an event ("Walked out: they were too unhappy to keep working for you"). Flight
risk employees start looking at 50; an Anchor never leaves but produces half while below 30. The in-game tooltip adds "below 30
*from your choices*", whose scope (do taxes and events count?) isn't explained `[GAP]` (U-V27-21).

*Derived* (fits the 5% cap and a dev tooltip of 0.6%/h for a Flight risk at 44): **quit chance per hour = 5% × (T − H) / T**,
T = 30 (50 for Flight risk).

| Happiness | 29 | 25 | 20 | 15 | 10 | 0 |
|---|---|---|---|---|---|---|
| Quit chance per hour | 0.17% | 0.83% | 1.67% | 2.5% | 3.33% | 5% |
| Chance to be gone within 24 h | 3.9% | 18% | 33% | 45% | 56% | 71% |

*Derived:* at **20% employee tax** a fresh employee (50) sits at 30 before any other penalty. Since v0.27.3 each Responsibility
point adds 3, so a fresh hire (Responsibility 1–4) sits at **33–42**; under v0.27.2, 2 Responsibility lifted it only to 34.

## Training `[RULE]` (`employees.training`)

One draw per employee per day, plus the **Trainer** pool (`[VERSIONED]` since 2026-10-31: 2 shared sessions per Trainer a day for its
coworkers, refilling at 00:00 UTC; before, +1 for every coworker), **10 Energy**, uses 1 Potential. The hand shows its rarity and
each card's estimated profit per day (since 2026-10-31). `[VERSIONED]` Since v0.27.4 an employee of a **disabled** company can't
be trained. The **rarity is rolled once
for the whole hand**, among the rarities the employee has enough eligible cards in; you see 3 cards of that rarity and keep 1
`[LIVE-CLIENT]`.

**Rarity odds** `[LIVE-CLIENT]` (in-game: "each level moves card odds off Common"). With M = your **Management level** and K = the
employee's Luck (including Lucky charm, Gambler). `[VERSIONED]` Since v0.27.3 Management carries the shifts Leadership had, with the
same numbers (client `skills.managementWeightShiftPerLevel`, fed the skill **level**, not the 1 + level value); from v0.27 to
v0.27.2, M was the Leadership level.

| Rarity | Weight |
|---|---|
| Common | max(0, 55 − 2M − K) |
| Uncommon | 25 + 1·M + 0.5·K |
| Rare | 13 + 0.6·M + 0.3·K |
| Epic | 5 + 0.3·M + 0.15·K |
| Legendary | 2 + 0.1·M + 0.05·K |

The weights total 100 until Common reaches 0 (2M + K ≥ 55); after that each share is weight ÷ total. Confirmed by two dev
screens (taken with Leadership: level 6, Luck 4 → 39 / 33 / 17.8 / 7.4 / 2.8%; level 10, Luck 3 → 32 / 36.5 / 19.9 / 8.45 /
3.15%) and Elereo's table. Examples: M0 K0 → 55 / 25 / 13 / 5 / 2; **M10 K0 → 35 / 35 / 19 / 8 / 3**; M10 K10 → 25 / 40 / 22 /
9.5 / 3.5; M10 K40 → 0 / 52.4 / 29.5 / 13.3 / 4.8.

**Cards** `[LIVE-CLIENT]` (client constants and in-game names):

| Card | Common | Uncommon | Rare | Epic | Legendary |
|---|---|---|---|---|---|
| Drill / Intensive drill (one stat: Production, Responsibility or Luck) | +1 | +2 | — | +3 | +4 |
| Negotiation (expected wage) | −5% | −10% | −20% | — | — |
| Rehab (clear one **bad** trait; always Rare since v0.27.3 `[VERSIONED]`, before also an Uncommon one for a mixed trait) | — | — | a bad trait | — | — |
| Wild card: a random trait, good or bad, revealed once picked, and **+2** to a random stat; since v0.27.3 the card shows the chance of a bad trait. `[VERSIONED]` Rare and +2 since v0.27.4 (Uncommon and +1 before) | — | — | ✓ | — | — |
| **Reroll** (v0.27.4): "Deals a new hand in place of this one, at no extra energy or training potential. Its rarity is rolled again." | — | ✓ | — | — | — |
| New habit (teach a named trait; needs a free slot) | — | — | — (a **mixed** trait until v0.27.4; client `habitRarityByPolarity` now positive only) | a good trait | **Two new habits**: two good traits (two free slots) |
| Second wind (training Potential) | — | — | +2 | +3 | +4 |
| Clean slate: clear every bad trait; dealt only with ≥ 2 bad traits; mixed traits stay | — | — | — | — | ✓ |

- Second wind's gain includes the draw just spent: +2 means **one** session more, +4 three more. Max Potential stays ≤ 15, and a
  card that would pass it isn't offered.
- Negotiation never goes below 70% expectation. Old friends, Nemesis and Sweethearts can't be taught (events only).
- Since v0.27.2 each card shows the **before → after** value. The client never offers a New habit, or a Two new habits pair,
  that clashes with a trait the employee has (or the pair's two traits with each other), and deals a Wild card only while some
  non-clashing trait is left `[LIVE-CLIENT]` (see the incompatible pairs under Traits).
- Training is lost if you close the hand without picking ("Pick one card, the other is lost").
- Since v0.27.3 each card shows the **wage change** it causes. A taught **Specialist** gets the company's good.
- `[LIVE-CLIENT]` The Wild card's shown chance is bad traits ÷ all traits the employee could still gain (not held, not clashing,
  matching their gender, no relationship traits). That ratio implies a **uniform** draw, not one by roll weight *[Derived]*: 14 of
  48 (≈29%) for an employee with no traits since v0.27.4 (13 of 47, ≈28%, before Bully turned bad and Talks to Machines arrived).
- Picking the Reroll card replaces the hand with a new one of a freshly rolled rarity "at no extra energy or training potential"
  (in-game text), so the session still ends with a real card. A weak Uncommon hand that holds a Reroll can thus be re-rolled
  toward Rare/Epic/Legendary odds at no cost *[Derived]*. Whether a rerolled hand can contain another Reroll isn't stated `[GAP]`.

`[STRAT-EXT]` Card priorities (consensus: **good traits first**):

| Guide | Order |
|---|---|
| Wodkabouter, economy players (12+ companies) | good traits > Second wind > Production / Negotiation > Responsibility > Luck |
| Wodkabouter, war players (< 6 companies) | good traits > Production / Negotiation > Second wind > Responsibility / Luck |
| Piraterer | good traits (New habit; Wild card if you dare) > Production > Second wind > Negotiation or Luck > Responsibility; Negotiation beats Production once paid Production is high |
| babeuce | Common/Uncommon: Production, else Negotiation · Rare: Rehab a bad trait, else Second wind · Epic/Legendary: good traits, then Second wind |

These priorities predate v0.27.3, when a Responsibility drill only shielded losses. Now +1 Responsibility is +3% output
(unpaid) while happiness stays under 100, and it also lowers the quit risk and helps event checks through happiness *[Derived]*.

*Derived* (in PP-value units per day, B = production bonus, E = expectation): a **+1 Production drill** adds
`6 × (1 + B − E)`; **Negotiation −x** saves `6 × paid Production × x`; **trait Production +1** adds `6 × (1 + B)`; a **+y% bonus**
(tool, specialization) adds `6 × Production × y`; a **+1 Responsibility drill** (v0.27.3) adds `6 × Production × 0.03` while
happiness is below 100. So Responsibility beats a +1 Production drill once `0.03 × Production > 1 + B − E` (Production 20 at
B +50%, E 100%: 0.6 > 0.5), and Negotiation −5% beats a +1 drill once paid Production × 0.05 > 1 + B − E
(e.g. paid Production 10, B +50%, E 100%: a tie). Wodkabouter's "profitability modifier" is the same `B − (E − 1)`: at B +60%,
expectation −20%, a +1 drill adds 0.48 money a day at a PP value of 0.1.

## Events `[RULE]` (`employees.events`)

78 small stories, some with follow-ups. About **1 per day with 3 employees**, max 3 per day, at most 1 per employee per day.
`[VERSIONED]` Since v0.27.1 an employee can get one **right after hiring** (client `minHiredHours` 0; under v0.27 only after
48 h), and only while you log in at least every **3 days**. You see the odds before choosing;
Management (+2 per level since v0.27.3; Leadership before), happiness and Luck improve them. Ignore one for **36 h** and the
default option is chosen. Since v0.27.3 an event acts on the tool and coworkers present **when it appeared**, even if you change
them before answering. Outcomes: happiness,
bonuses, stats, traits, toolboxes, wooden cases, scrap, money, or the employee leaving or dying.

Constants, costs (in "wage-days"), the check inputs and the events that matter are on [employee-events.md](employee-events.md).

## Tools `[RULE]` (`employees.tools`)

- 6 tool types, each for its own goods `[LIVE-CLIENT]` (client map, matching fish's list):

  | Tool | Goods |
  |---|---|
  | sickle | grain, livestock, Mysterious Plant (`coca`), wood, fish |
  | pickaxe | limestone, iron, lead, petroleum |
  | skillet | bread, steak, cooked fish |
  | hammer | steel, concrete |
  | flask | oil, paper, Pill (`cocain`) |
  | caliper | light ammo, ammo, heavy ammo |

  Each tool rolls its bonus within its rarity's range `[LIVE]`:

  | Common | Uncommon | Rare | Epic | Legendary | Mythic |
  |---|---|---|---|---|---|
  | +3–6% | +7–12% | +13–20% | +21–30% | +31–45% | +46–65% |

  The article's "+3% to +65%" are the two ends of this scale.
- **Toolboxes**: each worked hour an employee has a **0.1% chance per Luck point** to find one `[LIVE-CLIENT]`;
  `[VERSIONED]` no cap since 2026-10-29 (unannounced, client and UI text only; was max 2%); events give some too. Odds: Common 35%, Uncommon 37%, Rare 20%, Epic 6.5%, Legendary 1.3%, Mythic 0.2%
  (sums to 100%; article only). A Scavenger doubles the chance at −25% output (before 2026-10-29 also the cap, 4%); a Salvager still finds boxes with
  full storage. Found boxes wait for a "Claim the toolbox" click; the workforce panel shows the expected boxes per day `[OBS]`.
- A tool lasts about **500 worked hours**. It shows a **durability %**, which some events raise or cut (see
  [employee-events.md](employee-events.md)); worn out, it gives no bonus until replaced.
- Tools can be dismantled for scrap; tools and toolboxes **can't be traded or sold**.
- `[VERSIONED]` Since v0.27.4 moving an employee to a company whose good their tool doesn't fit **sends the tool back to your
  inventory** (before, it stayed in their hands, unused). Equipping a tool opens the same window as equipment and shows the
  Production of employees already holding one; the **?** next to an employee's tool lists every tool and the goods it boosts
  ("A tool only boosts an employee in a company producing one of the goods listed under it").
- *Derived:* the tool bonus adds percentage points on the employee's whole Production, so a tool is worth most on the employee
  with the **highest Production stat**, not the highest current output (Wodkabouter, babeuce agree) `[STRAT-EXT]`. Handy (+40%
  with any tool) makes even a Common tool count.
- `[STRAT-EXT]` babeuce and Wodkabouter say Legendary and Mythic tools earn more scrapped than used. Neither shows the numbers,
  and the scrap yield per rarity isn't documented `[GAP]`; compare `6 × Production × bonus × 21 days` (one tool life, in PP)
  with the scrap value before scrapping.

## Managers `[RULE]` (`employees.managers`)

A manager is a player hired to run another player's company, now the **only way to work for another player**. A "Management
point" is the skill's value: **1 + 1 per level, 11 at level 10** `[LIVE-CLIENT]`, so 11 × 2% gives the +22% cap (U-V27-5). "Every
manager has at least 1 point, so even one with no Management level gives 2%" `[LIVE-CLIENT]` text.
- One manager job per company; the owner sets the pay **per Management point**, kept within **80–120% of the average manager pay**.
  Applying hires you at once. The manager job market opens at level 10.
- Effect: +2% employee production per Management point, max +22% (stacks with the owner's own, max +44%).
- Once a day the manager picks one employee for +5 happiness for 48 h; boosts stack.
- Paid every hour: the manager clicks **Collect**, and the **manager tax** of the country the company sits in is **withheld from
  that pay** `[LIVE-CLIENT]` text (a Congress-voted tax that starts at the country's income tax). On the dev server the same
  tooltip still said "income tax" `[OBS]`.
- **24 h lock** after hiring: neither side can end the contract. A disabled company pays its manager nothing.
- `[VERSIONED]` v0.27.1 fixes: **manager wages divided by 10** ("better to start low and increase over time"), managers are
  **paid every hour even in a company with no employees**, and they can leave a paused company. Manager offers now show an
  estimated profit. The 80–120% band is unchanged.
- `[OBS]` pay levels (market prices, not rules): dev server 0.472/h at 8 points (11.3 a day, 1.4 per point); on launch day
  Wodkabouter saw about **0.5 a day per Management level**; on 2026-10-27 09:00 UTC, before the fix note, a top manager cost
  **2.2–3.3 a day** after pay "dropped sharply after the first day" (guide `6adfb0879f5bbacb371170b9`). Recheck after the ÷10.
- *Derived:* the daily **care** (+5 for 48 h, once a day) averages +3.3 happiness per employee in a 3-employee company, i.e.
  +3.3% output regardless of the manager's level. So a low-level manager can be good value for the pay (Wodkabouter).

## Derived economics `[Derived]` — check against live data

These follow from the rules above. The 10%-per-hour Energy regen is confirmed (`regenDividedBy` 10); the PP unit is assumed
unchanged. The in-game "daily profit" is the same estimate: a day of output at the PP value minus a day of wages (and, for a
company, its manager) `[LIVE-CLIENT]` text. `[VERSIONED]` Since v0.27.3 it prices the output at **the produced good's** PP value,
not the average of all goods, so it now follows the per-good formula below.

- **Profit per employee-day** (raw-material company, where a PP is worth about `PP_value`):
  `6 × PP_value × [Production × (1 + B) − paid Production × E]`, minus any tax the owner bears. Without trait Production this is
  `6 × PP_value × Production × (B − (E − 1))`: with no boosts, a 100%-expectation employee only breaks even, a 70% one keeps 30%,
  and a 130% one needs +30% of boosts. For processed goods, replace `PP_value` in the output term with the product's net value
  per PP, `(price − input cost) / recipe PP` (F-BASE-PER-PP).
- **Value of a Management level** (owner): `Σ Production of all employees × 6 × PP_value × 0.02` a day. Use the Production stats
  (incl. traits), not the output. Wodkabouter: 36 employees at Production 12 → about **5 money a day per level** at PP 0.1, versus
  about 12 for a point of Production or Energy spent on self-work. He aims for Management at about half the Production/Energy
  levels with 12 full companies, less with fewer employees. Since v0.27.3 a Management level also moves training-card odds off
  Common and adds +2 to event checks (Leadership's old job), so these ratios undervalue Management for players who train a lot
  *[Derived]*.
- **Taxes hit output twice**: every 1% of employee tax costs 1 happiness, which is −1% output (less with Responsibility). A 15%
  tax turns 50 happiness into 35 (−15% output) and moves the employee toward the quit threshold of 30.
- **Country tax policy** `[STRAT-EXT]` (Wodkabouter): +1% tax ≈ −1% output, so revenue and lost output roughly offset. High-
  Responsibility crews tolerate higher taxes; employees with flat Production traits lose unpaid, untaxed output, so they favour
  low taxes. The best rate depends on the country's crews.
- **Scale**: base output is `6 × Production` PP per day if they work every hour, so 6–24 PP/day for a fresh hire. A trained
  employee reaches far more (dev examples: Production 11–18 with +50–123% bonus → 99–241 PP/day). Piraterer's best dev employee
  made as much profit as an AE6 company; babeuce says employees can match the Automated Engine `[OBS]`. Self-work at 30 PP per 10
  Energy is larger per Energy spent, but employees add output without Energy beyond hiring and training.
- **Shelf life**: from 18–45 an employee reaches 65 in 20–47 days of work or training (since v0.27.4; calendar days before), so
  idle days and a disabled company no longer use it up. Potential 3–10 gives 3–10 training days unless Second wind
  adds more. A young candidate with high Potential is the better hire when the hint shows it.
- **Toolbox rate**: Luck L gives `1 − (1 − 0.001 L)^24` ≈ `0.024 × L` toolboxes per 24 worked hours (Luck 4 → 9% a day, one every
  ~10 days, matching the in-game "about 9% a day"; no cap since 2026-10-29, so Luck 30 → p = 3% an hour, about 0.5 a day;
  until then the 2% cap at Luck 20 → about one every 2 days). Three employees at Luck 4
  find about **2 a week**. A tool's ~500 worked hours ≈ 21 days of continuous work.
- **Energy budget**: hiring (10), candidate rerolls (10, 20, 40 …), firing within 24 h (a reroll until v0.27.1) and training (10 per draw) compete
  with self-work for the same bar. Training 36 employees once costs **360 Energy a day**, while a 200-Energy bar refills 480 a
  day. Three employees trained daily cost 30 Energy, i.e. 3 self-work actions.
- **A manager pays off** when `2% × Management points × (value of the company's daily employee output)` plus the care effect
  exceeds the daily pay. With at most 3 employees per company, managers mostly matter for strong, fully staffed companies.

## Strategy `[STRAT-EXT]` (community guides, launch day 2026-10-26)

Advice, not rules. Most of it was written before or on launch day, from the dev server.

- **Day one** (Nadim, Luminous, Piraterer): use the free skill reset (Entrepreneurship is refunded) and the free company move to
  bring companies home; hire, but reroll little; keep cash for wages; upgrade the Break Room once you have 20 steel (L3: 100
  steel in total); log in at least every 3 days so events keep coming; Congress should agree before picking a government type
  (30-day lock).
- **Location**: a core region of your own country (+5%, taxes stay home), low employee and manager tax, and **safe from battles**
  (−5 happiness per battle; the 1% death risk these guides cite was switched off in v0.27.1 "for now"). babeuce would leave a
  frequently attacked region (his example: the Balkans).
- **Hiring**: the youngest candidate first (an extra 20+ working days), then high Potential (8+), then good traits; base stats
  matter less. babeuce: reroll only if nobody is under 35 and all look bad, never twice; fire a bad hire the next day (his "after
  24 h, or it counts as a reroll" no longer applies: firing is free since v0.27.1). Piraterer: hire in every company, reroll once or twice at most, swap bad ones later; a high
  wage hints at high Production or a high expectation, so war-mode players can pick high-wage hires and cut the wage with
  Negotiation. A Potential-3 hire with no useful trait is a candidate for firing (fish).
- **Pace**: hire one employee and train it before hiring the next, because hiring and training share Energy (babeuce). Day-one
  losses are normal; trained employees turn a profit later.
- **Don't move employees** without a reason: they lose happiness, and switching goods restarts specialization for the new good
  (babeuce). Avoid full storage, firing, and high-tax regions (fish).
- **War players**: don't hire many employees or upgrade Break Rooms if you'll cut active companies for a war build within ~2
  weeks (fish). Piraterer: a Luck-heavy crew can farm toolboxes for milestones and scrap.
- **Managers** (babeuce): hire a manager you know, ideally a war-mode friend (a "buddy system"); the manager should care for the
  unhappiest employee and boost the best earners. A low-Production company can lose money on a manager.
- **Don't chase the perfect employee** (fish): they retire, quit or die, and traits, events and cards are random.
- Skill builds: see [skills-and-respec.md](skills-and-respec.md#v027-builds-strat-ext).

### After the deploy `[STRAT-EXT]` / `[OBS]` (guides of 2026-10-26/27, see [guide-articles-ledger.md](guide-articles-ledger.md))

The first guides written on the live game. Their money figures are **market snapshots of 2026-10-27** (7-day prices to
2026-10-25); recompute before relying on them.

- **Keep or fire** (`6adfb0879f5bbacb371170b9`, "Keep him or fire him?", the most-bookmarked v0.27 guide). Open the employee
  card: next to happiness sit two chips, the **bonus chip** (pickaxe) and the **wage chip** (coins). Green daily profit: keep.
  Red: keep if the wage chip is not above the bonus chip; wait if it is up to 20 points above; fire if more. Reason: the bonus
  chip rises by 1 point a day for 20 days (specialization), so a 12-point gap closes in about 12 days. This matches the profit
  formula below, where the margin is `B − (E − 1)`.
- **Energy is the real price** of a hire or a training: the same 10 Energy spent on self-work makes about 3–6 money (same guide).
  The admin's v0.27.1 note agrees that **Energy + Production** (self-work only, no employees) is a viable build.
- **Traits** (same guide, at its "ordinary worker" of Production 3 after 20 days): an ordinary worker nets ~0.36 a day; Specialist,
  Craftsman (factories) or Laborer (raw goods) add ~2.2; a Loner working alone ~2.28 versus ~1.09 for three ordinary workers, so
  never give a Loner coworkers; buy Break Room L2/L3 (100 steel in total, ~198 money then) only for workers with good traits.
  Fire or retrain Homesick (abroad) and Xenophobe (with foreign coworkers).
- **Training card by wage chip** (same guide): a cheap worker (wage chip −20% or lower) takes Production; an expensive one (+20% or
  higher) takes Negotiation, because a Production card raises his wage too. Consistent with the drill vs Negotiation derivation
  above.
- **Product choice** `[OBS]` 2026-10-27: per ordinary worker, cooked fish, steak and bread ~0.9 a day; iron and steel ~0.3; grain
  and livestock lose money even after 20 days of specialization.
- **Managers** (same guide, before the v0.27.1 ÷10 fix): with three ordinary workers a manager adds ~1.4 a day, less than he
  cost; with three Production-6 workers ~2.8, enough to pay for himself.
- **Hiring order** (`6adf9ec5c8c21508478c4545`, "Don't Panic"): hire an 18–23-year-old if one is offered, else wait for the
  00:00 UTC candidates; train; upgrade the Break Room in companies that already have a worker and match traits (e.g. Girl Power
  wants female coworkers); reroll at most once. Same as the "youngest first" advice above.

### After v0.27.3 *[Derived]*

Consequences of the 2026-10-29 changes; not yet tested by any guide.

- **Skills**: the refunded Leadership points and the free reset (no cooldown) go to Management, which now holds the production
  bonus, the card odds and the event odds. The economy build is Energy, Production, Companies and Management.
- **Hiring**: pick by Production and the readable wage expectation; the trait and Potential are still hidden, so age (shelf life)
  still matters most. Every hire now has a trait, a bad one about a third of the time.
- **Culling is cheaper**: a bad hire can go after 12 h, and firing no longer costs the crew happiness.
- **Rearranging is free**: transfers cost no happiness, so arrange crews around coworker traits (Loner alone, Sociable, Girl
  power, Cosmopolitan, Prima donna, Mentor). Still a cost: Creature of habit (−30% for 3 days), and Veteran, Diamond in the rough
  and Burnout restart their tenure; moving to a company with another good uses that good's specialization figure.
- **Responsibility** is worth +3% output per point, so a Responsibility card is no longer filler; a Foreman's +9 per coworker is direct happiness since v0.28, worth the same.

### After v0.27.4 *[Derived]*

Consequences of the 2026-11-02 changes; not yet tested by any guide.

- **Talks to Machines** pays most in a company with a high Automated Engine and nobody else. The engine makes `level × 24` PP a
  day with no production bonus (U-V27-7, closed), so the trait adds that again: **+168 PP a day at AE7** (≈ 16.6 money at a PP
  value of 0.099), about what a Production-28 employee makes before bonuses, while its wage depends only on its own paid
  Production. Give it the company to itself (a higher Break Room is wasted there), pair it with Loner if possible, and keep coworker
  traits away (they clash anyway). Unconfirmed live `[GAP]`: whether a manager or an employee away on an event breaks
  "working alone", and whether the doubling needs the employee to work that hour.
- **Ageing per worked day**: shelf life is now counted in working days, so pausing (a disabled company, unpaid hours, days you
  don't train) no longer burns it. A war player who must disable companies keeps the crew's age frozen until re-enabled.
  Presumably a day with a single worked hour or one training still ages them a full year (U-V274-6).
- **Training**: the Wild card is rarer (Rare weight 13 vs Uncommon 25) but stronger (+2 stat), and competes with Rehab, Second wind
  +2 and Negotiation −20% in Rare hands. Mixed traits (Craftsman, Laborer, Sociable, Rival, Comic, Mentor, Prima donna, Gambler,
  Scavenger, Anchor) can no longer be taught, only hired or drawn from a Wild card. A Reroll in an Uncommon hand is worth taking
  when the other two cards are weak.
- **Events**: cheap paid answers now usually beat free ones (the 23 cut coin costs run 0.1–1.9 wage-days, most under 0.75); Van Race and Gambling Debts have
  positive expected value at their base odds ([employee-events.md](employee-events.md#evaluating-an-event-derived)).
- **Bully** is now a Rehab target; with the new bad-trait weight about a third of hires still start with a bad trait.

## Management checklist `[STRAT-RO]`, revised for v0.27

Keep money for the hourly payroll (a missed hour stops everyone and lowers happiness) · keep storage from filling (it lowers
happiness, stops the toolbox rolls, and full storage stopped production before v0.27) · watch happiness against the tax rate ·
don't fire impulsively (a new hire is locked for 12 h; coworkers lost 5 happiness until v0.27.3) · train while Potential lasts · answer events within 36 h. The old "don't hire
too early" advice was about player wages and no longer applies as-is; recompute with the profit formula above.

## Moderation `[RULE~]`

The pre-v0.27 rules on abnormal wages and reciprocal minimum-wage employment ([account-rules-and-security.md](account-rules-and-security.md))
targeted player wages. Manager pay is the remaining player-to-player wage; its 80–120% band is enforced by the game. Whether
moderation applies the old 0.8×–1.2× indicator to manager pay isn't stated `[GAP]`. (The in-game rules text still lists
"low-wage labor, lower than 0.8× and above 1.2× the normal salary" `[LIVE-CLIENT]`.)
