# Domain: global rankings and articles

**Solves:** leaderboards (weekly or all-time damage, wealth, level, terrain, bounty, referrals, MU reputation, alliance stats) and tier thresholds; the newspaper feed and article lookup.

Labels: **[spec]** · **[observed 2026-10-03]** · **[project]** · **[assumption]**

---

## `ranking.getRanking`
Input: `rankingType*` **[spec]**. The description mentions an "optional year-week filter", but **no such input field exists in the schema** **[spec]**. Treat historical weeks as unsupported unless the live spec adds a field.

`rankingType` enum **[spec]**, grouped by entity key in items **[observed for those marked ✓]**:

| Entity key in items | Values |
|---|---|
| `country` ✓ | `weeklyCountryDamages, weeklyCountryDamagesPerCitizen, countryRegionDiff, countryDevelopment, countryActivePopulation, countryDamages ✓, countryWealth, countryBounty` (`countryProductionBonus` removed in v0.27, `invalid_enum_value` **[observed 2026-10-26]**) |
| `user` (+ `country`, `mu`) ✓ | `weeklyUserDamages ✓, userDamages, userWealth ✓, userLevel, userReferrals, userSubscribers, userTerrain, userPremiumMonths, userPremiumGifts, userCasesOpened, userGemsPurchased, userBounty, userSkinsOwned, userMilestoneTiers, userMissionsClaimed` |
| `mu` ✓ | `muWeeklyDamages ✓, muDamages, muTerrain, muWealth, muBounty, muReputation` |
| `alliance` ✓ | `allianceInitialDevelopment, allianceDevelopment, allianceWeeklyDamages, allianceDamages ✓, alliancePopulation, allianceWeeklyDamagesPerCitizen` |

Response **[observed]**:
```jsonc
{"_id": "…", "type": "weeklyUserDamages", "isGlobal": false,
 "items": [{"user": "<userId>", "country": "<countryId>", "mu": "<muId>", "value": 26683802, "rank": 1, "tier": "master", "_id": "…"}, …],
 "tierValues": {"bronze": 24, "silver": 61599, "gold": 446705, "platinum": 3469984, "diamond": 8926205, "master": 14200239}}
```
- **Unpaginated; returns the full list in one response.** Sizes seen: weeklyUserDamages ~13.9k, userWealth ~15.3k, muWeeklyDamages ~1k, countryDamages 180, allianceDamages 12.
- **`muWeeklyDamages` items** **[observed 2026-11-04]**: `{mu, value, rank, tier, _id}`, 967 MUs, sorted by `rank` (1 = 133.8M, #100 = 27.6M on a Wednesday). "MU in the weekly top N" = `rank <= N`. It resets with the weekly missions (Monday 00:00 UTC), so read it before the reset for a week's result (`cogs/tasks/mu_challenge.py` reads it hourly and keeps the last value).
- User rankings include the user's **`country` and `mu`**, so "top N players of country X / MU Y" is a local filter on one response, not one call per citizen. `top_user_weekly_damages.py` already does this for country **[project]**.
- Items give IDs only. Resolve names with `getUserLite` for just the top N.
- `userWealth` and `userLevel` list **every player**, zero wealth included (14,697 items each **[observed 2026-11-03]**), so filtering them on `country` gives a country's full citizen list (unlike `user.getUsersByCountry`). `userLevel`'s `value` is total XP (191,771 for #1), not the level.
- The same `{value, rank, tier}` appears under `rankings.<type>` on user, country and MU objects, which is cheaper when you need one entity's rank.
- Ranking week boundaries: see `gameConfig.getDates().weeklyMissionRegenAt` **[assumption: that week and the ranking week coincide]**.

## Articles

### `article.getArticlesPaginated`
Inputs **[spec]**: `type*` ∈ `daily | weekly | top | my | subscriptions | last`, `limit` (1–100, default 10), `cursor`, `userId` (author), `categories[]`, `languages[]`, `positiveScoreOnly`.
- `my` and `subscriptions` presumably depend on the authenticated user **[assumption]**.
- Category and language values are not enumerated in the spec. Observed values: `category: "entertainment"`, `language: "it"`.
- `categories: ["official"]` **really filters** (every one of the 81 items returned had `category: "official"`; paged with
  `nextCursor`, no key needed) **[observed 2026-10-25]**. The official category holds the admin's patch notes plus staff posts and
  translations (es/de/pt/tr). One patch (v0.25.1, `6a2d86d5ab0e47773095df00`) exists only as a staff article there, so a
  `userId`-only fetch of the admin misses it.
- `languages: ["en"]` **really filters** too, and combines with `categories` **[observed 2026-10-27]**: `{categories:["guide"],
  languages:["en"]}` paged to 666 items (7 pages of 100); the same query without `languages` gave 1,717 guide items (ar 316,
  es 150, de 104, pt 97, it 76 …) whose `en` ones were exactly those 666 ids. To prove a filtered set is complete, run it once
  unfiltered and compare ids.
- List items already carry the **full `content`** (identical length to `getArticleById` for all 666 guides) **[observed
  2026-10-27]**, so a bulk read needs no per-article fetch; fetch by id only to re-check metadata.
- `createdAt` isn't always the real creation time: the admin's v0.25.2 article has `createdAt` 2026-08-19, but its ObjectId
  timestamp (first 8 hex digits = Unix seconds) and two translations date it 2026-08-17 **[observed 2026-10-25]**. To date a post
  as early as possible, compare `createdAt`, `publishedAt`, the ObjectId and translations of the same post.
- Titles and content contain emoji. `print()` on the Windows console (cp1252) raises `UnicodeEncodeError`, so write output to
  a file opened with `encoding="utf-8"`, or call `sys.stdout.reconfigure(encoding="utf-8")` first. `PYTHONIOENCODING=utf-8`
  works only without `-I`: `python -I` ignores `PYTHON*` env vars and still crashes **[observed 2026-10-31]**.
- No `meme` category has been seen; memes are posted under `entertainment`. To list them, fetch
  `{categories:["entertainment"], languages:["en"]}` (both filters held on 300 of 300 items **[observed 2026-10-31]**) and
  match `meme` locally in the title or tag-stripped text: 39 of the newest 300 matched, all but one in the title. Image-only
  jokes that never say "meme" ("Day N of monke", "COMIC OF THE DAY") are missed, so tell the user which rule you applied.

Item **[observed]**:
```jsonc
{"_id": "…", "title": "…", "content": "<p class=\"tiptap-block\">…</p>",   // full HTML
 "language": "it", "category": "entertainment", "author": "<userId>",
 "isPublished": true, "isDeleted": false, "isPublic": false,
 "stats": {"likes": 0, "dislikes": 0, "score": 0, "views": 29, "comments": 0, "subs": 0, "tips": 0, "gemTips": 0},
 "publishedAt": "iso", "slug": "la-rinascita-2f8e60", "createdAt": "iso", "updatedAt": "iso"}
```
`type: "last"` is newest first **[observed]**, ordered by `publishedAt`, not by `_id`/`createdAt`: an article whose ObjectId
dates it 2026-10-21 (`6ad87040afd627cc0d2c93f5`) was published 2026-10-29 and sat among the 10-29 items **[observed
2026-10-31]**. A poller that stops at the first already-seen id still catches such late publications, because they land on top.
- `userId` filters by author and pages through `nextCursor` without needing an API key **[observed 2026-10-13]**: the game admin
  `6813b758efecdf9bab195068` returned 100 articles (official patch notes v0.15.0 → v0.26.1). Categories seen there:
  `official`, `news`, `other`, `stats`, and missing (`null`) on the oldest ones.
- `content` HTML: the editor turns `*` into `<em>`, so `a * b` becomes `a <em>b</em>` and the multiplication sign is lost when
  you strip tags **[observed]**. Check the raw HTML for formulas.
- Tags of countries, regions, users, MUs, parties, alliances, battles and articles are **empty**
  `<span data-content-link="" data-content-type="country" data-content-data='{"countryId":"…","fullMatch":"<url>"}'>`
  elements, so the tagged name never appears in the text; match the id in the HTML instead (1,693 country tags in 1,000
  articles, all empty) **[observed 2026-10-24]**. Inline styles carry fonts such as `font-family: "Times New Roman"`, so
  never substring-match the raw HTML for words.
- **Writing text for players to paste into an article:** a bare `https://app.warera.io/user/<id>` or `https://app.warera.io/mu/<id>`
  becomes such a tag (its `data-original-text` is the URL) **[observed 2026-11-03, the government's weekly-top articles: 100
  user and 8 MU tags]**, so generated article text should name players and MUs by these URLs.
- `updatedAt` changes when the article is viewed (32 of 99 within an hour, with identical content), so it can't detect
  edits; compare the title and content instead **[observed 2026-10-24]**. For polling, fetch **one page** and stop when you reach an already-seen ID. Don't drain all pages; see api-opportunities.md about `warera.game.get_articles`.

### `article.getArticleById` / `article.getArticleLiteById`
Input: `articleId*`. Works without an API key; the article sits at `result.data` **[observed 2026-10-25]**. Full returns the object above. Lite returns `{_id, title, stats}` and **does not count as a view** **[spec]**, so prefer lite for bots that only need title or stats.
Web link: `https://app.warera.io/article/<id>` **[project]**.

### `article.getWelcomeArticleByCountryId` (not in official spec; [explorer], verified live 2026-10-03)
Input: `countryId*`. Returns the country's pinned welcome article for new citizens: a **full article object** (same shape as `getArticleById`, including HTML `content`) plus `welcomeArticleOfCountry: "<countryId>"` **[observed]**. Romania's was a guide in the `guide` category, language `ro`. `country.getCountryById().pinnedArticle` held the same article ID **[observed]**, so `getArticleLiteById(pinnedArticle)` is the cheaper route when you only need the title.
