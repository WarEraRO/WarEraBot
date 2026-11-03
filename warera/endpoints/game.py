"""Game-wide data: configuration, statistics, global rankings and articles."""
from warera.endpoints.base import Endpoint, guarded


class GameAPI(Endpoint):
    """`gameConfig.getGameConfig`, `gameConfig.getDates`, `gameStat.*`, `ranking.getRanking` and `article.getArticlesPaginated`."""

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
        """ranking.getRanking for `ranking_type` (e.g. weeklyUserDamages): every entry, unpaginated, or None."""
        return await self._get('ranking.getRanking', {'rankingType': ranking_type}, kind=None)

    @guarded()
    async def get_articles(self, max_items=None):
        """Newest articles first, from every page, or only until `max_items` articles were fetched; None if the first page fails.

        With `max_items`, the first `max_items` items are the same as without it; the list may be longer.
        A later page that fails ends the list early.
        """
        return await self._collect('article.getArticlesPaginated', {'limit': 100, 'type': 'last'},
                                   partial=True, max_items=max_items)
