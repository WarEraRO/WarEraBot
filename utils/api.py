import json
import asyncio
import logging
from datetime import datetime, timezone
from aiohttp import ClientError
import discord
import aiohttp
from config import config
from utils.computational import triangular

PLAYER_CACHE = {}

logger = logging.getLogger(__name__)

# Shared aiohttp session to avoid repeatedly creating/closing sessions which
# can leak file descriptors / sockets when done frequently.
_shared_session: aiohttp.ClientSession | None = None

async def get_shared_session() -> aiohttp.ClientSession:
    """Return a singleton ClientSession, creating it if needed."""
    global _shared_session
    api_key = config.get('api')
    if _shared_session is None or getattr(_shared_session, 'closed', False):
        headers = {'X-API-Key': api_key}
        _shared_session = aiohttp.ClientSession(headers=headers)
    else:
        # Ensure session uses current API key in case it was rotated at runtime
        try:
            if api_key and _shared_session.headers.get('X-API-Key') != api_key:
                _shared_session.headers['X-API-Key'] = api_key
        except Exception:
            # Non-fatal: log and continue using existing session
            logger.exception('Failed updating shared session headers')
    return _shared_session

async def close_shared_session() -> None:
    """Close the shared ClientSession if it exists."""
    global _shared_session
    if _shared_session is not None and not getattr(_shared_session, 'closed', False):
        try:
            await _shared_session.close()
        finally:
            _shared_session = None


async def _get_with_retry(session, url, params=None, max_retries=5, initial_backoff=1.0, backoff_factor=2.0, max_backoff=60.0, quiet_statuses=()):
    # quiet_statuses: client error codes that are an expected answer (e.g. 404 "no hits"); still None, logged at debug
    attempt = 0
    while True:
        try:
            async with session.get(url, params=params) as response:
                # Handle rate limiting
                if response.status == 429:
                    retry_after = response.headers.get('Retry-After')
                    try:
                        wait = int(retry_after) if retry_after is not None else int(initial_backoff * (backoff_factor ** attempt))
                    except Exception:
                        wait = initial_backoff * (backoff_factor ** attempt)
                    wait = min(wait, max_backoff)
                    logger.warning('429 from %s, retrying after %s seconds (attempt %d)', url, wait, attempt + 1)
                    await asyncio.sleep(wait)
                    attempt += 1
                    if attempt >= max_retries:
                        logger.error('Max retries reached for %s', url)
                        return None
                    continue

                # Do not retry on client errors (4xx) except 429; report and bail out
                if 400 <= response.status < 500:
                    try:
                        body = await response.text()
                    except Exception:
                        body = '<unreadable body>'
                    if response.status in quiet_statuses:
                        logger.debug('Client error %s from %s', response.status, url)
                    else:
                        logger.error('Client error %s from %s, body=%s', response.status, url, body)
                    return None

                # Retry on server errors
                if 500 <= response.status < 600:
                    wait = min(initial_backoff * (backoff_factor ** attempt), max_backoff)
                    logger.warning('Server error %s from %s, retrying after %s seconds (attempt %d)', response.status, url, wait, attempt + 1)
                    await asyncio.sleep(wait)
                    attempt += 1
                    if attempt >= max_retries:
                        logger.error('Max retries reached for %s', url)
                        return None
                    continue

                response.raise_for_status()
                return await response.json()

        except (ClientError, asyncio.TimeoutError) as e:
            wait = min(initial_backoff * (backoff_factor ** attempt), max_backoff)
            logger.warning('Network error contacting %s: %s; retrying in %s seconds (attempt %d)', url, e, wait, attempt + 1)
            await asyncio.sleep(wait)
            attempt += 1
            if attempt >= max_retries:
                logger.exception('Max retries reached for %s: %s', url, e)
                return None
        except Exception as e:
            logger.exception('Unexpected error contacting %s: %s', url, e)
            return None

def _quoted(username):
    """The search text that asks search.searchAnything for `username` as an exact phrase.

    A plain search is fuzzy and returns at most 5 users, so a short name is often crowded out by
    longer names containing it ("Tert" returned 5 others, not Tert). Quoted, every one of 257
    linked server members was found, most as the only result [observed 2026-10-24; not in the spec].
    """
    return f'"{username}"'

async def get_user(username, session, base_url="https://api2.warera.io/trpc/search.searchAnything"):
    """The user whose username is exactly `username`, or None.

    Searches the quoted name first and falls back to the plain name if that finds no exact match.
    A cached id is fetched without re-checking the username.
    """
    try:
        if username in PLAYER_CACHE.keys():
            user = await get_user_info(PLAYER_CACHE[username], session)
            return user

        for search_text in (_quoted(username), username):
            input_data = {'searchText': search_text}
            params = {"input": json.dumps(input_data)}
            data = await _get_with_retry(session, base_url, params=params)
            if not data:
                continue
            api_result = data.get('result', {}).get('data')
            if not api_result or api_result.get('hasData') is False:
                continue
            for userId in api_result.get('userIds', []) or []:
                user = await get_user_info(userId, session)
                if user is None:
                    continue
                if username == user.get('username'):
                    PLAYER_CACHE[username] = user.get('_id')
                    return user
        return None
    except Exception as e:
        logger.exception('get_user failed: %s', e)
        return None

async def get_user_info(userId, session, base_url="https://api2.warera.io/trpc/user.getUserLite"):
    try:
        input_data = {'userId': userId}
        params = {"input": json.dumps(input_data)}
        data = await _get_with_retry(session, base_url, params=params)
        if not data:
            return None
        api_result = data.get('result', {}).get('data')
        if not api_result:
            return None
        return api_result
    except Exception as e:
        logger.exception('get_user_info failed: %s', e)
        return None

# tRPC httpBatchLink: N calls of one procedure in a single GET. A batch counts as one request
# against the rate limit [observed 2026-10-09: 5, 25, 50 and 100 calls each cost 1].
# 50 calls per chunk keeps the URL around 4.5 KB.
BATCH_CHUNK_SIZE = 50

async def _get_batch(session, procedure, inputs, chunk_size=BATCH_CHUNK_SIZE, base_url="https://api2.warera.io/trpc", quiet_statuses=()):
    """Run `procedure` once per item of `inputs` using tRPC batching.

    Returns a list aligned with `inputs`: each item's `result.data`, or None when that call
    errored or its chunk failed. Never raises. `quiet_statuses` is passed to _get_with_retry.
    """
    results = []
    for start in range(0, len(inputs), chunk_size):
        chunk = inputs[start:start + chunk_size]
        try:
            url = f"{base_url}/{','.join([procedure] * len(chunk))}"
            params = {"batch": "1", "input": json.dumps({str(i): inp for i, inp in enumerate(chunk)})}
            data = await _get_with_retry(session, url, params=params, quiet_statuses=quiet_statuses)
            if not isinstance(data, list) or len(data) != len(chunk):
                results.extend([None] * len(chunk))
                continue
            for envelope in data:
                results.append(((envelope or {}).get('result') or {}).get('data') or None)
        except Exception as e:
            logger.exception('_get_batch %s failed: %s', procedure, e)
            results.extend([None] * len(chunk))
    return results

async def get_users_info(user_ids, session):
    """Batched user.getUserLite: {userId: user} for the ids that resolved."""
    ids = list(dict.fromkeys(user_ids))
    users = await _get_batch(session, 'user.getUserLite', [{'userId': uid} for uid in ids])
    return {uid: user for uid, user in zip(ids, users) if user}

async def get_users_full(user_ids, session):
    """Batched user.getUserById: {userId: user} for the ids that resolved.

    Same request cost as get_users_info. The full user carries the getUserLite fields the bot reads
    (skills, buffs, dates, leveling, mu) plus stats.wealth, region and location [observed 2026-10-14].
    """
    ids = list(dict.fromkeys(user_ids))
    users = await _get_batch(session, 'user.getUserById', [{'userId': uid} for uid in ids])
    return {uid: user for uid, user in zip(ids, users) if user}

async def get_military_units_by_ids(mu_ids, session):
    """Batched mu.getById: {muId: mu} for the ids that resolved."""
    ids = list(dict.fromkeys(mu_ids))
    mus = await _get_batch(session, 'mu.getById', [{'muId': mu_id} for mu_id in ids])
    return {mu_id: mu for mu_id, mu in zip(ids, mus) if mu}

async def get_countries_by_ids(country_ids, session):
    """Batched country.getCountryById: {countryId: country} for the ids that resolved."""
    ids = list(dict.fromkeys(country_ids))
    countries = await _get_batch(session, 'country.getCountryById', [{'countryId': country_id} for country_id in ids])
    return {country_id: country for country_id, country in zip(ids, countries) if country}

async def get_battle_orders(battle_sides, session):
    """Batched battleOrder.getByBattle: {(battleId, side): [order]} for the (battleId, side) pairs that resolved.

    Each order carries `country` or `mu`, `priority` (low/medium/high) and `rank`/`text`; rank and text
    are filled in only for citizens of the ordering country or members of the ordering MU [spec].
    """
    pairs = list(dict.fromkeys(battle_sides))
    orders = await _get_batch(session, 'battleOrder.getByBattle', [{'battleId': battle_id, 'side': side} for battle_id, side in pairs])
    return {pair: items for pair, items in zip(pairs, orders) if isinstance(items, list)}

async def get_regions_by_ids(region_ids, session):
    """Batched region.getById: {regionId: region} for the ids that resolved."""
    ids = list(dict.fromkeys(region_ids))
    regions = await _get_batch(session, 'region.getById', [{'regionId': region_id} for region_id in ids])
    return {region_id: region for region_id, region in zip(ids, regions) if region}

async def get_mu_upgrades(mu_id, upgrade_types, session):
    """Batched upgrade.getUpgradeByTypeAndEntity for one MU: {upgradeType: upgrade} for the types that resolved.

    MU types are headquarters and dormitories. An upgrade carries level, status (active/disabled)
    and willBeActiveAt (pending activation) [observed 2026-10-14].
    """
    types = list(dict.fromkeys(upgrade_types))
    upgrades = await _get_batch(session, 'upgrade.getUpgradeByTypeAndEntity', [{'upgradeType': kind, 'muId': mu_id} for kind in types])
    return {kind: upgrade for kind, upgrade in zip(types, upgrades) if isinstance(upgrade, dict)}

async def get_won_auctions_by_battles(battle_ids, session):
    """Batched mercenaryContractAuction.getPaginatedAuctions (status won): {battleId: [auction]}, first page only.

    One page holds the 50 newest won contracts of a battle [observed 2026-10-14: the battleId filter works];
    battles whose call failed are missing from the dict.
    """
    ids = list(dict.fromkeys(battle_ids))
    pages = await _get_batch(session, 'mercenaryContractAuction.getPaginatedAuctions', [{'battleId': battle_id, 'status': 'won', 'limit': 50} for battle_id in ids])
    return {battle_id: page.get('items') or [] for battle_id, page in zip(ids, pages) if isinstance(page, dict)}

async def get_users_equipment(user_ids, session):
    """Batched inventory.fetchCurrentEquipment: {userId: equipment} for the ids that resolved.

    Equipment maps slots (weapon, helmet, chest, pants, boots, gloves) to items with code, state and maxState,
    and `ammo` to the ammo code. A player with nothing equipped returns {}, which the batch reports as missing.
    """
    ids = list(dict.fromkeys(user_ids))
    equipment = await _get_batch(session, 'inventory.fetchCurrentEquipment', [{'userId': user_id} for user_id in ids])
    return {user_id: items for user_id, items in zip(ids, equipment) if isinstance(items, dict)}

async def get_last_tournament(session, base_url="https://api2.warera.io/trpc/tournament.getLastTournament"):
    """The most recently created or active tournament (not in the official spec; explorer-documented)."""
    try:
        data = await _get_with_retry(session, base_url, params={"input": json.dumps({})})
        api_result = (data or {}).get("result", {}).get("data")
        if isinstance(api_result, dict):
            return api_result
        return None
    except Exception as e:
        logger.exception('get_last_tournament failed: %s', e)
        return None

async def get_country_governments(country_ids, session):
    """Batched government.getByCountryId: {countryId: government} for the ids that resolved."""
    ids = list(dict.fromkeys(country_ids))
    governments = await _get_batch(session, 'government.getByCountryId', [{'countryId': country_id} for country_id in ids])
    return {country_id: government for country_id, government in zip(ids, governments) if government}

async def _search_users_by_name(usernames, session):
    """Resolve uncached usernames with batched search + getUserLite; exact matches go into PLAYER_CACHE.

    Names are searched quoted first (see _quoted); only the names that found no exact match are
    searched again plain.
    """
    names = list(dict.fromkeys(usernames))
    found = {}
    for search_text in (_quoted, lambda name: name):
        missing = [name for name in names if name not in found]
        if not missing:
            break
        searches = await _get_batch(session, 'search.searchAnything', [{'searchText': search_text(name)} for name in missing])
        candidate_ids = []
        for search in searches:
            if search and search.get('hasData') is not False:
                candidate_ids.extend(search.get('userIds') or [])
        candidates = await get_users_info(candidate_ids, session)
        by_username = {user.get('username'): user for user in candidates.values()}
        for name in missing:
            user = by_username.get(name)
            if user is not None:
                PLAYER_CACHE[name] = user.get('_id')
                found[name] = user
    return found

async def get_users_by_name(usernames, session):
    """Batched get_user(): {username: user} for the usernames that resolved.

    Like get_user, a cached id is fetched without re-checking the username.
    """
    try:
        names = list(dict.fromkeys(usernames))
        cached = {name: PLAYER_CACHE[name] for name in names if name in PLAYER_CACHE}
        users_by_id = await get_users_info(cached.values(), session)
        found = {name: users_by_id[uid] for name, uid in cached.items() if uid in users_by_id}
        missing = [name for name in names if name not in cached]
        if missing:
            found.update(await _search_users_by_name(missing, session))
        return found
    except Exception as e:
        logger.exception('get_users_by_name failed: %s', e)
        return {}

async def get_user_ids_by_name(usernames, session):
    """{username: userId}; cached names cost no request, only the rest are searched."""
    try:
        names = list(dict.fromkeys(usernames))
        found = {name: PLAYER_CACHE[name] for name in names if name in PLAYER_CACHE}
        missing = [name for name in names if name not in found]
        if missing:
            for name, user in (await _search_users_by_name(missing, session)).items():
                found[name] = user.get('_id')
        return found
    except Exception as e:
        logger.exception('get_user_ids_by_name failed: %s', e)
        return {}

async def get_all_countries(session, base_url="https://api2.warera.io/trpc/country.getAllCountries"):
    try:
        data = await _get_with_retry(session, base_url)
        if not data:
            return None
        api_result = data.get('result', {}).get('data')
        if not api_result:
            return None
        return api_result
    except Exception as e:
        logger.exception('get_all_countries failed: %s', e)
        return None
    
async def get_all_country_names():
    session = await get_shared_session()
    countries = await get_all_countries(session)
    if not countries:
        return None
    lst = []
    for c in countries:
        lst.append(c['name'])
    return lst

async def get_country_government(counrtyId, session, base_url="https://api2.warera.io/trpc/government.getByCountryId"):
    try:
        input_data = {'countryId': counrtyId}
        params = {"input": json.dumps(input_data)}
        data = await _get_with_retry(session, base_url, params=params)
        if not data:
            return None
        api_result = data.get('result', {}).get('data')
        if not api_result:
            return None
        return api_result
    except Exception as e:
        logger.exception('get_country_government failed: %s', e)
        return None

async def get_fight_status(userId: str, session, member: discord.Member | None = None, eco=True, base_url: str = "https://api2.warera.io/trpc/user.getUserLite") -> dict | None:
    """Fetch lightweight user info and return a dict with fight-related fields.

    Returns a dict or None on failure. Dict keys:
    - userId, warera_name, display_name, avatar_url, level, is_active,
      health_curr, health_total, hunger_curr, hunger_total, buff_text
    """
    try:
        api_result = await get_user_info(userId, session, base_url=base_url)
        if not api_result:
            return None
        return fight_status_from_user(userId, api_result, member, eco)
    except Exception as e:
        logger.exception('get_fight_status failed for %s: %s', userId, e)
        return None

def fight_status_from_user(userId: str, api_result: dict, member: discord.Member | None = None, eco=True) -> dict | None:
    """get_fight_status() for a user.getUserLite result that was already fetched (no request).

    Returns the same dict, or None for an economy build when `eco` is False or on failure.
    """
    try:
        if not eco:
            economy_skill_points = 0
            fight_skill_points = 0
            for skill_name, skill_data in api_result['skills'].items():
                level = skill_data['level']
                if level != 0:
                    economy = ['energy', 'companies', 'entrepreneurship', 'production']
                    if skill_name in economy:
                        economy_skill_points += triangular(level)
                    else:
                        fight_skill_points += triangular(level)
            total_skill_points = api_result['leveling']['totalSkillPoints']
            unspent_skill_points = api_result['leveling']['availableSkillPoints']

            # division by zero, should not be possible (level 1 = 4 points already)
            if total_skill_points == 0:
                return None

            percentage = ((economy_skill_points + unspent_skill_points) / total_skill_points) * 100
            is_economy = percentage > 50
            if is_economy:
                return None

        leveling = api_result.get('leveling', {})
        level = leveling.get('level', 'N/A')
        is_active = api_result.get('isActive', False)

        skills = api_result.get('skills', {}) or {}
        health = skills.get('health', {}) or {}
        hunger = skills.get('hunger', {}) or {}

        health_curr = health.get('currentBarValue')
        health_total = health.get('total')
        hunger_curr = hunger.get('currentBarValue')
        hunger_total = hunger.get('total')

        buffs = api_result.get('buffs') or {}
        buff_text = "No buff/debuff"
        # Prefer debuffEndAt when present, otherwise fall back to buffEndAt
        buff_end_at = None
        buff_type = None
        buff_active = False
        if isinstance(buffs, dict) and buffs:
            if 'debuffEndAt' in buffs and buffs.get('debuffEndAt'):
                buff_end_at = buffs.get('debuffEndAt')
                buff_type = 'Debuff'
            elif 'buffEndAt' in buffs and buffs.get('buffEndAt'):
                buff_end_at = buffs.get('buffEndAt')
                buff_type = 'Buff'

            if buff_end_at:
                try:
                    buff_dt = datetime.fromisoformat(buff_end_at.replace('Z', '+00:00'))
                    now = datetime.now(timezone.utc)
                    remaining = buff_dt - now
                    buff_active = remaining.total_seconds() > 0
                    if buff_active:
                        hours = remaining.seconds // 3600
                        minutes = (remaining.seconds % 3600) // 60
                        # Provide relative time only (e.g. "Buff ends in 1d 2h 3m")
                        buff_text = f"{buff_type} ends in {hours}h {minutes}m"
                    else:
                        buff_text = f"{buff_type} expired"
                except Exception:
                    buff_active = False
                    buff_text = f"{buff_type}: {buff_end_at}"

        # avatar (may be unused by callers)
        avatar_url = None
        display_name = None
        if member is not None:
            try:
                display_name = member.display_name
                asset = member.display_avatar
                try:
                    avatar_url = str(asset.with_size(64))
                except Exception:
                    avatar_url = getattr(asset, 'url', None)
            except Exception:
                display_name = None

        return {
            'userId': userId,
            'warera_name': api_result.get('username'),
            'display_name': display_name,
            'avatar_url': avatar_url,
            'level': level,
            'last_connection_at': (api_result.get('dates') or {}).get('lastConnectionAt'),
            'is_active': is_active,
            'health_curr': health_curr,
            'health_total': health_total,
            'hunger_curr': hunger_curr,
            'hunger_total': hunger_total,
            'buff_text': buff_text,
            'buff_type': buff_type,
            'buff_end_at': buff_end_at,
            'buff_active': bool(buff_active),
        }
    except Exception as e:
        logger.exception('get_fight_status failed for %s: %s', userId, e)
        return None
    
async def get_military_unit(muId, session, base_url="https://api2.warera.io/trpc/mu.getById"):
    try:
        input_data = {'muId': muId}
        params = {"input": json.dumps(input_data)}
        data = await _get_with_retry(session, base_url, params=params)
        if not data:
            return None
        api_result = data.get('result', {}).get('data')
        if not api_result:
            return None
        return api_result
    except Exception as e:
        logger.exception('get_military_unit failed: %s', e)
        return None

async def request_military_units(input_data, session, base_url="https://api2.warera.io/trpc/mu.getManyPaginated"):
    try:
        params = {"input": json.dumps(input_data)}
        data = await _get_with_retry(session, base_url, params=params)
        if not data:
            return None
        return data
    except Exception as e:
        logger.exception('request_military_units failed: %s', e)
        return None

async def get_military_units(session, base_url="https://api2.warera.io/trpc/mu.getManyPaginated"):
    """Return a flat list of military unit items from the paginated mu.getManyPaginated endpoint.

    Returns list[dict] or None on failure. Each item is expected to contain at least a `name` key
    and optionally a `members` list.
    """
    try:
        input_data = {"limit": 100}
        params = {"input": json.dumps(input_data)}
        mus = await _get_with_retry(session, base_url, params=params)
        if not mus:
            return None

        data = mus.get('result', {}).get('data') or {}
        items = data.get('items') or []
        next_cursor = data.get('nextCursor')

        while next_cursor:
            input_data['cursor'] = next_cursor
            params = {"input": json.dumps(input_data)}
            mus = await _get_with_retry(session, base_url, params=params)
            if not mus:
                break
            data = mus.get('result', {}).get('data') or {}
            new_items = data.get('items') or []
            items += new_items
            next_cursor = data.get('nextCursor')

        return items
    except Exception as e:
        logger.exception('get_military_units failed: %s', e)
        return None
    
async def get_active_battles(session, base_url="https://api2.warera.io/trpc/battle.getBattles"):
    try:
        input_data = {"isActive": True, "limit": 100}
        params = {"input": json.dumps(input_data)}
        mus = await _get_with_retry(session, base_url, params=params)
        if not mus:
            return None

        data = mus.get('result', {}).get('data') or {}
        items = data.get('items') or []
        next_cursor = data.get('nextCursor')

        while next_cursor:
            input_data['cursor'] = next_cursor
            params = {"input": json.dumps(input_data)}
            mus = await _get_with_retry(session, base_url, params=params)
            if not mus:
                break
            data = mus.get('result', {}).get('data') or {}
            new_items = data.get('items') or []
            items += new_items
            next_cursor = data.get('nextCursor')

        return items
    except Exception as e:
        logger.exception('get_active_battles failed: %s', e)
        return None
    
async def get_country(countryId, session, base_url="https://api2.warera.io/trpc/country.getCountryById"):
    try:
        input_data = {'countryId': countryId}
        params = {"input": json.dumps(input_data)}
        data = await _get_with_retry(session, base_url, params=params)
        if not data:
            return None
        api_result = data.get('result', {}).get('data')
        if not api_result:
            return None
        return api_result
    except Exception as e:
        logger.exception('get_country failed: %s', e)
        return None

async def get_alliance(allianceId, session, base_url="https://api2.warera.io/trpc/alliance.getById"):
    """The alliance with this id (`country.allianceId`), or None when it could not be fetched.

    `alliance.getById` is not in the official API spec (documented by the community explorer). The
    result carries `memberCountries`, a list of `{"country": <country id>, "suspended": bool, ...}`.
    """
    try:
        input_data = {'allianceId': allianceId}
        params = {"input": json.dumps(input_data)}
        data = await _get_with_retry(session, base_url, params=params)
        if not data:
            return None
        api_result = data.get('result', {}).get('data')
        if not api_result:
            return None
        return api_result
    except Exception as e:
        logger.exception('get_alliance failed: %s', e)
        return None

async def get_mercenary_auctions(session, base_url="https://api2.warera.io/trpc/mercenaryContractAuction.getPaginatedAuctions"):
    try:
        input_data = {"limit": 50, "status": "active"}
        params = {"input": json.dumps(input_data)}
        mus = await _get_with_retry(session, base_url, params=params)
        if not mus:
            return None

        data = mus.get('result', {}).get('data') or {}
        items = data.get('items') or []
        next_cursor = data.get('nextCursor')

        while next_cursor:
            input_data['cursor'] = next_cursor
            params = {"input": json.dumps(input_data)}
            mus = await _get_with_retry(session, base_url, params=params)
            if not mus:
                break
            data = mus.get('result', {}).get('data') or {}
            new_items = data.get('items') or []
            items += new_items
            next_cursor = data.get('nextCursor')

        return items
    except Exception as e:
        logger.exception('get_mercenary_auctions failed: %s', e)
        return None
    
async def get_won_mercenary_auctions(session, created_after: str, base_url="https://api2.warera.io/trpc/mercenaryContractAuction.getPaginatedAuctions"):
    """Won mercenary contracts created at or after `created_after` (ISO string), newest first.

    The list is sorted by createdAt descending, so paging stops at the first older item.
    """
    try:
        input_data = {"status": "won", "limit": 50}
        items = []
        while True:
            params = {"input": json.dumps(input_data)}
            data = await _get_with_retry(session, base_url, params=params)
            if not data:
                # a partial list could hide contracts from the startup seed, so fail the whole scan
                return None
            page = data.get('result', {}).get('data') or {}
            for item in page.get('items') or []:
                if str(item.get('createdAt') or '') < created_after:
                    return items
                items.append(item)
            next_cursor = page.get('nextCursor')
            if not next_cursor:
                return items
            input_data['cursor'] = next_cursor
    except Exception as e:
        logger.exception('get_won_mercenary_auctions failed: %s', e)
        return None

async def get_battle(battleId, session, base_url="https://api2.warera.io/trpc/battle.getById"):
    try:
        input_data = {"battleId": battleId}
        params = {"input": json.dumps(input_data)}
        data = await _get_with_retry(session, base_url, params=params)
        api_result = (data or {}).get("result", {}).get("data")
        if isinstance(api_result, dict):
            return api_result
        return None
    except Exception as e:
        logger.exception('get_battle failed: %s', e)
        return None

async def get_round(roundId, session, base_url="https://api2.warera.io/trpc/round.getById"):
    try:
        input_data = {"roundId": roundId}
        params = {"input": json.dumps(input_data)}
        data = await _get_with_retry(session, base_url, params=params)
        api_result = (data or {}).get("result", {}).get("data")
        if isinstance(api_result, dict):
            return api_result
        return None
    except Exception as e:
        logger.exception('get_round failed: %s', e)
        return None

async def get_game_config(session, base_url="https://api2.warera.io/trpc/gameConfig.getGameConfig"):
    try:
        params = {"input": json.dumps({})}
        data = await _get_with_retry(session, base_url, params=params)
        api_result = (data or {}).get("result", {}).get("data")
        if isinstance(api_result, dict):
            return api_result
        return None
    except Exception as e:
        logger.exception('get_game_config failed: %s', e)
        return None

async def get_market_prices(session, base_url="https://api2.warera.io/trpc/itemTrading.getPrices"):
    try:
        data = await _get_with_retry(session, base_url)
        if not data:
            return None
        return data
    except Exception as e:
        logger.exception('get_market_prices failed: %s', e)
        return None
    
async def get_rankings(filter, session, base_url="https://api2.warera.io/trpc/ranking.getRanking"):
    try:
        input_data = {"rankingType": filter}
        params = {"input": json.dumps(input_data)}
        data = await _get_with_retry(session, base_url, params=params)
        if not data:
            return None
        api_result = data.get('result', {}).get('data')
        if not api_result:
            return None
        return api_result
    except Exception as e:
        logger.exception('get_rankings failed: %s', e)
        return None
    
async def get_country_users(countryId, session, base_url="https://api2.warera.io/trpc/user.getUsersByCountry"):
    try:
        input_data = {"limit": 100, "countryId": countryId}
        params = {"input": json.dumps(input_data)}
        mus = await _get_with_retry(session, base_url, params=params)
        if not mus:
            return None

        data = mus.get('result', {}).get('data') or {}
        items = data.get('items') or []
        next_cursor = data.get('nextCursor')

        while next_cursor:
            input_data['cursor'] = next_cursor
            params = {"input": json.dumps(input_data)}
            mus = await _get_with_retry(session, base_url, params=params)
            if not mus:
                break
            data = mus.get('result', {}).get('data') or {}
            new_items = data.get('items') or []
            items += new_items
            next_cursor = data.get('nextCursor')

        return items
    except Exception as e:
        logger.exception('get_country_users failed: %s', e)
        return None
    
def _page_ends_before(page_items, created_after) -> bool:
    """True when the last item of a newest-first page was created before `created_after` (ISO string)."""
    if created_after is None or not page_items:
        return False
    last_created_at = page_items[-1].get('createdAt')
    return isinstance(last_created_at, str) and last_created_at < created_after

async def get_user_transactions(userId, transactionType, session, base_url="https://api2.warera.io/trpc/transaction.getPaginatedTransactions", created_after=None):
    """A user's transactions of one type, newest first. Requires an API key.

    With `created_after` (ISO string), paging stops after the first page that reaches older transactions;
    every transaction created at or after it is still returned, and some older ones may be too.
    """
    try:
        input_data = {"limit": 100, "userId": userId, "transactionType": transactionType}
        params = {"input": json.dumps(input_data)}
        mus = await _get_with_retry(session, base_url, params=params)
        if not mus:
            return None

        data = mus.get('result', {}).get('data') or {}
        items = data.get('items') or []
        next_cursor = data.get('nextCursor')
        # sorted by createdAt descending [observed 2026-10-12 across pages], so later pages are all older
        reached_older = _page_ends_before(items, created_after)

        while next_cursor and not reached_older:
            input_data['cursor'] = next_cursor
            params = {"input": json.dumps(input_data)}
            mus = await _get_with_retry(session, base_url, params=params)
            if not mus:
                break
            data = mus.get('result', {}).get('data') or {}
            new_items = data.get('items') or []
            items += new_items
            next_cursor = data.get('nextCursor')
            reached_older = _page_ends_before(new_items, created_after)

        return items
    except Exception as e:
        logger.exception('get_user_transactions failed: %s', e)
        return None
    
async def get_articles(session, base_url="https://api2.warera.io/trpc/article.getArticlesPaginated", max_items=None):
    """Newest articles first, from every page, or only until `max_items` articles were fetched.

    With `max_items`, the first `max_items` items are the same as without it; the list may be longer.
    """
    try:
        input_data = {"limit": 100, "type": "last"}
        params = {"input": json.dumps(input_data)}
        mus = await _get_with_retry(session, base_url, params=params)
        if not mus:
            return None

        data = mus.get('result', {}).get('data') or {}
        items = data.get('items') or []
        next_cursor = data.get('nextCursor')

        while next_cursor and (max_items is None or len(items) < max_items):
            input_data['cursor'] = next_cursor
            params = {"input": json.dumps(input_data)}
            mus = await _get_with_retry(session, base_url, params=params)
            if not mus:
                break
            data = mus.get('result', {}).get('data') or {}
            new_items = data.get('items') or []
            items += new_items
            next_cursor = data.get('nextCursor')

        return items
    except Exception as e:
        logger.exception('get_articles failed: %s', e)
        return None
    
async def get_regions_object(session, base_url="https://api2.warera.io/trpc/region.getRegionsObject"):
    try:
        data = await _get_with_retry(
            session,
            base_url,
        )
        api_result = (data or {}).get("result", {}).get("data")
        if isinstance(api_result, dict):
            return api_result
        return None
    except Exception as e:
        logger.exception('get_regions_object failed: %s', e)
        return None
    
async def get_region(session, region_id, base_url="https://api2.warera.io/trpc/region.getById"):
    try:
        input_data = {"regionId": region_id}
        params = {"input": json.dumps(input_data)}
        data = await _get_with_retry(
            session,
            base_url,
            params=params,
        )
        api_result = (data or {}).get("result", {}).get("data")
        if isinstance(api_result, dict):
            return api_result
        return None
    except Exception as e:
        logger.exception('get_region failed: %s', e)
        return None

# tournament.getById and tournamentTeam.getById are not in the public OpenAPI spec (0.17.4-beta);
# they are what the game client uses and may change without notice.
async def get_tournament(tournamentId, session, base_url="https://api2.warera.io/trpc/tournament.getById"):
    try:
        input_data = {"tournamentId": tournamentId}
        params = {"input": json.dumps(input_data)}
        data = await _get_with_retry(session, base_url, params=params)
        api_result = (data or {}).get("result", {}).get("data")
        if isinstance(api_result, dict):
            return api_result
        return None
    except Exception as e:
        logger.exception('get_tournament failed: %s', e)
        return None

async def get_tournament_team(tournamentTeamId, session, base_url="https://api2.warera.io/trpc/tournamentTeam.getById"):
    try:
        input_data = {"tournamentTeamId": tournamentTeamId}
        params = {"input": json.dumps(input_data)}
        data = await _get_with_retry(session, base_url, params=params)
        api_result = (data or {}).get("result", {}).get("data")
        if isinstance(api_result, dict):
            return api_result
        return None
    except Exception as e:
        logger.exception('get_tournament_team failed: %s', e)
        return None

async def get_ended_battles(session, created_after: str, base_url="https://api2.warera.io/trpc/battle.getBattles"):
    """Ended battles created at or after `created_after` (ISO string), newest first.

    The list is sorted by createdAt descending, so paging stops at the first older item.
    """
    try:
        input_data = {"isActive": False, "limit": 100}
        items = []
        while True:
            params = {"input": json.dumps(input_data)}
            data = await _get_with_retry(session, base_url, params=params)
            if not data:
                # a partial list would silently undercount battles
                return None
            page = data.get('result', {}).get('data') or {}
            for item in page.get('items') or []:
                if str(item.get('createdAt') or '') < created_after:
                    return items
                items.append(item)
            next_cursor = page.get('nextCursor')
            if not next_cursor:
                return items
            input_data['cursor'] = next_cursor
    except Exception as e:
        logger.exception('get_ended_battles failed: %s', e)
        return None

async def get_battle_ranking(battleId, dataType, rankingType, side, session, base_url="https://api2.warera.io/trpc/battleRanking.getRanking"):
    """Every entry of a battle leaderboard (dataType: damage|points|money, rankingType: user|country|mu,
    side: attacker|defender|merged). None if any page fails."""
    try:
        input_data = {"battleId": battleId, "dataType": dataType, "type": rankingType, "side": side, "limit": 100}
        items = []
        while True:
            params = {"input": json.dumps(input_data)}
            data = await _get_with_retry(session, base_url, params=params)
            if not data:
                return None
            page = data.get('result', {}).get('data') or {}
            items += page.get('items') or []
            next_cursor = page.get('nextCursor')
            if not next_cursor:
                return items
            input_data['cursor'] = next_cursor
    except Exception as e:
        logger.exception('get_battle_ranking failed: %s', e)
        return None

async def get_ranking_pages(scope, data_type, ranking_type, side, session, stop=None, max_pages=None, base_url="https://api2.warera.io/trpc/battleRanking.getRanking"):
    """battleRanking.getRanking entries from the top for one scope ({"battleId"}, {"roundId"} or {"warId"}).

    Pages are read until `stop(items)` returns True, the ranking ends or `max_pages` pages were read.
    Returns (items, complete), where complete is True only when the whole ranking was read; None when
    the first page fails. A later page that fails ends the read with complete False.
    """
    try:
        input_data = {**scope, "dataType": data_type, "type": ranking_type, "side": side, "limit": 100}
        items, pages = [], 0
        while True:
            data = await _get_with_retry(session, base_url, params={"input": json.dumps(input_data)})
            if not data:
                return None if not pages else (items, False)
            page = data.get('result', {}).get('data') or {}
            items += page.get('items') or []
            pages += 1
            next_cursor = page.get('nextCursor')
            if not next_cursor:
                return items, True
            if (stop and stop(items)) or (max_pages and pages >= max_pages):
                return items, False
            input_data['cursor'] = next_cursor
    except Exception as e:
        logger.exception('get_ranking_pages failed: %s', e)
        return None

async def get_battle_loot_summaries(battle_id, user_ids, session):
    """Batched battleLootSummary.getByBattleAndUser: {userId: summary} for the users who hit the battle.

    A user with no hits in the battle gets a 404 [observed], so is missing from the dict, like a failed call.
    When every user of a batch chunk has no hits the whole request is a 404, which is expected and not logged.
    """
    ids = list(dict.fromkeys(user_ids))
    summaries = await _get_batch(
        session, 'battleLootSummary.getByBattleAndUser', [{'battleId': battle_id, 'userId': user_id} for user_id in ids], quiet_statuses=(404,)
    )
    return {user_id: summary for user_id, summary in zip(ids, summaries) if isinstance(summary, dict)}

# muMember.getByMu is not in the public OpenAPI spec (0.17.4-beta); it is documented by the community
# explorer (warera.realmarijn.nl) and may change without notice.
async def get_mu_members(muId, session, base_url="https://api2.warera.io/trpc/muMember.getByMu"):
    """One record per MU member with weekly/monthly/total damage and help counters."""
    try:
        input_data = {"muId": muId}
        params = {"input": json.dumps(input_data)}
        data = await _get_with_retry(session, base_url, params=params)
        api_result = (data or {}).get("result", {}).get("data")
        if isinstance(api_result, list):
            return api_result
        return None
    except Exception as e:
        logger.exception('get_mu_members failed: %s', e)
        return None

async def get_mu_transactions(muId, transactionType, created_after: str, session, base_url="https://api2.warera.io/trpc/transaction.getPaginatedTransactions"):
    """An MU's transactions of one type (or a list of types) created at or after `created_after` (ISO string), newest first.

    Requires an API key. The list is sorted by createdAt descending, so paging stops at the first older item.
    """
    try:
        input_data = {"muId": muId, "transactionType": transactionType, "limit": 100}
        items = []
        while True:
            params = {"input": json.dumps(input_data)}
            data = await _get_with_retry(session, base_url, params=params)
            if not data:
                return None
            page = data.get('result', {}).get('data') or {}
            for item in page.get('items') or []:
                if str(item.get('createdAt') or '') < created_after:
                    return items
                items.append(item)
            next_cursor = page.get('nextCursor')
            if not next_cursor:
                return items
            input_data['cursor'] = next_cursor
    except Exception as e:
        logger.exception('get_mu_transactions failed: %s', e)
        return None

# tradingOrder.getPublicOrdersByOwner is not in the public OpenAPI spec (0.17.4-beta); it is documented by the
# community explorer (warera.realmarijn.nl) and may change without notice.
async def get_mu_public_orders(muId, session, base_url="https://api2.warera.io/trpc/tradingOrder.getPublicOrdersByOwner"):
    """An MU's open market orders: {buyOrders, sellOrders, allOrders, totalBuyMoneyInvested, totalSellMoneyExpected, …}."""
    try:
        input_data = {"muId": muId}
        params = {"input": json.dumps(input_data)}
        data = await _get_with_retry(session, base_url, params=params)
        api_result = (data or {}).get("result", {}).get("data")
        if isinstance(api_result, dict):
            return api_result
        return None
    except Exception as e:
        logger.exception('get_mu_public_orders failed: %s', e)
        return None
