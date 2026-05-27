from discord.ext import commands, tasks
from utils.api import get_shared_session, get_mercenary_auctions, get_country
from utils.db import init_db
from config import config

# how often the mercenary auction monitor runs (minutes)
MERCENARY_MONITOR_INTERVAL_MINUTES = 1

class MercenaryContractsJob(commands.Cog):
    def __init__(self, bot: commands.Bot):
        # track displayed mercenary auctions: auction_id -> token (updatedAt/currentPayout)
        self.displayed_auctions: dict = {}
        self.bot = bot
        try:
            init_db()
        except Exception:
            pass
        self.mercenary_monitor.start()

    def cog_unload(self):
        self.mercenary_monitor.cancel()
    
    @tasks.loop(minutes=MERCENARY_MONITOR_INTERVAL_MINUTES)
    async def mercenary_monitor(self):
        """Checks active mercenary contract auctions and posts new/changed ones.

        Message format: "<country_name> posted a <initialPerK>/<budget> contract for <forCountrySide> side."
        """
        guild = self.bot.get_guild(config['guild'])
        if guild is None:
            return

        session = await get_shared_session()
        try:
            auctions = await get_mercenary_auctions(session)
        except Exception:
            auctions = None

        if not auctions:
            return

        channel = guild.get_channel(config.get('channels', {}).get('contracts')) if guild else None
        if channel is None:
            return

        # simple cache for country names
        country_cache: dict = {}
        async def resolve_country(cid):
            if not cid:
                return 'unknown'
            if cid in country_cache:
                return country_cache[cid]
            try:
                cobj = await get_country(cid, session)
            except Exception:
                cobj = None
            name = cobj.get('name') if isinstance(cobj, dict) else str(cid)
            country_cache[cid] = name
            return name

        seen_ids = set()
        for a in auctions:
            aid = a.get('_id')
            if not aid:
                continue
            seen_ids.add(aid)

            status = a.get('status')
            # only post active auctions
            if status != 'active':
                continue

            # token to detect changes (prefer updatedAt, fallback to createdAt or currentPayout)
            token = a.get('updatedAt') or a.get('createdAt') or a.get('currentPayout')
            prev = self.displayed_auctions.get(aid)
            if prev == token:
                continue

            country_name = await resolve_country(a.get('country') or a.get('forCountry'))
            initial = a.get('initialPerK')
            budget = a.get('budget')
            side = a.get('forCountrySide') or a.get('forCountrySide')
            battle_link = f"https://app.warera.io/battle/{a.get('battle')}"
            text = f"**[CONTRACT]** {country_name} posted a {initial}/{budget} contract for {side} side — [View Battle]({battle_link})"
            try:
                sent = await channel.send(text)
                await sent.edit(suppress=True)
            except Exception:
                pass

            # record token
            self.displayed_auctions[aid] = token

        # prune auctions that are no longer active
        to_prune = [k for k in list(self.displayed_auctions.keys()) if k not in seen_ids]
        for k in to_prune:
            try:
                del self.displayed_auctions[k]
            except Exception:
                pass

    @mercenary_monitor.before_loop
    async def before_mercenary_monitor(self):
        await self.bot.wait_until_ready()

async def setup(bot: commands.Bot):
    await bot.add_cog(MercenaryContractsJob(bot))