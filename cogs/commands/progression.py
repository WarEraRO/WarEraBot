"""/progression: the next steps for a player's account, from their live WarEra data.

Companies follow BuhDeuce's "PERFECT ECONOMIC GUIDE" (https://app.warera.io/article/69998fd7d87267cb1de203d7):
economy builds go past the Romanian guide's 6 companies at Automated Engine 5 to 12 companies at Automated Engine 7
by level 50, while fight builds stop at the guide's war path of 6 companies at AE6. Production, Energy and
Entrepreneurship follow SKILL_ORDER, an add-only order computed with the economic-build-warera.netlify.app model;
the Companies skill is bought when the company plan needs it. Costs, caps and unlock levels come from gameConfig.
Inventory and mission progress are not readable with the API, so the plan never depends on them.
"""
import asyncio
import logging
import time
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

from cogs.commands.fight_wealth import _pack
from utils.api import get_game_config, get_market_prices, get_shared_session, get_user, get_user_companies, get_users_full
from utils.computational import is_economy_build
from utils.db import find_api_id_by_discord_id
from utils.i18n import Translator, get_translator

logger = logging.getLogger(__name__)

GAME_CONFIG_TTL = 3600
PROFILE_URL = "https://app.warera.io/user/{id}"
# the first companies feed the construction chain: concrete builds companies, steel upgrades them
STARTER_ORDER = ("limestone", "concrete", "iron", "steel")
# (companies, Automated Engine level) rungs, climbed in order (BuhDeuce's guide). Both paths share the start up to
# the Romanian guide's 6 companies at AE5. Economy builds then go to 12 companies (Companies skill 10) at AE7, both
# the game's maximum; fight builds stop at the war path's 6 companies at AE6, the minimum for fighting (user
# decision, 2026-10-25), because they would disable the companies above their cap.
_SHARED_LADDER = ((1, 3), (2, 3), (3, 3), (3, 4), (4, 4), (5, 4), (6, 4), (6, 5))
ECONOMY_LADDER = _SHARED_LADDER + ((10, 5), (10, 6), (12, 6), (12, 7))
WAR_LADDER = _SHARED_LADDER + ((6, 6),)
# the player level by which the economy goal should be reached (user decision, 2026-10-25)
GOAL_LEVEL = 50
# Production, Energy and Entrepreneurship one level at a time, best coins/day per skill point first, from the
# economic-build-warera.netlify.app model with its live inputs on 2026-10-25 (wage 0.15, production bonus 55%,
# iron 0.0976 per production point, tax 9%). Add-only, so following it never needs a skill reset; it stayed on
# average within about 2% of the calculator's best build for every budget. Regenerate with
# .claude/skills/warerabot-dev/scripts/skill_order.py.
SKILL_ORDER = (
    ("production", 1), ("energy", 1), ("production", 2), ("entrepreneurship", 1), ("energy", 2), ("production", 3),
    ("production", 4), ("energy", 3), ("entrepreneurship", 2), ("production", 5), ("energy", 4), ("production", 6),
    ("energy", 5), ("production", 7), ("entrepreneurship", 3), ("energy", 6), ("production", 8), ("energy", 7),
    ("production", 9), ("entrepreneurship", 4), ("production", 10), ("energy", 8), ("energy", 9), ("entrepreneurship", 5),
    ("energy", 10), ("entrepreneurship", 6), ("entrepreneurship", 7), ("entrepreneurship", 8), ("entrepreneurship", 9), ("entrepreneurship", 10),
)
ORDER_SKILLS = ("production", "energy", "entrepreneurship")
# a company this full gets a warning; a full storage stops its production
STORAGE_WARN_RATIO = 0.9


def _level_table(game_config: dict, section: str, name: str) -> dict:
    """gameConfig `<section>.<name>.levels`, keyed by level number as a string, or {} when missing."""
    return ((game_config.get(section) or {}).get(name) or {}).get("levels") or {}


def _ae(company: dict) -> int:
    return int((company.get("activeUpgradeLevels") or {}).get("automatedEngine") or 1)


def _skill_level(user: dict, skill: str) -> int:
    return int(((user.get("skills") or {}).get(skill) or {}).get("level") or 0)


def skill_points_to(game_config: dict, skill: str, current: int, target: int) -> int:
    """Skill points needed to raise `skill` from level `current` to `target`, from gameConfig `totalCost`."""
    if target <= current:
        return 0
    levels = _level_table(game_config, "skills", skill)
    return int((levels.get(str(target)) or {}).get("totalCost") or 0) - int((levels.get(str(current)) or {}).get("totalCost") or 0)


def skill_advice(user: dict, game_config: dict, reserved: int = 0) -> dict:
    """Walk SKILL_ORDER from the player's current levels and spend their unspent points along it.

    Steps the player already has (their skill is at or above the step's level) are skipped, so a player who
    deviated from the order simply continues from its first missing step, which is always one level above the
    skill's current level.

    Args:
        user: The player's user object (`skills`, `leveling`).
        game_config: gameConfig, for the cost of each skill level.
        reserved: Unspent points kept for something else first (the Companies skill for the next company).

    Returns:
        A dict with `levels` ({skill: current level} for ORDER_SKILLS), `available` (unspent points left after
        `reserved`), `spend` ((skill, level, points) steps the points pay for, in order) and `next`: the first
        step they can't pay for, as (skill, level, points), or None when every skill in the order is at 10.
    """
    available = max(0, int((user.get("leveling") or {}).get("availableSkillPoints") or 0) - reserved)
    levels = {skill: _skill_level(user, skill) for skill in ORDER_SKILLS}
    after = dict(levels)
    spend = []
    left = available
    for skill, level in SKILL_ORDER:
        if after[skill] >= level:
            continue
        points = skill_points_to(game_config, skill, after[skill], level)
        if points > left:
            return {"levels": levels, "available": available, "spend": spend, "next": (skill, level, points)}
        spend.append((skill, level, points))
        after[skill] = level
        left -= points
    return {"levels": levels, "available": available, "spend": spend, "next": None}


def ladder_for(user: dict) -> tuple[tuple[int, int], ...]:
    """WAR_LADDER for a fight build, ECONOMY_LADDER otherwise (no skill points counts as economy)."""
    return WAR_LADDER if is_economy_build(user) is False else ECONOMY_LADDER


def company_step(companies: list[dict], user: dict, game_config: dict, ladder: tuple[tuple[int, int], ...] = ECONOMY_LADDER) -> dict:
    """The next company action on the way up `ladder` (ECONOMY_LADDER or WAR_LADDER).

    Checked in order: a company producing something outside STARTER_ORDER while a starter item is still
    missing is converted; then the first rung not reached yet asks for a new company (or, at the company cap,
    for the Companies skill or the player level that unlocks it) or for the lowest Automated Engine to be
    upgraded.

    Returns:
        A dict with `action` ("convert", "build", "skill", "unlock", "upgrade" or "done") and, depending on
        it: `company` (the company to convert or upgrade), `item` (item to produce, None when free to
        choose), `number` (company number to build), `target` (AE, skill or player level), `points` (skill
        points) and `cost` ({item code: quantity} of construction materials).
    """
    count = len(companies)
    company_rules = game_config.get("company") or {}
    expected = STARTER_ORDER[:max(count, 1)]
    have = {company.get("itemCode") for company in companies}
    missing = next((item for item in expected if item not in have), None)
    if missing:
        off_plan = next((company for company in companies if company.get("itemCode") not in expected), None)
        if off_plan:
            return {
                "action": "convert",
                "company": off_plan,
                "item": missing,
                "cost": {"concrete": int(company_rules.get("changeItemCost") or 0)},
            }

    for wanted, ae in ladder:
        if count < wanted:
            companies_level = _skill_level(user, "companies")
            levels = _level_table(game_config, "skills", "companies")
            cap = int((levels.get(str(companies_level)) or {}).get("value") or companies_level + 2)
            if count >= cap:
                next_level = (levels.get(str(companies_level + 1)) or {})
                unlock = int(next_level.get("unlockAtLevel") or 0)
                if int((user.get("leveling") or {}).get("level") or 1) < unlock:
                    return {"action": "unlock", "target": unlock, "number": count + 1}
                return {
                    "action": "skill",
                    "target": companies_level + 1,
                    "points": int(next_level.get("cost") or companies_level + 1),
                    "number": count + 1,
                }
            # the k-th company costs k times the per-company increase in concrete (the free first one included)
            return {
                "action": "build",
                "number": count + 1,
                "item": STARTER_ORDER[count] if count < len(STARTER_ORDER) else None,
                "cost": {"concrete": int(company_rules.get("constructionCostIncreasePerCompany") or 0) * (count + 1)},
            }
        behind = sorted((company for company in companies if _ae(company) < ae), key=_ae)
        if behind:
            company = behind[0]
            levels = _level_table(game_config, "upgradesConfig", "automatedEngine")
            steel = sum(int((levels.get(str(level)) or {}).get("steelCost") or 0) for level in range(_ae(company) + 1, ae + 1))
            return {"action": "upgrade", "company": company, "target": ae, "cost": {"steel": steel}}
    return {"action": "done"}


def storage_alerts(companies: list[dict], game_config: dict) -> list[tuple[dict, float, int]]:
    """(company, stock, capacity) for each company at STORAGE_WARN_RATIO of its storage or full."""
    levels = _level_table(game_config, "upgradesConfig", "storage")
    alerts = []
    for company in companies:
        level = (company.get("activeUpgradeLevels") or {}).get("storage") or 1
        capacity = int(((levels.get(str(level)) or {}).get("stats") or {}).get("maxProduction") or 0)
        stock = float(company.get("production") or 0)
        if company.get("isFull") or (capacity and stock >= capacity * STORAGE_WARN_RATIO):
            alerts.append((company, stock, capacity))
    return alerts


def claimed_daily_reward(user: dict, now: datetime) -> bool | None:
    """Whether the daily login reward was claimed this game day (00:00 UTC rollover); None when unknown.

    Reads `dates.lastDailyCalendarClaimedAt`; `lastDailyRewardClaimedAt` stopped updating in August 2026
    [observed 2026-10-25].
    """
    claimed = (user.get("dates") or {}).get("lastDailyCalendarClaimedAt")
    if not claimed:
        return None
    try:
        claimed_at = datetime.fromisoformat(str(claimed).replace("Z", "+00:00"))
    except ValueError:
        return None
    return claimed_at.astimezone(timezone.utc).date() == now.astimezone(timezone.utc).date()


def _item(code: str | None, tr: Translator) -> str:
    """The translated name of an item code, or the code itself when it has no translation."""
    if not code:
        return tr("common.unknown")
    key = f"damage.products.{code}"
    label = tr(key)
    return code if label == key else label


def _cost_text(cost: dict, prices: dict, market_open: bool, tr: Translator) -> str:
    """'needs 150 Concrete (≈ $262)': the materials, priced at market when the player can use the market."""
    parts = [f"**{quantity:g} {_item(code, tr)}**" for code, quantity in cost.items() if quantity]
    if not parts:
        return ""
    text = tr("progression.needs", materials=" + ".join(parts))
    money = sum(quantity * float(prices[code]) for code, quantity in cost.items() if quantity and prices.get(code))
    if market_open and money:
        text += " " + tr("progression.market_value", money=f"{money:,.0f}")
    return text


def _step_text(step: dict, prices: dict, market_open: bool, tr: Translator) -> str:
    """The next company action as one or two lines."""
    action = step["action"]
    if action == "done":
        return tr("progression.step.done")
    if action == "unlock":
        return tr("progression.step.unlock", level=step["target"], number=step["number"])
    if action == "skill":
        return tr("progression.step.skill", level=step["target"], points=step["points"], number=step["number"])
    if action == "build":
        line = (
            tr("progression.step.build", number=step["number"], item=_item(step["item"], tr))
            if step["item"]
            else tr("progression.step.build_free", number=step["number"])
        )
    elif action == "convert":
        company = step["company"]
        line = tr(
            "progression.step.convert",
            company=discord.utils.escape_markdown(str(company.get("name") or tr("common.unknown"))),
            source=_item(company.get("itemCode"), tr),
            item=_item(step["item"], tr),
        )
    else:
        company = step["company"]
        line = tr(
            "progression.step.upgrade",
            company=discord.utils.escape_markdown(str(company.get("name") or tr("common.unknown"))),
            item=_item(company.get("itemCode"), tr),
            level=step["target"],
        )
    cost = _cost_text(step.get("cost") or {}, prices, market_open, tr)
    return f"{line}\n{cost}" if cost else line


def build_embed(user: dict, companies: list[dict], game_config: dict, prices: dict, now: datetime, tr: Translator) -> discord.Embed:
    """The progression embed: next company step, companies, skill points and the daily checklist.

    Args:
        user: The player's `user.getUserById` object.
        companies: The player's companies (`get_user_companies`).
        game_config: `gameConfig.getGameConfig`.
        prices: {item code: market price}; may be empty.
        now: Current time, for the daily reward check.
        tr: Translator for the server's language.
    """
    level = int((user.get("leveling") or {}).get("level") or 1)
    market_level = int((game_config.get("user") or {}).get("marketMinLevel") or 0)
    market_open = level >= market_level
    money = ((user.get("stats") or {}).get("wealth") or {}).get("money")
    economy = is_economy_build(user)

    embed = discord.Embed(title=tr("progression.title"), color=discord.Color.teal(), timestamp=now)
    embed.set_author(
        name=str(user.get("username") or tr("common.unknown")),
        icon_url=user.get("avatarUrl") or None,
        url=PROFILE_URL.format(id=user.get("_id")),
    )
    summary = tr("progression.summary", level=level, companies=len(companies))
    if money is not None:
        summary += " · " + tr("progression.money", money=f"{float(money):,.0f}")
    ladder = ladder_for(user)
    war = ladder is WAR_LADDER
    goal_key = "progression.goal_war" if war else "progression.goal"
    lines = [summary, tr(goal_key, companies=ladder[-1][0], ae=ladder[-1][1], level=GOAL_LEVEL)]
    if economy is False:
        lines.append(tr("progression.fight_build"))
    embed.description = "\n".join(lines)

    step = company_step(companies, user, game_config, ladder)
    step_text = tr("progression.step.done_war") if war and step["action"] == "done" else _step_text(step, prices, market_open, tr)
    embed.add_field(name=tr("progression.step_title"), value=step_text, inline=False)

    if companies:
        full = {id(company) for company, _, _ in storage_alerts(companies, game_config)}
        storage_levels = _level_table(game_config, "upgradesConfig", "storage")
        rows = []
        for company in companies:
            storage = (company.get("activeUpgradeLevels") or {}).get("storage") or 1
            capacity = int(((storage_levels.get(str(storage)) or {}).get("stats") or {}).get("maxProduction") or 0)
            stock = float(company.get("production") or 0)
            stock_text = f"{stock:,.0f}/{capacity:,}" if capacity else f"{stock:,.0f}"
            rows.append(f"`AE{_ae(company)}` {_item(company.get('itemCode'), tr)} · {'⚠️' if id(company) in full else '📦'} {stock_text}")
        for name, value in _pack(tr("progression.companies_title"), rows):
            embed.add_field(name=name, value=value, inline=False)

    # the Companies skill for the next company comes before the order
    reserved = step["points"] if step["action"] == "skill" else 0
    advice = skill_advice(user, game_config, reserved)
    skill_lines = [" · ".join(f"{tr(f'progression.skills.{skill}')} **{level}**" for skill, level in advice["levels"].items())]
    if reserved:
        skill_lines.append(tr("progression.companies_first", points=reserved, level=step["target"]))
    # everything payable now is spent at once, so each skill is shown as one raise to its last step
    merged: dict[str, list[int]] = {}
    for skill, level, points in advice["spend"]:
        merged[skill] = [level, merged.get(skill, [0, 0])[1] + points]
    for skill, (level, points) in merged.items():
        skill_lines.append(tr("progression.spend", points=points, skill=tr(f"progression.skills.{skill}"), target=level))
    if advice["next"]:
        skill, level, points = advice["next"]
        skill_lines.append(tr("progression.next", skill=tr(f"progression.skills.{skill}"), level=level, points=points))
        if not advice["spend"] and advice["available"]:
            skill_lines.append(tr("progression.save", points=advice["available"]))
    else:
        skill_lines.append(tr("progression.order_done"))
    embed.add_field(name=tr("progression.skills_title"), value="\n".join(skill_lines), inline=False)

    checklist = []
    if claimed_daily_reward(user, now) is False:
        checklist.append(tr("progression.check.daily_reward"))
    if not market_open:
        checklist.append(tr("progression.check.missions", level=market_level))
    if not user.get("company"):
        checklist.append(tr("progression.check.job"))
    for company, stock, capacity in storage_alerts(companies, game_config):
        checklist.append(
            tr(
                "progression.check.storage",
                company=discord.utils.escape_markdown(str(company.get("name") or tr("common.unknown"))),
                item=_item(company.get("itemCode"), tr),
                percent=round(stock / capacity * 100) if capacity else 100,
            )
        )
    if not user.get("mu"):
        checklist.append(tr("progression.check.mu"))
    if not user.get("party"):
        checklist.append(tr("progression.check.party"))
    # 12 full companies alone take more than one field
    for name, value in _pack(tr("progression.checklist_title"), checklist):
        embed.add_field(name=name, value=value, inline=False)

    embed.set_footer(text=tr("progression.footer"))
    return embed


async def resolve_player_id(interaction: discord.Interaction, player: str | None, session) -> str | None:
    """The WarEra id of `player` (exact username), or of the caller when no player is given.

    The caller is found by their Discord-id link in the database first, then by their server nickname,
    which the server keeps equal to the in-game username. Also used by /economy.
    """
    if player:
        user = await get_user(player.strip(), session)
        return str(user["_id"]) if user and user.get("_id") else None
    try:
        api_id = await asyncio.to_thread(find_api_id_by_discord_id, interaction.user.id)
    except Exception:
        logger.exception("Could not read the WarEra player linked to %s", interaction.user.id)
        api_id = None
    if api_id:
        return str(api_id)
    user = await get_user(interaction.user.display_name, session)
    return str(user["_id"]) if user and user.get("_id") else None


class Progression(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._game_config: dict | None = None
        self._game_config_at = 0.0

    async def _config(self, session) -> dict | None:
        """gameConfig, cached for GAME_CONFIG_TTL; the last good copy when a refresh fails."""
        if self._game_config is None or time.monotonic() - self._game_config_at > GAME_CONFIG_TTL:
            game_config = await get_game_config(session)
            if game_config:
                self._game_config, self._game_config_at = game_config, time.monotonic()
        return self._game_config

    @app_commands.command(name="progression", description="Show the next steps for your WarEra account: skill points, companies and daily checklist.")
    @app_commands.describe(player="WarEra username (default: you)")
    async def progression_command(self, interaction: discord.Interaction, player: str | None = None):
        await interaction.response.defer(ephemeral=True)
        tr = await get_translator(interaction.guild_id)
        session = await get_shared_session()

        player_id = await resolve_player_id(interaction, player, session)
        if not player_id:
            key = "progression.player_not_found" if player else "progression.self_not_found"
            await interaction.followup.send(tr(key, name=discord.utils.escape_markdown(player or "")), ephemeral=True)
            return

        users, companies, game_config, prices = await asyncio.gather(
            get_users_full([player_id], session),
            get_user_companies(player_id, session),
            self._config(session),
            get_market_prices(session),
        )
        user = users.get(player_id)
        if not user or companies is None or not game_config:
            await interaction.followup.send(tr("progression.unavailable"), ephemeral=True)
            return
        # get_market_prices returns the whole tRPC envelope
        price_map = ((prices or {}).get("result") or {}).get("data") if isinstance(prices, dict) else None
        embed = build_embed(user, companies, game_config, price_map or {}, datetime.now(timezone.utc), tr)
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    """Extension entry point for bot.load_extension."""
    await bot.add_cog(Progression(bot))
