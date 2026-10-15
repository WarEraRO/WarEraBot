import asyncio
import logging
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

from cogs.tasks.loot_alerts import SUBSCRIPTION_JOB as LOOT_SUBSCRIPTION_JOB
from cogs.tasks.loot_alerts import SUBSCRIPTION_TARGET as LOOT_SUBSCRIPTION_TARGET
from cogs.tasks.military_unit_contract_monitor import SUBSCRIPTION_JOB, SUBSCRIPTION_TARGET, contract_units
from config import config
from utils.api import get_military_unit, get_shared_session, get_user_info
from utils.common import get_mu_destination
from utils.db import (
    add_job_subscription,
    find_api_id_by_discord_id,
    get_user_job_subscriptions,
    init_db,
    remove_job_subscription,
)
from utils.i18n import Translator, get_translator

logger = logging.getLogger(__name__)


class Subscriptions(commands.Cog):
    subscribe = app_commands.Group(
        name="subscribe", description="Get pinged by a bot job.", guild_only=True
    )
    unsubscribe = app_commands.Group(
        name="unsubscribe", description="Stop getting pinged by a bot job.", guild_only=True
    )

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # creates the job_subscriptions table
        try:
            init_db()
        except Exception:
            pass

    async def _destination_text(self, guild: discord.Guild, mu_id: str, tr: Translator) -> str:
        unit = contract_units().get(mu_id)
        destination = await get_mu_destination(guild, unit, "contractsId") if unit and guild else None
        return destination.mention if destination else tr("subscriptions.unit_channel")

    async def _remove_subscriptions(self, discord_id: int | str, job: str | None = None) -> list[dict]:
        """Remove a member's job subscriptions (of every job when `job` is None) and return the removed ones.

        Raises:
            Exception: A database error. Subscriptions removed before it stay removed.
        """
        subscriptions = await asyncio.to_thread(get_user_job_subscriptions, discord_id, job)
        for subscription in subscriptions:
            await asyncio.to_thread(remove_job_subscription, subscription["job"], subscription["target_id"], discord_id)
        return subscriptions

    @commands.Cog.listener()
    async def on_raw_member_remove(self, payload: discord.RawMemberRemoveEvent):
        """Drop every job subscription of a member who left the server the pings are posted in."""
        if payload.guild_id != config["guild"]:
            return
        try:
            removed = await self._remove_subscriptions(payload.user.id)
        except Exception:
            logger.exception("Could not drop the job subscriptions of %s, who left the server", payload.user.id)
            return
        if removed:
            logger.info("Dropped %d job subscription(s) of %s, who left the server", len(removed), payload.user.id)

    # ------------------------------------------------------------------ /subscribe contracts

    @subscribe.command(name="contracts", description="Get pinged when your military unit wins a mercenary contract.")
    async def subscribe_contracts(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        tr = await get_translator(interaction.guild_id)

        # only the WarEra player linked to the caller's Discord account (see the unidentified_members job)
        try:
            api_id = await asyncio.to_thread(find_api_id_by_discord_id, interaction.user.id)
        except Exception:
            logger.exception("Could not read the WarEra player linked to %s", interaction.user.id)
            await interaction.followup.send(tr("subscriptions.failed"), ephemeral=True)
            return
        if not api_id:
            await interaction.followup.send(tr("subscriptions.not_linked"), ephemeral=True)
            return

        session = await get_shared_session()
        user = await get_user_info(api_id, session)
        if not user:
            await interaction.followup.send(tr("subscriptions.player_not_found"), ephemeral=True)
            return

        # only members of an MU that gets contract posts may subscribe; the MU itself is not stored
        mu_id = str(user.get("mu") or "")
        if mu_id not in contract_units():
            await interaction.followup.send(tr("subscriptions.not_in_unit"), ephemeral=True)
            return

        try:
            created = await asyncio.to_thread(
                add_job_subscription,
                SUBSCRIPTION_JOB,
                SUBSCRIPTION_TARGET,
                interaction.user.id,
                str(api_id),
                datetime.now(timezone.utc).isoformat(),
            )
        except Exception:
            logger.exception("Could not save the contract subscription of %s", interaction.user.id)
            await interaction.followup.send(tr("subscriptions.failed"), ephemeral=True)
            return

        military_unit = await get_military_unit(mu_id, session)
        mu_name = discord.utils.escape_markdown(str((military_unit or {}).get("name") or mu_id))
        if not created:
            await interaction.followup.send(tr("subscriptions.already_subscribed", mu=mu_name), ephemeral=True)
            return
        channel = await self._destination_text(interaction.guild, mu_id, tr)
        await interaction.followup.send(tr("subscriptions.subscribed", mu=mu_name, channel=channel), ephemeral=True)

    # ------------------------------------------------------------------ /unsubscribe contracts

    @unsubscribe.command(name="contracts", description="Stop getting pinged when your military unit wins a mercenary contract.")
    async def unsubscribe_contracts(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        tr = await get_translator(interaction.guild_id)

        try:
            removed = await self._remove_subscriptions(interaction.user.id, SUBSCRIPTION_JOB)
        except Exception:
            logger.exception("Could not remove the contract subscription of %s", interaction.user.id)
            await interaction.followup.send(tr("subscriptions.failed"), ephemeral=True)
            return
        if not removed:
            await interaction.followup.send(tr("subscriptions.not_subscribed"), ephemeral=True)
            return
        await interaction.followup.send(tr("subscriptions.unsubscribed"), ephemeral=True)

    # ------------------------------------------------------------------ /subscribe loot

    @subscribe.command(name="loot", description="Get a DM about your loot in the last minutes of each round of a battle you hit.")
    async def subscribe_loot(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        tr = await get_translator(interaction.guild_id)

        # only the WarEra player linked to the caller's Discord account (see the unidentified_members job)
        try:
            api_id = await asyncio.to_thread(find_api_id_by_discord_id, interaction.user.id)
        except Exception:
            logger.exception("Could not read the WarEra player linked to %s", interaction.user.id)
            await interaction.followup.send(tr("subscriptions.failed"), ephemeral=True)
            return
        if not api_id:
            await interaction.followup.send(tr("subscriptions.not_linked"), ephemeral=True)
            return

        session = await get_shared_session()
        if not await get_user_info(api_id, session):
            await interaction.followup.send(tr("subscriptions.player_not_found"), ephemeral=True)
            return

        # any player may subscribe; the build, bars and debuff are checked when a round is ending
        try:
            created = await asyncio.to_thread(
                add_job_subscription,
                LOOT_SUBSCRIPTION_JOB,
                LOOT_SUBSCRIPTION_TARGET,
                interaction.user.id,
                str(api_id),
                datetime.now(timezone.utc).isoformat(),
            )
        except Exception:
            logger.exception("Could not save the loot alert subscription of %s", interaction.user.id)
            await interaction.followup.send(tr("subscriptions.failed"), ephemeral=True)
            return
        key = "subscriptions.loot_subscribed" if created else "subscriptions.loot_already_subscribed"
        await interaction.followup.send(tr(key), ephemeral=True)

    # ------------------------------------------------------------------ /unsubscribe loot

    @unsubscribe.command(name="loot", description="Stop getting DMs about your loot when a round is ending.")
    async def unsubscribe_loot(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        tr = await get_translator(interaction.guild_id)

        try:
            removed = await self._remove_subscriptions(interaction.user.id, LOOT_SUBSCRIPTION_JOB)
        except Exception:
            logger.exception("Could not remove the loot alert subscription of %s", interaction.user.id)
            await interaction.followup.send(tr("subscriptions.failed"), ephemeral=True)
            return
        key = "subscriptions.loot_unsubscribed" if removed else "subscriptions.loot_not_subscribed"
        await interaction.followup.send(tr(key), ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Subscriptions(bot))
