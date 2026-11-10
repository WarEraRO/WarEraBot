"""Battles, rounds, battle rankings, orders and loot; tournaments; mercenary contracts."""
from warera.endpoints.base import Endpoint, guarded, log_failure
from warera.exceptions import NotFoundError, ProcedureNotFoundError, WarEraAPIError


class BattlesAPI(Endpoint):
    """`battle.*`, `round.getById`, `battleOrder.getByBattle`, `battleRanking.getRanking` and `battleLootSummary.*`."""

    @guarded()
    async def get(self, battle_id):
        """The battle.getById object of `battle_id`, or None."""
        return await self._get('battle.getById', {'battleId': battle_id}, allow_empty=True)

    @guarded()
    async def get_active(self):
        """Every active battle (all battle.getBattles pages), or None if the first page fails.

        A later page that fails ends the list early.
        """
        return await self._collect('battle.getBattles', {'isActive': True, 'limit': 100}, partial=True)

    @guarded()
    async def get_active_for_country(self, country_id):
        """Every active battle with `country_id` as attacker or defender (all pages); None if any page fails.

        Unlike get_active, a partial list is never returned: a missing battle would make a war look idle.
        """
        return await self._collect('battle.getBattles', {'isActive': True, 'limit': 100, 'countryId': country_id},
                                   partial=False)

    @guarded()
    async def get_ended_for_country_since(self, country_id, created_after):
        """Ended battles with `country_id` as a side, created at or after `created_after` (ISO), newest first.

        Filtered on createdAt, not endedAt: to get the battles that ended since a moment, ask from far
        enough back to cover the longest battle. None if any page fails.
        """
        return await self._collect_since('battle.getBattles', {'isActive': False, 'limit': 100, 'countryId': country_id},
                                         created_after)

    @guarded()
    async def get_ended_since(self, created_after):
        """Ended battles created at or after `created_after` (ISO string), newest first; None if any page fails.

        The list is sorted by createdAt descending, so paging stops at the first older item. A partial
        list would silently undercount battles, hence None.
        """
        return await self._collect_since('battle.getBattles', {'isActive': False, 'limit': 100}, created_after)

    @guarded()
    async def get_round(self, round_id):
        """The round.getById object of `round_id`, or None."""
        return await self._get('round.getById', {'roundId': round_id}, allow_empty=True)

    @guarded(dict)
    async def get_orders_many(self, battle_sides):
        """Batched battleOrder.getByBattle: {(battleId, side): [order]} for the pairs with orders.

        Each order carries `country` or `mu`, `priority` (low/medium/high) and `rank`/`text`; rank and text
        are filled in only for citizens of the ordering country or members of the ordering MU [spec].
        A side without orders is missing, like a failed call.
        """
        return await self._get_keyed('battleOrder.getByBattle', battle_sides,
                                     lambda pair: {'battleId': pair[0], 'side': pair[1]}, kind=list)

    @guarded()
    async def get_ranking(self, battle_id, data_type, ranking_type, side):
        """Every entry of a battle leaderboard, or None if any page fails.

        `data_type` is damage, points or money; `ranking_type` user, country, mu or alliance
        (alliance since v0.28.1, 2026-11-07); `side` attacker, defender or merged.
        """
        return await self._collect('battleRanking.getRanking', {
            'battleId': battle_id, 'dataType': data_type, 'type': ranking_type, 'side': side, 'limit': 100,
        }, partial=False)

    @guarded()
    async def get_ranking_pages(self, scope, data_type, ranking_type, side, stop=None, max_pages=None):
        """battleRanking.getRanking entries from the top for one scope ({"battleId"}, {"roundId"} or {"warId"}).

        Pages are read until `stop(items)` returns True, the ranking ends or `max_pages` pages were read.
        Returns (items, complete), where complete is True only when the whole ranking was read; None when
        the first page fails. A later page that fails ends the read with complete False.
        """
        input_data = {**scope, 'dataType': data_type, 'type': ranking_type, 'side': side, 'limit': 100}
        items, pages = [], 0
        while True:
            try:
                page = await self.client.call('battleRanking.getRanking', input_data)
            except WarEraAPIError as error:
                log_failure('battleRanking.getRanking', error)
                return None if not pages else (items, False)
            page = page if isinstance(page, dict) else {}
            items += page.get('items') or []
            pages += 1
            next_cursor = page.get('nextCursor')
            if not next_cursor:
                return items, True
            if (stop and stop(items)) or (max_pages and pages >= max_pages):
                return items, False
            input_data['cursor'] = next_cursor

    @guarded(dict)
    async def get_loot_summaries(self, battle_id, user_ids):
        """Batched battleLootSummary.getByBattleAndUser: {userId: summary} for the users who hit the battle.

        A user with no hits in the battle gets a 404 [observed], so is missing from the dict, like a
        failed call; those 404s are expected and logged at debug only.
        """
        return await self._get_keyed('battleLootSummary.getByBattleAndUser', user_ids,
                                     lambda uid: {'battleId': battle_id, 'userId': uid}, expected=(NotFoundError,))

    @guarded(dict)
    async def get_loot_summaries_many(self, pairs):
        """Batched battleLootSummary.getByBattleAndUser over many battles: {(battleId, userId): summary or None}.

        The (battleId, userId) pairs may span battles, so they share batches. Unlike get_loot_summaries,
        "no hits in that battle" (404) is kept apart from a failure: such a pair maps to None, while a pair
        whose call failed for another reason is missing from the dict, so callers know what to retry.
        """
        pairs = list(dict.fromkeys(pairs))
        if not pairs:
            return {}
        values = await self.client.call_many('battleLootSummary.getByBattleAndUser',
                                             [{'battleId': battle_id, 'userId': user_id} for battle_id, user_id in pairs])
        result = {}
        for pair, value in zip(pairs, values):
            if isinstance(value, WarEraAPIError):
                log_failure('battleLootSummary.getByBattleAndUser', value, expected=(NotFoundError,))
                if isinstance(value, NotFoundError) and not isinstance(value, ProcedureNotFoundError):
                    result[pair] = None
            elif isinstance(value, dict) and value:
                result[pair] = value
        return result



class TournamentsAPI(Endpoint):
    """`tournament.*` and `tournamentTeam.getById`.

    None of these is in the public OpenAPI spec (0.17.4-beta): getLastTournament is explorer-documented,
    getById and tournamentTeam.getById are what the game client uses and may change without notice.
    """

    @guarded()
    async def get_last(self):
        """The most recently created or active tournament, or None."""
        return await self._get('tournament.getLastTournament', {}, allow_empty=True)

    @guarded()
    async def get(self, tournament_id):
        """The tournament.getById object; its `type` is `country` or `mu`. None on failure."""
        return await self._get('tournament.getById', {'tournamentId': tournament_id}, allow_empty=True)

    @guarded()
    async def get_team(self, tournament_team_id):
        """The tournamentTeam.getById object: `countries[]` is the coalition, `mus[]` the MU. None on failure."""
        return await self._get('tournamentTeam.getById', {'tournamentTeamId': tournament_team_id}, allow_empty=True)


class ContractsAPI(Endpoint):
    """Mercenary contract auctions (`mercenaryContractAuction.getPaginatedAuctions`)."""

    @guarded()
    async def get_active_auctions(self):
        """Every active auction (all pages of 50), or None if the first page fails; a later failure ends it early."""
        return await self._collect('mercenaryContractAuction.getPaginatedAuctions', {'limit': 50, 'status': 'active'},
                                   partial=True)

    @guarded()
    async def get_won_since(self, created_after):
        """Won mercenary contracts created at or after `created_after` (ISO string), newest first.

        The list is sorted by createdAt descending, so paging stops at the first older item. None if any
        page fails: a partial list could hide contracts from a monitor's startup seed.
        """
        return await self._collect_since('mercenaryContractAuction.getPaginatedAuctions', {'status': 'won', 'limit': 50},
                                         created_after)

    @guarded(dict)
    async def get_won_by_battles(self, battle_ids):
        """Batched won auctions per battle: {battleId: [auction]}, first page only.

        One page holds the 50 newest won contracts of a battle [observed 2026-10-14: the battleId filter
        works]; battles whose call failed are missing from the dict.
        """
        pages = await self._get_keyed('mercenaryContractAuction.getPaginatedAuctions', battle_ids,
                                      lambda bid: {'battleId': bid, 'status': 'won', 'limit': 50})
        return {battle_id: page.get('items') or [] for battle_id, page in pages.items()}
