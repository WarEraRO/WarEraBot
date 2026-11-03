"""Players: lookups by id and by username, country listings and equipment."""
from warera.endpoints.base import Endpoint, guarded


def _quoted(username):
    """The search text that asks search.searchAnything for `username` as an exact phrase.

    A plain search is fuzzy and returns at most 5 users, so a short name is often crowded out by
    longer names containing it ("Tert" returned 5 others, not Tert). Quoted, every one of 257
    linked server members was found, most as the only result [observed 2026-10-24; not in the spec].
    """
    return f'"{username}"'


class UsersAPI(Endpoint):
    """`user.*`, `search.searchAnything` and `inventory.fetchCurrentEquipment`.

    `username_ids` maps every username resolved by an exact match to its user id, for the life of the
    process; the name lookups trust it without re-checking the username.
    """

    def __init__(self, client):
        """Bind to `client` with an empty username cache."""
        super().__init__(client)
        self.username_ids = {}

    @guarded()
    async def get(self, user_id):
        """The user.getUserLite object of `user_id`, or None."""
        return await self._get('user.getUserLite', {'userId': user_id})

    @guarded(dict)
    async def get_many(self, user_ids):
        """Batched user.getUserLite: {userId: user} for the ids that resolved."""
        return await self._get_keyed('user.getUserLite', user_ids, lambda uid: {'userId': uid})

    @guarded(dict)
    async def get_full_many(self, user_ids):
        """Batched user.getUserById: {userId: user} for the ids that resolved.

        Same request cost as get_many. The full user carries the getUserLite fields the bot reads
        (skills, buffs, dates, leveling, mu) plus stats.wealth, region and location [observed 2026-10-14].
        """
        return await self._get_keyed('user.getUserById', user_ids, lambda uid: {'userId': uid})

    @guarded(dict)
    async def get_equipment_many(self, user_ids):
        """Batched inventory.fetchCurrentEquipment: {userId: equipment} for the ids that resolved.

        Equipment maps slots (weapon, helmet, chest, pants, boots, gloves) to items with code, state and
        maxState, and `ammo` to the ammo code. A player with nothing equipped returns {}, so is missing.
        """
        return await self._get_keyed('inventory.fetchCurrentEquipment', user_ids, lambda uid: {'userId': uid})

    @guarded()
    async def get_by_country(self, country_id):
        """Every user.getUsersByCountry item of `country_id` (all pages), or None if the first page fails.

        A later page that fails ends the list early. Not a full citizen directory: it missed a
        Romanian citizen [observed 2026-10-24].
        """
        return await self._collect('user.getUsersByCountry', {'limit': 100, 'countryId': country_id}, partial=True)

    @guarded()
    async def find_by_name(self, username):
        """The user (getUserLite) whose username is exactly `username`, or None.

        Searches the quoted name first and falls back to the plain name if that finds no exact match.
        A cached id is fetched without re-checking the username.
        """
        if username in self.username_ids:
            return await self.get(self.username_ids[username])
        for search_text in (_quoted(username), username):
            search = await self._get('search.searchAnything', {'searchText': search_text})
            if not search or search.get('hasData') is False:
                continue
            user_ids = search.get('userIds') or []
            candidates = await self.get_many(user_ids)
            for user_id in user_ids:
                user = candidates.get(user_id)
                if user is not None and user.get('username') == username:
                    self.username_ids[username] = user.get('_id')
                    return user
        return None

    @guarded(dict)
    async def find_many_by_name(self, usernames):
        """Batched find_by_name(): {username: user} for the usernames that resolved.

        Like find_by_name, a cached id is fetched without re-checking the username.
        """
        names = list(dict.fromkeys(usernames))
        cached = {name: self.username_ids[name] for name in names if name in self.username_ids}
        users_by_id = await self.get_many(cached.values())
        found = {name: users_by_id[uid] for name, uid in cached.items() if uid in users_by_id}
        missing = [name for name in names if name not in cached]
        if missing:
            found.update(await self._search_names(missing))
        return found

    @guarded(dict)
    async def ids_by_name(self, usernames):
        """{username: userId}; cached names cost no request, only the rest are searched."""
        names = list(dict.fromkeys(usernames))
        found = {name: self.username_ids[name] for name in names if name in self.username_ids}
        missing = [name for name in names if name not in found]
        if missing:
            for name, user in (await self._search_names(missing)).items():
                found[name] = user.get('_id')
        return found

    async def _search_names(self, usernames):
        """Resolve usernames with batched search + getUserLite; exact matches go into `username_ids`.

        Names are searched quoted first (see _quoted); only the names that found no exact match are
        searched again plain.
        """
        names = list(dict.fromkeys(usernames))
        found = {}
        for search_text in (_quoted, lambda name: name):
            missing = [name for name in names if name not in found]
            if not missing:
                break
            searches = await self._get_keyed('search.searchAnything', missing,
                                             lambda name, text=search_text: {'searchText': text(name)})
            candidate_ids = []
            for name in missing:
                search = searches.get(name)
                if search and search.get('hasData') is not False:
                    candidate_ids.extend(search.get('userIds') or [])
            candidates = await self.get_many(candidate_ids)
            by_username = {user.get('username'): user for user in candidates.values()}
            for name in missing:
                user = by_username.get(name)
                if user is not None:
                    self.username_ids[name] = user.get('_id')
                    found[name] = user
        return found
