# Account rules, security and anti-abuse

These are **game rules enforced by WarEra administrators** `[RULE]` (moderation; intent is evaluated by admins). Romanian reporting
procedures are `[POLICY-RO]`.

## One account

Players are limited to **one account**. Creating several or using someone else's — for any reason — is strictly forbidden.
Intentional or repeated violations → permanent ban.

## Shared IP / devices — Family Groups

Players may share an IP only if registered as a **Family Group**, requested **in advance** from an admin on the official Discord.
Members may **not**: trade equipment (or, per v0.16.3, sell any items) to each other, or work for each other. Market orders never
match between family members. All transactions must stay fair and balanced.
Circumventing → loss of status, fines, temporary or permanent bans.

## Bots and automation

Bots, scripts or any automation for advantage are strictly forbidden — including web scraping and scripts bypassing game
features/restrictions. **Allowed**: tools that collect/display data through the **official public API**. For other data access,
contact the game team. (This repository's Discord bot reads the public API — consistent with this rule.)

## Country funds (Rule 6)

Using an office to move a country's treasury for personal gain or for another nation is punishable; tax revenue stays with the
country that collected it, intent decides, and consulting moderation before a large non-standard transfer avoids penalties
(admin article, 2026-02-08). Details and the cases it cites: [proxies.md](proxies.md), "The admin's Rule 6 ruling".

## Community behaviour (Rule 7) `[RULE]` (admin article "Updating 7th rule", 2026-01-27)

- **English only** in World/Global chat. Use the report tool fairly.
- Prohibited, directly or implied: insults, slurs, targeted harassment; doxxing (names, addresses) without explicit consent;
  sexual content; discrimination and hate speech; content about **ongoing real-world wars** (the article names Russia–Ukraine and
  Israel–Palestine); glorifying hateful ideologies, terrorism, genocide denial or war crimes (the article lists nazism, fascism,
  Putinism and communism among them); profiles (picture, description, name) tied to those or to political figures of ongoing wars
  (humour tolerated, never for nazism); promoting rule-breaking or cheating; promoting other games, products or services; spam.
- Applies everywhere players can write in the game (chat, articles, profiles) and on the WarEra Discord.
- Sanctions: removal, then mutes and/or bans of increasing length; permanent for heavy repeat offenders.

`[STRAT-RO]` Romanian coordination talk belongs on the Romanian Discord, not in world chat; keep in-game names, avatars and
articles clear of real-world conflicts.

## Exploiting bugs

Exploiting or ignoring bugs for personal gain is forbidden. Report bugs and stop testing them; give reproduction details
(action, time, unexpected result). Valuable reports earn the **Exploit Finder** badge.

## Boosting and exploitation

Accounts existing solely to benefit a player, group, MU or country are not allowed. Forms include (non-exhaustive):
- abnormally paid work: **below 0.8× or above 1.2× the normal wage** (`rules.abnormal_wage_band`; "normal wage" not precisely
  defined `[GAP]`);
- off-market or manipulated prices;
- funnelling assets without fair exchange;
- repeated tipping of articles;
- repeated donations of resources/money to an MU or country to advantage someone.

Not all help is boosting; admins judge intent. History: until September 2025 boosting was tolerated in some cases (a player
leaving, giveaways, one-time trades); the admin called those rules unclear on 2025-09-08 and announced a rework. Boosting is
prohibited **even when leaving the game** (v0.17.7 rules note, 2025-10-04). The game
itself also caps wages at ±30% of the 24 h average (v0.17.0). Exploited accounts → permanent ban; the boosted account → temporary ban, fine,
or permanent ban on repeat.

Suspicious patterns to report `[RULE]` list: multiple accounts per person; intentional bug exploitation; bots/scripts; repeated
transfers of money/resources/gear without justified exchange; trades at manipulated prices; artificial wages to move value;
gear buy-and-resell schemes to move value; repeated donations whose real purpose is advantaging someone; using country/MU
resources for personal interest or another entity. Players sharing a connection must declare a Family Group in advance.

Reciprocal minimum-wage employment: admins view minimum-wage hiring as suspicious; exploiting several players this way can be
sanctioned; a transparent, balanced 1:1 reciprocal arrangement is treated differently.

**From v0.27** (2026-10-26) the job market is gone, so player wages exist only as **manager pay**, which the game keeps within
80–120% of the average manager pay. The wage-based indicators above then apply, if at all, to manager contracts; the article
doesn't say how moderation treats them `[GAP]`. The other boosting rules (transfers, prices, donations, tips) are unaffected.

## Assessing a suspected boosting transaction (Scenario) `[STRAT-RO]` method

1. Get price vs market reference at that time (`transaction.reference_price`), quantities, frequency, counterparties.
2. Flags: price ratio far from market (e.g. <0.5× or >2× — heuristic, not a rule), one-directional value flow, repetition,
   Family Group or shared-IP links, wages outside 0.8×–1.2×, donations benefiting one person.
3. Conclude only "potential boosting — needs admin review"; never accuse on one data point. Report with evidence through
   official channels. `validate_game_snapshot.py` flags price-ratio outliers.

## Penalties and appeals

Penalties and their justification are visible on user profiles. Appeals go through the official game Discord with explanations
and evidence. Violations can be reported with supporting evidence.

## Account security

Email login recommended: a verification code is sent to the account's email at login. Use an address you always control; never
share codes; lost email access → contact WarEra support via official channels. Inactivity: [progression.md](progression.md).

## Terms of Use and Privacy Policy of 2026-09-28 `[OBS]` (third-party summary, not read at the source)

A player's diff summary (`6aca745113d6372b785457bc`, "Diff summary of the old and new terms and privacy statements",
2026-10-10) says new Terms and a new Privacy Policy took effect on **2026-09-28**, replacing the old texts entirely and written
for EU and French law (operator WAR ERA SARL, Paris). This skill hasn't read the documents themselves, so treat each point as
"reported" and check the official text before acting on it.

- **Accounts**: under 15 needs a parent's or guardian's consent; under 18 needs a parent's authorisation for purchases. One account
  per person; sharing an account or a device is banned; an approved Family Group may share an IP address but **not a device**
  (consistent with the rules above).
- **Conduct**: a ban on **real-money trading** (with in-game fines as a possible penalty); a rule against knowingly helping
  someone else break the rules; ban evasion; account-sharing detection and appeals; a phone-verification process (after a
  request, 48 h of normal use, then purchases and donations are restricted, and the account is suspended after 5 days; there is
  an alternative route without a phone).
- **Public API rules**: no scraping, no getting around rate limits, **no use of non-public endpoints**. This matters for tools
  and bots: the `warera-api` skill documents client-only (🕵️) procedures, which may count as non-public. Read the official
  Terms before relying on them.
- **Moderation**: final permanent bans are never made by automated processing alone; moderation outcomes are public for a
  limited time without naming the staff member; the anti-multi-account system is described as profiling that users can contest.
- **Monetisation**: "Premium" is now the **Supporter Plan** (the in-game name since v0.27 too); paid boxes show odds and pool
  before purchase, with duplicate protection and no pity mechanic; skins and packs are permanent unlocks.
- **Security research**: responsible disclosure; dev environments may be tested freely, production only with written
  permission; 90-day disclosure window; no paid bug bounty.

A player's sanction history posted on 2026-10-17 (`6ad36af3d74c7aa06af70c08`) shows what penalties look like in practice: a
2-day ban under Rule 1 (one account), a fine of 251 coins, and a warning message. That's one anecdote, not a penalty scale.
