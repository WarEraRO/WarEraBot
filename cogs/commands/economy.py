"""/economy: the best Production, Energy and Entrepreneurship build for a player, from live market data.

The income model is the one of economic-build-warera.netlify.app: coins per day = job + self-work, where
    job       = Energy actions/day x Production x wage per production point after tax
    self-work = Entrepreneurship actions/day x Production x (1 + company bonus) x value of a production point
and a bar skill gives value / regenDividedBy per hour, spent energyCostPerAction per action (gameConfig).

Unlike the site, the inputs are the player's: the wage is the best open job offer each candidate build qualifies
for (minimum Energy, Production and level, citizenship), and self-work is valued at the player's best company
(its production bonus, and its item's market price minus its inputs per production point). The skill points are
the player's total minus what the Companies skill needs for the chosen number of companies; Management and the
companies' Automated Engine output are not part of the model.
"""
import asyncio
import logging
import time
from datetime import datetime, timezone
from itertools import product

import discord
from discord import app_commands
from discord.ext import commands

from cogs.commands.progression import _item, _level_table, _skill_level, resolve_player_id
from utils.api import (
    get_game_config,
    get_market_prices,
    get_production_bonuses,
    get_shared_session,
    get_user_companies,
    get_users_full,
    get_work_offers,
)
from utils.i18n import Translator, get_translator

logger = logging.getLogger(__name__)

GAME_CONFIG_TTL = 3600
BUILD_SKILLS = ("production", "energy", "entrepreneurship")
MAX_SKILL_LEVEL = 10
# best build plus this many runners-up
ALTERNATIVES = 3


def skill_value(game_config: dict, skill: str, level: int) -> float:
    """The skill's value at `level` (gameConfig `skills.<skill>.levels[level].value`)."""
    return float((_level_table(game_config, "skills", skill).get(str(level)) or {}).get("value") or 0)


def skill_total_cost(game_config: dict, skill: str, level: int) -> int:
    """Skill points that levels 1..`level` of `skill` cost together (gameConfig `totalCost`)."""
    return int((_level_table(game_config, "skills", skill).get(str(level)) or {}).get("totalCost") or 0)


def actions_per_day(game_config: dict, bar_value: float) -> float:
    """Work actions a bar (Energy or Entrepreneurship) of `bar_value` refills per day."""
    user_rules = game_config.get("user") or {}
    regen_divisor = float(user_rules.get("regenDividedBy") or 10)
    cost_per_action = float(user_rules.get("energyCostPerAction") or 10)
    return bar_value / regen_divisor * 24 / cost_per_action


def best_offer(offers: list[dict], energy: float, production: float, level: int, country: str | None, user_id: str) -> dict | None:
    """The best-paid open offer (after tax) a worker with these skill values can take, or None.

    Offers of the player's own companies and offers restricted to another citizenship are skipped.
    """
    eligible = [
        offer
        for offer in offers
        if (offer.get("quantity") or 0) > 0
        and str(offer.get("user")) != user_id
        and (not offer.get("citizenship") or offer.get("citizenship") == country)
        and (offer.get("minEnergy") or 0) <= energy
        and (offer.get("minProduction") or 0) <= production
        and (offer.get("minLevel") or 0) <= level
    ]
    return max(eligible, key=lambda offer: float(offer.get("wageAfterTax") or offer.get("wage") or 0), default=None)


def point_value(item_code: str, prices: dict, game_config: dict) -> float | None:
    """Coins one production point of `item_code` is worth: its price minus its inputs' prices, per point.

    None when the item or one of its inputs has no market price.
    """
    item = (game_config.get("items") or {}).get(item_code) or {}
    points = float(item.get("productionPoints") or 0)
    if not points or prices.get(item_code) is None:
        return None
    inputs = 0.0
    for input_code, quantity in (item.get("productionNeeds") or {}).items():
        if prices.get(input_code) is None:
            return None
        inputs += float(quantity) * float(prices[input_code])
    return (float(prices[item_code]) - inputs) / points


def best_self_work(companies: list[dict], bonuses: dict, prices: dict, game_config: dict) -> dict | None:
    """The company whose self-work pays most per production point, or None when no company can be valued.

    Returns:
        {"company", "bonus" (percent), "point_value" (coins per point before the bonus), "per_point" (with it)}.
    """
    best = None
    for company in companies:
        value = point_value(str(company.get("itemCode")), prices, game_config)
        if value is None:
            continue
        bonus = float((bonuses.get(str(company.get("_id"))) or {}).get("total") or 0)
        per_point = max(0.0, value) * (1 + bonus / 100)
        if best is None or per_point > best["per_point"]:
            best = {"company": company, "bonus": bonus, "point_value": value, "per_point": per_point}
    return best


def build_income(levels: dict, offers: list[dict], self_work: dict | None, user: dict, game_config: dict) -> dict:
    """Coins per day of a build {skill: level}: job, self-work, total and the job offer used."""
    production = skill_value(game_config, "production", levels["production"])
    energy = skill_value(game_config, "energy", levels["energy"])
    entrepreneurship = skill_value(game_config, "entrepreneurship", levels["entrepreneurship"])
    offer = best_offer(
        offers,
        energy,
        production,
        int((user.get("leveling") or {}).get("level") or 1),
        user.get("country"),
        str(user.get("_id")),
    )
    wage = float(offer.get("wageAfterTax") or offer.get("wage") or 0) if offer else 0.0
    job = actions_per_day(game_config, energy) * production * wage
    own = actions_per_day(game_config, entrepreneurship) * production * self_work["per_point"] if self_work else 0.0
    return {"job": job, "self": own, "total": job + own, "offer": offer}


def best_builds(budget: int, offers: list[dict], self_work: dict | None, user: dict, game_config: dict, count: int = 1 + ALTERNATIVES) -> list[dict]:
    """The `count` best builds that fit `budget` skill points, best first.

    Every combination of levels 0..MAX_SKILL_LEVEL is tried, as the calculator does; ties go to the cheaper build.

    Returns:
        Dicts with `levels` ({skill: level}), `points` (skill points used) and the `build_income` fields.
    """
    builds = []
    for combo in product(range(MAX_SKILL_LEVEL + 1), repeat=len(BUILD_SKILLS)):
        levels = dict(zip(BUILD_SKILLS, combo))
        points = sum(skill_total_cost(game_config, skill, level) for skill, level in levels.items())
        if points > budget:
            continue
        builds.append({"levels": levels, "points": points, **build_income(levels, offers, self_work, user, game_config)})
    builds.sort(key=lambda build: (-build["total"], build["points"]))
    return builds[:count]


def _levels_text(levels: dict, tr: Translator) -> str:
    return " · ".join(f"{tr(f'progression.skills.{skill}')} **{level}**" for skill, level in levels.items())


def build_embed(
    user: dict,
    companies_level: int,
    budget: int,
    builds: list[dict],
    current: dict,
    self_work: dict | None,
    game_config: dict,
    now: datetime,
    tr: Translator,
) -> discord.Embed:
    """The /economy embed: best build, the player's build now and how to switch, runners-up and market inputs.

    Args:
        user: The player's `user.getUserById` object.
        companies_level: The Companies skill level the budget keeps points for.
        budget: Skill points left for BUILD_SKILLS.
        builds: `best_builds` output, best first (never empty: the all-zero build always fits).
        current: `build_income` of the player's current levels, plus `levels`.
        self_work: `best_self_work` output, or None.
        game_config: gameConfig.
        now: Time of the market data.
        tr: Translator for the server's language.
    """
    leveling = user.get("leveling") or {}
    best = builds[0]
    companies_cap = int(skill_value(game_config, "companies", companies_level))
    embed = discord.Embed(title=tr("economy.title"), color=discord.Color.gold(), timestamp=now)
    embed.set_author(name=str(user.get("username") or tr("common.unknown")), icon_url=user.get("avatarUrl") or None)
    embed.description = tr(
        "economy.budget",
        level=int(leveling.get("level") or 1),
        total=int(leveling.get("totalSkillPoints") or 0),
        companies=companies_cap,
        companies_points=skill_total_cost(game_config, "companies", companies_level),
        budget=budget,
    )

    embed.add_field(
        name=tr("economy.best_title"),
        value="\n".join(
            [
                _levels_text(best["levels"], tr) + " · " + tr("economy.points", points=best["points"]),
                tr("economy.income", job=f"{best['job']:,.1f}", own=f"{best['self']:,.1f}", total=f"{best['total']:,.1f}"),
            ]
        ),
        inline=False,
    )

    now_lines = [
        _levels_text(current["levels"], tr) + " · " + tr("economy.per_day", total=f"{current['total']:,.1f}"),
    ]
    gain = best["total"] - current["total"]
    current_points = sum(skill_total_cost(game_config, skill, level) for skill, level in current["levels"].items())
    # points the best build still needs on top of the current one, when no skill has to go down
    missing = sum(
        skill_total_cost(game_config, skill, best["levels"][skill]) - skill_total_cost(game_config, skill, current["levels"][skill])
        for skill in BUILD_SKILLS
    )
    only_up = all(current["levels"][skill] <= best["levels"][skill] for skill in BUILD_SKILLS)
    available = int(leveling.get("availableSkillPoints") or 0)
    user_rules = game_config.get("user") or {}
    cooldown = int(user_rules.get("resetSkillDaysCooldown") or 0)
    free_resets = int(leveling.get("freeReset") or 0)
    # a reset refunds every allocated point, combat skills included, at a cost per point
    reset_cost = float(user_rules.get("resetSkillsCostPerPoint") or 0) * int(leveling.get("spentSkillPoints") or 0)
    if current_points > budget:
        now_lines.append(
            tr("economy.over_budget", points=current_points, budget=budget, companies=companies_cap, change=f"{gain:+,.1f}")
        )
        now_lines.append(
            tr("economy.reset_cost_free", free=free_resets, days=cooldown)
            if free_resets > 0
            else tr("economy.reset_cost_paid", cost=f"{reset_cost:,.0f}", days=cooldown)
        )
    elif all(current["levels"][skill] == best["levels"][skill] for skill in BUILD_SKILLS) or gain <= 0.05:
        now_lines.append(tr("economy.already_best"))
    elif only_up and missing <= available:
        now_lines.append(tr("economy.add_points", gain=f"{gain:,.1f}", points=missing, available=available))
    elif free_resets > 0:
        now_lines.append(tr("economy.reset_free", gain=f"{gain:,.1f}", free=free_resets, days=cooldown))
    else:
        now_lines.append(
            tr("economy.reset_paid", gain=f"{gain:,.1f}", cost=f"{reset_cost:,.0f}", payback=f"{reset_cost / gain:,.1f}", days=cooldown)
        )
    embed.add_field(name=tr("economy.now_title"), value="\n".join(now_lines), inline=False)

    if len(builds) > 1:
        lines = [
            f"`{index}.` " + _levels_text(build["levels"], tr) + " · " + tr("economy.points", points=build["points"])
            + " · " + tr("economy.per_day", total=f"{build['total']:,.1f}")
            for index, build in enumerate(builds[1:], start=2)
        ]
        embed.add_field(name=tr("economy.alternatives_title"), value="\n".join(lines), inline=False)

    inputs = []
    offer = best["offer"]
    if offer:
        wage = f"{float(offer.get('wageAfterTax') or offer.get('wage') or 0):.3f}"
        if offer.get("minEnergy") or offer.get("minProduction"):
            inputs.append(
                tr(
                    "economy.job_input",
                    wage=wage,
                    energy=int(offer.get("minEnergy") or 0),
                    production=int(offer.get("minProduction") or 0),
                )
            )
        else:
            inputs.append(tr("economy.job_input_open", wage=wage))
    else:
        inputs.append(tr("economy.no_job"))
    if self_work:
        inputs.append(
            tr(
                "economy.self_input",
                company=discord.utils.escape_markdown(str(self_work["company"].get("name") or tr("common.unknown"))),
                item=_item(self_work["company"].get("itemCode"), tr),
                bonus=f"{self_work['bonus']:g}",
                value=f"{self_work['point_value']:.3f}",
            )
        )
    else:
        inputs.append(tr("economy.no_self_work"))
    embed.add_field(name=tr("economy.inputs_title"), value="\n".join(inputs), inline=False)
    embed.set_footer(text=tr("economy.footer"))
    return embed


class Economy(commands.Cog):
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

    @app_commands.command(name="economy", description="Find the best economy build (Production, Energy, Entrepreneurship) from today's market.")
    @app_commands.describe(
        companies="Number of companies to keep Companies skill points for (default: your current limit)",
        player="WarEra username (default: you)",
    )
    async def economy_command(
        self,
        interaction: discord.Interaction,
        companies: app_commands.Range[int, 2, 12] | None = None,
        player: str | None = None,
    ):
        await interaction.response.defer(ephemeral=True)
        tr = await get_translator(interaction.guild_id)
        session = await get_shared_session()

        player_id = await resolve_player_id(interaction, player, session)
        if not player_id:
            key = "progression.player_not_found" if player else "progression.self_not_found"
            await interaction.followup.send(tr(key, name=discord.utils.escape_markdown(player or "")), ephemeral=True)
            return

        users, owned, game_config, prices, offers = await asyncio.gather(
            get_users_full([player_id], session),
            get_user_companies(player_id, session),
            self._config(session),
            get_market_prices(session),
            get_work_offers(session),
        )
        user = users.get(player_id)
        # get_market_prices returns the whole tRPC envelope
        price_map = ((prices or {}).get("result") or {}).get("data") if isinstance(prices, dict) else None
        if not user or owned is None or not game_config or not price_map or offers is None:
            await interaction.followup.send(tr("progression.unavailable"), ephemeral=True)
            return
        # company.getProductionBonus is not in the public OpenAPI spec (see utils/api.py)
        bonuses = await get_production_bonuses([str(company.get("_id")) for company in owned], session)

        # Companies skill level n allows n + 2 companies (gameConfig value)
        companies_level = companies - 2 if companies is not None else _skill_level(user, "companies")
        budget = int((user.get("leveling") or {}).get("totalSkillPoints") or 0) - skill_total_cost(game_config, "companies", companies_level)
        if budget < 0:
            await interaction.followup.send(tr("economy.not_enough_points", companies=companies), ephemeral=True)
            return

        self_work = best_self_work(owned, bonuses, price_map, game_config)
        builds = best_builds(budget, offers, self_work, user, game_config)
        current_levels = {skill: min(MAX_SKILL_LEVEL, _skill_level(user, skill)) for skill in BUILD_SKILLS}
        current = {"levels": current_levels, **build_income(current_levels, offers, self_work, user, game_config)}
        embed = build_embed(user, companies_level, budget, builds, current, self_work, game_config, datetime.now(timezone.utc), tr)
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    """Extension entry point for bot.load_extension."""
    await bot.add_cog(Economy(bot))
