"""Market prices and money transactions."""
from warera.endpoints.base import Endpoint, guarded


def _page_ends_before(page_items, created_after):
    """True when the last item of a newest-first page was created before `created_after` (ISO string)."""
    if created_after is None or not page_items:
        return False
    last_created_at = page_items[-1].get('createdAt')
    return isinstance(last_created_at, str) and last_created_at < created_after


class MarketAPI(Endpoint):
    """`itemTrading.getPrices` and `transaction.getPaginatedTransactions` (the latter requires an API key)."""

    @guarded()
    async def get_prices(self):
        """{itemCode: price} for every tradable item (itemTrading.getPrices, no input), or None."""
        return await self._get('itemTrading.getPrices')

    @guarded()
    async def get_user_transactions(self, user_id, transaction_type, created_after=None):
        """A user's transactions of one type, newest first, or None if the first page fails. Requires an API key.

        With `created_after` (ISO string), paging stops after the first page that reaches older transactions;
        every transaction created at or after it is still returned, and some older ones may be too. A later
        page that fails ends the list early.
        """
        # sorted by createdAt descending [observed 2026-10-12 across pages], so later pages are all older
        return await self._collect('transaction.getPaginatedTransactions',
                                   {'limit': 100, 'userId': user_id, 'transactionType': transaction_type},
                                   partial=True, stop_page=lambda items: _page_ends_before(items, created_after))

    @guarded()
    async def get_mu_transactions(self, mu_id, transaction_type, created_after):
        """An MU's transactions of one type (or a list of types) created at or after `created_after` (ISO string).

        Newest first; requires an API key. The list is sorted by createdAt descending, so paging stops at
        the first older item. None if any page fails.
        """
        return await self._collect_since('transaction.getPaginatedTransactions',
                                         {'muId': mu_id, 'transactionType': transaction_type, 'limit': 100}, created_after)

    @guarded()
    async def get_country_transactions(self, country_id, transaction_type, created_after):
        """A country's transactions of one type (or a list of types) created at or after `created_after` (ISO string).

        Newest first; requires an API key. With "donation" these are donations *to* the country (donor in
        `buyerId`, the country in `sellerCountryId`). Paging stops at the first older item. None if any page fails.
        """
        # countryId + donation lists donations to that country [observed 2026-11-02, Romania]
        return await self._collect_since('transaction.getPaginatedTransactions',
                                         {'countryId': country_id, 'transactionType': transaction_type, 'limit': 100},
                                         created_after)
