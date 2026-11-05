# Update process — adding patch notes, guide editions and live drift without losing history

## Triggers

- New official patch notes or announcements.
- New edition of the Romanian guide (or another guide).
- `python .claude/skills/warera-config/scripts/check_config.py` reports drift in the live config.
- Repeated live observations contradicting a stored value.

## Workflow

1. **Ingest** the source. Register it in `data/mechanics.yaml → sources` with a new ID (e.g. `PATCH_0_26_2`), title, date,
   `game_version`, and `priority` (official patch notes = 2, official docs = 3, guides = 4–5, community estimates = 7).
2. **Classify** each statement: game mechanic / value / formula / community strategy / Romanian policy / historical / observation.
   Strategy and policy go to `ro.*` IDs (or only to prose); observations to `obs.*`.
3. **Identify affected mechanic IDs** (`grep -n "<keyword>" data/*.yaml references/*.md`). If none exists, create one with a stable
   dotted ID in the right category.
4. **Record the previous value as history**: set its `status: historical` and `effective_to` (only if the patch states the date;
   otherwise leave it out and add a note). Never delete or edit the old value.
5. **Insert the new value** as a new `values[]` entry: `status: current` (or `scheduled` for future changes), `changed_in`,
   `effective_from` (exact UTC if known), `source`, `confidence`, `last_verified`, `notes`.
   - Scheduled change: add the new entry with `status: scheduled` and `effective_from`; leave the old one `current` and set its
     `effective_to` to the same instant. After the date passes, flip statuses (old → historical, new → current) — resolution is
     already correct before you do.
   - **Scope change, no new number** (e.g. v0.26.2: no bunker in civil wars): close the old entry the same way, copy its value
     map into the new entry and add an explicit key (`civil_war: not_applied`). Cases the patch doesn't mention go in `notes` as
     `[GAP]`, never into the value. Then remove the outdated claim from the current entry's notes. The old entry keeps it as history.
   - **System removed** (e.g. v0.27: deposits, ethics): close the old entry and add a new one whose value starts with `"none - "`
     and names the replacement. A **brand-new system** gets a mechanic ID whose only entry is `scheduled`. The validator then warns
     "no value in force now" until the date passes; that's expected, not an error.
   - **A removed system leaves advice behind under other names.** For v0.28 (travel off) grepping "stamina|travel|wooden case"
     missed current-tense lines about "launch regions", "front distance", "reserve oil", "move to the battle region" and
     "where attackers must stand" in scenarios, checklists, data-model, snapshot-schema and evaluation; the reviewer found them.
     Grep the consequences (costs, prerequisites, checklist steps) as well as the name, and data files as well as prose.
   - **Value changes shape** (e.g. v0.27: `bonus.patriotic` went from a number to a map by government type): every script that reads
     the ID breaks or silently drops the part once the date passes, while tests at today's date still pass. `grep -n "<id>" scripts/*.py`,
     run each consumer with `--as-of` after the date, and make selftests that replay old-rule scenarios pin a pre-change date.
   - **Back-filling history breaks old dates the same way.** A historical entry that lacks keys the scripts index (e.g. bunker
     entries before v0.25.0 without `L1`..`L5`), or a mechanic that resolves to `None` before it was introduced (e.g.
     `bonus.total_floor` before v0.25.5), crashes consumers only for `--as-of` dates in that window, while the selftest stays green
     (2026-10-25). After adding history, run each consumer with an `--as-of` date before the earliest new `effective_from`, and
     guard missing keys/`None` with a warning instead of indexing blindly.
6. **Conflicts**: if the new source disagrees with a higher-priority one, don't replace — mark `disputed`, add a `conflicts` entry,
   and add/refresh a row in [unresolved-mechanics.md](unresolved-mechanics.md). Resolve only with newer **authoritative** evidence.
7. **Update prose references** that cite the value (routing in SKILL.md §5; `grep` the mechanic ID and the old number). Mark
   superseded statements `[VERSIONED]` and point to the history; move removed systems to [deprecated-mechanics.md](deprecated-mechanics.md).
8. **Update formulas** in [formulas.md](formulas.md) and the calculators if a formula changed. Version-gate the code by reading values
   through `wlib.resolve(id, as_of)` rather than hardcoding; never encode a guessed formula.
9. **Validate**: `python scripts/validate_mechanics.py` (must report 0 errors; review warnings) and
   `python scripts/combat_bonus_calculator.py --selftest` (update `reference_scenarios` only if the source publishes new totals).
   The validator reads only `mechanics.yaml`. Parse any other edited data file with
   `python -c "import sys; sys.path.insert(0,'scripts'); import wlib; print(wlib.load_yaml('data/patch-history.yaml')['patches'][0])"`.
   PyYAML may be missing, and `wlib` falls back to its subset parser. Spot-check `wlib.resolve(id, date)` on one date before
   and one after the change. It returns the whole entry (status, source, notes …), so read `wlib.resolve(id, date)['value']`;
   `.get(key)` on the entry itself silently gives `None` (2026-11-01).
   **The subset parser accepts broken quoting**: on 2026-10-29 a notes line ending `…[OBS]." Closed by v0.27.2 (…)."` passed
   with 0 errors. Copy the skill to the scratchpad before editing and check every changed line for an odd number of `"`. On
   a CRLF file, `line[:-1]` strips the `\r`, not the closing quote (that's how the line above broke).
10. **Downstream impact**: list scripts/analytics affected (calculators reading the ID, `snapshot-schema.yaml` bounds such as
    `deposit_bonus_percent` warn range or `battle.round` max, the bot's cogs under `cogs/` that hardcode the value, sibling
    `warera-config` quick table). Note them in the CHANGELOG entry.
11. **CHANGELOG.md**: add an entry (date, source, mechanic IDs changed, conflicts opened/closed, files touched).
12. Bump `registry_as_of` in `mechanics.yaml` and the `as_of` of any data table you edited.

## Example — a patch changes the alliance full bonus on a future date

```yaml
  - id: bonus.alliance
    values:
      - value: {full_bonus: 20, full_bonus_max_share_percent: 10, slope_per_point_above: -4, floor: -20}
        status: current
        effective_to: "2026-11-01T00:00:00Z"
        source: [GUIDE]
        ...
      - value: {full_bonus: 15, full_bonus_max_share_percent: 10, slope_per_point_above: -3, floor: -15}
        status: scheduled
        changed_in: v0.99.0
        effective_from: "2026-11-01T00:00:00Z"
        source: [PATCH_0_99_0]
        confidence: high
```
`combat_bonus_calculator.py --alliance-share 12 --as-of 2026-10-25` uses the first; `--as-of 2026-11-05` the second.
(Illustrative values only — not a real patch.)

## Official patch notes published as in-game articles

- Official notes are WarEra articles. Given `https://app.warera.io/article/<id>`, fetch
  `article.getArticleById {articleId}` (see the `warera-api` skill) and check `category == "official"`. Record the article ID as the
  source reference.
- **Titles often carry no version number.** Example: "Little update about Civil Wars & Moderation Survey" (`6accd48eca2ce961eea235ff`,
  2026-10-14), which the user calls **v0.26.2**. So grepping the skill for a version string can miss a patch that's already
  recorded. To check whether an article is integrated, grep for its **ID**, title keywords **and** the mechanics it touches. When
  you record one, write its version label (as the user gives it) and its ID side by side, so the next version grep finds it.
  `getArticleById` worked without an API key (observed 2026-10-25), and the article is at `result.data` in the response.
- Use `publishedAt` as `effective_from` at **day precision** (user decision 2026-10-13) when the post follows the deploy. **Exception
  (2026-10-25, v0.27):** when the text itself announces the deploy time ("Update will happen tomorrow (26/10) around 14:00 UTC"),
  use that time, record the entries as `scheduled`, and note `publishedAt` beside it. Confirm after the deploy.
- Titles ending in "(UPDATED)" are edited in place (`updatedAt`). An edit does **not** mean every value in the text is current.
  v0.25.0-beta (published 2026-06-10, edited 2026-10-12) still lists an alliance bonus, Sworn Enemy upkeep and Pacification value
  that later changed.
- "Newer official patch notes" outrank the guide only when they are newer. An older official patch never overrides a later guide
  edition or a live observation. Record its value as `historical`, with the change date unknown unless a source dates it.
- **Bulk source:** every patch note and announcement is an article by the game admin (author `6813b758efecdf9bab195068`). The
  user calls these the most trusted source, newest first. Fetch them all with `article.getArticlesPaginated {type:"last",
  limit:100, userId:"6813b758efecdf9bab195068"}` and follow `nextCursor`. On 2026-10-13 that was 100 articles covering
  v0.15.0 → v0.26.1, about 145 KB of text, small enough to read in full. Save them to the scratchpad and grep by keyword.
- **Also fetch the whole `official` category** (`{type:"last", limit:100, categories:["official"]}`): v0.25.1 exists **only** as a
  staff article there (`6a2d86d5ab0e47773095df00`), so a `userId`-only fetch misses it. On 2026-10-25 the category held 81
  articles: 55 by the admin, the rest translations (es, de, pt, tr; sometimes published a day or two before the admin's own post)
  and staff announcements. Translations are not new versions; use them only to date a patch earlier.
- **Ingesting several patches:** process them newest first and let a newer patch override an older one where they overlap
  (user rule 2026-10-25). Example: v0.25.1 turned mission auto-claim on, v0.25.5 turned it off, so "auto-claim" is history, not
  current. Before marking an older patch's rule `current`, grep the later patches for the same mechanic.
- **HTML pitfall:** the article editor turns a `*…*` pair into `<em>…</em>`, so formulas lose their multiplication signs once tags
  are stripped. Count the stars: v0.20.0's raw `((population <em>avgLevel) / 20) </em>* 0.95` keeps one `*` after the pair, so the
  original likely had `** 0.95` (a power), not `* 0.95` (U-DEV-1a). When a formula looks broken, read the raw `content` HTML.
- **`updatedAt` doesn't mark content edits.** On 2026-10-25 the 8 newest admin articles all showed `updatedAt` between 10-19 and
  10-25, including `6accd48eca2ce961eea235ff`, whose rules matched what had been recorded on 10-13 (`updatedAt` probably
  moves with likes/comments; unverified). Rely on "(UPDATED)" in the title and
  diff the content. When the post dates the patch ("patched yesterday"), compare `createdAt` with `publishedAt` to bound the day.
- **Future-dated articles:** `getArticlesPaginated` can return an article whose `publishedAt` is still in the future (v0.27,
  `6ade08f7899288ce9f0bfe36`, seen 2026-10-25 with publishedAt 2026-10-28). Treat it as an announcement. Its text may still
  change (v0.27 was edited the day it was created: `updatedAt` 19:04 vs `createdAt` 13:49), so re-fetch and diff it before
  flipping its `scheduled` entries. `publishedAt` isn't necessarily the deploy date: v0.27's text announced the 26th, two days
  earlier than its `publishedAt`.
- **After a scheduled patch deploys:** re-run `check_config.py`, compare the new config with the scheduled values (Break Room
  levels, skill tables, candidacy level, starting oil …), flip `scheduled` → `current` and the closed entries → `historical`,
  correct `effective_from` if the deploy slipped, and remove the "`[SCHEDULED]` until confirmed" banners from the topic files.
  How it went for v0.27 (2026-10-26), reuse it:
  1. Confirm the deploy cheaply first: the live client bundle (below) has the new constants hours before you'd notice in game.
  2. Run `check_config.py` **without** `--update` (the snapshot belongs to `warera-config`); save its diff to the scratchpad and
     register it as a dated source (`LIVECFG_V027`).
  3. `.claude/` is git-ignored, so there is no `git diff` to fall back on: **copy `mechanics.yaml` to the scratchpad first**, then
     flip with a script that splits the file into value blocks (`      - value` … next block or `  - id:`). Anchor each block on
     its `value:` line, never on `status`/`source` lines: those repeat across mechanics (on 2026-10-30 the v0.27.1 entries of
     `employees.hiring` and `employees.events` had identical status, date and source lines). Only `status:` lines
     change, plus `last_verified` and the new source **on entries the config or client actually shows**. Diff the backup
     afterwards: only `status`/`source`/`last_verified` lines may differ.
  4. Entries backed only by the article (server-side rules: government types, bonuses, starting bag …) become `current` without
     `last_verified`. The validator then warns "active value without last_verified" for each (18 for v0.27). That warning is the
     honest signal; don't silence it with a fake date.
  5. Read the config diff for **changes the article never mentioned** (v0.27: bounty cap `maxBountyWageMultiplier` 6 →
     `maxBountyPpMultiplier` 9; alliance leave cooldown suspended to 2026-10-30) and give each its own entry or note.
  6. Run every script that reads a flipped ID with `--as-of` after the deploy (here `combat_bonus_calculator.py` plain and with
     `--government`), then the selftest.
  7. Prose: swap `[SCHEDULED …]` tags for `[RULE]` (or `[LIVE]` where the config shows the value), then
     `grep -n -E "until (the deploy|confirmed)|after the deploy|announced for|still pending|\(scheduled\)"` and rewrite each banner by
     hand. Check line endings at the end (Git Bash `sed -i` and Python text mode both turn CRLF files LF; see `warerabot-dev`).
- **Live client bundle as a source** (`[LIVE-CLIENT]`, no API key): `curl` `https://app.warera.io/`, take the
  `/_next/static/chunks/pages/_app-*.js` path from the HTML, download it (~4 MB) and search it with Python. It ships the client's
  copy of gameConfig (`regenDividedBy`, `featureUnlockLevels`, `prestige`), the skill ladders (the module with `baseValue`,
  `increment`, `unlockAtLevel`), and the v0.27 employee constants (`traitsPerEmployee`, trait table, `storyteller` event settings).
  It has **client-side constants only**; server rules (tool bonus odds, Break Room levels, wooden-case odds) need the config or UI.
  `dev.warera.io` serves the next beta build the same way, so upcoming patches can be read a day early (as the codex did for v0.27).
  - The same bundle also holds the **training-card config** (search `secondWindGains`), the **tool → goods map** (`[a.SICKLE]:[`),
    and every **employee event definition** (start at `x={[a.Hj.NIGHT_SHIFT_TINKERER]:{code`: pool, weight, cooldowns, per-option
    `check {type, base, traitMods}`, outcomes; helper `l(target, delta, days)` = happiness for `24 × days` hours).
  - **In-game English text** is not in `_app`: UI strings are lingui ids (`r.x6,{id:"zXV9VT"}`). The locale catalogs are async
    chunks listed in `/_next/static/chunks/webpack-*.js` (the `r.u` map of chunk id → hash). Download them all and keep one whose
    `"++8kYz"` value starts with "Punishments" (English; several locales fall back to it). The payload is `JSON.parse('…')`:
    decode the JS escapes (`\xNN`, `\uNNNN`, `\\`, `\'`) **before** `json.loads`, and write with `errors='surrogatepass'`. Then
    grep the catalog for tooltip wording; it settled the v0.27 bonus stacking ("added together").
- **Feature flags for scheduled switch-offs (v0.28, 2026-11-04):** the config can carry booleans for a system the admin turns
  off later (`mapTravel.{movementEnabled, travelHomeEnabled, mapCasesEnabled, positionMarkerEnabled, staminaBarEnabled}`,
  `battle.locationGateEnabled`). `tools/agent-cli gc mapTravel` reads them live. When an article says "in N days", record the
  entries `scheduled` at day precision and flip them when the flag flips; the client hides the matching UI behind the same flags
  (search the bundle for the flag name to see what goes). The warera-config snapshot predates these keys.
- **Dating a silent patch (2026-11-01):** no article, so bound the deploy with live evidence. The UI catalog's git history
  (vatoutou/warera-translation) shows when a string appeared (commit time), and the API's own state can date it to the day: e.g.
  `charmLuck.until` = next reset + 1 h, so a value expiring 2026-11-01T01:00Z was handed out on 2026-10-31. Use the deploy day as
  `effective_from`, label the version `silent-YYYY-MM-DD` (or `unannounced-…`), and register the community report at priority 7
  with the live reads as the real basis. A catalog diff over the gap also catches silent changes nobody reported (the toolbox cap).
- **Silent changes exist:** some values changed with no article (Sworn Enemy upkeep ×2 → ×10, Fanatic Expansionist Pacification
  Center +2.5% → +3%). If no article mentions a change, its date is unknown. That doesn't mean the value never changed.

## Verifying a patch against the live game (v0.27.2, 2026-10-29)

A short patch note ("income doubled", "no more contradicting traits") is worth testing before you record it. All read-only; put
the scripts in scratchpad files, call the API at about 1 request/s, and register each check as a dated priority-1 source
(`kind: trusted_script_output`, e.g. `LIVECFG_V0272`, `LIVEAPI_20261029`).

- **Which config keys did the patch add?** Run `check_config.py` without `--update` (its snapshot is still pre-v0.27, so the
  diff is large) and compare the added / removed / changed counts with the last registered live check: 248 / 65 / 63 on
  2026-10-26 became 250 / 65 / 63, and the two extra keys were exactly the patch's income multipliers.
- **Check numbers by ratio on the API.** `region.getById` has an `income{development, strategicResourcesBonus, …, govType,
  total}` block in coins **per hour** (the client shows ×24 as "Estimated daily income"). `income.development × 24 /
  development` gives the multiplier (2.000 in all 40 regions); `strategicResourcesBonus × 12` matched the initial country's
  `coreDevelopment` from `country.getAllCountries`, which settled "development" = core, not current or average. The `govType`
  line shows how government types stack (on top of the ×2). Find the unit in the client first: search the bundle for the
  field name and look for `*24`.
- **Check employee rules on real rosters.** `company.getCompanies {perPage: 100}` → `employee.getCompanyRoster {companyId}`
  with the bot key. `trainingHistory[]` (`outcome.gained`, `traitTo`, `traitTo2`, `pickedAt`) separates trained traits from
  traits rolled at hire, and comparing `pickedAt` with the patch time shows whether the patch cleaned up existing state (it
  didn't: pre-patch clashing pairs were still there). Each employee's `happinessBreakdown.contributions[]` names every happiness
  term (`responsibility`, `incomeTax`, `recentlyMoved` with an `until` date …), which checks a happiness rule directly (v0.27.3:
  "responsibility +9" at Responsibility 3). A Specialist's trait `arg` against `estimate.itemCode` shows which good it boosts. For
  quick calls use the warera-api `probe.py`; a script of your own needs a `User-Agent` header (plain urllib gets 403).
- **Diff the whole employee-constants object, not just the article's items.** In the client it starts at `traitsPerEmployee:`
  and holds `fire`, `move`, `training`, `luck`, `responsibilityHappinessPerPoint` and `skills`; the event-check constants sit
  beside the storyteller settings (`check:{skillPerLevel…}`). Record their values in the live-client source's notes (as
  `LIVECLIENT_V0273` does; the scratchpad doesn't survive the session) and compare on the next read. v0.27.3 changed six of these keys with no config change apart from the vanished `leadership` skill, and the client
  confirmed details the article left out (card odds take the Management **level**; `statPivot` 3 → 0).
- **Check wage claims on rosters** (v0.27.4, 2026-11-02): implied paid Production = `wage × 4 / (PP value × wageExpectation)`
  (`gameStat.getPpMoneyValue`), compared with `breakdown.production.base + trained` and with the flat `contributions[]` added.
  Split employees by `updatedAt` / `lastTrainedAt` after the deploy: a card drawn after it recalculates the wage. Note that the
  roster's `base.production` already includes trained points.
- **Check map rules on the live region graph** (v0.28, 2026-11-04): `tools/agent-cli probe region.getRegionsObject '{}' --chars 99999999`
  returns every region with `neighbors` and `isLinkedToCapital`. The first output line is a header that itself contains `{}`, so
  parse from the second line (`json.JSONDecoder().raw_decode`). Count links, check symmetry, BFS from every region for the
  longest shortest path (20 on 2026-11-04, while the skill still said 19) and spot-check announced link removals by region code.
- **Client lists change too**: the incompatible-trait list grew from 14 to 32 pairs with no config change. Find a list's
  consumer before describing its effect (here the training-card pool builder, not hiring).

## Resolving queue items with the user

Use this when working through [unresolved-mechanics.md](unresolved-mechanics.md) interactively:

1. Ask **one focused question per item**, always with a "not sure / keep open" option. Then ask the **basis** of the answer: in-game
   (UI/tooltip/dialog), an official source (name and date), or a working-stance decision. Don't skip this when the answer already
   contains a value; users often give a value without its basis.
2. Record the basis in the row. In-game = user-supplied live observation (priority 1) dated that day. A stance closes nothing: the
   conflict stays documented. A value given without a basis is recorded as "user-stated (basis not specified)".
3. An answer that restates guide text is not new evidence. Ask whether it was seen in-game before closing the conflict.
4. Check every answer against the existing sources. When it contradicts one (e.g. a currency or multiplier), ask again instead
   of picking a side.
5. Terms that the answer introduces but doesn't define (e.g. "average development") become a follow-up question or a logged
   sub-question (`U-XXX-na`). Never fill them in.
6. Resolutions that only arithmetic supports (a formula reproducing an old example) stay **narrowed** until the user confirms them.
7. Save each answer to the file as it arrives (item 17). After the session, sync `data/mechanics.yaml`,
   prose references, calculators and the CHANGELOG in one pass, and run the validators.
8. **Pre-scan the admin articles first** (user decision 2026-10-13). Record an item without asking when an article settles it and
   no later source contradicts it, and cite the article and its date. Ask the user when the articles are silent, when a newer
   source contradicts them, or when the article is older than the guide and the guide disagrees.
9. Every question offers **"Answer later"**. A deferred item stays in "Remaining ambiguities" marked `deferred YYYY-MM-DD`, and
   the session tracker at the top of the file lists it, so the next session can start from that list.
10. If a free-text answer repeats an example from your own question word for word (e.g. "1 coin per point per day"), confirm
    that it is a real observation before recording it.
11. When the user defers several items in a row, offer to stop and write the tracker.
12. **Order of the queue:** first the items never asked ("Still open, not yet asked" in the tracker), then the deferred ones.
    Group closely related items back to back (e.g. U-CMB-9a stacking, then A-3 miss, then A-12 rounding).
13. **Free-text answers** (tables, odds, lists): say in the question itself "type them in 'Other'". `AskUserQuestion` needs
    ≥ 2 options and rejects a one-option question. An option like "Yes, I'll give them" gets clicked without any text, so you
    end up asking a second time. If only one path remains, ask in plain text in the final message instead.
14. **Partial answers:** when a multi-part question gets only some parts answered, record those parts and give each remaining
    part its own sub-ID (`U-CMB-11b` → `11c` → `11d`). Ask about each unanswered part **once** more. If it still isn't answered,
    mark it "open (asked, no answer)" instead of asking again.
15. **When the user points to code** (e.g. "check `cogs/commands/damage.py`"), read the code before recording anything. Record
    the code path as the basis ("user-stated; bot code"), and only for what the user actually confirmed.
16. Sanity-check user-supplied tables (odds sum to 100%, values match a known pattern) and say so when recording them.
17. Record each answer in the file **right after it arrives**, not in one batch at the end, so a stopped session loses nothing.
    At the end, rewrite the session tracker (resolved / deferred / open lists) and mark closures in the older tables, so no
    stale "deferred" tag survives (`grep -n -i "deferred 2026" unresolved-mechanics.md`).
18. **Item statuses** (user convention since 2026-10-14): resolved · partly resolved · **deferred** (ask again next session) ·
    **incomplete** (the user wants only the parts they supplied documented, the rest marked incomplete; don't fill gaps) ·
    **closed as permanently unknown** (keep `[GAP]`, never use the key, never ask again). For config-key semantics and
    undated history, offer an "Unknown, close it" option next to "Answer later"; the user picks it when nobody knows.
19. When a new answer restates a previously closed item with a different value (e.g. "amount / 2" vs the closed 50% ally /
    100% other split), ask which is current before recording either. Often the new wording covers only one case.
20. When every queued item is settled or deferred, list any caveats still noted inside closed rows (e.g. "rounding not
    re-checked") and ask whether to queue them. Don't add them without asking.
21. **Reversals:** when an answer overturns an earlier user-confirmed closure (pass 5: U-CDX-1 reversed U-CMB-9a), mark the old
    resolution historical/wrong in the new row, `grep` the old ID across the skill and the bot, and list every hit in the
    tracker's follow-up maintenance. Fix SKILL.md's own statements before the session ends, because it is what loads first.
    Bot code (e.g. `cogs/commands/damage.py`) changes behaviour, so leave it for a separate task.
22. **When the user says stop:** write the tracker with four lists: resolved, deferred (ask again), new open sub-items, and
    **not reached** (queued but never asked). The next session starts with "not reached", then "deferred".
23. The user may call this skill "the game-design skill"; the queue lives in this skill's `references/`.

## Third-party rules aggregators (e.g. the UNIKHORNE codex, ingested 2026-10-26)

- **Fetch the data, not the page.** warera.unikhorne.dev/codex is a React shell; the content is JSON at `/api/codex` (categories →
  entries with `body`, `formula`, `sources`, `verify` tier, `conflicts`; plus `ranks` and a `sources` registry) and
  `/api/codex/patchnotes` (its mirror of the admin articles). Find such endpoints by grepping the page's compiled JS for `/api/`.
  WebFetch summarises; `curl` + a scratchpad dump to Markdown keeps every number.
- **Compare its patch mirror by ID, not title**: its slugs end in the **last 6 hex characters of the article ID**
  (`…-a3c0a1` = `6a282e4c9bbf471e91a3c0a1`). Match those against `data/patch-history.yaml`, then by version string for the
  wiki-transcribed v0.15–v0.17 entries. Only the unversioned posts (rules, events) were new.
- **Check what each trust tier really covers.** The codex's "engine" tier reproduced profile Attack totals, which contain **no battle
  bonuses**, so it says nothing about U-CMB-9a. A table it copied from the wiki (ranks) is the same source, not a second one.
- **Re-derive its computed figures with current inputs.** Its Prestige timing (228/152 days) only fit pre-v0.25.5 XP rates; the
  current figures differ by a third. Check every derived number before adopting it.
- **Verify what you can against live data before labelling.** Its v0.27 workforce numbers all matched the live client and moved
  from `[CODEX]` to `[LIVE-CLIENT]`; the rest stayed `[CODEX]` / `[OBS]`, and disagreements became `U-CDX-n` rows instead of edits.
- Its stale claims (civil wars keeping orders, election level 15 …) go in a "stale, don't re-import" list in
  [unresolved-mechanics.md](unresolved-mechanics.md), so the next ingest doesn't re-open them.

## Community guides published as in-game articles (e.g. the v0.27 guides, ingested 2026-10-26)

- Fetch each with `article.getArticleById` and strip the HTML, but **also list the `<img>` URLs** (imgur, media.warera.io) and
  view them: tables, tier lists and tooltips are often only in screenshots, and some guides are a single image.
- **Dev-server screenshots are not the live game.** Tells: an employee "hired 25d ago" on launch day, `0` Energy costs. Label them
  `[OBS]` of the beta. The number on a HIRE / WORK / REROLL button is the player's **current Energy**, not the cost.
- Check a guide's derived numbers against its own screenshots before adopting them (fish's "80–120% output" contradicted his
  own hourly log), then against the live client; record disagreements as conflict rows (G27-n) rather than edits.
- Register the batch as one source with every article ID in its notes (`V027_GUIDES`), and label advice `[STRAT-EXT]` per author.

### A whole category at once (the 666 English guides, 2026-10-27)

- **Enumerate with the filters and prove completeness**: `{type:"last", limit:100, categories:["guide"], languages:["en"]}` until
  `nextCursor` is empty, then the same without `languages` and count the `en` items. Both gave the same 666 ids, so the filters
  work. Fetch every body with `getArticleById` (the list items already carry `content`, but fetch anyway to confirm the metadata).
- **Expect slop.** About a quarter of the category was empty posts, jokes, sermons, recipes, tip begging or texts about another
  game, and another sixth country welcome pages and tool ads. Triage before reading: length, density of game words, title
  patterns, then read the opening of every low-scoring article before calling it slop.
- **Read in tiers and say which tier each article got**: full read for post-patch and mechanics-heavy guides; a claim extraction
  (lines with numbers, formulas or rule words) for the rest of the substantive ones; a short claim skim for generic advice. The
  ledger column "Review" records it, so "consistent" never pretends to more checking than happened.
- **Most guide mechanics are already in the skill.** The value was in a handful of observations that matched unexplained config
  keys (resistance growth/decay), post-deploy live numbers, UI paths, and in spotting dev-server systems that aren't live (G-ART-3).
  Grep the catalog and client before importing any feature a guide describes.
- **Re-check the `official` category during any ingest**: v0.27.1 appeared the same afternoon and changed five v0.27 rules.
- Scripts used (scratchpad, not kept): enumerate + fetch, HTML → text keeping `<em>` as `*`, triage, claim extraction, ledger
  generator with manual verdicts winning over rules.

## The game's English UI catalog (vatoutou/warera-translation)

- `en/messages.po` on GitHub is the client's lingui English catalog (`msgid` = source text, `#:` lines = the component that shows
  it). It equals the "English text catalog" read from the client bundle, without the JS decoding. Pin a commit
  (`https://raw.githubusercontent.com/vatoutou/warera-translation/<sha>/en/messages.po`) and record it as the snapshot.
- **Its git history dates UI changes**: list commits with `api.github.com/repos/vatoutou/warera-translation/commits?path=en/messages.po`,
  download two snapshots and diff by `msgid`. The v0.27.1 diff (78 added, 63 removed) independently showed the free firing and the
  dropped 48 h event wait.
- Use it for labels, paths and wording only. A string can outlive its mechanic (the "Killed in battle" status after v0.27.1), and
  placeholders (`{coreRegionBonusPercent}`) carry no values; take numbers from the config or the client.
- `.po` parsing: join continued `"..."` lines, keep every `#:` reference, and print with `PYTHONIOENCODING=utf-8` on Windows.

## Where the live client keeps a few tables (bundle of 2026-10-27)

Search the `_app-*.js` text for: `PLUTOCRACY` (government-type modifier table and the order-cost function, near
`coreDevelopmentIncomeMultiplier`), `lootChancePercent:25` (wooden-case config), `storyteller:{` (employee event constants,
`minHiredHours`), `fire:{` (firing), `maxRounds:` (battle constants), `luck:{` (toolbox chance per point, `charmGraceHours`; a vanished key such as
`maxToolboxChancePerHour` is how the toolbox cap's removal showed), `trainerSessionsPerDay` (the Trainer trait and, next to
`trainerSessionsUsed`, the function that counts trainable employees per company). Save the extracted **event definitions and trait table** of each read to a dated file (or quote the changed ones in the
source notes): on 2026-11-02 the v0.27.4 cost diff had to use a dev-server guide as "before", because no live copy was kept.
Rosters (`employee.getCompanyRoster`) carry the
matching server state: `charmLuck {amount, until}`, `trainerSessionsUsed(At)`, `trainingsToday`, `lastTrainedAt` (2026-11-01).
Module ids change between builds; the keys don't.

## Community wiki rule

warera.wiki (and similar community pages) is **outdated**. When ingesting it: compare every claim with live config and the latest
guide; record agreeing claims with both sources; record contradicted claims only as `conflicts` (or as history if clearly older);
record uncorroborated claims with `confidence: low` and a `[WIKI-ONLY]` note. Wiki-hosted official patch notes may be used for
dated **history** only.

## Do not

- Overwrite a value in place, average conflicting values, or invent an `effective_from` from an observation date (use
  `first_observed` instead).
- Turn the raw patch log into rules: derive the state.
- Promote a single live observation to a global mechanic.
- Present a Romanian policy as a mechanic because a patch touched a related feature.
- Write an article ID from memory or pad a short suffix into a full ID. Twice on 2026-10-27 a 6-character suffix got an invented
  prefix in a citation. Copy every ID from the fetched data (file name or JSON), then grep it back.
- Type ledger or summary counts by hand. They drifted twice on 2026-10-27 after late verdict changes. Generate them from the data,
  and update every file that quotes a count with an asserted find-and-replace (CHANGELOG, source-map, SKILL.md, the ledger header).
