import discord
from discord import app_commands
from discord.ext import commands

from config import config


class BattleOrders(commands.Cog):
    priority = app_commands.Group(
        name="priority",
        description="Manage battle order priorities.",
    )

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _member_has_government(self, member: discord.Member) -> bool:
        gov_ids = config.get("roles", {}).get("government", [])
        return bool(gov_ids) and any(
            role.id in gov_ids for role in getattr(member, "roles", [])
        )

    def _monitor(self):
        return self.bot.get_cog("BattleOrderMonitorJob")

    async def _require_monitor(self, interaction: discord.Interaction):
        monitor = self._monitor()
        if monitor is None:
            await interaction.followup.send("Battle order monitor is not loaded.")
            return None
        return monitor

    @priority.command(name="list", description="List current battle order priorities.")
    async def list_priorities(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        monitor = await self._require_monitor(interaction)
        if monitor is None:
            return

        entries = await monitor.get_priorities()
        embed = discord.Embed(
            title="Battle Order Priorities",
            color=discord.Color.red(),
        )
        if not entries:
            embed.description = "No battle order priorities are currently active."
        else:
            lines = []
            for index, entry in enumerate(entries, start=1):
                description = entry.get("description") or "No description."
                lines.append(
                    f"{index}. Order Description: {description}\n"
                    f"{monitor.format_priority_title(entry)}"
                )
            embed.description = "\n\n".join(lines)

        await interaction.followup.send(embed=embed)

    @priority.command(name="refresh", description="Force a battle order priority refresh.")
    async def refresh(self, interaction: discord.Interaction):
        if not self._member_has_government(interaction.user):
            await interaction.response.send_message(
                "You are not authorized to use this command.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        monitor = await self._require_monitor(interaction)
        if monitor is None:
            return

        added = await monitor.check_orders(notify=True)
        await interaction.followup.send(f"Battle order priorities refreshed. Added {added} new priorities.")

    @priority.command(name="set", description="Set the description for a battle order priority.")
    @app_commands.describe(
        entry_number="Priority number from /priority list",
        description="Order description to set",
    )
    async def set_description(
        self,
        interaction: discord.Interaction,
        entry_number: int,
        description: str,
    ):
        if not self._member_has_government(interaction.user):
            await interaction.response.send_message(
                "You are not authorized to use this command.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        monitor = await self._require_monitor(interaction)
        if monitor is None:
            return

        updated = await monitor.set_description(entry_number, description)
        if not updated:
            await interaction.followup.send("Invalid priority number.")
            return
        await interaction.followup.send(f"Updated priority {entry_number}.")

    @priority.command(name="add", description="Add an active battle to the priority list.")
    @app_commands.describe(
        link="WarEra battle link",
        description="Order description",
    )
    async def add(
        self,
        interaction: discord.Interaction,
        link: str,
        description: str,
    ):
        if not self._member_has_government(interaction.user):
            await interaction.response.send_message(
                "You are not authorized to use this command.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        monitor = await self._require_monitor(interaction)
        if monitor is None:
            return

        added, message, entry = await monitor.add_priority_from_link(link, description)
        if not added:
            await interaction.followup.send(message)
            return

        priorities = await monitor.get_priorities()
        number = next(
            (
                index
                for index, priority_entry in enumerate(priorities, start=1)
                if priority_entry.get("token") == entry.get("token")
            ),
            len(priorities),
        )
        await interaction.followup.send(f"{message} It is priority {number}.")

    @priority.command(name="move", description="Swap two battle order priorities.")
    @app_commands.describe(
        entry_number_a="First priority number",
        entry_number_b="Second priority number",
    )
    async def move(
        self,
        interaction: discord.Interaction,
        entry_number_a: int,
        entry_number_b: int,
    ):
        if not self._member_has_government(interaction.user):
            await interaction.response.send_message(
                "You are not authorized to use this command.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        monitor = await self._require_monitor(interaction)
        if monitor is None:
            return

        moved = await monitor.move_priorities(entry_number_a, entry_number_b)
        if not moved:
            await interaction.followup.send("One or both priority numbers are invalid.")
            return
        await interaction.followup.send(f"Swapped priorities {entry_number_a} and {entry_number_b}.")

    @priority.command(name="remove", description="Remove a battle order priority.")
    @app_commands.describe(entry_number="Priority number from /priority list")
    async def remove(
        self,
        interaction: discord.Interaction,
        entry_number: int,
    ):
        if not self._member_has_government(interaction.user):
            await interaction.response.send_message(
                "You are not authorized to use this command.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        monitor = await self._require_monitor(interaction)
        if monitor is None:
            return

        removed = await monitor.remove_priority(entry_number)
        if not removed:
            await interaction.followup.send("Invalid priority number.")
            return
        await interaction.followup.send(f"Removed priority {entry_number}.")


async def setup(bot: commands.Bot):
    await bot.add_cog(BattleOrders(bot))
