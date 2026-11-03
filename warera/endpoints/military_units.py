"""Military units: units, members' stats, upgrades and market orders."""
from warera.endpoints.base import Endpoint, guarded


class MilitaryUnitsAPI(Endpoint):
    """`mu.*`, `muMember.getByMu`, MU `upgrade.getUpgradeByTypeAndEntity` and `tradingOrder.getPublicOrdersByOwner`."""

    @guarded()
    async def get(self, mu_id):
        """The mu.getById object of `mu_id`, or None. `members` lists the members' user ids."""
        return await self._get('mu.getById', {'muId': mu_id})

    @guarded(dict)
    async def get_many(self, mu_ids):
        """Batched mu.getById: {muId: mu} for the ids that resolved."""
        return await self._get_keyed('mu.getById', mu_ids, lambda mu_id: {'muId': mu_id})

    @guarded()
    async def get_all(self):
        """Every military unit from the paginated mu.getManyPaginated, or None if the first page fails.

        Each item has at least `name` and usually `members`. A later page that fails ends the list early.
        """
        return await self._collect('mu.getManyPaginated', {'limit': 100}, partial=True)

    # muMember.getByMu is not in the public OpenAPI spec (0.17.4-beta); it is documented by the community
    # explorer (warera.realmarijn.nl) and may change without notice.
    @guarded()
    async def get_members(self, mu_id):
        """One record per MU member with weekly/monthly/total damage and help counters ([] for none), or None."""
        return await self._get('muMember.getByMu', {'muId': mu_id}, kind=list, allow_empty=True)

    @guarded(dict)
    async def get_upgrades(self, mu_id, upgrade_types):
        """Batched upgrade.getUpgradeByTypeAndEntity for one MU: {upgradeType: upgrade} for the types that resolved.

        MU types are headquarters and dormitories. An upgrade carries level, status (active/disabled)
        and willBeActiveAt (pending activation) [observed 2026-10-14].
        """
        return await self._get_keyed('upgrade.getUpgradeByTypeAndEntity', upgrade_types,
                                     lambda kind: {'upgradeType': kind, 'muId': mu_id})

    # tradingOrder.getPublicOrdersByOwner is not in the public OpenAPI spec (0.17.4-beta); it is documented by
    # the community explorer (warera.realmarijn.nl) and may change without notice.
    @guarded()
    async def get_public_orders(self, mu_id):
        """An MU's open market orders: {buyOrders, sellOrders, allOrders, totalBuyMoneyInvested, totalSellMoneyExpected, …}."""
        return await self._get('tradingOrder.getPublicOrdersByOwner', {'muId': mu_id}, allow_empty=True)
