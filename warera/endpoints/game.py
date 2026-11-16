"""Game-wide data: configuration, statistics, global rankings and articles."""
import asyncio

from warera.endpoints.base import Endpoint, guarded


class GameAPI(Endpoint):
    """`gameConfig.getGameConfig`, `gameConfig.getDates`, `gameStat.*`, `ranking.getRanking`, `ranking.getRankingPage` and `article.getArticlesPaginated`."""

    @guarded()
    async def get_config(self):
        """gameConfig.getGameConfig (every game constant), or None.

        Cached by the client for an hour by default (see `DEFAULT_CACHE_TTLS`); when a refresh fails the
        expired copy is returned. The same dict is shared by every caller, so never modify it.
        """
        return await self._get('gameConfig.getGameConfig', {}, allow_empty=True)

    @guarded()
    async def get_dates(self):
        """gameConfig.getDates (no input): the game clock as ISO strings (nextDayAt, weeklyMissionRegenAt, ...), or None."""
        return await self._get('gameConfig.getDates')

    @guarded()
    async def get_pp_money_value(self):
        """The game's money value of 1 production point (explorer-documented, no input), or None."""
        value = await self._get('gameStat.getPpMoneyValue', kind=(int, float), allow_empty=True)
        return float(value) if value is not None else None

    @guarded(dict)
    async def get_equipment_averages(self, item_codes):
        """Batched gameStat.getEquipmentAvgByCode (undocumented): {itemCode: average price} for the codes that resolved.

        Codes whose average is missing or 0 are left out.
        """
        return await self._get_keyed('gameStat.getEquipmentAvgByCode', item_codes, lambda code: {'itemCode': code},
                                     kind=(int, float, str))

    @guarded()
    async def get_ranking(self, ranking_type):
        """ranking.getRanking for `ranking_type` (e.g. weeklyUserDamages): tier cutoffs, `count` and the top 100 entries, or None.

        Since 2026-11-16 it no longer lists every entry; use `get_ranking_entries` for the rest, or for the
        players of one country or MU.
        """
        return await self._get('ranking.getRanking', {'rankingType': ranking_type}, kind=None)

    @guarded()
    async def get_ranking_entries(self, ranking_type, country_id=None, mu_id=None):
        """Every entry of a ranking, best first, read page by page from ranking.getRankingPage; None if any page fails.

        `country_id` / `mu_id` keep the players of one country or MU (player rankings only). Entries whose
        value is 0 are not listed, and an entry's `rank` is its rank in the whole ranking. A whole unfiltered
        player ranking is ~460 pages read one after another, so filter when you can.
        """
        input_data = {'rankingType': ranking_type, 'limit': 50}
        if country_id:
            input_data['countryId'] = country_id
        if mu_id:
            input_data['muId'] = mu_id
        return await self._collect('ranking.getRankingPage', input_data, partial=False)

    @guarded()
    async def get_ranked_citizen_ids(self, country_id):
        """Ids of the citizens of `country_id` in its userWealth, userLevel or userDamages ranking; None if any fails.

        The rankings leave out entries at 0, so only a brand-new player with no wealth and no damage who isn't
        in the level ranking yet is missing (Romania, 2026-11-16: 462 of 472 citizens found). userDamages
        (all-time) keeps every player who ever fought, so period damage and bounty totals filtered by this set
        lose no one. The citizenship is the one the ranking recorded, which can lag behind a change.
        """
        if not country_id:
            return None
        rankings = await asyncio.gather(*(
            self.get_ranking_entries(ranking_type, country_id=country_id)
            for ranking_type in ('userWealth', 'userLevel', 'userDamages')
        ))
        if any(entries is None for entries in rankings):
            return None
        return {
            str(item['user']) for entries in rankings for item in entries
            if item.get('user') and item.get('country') == country_id
        }

    @guarded()
    async def get_articles(self, max_items=None):
        """Newest articles first, from every page, or only until `max_items` articles were fetched; None if the first page fails.

        With `max_items`, the first `max_items` items are the same as without it; the list may be longer.
        A later page that fails ends the list early.
        """
        return await self._collect('article.getArticlesPaginated', {'limit': 100, 'type': 'last'},
                                   partial=True, max_items=max_items)
