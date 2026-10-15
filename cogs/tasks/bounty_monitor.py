from discord.ext import commands, tasks
from utils.api import get_shared_session, get_active_battles, get_countries_by_ids
from utils.db import init_db
from utils.i18n import get_translator
from config import config
from datetime import datetime, timezone

# how often the bounty monitor runs (minutes)
BOUNTY_MONITOR_INTERVAL_MINUTES = 1

class BountyMonitorJob(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # track displayed bounties: key -> last seen bountyEffectiveAt
        # key format: "{battle_id}:{side}" where side is 'attacker' or 'defender'
        self.displayed_bounties: dict = {}
        # bounties active at the first successful run after a restart are recorded without posting
        self._seeded = False
        try:
            init_db()
        except Exception:
            pass
        self.bounty_monitor.start()

    def cog_unload(self):
        self.bounty_monitor.cancel()
    
    @tasks.loop(minutes=BOUNTY_MONITOR_INTERVAL_MINUTES)
    async def bounty_monitor(self):
        """Post the active battles' new or changed bounties to the bounties channel.

        A side counts when its moneyPool is above 0, it has a bountyEffectiveAt and it pays at
        least 0.1 per 1k damage. Each such side gets one plain-text message, sent again only
        when its bountyEffectiveAt changes.

        The first run that fetches the battles after a restart only records the
        current bounties, so bounties posted before the restart are not posted again.
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

        if not self._seeded:
            # same keys and values as the posting loop below records
            for entry in battles_with_bounty:
                bid = entry['id'] or 'unknown'
                for side in ('attacker', 'defender'):
                    if entry[f'{side}_pool'] > 0 and entry[f'{side}_bounty_at']:
                        self.displayed_bounties[f"{bid}:{side}"] = entry[f'{side}_bounty_at']
            self._seeded = True
            return

        if not battles_with_bounty:
            return

        # Fetch country names for all referenced country ids (one batched request)
        country_cache: dict = {}
        country_ids = []
        for entry in battles_with_bounty:
            b = entry['battle']
            atk_cid = (b.get('attacker') or {}).get('country')
            def_cid = (b.get('defender') or {}).get('country')
            if atk_cid:
                country_ids.append(atk_cid)
            if def_cid:
                country_ids.append(def_cid)
        countries = await get_countries_by_ids(country_ids, session)
        for cid in country_ids:
            cobj = countries.get(cid)
            country_cache[cid] = (cobj.get('name') or cid) if isinstance(cobj, dict) else cid

        # For each side with a positive pool, send a single embed if it's new/changed
        channel = guild.get_channel(config.get('channels', {}).get('bounties')) if guild else None
        tr = await get_translator(guild)
        unknown = tr('common.unknown')
        current_keys = set()
        for entry in battles_with_bounty:
            b = entry['battle']
            bid = entry['id'] or 'unknown'
            atk = b.get('attacker') or {}
            dfn = b.get('defender') or {}
            atk_cid = atk.get('country')
            def_cid = dfn.get('country')
            atk_name = country_cache.get(atk_cid, atk_cid or unknown)
            def_name = country_cache.get(def_cid, def_cid or unknown)

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
                    msg = tr(
                        "bounty_monitor.bounty",
                        money_per=money_per,
                        pool=pool,
                        country=atk_name,
                        side=tr("common.side_title.attacker"),
                        opponent=def_name,
                        opponent_side=tr("common.side_title.defender"),
                        link=battle_link,
                    )
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
                    msg = tr(
                        "bounty_monitor.bounty",
                        money_per=money_per,
                        pool=pool,
                        country=def_name,
                        side=tr("common.side_title.defender"),
                        opponent=atk_name,
                        opponent_side=tr("common.side_title.attacker"),
                        link=battle_link,
                    )
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