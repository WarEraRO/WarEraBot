"""/server_ids: every channel, active thread and role of the server with its id, for filling in config.json.

Developer role only. The lists are sent as ephemeral embeds, so only the developer who ran the command sees them.
"""
import logging
from typing import List

import discord
from discord import app_commands
from discord.ext import commands

from utils.common import is_developer
from utils.i18n import Translator, get_translator

logger = logging.getLogger(__name__)

# the user's cap for one embed (Discord allows 4096 in a description)
DESCRIPTION_LIMIT = 4000
# Discord's limits for all the embeds of one message
MESSAGE_EMBED_LIMIT = 10
MESSAGE_TOTAL_LIMIT = 6000

CHANNEL_ICONS = {
    discord.ChannelType.text: "#",
    discord.ChannelType.news: "📢",
    discord.ChannelType.voice: "🔊",
    discord.ChannelType.stage_voice: "🎙️",
    discord.ChannelType.forum: "💬",
    discord.ChannelType.media: "🖼️",
    discord.ChannelType.category: "📁",
}
THREAD_ICON = "🧵"


def _line(icon: str, name: str, object_id: int) -> str:
    """One list entry: icon, name with its markdown escaped, and the id in a code span so it copies cleanly."""
    return f"{icon} {discord.utils.escape_markdown(name)} — `{object_id}`"


def channel_lines(guild: discord.Guild, tr: Translator) -> List[str]:
    """The guild's channels in sidebar order: each category as a bold header, followed by its channels.

    Channels outside any category come first, under the `server_ids.no_category` header.
    """
    lines: List[str] = []
    for category, channels in guild.by_category():
        if category is None:
            if channels:
                lines.append(f"**{tr('server_ids.no_category')}**")
        else:
            lines.append(f"**{_line(CHANNEL_ICONS[discord.ChannelType.category], category.name, category.id)}**")
        for channel in channels:
            lines.append(_line(CHANNEL_ICONS.get(channel.type, "#"), channel.name, channel.id))
    return lines


def thread_lines(guild: discord.Guild) -> List[str]:
    """The guild's cached (active) threads, grouped by parent channel, each followed by its parent's name.

    Archived threads are not in the guild cache, so they are not listed.
    """
    threads = sorted(
        guild.threads,
        key=lambda thread: (thread.parent.position if thread.parent else -1, thread.parent_id, thread.name.casefold()),
    )
    lines: List[str] = []
    for thread in threads:
        line = _line(THREAD_ICON, thread.name, thread.id)
        if thread.parent is not None:
            line += f" · #{discord.utils.escape_markdown(thread.parent.name)}"
        lines.append(line)
    return lines


def role_lines(guild: discord.Guild) -> List[str]:
    """The guild's roles from highest to lowest, @everyone (whose id is the guild id) last."""
    return [_line("@", role.name.lstrip("@"), role.id) for role in reversed(guild.roles)]


def chunk_lines(lines: List[str], limit: int = DESCRIPTION_LIMIT) -> List[str]:
    """Join whole lines into texts of at most `limit` characters each; a line is never split."""
    chunks: List[str] = []
    current = ""
    for line in lines:
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) > limit and current:
            chunks.append(current)
            current = line
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def section_embeds(title_key: str, lines: List[str], tr: Translator) -> List[discord.Embed]:
    """One section (channels, threads or roles) as numbered embeds, with the section's item count in each footer."""
    chunks = chunk_lines(lines) or [tr("common.none")]
    embeds: List[discord.Embed] = []
    for page, chunk in enumerate(chunks, start=1):
        embed = discord.Embed(
            title=tr(title_key, page=page, pages=len(chunks)),
            description=chunk,
            color=discord.Color.blurple(),
        )
        embed.set_footer(text=tr("common.total", total=len(lines)))
        embeds.append(embed)
    return embeds


def group_messages(embeds: List[discord.Embed]) -> List[List[discord.Embed]]:
    """Group the embeds, in order, into as few messages as Discord's per-message limits allow."""
    messages: List[List[discord.Embed]] = []
    for embed in embeds:
        if (
            messages
            and len(messages[-1]) < MESSAGE_EMBED_LIMIT
            and sum(len(item) for item in messages[-1]) + len(embed) <= MESSAGE_TOTAL_LIMIT
        ):
            messages[-1].append(embed)
        else:
            messages.append([embed])
    return messages


class ServerIds(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="server_ids", description="List every channel, thread and role of this server with its id (developers only).")
    @app_commands.guild_only()
    async def server_ids(self, interaction: discord.Interaction):
        tr = await get_translator(interaction.guild_id)
        if not is_developer(interaction.user):
            await interaction.response.send_message(tr("common.not_authorized"), ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        embeds = (
            section_embeds("server_ids.channels_title", channel_lines(guild, tr), tr)
            + section_embeds("server_ids.threads_title", thread_lines(guild), tr)
            + section_embeds("server_ids.roles_title", role_lines(guild), tr)
        )
        for message in group_messages(embeds):
            await interaction.followup.send(embeds=message, ephemeral=True)
        logger.info("Server ids listed for %s (%s)", interaction.user, interaction.user.id)


async def setup(bot: commands.Bot):
    """Extension entry point: register the ServerIds cog (called by `bot.load_extension`)."""
    await bot.add_cog(ServerIds(bot))
