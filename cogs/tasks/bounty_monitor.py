"""bounty_monitor: post the bounties of active battles to the public bounties channel (config `channels.bounties`).

A battle side is posted when it has a bounty left (`moneyPool` above 0 and a `bountyEffectiveAt`) and either:

- its country is friendly (Romania, its defensive-pact partners or the members of its alliance that are not
  suspended, from `bounty_alerts.friendly_countries`), at any rate; or
- it pays at least MIN_PUBLIC_RATE per 1k damage, whatever its country.

Each such side gets one plain-text message, sent again only when its `bountyEffectiveAt` changes.
"""

from discord.ext import commands, tasks

from cogs.commands.mu_order_alignment import BATTLE_LINK, SIDES, _opposite
from cogs.tasks.bounty_alerts import _amount, friendly_countries
from cogs.tasks.military_unit_contract_monitor import format_amount
from config import config
from utils.api import warera
from utils.db import init_db
from utils.i18n import get_translator

# how often the bounty monitor runs (minutes)
BOUNTY_MONITOR_INTERVAL_MINUTES = 1
# minimum pay per 1k damage for a bounty of a country that is not friendly to be posted
MIN_PUBLIC_RATE = 0.1


def _battle_id(battle: dict) -> str:
    return str(battle.get('_id') or battle.get('id') or battle.get('battleId') or 'unknown')


def public_bounty_sides(battle: dict, friendly_ids: set[str]) -> list[str]:
    """The sides of a battle to post in the bounties channel, in SIDES order.

    A side qualifies when it has a bounty left (moneyPool above 0 and a bountyEffectiveAt) and its
    country is in friendly_ids or it pays at least MIN_PUBLIC_RATE per 1k damage. Each side is judged on
    its own, so a low bounty is not posted just because the other side's bounty qualifies.
    """
    sides = []
    for side in SIDES:
        data = battle.get(side) or {}
        if _amount(data.get('moneyPool')) <= 0 or not data.get('bountyEffectiveAt'):
            continue
        if (
            str(data.get('country') or '') in friendly_ids
            or _amount(data.get('moneyPer1kDamages')) >= MIN_PUBLIC_RATE
        ):
            sides.append(side)
    return sides


class BountyMonitorJob(commands.Cog):
    """Background job that posts public bounties to the bounties channel (see the module docstring)."""

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

        The sides posted are those of `public_bounty_sides` (friendly countries at any rate, other
        countries from MIN_PUBLIC_RATE per 1k damage). Each gets one plain-text message, sent again only
        when its bountyEffectiveAt changes. Nothing is posted in a run whose friendly countries (never
        loaded yet) or battle list cannot be fetched.

        The first run that fetches the battles after a restart only records the
        current bounties, so bounties posted before the restart are not posted again.
        """
        guild = self.bot.get_guild(config['guild'])
        if guild is None:
            return

        friends = await friendly_countries()
        if friends is None:
            return
        friendly_ids, country_names = friends

        try:
            battles = await warera.battles.get_active()
        except Exception:
            battles = None
        if not battles:
            return

        # (battle id, battle, side) of every side to post
        bounties = [
            (_battle_id(battle), battle, side)
            for battle in battles
            for side in public_bounty_sides(battle, friendly_ids)
        ]

        if not self._seeded:
            # same keys and values as the posting loop below records
            for bid, battle, side in bounties:
                self.displayed_bounties[f"{bid}:{side}"] = battle[side]['bountyEffectiveAt']
            self._seeded = True
            return

        channel = guild.get_channel(config.get('channels', {}).get('bounties'))
        tr = await get_translator(guild) if bounties else None
        for bid, battle, side in bounties:
            key = f"{bid}:{side}"
            data = battle[side]
            if self.displayed_bounties.get(key) == data['bountyEffectiveAt']:
                continue
            opponent_side = _opposite(side)
            unknown = tr('common.unknown')
            cid = data.get('country')
            opponent_cid = (battle.get(opponent_side) or {}).get('country')
            # Format: "moneyPer/pool from <country_A> (Side) against <country_B> (Opponent side) — View battle: <link>"
            msg = tr(
                "bounty_monitor.bounty",
                # friendly rates can be tiny: format_amount avoids scientific notation (5e-05)
                money_per=format_amount(_amount(data.get('moneyPer1kDamages'))),
                pool=round(_amount(data.get('moneyPool')), 2),
                country=country_names.get(str(cid), cid or unknown),
                side=tr(f"common.side_title.{side}"),
                opponent=country_names.get(str(opponent_cid), opponent_cid or unknown),
                opponent_side=tr(f"common.side_title.{opponent_side}"),
                link=BATTLE_LINK.format(bid),
            )
            if channel:
                try:
                    sent = await channel.send(msg)
                    await sent.edit(suppress=True)
                except Exception:
                    pass
            self.displayed_bounties[key] = data['bountyEffectiveAt']

        # prune displayed_bounties keys for battles that are no longer active
        active_ids = {_battle_id(battle) for battle in battles}
        for key in [k for k in self.displayed_bounties if k.split(':')[0] not in active_ids]:
            del self.displayed_bounties[key]

    @bounty_monitor.before_loop
    async def before_bounty_monitor(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    """Register the bounty monitor cog (discord.py extension entry point)."""
    await bot.add_cog(BountyMonitorJob(bot))
