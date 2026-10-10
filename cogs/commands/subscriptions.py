import asyncio
import logging
import time
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

from cogs.tasks.military_unit_contract_monitor import SUBSCRIPTION_JOB, contract_units
from utils.api import get_military_units_by_ids, get_shared_session, get_user, get_user_info
from utils.common import get_mu_destination
from utils.db import (
    add_job_subscription,
    find_api_id_by_discord_id,
    find_api_id_by_discord_username,
    find_api_id_by_display_name,
    get_user_job_subscriptions,
    init_db,
    remove_job_subscription,
    save_user,
)
from utils.i18n import Translator, get_translator

logger = logging.getLogger(__name__)

MU_NAMES_TTL = 3600


class Subscriptions(commands.Cog):
    subscribe = app_commands.Group(
        name="subscribe", description="Get pinged by a bot job.", guild_only=True
    )
    unsubscribe = app_commands.Group(
        name="unsubscribe", description="Stop getting pinged by a bot job.", guild_only=True
    )

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # MU id -> in-game name (mu.getById), for the MUs that get contract embeds
        self._mu_names: dict[str, str] = {}
        self._mu_names_at = 0.0
        self._mu_names_task: asyncio.Task | None = None
        # creates the job_subscriptions table
        try:
            init_db()
        except Exception:
            pass

    async def cog_load(self):
        # warmed in the background so autocomplete has names right away
        self._refresh_mu_names()

    def cog_unload(self):
        if self._mu_names_task and not self._mu_names_task.done():
            self._mu_names_task.cancel()

    def _refresh_mu_names(self) -> None:
        """Start refreshing the MU names unless a refresh is already running."""
        if self._mu_names_task and not self._mu_names_task.done():
            return

        async def _refresh():
            session = await get_shared_session()
            military_units = await get_military_units_by_ids(list(contract_units()), session)
            # a failed fetch keeps the name already known
            for mu_id, military_unit in military_units.items():
                if military_unit.get("name"):
                    self._mu_names[mu_id] = str(military_unit["name"])
            self._mu_names_at = time.monotonic()

        self._mu_names_task = asyncio.create_task(_refresh())

    def _find_unit(self, value: str) -> str | None:
        """The MU id matching an MU id (autocomplete value) or in-game MU name (typed by hand)."""
        value = (value or "").strip()
        for mu_id in contract_units():
            if value == mu_id or value.lower() == self._mu_names.get(mu_id, "").lower():
                return mu_id
        return None

    def _mu_name(self, mu_id: str) -> str:
        return discord.utils.escape_markdown(self._mu_names.get(mu_id, mu_id))

    async def _fetch_player(self, member: discord.Member, session) -> dict | None:
        """The member's WarEra user (getUserLite), from the saved mapping or by their display name."""
        try:
            api_id = await asyncio.to_thread(
                lambda: find_api_id_by_discord_id(member.id)
                or find_api_id_by_display_name(member.display_name)
                or find_api_id_by_discord_username(member.name)
            )
        except Exception:
            api_id = None
        if api_id:
            user = await get_user_info(api_id, session)
            if user:
                return user

        user = await get_user(member.display_name, session)
        if isinstance(user, dict) and user.get("_id"):
            try:
                await asyncio.to_thread(save_user, member.name, member.display_name, user["_id"], member.id)
            except Exception:
                pass
            return user
        return None

    async def _destination_text(self, guild: discord.Guild, mu_id: str, tr: Translator) -> str:
        unit = contract_units().get(mu_id)
        destination = await get_mu_destination(guild, unit, "contractsId") if unit and guild else None
        return destination.mention if destination else tr("subscriptions.unit_channel")

    # ------------------------------------------------------------------ /subscribe contracts

    @subscribe.command(name="contracts", description="Get pinged when your military unit wins a mercenary contract.")
    @app_commands.describe(military_unit="Your military unit (defaults to the one you are in)")
    async def subscribe_contracts(self, interaction: discord.Interaction, military_unit: str | None = None):
        await interaction.response.defer(ephemeral=True)
        tr = await get_translator(interaction.guild_id)

        mu_id = None
        if military_unit:
            mu_id = self._find_unit(military_unit)
            if mu_id is None:
                await interaction.followup.send(tr("subscriptions.unknown_unit"), ephemeral=True)
                return

        session = await get_shared_session()
        user = await self._fetch_player(interaction.user, session)
        if user is None:
            await interaction.followup.send(tr("subscriptions.player_not_found"), ephemeral=True)
            return

        # only members of the MU may subscribe to its contracts
        player_mu = str(user.get("mu") or "")
        if mu_id is None:
            if player_mu not in contract_units():
                await interaction.followup.send(tr("subscriptions.not_in_unit"), ephemeral=True)
                return
            mu_id = player_mu
        elif player_mu != mu_id:
            await interaction.followup.send(tr("subscriptions.not_member", mu=self._mu_name(mu_id)), ephemeral=True)
            return

        if mu_id not in self._mu_names:
            self._refresh_mu_names()
            await self._mu_names_task

        try:
            created = await asyncio.to_thread(
                add_job_subscription,
                SUBSCRIPTION_JOB,
                mu_id,
                interaction.user.id,
                str(user["_id"]),
                datetime.now(timezone.utc).isoformat(),
            )
        except Exception:
            logger.exception("Could not save contract subscription of %s for MU %s", interaction.user.id, mu_id)
            await interaction.followup.send(tr("subscriptions.failed"), ephemeral=True)
            return

        mu_name = self._mu_name(mu_id)
        if not created:
            await interaction.followup.send(tr("subscriptions.already_subscribed", mu=mu_name), ephemeral=True)
            return
        channel = await self._destination_text(interaction.guild, mu_id, tr)
        await interaction.followup.send(tr("subscriptions.subscribed", mu=mu_name, channel=channel), ephemeral=True)

    # ------------------------------------------------------------------ /unsubscribe contracts

    @unsubscribe.command(name="contracts", description="Stop getting pinged when a military unit wins a mercenary contract.")
    @app_commands.describe(military_unit="Military unit to unsubscribe from (defaults to all of them)")
    async def unsubscribe_contracts(self, interaction: discord.Interaction, military_unit: str | None = None):
        await interaction.response.defer(ephemeral=True)
        tr = await get_translator(interaction.guild_id)

        try:
            subscriptions = await asyncio.to_thread(get_user_job_subscriptions, interaction.user.id, SUBSCRIPTION_JOB)
        except Exception:
            logger.exception("Could not read contract subscriptions of %s", interaction.user.id)
            await interaction.followup.send(tr("subscriptions.failed"), ephemeral=True)
            return
        subscribed = [str(s["target_id"]) for s in subscriptions]

        if military_unit:
            # an MU removed from config.json can still be unsubscribed by its id
            mu_id = self._find_unit(military_unit) or (military_unit.strip() if military_unit.strip() in subscribed else None)
            if mu_id is None:
                await interaction.followup.send(tr("subscriptions.unknown_unit"), ephemeral=True)
                return
            if mu_id not in subscribed:
                await interaction.followup.send(tr("subscriptions.not_subscribed", mu=self._mu_name(mu_id)), ephemeral=True)
                return
            targets = [mu_id]
        else:
            if not subscribed:
                await interaction.followup.send(tr("subscriptions.no_subscriptions"), ephemeral=True)
                return
            targets = subscribed

        removed = []
        try:
            for mu_id in targets:
                await asyncio.to_thread(remove_job_subscription, SUBSCRIPTION_JOB, mu_id, interaction.user.id)
                removed.append(mu_id)
        except Exception:
            logger.exception("Could not remove contract subscriptions of %s", interaction.user.id)
            if not removed:
                await interaction.followup.send(tr("subscriptions.failed"), ephemeral=True)
                return

        names = ", ".join(f"**{self._mu_name(mu_id)}**" for mu_id in removed)
        await interaction.followup.send(tr("subscriptions.unsubscribed", mus=names), ephemeral=True)

    # ------------------------------------------------------------------ autocomplete

    @subscribe_contracts.autocomplete("military_unit")
    @unsubscribe_contracts.autocomplete("military_unit")
    async def military_unit_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        if time.monotonic() - self._mu_names_at > MU_NAMES_TTL:
            self._refresh_mu_names()
        current = (current or "").lower()
        # an MU whose name has not been fetched yet is offered by its id
        names = sorted(((self._mu_names.get(mu_id, mu_id), mu_id) for mu_id in contract_units()), key=lambda item: item[0].lower())
        return [
            app_commands.Choice(name=name[:100], value=mu_id)
            for name, mu_id in names
            if current in name.lower()
        ][:25]


async def setup(bot: commands.Bot):
    await bot.add_cog(Subscriptions(bot))
