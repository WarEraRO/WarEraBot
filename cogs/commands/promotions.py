import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timezone
from config import config
from utils.api import get_user, get_shared_session
from utils.computational import triangular
from utils.i18n import Translator, get_translator

_PAGE_SIZE = 15
ECONOMY_SKILLS = ["energy", "companies", "entrepreneurship", "production"]

# (key, color); titles are promotions.title_<key>
_FILTERS = [
    ("candidates",   discord.Color.green()),
    ("fight_issues", discord.Color.orange()),
    ("inactive",     discord.Color.dark_grey()),
    ("data_issues",  discord.Color.red()),
]


def _format_items(items: list, tr: Translator) -> list[str]:
    lines = []
    for it in items:
        if isinstance(it, tuple):
            if len(it) == 3:
                lines.append(tr("promotions.line", name=it[0], level=it[1], note=it[2]))
            elif len(it) == 2:
                lines.append(f"{it[0]} — {it[1]}")
            else:
                lines.append(str(it))
        else:
            lines.append(str(it))
    return lines


def _build_pages(items: list, title: str, color: discord.Color, tr: Translator) -> list[discord.Embed]:
    lines = _format_items(items, tr)
    if not lines:
        embed = discord.Embed(title=title, description=tr("promotions.empty_category"), color=color)
        embed.set_footer(text=tr("common.page_total", page=1, pages=1, total=0))
        return [embed]
    total = len(lines)
    total_pages = max(1, (total - 1) // _PAGE_SIZE + 1)
    pages = []
    for i in range(0, total, _PAGE_SIZE):
        chunk = lines[i : i + _PAGE_SIZE]
        embed = discord.Embed(title=title, color=color)
        embed.description = "\n".join(f"• {l}" for l in chunk)
        embed.set_footer(text=tr("common.page_total", page=i // _PAGE_SIZE + 1, pages=total_pages, total=total))
        pages.append(embed)
    return pages


class _PromotionView(discord.ui.View):
    def __init__(self, data: dict[str, list], tr: Translator, timeout: int = 180):
        super().__init__(timeout=timeout)
        self.message: discord.Message | None = None
        self.active_filter: str = "candidates"
        self.page_index: dict[str, int] = {key: 0 for key, *_ in _FILTERS}
        self._pages: dict[str, list[discord.Embed]] = {
            key: _build_pages(data[key], tr(f"promotions.title_{key}"), color, tr)
            for key, color in _FILTERS
        }
        self.prev_btn.label = tr("common.prev")
        self.next_btn.label = tr("common.next")
        self.btn_candidates.label = tr("promotions.button_candidates")
        self.btn_fight.label = tr("promotions.button_fight_issues")
        self.btn_inactive.label = tr("promotions.button_inactive")
        self.btn_data.label = tr("promotions.button_data_issues")
        self._sync_buttons()

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
        cur = self._current_page
        self.prev_btn.disabled = cur == 0
        self.next_btn.disabled = cur == last
        for btn in (self.btn_candidates, self.btn_fight, self.btn_inactive, self.btn_data):
            key = btn.custom_id
            btn.style = discord.ButtonStyle.success if key == self.active_filter else discord.ButtonStyle.secondary

    async def _refresh(self, interaction: discord.Interaction):
        self._sync_buttons()
        await interaction.response.edit_message(
            embed=self._current_pages[self._current_page], view=self
        )

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

    # ------------------------------------------------------------------ row 0: navigation

    @discord.ui.button(label="◀ Prev", style=discord.ButtonStyle.primary, row=0)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self._current_page = max(0, self._current_page - 1)
        await self._refresh(interaction)

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.primary, row=0)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self._current_page = min(len(self._current_pages) - 1, self._current_page + 1)
        await self._refresh(interaction)

    # ------------------------------------------------------------------ row 1: filters

    @discord.ui.button(label="Candidates", style=discord.ButtonStyle.success, custom_id="candidates", row=1)
    async def btn_candidates(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.active_filter = "candidates"
        await self._refresh(interaction)

    @discord.ui.button(label="Fight Issues", style=discord.ButtonStyle.secondary, custom_id="fight_issues", row=1)
    async def btn_fight(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.active_filter = "fight_issues"
        await self._refresh(interaction)

    @discord.ui.button(label="Inactive", style=discord.ButtonStyle.secondary, custom_id="inactive", row=1)
    async def btn_inactive(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.active_filter = "inactive"
        await self._refresh(interaction)

    @discord.ui.button(label="Data Issues", style=discord.ButtonStyle.secondary, custom_id="data_issues", row=1)
    async def btn_data(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.active_filter = "data_issues"
        await self._refresh(interaction)


class Promotions(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="promotions",
        description="Check newbie members for promotion eligibility and compliance.",
    )
    async def promotions(self, interaction: discord.Interaction):
        await interaction.response.defer()
        tr = await get_translator(interaction.guild_id)

        guild = interaction.guild or self.bot.get_guild(config["guild"])
        if guild is None:
            await interaction.followup.send(tr("common.guild_not_found"), ephemeral=True)
            return

        newbie_role = guild.get_role(config["roles"].get("newbie"))
        members = newbie_role.members if newbie_role else []

        candidates = []
        fight_issues = []
        inactive_candidates = []
        data_issues = []

        session = await get_shared_session()
        for member in members:
            try:
                user = await get_user(member.display_name, session)
                if not user:
                    data_issues.append((member.display_name, tr("promotions.no_api_data")))
                    continue

                leveling = user.get("leveling", {}) or {}
                level = leveling.get("level") if isinstance(leveling.get("level"), int) else None

                last_conn = None
                try:
                    last_conn_str = (user.get("dates") or {}).get("lastConnectionAt")
                    if last_conn_str:
                        last_conn = datetime.fromisoformat(last_conn_str.replace("Z", "+00:00"))
                    delta = datetime.now(timezone.utc) - last_conn
                    if delta.total_seconds() >= 5 * 24 * 3600:
                        inactive_candidates.append((member.display_name, level, tr("promotions.last_active", date=last_conn_str)))
                        continue
                except Exception:
                    last_conn = None

                if last_conn is None:
                    data_issues.append((member.display_name, level, tr("promotions.no_last_connection")))
                    continue

                economy_skill_points = 0
                fight_skill_points = 0
                skills = user.get("skills", {}) or {}
                for skill_name, skill_data in skills.items():
                    lvl = skill_data.get("level", 0)
                    if not lvl:
                        continue
                    if skill_name in ECONOMY_SKILLS:
                        economy_skill_points += triangular(lvl)
                    else:
                        fight_skill_points += triangular(lvl)

                total_skill_points = leveling.get("totalSkillPoints") or 0
                unspent_skill_points = leveling.get("availableSkillPoints", 0)
                percentage = (
                    ((economy_skill_points + unspent_skill_points) / total_skill_points) * 100
                    if total_skill_points else 0
                )
                is_economy = percentage > 50
                is_fighter_mode = not is_economy

                if level is not None and (level >= 20 or (level >= 15 and is_economy)):
                    candidates.append((member.display_name, level, tr("promotions.reason_economy") if is_economy else tr("promotions.reason_level")))

                if is_fighter_mode and level is not None and level <= 15:
                    fight_issues.append((member.display_name, level, tr("promotions.low_level_fighter")))

            except Exception:
                data_issues.append((getattr(member, "display_name", tr("common.unknown")), tr("promotions.error")))

        for lst in (candidates, fight_issues, inactive_candidates, data_issues):
            lst.sort(key=lambda x: (x[0] if isinstance(x, tuple) else x).lower())

        data = {
            "candidates": candidates,
            "fight_issues": fight_issues,
            "inactive": inactive_candidates,
            "data_issues": data_issues,
        }

        if not any(data.values()):
            await interaction.followup.send(
                embed=discord.Embed(
                    title=tr("promotions.title"),
                    description=tr("promotions.none_found"),
                    color=discord.Color.green(),
                )
            )
            return

        view = _PromotionView(data, tr)
        msg = await interaction.followup.send(
            embed=view._current_pages[0], view=view, wait=True
        )
        view.message = msg


async def setup(bot: commands.Bot):
    await bot.add_cog(Promotions(bot))
