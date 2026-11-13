"""mu_help_requests: post the help requests of military unit members in their MU's help-requests thread.

The posts go to the threads set in config.json `military_units[].threadIds.helpRequestsId`; MUs without that
key get nothing (no channelId fallback). MUs that share a thread share its posts. Every minute the job:

1. Reads the members of those MUs (`mu.getById`) and their players (`user.getUserById`, one batched request;
   full users because the build comes from skills, which `getUserLite` no longer returns).
2. Treats a player's `dates.lastHelpAskedAt` that is newer than the last one handled as a new help request.
   The API has no list of open requests (`muHelp.*` is closed to API keys), so the bot can't tell when a
   request has received all its helps.
3. Deletes the player's previous post when they ask for help again, and posts the new request as one short
   line, but only when the player is in a Pill buff, or on an economy build (posted whatever their Pill
   state and marked as eco). A request made outside a buff (no Pill, or in the debuff) stays pending: the
   buff is checked again every run, and the request is posted once the player takes a Pill, unless a newer
   request replaces it or the help cooldown (gameConfig ``mu.helpCooldownHours``) passes first.
   The new post is sent before the old one is deleted, so a failed send keeps the old one until the retry.
   While the MU has several requests posted, its lines tell readers to press LOAD MORE on the MU page; the
   lines are edited when that changes.
4. Deletes the post of a player who left the MU (only when the MU was read successfully), and the posts of
   an MU taken out of the config or moved to another thread.

The posts are tracked in memory. After a restart, the first run reads the last HISTORY_SCAN_LIMIT messages of
each thread and adopts the bot's own posts (text starting with POST_MARKER, with a player and an MU link and
the request time as a Discord timestamp), so they are still deleted when replaced; older duplicates of a player's post are deleted. Requests made
while the bot was down are posted only if they are at most RESTART_GRACE old at the first run.
"""

import asyncio
import logging
import re
from collections import Counter
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands, tasks

from cogs.tasks.fight_ready import ready_state
from cogs.tasks.military_unit_contract_monitor import parse_iso
from config import config
from utils.api import warera
from utils.common import get_mu_destination
from utils.computational import is_economy_build
from utils.i18n import Translator, get_translator

logger = logging.getLogger(__name__)

MU_HELP_INTERVAL_MINUTES = 1
THREAD_KEY = "helpRequestsId"
# messages read per thread after a restart to find the posts made before it (one post per member at most,
# plus whatever members write in the thread)
HISTORY_SCAN_LIMIT = 1000
# requests this old at the first run after a restart are still posted (the adopted posts prevent duplicates)
RESTART_GRACE = timedelta(minutes=10)
# gameConfig mu.helpCooldownHours on 2026-11-13, used only when gameConfig can't be read
DEFAULT_HELP_COOLDOWN_HOURS = 12

USER_URL = "https://app.warera.io/user/{}"
MU_URL = "https://app.warera.io/mu/{}"
# every post starts with this marker and links the player and the MU, which marks the job's own posts
POST_MARKER = "🆘"
_POST_PATTERN = re.compile(r"/user/([a-f\d]{24}).*?/mu/([a-f\d]{24})", re.DOTALL)
# the request time, written as a Discord timestamp ("5 minutes ago") and read back after a restart
_ASKED_PATTERN = re.compile(r"<t:(\d+):R>")


def help_units() -> dict[str, dict]:
    """MU id -> config entry for the MUs with a help-requests thread (threadIds.helpRequestsId)."""
    return {
        str(unit["id"]): unit
        for unit in config.get("military_units", [])
        if unit.get("id") and (unit.get("threadIds") or {}).get(THREAD_KEY)
    }


def help_threads(units: dict[str, dict]) -> dict[int, list[dict]]:
    """Help-requests thread id -> the config entries of the MUs posting there (several MUs may share one)."""
    threads: dict[int, list[dict]] = {}
    for unit in units.values():
        threads.setdefault(int(unit["threadIds"][THREAD_KEY]), []).append(unit)
    return threads


def _aware(moment: datetime | None) -> datetime | None:
    """The timestamp as timezone-aware UTC (the API sends "Z" times; a naive one would break comparisons)."""
    if moment is not None and moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment


def help_request_kind(user: dict, now: datetime) -> str | None:
    """Whether a player's help request is posted, and how.

    Args:
        user: A ``user.getUserById`` payload (needs ``skills`` for the build and ``buffs`` for the Pill).
        now: Current time, timezone-aware UTC.

    Returns:
        ``"eco"`` for an economy build (posted whatever the Pill state), ``"buff"`` for anyone else in a
        Pill buff, and None (not posted) for a player without a buff, in the debuff, or whose build
        can't be read and who has no buff.
    """
    if is_economy_build(user) is True:
        return "eco"
    if ready_state(user, now) == "buff":
        return "buff"
    return None


def _link_text(text: str) -> str:
    """Escape a name for the text of a masked link, brackets included (escape_markdown leaves them)."""
    return discord.utils.escape_markdown(text).replace("[", "\\[").replace("]", "\\]")


def build_request_line(tr: Translator, user: dict, mu: dict, asked: datetime, eco: bool) -> str:
    """The one-line post for a help request, without the LOAD MORE hint (see `with_hint`).

    Args:
        tr: Translator of the server language.
        user: The player's payload (``_id``, ``username``).
        mu: The MU's ``mu.getById`` payload (``_id``, ``name``).
        asked: When the request was made (``dates.lastHelpAskedAt``), shown as a relative Discord timestamp.
        eco: Mark the player as an economy build.

    Returns:
        The message text; it starts with POST_MARKER and holds the request time, which the restart
        recovery relies on.
    """
    line = tr(
        "mu_help_requests.request",
        player=_link_text(str(user.get("username") or user["_id"])),
        player_url=USER_URL.format(user["_id"]),
        when=f"<t:{int(asked.timestamp())}:R>",
        mu=_link_text(str(mu.get("name") or mu["_id"])),
        mu_url=MU_URL.format(mu["_id"]),
    )
    if eco:
        line += tr("mu_help_requests.eco")
    return line


def with_hint(tr: Translator, base: str, hint: bool) -> str:
    """The post text: the base line, plus the LOAD MORE hint while the MU has several requests posted."""
    return base + tr("mu_help_requests.load_more") if hint else base


def _hint_suffixes() -> tuple[str, ...]:
    """The LOAD MORE hint in every server language, to strip it from a post read back after a restart."""
    return tuple({Translator(language)("mu_help_requests.load_more") for language in ("en", "ro")})


def post_owner(message: discord.Message) -> tuple[str, str, datetime, str, bool] | None:
    """Read back a help-request post made by this job.

    The request time comes from the post's Discord timestamp, rounded up to the next second so the same
    request never looks newer than its post; a post without one falls back to the time it was posted.

    Args:
        message: Any message of the thread.

    Returns:
        (player id, MU id, request time, text without the LOAD MORE hint, whether it had the hint), or
        None for any message that isn't a help-request post.
    """
    content = message.content or ""
    if not content.startswith(POST_MARKER):
        return None
    match = _POST_PATTERN.search(content)
    if not match:
        return None
    asked_match = _ASKED_PATTERN.search(content)
    asked = (
        datetime.fromtimestamp(int(asked_match.group(1)) + 1, tz=timezone.utc)
        if asked_match else _aware(message.created_at)
    )
    base, hint = content, False
    for suffix in _hint_suffixes():
        if content.endswith(suffix):
            base, hint = content[:-len(suffix)], True
            break
    return match.group(1), match.group(2), asked, base, hint


class MuHelpRequestsJob(commands.Cog):
    """Background job that posts MU members' help requests in their help-requests thread (see the module docstring)."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # player id -> {"thread_id", "mu_id", "message_id", "asked_at", "base", "hint"}; asked_at is the request
        # time (read back from the post's timestamp after a restart), so only a later request replaces the
        # post; base is the text without the LOAD MORE hint, hint whether the post shows it
        self._posts: dict[str, dict] = {}
        # player id -> the latest lastHelpAskedAt already handled (posted, or dropped after the help cooldown
        # without a buff); a newer request stays pending until then
        self._seen: dict[str, datetime] = {}
        # player id -> (request time, "eco"/"buff") of a request whose post failed to send: the verdict is
        # kept for the retry, so a buff that ends in between doesn't drop it
        self._verdicts: dict[str, tuple[datetime, str]] = {}
        # requests older than this (minus RESTART_GRACE) were made before the bot started and are not posted
        self._started_at = datetime.now(timezone.utc)
        # threads whose history was read back for posts made before a restart
        self._recovered: set[int] = set()
        # threads already reported as missing or unreadable, so the warning is logged once
        self._warned: set[int] = set()
        # a forced /run_job and the scheduled run must not both post the same request
        self._lock = asyncio.Lock()
        self.mu_help_requests.start()

    def cog_unload(self):
        """Stop the loop when the cog is unloaded."""
        self.mu_help_requests.cancel()

    @tasks.loop(minutes=MU_HELP_INTERVAL_MINUTES)
    async def mu_help_requests(self):
        """Post new help requests and delete replaced ones in every help-requests thread (see the module docstring).

        Errors are logged, not raised, so one bad run never stops the loop.
        """
        guild = self.bot.get_guild(config["guild"])
        if guild is None:
            return
        threads = help_threads(help_units())
        if not threads:
            return
        async with self._lock:
            try:
                await self._run(guild, threads)
            except Exception:
                logger.exception("MU help requests run failed")

    @mu_help_requests.before_loop
    async def before_mu_help_requests(self):
        """Wait until the bot is ready, so the guild and its threads are cached."""
        await self.bot.wait_until_ready()

    async def _run(self, guild: discord.Guild, threads: dict[int, list[dict]]):
        """One run over the threads whose channel exists and whose history was read back.

        Args:
            guild: The configured guild.
            threads: Thread id -> MU config entries, from `help_threads`.
        """
        channels = {}
        for thread_id, units in threads.items():
            channel = await self._thread(guild, thread_id, units)
            # a thread whose history could not be read is skipped, so no post is duplicated
            if channel is not None and (thread_id in self._recovered or await self._recover(channel, thread_id)):
                channels[thread_id] = channel
        if not channels:
            return

        unit_threads = {str(unit["id"]): thread_id for thread_id in channels for unit in threads[thread_id]}
        mus = await warera.mus.get_many(list(unit_threads))
        # MU id -> member ids, only for the MUs that loaded; a member of two MUs is kept in the first
        mu_members = {mu_id: set(mu.get("members") or []) for mu_id, mu in mus.items()}
        member_mu: dict[str, str] = {}
        for mu_id, members in mu_members.items():
            for user_id in members:
                member_mu.setdefault(str(user_id), mu_id)
        users = await warera.users.get_full_many(list(member_mu)) if member_mu else {}

        configured = {str(unit["id"]) for units in threads.values() for unit in units}
        for user_id, post in list(self._posts.items()):
            if post["thread_id"] not in channels:
                continue
            members = mu_members.get(post["mu_id"])
            # a member who left a loaded MU no longer has a request there, and an MU taken out of the
            # config (or moved to another thread) leaves its posts behind otherwise
            if (members is not None and user_id not in members) or post["mu_id"] not in configured \
                    or (post["mu_id"] in unit_threads and unit_threads[post["mu_id"]] != post["thread_id"]):
                await self._delete_post(channels[post["thread_id"]], self._posts.pop(user_id))

        now = datetime.now(timezone.utc)
        tr = None
        cooldown = None
        for user_id, mu_id in member_mu.items():
            user = users.get(user_id)
            asked = _aware(parse_iso(((user or {}).get("dates") or {}).get("lastHelpAskedAt")))
            if asked is None:
                continue
            old = self._posts.get(user_id)
            if old is not None and asked <= old["asked_at"]:
                continue  # the request already posted
            if old is not None and old["thread_id"] not in channels:
                continue  # the old post's thread is unreadable this run; retried next run
            handled = self._seen.get(user_id, self._started_at - RESTART_GRACE)
            if asked > handled:
                verdict = self._verdicts.get(user_id)
                kind = verdict[1] if verdict and verdict[0] == asked else help_request_kind(user, now)
                if kind is not None:
                    tr = tr or await get_translator(guild)
                    thread_id = unit_threads[mu_id]
                    base = build_request_line(tr, user, mus[mu_id], asked, kind == "eco")
                    others_open = any(p["mu_id"] == mu_id for uid, p in self._posts.items() if uid != user_id)
                    if not await self._create_post(channels[thread_id], user_id, mu_id, thread_id, asked,
                                                   base, others_open, tr):
                        # the old post stays until the new one is out; same verdict on the retry
                        self._verdicts[user_id] = (asked, kind)
                        continue
                    self._verdicts.pop(user_id, None)
                    self._seen[user_id] = asked
                else:
                    # no buff yet: the request stays pending and the buff is checked again every run (the
                    # player may leave the debuff and take a Pill), until the help cooldown is over
                    if cooldown is None:
                        cooldown = await self._help_cooldown()
                    if now - asked >= cooldown:
                        self._seen[user_id] = asked
            if old is not None:
                # a new request replaces the posted one, whether or not the new one is posted
                if self._posts.get(user_id) is old:
                    self._posts.pop(user_id)
                await self._delete_post(channels[old["thread_id"]], old)

        await self._sync_hints(guild, channels, tr)

    async def _help_cooldown(self) -> timedelta:
        """How long an unposted request keeps waiting for a buff: gameConfig ``mu.helpCooldownHours``.

        After that the player may ask again, so the old request is dropped. Falls back to
        DEFAULT_HELP_COOLDOWN_HOURS when gameConfig can't be read (it is cached for an hour).
        """
        game_config = await warera.game.get_config() or {}
        hours = (game_config.get("mu") or {}).get("helpCooldownHours") or DEFAULT_HELP_COOLDOWN_HOURS
        return timedelta(hours=hours)

    async def _sync_hints(self, guild: discord.Guild, channels: dict, tr: Translator | None):
        """Add or remove the LOAD MORE hint so it shows exactly while an MU has several requests posted.

        Args:
            guild: The configured guild, for the translator.
            channels: Thread id -> channel of the threads read this run; posts elsewhere are left alone.
            tr: The run's translator, or None when it hasn't been read yet.
        """
        counts = Counter(post["mu_id"] for post in self._posts.values())
        for user_id, post in list(self._posts.items()):
            want = counts[post["mu_id"]] > 1
            if post["hint"] == want or post["thread_id"] not in channels:
                continue
            tr = tr or await get_translator(guild)
            channel = channels[post["thread_id"]]
            await self._unarchive(channel)
            try:
                await channel.get_partial_message(post["message_id"]).edit(
                    content=with_hint(tr, post["base"], want),
                    allowed_mentions=discord.AllowedMentions.none(),
                )
                post["hint"] = want
            except discord.NotFound:
                # deleted by someone: the request is no longer shown, and is not posted again
                self._posts.pop(user_id, None)
            except discord.DiscordException:
                logger.exception("Failed to update help request message %s", post["message_id"])

    async def _thread(self, guild: discord.Guild, thread_id: int, units: list[dict]):
        """The help-requests thread, or None (logged once per thread) when it does not exist or is not visible."""
        channel = await get_mu_destination(guild, units[0], THREAD_KEY)
        if channel is None and thread_id not in self._warned:
            logger.warning("Help requests thread %s (MU %s) not found", thread_id, units[0].get("friendlyName"))
            self._warned.add(thread_id)
        return channel

    async def _recover(self, channel, thread_id: int) -> bool:
        """Adopt the help-request posts this job left in the thread before a restart.

        Older duplicates of a player's post are deleted.

        Args:
            channel: The help-requests thread or channel.
            thread_id: Its configured id.

        Returns:
            False when the history cannot be read; the thread is retried next run and gets no posts until
            then, so no post is duplicated.
        """
        adopted: dict[str, dict] = {}
        duplicates: list[int] = []
        me = channel.guild.me
        try:
            # newest first: the first post seen for a player is the one kept
            async for message in channel.history(limit=HISTORY_SCAN_LIMIT):
                if me is None or message.author.id != me.id or (owner := post_owner(message)) is None:
                    continue
                user_id, mu_id, asked, base, hint = owner
                if user_id in adopted or user_id in self._posts:
                    duplicates.append(message.id)
                    continue
                adopted[user_id] = {
                    "thread_id": thread_id,
                    "mu_id": mu_id,
                    "message_id": message.id,
                    "asked_at": asked,
                    "base": base,
                    "hint": hint,
                }
        except discord.DiscordException:
            if thread_id not in self._warned:
                logger.exception("Could not read the history of help requests thread %s", thread_id)
                self._warned.add(thread_id)
            return False

        if duplicates:
            await self._unarchive(channel)
        for message_id in duplicates:
            await self._delete_message(channel, message_id)
        self._posts.update(adopted)
        self._recovered.add(thread_id)
        if adopted:
            logger.info("Help requests thread %s: adopted %d post(s) made before the restart", thread_id, len(adopted))
        return True

    async def _create_post(self, channel, user_id: str, mu_id: str, thread_id: int, asked: datetime,
                           base: str, hint: bool, tr: Translator) -> bool:
        """Post one help request (no mentions, no link previews).

        Returns:
            True when posted; a failed send is logged and retried next run.
        """
        try:
            message = await channel.send(
                content=with_hint(tr, base, hint),
                suppress_embeds=True,
                allowed_mentions=discord.AllowedMentions.none(),
            )
        except discord.DiscordException:
            logger.exception("Failed to post the help request of player %s", user_id)
            return False
        self._posts[user_id] = {
            "thread_id": thread_id, "mu_id": mu_id, "message_id": message.id, "asked_at": asked,
            "base": base, "hint": hint,
        }
        return True

    async def _delete_post(self, channel, post: dict):
        """Delete a replaced or outdated help-request post."""
        await self._unarchive(channel)
        await self._delete_message(channel, post["message_id"])

    async def _delete_message(self, channel, message_id: int):
        try:
            await channel.get_partial_message(message_id).delete()
        except discord.NotFound:
            pass
        except discord.DiscordException:
            logger.exception("Failed to delete help request message %s", message_id)

    async def _unarchive(self, channel):
        """Reopen an archived thread so its posts can be deleted (sending reopens it anyway)."""
        if isinstance(channel, discord.Thread) and channel.archived and not channel.locked:
            try:
                await channel.edit(archived=False)
            except discord.DiscordException:
                logger.exception("Could not unarchive help requests thread %s", channel.id)


async def setup(bot: commands.Bot):
    """Load the job (discord.py extension entry point)."""
    await bot.add_cog(MuHelpRequestsJob(bot))
