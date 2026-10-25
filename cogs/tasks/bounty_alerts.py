"""bounty_alerts: keep one live post per allied bounty in each military unit's bounty thread.

Members subscribe with `/subscribe bounty` (cogs/commands/subscriptions.py). The posts go to the threads set
in config.json `military_units[].threadIds.bountyId`; MUs without that key get nothing (no channelId fallback,
so the MU channels are not flooded). MUs that share a thread share its posts. Every minute the job:

1. Builds the friendly countries: Romania, its defensive-pact partners (`country.defensivePacts`) and the
   members of its alliance that are not suspended (`alliance.getById`), refreshed every hour.
2. Lists the active battles and keeps the sides of a friendly country with a bounty: `moneyPool` above 0
   and a `bountyEffectiveAt`. Unlike bounty_monitor there is no minimum rate, because allied bounties
   usually pay well under 0.1 per 1k damage. One post per battle covers every friendly side.
3. Posts a new bounty with the eligible subscribers mentioned in the message text, and on later runs only
   edits its embed (rate and pool), which notifies nobody. A subscriber is eligible while they are in an MU
   of that thread, on a fight build (no skill points counts as economy) and can fight (`can_fight`: health
   10+ or hunger left, and no debuff). Each subscriber is mentioned at most once per post: those who become
   eligible later (debuff over, skills reset to fight) are mentioned in a reply to the post.
4. Deletes the post and its replies once the battle has no friendly bounty left. A bounty that runs out and
   is replaced by a new one between two runs only updates the post.

The posts are tracked in memory. After a restart, the first run reads the last HISTORY_SCAN_LIMIT messages of
each thread and adopts the bot's own posts (embed in EMBED_COLOR with a battle link) and their replies, so
they keep updating, are deleted when their bounty ends and nobody is mentioned twice.
"""

import asyncio
import json
import logging
import re
import time
from datetime import datetime, timezone

import discord
from discord.ext import commands, tasks

from cogs.commands.mu_order_alignment import BATTLE_LINK, COUNTRY_NAME, SIDES
from cogs.tasks.military_unit_contract_monitor import SIDE_ICONS, can_fight, format_amount
from config import config
from utils.api import get_active_battles, get_all_countries, get_alliance, get_battle, get_shared_session, get_users_info
from utils.common import country_flag, get_mu_destination
from utils.computational import is_economy_build
from utils.db import get_job_subscribers, remove_job_subscription
from utils.i18n import Translator, get_translator

logger = logging.getLogger(__name__)

BOUNTY_ALERTS_INTERVAL_MINUTES = 1
FRIENDLY_COUNTRIES_TTL_SECONDS = 60 * 60
# messages read per thread after a restart to find the posts made before it
HISTORY_SCAN_LIMIT = 100

# job name and target in the job_subscriptions table (see cogs/commands/subscriptions.py). The MU is not
# stored: a subscriber is pinged in the bounty thread of whichever configured MU they are in.
SUBSCRIPTION_JOB = "bounty_alerts"
SUBSCRIPTION_TARGET = "current_mu"
THREAD_KEY = "bountyId"

# the color and the battle link mark the job's own posts when a thread is read back after a restart
EMBED_COLOR = discord.Color.gold()
BATTLE_URL_PATTERN = re.compile(r"/battle/([a-f\d]{24})$")


def bounty_units() -> dict[str, dict]:
    """MU id -> config entry for the MUs with a bounty thread (threadIds.bountyId)."""
    return {
        str(unit["id"]): unit
        for unit in config.get("military_units", [])
        if unit.get("id") and (unit.get("threadIds") or {}).get(THREAD_KEY)
    }


def bounty_threads(units: dict[str, dict]) -> dict[int, list[dict]]:
    """Bounty thread id -> the config entries of the MUs posting there (several MUs may share one)."""
    threads: dict[int, list[dict]] = {}
    for unit in units.values():
        threads.setdefault(int(unit["threadIds"][THREAD_KEY]), []).append(unit)
    return threads


def _amount(value) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def friendly_bounty_sides(battle: dict, friendly_ids: set[str]) -> list[str]:
    """The sides of an active battle whose country is friendly and has a bounty left (moneyPool > 0)."""
    if battle.get("isActive") is False:
        return []
    sides = []
    for side in SIDES:
        data = battle.get(side) or {}
        if (
            str(data.get("country") or "") in friendly_ids
            and _amount(data.get("moneyPool")) > 0
            and data.get("bountyEffectiveAt")
        ):
            sides.append(side)
    return sides


def _country_label(name: str) -> str:
    flag = country_flag(name)
    return f"{flag} **{name}**" if flag else f"**{name}**"


def build_bounty_embed(battle: dict, sides: list[str], country_names: dict[str, str], tr: Translator) -> discord.Embed:
    """The post of a battle's friendly bounties: both countries, the battle link and each side's rate and pool."""
    link = BATTLE_LINK.format(battle.get("_id"))
    unknown = tr("common.unknown")
    names = {side: country_names.get(str((battle.get(side) or {}).get("country") or ""), unknown) for side in SIDES}
    embed = discord.Embed(
        title=tr("bounty_alerts.title", countries=" / ".join(names[side] for side in sides)),
        url=link,
        description=tr(
            "bounty_alerts.description",
            attacker_icon=SIDE_ICONS["attacker"],
            attacker=_country_label(names["attacker"]),
            defender_icon=SIDE_ICONS["defender"],
            defender=_country_label(names["defender"]),
            link=link,
        ),
        color=EMBED_COLOR,
        timestamp=datetime.now(timezone.utc),
    )
    for side in sides:
        data = battle.get(side) or {}
        embed.add_field(
            name=f"{SIDE_ICONS[side]} {names[side]} ({tr(f'common.side_title.{side}')})",
            value=tr(
                "bounty_alerts.side_value",
                rate=format_amount(data.get("moneyPer1kDamages"), unknown),
                pool=f"{_amount(data.get('moneyPool')):,.2f}",
            ),
            inline=True,
        )
    embed.set_footer(text=tr("bounty_alerts.footer"))
    return embed


def _signature(embed: discord.Embed) -> str:
    """The embed without its timestamp, to edit a post only when its content changed."""
    data = embed.to_dict()
    data.pop("timestamp", None)
    return json.dumps(data, sort_keys=True)


def _post_battle_id(message: discord.Message) -> str | None:
    """The battle id of a bounty post made by this job (see EMBED_COLOR), or None for any other message."""
    for embed in message.embeds:
        if embed.colour is not None and embed.colour.value == EMBED_COLOR.value and embed.url:
            match = BATTLE_URL_PATTERN.search(embed.url)
            if match:
                return match.group(1)
    return None


def _mentions(discord_ids) -> str:
    return " ".join(f"<@{discord_id}>" for discord_id in discord_ids)


class BountyAlertsJob(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # thread id -> battle id -> {"message_id", "pinged": discord ids, "replies": message ids, "signature"}
        self._posts: dict[int, dict[str, dict]] = {}
        # threads whose history was read back for posts made before a restart
        self._recovered: set[int] = set()
        # threads already reported as missing or unreadable, so the warning is logged once
        self._warned: set[int] = set()
        self._friends: tuple[set[str], dict[str, str], float] | None = None
        self.bounty_alerts.start()

    def cog_unload(self):
        self.bounty_alerts.cancel()

    @tasks.loop(minutes=BOUNTY_ALERTS_INTERVAL_MINUTES)
    async def bounty_alerts(self):
        """Create, update or delete the bounty posts of every bounty thread (see the module docstring).

        Nothing changes in a run whose friendly countries or battle list cannot be fetched. A post whose
        battle left the listing is checked with `battle.getById` and left untouched when that fails, so a
        failed listing page never deletes posts.
        """
        guild = self.bot.get_guild(config["guild"])
        if guild is None:
            return
        threads = bounty_threads(bounty_units())
        if not threads:
            return

        session = await get_shared_session()
        friends = await self._friendly_countries(session)
        if friends is None:
            return
        friendly_ids, country_names = friends
        battles = await get_active_battles(session)
        if battles is None:
            return

        # first run after a restart: adopt the posts left in each thread before checking which battles ended
        for thread_id, units in threads.items():
            if thread_id not in self._recovered and (channel := await self._thread(guild, thread_id, units)):
                await self._recover(channel, thread_id)

        by_id = {str(battle["_id"]): battle for battle in battles if battle.get("_id")}
        # a tracked battle missing from the listing has ended, or a listing page failed
        unchecked: set[str] = set()
        tracked = {battle_id for posts in self._posts.values() for battle_id in posts}
        for battle_id in tracked - by_id.keys():
            battle = await get_battle(battle_id, session)
            if battle is None:
                unchecked.add(battle_id)
            else:
                by_id[battle_id] = battle
        bounties = {
            battle_id: sides
            for battle_id, battle in by_id.items()
            if (sides := friendly_bounty_sides(battle, friendly_ids))
        }

        channels = {}
        for thread_id, units in threads.items():
            # a thread whose history could not be read is skipped, so no post is duplicated
            if thread_id not in self._recovered or not (bounties or self._posts.get(thread_id)):
                continue
            if channel := await self._thread(guild, thread_id, units):
                channels[thread_id] = channel
        if not channels:
            return

        eligible = await self._eligible_subscribers(threads, bounties, guild, session) if bounties else {}
        tr = await get_translator(guild) if bounties else None
        for thread_id, channel in channels.items():
            posts = self._posts.setdefault(thread_id, {})
            if posts:
                await self._unarchive(channel)
            for battle_id in list(posts):
                if battle_id not in bounties and battle_id not in unchecked:
                    await self._delete_post(channel, posts.pop(battle_id))
            for battle_id, sides in bounties.items():
                embed = build_bounty_embed(by_id[battle_id], sides, country_names, tr)
                mentions = eligible.get(thread_id, [])
                if battle_id in posts:
                    await self._update_post(channel, posts[battle_id], embed, mentions, tr)
                else:
                    await self._create_post(channel, posts, battle_id, embed, mentions)

    @bounty_alerts.before_loop
    async def before_bounty_alerts(self):
        await self.bot.wait_until_ready()

    async def _friendly_countries(self, session) -> tuple[set[str], dict[str, str]] | None:
        """The friendly country ids and every country's id -> name, cached for an hour.

        A failed refresh keeps the previous result (and retries next run); None when nothing was ever loaded.
        """
        now = time.monotonic()
        if self._friends and now - self._friends[2] < FRIENDLY_COUNTRIES_TTL_SECONDS:
            return self._friends[0], self._friends[1]
        loaded = await self._load_friendly_countries(session)
        if loaded is None:
            return (self._friends[0], self._friends[1]) if self._friends else None
        self._friends = (*loaded, now)
        return loaded

    async def _load_friendly_countries(self, session) -> tuple[set[str], dict[str, str]] | None:
        """Romania, its defensive-pact partners and its alliance's members that are not suspended.

        None when the countries or the alliance cannot be fetched, or Romania is missing from the list.
        """
        countries = await get_all_countries(session)
        if not countries:
            return None
        names = {str(country["_id"]): str(country.get("name")) for country in countries if country.get("_id")}
        romania = next((country for country in countries if country.get("name") == COUNTRY_NAME), None)
        if romania is None:
            logger.warning("%s is missing from the country list", COUNTRY_NAME)
            return None
        friendly_ids = {str(romania["_id"])} | {str(partner) for partner in romania.get("defensivePacts") or []}
        if romania.get("allianceId"):
            alliance = await get_alliance(str(romania["allianceId"]), session)
            if alliance is None:
                return None
            friendly_ids |= {
                str(member["country"])
                for member in alliance.get("memberCountries") or []
                if member.get("country") and not member.get("suspended")
            }
        return friendly_ids, names

    async def _thread(self, guild: discord.Guild, thread_id: int, units: list[dict]):
        """The bounty thread, or None (logged once per thread) when it does not exist or is not visible."""
        channel = await get_mu_destination(guild, units[0], THREAD_KEY)
        if channel is None and thread_id not in self._warned:
            logger.warning("Bounty thread %s (MU %s) not found", thread_id, units[0].get("friendlyName"))
            self._warned.add(thread_id)
        return channel

    async def _recover(self, channel, thread_id: int) -> bool:
        """Adopt the bounty posts and ping replies this job left in the thread before a restart.

        Older duplicates of a battle's post are deleted. False when the history cannot be read; the thread
        is retried next run and gets no posts until then, so no post is duplicated.
        """
        posts: dict[str, dict] = {}
        replies: dict[int, list[discord.Message]] = {}
        duplicates: list[int] = []
        me = channel.guild.me
        try:
            # newest first: the first post seen for a battle is the one kept
            async for message in channel.history(limit=HISTORY_SCAN_LIMIT):
                if me is None or message.author.id != me.id:
                    continue
                battle_id = _post_battle_id(message)
                if battle_id and battle_id in posts:
                    duplicates.append(message.id)
                elif battle_id:
                    posts[battle_id] = {
                        "message_id": message.id,
                        "pinged": {str(user_id) for user_id in message.raw_mentions},
                        "replies": [],
                        "signature": None,
                    }
                elif message.reference and message.reference.message_id:
                    replies.setdefault(message.reference.message_id, []).append(message)
        except discord.DiscordException:
            if thread_id not in self._warned:
                logger.exception("Could not read the history of bounty thread %s", thread_id)
                self._warned.add(thread_id)
            return False

        by_message = {post["message_id"]: post for post in posts.values()}
        for message_id, messages in replies.items():
            if (post := by_message.get(message_id)) is not None:
                for message in messages:
                    post["replies"].append(message.id)
                    post["pinged"].update(str(user_id) for user_id in message.raw_mentions)
        for message_id in duplicates:
            await self._delete_message(channel, message_id)
        self._posts[thread_id] = posts
        self._recovered.add(thread_id)
        if posts:
            logger.info("Bounty thread %s: adopted %d post(s) made before the restart", thread_id, len(posts))
        return True

    async def _eligible_subscribers(self, threads: dict[int, list[dict]], bounties: dict[str, list[str]],
                                    guild: discord.Guild, session) -> dict[int, list[str]]:
        """Bounty thread id -> Discord ids of the subscribers able to fight for its bounties now.

        Only subscribers not yet mentioned in some current post are fetched (one batched request). Those
        who left the server are dropped from the database.
        """
        try:
            subscriptions = await asyncio.to_thread(get_job_subscribers, SUBSCRIPTION_JOB, SUBSCRIPTION_TARGET)
        except Exception:
            logger.exception("Could not read bounty subscribers")
            return {}
        subscriptions = await self._drop_departed(subscriptions, guild)
        pending = {
            str(s["discord_id"]): str(s["api_id"])
            for s in subscriptions
            if s.get("api_id") and any(
                str(s["discord_id"]) not in (self._posts.get(thread_id, {}).get(battle_id) or {}).get("pinged", ())
                for thread_id in threads
                for battle_id in bounties
            )
        }
        if not pending:
            return {}
        # a subscriber whose player could not be fetched is not pinged this run
        users = await get_users_info(pending.values(), session)
        unit_threads = {str(unit["id"]): thread_id for thread_id, units in threads.items() for unit in units}
        now = datetime.now(timezone.utc)
        eligible: dict[int, list[str]] = {}
        for discord_id, api_id in pending.items():
            user = users.get(api_id)
            if not user or is_economy_build(user) is not False or not can_fight(user, now):
                continue
            thread_id = unit_threads.get(str(user.get("mu") or ""))
            if thread_id is not None:
                eligible.setdefault(thread_id, []).append(discord_id)
        return eligible

    async def _drop_departed(self, subscriptions: list[dict], guild: discord.Guild) -> list[dict]:
        """The subscriptions of members still in the guild; the others are removed from the database.

        Membership is only judged once the guild's member list is fully cached (`guild.chunked`),
        so a member missing from a partial cache is neither skipped nor unsubscribed.
        """
        if not guild.chunked:
            return subscriptions
        staying = []
        for subscription in subscriptions:
            discord_id = str(subscription["discord_id"])
            if discord_id.isdigit() and guild.get_member(int(discord_id)) is None:
                try:
                    await asyncio.to_thread(remove_job_subscription, SUBSCRIPTION_JOB, SUBSCRIPTION_TARGET, discord_id)
                    logger.info("Dropped the bounty subscription of %s, who left the server", discord_id)
                except Exception:
                    logger.exception("Could not drop the bounty subscription of %s", discord_id)
                continue
            staying.append(subscription)
        return staying

    async def _create_post(self, channel, posts: dict[str, dict], battle_id: str, embed: discord.Embed,
                           mentions: list[str]):
        """Post a new bounty with the eligible subscribers mentioned; a failed send is retried next run."""
        try:
            message = await channel.send(
                content=_mentions(mentions) or None,
                embed=embed,
                allowed_mentions=discord.AllowedMentions(everyone=False, roles=False, users=True),
            )
        except discord.DiscordException:
            logger.exception("Failed to post the bounty of battle %s", battle_id)
            return
        posts[battle_id] = {"message_id": message.id, "pinged": set(mentions), "replies": [], "signature": _signature(embed)}

    async def _update_post(self, channel, post: dict, embed: discord.Embed, mentions: list[str], tr: Translator):
        """Edit the post's embed when it changed, and mention newly eligible subscribers in a reply.

        Only the embed is edited, so the mentions in the post's text never notify anyone again. A post
        deleted by someone is posted again without mentions.
        """
        signature = _signature(embed)
        if signature != post["signature"]:
            try:
                await channel.get_partial_message(post["message_id"]).edit(embed=embed)
                post["signature"] = signature
            except discord.NotFound:
                try:
                    message = await channel.send(embed=embed)
                except discord.DiscordException:
                    logger.exception("Failed to post again the deleted bounty message %s", post["message_id"])
                    return
                post["message_id"] = message.id
                post["signature"] = signature
            except discord.DiscordException:
                logger.exception("Failed to update the bounty message %s", post["message_id"])

        new = [discord_id for discord_id in mentions if discord_id not in post["pinged"]]
        if not new:
            return
        try:
            reply = await channel.send(
                content=tr("bounty_alerts.new_eligible", mentions=_mentions(new)),
                reference=channel.get_partial_message(post["message_id"]).to_reference(fail_if_not_exists=False),
                allowed_mentions=discord.AllowedMentions(everyone=False, roles=False, users=True, replied_user=False),
            )
        except discord.DiscordException:
            logger.exception("Failed to mention new bounty subscribers under message %s", post["message_id"])
            return
        post["replies"].append(reply.id)
        post["pinged"].update(new)

    async def _delete_post(self, channel, post: dict):
        """Delete a post whose bounty ended, with its ping replies."""
        for message_id in [post["message_id"], *post["replies"]]:
            await self._delete_message(channel, message_id)

    async def _delete_message(self, channel, message_id: int):
        try:
            await channel.get_partial_message(message_id).delete()
        except discord.NotFound:
            pass
        except discord.DiscordException:
            logger.exception("Failed to delete bounty message %s", message_id)

    async def _unarchive(self, channel):
        """Reopen an archived thread so its posts can be edited and deleted (sending reopens it anyway)."""
        if isinstance(channel, discord.Thread) and channel.archived and not channel.locked:
            try:
                await channel.edit(archived=False)
            except discord.DiscordException:
                logger.exception("Could not unarchive bounty thread %s", channel.id)


async def setup(bot: commands.Bot):
    await bot.add_cog(BountyAlertsJob(bot))
