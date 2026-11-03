"""Countries, their governments and alliances, and regions."""
from warera.endpoints.base import Endpoint, guarded


class CountriesAPI(Endpoint):
    """`country.*`, `government.getByCountryId` and `alliance.getById`."""

    @guarded()
    async def get(self, country_id):
        """The country.getCountryById object of `country_id`, or None."""
        return await self._get('country.getCountryById', {'countryId': country_id})

    @guarded(dict)
    async def get_many(self, country_ids):
        """Batched country.getCountryById: {countryId: country} for the ids that resolved."""
        return await self._get_keyed('country.getCountryById', country_ids, lambda cid: {'countryId': cid})

    @guarded()
    async def get_all(self):
        """Every country (country.getAllCountries, about 180, unpaginated), or None."""
        return await self._get('country.getAllCountries', kind=list)

    @guarded()
    async def get_names(self):
        """The name of every country, in get_all() order, or None."""
        countries = await self.get_all()
        if not countries:
            return None
        return [country['name'] for country in countries]

    @guarded(dict)
    async def get_governments(self, country_ids):
        """Batched government.getByCountryId: {countryId: government} for the ids that resolved."""
        return await self._get_keyed('government.getByCountryId', country_ids, lambda cid: {'countryId': cid})

    @guarded()
    async def get_alliance(self, alliance_id):
        """The alliance with this id (`country.allianceId`), or None.

        `alliance.getById` is not in the official API spec (documented by the community explorer). The
        result carries `memberCountries`, a list of `{"country": <country id>, "suspended": bool, ...}`.
        """
        return await self._get('alliance.getById', {'allianceId': alliance_id})


class RegionsAPI(Endpoint):
    """`region.getById` and `region.getRegionsObject`."""

    @guarded()
    async def get(self, region_id):
        """The region.getById object of `region_id`, or None."""
        return await self._get('region.getById', {'regionId': region_id}, allow_empty=True)

    @guarded(dict)
    async def get_many(self, region_ids):
        """Batched region.getById: {regionId: region} for the ids that resolved."""
        return await self._get_keyed('region.getById', region_ids, lambda rid: {'regionId': rid})

    @guarded()
    async def get_all(self):
        """region.getRegionsObject: {regionId: region} for every region (about 0.9 MB), or None."""
        return await self._get('region.getRegionsObject', allow_empty=True)
