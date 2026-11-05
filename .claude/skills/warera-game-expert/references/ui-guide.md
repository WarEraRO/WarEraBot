# In-game UI: current labels, where things are, and what the labels used to be

> **Source** `TRANSLATION_EN`: the game's English catalog (`en/messages.po`) in vatoutou/warera-translation, commit `a8060359fca8`
> of **2026-10-27 17:46 UTC** (v0.27.1), 4,337 strings, each with the component that shows it. Old labels come from commit
> `cea816fe0c9b` (2026-09-30, the last before v0.27) and `e20fa04b12ec` (2026-10-26 22:09 UTC, v0.27).
>
> **How to read this page.** A **label** in quotes is verified: the exact string exists in the catalog. A **path** ("Market →
> Jobs") is inferred from the component that shows the label and from the in-game tutorial text, unless it's marked `[OBS]`
> (a player or guide saw it). UI text is evidence of what the interface says, **not proof of a mechanic**: the catalog still has
> a "Killed: died in a battle fought over the region they worked in" status after v0.27.1 switched battle deaths off, and a
> "Job market" entry in the company menu after the job market was removed. Numbers in `{braces}` are placeholders filled by the
> client; their values come from the config or the client, cited where this skill has them.

## Main navigation

| Area | Labels (component) |
|---|---|
| Bottom menu | "Battles", "Companies", "Inventory", "MU", "Market" (`LayoutMenu`) |
| Right-hand icons | "Progression", "News", "Events", "Country", "Party", "Ranks", "Shop", "Feed", "Admin" (`LayoutRightIcons`) |
| Map filters | v0.27.2: an **employees** filter, and each region shows how many employees work there (patch note; label text not checked) |
| Map user menu | "Atlas", "Focus on you", "Back to home region", "Nearest wooden case", "Quick move & collect on case click", "Time until the next case roll", "{x}% base chance, plus your Luck skill" (`LayoutMapUserMenu`); the travel and case entries disappear when movement is turned off (~2026-11-10, v0.28; config `mapTravel` flags) |
| Settings (v0.28; was "Options") | a **Settings** window with tabs **Graphics**, **Map**, **Interface**, **General**; "Preset" **Low / Medium / High** ("Custom" once you change a setting); "Map pixel ratio" x1–x3 ("Lower is softer but saves battery and memory"); "Arcs" ("Neighbor and attack arcs on the map"; "Red between countries at war, blue between allies, gray otherwise") |
| Battle | v0.28: no **Move** button and no "Move to the battle first (costs Stamina), then hit."; reworked **Last Hits** (hits and damage per second); battle rankings filter **Alliances** next to Countries and Military units (damage, ground points, money) |
| Loading screen | v0.28: shows "build {build}" (quote it in bug reports) |
| Region menu (tap a region, or right-click on PC: tutorial text "Right-click any region on the map to open its menu.") | "Region", "Country", "Initial country", "Origin", "Alliance", "Attack", "Collect", "Move & collect", "You are here", "Companies (active, not disabled)", "Estimated daily income", "{n} regions away" (`MapMenu`) |

## Progression page

Tabs: "Missions", "Milestones", "Levels", "Skills", "Guides" (`ProgressHeader`; header "Missions, milestones, levels, skills &
guides"). Missions are **claimed by hand** (loading tip "Missions are claimed by hand: open Progression to collect your XP, cases
and Money"). The **Levels** tab lists what each level opens; its labels are: "Trade items", "Manager jobs", "Craft items",
"Workforce chart", "Write articles", "Vote in elections", "Run in elections", "Join resistances", "Join unrest", "Donate to
country/MU", "Take control of a country", "Active citizen", "Unrestricted chat", "Produce all", "Open all cases", "Bulk dismantle".
The unlock levels themselves are in [progression.md](progression.md) (`featureUnlockLevels`). The **Guides** tab holds the six
v0.27 tutorials ("{chaptersDone} of {n} guides done"; a paused guide can be resumed "from the Guides tab of the Progression page").

Skills: "Presets", "Skill presets", "Save current", "Load preset" ("Save a build and reload it anytime. If you don't have enough
skill points, the build is scaled down proportionally to fit."); Supporters can save more presets.

v0.27 mission labels (`_user/mission`): "Hire an employee in one of your companies", "Train your employees {n} times", "Answer {n}
employee events", "Give a tool to one of your employees" (Equip a Tool), "Have your employees find {n}" (Toolbox Finds), "Take care
of an employee {n} times in the company you manage" (Take Care), "Become the manager of another player's company", "Work {n} times
in your companies". The older missions keep their wording in plural forms.

## Market

Tabs: "Market", "Equipments", "Jobs", "Your offers" (`MarketHeader`). The Jobs tab is titled **"Manager positions"**, with the
filters "All positions" and "I qualify" (`ManagerOfferList`; Nadim's FAQ: Market → Jobs → "I qualify", offers were taken within
seconds on launch day `[OBS]`). Taking a position warns "Taking another position will make you leave this one!".
`[OBS]` (same FAQ): equipment search is the plus box to the left of "Cheapest". v0.27.1 added "Same price for all items" when
listing several items, seller flags on offers, and an estimated profit on manager offers.

## Companies and employees

- **Companies page**: "Workforce" (the workforce panel), "Advanced view" (v0.27.1: employee stats per company).
- **Company menu** (`CompanyDropdown`): "Change production", "Move company" ("{freeMoves} free"), "Upgrade automated engine",
  "Upgrade break room", "Upgrade storage", "Hire a manager", "Disable company" / "Enable company" ("You already have {n} active
  companies. Disable one first."), "Rename", "Move to top", "Destruct" ("{x}% of invested"). Only active companies work;
  a disabled one shows "Paused: nobody produces here" (since v0.27.4 "Paused: nobody works, ages or trains here").
- **Recruiting** (`RecruitModal`): "Candidates", "Reroll all", "Recruit", "Roster", "No candidates available". Hiring costs
  Energy "and no money. New candidates show up every day" (loading tip). Since v0.27.2 the window counts down to the daily
  candidate refresh at 00:00 UTC, and names match the candidate's country (patch note; label text not checked).
- **Employee card** (`EmployeeModal`): "Stats", "Traits", "Coworkers", "Daily output", "Daily production", "Daily wage", **"Daily
  profit"**, "Last works", "Train" ("Next to train ({n} left)", "Pick a card"), "Move" / "Swap with" / "Move here" ("Anyone moved
  cannot be fired for {24} hours"), "Fire", "Rename" (a Supporter feature). Tags: "Wage expectation", "Training potential",
  "Happiness". Training cards show the before → after value, and event odds bars put failures on the left and successes on the
  right (both v0.27.2). Found toolboxes wait behind **"Claim the toolbox"**; the trait tooltips group into "Tools" and "Events".
  `[OBS]` (guide `6adfb0879f5bbacb371170b9`): the card shows two small chips next to happiness, the bonus chip (pickaxe) and the
  wage chip (coins); see the keep-or-fire rule in [employees-and-wages.md](employees-and-wages.md).
- **Tool slot**: given to an employee, not to you or the company; "This good needs another kind of tool: every tool your
  employees hold here goes back to your inventory" when production changes. `[OBS]` (Nadim): the tool slot is the small icon on
  the right of the employee's row. Tool names by type: sickle (Rusty Sickle, Farmhand's Sickle, Honed Sickle, Harvester's Edge,
  Reaper's Crescent, Worldroot Scythe), pickaxe (Chipped, Iron, Tempered, Deepcut Pickaxe, Diamond Auger, Seismic Breaker),
  skillet (Dented, Cast Iron, Seasoned, Chef's Skillet, Firestorm Skillet, Ambrosia Pan), hammer (Cracked Hammer, Blacksmith's
  Hammer, Forge Hammer, Molten Maul, Anvilbreaker, Starforge Hammer), flask (Cloudy, Sealed, Copper Flask, Catalyst Flask,
  Philosopher's Flask, Quintessence Still), caliper (Loose, Brass, Machinist's, Precision, Micron, Absolute Caliper). Each list
  is in item-code order `sickle1` … `sickle6` (catalog line order = the client's code order, checked 2026-10-27). Equipment uses
  the same digits for rarity (`pants1` Common … `pants6` Mythic), so the first name of each type is presumably Common and the last
  Mythic `[Derived]`; the client bundle doesn't show the tool items' rarity field directly.
- **Managers** (`ManagerCollectButton`, `ManagerCareButton`): "Collect" ("Everything you earned is paid out now."), "Care",
  "Resign from this position?" ("You can resign {in …}" during the 24 h lock).
- **Taxes on the company page**: "Employee tax" ("The state collects {x}% of your employees' wages as employee tax"), "Manager
  tax" ("The state withholds {x}% of a hired manager's pay as manager tax"), "Low tax", "Core region" ("your employees here get
  +5% production").

## Country, region and government

- **Country page** sections include "Government", "Congress members", "Laws", "Elections" ("Presidential elections", "Congress
  elections"), "Taxes", "Diplomacy", "Battle orders", "Core regions", "Conquered regions", "Strategic resources income", "Unrest",
  "Mercenary Contracts", "Mercenary Auctions", "Donations", "Citizenship Applications", "Take control". "Daily income" /
  "Estimated daily income": "Sum of the regions the country currently controls. Market taxes and other income are not included."
- **Region page**: "Development income", "Est. daily income" ("Estimated from current development, rosters, managers and tax
  rates. Updated hourly.").
- **Government types**: names "Provisional", "Republic", "Nationalist State", "Homeland Front", "Federation", "Plutocracy",
  "Autocracy", "Mercenary State"; law "Set government type" ("It can't change again for {30} days"). Effect lines and their
  values: [government-types.md](government-types.md).
- **Ministers**: "Min of Defense", "Min of Economy", "Min of Foreign Affairs" (profile titles).
- **Party**: "Treasurer" is a party role; "Parties can no longer start resistance"; "Party ethics were replaced by government
  types".
- **Article polls**: "Add poll", 1 hour … 7 days, "Allow multiple answers", "Minimum level to vote", "Restrict to nationality"
  ("Only players who were already citizens of {country} when the poll started can vote"); the timer "starts when the article is
  published".

## Rules the loading screen states (current wording, v0.27)

The loading tips (`loadingTips`) are short official statements of rules. Values in brackets are the ones this skill has from the
config or the client.

- Bars: "Your Energy, Health and Hunger refill by {10}% of their max every hour. A full bar wastes that regen, so spend it first";
  "Above your bar's max, the extra is lost at the next hourly regen."
- Combat: "Armor and Dodge have diminishing returns: each point is worth a bit less than the one before" (in percent terms; per
  hit of Health they scale linearly, see [formulas.md](formulas.md)); "Critical chance caps at 100%: every point above turns into
  {…} critical damages"; "Precision caps at 100%: every point above turns into {+4 Attack}"; "Every hit in battle costs {10
  Health}"; "Every hit that lands rolls your Loot chance for a {case}, and a 100 times rarer roll for an {elite case}"; "Never
  fight without ammo: light +{10}%, ammo +{20}%, heavy +{40}% Attack"; a Pill "boosts your Attack by {60}% for {8}h, then lowers
  it just as much for {15.5}h".
- Bonuses: "Fighting for your own country gives +{20}% damage. Tournament battles don't count"; "Follow the battle orders of your
  country and your Military Unit: each one gives up to +{15}% damage"; "Fighting for a country that occupies your own country's
  regions cuts your damage by {50}%"; "A Military Unit's Headquarters gives its members up to +{20}% damage"; MU help "every
  {12}h: each help gives you {2 Health}".
- Food: "Each meal costs 1 [Hunger]. Bread restores {10}% of your max Health, steak {15}% and cooked fish {20}%."
- Travel (until ~2026-11-10, v0.28): "Each region you cross costs {10 Stamina}. When the bar runs dry, the trip costs {2 oil} per region instead"; "Once
  every {12}h, travelling back to your home region is free"; "Moving your home to another region costs {100 concrete}".
- Wooden cases (until ~2026-11-10, v0.28): "Every hour, you have a {25}% chance that a wooden case drops somewhere on the map, just for you. Go stand on it to
  claim it"; "Wooden cases vanish after {48}h, and no new one drops while {5} are waiting."
- Economy: "Working in your own company costs {10 Energy} and adds your Production to its storage"; "Production stays in a company
  until you produce"; "A company with a full storage can't be worked and makes its employees unhappy"; "A company's Break Room
  level is the number of employees it can hold"; "Moving an employee to another company is free, but costs them {5} happiness for
  {7} days"; "Employees get +{1}% production for every day spent on the same good, up to +{20}%"; "Employees below {30} happiness
  may quit"; "Train each employee once a day, resetting at 00:00 UTC: you draw {3} cards and keep the one you like"; "Clicking a
  cost you can't afford opens the market, already filled with exactly what you're missing."
- Politics and rules: "Changing citizenship has a {30}-day cooldown"; "A region's Development turns into daily Money for the
  country that owns it"; "Spend Energy or Health to raise the resistance of an occupied region"; "One account per player.
  Multi-accounting can get you permanently banned"; "Found a bug? Report it instead of using it."

## Old → new labels (v0.26 → v0.27)

| Before v0.27 (removed strings) | Since v0.27 |
|---|---|
| "Job offers", "Go to job market", "Find another job", "New job offer", "Your current job" | "Manager positions" (Market → Jobs), "Hire a manager" |
| "Entrepreneurship" ("Used to Self Work in your own companies") | gone; **Energy** pays self-work ("Spent to work your companies, hire and train employees, and push resistance or unrest bars") |
| "Workers", "{n}/{max} Workers", "Maximum of {n} workers", "Fire worker?", "Wage per production", "Propose wage reduction" | "Employees", "Maximum of {n} employees", "Fire", "Wage expectation" (set by the employee) |
| "Fidelity Bonus" ("increases by … every day you work for the same employer") | "Specialization progress" (per employee and good, +1%/day, max +20%) |
| "Income Tax" on a company ("deducted from your workers' wages") | "Employee tax" and "Manager tax" |
| "Ethics", "Ethics Points", party ethic names (Agrarian … Unethical) | "Government type" (country level) |
| "Specialty", "Specialization item", "Country production bonus" | "Country specializations were removed from the game"; "Strategic resources income" |
| "Deposit will be depleted in", "from deposit resources" | gone (deposits off) |
| Missions "Find a job at a company", "Work {n} times for an employer" | "Become the manager of another player's company", "Work {n} times in your companies" |
| "Collect the wooden case lying on this region" | "Collect the {n} wooden cases lying on this region" (one click for all) |
| "Premium" ("See all your workers and companies stats") | "Supporter" / "Supporter Plan" ("See all your employees and companies stats") |
| Prestige: "You will drop to level 25 (losing 65,000 XP), gain a permanent +50% XP bonus …" | "You drop to level {newLevel} and lose {xpPenalty}. Your total XP is kept."; "Permanent {bonus} XP bonus, paused while you are at level {50}" |

v0.27 → v0.27.1 (2026-10-27): the trait tooltips became condition → effect tables (same values); removed: "Hired less than
{24}h ago, so this counts as a reroll" (firing is free) and "never to someone hired less than {48 h} ago" in the event
description; added: "Advanced view", "Same price for all items", "Coworker trainings per day", "Toolbox chance and cap", "Broken:
no longer boosts Production" (worn-out tool), and a tool-value estimate "What a day of the extra production this tool gives is
worth at the market value of a point".
v0.27.3 → silent patch (UI catalog commits 89b0525 2026-10-29, 0ac5360 and 77f0bc4 2026-10-31): the Luck text lost "(up to
{LUCK_MAX_PERCENT}%)" and Scavenger "and cap" (toolbox cap gone); training shows "{handRarityName} hand. Pick one, the others
are lost." and each card's estimated profit ("What this card changes in a day of their production at market value, minus a day
of their wage. Higher production also raises the wage they ask."); a Trainer's badge shows "{left}/{perDay} sessions left today"
or "No session left: …". New **Reorganize** button on the workforce summary → "Reorganize workforce": "Drag employees between
companies. Nothing changes until you apply.", Before /day → After /day and Difference, "Apply this setup?" ("Their time in the
company starts over."), for everyone. Skin propositions are gone (only Banner / Emote asset propositions remain `[OBS]`, article
`6ae682c7470184738824c070`), skin packs say "Includes a free banner", and the loading tip "Spend Energy on Construction to help
build your region's upgrades" was removed (reason not stated).
v0.27.4 (UI catalog commit 4838d69, 2026-11-02 16:22Z; 44 strings added, 35 removed): equipping a tool opens the equipment window;
"All tools" (the ? next to a tool: "A tool only boosts an employee in a company producing one of the goods listed under it");
tool returns ("Their tool does not fit there: it goes back to your inventory."); disabled-company warnings ("{0} is disabled:
{who} will not work, age or train there", "Not aging: no work or training today. Resting in the cryogenic chamber until there is
something to do."); training "Reroll" ("Swaps this hand for a new one, for free.") and the Wild card "+2 to a random stat";
"Teaches one mixed trait" removed; trait "Talks to Machines" ("Automated engine output x2 when working alone"); Responsibility is
shown as "Personal morale" ("A lasting boost to their happiness.") instead of a stat (v0.28: Nationalist, Statist and Foreman
show on their own happiness lines, no longer inside Personal morale; the employee window's stats panel shows "Daily output" and
"Daily wage" side by side); "Hidden trait" and "Train to reveal traits"
removed. The article also lists multi-select dismantle filters, donate-mission tags on the Country and MU buttons, a new company
card header, the workforce summary in companies-page order, the mobile white-map fix, the client switching to the latest version
on its own at the next page change, and 6 skin packs that can include a free banner.

## Quick UI answers `[OBS]` (players, 2026-09-15 … 2026-10-26)

- Saved articles: News → the last tab next to Subscribed / New / Top (guide `6adf87bcdcb1ff9bae181008`).
- Wooden case on the map: the star-looking map button (same guide); the map user menu also has "Nearest wooden case".
- Move home: open the region, the menu in its upper-right corner, pay 100 concrete (guide `6aa98e89603c4ac4ea28c025`, 2026-09-15).
