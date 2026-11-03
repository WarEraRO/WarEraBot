"""Companies, their production bonuses, and their NPC employees (v0.27)."""
from warera.endpoints.base import Endpoint, guarded, log_failure
from warera.exceptions import NotFoundError, WarEraAPIError


def _listing_ids(listing):
    """Company ids of a company.getCompanies page; its items are bare id strings or objects with `_id`."""
    return [item if isinstance(item, str) else (item or {}).get('_id') for item in listing.get('items') or []]


class CompaniesAPI(Endpoint):
    """`company.*`, `employee.getCompanyRoster` and `work.getStatsByEmployee`."""

    @guarded(dict)
    async def get_many(self, company_ids):
        """Batched company.getById: {companyId: company} for the ids that resolved."""
        return await self._get_keyed('company.getById', company_ids, lambda cid: {'companyId': cid})

    @guarded()
    async def get_owned_by(self, user_id):
        """Every company `user_id` owns, as company.getById objects in listing order, or None.

        company.getCompanies returns bare id strings, so the companies are then fetched in one batched
        company.getById request. One page of 100 covers every player (Companies skill 10 allows 12).
        None when the listing or any company fails to load, so callers never plan from a partial list.
        """
        listing = await self._get('company.getCompanies', {'userId': user_id, 'perPage': 100}, allow_empty=True)
        if listing is None:
            return None
        ids = _listing_ids(listing)
        companies = await self.client.call_many('company.getById', [{'companyId': cid} for cid in ids if cid])
        if len(companies) != len(ids) or not all(isinstance(company, dict) and company for company in companies):
            errors = [company for company in companies if isinstance(company, WarEraAPIError)]
            if errors:
                log_failure('company.getById', errors[0])
            return None
        return companies

    @guarded(dict)
    async def get_ids_owned_by_many(self, user_ids):
        """Batched company.getCompanies: {userId: [companyId]} for the users whose listing loaded.

        The listing holds 10 ids unless perPage is raised; one page of 100 covers every player.
        """
        listings = await self._get_keyed('company.getCompanies', user_ids, lambda uid: {'userId': uid, 'perPage': 100})
        return {user_id: [cid for cid in _listing_ids(listing) if cid] for user_id, listing in listings.items()}

    @guarded(dict)
    async def get_production_bonuses(self, company_ids):
        """Batched company.getProductionBonus: {companyId: bonus} for the ids that resolved.

        Not in the official spec (explorer-documented). A bonus is {strategicBonus, depositBonus,
        ethicSpecializationBonus, ethicDepositBonus, total}, in percent [observed 2026-10-25].
        """
        return await self._get_keyed('company.getProductionBonus', company_ids, lambda cid: {'companyId': cid})

    # employee.getCompanyRoster and work.getStatsByEmployee are not in the official spec: the first is a
    # game-client query opened to API keys in v0.27.2 (2026-10-28), the second is explorer-documented.
    @guarded(dict)
    async def get_rosters(self, company_ids):
        """Batched employee.getCompanyRoster: {companyId: roster} for the ids that resolved. Requires an API key.

        A roster is {employees: [employee], hourly}; each employee has _id, owner, company and createdAt
        (the hire time) [observed 2026-10-28]. An unknown company id answers 404, logged at debug only.
        """
        return await self._get_keyed('employee.getCompanyRoster', company_ids, lambda cid: {'companyId': cid},
                                     expected=(NotFoundError,))

    @guarded(dict)
    async def get_employee_work_stats(self, employee_ids):
        """Batched work.getStatsByEmployee: {employeeId: [day]} for the ids that resolved. Requires an API key.

        Each day is {dailyDate (YYYY-MM-DD, UTC game day), total, wage, employeeProd}, with production in
        production points [observed 2026-11-01].
        """
        return await self._get_keyed('work.getStatsByEmployee', employee_ids, lambda eid: {'employeeId': eid}, kind=list)
