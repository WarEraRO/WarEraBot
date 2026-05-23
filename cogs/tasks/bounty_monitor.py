from discord.ext import commands, tasks
from utils.api import get_shared_session, get_active_battles, get_country
from utils.db import init_db
from config import config
from datetime import datetime, timezone
import asyncio

# how often the bounty monitor runs (minutes)
BOUNTY_MONITOR_INTERVAL_MINUTES = 1

class BountyMonitorJob(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # track displayed bounties: key -> last seen bountyEffectiveAt
        # key format: "{battle_id}:{side}" where side is 'attacker' or 'defender'
        self.displayed_bounties: dict = {}
        try:
            init_db()
        except Exception:
            pass
        self.bounty_monitor.start()

    def cog_unload(self):
        self.bounty_monitor.cancel()
    
    @tasks.loop(minutes=BOUNTY_MONITOR_INTERVAL_MINUTES)
    async def bounty_monitor(self):
        """Checks active battles for bounties that are upcoming or currently active
        (moneyPool != 0 and bountyEffectiveAt present). Sends a summary embed
        to the public channel when any are found.
        """
        guild = self.bot.get_guild(config['guild'])
        if guild is None:
            return

        session = await get_shared_session()
        try:
            battles = await get_active_battles(session)
        except Exception:
            battles = None

        if not battles:
            return

        now = datetime.now(timezone.utc)
        # Collect battles that have a positive moneyPool on either side and a bountyEffectiveAt
        battles_with_bounty = []
        for battle in battles:
            bid = battle.get('_id') or battle.get('id') or battle.get('battleId') or None
            attacker = battle.get('attacker') or {}
            defender = battle.get('defender') or {}

            try:
                atk_pool = float(attacker.get('moneyPool') or 0)
            except Exception:
                atk_pool = 0.0
            try:
                def_pool = float(defender.get('moneyPool') or 0)
            except Exception:
                def_pool = 0.0

            try:
                atk_money = float(attacker.get('moneyPer1kDamages') or 0)
            except Exception:
                atk_money = 0.0
            try:
                def_money = float(defender.get('moneyPer1kDamages') or 0)
            except Exception:
                def_money = 0.0

            atk_bounty_at = attacker.get('bountyEffectiveAt')
            def_bounty_at = defender.get('bountyEffectiveAt')

            # Only consider pools strictly greater than 0
            if (atk_pool > 0 and atk_bounty_at and atk_money >= 0.1) or (def_pool > 0 and def_bounty_at and def_money >= 0.1):
                battles_with_bounty.append({
                    'battle': battle,
                    'id': bid,
                    'attacker_pool': atk_pool,
                    'defender_pool': def_pool,
                    'attacker_bounty_at': atk_bounty_at,
                    'defender_bounty_at': def_bounty_at,
                })

        if not battles_with_bounty:
            return

        # Fetch country names for all referenced country ids
        country_cache: dict = {}
        async def resolve_country(cid):
            if not cid:
                return None
            if cid in country_cache:
                return country_cache[cid]
            try:
                cobj = await get_country(cid, session)
            except Exception:
                cobj = None
            if isinstance(cobj, dict):
                name = cobj.get('name') or cid
            else:
                name = cid
            country_cache[cid] = name
            return country_cache[cid]

        # Resolve countries used in the selected battles
        tasks_resolve = []
        for entry in battles_with_bounty:
            b = entry['battle']
            atk_cid = (b.get('attacker') or {}).get('country')
            def_cid = (b.get('defender') or {}).get('country')
            if atk_cid:
                tasks_resolve.append(resolve_country(atk_cid))
            if def_cid:
                tasks_resolve.append(resolve_country(def_cid))
        # run resolves
        await asyncio.gather(*tasks_resolve)

        # For each side with a positive pool, send a single embed if it's new/changed
        channel = guild.get_channel(config.get('channels', {}).get('public')) if guild else None
        current_keys = set()
        for entry in battles_with_bounty:
            b = entry['battle']
            bid = entry['id'] or 'unknown'
            atk = b.get('attacker') or {}
            dfn = b.get('defender') or {}
            atk_cid = atk.get('country')
            def_cid = dfn.get('country')
            atk_name = country_cache.get(atk_cid, atk_cid or 'unknown')
            def_name = country_cache.get(def_cid, def_cid or 'unknown')

            # attacker side: send a simple plain-text message instead of an embed
            if entry['attacker_pool'] > 0 and entry['attacker_bounty_at']:
                key = f"{bid}:attacker"
                current_keys.add(key)
                prev = self.displayed_bounties.get(key)
                if prev != entry['attacker_bounty_at']:
                    try:
                        money_per = float(atk.get('moneyPer1kDamages') or 0)
                    except Exception:
                        money_per = 0.0
                    pool = round(float(entry['attacker_pool']), 2)
                    battle_link = f"https://app.warera.io/battle/{bid}"
                    # Format: "moneyPer/pool from <country_A> (Attacker) against <country_B> (Defender) — View battle: <link>"
                    msg = f"**[BOUNTY]** {money_per}/{pool} from {atk_name} (Attacker) against {def_name} (Defender) — [View Battle]({battle_link})"
                    if channel:
                        try:
                            sent = await channel.send(msg)
                            await sent.edit(suppress=True)
                        except Exception:
                            pass
                    self.displayed_bounties[key] = entry['attacker_bounty_at']

            # defender side: send a simple plain-text message instead of an embed
            if entry['defender_pool'] > 0 and entry['defender_bounty_at']:
                key = f"{bid}:defender"
                current_keys.add(key)
                prev = self.displayed_bounties.get(key)
                if prev != entry['defender_bounty_at']:
                    try:
                        money_per = float(dfn.get('moneyPer1kDamages') or 0)
                    except Exception:
                        money_per = 0.0
                    pool = round(float(entry['defender_pool']), 2)
                    battle_link = f"https://app.warera.io/battle/{bid}"
                    # Format: "moneyPer/pool from <country_A> (Defender) against <country_B> (Attacker) — View battle: <link>"
                    msg = f"**[BOUNTY]** {money_per}/{pool} from {def_name} (Defender) against {atk_name} (Attacker) — [View Battle]({battle_link})"
                    if channel:
                        try:
                            sent = await channel.send(msg)
                            await sent.edit(suppress=True)
                        except Exception:
                            pass
                    self.displayed_bounties[key] = entry['defender_bounty_at']

        # prune displayed_bounties keys for battles that are no longer active
        active_ids = set()
        for b in battles:
            bid = b.get('_id') or b.get('id') or b.get('battleId') or None
            if bid:
                active_ids.add(str(bid))

        to_remove = [k for k in list(self.displayed_bounties.keys()) if k.split(':')[0] not in active_ids]
        for k in to_remove:
            try:
                del self.displayed_bounties[k]
            except Exception:
                pass

    @bounty_monitor.before_loop
    async def before_bounty_monitor(self):
        await self.bot.wait_until_ready()

async def setup(bot: commands.Bot):
    await bot.add_cog(BountyMonitorJob(bot))