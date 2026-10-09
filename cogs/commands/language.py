import logging
from typing import List

import discord
from discord import app_commands
from discord.ext import commands

from utils import db
from utils.common import is_developer
from utils.i18n import LANGUAGES, Translator, get_translator, normalize_language, set_guild_language

logger = logging.getLogger(__name__)


class Language(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # creates the guild_settings table the language is stored in
        try:
            db.init_db()
        except Exception:
            pass

    @app_commands.command(name="setlang", description="Set the language the bot uses in this server (developers only).")
    @app_commands.describe(language="Language for all bot messages in this server")
    @app_commands.guild_only()
    async def setlang(self, interaction: discord.Interaction, language: str):
        tr = await get_translator(interaction.guild_id)
        if not is_developer(interaction.user):
            await interaction.response.send_message(tr("common.not_authorized"), ephemeral=True)
            return

        code = normalize_language(language)
        if code is None:
            await interaction.response.send_message(
                tr("setlang.unknown", language=language, available=", ".join(LANGUAGES.values())),
                ephemeral=True,
            )
            return

        try:
            await set_guild_language(interaction.guild_id, code)
        except Exception:
            logger.exception("Could not save language %s for guild %s", code, interaction.guild_id)
            await interaction.response.send_message(tr("setlang.failed"), ephemeral=True)
            return

        logger.info("Language of guild %s set to %s by %s (%s)", interaction.guild_id, code, interaction.user, interaction.user.id)
        # confirmed in the language just chosen
        tr = Translator(code)
        await interaction.response.send_message(tr("setlang.updated", language=tr(f"languages.{code}")))

    @setlang.autocomplete("language")
    async def language_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        if not is_developer(interaction.user):
            return []
        current = (current or "").strip().casefold()
        return [
            app_commands.Choice(name=name, value=code)
            for code, name in LANGUAGES.items()
            if current in name.casefold() or current == code
        ]


async def setup(bot: commands.Bot):
    await bot.add_cog(Language(bot))
