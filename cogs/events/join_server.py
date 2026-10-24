"""Strips every role a member has when they join the server, so leaving and rejoining can't keep old roles.

Only the Unverified role (`config.json` `roles.unverified`, given by Carl-bot) is kept.
"""
import logging

import discord
from discord.ext import commands

from config import config
from utils.i18n import get_translator

logger = logging.getLogger(__name__)


def roles_to_strip(member: discord.Member, keep_id: int) -> list[discord.Role]:
    """The roles to remove from a member who just joined.

    Args:
        member: The member who joined, with the roles they have at that moment.
        keep_id: Id of the role that is never removed (Unverified).

    Returns:
        Every role other than `keep_id` that the bot can remove: not @everyone, not managed by an
        integration (bot roles, Server Booster) and below the bot's top role.
    """
    return [role for role in member.roles if role.id != keep_id and role.is_assignable()]


class JoinServer(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Remove every role, except Unverified, that a member has when they join the server.

        Bots are skipped. When `roles.unverified` is not configured nothing is removed, so the
        Unverified role can't be stripped by mistake. The removal is posted in the reports channel.
        """
        if member.guild.id != config["guild"] or member.bot:
            return
        keep_id = config["roles"].get("unverified")
        if not keep_id:
            logger.warning("roles.unverified is not configured; the roles of %s were not stripped on join", member.id)
            return
        roles = roles_to_strip(member, keep_id)
        if not roles:
            return

        guild = member.guild
        tr = await get_translator(guild)
        try:
            await member.remove_roles(*roles, reason=tr("join_server.reason"))
        except discord.DiscordException:
            logger.exception("Could not strip the roles %s of %s, who joined the server", roles, member.id)
            return
        logger.info("Stripped %s from %s, who joined the server", [role.name for role in roles], member.id)

        channel = guild.get_channel(config["channels"]["reports"])
        if channel is None:
            return
        embed = discord.Embed(
            title=tr("join_server.title"),
            description=tr("join_server.description", member=f"{member.mention} ({member.display_name})"),
            color=discord.Color.orange(),
        )
        embed.add_field(name=tr("join_server.roles"), value=", ".join(role.name for role in roles), inline=False)
        try:
            await channel.send(embed=embed)
        except discord.DiscordException:
            logger.exception("Could not report the roles stripped from %s", member.id)


async def setup(bot: commands.Bot):
    """Extension entry point called by `bot.load_extension` (see run.py)."""
    await bot.add_cog(JoinServer(bot))
