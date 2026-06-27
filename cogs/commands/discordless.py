import discord
import asyncio
from discord import app_commands
from discord.ext import commands

from config import config
from utils.api import get_all_countries, get_country_users, get_shared_session, get_user_info


COUNTRY_NAME = "Romania"
PAGE_SIZE = 15
USER_INFO_CONCURRENCY = 8


def _normalize_name(value: object) -> str:
    return str(value or "").strip().casefold()


def _user_id(user: dict) -> str | None:
    return user.get("_id")


def _username(user: dict) -> str:
    return str(user.get("username") or user.get("name") or "Unknown")


def _find_country(countries: list[dict], name: str) -> dict | None:
    wanted = _normalize_name(name)
    for country in countries:
        if _normalize_name(country.get("name")) == wanted:
            return country
    return None


def _build_pages(users: list[dict], discord_count: int, country_total: int) -> list[discord.Embed]:
    title = f"{COUNTRY_NAME} Users Not In Discord"
    if not users:
        embed = discord.Embed(
            title=title,
            description="*All Romania citizens were found in Discord.*",
            color=discord.Color.green(),
        )
        embed.set_footer(
            text=f"Page 1 of 1 - Missing: 0 - Discord checked: {discord_count} - Country users: {country_total}"
        )
        return [embed]

    total = len(users)
    total_pages = max(1, (total - 1) // PAGE_SIZE + 1)
    pages = []

    for i in range(0, total, PAGE_SIZE):
        chunk = users[i : i + PAGE_SIZE]
        lines = []
        for user in chunk:
            username = _username(user)
            user_id = _user_id(user)
            if user_id:
                lines.append(f"- [{username}](https://app.warera.io/user/{user_id}) - Level: {user['leveling']['level']}")
            else:
                lines.append(f"- {username} - Level: {user['leveling']['level']}")

        embed = discord.Embed(
            title=title,
            description="\n".join(lines),
            color=discord.Color.orange(),
        )
        embed.set_footer(
            text=(
                f"Page {i // PAGE_SIZE + 1} of {total_pages} - Missing: {total} - "
                f"Discord checked: {discord_count} - Country users: {country_total}"
            )
        )
        pages.append(embed)

    return pages


class _Paginator(discord.ui.View):
    def __init__(self, pages: list[discord.Embed], timeout: int = 180):
        super().__init__(timeout=timeout)
        self.pages = pages
        self.current = 0
        self.message: discord.Message | None = None
        self._sync()

    def _sync(self) -> None:
        self.prev_btn.disabled = self.current == 0
        self.next_btn.disabled = self.current == len(self.pages) - 1

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

    @discord.ui.button(label="Prev", style=discord.ButtonStyle.primary)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current = max(0, self.current - 1)
        self._sync()
        await interaction.response.edit_message(embed=self.pages[self.current], view=self)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.primary)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current = min(len(self.pages) - 1, self.current + 1)
        self._sync()
        await interaction.response.edit_message(embed=self.pages[self.current], view=self)


class Discordless(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._user_cache: dict[str, dict] = {}

    async def _resolve_user(
        self,
        user_ref: dict,
        session,
        semaphore: asyncio.Semaphore,
    ) -> dict | None:
        user_id = _user_id(user_ref)
        if not user_id:
            return None
        if user_id in self._user_cache:
            return self._user_cache[user_id]

        async with semaphore:
            user = await get_user_info(user_id, session)
        if user:
            self._user_cache[user_id] = user
        return user


    @app_commands.command(
        name="discorless",
        description="List Romania citizens who are not present in Discord as Citizen/Newbie members.",
    )
    async def discorless(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)

        guild = interaction.guild or self.bot.get_guild(config["guild"])
        if guild is None:
            await interaction.followup.send("Guild not found.", ephemeral=True)
            return

        citizen_role = guild.get_role(config["roles"].get("citizen"))
        newbie_role = guild.get_role(config["roles"].get("newbie"))

        members: set[discord.Member] = set()
        if citizen_role:
            members.update(citizen_role.members)
        if newbie_role:
            members.update(newbie_role.members)

        discord_names = {
            _normalize_name(member.display_name)
            for member in members
            if _normalize_name(member.display_name)
        }

        session = await get_shared_session()
        countries = await get_all_countries(session)
        if not countries:
            await interaction.followup.send(
                "Could not load the country list. Please try again later.",
                ephemeral=True,
            )
            return

        country = _find_country(countries, COUNTRY_NAME)
        if country is None:
            await interaction.followup.send(
                f"Could not find `{COUNTRY_NAME}` in the WarEra country list.",
                ephemeral=True,
            )
            return

        user_refs = await get_country_users(country["_id"], session)
        if user_refs is None:
            await interaction.followup.send(
                f"Could not load {COUNTRY_NAME} users. Please try again later.",
                ephemeral=True,
            )
            return
        
        semaphore = asyncio.Semaphore(USER_INFO_CONCURRENCY)
        resolved_users = await asyncio.gather(
            *(
                self._resolve_user(user_ref, session, semaphore)
                for user_ref in user_refs
            )
        )
        users = [user for user in resolved_users if user is not None]

        missing = [
            user
            for user in users
            if _normalize_name(_username(user)) not in discord_names
        ]
        missing.sort(key=lambda user: _normalize_name(_username(user)))

        pages = _build_pages(missing, len(discord_names), len(user_refs))
        if len(pages) == 1:
            await interaction.followup.send(embed=pages[0])
        else:
            view = _Paginator(pages)
            msg = await interaction.followup.send(embed=pages[0], view=view, wait=True)
            view.message = msg


async def setup(bot: commands.Bot):
    await bot.add_cog(Discordless(bot))
