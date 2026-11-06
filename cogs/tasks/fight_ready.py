"""Fight Ready role sync: marks the fighters who can fight right now.

Every ``FIGHT_READY_INTERVAL_MINUTES`` the job gives ``roles.fight_ready`` to every member holding the
Fighter role (``roles.fight``, managed by ``skill_roles``) whose player has no active debuff, and removes
it from fighters in debuff and from anyone who no longer holds the Fighter role. The Fighter role
itself is never touched.

Players are matched by their database link first and by server nickname otherwise. A member whose
player could not be loaded this run keeps their current role, so an API outage never strips it.
"""

import asyncio
import logging
from datetime import datetime, timezone

import discord
from discord.ext import commands, tasks

from cogs.tasks.military_unit_contract_monitor import parse_iso
from config import config
from utils.api import warera
from utils.db import get_api_ids_by_discord_id
from utils.i18n import get_translator

logger = logging.getLogger(__name__)

FIGHT_READY_INTERVAL_MINUTES = 5


def is_ready(user: dict, now: datetime) -> bool:
    """True when the player has no active debuff (``buffs.debuffEndAt`` missing or in the past).

    Args:
        user: A ``user.getUserLite`` payload.
        now: Current time, timezone-aware UTC.

    Returns:
        Whether the player can take part in fights without the post-Pill debuff.
    """
    debuff_end = parse_iso((user.get("buffs") or {}).get("debuffEndAt"))
    if debuff_end and debuff_end.tzinfo is None:
        # the API sends "Z" timestamps; a naive one would make the comparison raise and abort the run
        debuff_end = debuff_end.replace(tzinfo=timezone.utc)
    return not (debuff_end and debuff_end > now)


async def _change_role(member, role, add: bool, reason: str) -> bool:
    """Add or remove one role, logging Discord errors instead of raising.

    An unhandled error would end the run early and stop the ``tasks.loop`` until the next restart.

    Args:
        member: Discord member to update.
        role: Role to add or remove.
        add: True to add the role, False to remove it.
        reason: Audit-log reason.

    Returns:
        Whether the change went through.
    """
    try:
        if add:
            await member.add_roles(role, reason=reason)
        else:
            await member.remove_roles(role, reason=reason)
        return True
    except discord.HTTPException as exc:
        logger.warning("fight_ready: could not %s role for %s (%s): %s",
                       "add" if add else "remove", member.display_name, member.id, exc)
        return False


class FightReadyJob(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.fight_ready.start()

    def cog_unload(self):
        """Stop the loop when the extension is unloaded."""
        self.fight_ready.cancel()

    async def _load_players(self, members) -> dict:
        """Map each member to their loaded WarEra player; members whose player didn't load are left out.

        Linked members (database Discord id -> API id) are fetched by id. Unlinked members, or every
        member when the link table can't be read, are resolved by their server nickname.

        Args:
            members: Discord members to resolve.

        Returns:
            ``{member: user}`` for the members whose player was found and loaded.
        """
        try:
            linked_ids = await asyncio.to_thread(get_api_ids_by_discord_id)
        except Exception:
            logger.warning("fight_ready: could not read player links, matching by nickname only", exc_info=True)
            linked_ids = {}
        api_ids = {m: linked_ids[str(m.id)] for m in members if linked_ids.get(str(m.id))}

        unlinked = [m for m in members if m not in api_ids]
        if unlinked:
            by_name = await warera.users.ids_by_name([m.display_name for m in unlinked])
            for member in unlinked:
                if by_name.get(member.display_name):
                    api_ids[member] = by_name[member.display_name]

        users = await warera.users.get_many(set(api_ids.values())) if api_ids else {}
        return {m: users[api_id] for m, api_id in api_ids.items() if api_id in users}

    @tasks.loop(minutes=FIGHT_READY_INTERVAL_MINUTES)
    async def fight_ready(self):
        """Give the Fight Ready role to fighters without a debuff and remove it from everyone else.

        Members holding Fight Ready without the Fighter role lose it without any API call. Fighters
        whose player couldn't be resolved or loaded are left as they are for this run.
        """
        guild = self.bot.get_guild(config["guild"])
        if guild is None:
            return
        roles = config.get("roles", {})
        fight_role = guild.get_role(roles.get("fight") or 0)
        ready_role = guild.get_role(roles.get("fight_ready") or 0)
        if fight_role is None or ready_role is None:
            logger.warning("fight_ready: role roles.fight or roles.fight_ready not found in the guild")
            return

        tr = await get_translator(guild)
        fighters = list(fight_role.members)
        added = removed = 0

        for member in ready_role.members:
            if fight_role not in member.roles:
                removed += await _change_role(member, ready_role, False, tr("fight_ready.reason_not_fighter"))

        players = await self._load_players(fighters)
        now = datetime.now(timezone.utc)
        for member in fighters:
            user = players.get(member)
            if user is None:
                continue
            has_role = ready_role in member.roles
            if is_ready(user, now):
                if not has_role:
                    added += await _change_role(member, ready_role, True, tr("fight_ready.reason_ready"))
            elif has_role:
                removed += await _change_role(member, ready_role, False, tr("fight_ready.reason_debuff"))

        missing = len(fighters) - len(players)
        if added or removed or missing:
            logger.info("fight_ready: %d added, %d removed, %d fighters not loaded (left unchanged)",
                        added, removed, missing)

    @fight_ready.before_loop
    async def before_fight_ready(self):
        """Wait for the gateway cache (guild members and roles) before the first run."""
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    """Extension entry point: register the Fight Ready job (its loop starts in ``__init__``)."""
    await bot.add_cog(FightReadyJob(bot))
