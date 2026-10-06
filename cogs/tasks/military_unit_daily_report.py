import asyncio
import logging
import math
from collections import Counter
from datetime import datetime, time as dt_time, timedelta, timezone

import discord
from discord.ext import commands, tasks

from config import config
from utils.api import (
    get_active_battles,
    get_all_countries,
    get_game_config,
    get_military_unit,
    get_mu_members,
    get_shared_session,
    get_user_info,
)
from utils.common import country_with_flag
from utils.computational import is_economy_build

logger = logging.getLogger(__name__)

# the game day and the daily missions reset at 00:00 UTC (gameConfig.getDates.nextDayAt), so the report runs just before
REPORT_TIME = dt_time(hour=23, minute=30, tzinfo=timezone.utc)
# MUs with less weekly damage than this get no report
MIN_REPORT_DAMAGE = 5_000_000
# item code of the pill, as listed in user.buffs.buffCodes / debuffCodes and gameConfig.items
PILL_CODE = "cocain"
# fallbacks for gameConfig items.cocain.flatStats.buffDurationHours / debuffDurationHours and user.resetSkillDaysCooldown
DEFAULT_PILL_BUFF_HOURS = 8
DEFAULT_PILL_DEBUFF_HOURS = 15.5
DEFAULT_SKILL_RESET_COOLDOWN_DAYS = 7
OFFLINE_AFTER = timedelta(hours=24)
RESKILL_WINDOW = timedelta(hours=24)
# share of fighters that should be able to pill at the suggested shared pill time
SHARED_WINDOW_PERCENT = 80
USER_CONCURRENCY = 5
# an MU has at most 25 members, so lists normally show everyone
NAMES_SHOWN = 25
ORDERS_SHOWN = 3
EMBED_FIELD_VALUE_LIMIT = 1024
# per embed, kept below Discord's 6000 so each part stays readable; longer reports are split into more embeds
EMBED_TOTAL_LIMIT = 4000
# Discord caps a message at 10 embeds and 6000 characters across all of them
MESSAGE_EMBED_LIMIT = 10
MESSAGE_TOTAL_LIMIT = 6000
BATTLE_LINK = "https://app.warera.io/battle/{}"


def _parse_iso(value) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _week_start(now: datetime) -> datetime:
    monday = now - timedelta(days=now.weekday())
    return monday.replace(hour=0, minute=0, second=0, microsecond=0)


def _fmt_short(value) -> str:
    """Compact damage figures: 950, 12.3K, 4.5M."""
    value = value or 0
    for divisor, suffix in ((1_000_000_000, "B"), (1_000_000, "M"), (1_000, "K")):
        if abs(value) >= divisor:
            return f"{value / divisor:.1f}{suffix}"
    return f"{round(value)}"


def _truncate(text: str) -> str:
    if len(text) <= EMBED_FIELD_VALUE_LIMIT:
        return text
    return text[: EMBED_FIELD_VALUE_LIMIT - 1] + "…"


def _hour_buckets(times: list[datetime], now: datetime | None = None) -> str:
    """`07h ×2 · 18h ×5`, sorted by time; times not after `now` are grouped as `now`, the first hour after
    `now`'s day is marked `tmrw`."""
    ready_now = sum(1 for value in times if now is not None and value <= now)
    buckets = Counter(
        value.replace(minute=0, second=0, microsecond=0) for value in times if now is None or value > now
    )
    parts = [f"now ×{ready_now}"] if ready_now else []
    marked = False
    for hour, count in sorted(buckets.items()):
        prefix = ""
        if now is not None and not marked and hour.date() > now.date():
            prefix, marked = "tmrw ", True
        parts.append(f"{prefix}{hour:%H}h ×{count}")
    return " · ".join(parts)


def _pill_settings(game_config: dict | None) -> dict:
    game_config = game_config or {}
    pill_stats = (((game_config.get("items") or {}).get(PILL_CODE) or {}).get("flatStats")) or {}
    return {
        "buff": timedelta(hours=float(pill_stats.get("buffDurationHours") or DEFAULT_PILL_BUFF_HOURS)),
        "debuff": timedelta(hours=float(pill_stats.get("debuffDurationHours") or DEFAULT_PILL_DEBUFF_HOURS)),
        "reset_cooldown": timedelta(
            days=float((game_config.get("user") or {}).get("resetSkillDaysCooldown") or DEFAULT_SKILL_RESET_COOLDOWN_DAYS)
        ),
    }


class MilitaryUnitDailyReportJob(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.mu_daily_report.start()

    def cog_unload(self):
        self.mu_daily_report.cancel()

    @tasks.loop(time=REPORT_TIME)
    async def mu_daily_report(self):
        # only MUs with a leaderId get a report, sent to the leader by DM
        units = {
            str(unit["id"]): unit
            for unit in config.get("military_units", [])
            if unit.get("id") and unit.get("leaderId")
        }
        if not units:
            return

        session = await get_shared_session()
        now = datetime.now(timezone.utc)
        game_config, battles, countries = await asyncio.gather(
            get_game_config(session),
            get_active_battles(session),
            get_all_countries(session),
        )
        settings = _pill_settings(game_config)
        country_names = {
            str(country.get("_id")): str(country.get("name"))
            for country in countries or []
            if country.get("_id") and country.get("name")
        }

        for mu_id, unit in units.items():
            try:
                embeds = await self._build_embeds(mu_id, unit, session, now, settings, battles, country_names)
                if not embeds:
                    continue
                leader = await self._leader(unit["leaderId"])
                if leader is None:
                    logger.warning("Leader %s of MU %s not found", unit["leaderId"], unit.get("friendlyName"))
                    continue
                for message_embeds in self._messages(embeds):
                    await leader.send(embeds=message_embeds)
            except discord.Forbidden:
                logger.warning("Cannot DM leader %s of MU %s (DMs closed?)", unit["leaderId"], unit.get("friendlyName"))
            except discord.DiscordException:
                logger.exception("Failed to send daily report for MU %s", unit.get("friendlyName"))

    @mu_daily_report.before_loop
    async def before_mu_daily_report(self):
        await self.bot.wait_until_ready()

    async def _leader(self, leader_id: int) -> discord.User | None:
        user = self.bot.get_user(int(leader_id))
        if user is not None:
            return user
        try:
            return await self.bot.fetch_user(int(leader_id))
        except discord.HTTPException:
            return None

    async def _fetch_user(self, user_id: str, session, semaphore: asyncio.Semaphore) -> dict | None:
        async with semaphore:
            return await get_user_info(user_id, session)

    def _pill_state(self, user: dict, now: datetime, settings: dict) -> dict:
        """Pill phase of a user: {"phase": "buff" | "debuff" | None, "pilled_at", "ready_at"}.

        The pill time is derived from when the buff or debuff ends, using the durations from gameConfig.
        """
        buffs = user.get("buffs") or {}
        # older responses had no codes, so an end time without codes is taken as a pill
        buff_end = _parse_iso(buffs.get("buffEndAt")) if PILL_CODE in (buffs.get("buffCodes") or [PILL_CODE]) else None
        debuff_end = _parse_iso(buffs.get("debuffEndAt")) if PILL_CODE in (buffs.get("debuffCodes") or [PILL_CODE]) else None
        if buff_end and buff_end > now:
            return {"phase": "buff", "pilled_at": buff_end - settings["buff"], "ready_at": buff_end + settings["debuff"]}
        if debuff_end and debuff_end > now:
            return {
                "phase": "debuff",
                "pilled_at": debuff_end - settings["debuff"] - settings["buff"],
                "ready_at": debuff_end,
            }
        return {"phase": None, "pilled_at": None, "ready_at": now}

    async def _build_embeds(
        self,
        mu_id: str,
        unit: dict,
        session,
        now: datetime,
        settings: dict,
        battles: list[dict] | None,
        country_names: dict[str, str],
    ) -> list[discord.Embed] | None:
        """The MU's daily report as one or more embeds, or None when it has no members or dealt less than
        MIN_REPORT_DAMAGE this week."""
        military_unit, members = await asyncio.gather(
            get_military_unit(mu_id, session),
            get_mu_members(mu_id, session),
        )
        if members is None:
            logger.warning("Skipping daily report for MU %s: members could not be fetched", unit.get("friendlyName"))
            return None
        if not members:
            logger.info("Skipping daily report for MU %s: no members", unit.get("friendlyName"))
            return None
        military_unit = military_unit if isinstance(military_unit, dict) else {}
        mu_name = military_unit.get("name") or unit.get("friendlyName") or mu_id

        weekly = (military_unit.get("rankings") or {}).get("muWeeklyDamages") or {}
        weekly_damage = weekly.get("value")
        if weekly_damage is None:
            weekly_damage = sum(member.get("weeklyDamagesCount") or 0 for member in members)
        if weekly_damage < MIN_REPORT_DAMAGE:
            logger.info("Skipping daily report for MU %s: %s weekly damage", mu_name, _fmt_short(weekly_damage))
            return None

        semaphore = asyncio.Semaphore(USER_CONCURRENCY)
        users = await asyncio.gather(
            *(self._fetch_user(str(member.get("user")), session, semaphore) for member in members)
        )
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        rows = []
        for member, user in zip(members, users):
            if not user:
                continue
            dates = user.get("dates") or {}
            rows.append({
                "name": discord.utils.escape_markdown(str(user.get("username") or "unknown")),
                "weekly": member.get("weeklyDamagesCount") or 0,
                "economy": is_economy_build(user),
                "pill": self._pill_state(user, now, settings),
                "skills": user.get("skills") or {},
                "last_reset_at": _parse_iso(dates.get("lastSkillsResetAt")),
                "last_help_at": _parse_iso(dates.get("lastHelpAskedAt")),
                "last_seen_at": _parse_iso(dates.get("lastConnectionAt")),
            })
        missing = len(members) - len(rows)
        # biggest hitters first, so the most impactful names are never cut from a list
        rows.sort(key=lambda row: row["weekly"], reverse=True)
        fighters = [row for row in rows if row["economy"] is False]

        # pills
        pilled_today = [row for row in fighters if row["pill"]["pilled_at"] and row["pill"]["pilled_at"] >= day_start]
        buffed = [row for row in pilled_today if row["pill"]["phase"] == "buff"]
        no_pill = [row for row in fighters if row["pill"]["phase"] is None]
        # still in the debuff of a pill taken before today (only when the report runs early in the day)
        cooling_down = [row for row in fighters if row["pill"]["phase"] == "debuff" and row not in pilled_today]

        # skill resets in the last 24h, for all members
        reskilled = sorted(
            (row for row in rows if row["last_reset_at"] and row["last_reset_at"] >= now - RESKILL_WINDOW),
            key=lambda row: row["last_reset_at"],
        )

        # MU orders on active battles
        orders = [
            (battle, side)
            for battle in battles or []
            for side in ("attacker", "defender")
            if mu_id in [str(item) for item in ((battle.get(side) or {}).get("muOrders") or [])]
        ]

        no_help = [row for row in fighters if not row["last_help_at"] or row["last_help_at"] < day_start]
        # regen is lost while a bar is full; fighters in debuff are expected to hold off
        full_bars = []
        for row in fighters:
            if row["pill"]["phase"] == "debuff":
                continue
            bars = [
                label for skill, label in (("health", "HP"), ("hunger", "food"))
                if (row["skills"].get(skill) or {}).get("total")
                and (row["skills"][skill].get("currentBarValue") or 0) >= row["skills"][skill]["total"]
            ]
            if bars:
                full_bars.append((row, bars))
        offline = [row for row in rows if row["last_seen_at"] and now - row["last_seen_at"] >= OFFLINE_AFTER]
        no_damage = [row for row in fighters if not row["weekly"] and row not in offline]

        # topics in report order; each is a list of (name, value, inline) fields that stays in one embed when it fits
        pills_text = (
            f"🔥 **{len(buffed)}** buffed now\n"
            f"🟢 **{len(pilled_today) - len(buffed)}** pilled earlier today (now in debuff)\n"
            f"⚪ **{len(no_pill)}** no pill today"
        )
        if cooling_down:
            pills_text += f"\n⏳ {len(cooling_down)} still in debuff from yesterday"
        pills = [(f"💊 Pills · {len(fighters)} fighters", pills_text, False)]
        if no_pill:
            pills.append((
                f"⚪ No pill today ({len(no_pill)})",
                self._name_list([f"{row['name']} ({_fmt_short(row['weekly'])})" for row in no_pill]),
                False,
            ))
        if pilled_today:
            pills.append(("🕒 Pill times today (UTC)", _hour_buckets([row["pill"]["pilled_at"] for row in pilled_today]), True))
        if fighters:
            pills.append(("📅 Next pill ready (UTC)", _hour_buckets([row["pill"]["ready_at"] for row in fighters], now), True))

        orders_and_skills = [("📌 MU orders now", self._orders_text(orders, battles, country_names), False)]
        if reskilled:
            lines = [
                f"{row['name']} → {'Economy' if row['economy'] else 'Fight'} · "
                f"next reset {row['last_reset_at'] + settings['reset_cooldown']:%b %d %H:%M}"
                for row in reskilled
            ]
            orders_and_skills.append((f"🔄 Skill resets, last 24h ({len(reskilled)})", self._name_list(lines, separator="\n"), False))

        tips = self._insights(fighters, no_pill, pilled_today, reskilled, orders, battles, no_help, now, settings)
        advice = [("💡 For tomorrow", "\n".join(f"• {tip}" for tip in tips), False)] if tips else []

        readiness = []
        if no_help:
            readiness.append((f"🤝 No MU help asked today ({len(no_help)})", self._name_list([row["name"] for row in no_help]), False))
        if full_bars:
            readiness.append((
                f"🔋 Full bars, regen lost ({len(full_bars)})",
                self._name_list([f"{row['name']} ({', '.join(bars)})" for row, bars in full_bars]),
                False,
            ))
        quiet = [f"{row['name']} ({(now - row['last_seen_at']).days}d offline)" for row in offline]
        quiet += [f"{row['name']} (0 dmg this week)" for row in no_damage]
        if quiet:
            readiness.append((f"💤 Quiet ({len(quiet)})", self._name_list(quiet), False))

        days = (now - _week_start(now)).days + 1
        description = f"Game day **{now:%a %b %d}** · resets 00:00 UTC\n⚔️ Week **{_fmt_short(weekly_damage)}**"
        if weekly.get("rank"):
            description += f" · rank #{weekly['rank']}"
        description += (
            f" · ~{_fmt_short(weekly_damage / days)}/day\n"
            f"👥 {len(fighters)} fighters · {len(rows) - len(fighters)} economy · {len(members)} members"
        )
        footer = "Fighters = members with a fight skill build · pill state read at report time"
        if missing:
            footer = f"⚠️ {missing} member(s) could not be fetched · " + footer

        author = f"🗓️ {mu_name} · Daily Report"
        icon_url = military_unit.get("avatarUrl") or None
        pages = self._paginate([pills, orders_and_skills, advice, readiness], author, description, footer)
        embeds = []
        for index, fields in enumerate(pages):
            embed = discord.Embed(
                description=description if index == 0 else None,
                color=discord.Color.blue(),
                timestamp=now if index == len(pages) - 1 else None,
            )
            embed.set_author(name=author + (f" ({index + 1}/{len(pages)})" if len(pages) > 1 else ""), icon_url=icon_url)
            for name, value, inline in fields:
                embed.add_field(name=name, value=_truncate(value) or "—", inline=inline)
            if index == len(pages) - 1:
                embed.set_footer(text=footer)
            embeds.append(embed)
        if len(embeds) > 1:
            logger.info("Daily report for MU %s split into %d embeds", mu_name, len(embeds))
        return embeds

    def _paginate(
        self,
        topics: list[list[tuple[str, str, bool]]],
        author: str,
        description: str,
        footer: str,
    ) -> list[list[tuple[str, str, bool]]]:
        """Split the topics' fields into pages that each fit in EMBED_TOTAL_LIMIT characters.

        A topic moves to a new page when it does not fit on the current one; only a topic too big for a
        page of its own is split between pages.
        """

        def fits(fields: list[tuple[str, str, bool]], first: bool) -> bool:
            # measured with the description on the first page, and the footer and a page counter on every page
            embed = discord.Embed(description=description if first else None)
            embed.set_author(name=author + " (10/10)")
            for name, value, inline in fields:
                embed.add_field(name=name, value=_truncate(value) or "—", inline=inline)
            embed.set_footer(text=footer)
            return len(embed) <= EMBED_TOTAL_LIMIT

        pages: list[list[tuple[str, str, bool]]] = [[]]
        for topic in topics:
            if not topic:
                continue
            if fits(pages[-1] + topic, first=len(pages) == 1):
                pages[-1] += topic
            elif pages[-1] and fits(topic, first=False):
                pages.append(list(topic))
            else:
                for field in topic:
                    if pages[-1] and not fits(pages[-1] + [field], first=len(pages) == 1):
                        pages.append([])
                    pages[-1].append(field)
        return pages

    def _messages(self, embeds: list[discord.Embed]) -> list[list[discord.Embed]]:
        """Group the embeds into as few messages as Discord's per-message limits allow."""
        messages: list[list[discord.Embed]] = []
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

    def _name_list(self, entries: list[str], separator: str = ", ") -> str:
        shown = separator.join(entries[:NAMES_SHOWN])
        if len(entries) > NAMES_SHOWN:
            shown += f"{separator}and {len(entries) - NAMES_SHOWN} more"
        return shown

    def _orders_text(self, orders: list[tuple[dict, str]], battles: list[dict] | None, country_names: dict[str, str]) -> str:
        if battles is None:
            return "unavailable"
        if not orders:
            return "No active MU order"
        lines = []
        for battle, side in orders[:ORDERS_SHOWN]:
            attacker = str((battle.get("attacker") or {}).get("country") or "")
            defender = str((battle.get("defender") or {}).get("country") or "")
            # tournament battles have no side country
            if attacker and defender:
                title = (
                    f"{country_with_flag(country_names.get(attacker), left=True)} vs "
                    f"{country_with_flag(country_names.get(defender), left=False)}"
                )
                fighting_for = country_with_flag(country_names.get(attacker if side == "attacker" else defender), left=True)
            else:
                title, fighting_for = "Tournament battle", side
            lines.append(f"[{title}]({BATTLE_LINK.format(battle.get('_id'))}) · for {fighting_for}")
        if len(orders) > ORDERS_SHOWN:
            lines.append(f"and {len(orders) - ORDERS_SHOWN} more")
        return "\n".join(lines)

    def _insights(
        self,
        fighters: list[dict],
        no_pill: list[dict],
        pilled_today: list[dict],
        reskilled: list[dict],
        orders: list[tuple[dict, str]],
        battles: list[dict] | None,
        no_help: list[dict],
        now: datetime,
        settings: dict,
    ) -> list[str]:
        tips = []
        if battles is not None and not orders:
            tips.append("No MU order is active; set one so fighters know where to pill and hit tomorrow.")
        elif orders and no_pill:
            tips.append(f"{len(no_pill)} fighter(s) did not pill today while the MU had an active order.")
        if len(fighters) >= 3:
            # earliest time by which most fighters can pill: a natural shared pill window
            ready = sorted(row["pill"]["ready_at"] for row in fighters)
            needed = math.ceil(len(ready) * SHARED_WINDOW_PERCENT / 100)
            ready_at = ready[needed - 1]
            if ready_at > now:
                start = ready_at.replace(minute=0, second=0, microsecond=0)
                if start < ready_at:
                    start += timedelta(hours=1)
                tips.append(
                    f"{needed}/{len(ready)} fighters can pill by {start:%H}:00 UTC; "
                    "agree on a shared pill time from then."
                )
            spread = {row["pill"]["pilled_at"].hour for row in pilled_today}
            if len(spread) >= 4:
                tips.append(f"Today's pills were spread over {len(spread)} different hours; a shared window hits harder.")
        to_economy = [row for row in reskilled if row["economy"]]
        if to_economy:
            back_at = min(row["last_reset_at"] for row in to_economy) + settings["reset_cooldown"]
            tips.append(f"{len(to_economy)} member(s) reset to economy; they can't reset back to fight before {back_at:%b %d}.")
        if no_help:
            tips.append(f"{len(no_help)} fighter(s) asked for no MU help today; that's free health, best used while pilled.")
        return tips


async def setup(bot: commands.Bot):
    await bot.add_cog(MilitaryUnitDailyReportJob(bot))
