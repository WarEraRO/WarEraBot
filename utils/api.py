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


async def _get_with_retry(session, url, params=None, max_retries=5, initial_backoff=1.0, backoff_factor=2.0, max_backoff=60.0):
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

async def get_user(username, session, base_url="https://api2.warera.io/trpc/search.searchAnything"):
    try:
        if username in PLAYER_CACHE.keys():
            user = await get_user_info(PLAYER_CACHE[username], session)
            return user

        input_data = {'searchText': username}
        params = {"input": json.dumps(input_data)}
        data = await _get_with_retry(session, base_url, params=params)
        if not data:
            return None
        api_result = data.get('result', {}).get('data')
        if not api_result or api_result.get('hasData') is False:
            return None
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
    
async def get_user_transactions(userId, transactionType, session, base_url="https://api2.warera.io/trpc/transaction.getPaginatedTransactions"):
    try:
        input_data = {"limit": 100, "userId": userId, "transactionType": transactionType}
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
        logger.exception('get_user_transactions failed: %s', e)
        return None
    
async def get_articles(session, base_url="https://api2.warera.io/trpc/article.getArticlesPaginated"):
    try:
        input_data = {"limit": 100, "type": "last"}
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
