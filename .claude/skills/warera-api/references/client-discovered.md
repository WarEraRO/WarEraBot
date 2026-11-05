# Procedures discovered in the game client (app.warera.io)

**How found (2026-10-03):** downloaded the game's Next.js client bundles (`https://app.warera.io/_next/static/chunks/*.js`, 247 chunks) and extracted every tRPC hook call (`<router>.<procedure>.useQuery/useInfiniteQuery/useMutation/fetch/...`). Input shapes come from the arguments the client passes. The client references **518 procedures in 106 routers**; **444** are in neither the official spec nor the community explorer. Labels: **[client]** = seen in client code; **[observed]** = live anonymous call.

> ⚠️ **None of these are documented or supported.** They're the game's internal API and can change with any client release. Use them only when nothing official or 🧭 does the job, and say so in code comments.
>
> 🚫 **Never call the mutations listed in section D.** They perform game actions (fighting, trading, voting, moderation, payments) as whoever owns the key. This bot is read-only.

## A. Read queries that work anonymously (13) [observed]

Marked 🕵️ in the endpoint index.

| Procedure | Input [client] | Returns [observed] | Why it matters |
|---|---|---|---|
| `itemTrading.getItemTrading` | `{itemCode}` | `{itemCode, minPrice, maxPrice, currentValue, values:[{valueAt:"YYYY-MM-DD", avgValue, totalValue, totalQuantity, transactionsCount}] (30 days), buyOrders, sellOrders}` | **30-day daily price and volume history** for a tradable good. Tradable goods only: equipment (`helmet3`) → 404 `Itemtradings not found.` |
| `tradingOrder.getTopOrdersPerItemCode` | `{itemCodes:[…], limit}` | `{<itemCode>: {buyOrders[], sellOrders[]}}` | Order books for **many items in one call**, instead of one `getTopOrders` per item |
| `battle.getActiveBattlesByCountry` | `{countryId}` | `["<battleId>", …]` | Active battle IDs a country takes part in, without paging through all battles (`[]` if none) |
| `mercenaryContractAuction.getActiveAuctions` | `{countryId?, battleId?, status?, limit, cursor}` | `{items:[auction incl. currentWinner, currentWinnerUser], nextCursor}` | Same data as the official `getPaginatedAuctions`. `status` **does** filter here (`won` → only won) |
| `alliance.getByIds` | `{ids:[allianceId…]}` | `[alliance]` | Batch version of 🧭 `alliance.getById` |
| `gameConfig.getMaxBountyRate` | none | bare number (`0.88`) | Current maximum money per 1k damage for bounties and contracts |
| `mu.getReputationBuyStatus` | `{muId}` | `{canBuy, cost, amount, currentReputation}` | MU's **current mercenary reputation** (fractional) |
| `gameStat.getBadgeStats` | none | `{<badge>: {count, percent}}` | How many players hold each badge |
| `gameStat.getMilestoneStats` | none | `{<milestone>: {<tier>: {count, percent}}}` | Milestone tier distribution |
| `articleInteraction.getArticleLikers` / `getArticleTippers` | `{articleId}` | `[{userId, createdAt}]` | Who liked or tipped an article. Same family, not probed: `getArticleDislikers`, `getArticleGemTippers` |
| `assetSale.getLastSkinGifts` | none | `[{buyer, giftedTo, skins:[{key, slot}], createdAt}]` | Cosmetic gift feed |
| `map.getMapData` | none | **3.8 MB TopoJSON** (`map.objects.regions` 726 geometries, `countries`, meshes) | Region and country geometry, for rendering maps. Cache hard |

The only equipment price source is still `gameStat.getEquipmentAvgByCode {itemCode}` (e.g. `helmet3` → `14.8`), already used in `damage.py`.

## B. Session-only read queries (42): unusable by the bot [observed]

The message is `"Unauthorized"`, **not** `"API token required"` (which the official key-gated procedures return).

**Retested with the bot's `X-API-Key` on 2026-10-03 [observed]: the key does NOT unlock them.**
- 41 of 42 return **`403 FORBIDDEN "API tokens cannot access this endpoint"`**. The server explicitly rejects API tokens here; they're **game-session only** (browser login). The same key got 200 from `transaction.getPaginatedTransactions` in the same run, so the key itself was valid.
- `gameData.getAllGameData` still returns `401 Unauthorized`, so it's probably admin-only.

➡️ **This bot can't use anything in this table.** Don't build features on them. Don't try to obtain or reuse a player's session cookie to get around this; that would be impersonating a player and is against the game's intended API use. The table stays here only so agents recognise the names and know they're closed. Inputs are from the client.

| Procedure | Input [client] | What it would give |
|---|---|---|
| `war.getPaginatedWars` | `{countryId, limit, cursor}` | A country's wars (no other way to list wars) |
| `war.getActiveWarBetweenCountries` | `{countryIdA, countryIdB}` | The active war between two countries |
| `law.getPaginatedLaws` / `law.getLaw` / `law.getAdditionalCost` | `{countryId,…}` / `{lawId}` / `{type, country, targetCountry, …}` | Country law proposals and votes |
| `allianceLaw.getPaginated` / `allianceLaw.getById` | `{allianceId}` / `{lawId}` | Alliance laws |
| `partyMotion.getPaginatedMotions` / `getMotion` / `getAdditionalCost` | `{partyId}` / `{motionId}` | Party motions |
| `announcement.getActive` / `getPaginated` | `{ownerType:"government"…, ownerId, limit}` | Government, MU and party announcements |
| `election.getElectionsOverview` | none | Election overview |
| `government.canTakeControl` | `{countryId}` | Takeover eligibility |
| `citizenshipApplication.getApplications` | `{countryId}` (page-style, `nextPage`) | Pending citizenship applications |
| `battle.getDamageBonuses` | `{battleId}` | Per-side damage bonuses |
| `battle.getSortedActiveBattles` / `getGroupedActiveBattles` | `{filter}` / none | Active battle lists as the game UI sorts them |
| `round.getRoundData` | `{roundId}` | Live round data |
| `battleLootSummary.getByBattle` / `loots.getLoot` | `{battleId}` / `{battleId, roundId?}` | Battle loot (presumably the caller's own) |
| `battleRanking.getUserRankingPosition` | `{battleId, roundId, side, type, dataType}` | The caller's rank position |
| `battleOrder.getActiveOrders` | none | All active orders visible to the caller |
| `mercenaryContract.getContracts` / `getActiveForBattle` / `getById` | `{muId?, countryId?, battleId?, status?, limit}` / `{muId, battleId}` / `{contractId}` | Accepted mercenary **contracts** (as opposed to auctions) |
| `muOffer.getManyPaginated` / `getByMu` / `getById`, `muOfferApplication.getManyPaginated` | `{countryId, limit}` / `{muId}` / `{muOfferId}` | MU recruitment offers and applications |
| `muHelp.getManyPaginated` | `{muId, limit}` | MU help requests |
| `partyApplication.getManyPaginated` | `{partyId, status?, limit}` | Party join applications |
| `inventory.getById` | `{countryId}` / `{muId}` / `{partyId}` | **Treasury, MU or party inventory** |
| `tradingOrder.getAllOrdersByOwner` | owner IDs | All orders of an owner (🧭 `getPublicOrdersByOwner` works anonymously) |
| `itemOffer.getItemOffers` | `{itemCode, userId?, limit, minSkills?}` | **Equipment market listings** |
| `badgeCollection.getByCountryId` / `getByMuId` / `getByUserId` | `{countryId}` / `{muId}` / `{userId}` | Badges |
| `milestone.getUserMilestones`, `mission.getUserMissionsResumee`, `referral.getUserReferrals` | `{userId}` | A user's milestones, missions and referrals |
| `company.getCompaniesCount` / `getActiveCompaniesCount` | `{userId}` | Company counts |
| `gameConfig.getGameEvents`, `giveaway.getLastGiveaway`, `centrifugo.getOnlineCount`, `gameData.getAllGameData {startDate, endDate}` | — | Event calendar, giveaway, **online player count**, game-wide stats |
| `skin.getSkins`, `skinPack.getLatestSkinPack`, `banner.getBanners` | `{limit}` | Cosmetics catalogue |

## C. Read queries deliberately NOT probed (111)

These are about the logged-in user's own account (`getMy*`, `getMe`, email, phone, kits, notifications), admin or moderation tools (IPs, fingerprints, reports, flags, bans, mod notes, admin logs, user list by email), private chat (`conversation.*`, `message.*`), auth flows, or IDs we lacked. They aren't appropriate or useful for a public bot.

- **actionLog**: getPaginated
- **adminLog**: getPaginated
- **allianceLaw**: getById
- **apiToken**: list
- **articleInteraction**: getArticleDislikers, getArticleGemTippers, getMyInteractions
- **asset**: estimateSkinPackPrice, getUserAssets
- **assetProposition**: getProposition, getPropositions
- **auth**: discordUrl, googleUrl
- **authorSubscriptions**: getAuthorSubscription, getMyAuthorIds, getMySubscribersIds
- **ban**: getBans
- **banner**: getBannerById, getBannersByIds
- **banword**: getAll
- **battleLootSummary**: getMyActiveRecap
- **blacklistedFingerprint**: getAll
- **blacklistedIp**: getAll
- **casinoUserResult**: getMine
- **centrifugo**: getJWT
- **company**: canProduceAll, getManageableCompanies
- **conversation**: getBannedMembers, getConversationById, getConversationByIdAdmin, getConversationByTag, getConversationsPaginated, getJoinableConversations, getParticipantsPaginated
- **conversationCheck**: getConversationCheck
- **conversationInvitation**: getPendingInvitations
- **country**: getMyCountry
- **countryFocus**: getMine
- **gameStat**: getEquipmentAvgByCode
- **generatedImage**: getPaginated
- **inventory**: equippedItems, getAdminUserOverview, getManageableInventories, getManageableInventoriesEntitiesIds, getMyInventory
- **inventoryAccount**: getInventoryAccounts
- **itemOffer**: getMyItemsPriceRange
- **klipy**: search, trending
- **law**: getAdditionalCost, getLaw
- **mercenaryContract**: getById
- **message**: getMessageById, getMessagesPaginated, getMessagesSince, getReportedMessageById
- **milestone**: getMyMilestones
- **mission**: getMissionsResumee, getMyMissions, getUserMissions (later probed: 403, see F)
- **muHelp**: getAvailableCount
- **muOffer**: getById
- **muOfferApplication**: getManyPaginated, getMyApplicationIdByMuOffer
- **notification**: getPaginated
- **notificationPrefs**: get
- **partyApplication**: getMyPendingApplicationForParty
- **partyMotion**: getAdditionalCost, getMotion
- **ranking**: getMyEstimatedCases
- **referral**: getUserReferralsPaginated
- **roundDamages**: getMyDamageInBattle
- **search**: searchChannels
- **skin**: getSkinsByKeys
- **skinPack**: getSkinPacks
- **tournament**: getMyRegistrationStatus, getMyTeamInLastTournament
- **transaction**: getTransactionById
- **user**: getComebackReward, getEmail, getMe, getModNotes, getMyEmail, getPhoneVerification, getTodayClaimCount, getUserList
- **userAdminRights**: listAdmins
- **userBlocks**: get
- **userConnection**: getByUserId, getIpSummary
- **userDeletionRequest**: getPaginated
- **userEquipmentSet**: getAll
- **userFamilyLink**: getFamilyGroup
- **userFavoriteBattle**: getFavoriteByBattleId
- **userFavoriteGif**: list
- **userFlag**: adminList, adminListBetweenUsers, adminListByUser, adminListByUserGrouped
- **userKits**: get
- **userMapLoot**: getMine
- **userPhoneVerification**: getPaginated
- **userReports**: getAllReportsPaginated, getAllReportsStats, getMyReportsPaginated, getOtherActiveReportsCount, getUnreadReportsCountForAdmin
- **whatsUp**: getWhatsUp, getWhatsUpDates, getWhatsUpDeckDates
- **worker**: getMyWorker

## D. Mutations: 🚫 never call (278)

Listed so you can recognise them, not to use them. These change game state.

- **adminLog**: cancelPhoneVerification, destroyItem, fineUser, giveMoneyToCountry, giveMoneyToMu, giveMoneyToUser, logViewInventory, muteUser, removeAllUserOffers, removeMoneyFromCountry, removeMoneyFromMu, removeUserDescription, requestPhoneVerification, unmuteUser, updateUserModNotes, warnUser
- **allianceLaw**: propose, vote
- **announcement**: create, markSeen, remove, toggleLike
- **apiToken**: create, regenerate, revoke
- **article**: adminChangeCategory, adminChangeLanguage, deleteArticle, pinArticleInCountry, publishArticle, saveArticle, unpinArticleInCountry
- **articleInteraction**: tipArticle, tipArticleGems, toggleDislike, toggleLike, toggleSubscription
- **asset**: giftBanner, giftSkin, giftSkinPack, removeBanner, removeSkin, setBanner, setSkin, unlockBanner, unlockSkin, unlockSkinPack
- **assetProposition**: approveProposition, deleteProposition, downVote, upVote, updatePropositionStatus
- **auth**: connect, logout, tryCode
- **authorSubscriptions**: unsubscribe
- **badgeCollection**: giveBadge
- **ban**: banUser, unbanUser
- **banner**: createFromProposition
- **banword**: addWord, removeWord
- **battle**: removeMercenaryContract, setMercenaryContractData
- **battleOrder**: disableOrder, setOrder, setOrderRanks, updateOrder
- **blacklistedFingerprint**: addFingerprint, removeFingerprint
- **blacklistedIp**: addIp, removeIp
- **casino**: roulette, slotSpin
- **centrifugo**: getSubscriptionToken
- **citizenshipApplication**: accept, create, reject
- **company**: changeProducedItem, createCompany, leave, moveCompany, moveToTop, produce, produceAll, renameCompany, sellCompany, toggleActivation, work
- **conversation**: banParticipant, createPrivateConversation, deleteConversation, demoteAdmin, editConversation, findOrCreateConversation, joinBattleConversation, joinConversation, kickParticipant, leaveConversation, markAllAsRead, muteConversation, pinConversation, pinMessage, promoteToAdmin, setTag, transferOwnership, unbanParticipant, unpinMessage
- **conversationInvitation**: acceptInvitation, declineInvitation, inviteUser
- **country**: contributeToUnrest
- **countryFocus**: clearFocus, setFocus
- **dot**: read, readByReference
- **election**: candidateToElection, kickCandidate, vote, withdrawFromElection
- **gameConfig**: setRuleArticle
- **generatedImage**: generate, regenerate, setAdjustments
- **giveaway**: enterGiveaway
- **government**: fireMember, nominateMember, resignFromCongress, resignFromGovernment, startAttack, takeControl
- **inventory**: craftItem, donate, openCase, openCases, scrapItem, scrapMultipleItems
- **itemOffer**: buyItem, createItemOffers, deleteItemOffer
- **itemTrading**: cancelOrderById
- **law**: proposeLaw, voteLaw
- **mercenaryContract**: adminDeleteContract, cancelContract
- **mercenaryContractAuction**: createAuction, placeBid
- **message**: createMessage, softDeleteMessage, upVoteMessage
- **milestone**: claimMilestone
- **mission**: claimFinishedMissionsReward, claimMissionReward, generateMissions, rerollMission
- **mu**: buyReputation, changeNationality, create, demoteFromCommander, leave, promoteToCommander, removeAvatar, removeMember, rename, resetName, transferOwnership
- **muHelp**: create, help, helpAll
- **muOffer**: create, delete, update
- **muOfferApplication**: accept, create, reject, unapply
- **notificationPrefs**: set, setAll
- **party**: create, kickMember, leave, removeAvatar, removeTreasurer, rename, resetDescription, resetName, setTreasurer, updateDescription
- **partyApplication**: accept, create, reject
- **partyMotion**: proposeMotion, voteMotion
- **referral**: setReferrer
- **region**: contributeToResistance, startResistanceBattle
- **roundDamages**: hit
- **shop**: createCheckoutSession, createCustomerPortalSession, createGemsCheckoutSession, giftSub
- **tournament**: register, unregister
- **tradingOrder**: cancelAllOrders, createOrder
- **transaction**: markAsProcessedByMod, unmarkAsProcessedByMod
- **upgrade**: createRegionUpgrade, downgradeUpgrade, increaseUpgradeLevel, toggleActivationByEntity
- **user**: acceptWarning, buyCheapestFoodAndConsume, changeEmail, claimComebackReward, claimDailyReward, consumeBuff, consumeFood, equipItems, equipSingleItem, getEmailUnmasked, markTourAsFinished, moveHome, moveToHomeRegion, moveToRegion, prestige, removeAvatar, removeDescription, resetSkills, resetTours, resetUsername, saveFirebaseToken, saveNewSkillLevels, sendGdprData, sendPhoneCode, unEquipSingleItem, unequipAll, updateColorScheme, updateDescription, updateFont, updatePreferences, updateUsername, updateUsernameEffect, verifyPhoneCode
- **userAdminRights**: setAdminType, setForUser
- **userBlocks**: block, unblock
- **userConnection**: getDistinctIps
- **userDeletionRequest**: requestDeleteAccount
- **userEquipmentSet**: add, equipSet, remove, update
- **userFamilyLink**: addToFamilyGroup, removeFromFamilyGroup
- **userFavoriteBattle**: addFavorite, removeFavorite
- **userFavoriteGif**: add, remove
- **userFlag**: adminDeleteFlag
- **userKits**: addKit, deleteKit, equipKit, updateKit
- **userReports**: create, markAsReadByAdmin, markAsUnreadByAdmin
- **whatsUp**: updateUserCheck
- **workOffer**: applyWorkOffer, createWorkOffer, editWorkOffer, removeWorkOffer
- **worker**: acceptWageReduction, fireWorker, reduceWorkerWage, rejectWageReduction, updateWorker (the `workOffer` and `worker` routers were removed in v0.27)

## E. v0.27 additions (re-discovery 2026-10-26)

The client now references **564 procedures in 110 routers**; 83 were new to this skill (37 queries, 46 mutations). Queries were probed with the bot's API key at about 1 request per second **[observed 2026-10-26]**.

**Readable with the API key** (added to the endpoint index): `managerOffer.getManyPaginated`, `managerOffer.getWageStats`, `managerOffer.getByCompanyId`, `manager.getByCompanyId`, `gameStat.getPpMoneyValue` (no input), `article.getPinnedArticles`, `upgrade.getMapUpgrades`, `work.getStatsByEmployee` (🔑), and the now-official `poll.getPoll` / `poll.getPollVoters`.

**403 "API tokens cannot access this endpoint"** (session-only): `employee.getCompanyRoster` (opened to API keys by 2026-10-28, see F), `employee.getCandidates`, `announcement.getPaginated`, `badgeCollection.getByCountryId`, `battle.getGroupedActiveBattles`, `company.getActiveCompaniesCount`, `itemOffer.getPriceSuggestions`.

**Not probed** (need an id the bot doesn't have, or are about the caller; all were probed on 2026-10-28, see F): `employee.getById`, `employee.getMyEmployees`, `employee.getMyWorkforceSummary`, `employeeEvent.getHistory`, `employeeEvent.getMine`, `employeeEvent.getPendingCount`, `manager.getMyContracts`, `manager.getMyJob`, `managerOffer.getMyProfile`, `badgeCollection.getByMuId`, `badgeCollection.getByUserId`, `battle.getViewersCount`, `itemOffer.getMyItemOffers`, `muOffer.getByMu`, `mercenaryContract.getActiveForBattle`, `tool.getMine`, `tutorialProgress.*`, `userSkillPreset.getAll`, `work.getLastByEmployee`, `effect.parsedAs`.

**🚫 New mutations, never call:**
- **employee**: acknowledgeLeave, claimAllFoundToolboxes, claimFoundToolboxes, drawTraining, fire, hire, move, pickTraining, rename, rerollAll, resetName
- **employeeEvent**: markSeen, resolve
- **manager**: acceptRateReduction, careForEmployee, changeRate, claimPay, fire, quit, rejectRateReduction, transfer
- **managerOffer**: applyToOffer, create, edit, remove
- **poll**: createPoll, endPoll, removeVote, updatePoll, vote
- **tool**: equip, unequip
- **userSkillPreset**: add, remove, update
- **others**: article.adminPinArticle, articleInteraction.setBookmark, asset.setSkinPack, citizenshipApplication.cancel, itemOffer.removeAllMyItemOffers, partyApplication.cancel, tutorialProgress.claimChapter, tutorialProgress.saveMyProgress, user.claimEnergyGift, user.getMyEmailUnmasked, userMapLoot.moveAndCollect

## F. Re-discovery and re-probe (2026-10-28, after v0.27.1)

The client now references **565 procedures in 110 routers**. New since E: `employee.getManagerPointValue`, `tutorialProgress.getMyProgress` and `tutorialProgress.getMyClaimedChapters` (E only named `tutorialProgress.*`). No longer referenced by the client (they may still exist on the server): the queries `itemOffer.getMyItemsPriceRange` and `tournament.getMyRegistrationStatus`, and the mutations `company.leave`, `user.markTourAsFinished`, `user.resetTours`, `tournament.register`, `tournament.unregister`.

The explorer added 12 procedures, all known from A or E: `article.getPinnedArticles`, `assetSale.getLastSkinGifts`, `gameConfig.getMaxBountyRate`, `gameStat.getPpMoneyValue`, `itemTrading.getItemTrading`, `managerOffer.getManyPaginated`, `managerOffer.getWageStats`, `poll.getPoll`, `poll.getPollVoters`, `tradingOrder.getTopOrdersPerItemCode`, `work.getLastByEmployee`, `work.getStatsByEmployee`. The endpoint index now tags them 🧭.

**Now readable with the API key** (403 or not probed before; 401 `API token required` without a key) **[observed 2026-10-28]**. A post shared on 2026-10-28 announced the employee procedures as API-token endpoints. Documented in the endpoint index and domain-economy.md → Employees:
- **employee**: getCompanyRoster, getCompanyEmployees, getCompanyEstimate, getManagerPointValue, getById, getMyEmployees, getMyWorkforceSummary (`getCompanyEmployees` and `getCompanyEstimate` are not referenced by the client at all)
- **employeeEvent**: getMine, getPendingCount, getHistory
- also `work.getLastByEmployee` (🔑, plain `Unauthorized` without a key) and `battle.getViewersCount {battleId}` (bare number)

**Still 403 for the API key [observed 2026-10-28]:** `employee.getCandidates`, `announcement.getPaginated`, `badgeCollection.getByCountryId` / `getByMuId` / `getByUserId`, `battle.getGroupedActiveBattles`, `company.getActiveCompaniesCount`, `itemOffer.getPriceSuggestions`, `itemOffer.getMyItemOffers`, `manager.getMyContracts`, `manager.getMyJob`, `managerOffer.getMyProfile`, `muOffer.getByMu`, `mercenaryContract.getActiveForBattle` (also `getContracts` and `getById`, observed 2026-10-29), `mission.getUserMissions` and `mission.getUserMissionsResumee` (observed 2026-10-29), `tool.getMine`, `userSkillPreset.getAll`, `tutorialProgress.getMyProgress`, `tutorialProgress.getMyClaimedChapters`.

"Readable" doesn't mean "allowed": see the Terms of Use note in SKILL.md before building on anything here that wasn't announced for API tokens.

## G. Re-discovery and re-probe (2026-11-02, after v0.27.4)

The client (build `1793641687026`, 261 files, 7.7 MB) now references **589 procedures in 111 routers**. New since F: 9 queries and 13 mutations, mostly the new **`skinStudio`** router (the skin designer). Probed with the bot key at about 1 request per second **[observed 2026-11-02]**:

| Procedure | Input [client] | Result |
|---|---|---|
| `gameStat.getPpMoneyValueByItem` | none | **200 without a key**: `{<itemCode>: money per production point}` for 20 goods. Added to the index 🕵️ |
| `skinStudio.getImageVersions` | none | **200 without a key**: `{<skinKey>: version timestamp ms}` (cache-busting for skin images; no use for the bot) |
| `employee.previewTraining` | `{employeeId}` | 403 "API tokens cannot access this endpoint" |
| `employee.simulateWorkforce` | `{moves:[{employeeId, companyId}]}` | 403 (the workforce planner's what-if; returns `{employees, companies[{companyId, cap}], before, after}` per the client) |
| `skinPack.getCollectionPacks` | none | 403 (401 anonymous) |
| `skinStudio.getSkins` / `getPacks` / `getBanners` | `{limit, search?, slot?}` / `{limit, status?}` / `{limit, status?, search?}` | 403 |
| `skinStudio.getSkin` / `getPack` / `getBanner` | `{skinKey}` / `{packKey}` / `{bannerId}` | 403 |
| `skinStudio.getPackCounts` / `getBannerCounts` | none | 403 (401 anonymous) |

**🚫 New mutations, never call:** `employee.applyWorkforce`; **skinStudio**: addPieces, createPack, publishPack, removePiece, saveSkinImage, updateBanner, updatePack, updateSkin.

**No longer referenced by the client:** `generatedImage.setAdjustments` (mutation) and `itemOffer.getMyItemOffers` (still 403 on the server). `employee.getCompanyEmployees` / `getCompanyEstimate` were never in the client and still answer the key.

**Re-probed, still 403 for the API key:** every query in F's "Still 403" list (`employee.getCandidates`, `announcement.getPaginated`, `badgeCollection.getByUserId`, `battle.getGroupedActiveBattles`, `company.getActiveCompaniesCount`, `itemOffer.getPriceSuggestions`, `itemOffer.getMyItemOffers`, `manager.getMyContracts`, `manager.getMyJob`, `managerOffer.getMyProfile`, `tool.getMine`, `userSkillPreset.getAll`, `tutorialProgress.getMyProgress`, `mission.getUserMissions`) and the B samples `war.getPaginatedWars`, `law.getPaginatedLaws`, `inventory.getById`, `itemOffer.getItemOffers`, `centrifugo.getOnlineCount`, `gameConfig.getGameEvents`.

The official spec (0.17.4-beta) was unchanged. The explorer added the ten `employee.*` / `employeeEvent.*` queries from F; the index now tags them as in the explorer.

## Repeating the discovery

1. Fetch `https://app.warera.io/` (send a browser `User-Agent`), collect `/_next/static/…/*.js` from the HTML, then fetch `/_next/static/<buildId>/_buildManifest.js` (its path is in the HTML) and add every `static/chunks/….js` it names. That gave 261 files (7 MB) on 2026-10-28 and 261 (7.7 MB) on 2026-11-02. Download into an empty scratchpad folder and parse with a script kept elsewhere (`python -I`).
2. Download all chunks, then regex `\.([a-z]\w*)\.([a-z]\w*)\.(useQuery|useInfiniteQuery|useSuspenseQuery|useMutation|fetch|query|mutate|invalidate)\b`.
3. Diff against `openapi.snapshot.json` + `explorer.snapshot.json` + every name in this file and the index. Read the ~170 characters after each `useQuery(` to get its input shape. Diff the other way too, from the names in this file to the client set, to find procedures the client dropped, and confirm each one by grepping the raw chunks for the bare method name, because the client may call it in a form the regex doesn't match.
4. Probe **queries only**, anonymously, at about 1 request per second. Then probe with the key (`scripts/probe.py`), including the previously 403 ones.
