import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timezone
from config import config
from utils.api import get_user, get_shared_session

_INACTIVE_THRESHOLD_SECONDS = 3 * 24 * 3600

_FILTERS = [
    ("wrong_mu",  "Wrong MU",        discord.Color.orange()),
    ("no_mu",     "No MU",           discord.Color.red()),
    ("inactive",  "Inactive Strays", discord.Color.dark_grey()),
]
_PAGE_SIZE = 15


def _is_inactive(user: dict) -> bool:
    try:
        last_conn_str = (user.get("dates") or {}).get("lastConnectionAt")
        if not last_conn_str:
            return False
        last_conn = datetime.fromisoformat(last_conn_str.replace("Z", "+00:00"))
        delta = datetime.now(timezone.utc) - last_conn
        return delta.total_seconds() >= _INACTIVE_THRESHOLD_SECONDS
    except Exception:
        return False


def _build_pages(names: list[str], title: str, color: discord.Color) -> list[discord.Embed]:
    if not names:
        embed = discord.Embed(title=title, description="*No players in this category.*", color=color)
        embed.set_footer(text="Page 1 of 1 — Total: 0")
        return [embed]
    total = len(names)
    total_pages = max(1, (total - 1) // _PAGE_SIZE + 1)
    pages = []
    for i in range(0, total, _PAGE_SIZE):
        chunk = names[i : i + _PAGE_SIZE]
        embed = discord.Embed(title=title, color=color)
        embed.description = "\n".join(f"• {n}" for n in chunk)
        embed.set_footer(text=f"Page {i // _PAGE_SIZE + 1} of {total_pages} — Total: {total}")
        pages.append(embed)
    return pages


class _StrayView(discord.ui.View):
    def __init__(self, data: dict[str, list[str]], timeout: int = 180):
        super().__init__(timeout=timeout)
        self.message: discord.Message | None = None
        self.data = data                # key -> sorted list of names
        self.active_filter: str = "wrong_mu"
        self.page_index: dict[str, int] = {key: 0 for key, *_ in _FILTERS}
        self._pages: dict[str, list[discord.Embed]] = {
            key: _build_pages(data[key], label, color)
            for key, label, color in _FILTERS
        }
        self._sync_buttons()

    # ------------------------------------------------------------------ helpers

    @property
    def _current_pages(self) -> list[discord.Embed]:
        return self._pages[self.active_filter]

    @property
    def _current_page(self) -> int:
        return self.page_index[self.active_filter]

    @_current_page.setter
    def _current_page(self, value: int):
        self.page_index[self.active_filter] = value

    def _sync_buttons(self):
        last = len(self._current_pages) - 1
        cur  = self._current_page
        # Navigation buttons are children[0] and children[1]
        self.prev_btn.disabled = cur == 0
        self.next_btn.disabled = cur == last
        # Filter buttons: highlight the active one
        for btn in (self.btn_wrong_mu, self.btn_no_mu, self.btn_inactive):
            key = btn.custom_id
            btn.style = discord.ButtonStyle.success if key == self.active_filter else discord.ButtonStyle.secondary

    async def _refresh(self, interaction: discord.Interaction):
        self._sync_buttons()
        await interaction.response.edit_message(
            embed=self._current_pages[self._current_page], view=self
        )

    # ------------------------------------------------------------------ timeout

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

    # ------------------------------------------------------------------ navigation (row 0)

    @discord.ui.button(label="◀ Prev", style=discord.ButtonStyle.primary, row=0)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self._current_page = max(0, self._current_page - 1)
        await self._refresh(interaction)

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.primary, row=0)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self._current_page = min(len(self._current_pages) - 1, self._current_page + 1)
        await self._refresh(interaction)

    # ------------------------------------------------------------------ filters (row 1)

    @discord.ui.button(label="Wrong MU", style=discord.ButtonStyle.success, custom_id="wrong_mu", row=1)
    async def btn_wrong_mu(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.active_filter = "wrong_mu"
        await self._refresh(interaction)

    @discord.ui.button(label="No MU", style=discord.ButtonStyle.secondary, custom_id="no_mu", row=1)
    async def btn_no_mu(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.active_filter = "no_mu"
        await self._refresh(interaction)

    @discord.ui.button(label="Inactive Strays", style=discord.ButtonStyle.secondary, custom_id="inactive", row=1)
    async def btn_inactive(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.active_filter = "inactive"
        await self._refresh(interaction)


class MuStray(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="mu_stray",
        description="List players not belonging to any configured military unit.",
    )
    async def mu_stray(self, interaction: discord.Interaction):
        await interaction.response.defer()

        guild = interaction.guild or self.bot.get_guild(config["guild"])
        if guild is None:
            await interaction.followup.send("Guild not found.", ephemeral=True)
            return

        citizen = guild.get_role(config["roles"]["citizen"])
        newbie = guild.get_role(config["roles"]["newbie"])

        members: set[discord.Member] = set()
        if citizen:
            members.update(citizen.members)
        if newbie:
            members.update(newbie.members)

        configured_mu_ids: set[str] = {unit["id"] for unit in config.get("military_units", [])}

        session = await get_shared_session()

        wrong_mu: list[str] = []
        no_mu: list[str] = []
        inactive: list[str] = []

        for member in members:
            try:
                user = await get_user(member.display_name, session)
            except Exception:
                user = None
            if not user:
                continue

            mu_id = user.get("mu") if isinstance(user, dict) else None
            if mu_id in configured_mu_ids:
                continue

            if _is_inactive(user):
                inactive.append(member.display_name)
            elif mu_id:
                wrong_mu.append(member.display_name)
            else:
                no_mu.append(member.display_name)

        for lst in (wrong_mu, no_mu, inactive):
            lst.sort(key=str.lower)

        if not wrong_mu and not no_mu and not inactive:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Military Unit Strays",
                    description="No stray players found.",
                    color=discord.Color.green(),
                )
            )
            return

        data = {"wrong_mu": wrong_mu, "no_mu": no_mu, "inactive": inactive}
        view = _StrayView(data)
        msg = await interaction.followup.send(
            embed=view._current_pages[0], view=view, wait=True
        )
        view.message = msg


async def setup(bot: commands.Bot):
    await bot.add_cog(MuStray(bot))
