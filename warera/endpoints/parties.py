"""Political parties: party details with leader and member list."""
from warera.endpoints.base import Endpoint, guarded


class PartiesAPI(Endpoint):
    """`party.getById`.

    party.getById is not in the public OpenAPI spec (0.17.4-beta); it is documented by the community explorer
    (warera.realmarijn.nl) and may change without notice.
    """

    @guarded()
    async def get(self, party_id):
        """The party.getById object of `party_id`, or None.

        It carries `name`, `country`, `leader` (user id), `councilMembers` and `members` (every member's
        user id, the leader included) [observed 2026-11-07].
        """
        return await self._get('party.getById', {'partyId': party_id})

    @guarded(dict)
    async def get_many(self, party_ids):
        """Batched party.getById: {partyId: party} for the ids that resolved."""
        return await self._get_keyed('party.getById', party_ids, lambda party_id: {'partyId': party_id})
