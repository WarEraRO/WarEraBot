"""Countries, their governments, alliances and wars, and regions."""
from warera.endpoints.base import Endpoint, guarded


class CountriesAPI(Endpoint):
    """`country.*`, `government.getByCountryId`, `alliance.getById`, `war.getById` and war events."""

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

    @guarded(dict)
    async def get_wars_many(self, war_ids):
        """Batched war.getById (explorer-documented): {warId: war} for the ids that resolved.

        A war carries `isActive`, `attacker`/`defender` (`{country, wonBattlesCount, ...}`), `priority`
        (the id of the country holding the war's priority) and `priorityEndAt` (ISO; kept once it passes).
        """
        return await self._get_keyed('war.getById', war_ids, lambda wid: {'warId': wid})

    @guarded()
    async def get_war_events_since(self, country_id, created_after):
        """warDeclared and peaceMade events involving `country_id` created at or after `created_after` (ISO), newest first.

        `data` is `{type: "warDeclared", war, attackerCountry, defenderCountry}` or
        `{type: "peaceMade", wars: [warId], countries}`. None if any page fails.
        """
        return await self._collect_since('event.getEventsPaginated',
                                         {'countryId': country_id, 'eventTypes': ['warDeclared', 'peaceMade'],
                                          'limit': 100},
                                         created_after)


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
