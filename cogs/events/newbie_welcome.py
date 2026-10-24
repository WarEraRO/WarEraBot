"""Welcome message posted in the ro_newbie chat when a member receives the newbie role."""
import logging

import discord
from discord.ext import commands

from config import config
from utils.api import get_game_config, get_military_units_by_ids, get_shared_session
from utils.i18n import Translator, get_translator

logger = logging.getLogger(__name__)

MU_LINK = "https://app.warera.io/mu/{id}"
# how many military units with free spots the welcome recommends
MUS_SHOWN = 5


def open_military_units(mus: dict, game_config: dict | None) -> list[tuple[str, str, int, int]]:
    """The configured military units that have free spots, most free spots first.

    An MU's capacity is the `members` stat of its active dormitories level in
    `gameConfig.upgradesConfig.dormitories.levels`; an MU whose level has no capacity there is skipped.

    Args:
        mus: `{muId: mu}` from `mu.getById`, as returned by `get_military_units_by_ids`.
        game_config: `gameConfig.getGameConfig`, or None when it could not be fetched.

    Returns:
        `(mu_id, name, members, capacity)` for each MU with fewer members than its capacity, in
        `config.json` order among MUs with the same number of free spots.
    """
    levels = (((game_config or {}).get("upgradesConfig") or {}).get("dormitories") or {}).get("levels") or {}
    open_mus = []
    for unit in config.get("military_units", []):
        mu = mus.get(unit["id"])
        if not mu:
            continue
        level = (mu.get("activeUpgradeLevels") or {}).get("dormitories")
        capacity = ((levels.get(str(level)) or {}).get("stats") or {}).get("members")
        members = len(mu.get("members") or [])
        if isinstance(capacity, int) and members < capacity:
            open_mus.append((unit["id"], mu.get("name") or unit["id"], members, capacity))
    return sorted(open_mus, key=lambda item: item[2] - item[3])


def welcome_embed(
    member: discord.Member,
    tr: Translator,
    newbie_role: str,
    citizen_role: str,
    open_mus: list[tuple[str, str, int, int]] | None,
) -> discord.Embed:
    """Build the embed that welcomes a member who just received the newbie role.

    Args:
        member: The member being welcomed; shown in the author line with their avatar.
        tr: Translator for the server's language.
        newbie_role: Name of the newbie role, as shown in the description.
        citizen_role: Name of the citizen role, as shown in the promotion field's name and value.
        open_mus: Military units with free spots from `open_military_units`; the first `MUS_SHOWN`
            are linked. None (data unavailable) or an empty list shows a hint to ask in the chat.

    Returns:
        The welcome embed. The mention that notifies the member is not part of it, because
        mentions inside an embed don't ping.
    """
    embed = discord.Embed(
        title=tr("newbie_welcome.title"),
        description=tr("newbie_welcome.description", role=newbie_role),
        color=discord.Color.green(),
    )
    embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)
    embed.add_field(name=tr("newbie_welcome.nickname.name"), value=tr("newbie_welcome.nickname.value"), inline=False)
    embed.add_field(name=tr("newbie_welcome.start.name"), value=tr("newbie_welcome.start.value"), inline=False)

    if open_mus:
        lines = [
            tr(
                "newbie_welcome.mus.line",
                # brackets in the name would break the markdown link
                name=name.replace("[", "(").replace("]", ")"),
                link=MU_LINK.format(id=mu_id),
                members=members,
                capacity=capacity,
                free=tr.plural("newbie_welcome.mus.free", capacity - members),
            )
            for mu_id, name, members, capacity in open_mus[:MUS_SHOWN]
        ]
        mus_value = "\n".join([tr("newbie_welcome.mus.intro"), *lines])
    else:
        mus_value = tr("newbie_welcome.mus.none")
    embed.add_field(name=tr("newbie_welcome.mus.name"), value=mus_value, inline=False)

    embed.add_field(
        name=tr("newbie_welcome.promotion.name", citizen=citizen_role),
        value=tr("newbie_welcome.promotion.value", citizen=citizen_role),
        inline=False,
    )
    embed.add_field(name=tr("newbie_welcome.help.name"), value=tr("newbie_welcome.help.value"), inline=False)
    return embed


class NewbieWelcome(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @staticmethod
    async def _open_military_units() -> list[tuple[str, str, int, int]] | None:
        """Fetch the configured MUs and the game config (2 requests); None when the MUs can't be read."""
        try:
            session = await get_shared_session()
            mus = await get_military_units_by_ids([unit["id"] for unit in config.get("military_units", [])], session)
            if not mus:
                return None
            return open_military_units(mus, await get_game_config(session))
        except Exception:
            logger.exception("Could not read the military units for the newbie welcome")
            return None

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """Welcome a member in the ro_newbie chat when they gain the newbie role.

        Only a role change counts: a restart or a member who already had the role posts nothing.
        The member is mentioned in the message content so they get notified; no one else is pinged.
        The configured military units with free spots are read live when the welcome is posted.
        """
        if after.guild.id != config["guild"]:
            return
        role_id = config["roles"].get("newbie")
        if not role_id or before.get_role(role_id) is not None or after.get_role(role_id) is None:
            return

        guild = after.guild
        channel_id = config.get("chats", {}).get("ro_newbie")
        channel = guild.get_channel_or_thread(channel_id) if channel_id else None
        if channel is None:
            logger.warning("Newbie chat %s not found; %s was not welcomed", channel_id, after.id)
            return

        tr = await get_translator(guild)
        citizen = guild.get_role(config["roles"].get("citizen") or 0)
        embed = welcome_embed(
            after,
            tr,
            newbie_role=after.get_role(role_id).name,
            citizen_role=citizen.name if citizen else tr("newbie_welcome.citizen_fallback"),
            open_mus=await self._open_military_units(),
        )
        try:
            await channel.send(
                content=after.mention,
                embed=embed,
                allowed_mentions=discord.AllowedMentions(everyone=False, roles=False, users=[after]),
            )
        except discord.DiscordException:
            logger.exception("Could not welcome %s in the newbie chat", after.id)


async def setup(bot: commands.Bot):
    """Extension entry point called by `bot.load_extension` (see run.py)."""
    await bot.add_cog(NewbieWelcome(bot))
