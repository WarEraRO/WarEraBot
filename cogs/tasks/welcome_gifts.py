"""welcome_gifts: hourly list of Romanian newcomers who can receive a welcome gift, with a claim button per line.

WarEra v0.28.4 (2026-11-22) lets level-15+ players send a newcomer (level 2-10, account under 7 days old,
counted from account creation) a welcome gift of 10, 20 or 30 money from the chat's Newcomers tab. The API
list of newcomers (``welcomeGift.getNewcomers``) is closed to API keys, so the job rebuilds it:

1. Every hour it reads Romania's ``userLevel`` ranking pages (players with any XP, so every player above
   level 1), keeps the ids created in the last NEWCOMER_AGE + ID_MARGIN (an ObjectId holds its creation
   time), loads those players (``user.getUserLite``, batched) and keeps the Romanian citizens at level
   MIN_LEVEL to MAX_LEVEL whose account is younger than NEWCOMER_AGE. MIN_LEVEL is the community's choice
   (players who stopped at level 1-6 are rarely worth a gift), not a game rule.
2. It posts one compact message in ``channels.recruitment`` (Discord's component layout, "Components V2"):
   one line per newcomer (profile link, level, account age) with its button at the end of the line,
   PAGE_SIZE per page with ◀ / ▶, a Romanian message to copy into the gift, and where the gift button is in
   the game. While the post is still the channel's latest message it is edited in place; once anyone
   (member or bot) has sent a message after it, the run sends a new post and deletes the old one, so the
   list stays at the bottom of the channel. Either way the refreshed list opens on the first page. The
   post is public, so turning the page turns it for everyone.
3. Up to MAX_CLAIMS members can take the same newcomer. Pressing a newcomer's 🎁 adds the presser to the
   newcomer's line ("✅ @member @member"), and the button counts the members who took them ("1/3"); once
   every spot is taken it shows ✅ and is disabled for everyone, so no more members plan a gift for that
   player. ↩️ frees the presser's claims. A claim stays while the newcomer is on the list and is carried
   into the next hourly post. Players taken on other pages are listed under the page.

The bot can't see whether a gift was sent or claimed, nor how many gifts a newcomer already has (the
``welcomeGift.*`` queries are closed to API keys): a claim only says who intends to send one.

State lives in memory. Every claim is also written in the post (on its line, or in the "on other pages"
line, as member mentions, which don't notify), so after a restart the first run reads them back from the
bot's latest post in the channel, refreshes that post (edited or replaced, as above) and deletes the older
ones. The buttons are ``DynamicItem`` items, matched by
custom id, so a post made before a restart keeps working once the cog is loaded.
"""

import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands, tasks

from cogs.commands.mu_order_alignment import COUNTRY_NAME
from cogs.tasks.military_unit_contract_monitor import parse_iso
from config import config
from utils.api import warera
from utils.i18n import Translator, get_translator

logger = logging.getLogger(__name__)

REPOST_INTERVAL = timedelta(hours=1)
# the loop's tick: after a failed API read (or a restart while the API is down, when the old post's buttons
# answer "not ready") the list is retried within this many minutes
CHECK_MINUTES = 5
# a tick that lands a little early still counts as a full hour
CHECK_SLACK = timedelta(minutes=1)
# community choice (user, 2026-11-23): players who stopped below level 7 are rarely worth a gift
MIN_LEVEL = 7
# game rule (v0.28.4): newcomers are level 2-10 and their account is under 7 days old
MAX_LEVEL = 10
NEWCOMER_AGE = timedelta(days=7)
# user choice (2026-11-25): how many members can take the same newcomer
MAX_CLAIMS = 3
# slack on the ObjectId pre-filter, in case an account's id was minted a little before its createdAt
ID_MARGIN = timedelta(days=1)
# A layout message holds at most 40 components. Each newcomer line is 3 (section, text, button); the rest is
# the container, the header text, the page/other-pages text, the ◀ ↩️ ▶ row (4) and the copy/hint text:
# 8 + 3 x 10 = 38.
PAGE_SIZE = 10
# Discord's limit for all text in one layout message
TEXT_LIMIT = 4000
# messages read after a restart to find the bot's earlier posts and their claims
HISTORY_SCAN_LIMIT = 500

GUIDE_URL = "https://app.warera.io/article/6afc576611793739420ee95c"
# the game's limit for a welcome-gift message (user, 2026-11-23); the copy text must fit in it
GIFT_MESSAGE_LIMIT = 280
USER_URL = "https://app.warera.io/user/{}"
ACCENT_COLOR = discord.Color.from_rgb(46, 204, 113)
CUSTOM_ID_PREFIX = "welcome_gift:"
CLAIM_ID = CUSTOM_ID_PREFIX + "claim:{}"
RELEASE_ID = CUSTOM_ID_PREFIX + "release"
PAGE_ID = CUSTOM_ID_PREFIX + "page:{}"
# a newcomer's text (their line, or an entry of the "on other pages" line): the profile link, then the
# "<@member>" mentions, up to the end of the line or the comma before the next entry (mentions inside an entry
# are separated by spaces). The link is matched with its unescaped "](<" opening and ">)" closing: names are
# escaped (`_link_text`) and come before the link, so a player name can't imitate a profile link or a mention
# and shift a claim to another id.
_CLAIM_PATTERN = re.compile(r"(?<!\\)\]\(<https://app\.warera\.io/user/([a-f\d]{24})>\)([^\n,]*)")
_MENTION_PATTERN = re.compile(r"<@!?(\d+)>")


def _id_created_at(object_id: str) -> datetime | None:
    """Creation time stored in a Mongo ObjectId (its first 4 bytes, seconds since the epoch), or None."""
    try:
        return datetime.fromtimestamp(int(object_id[:8], 16), tz=timezone.utc)
    except (TypeError, ValueError):
        return None


def candidate_ids(entries: list[dict], now: datetime) -> list[str]:
    """User ids from ranking entries whose ObjectId says the account may still be a newcomer.

    Args:
        entries: ``ranking.getRankingPage`` items (``user`` = user id).
        now: Current time, timezone-aware UTC.

    Returns:
        The ids created after ``now - NEWCOMER_AGE - ID_MARGIN``, in ranking order, without duplicates.
    """
    oldest = now - NEWCOMER_AGE - ID_MARGIN
    ids: list[str] = []
    for entry in entries:
        user_id = str(entry.get("user") or "")
        created = _id_created_at(user_id)
        if created is not None and created >= oldest and user_id not in ids:
            ids.append(user_id)
    return ids


def select_newcomers(users: dict[str, dict], country_id: str, now: datetime) -> list[dict]:
    """The listed newcomers: citizens of ``country_id`` at MIN_LEVEL-MAX_LEVEL with an account under NEWCOMER_AGE.

    Args:
        users: User id -> ``user.getUserLite`` payload.
        country_id: Romania's country id.
        now: Current time, timezone-aware UTC.

    Returns:
        ``{"id", "username", "level", "created"}`` dicts, newest account first (user choice, 2026-11-23).
    """
    newcomers = []
    for user_id, user in users.items():
        if str(user.get("country") or "") != country_id:
            continue
        level = (user.get("leveling") or {}).get("level")
        created = parse_iso(user.get("createdAt"))
        if not isinstance(level, int) or created is None:
            continue
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        if MIN_LEVEL <= level <= MAX_LEVEL and now - created < NEWCOMER_AGE:
            newcomers.append({
                "id": str(user_id),
                "username": str(user.get("username") or user_id),
                "level": level,
                "created": created,
            })
    newcomers.sort(key=lambda item: (item["created"], item["id"]), reverse=True)
    return newcomers


def page_count(newcomers: list[dict]) -> int:
    """Number of pages for the list (at least 1)."""
    return max(1, -(-len(newcomers) // PAGE_SIZE))


def clamp_page(page: int, newcomers: list[dict]) -> int:
    """``page`` limited to the pages the list has (0-based)."""
    return min(max(0, page), page_count(newcomers) - 1)


def _link_text(text: str) -> str:
    """Escape a name for the text of a masked link, brackets included (escape_markdown leaves them)."""
    return discord.utils.escape_markdown(text).replace("[", "\\[").replace("]", "\\]")


def _mentions(member_ids: list[int]) -> str:
    """The members' mentions, separated by spaces (no commas: they separate the "on other pages" entries)."""
    return " ".join(f"<@{member_id}>" for member_id in member_ids)


async def _route(interaction: discord.Interaction, handler: str, *args):
    """Pass a button press to the job's ``handler`` method; just acknowledge it when the job isn't loaded."""
    job = interaction.client.get_cog(WelcomeGiftsJob.__cog_name__)
    if job is None:
        await interaction.response.defer()
        return
    await getattr(job, handler)(interaction, *args)


class ClaimButton(discord.ui.DynamicItem[discord.ui.Button], template=r"welcome_gift:claim:(?P<user_id>[a-f\d]{24})"):
    """A newcomer's button: takes one of the newcomer's MAX_CLAIMS spots for the member who presses it.

    It shows 🎁 and how many members took the newcomer ("1/3"); once every spot is taken it shows ✅ and is
    disabled.
    """

    def __init__(self, user_id: str, claimed: int = 0):
        """Build the button for ``user_id``; ``claimed`` is how many members took the newcomer."""
        full = claimed >= MAX_CLAIMS
        super().__init__(discord.ui.Button(
            custom_id=CLAIM_ID.format(user_id),
            emoji="✅" if full else "🎁",
            label=f"{min(claimed, MAX_CLAIMS)}/{MAX_CLAIMS}",
            style=discord.ButtonStyle.secondary if full else discord.ButtonStyle.success,
            disabled=full,
        ))
        self.user_id = user_id

    @classmethod
    async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Button, match: re.Match[str]):
        """Rebuild the button from a pressed component's custom id (works for posts made before a restart)."""
        return cls(match["user_id"])

    async def callback(self, interaction: discord.Interaction):
        """Hand the press to the job, which owns the claims."""
        await _route(interaction, "handle_claim", self.user_id)


class ReleaseButton(discord.ui.DynamicItem[discord.ui.Button], template=r"welcome_gift:release"):
    """↩️: frees every newcomer the presser took, so others can take them."""

    def __init__(self):
        """Build the release button."""
        super().__init__(discord.ui.Button(custom_id=RELEASE_ID, emoji="↩️", style=discord.ButtonStyle.secondary))

    @classmethod
    async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Button, match: re.Match[str]):
        """Rebuild the button from a pressed component's custom id."""
        return cls()

    async def callback(self, interaction: discord.Interaction):
        """Hand the press to the job, which owns the claims."""
        await _route(interaction, "handle_release")


class PageButton(discord.ui.DynamicItem[discord.ui.Button], template=r"welcome_gift:page:(?P<page>\d+)"):
    """◀ or ▶: shows another page of the post (for everyone, since the post is shared)."""

    def __init__(self, page: int, emoji: str = "▶️", disabled: bool = False):
        """Build a button that opens ``page`` (0-based)."""
        super().__init__(discord.ui.Button(
            custom_id=PAGE_ID.format(page), emoji=emoji, style=discord.ButtonStyle.primary, disabled=disabled,
        ))
        self.page = page

    @classmethod
    async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Button, match: re.Match[str]):
        """Rebuild the button from a pressed component's custom id (the target page is in it)."""
        return cls(int(match["page"]))

    async def callback(self, interaction: discord.Interaction):
        """Hand the press to the job, which redraws the post."""
        await _route(interaction, "handle_page", self.page)


def build_layout(tr: Translator, copy_tr: Translator, newcomers: list[dict], claims: dict[str, list[int]],
                 page: int) -> discord.ui.LayoutView:
    """The post for one page: header, a line per newcomer with its button, page row, message to copy and hint.

    Args:
        tr: Translator of the server language (labels).
        copy_tr: Translator of the message to copy; always Romanian, because the newcomers are Romanian.
        newcomers: Every listed newcomer, in display order.
        claims: Newcomer id -> Discord ids of the members who took them, in claim order (at most MAX_CLAIMS);
            the button of a newcomer with MAX_CLAIMS members is disabled.
        page: The page shown (0-based; clamped to the list).

    Returns:
        A LayoutView with no timeout; presses are routed by custom id (ClaimButton / ReleaseButton / PageButton).
        Every claim is written as a profile link followed by the members' mentions (on its line, or in the "on
        other pages" line), which `claims_from_message` reads back after a restart. The ◀ / ▶ buttons appear
        only when there is more than one page; their custom ids hold the target page, so they always differ.
    """
    page = clamp_page(page, newcomers)
    start = page * PAGE_SIZE
    on_page = newcomers[start:start + PAGE_SIZE]
    pages = page_count(newcomers)

    header = f"### {tr('welcome_gifts.title')}\n{tr('welcome_gifts.intro', max=MAX_CLAIMS)}"
    rows = []
    for number, newcomer in enumerate(on_page, start=start + 1):
        line = tr(
            "welcome_gifts.line",
            n=number,
            player=_link_text(newcomer["username"]),
            url=USER_URL.format(newcomer["id"]),
            level=newcomer["level"],
            joined=f"<t:{int(newcomer['created'].timestamp())}:R>",
        )
        members = claims.get(newcomer["id"]) or []
        if members:
            line += tr("welcome_gifts.taken", members=_mentions(members))
        rows.append((newcomer["id"], line, len(members)))
    bottom = (
        f"{tr('welcome_gifts.copy_title')}\n```\n{copy_tr('welcome_gifts.copy_text', guide=GUIDE_URL)}\n```\n"
        + tr("welcome_gifts.hint", min=MIN_LEVEL, max=MAX_LEVEL, days=NEWCOMER_AGE.days)
    )

    status = [tr("welcome_gifts.page", page=page + 1, pages=pages, total=len(newcomers))] if pages > 1 else []
    page_ids = {newcomer["id"] for newcomer in on_page}
    elsewhere = [
        f"{number}. [{_link_text(newcomer['username'])}](<{USER_URL.format(newcomer['id'])}>) "
        f"{_mentions(claims[newcomer['id']])}"
        for number, newcomer in enumerate(newcomers, start=1)
        if claims.get(newcomer["id"]) and newcomer["id"] not in page_ids
    ]
    if elsewhere:
        # keep the whole message under Discord's text limit; claims cut here are still kept in memory
        budget = TEXT_LIMIT - len(header) - len(bottom) - sum(len(line) for _, line, _ in rows) - 200
        prefix = tr("welcome_gifts.other_pages", list="")
        kept: list[str] = []
        for entry in elsewhere:
            if len(prefix) + len(", ".join(kept + [entry])) > budget:
                logger.warning("Welcome gifts: %d claims on other pages left out of the post", len(elsewhere) - len(kept))
                break
            kept.append(entry)
        if kept:
            status.append(tr("welcome_gifts.other_pages", list=", ".join(kept)))

    container = discord.ui.Container(accent_colour=ACCENT_COLOR)
    container.add_item(discord.ui.TextDisplay(header))
    for user_id, line, claimed in rows:
        container.add_item(discord.ui.Section(discord.ui.TextDisplay(line), accessory=ClaimButton(user_id, claimed=claimed)))
    if status:
        container.add_item(discord.ui.TextDisplay("\n".join(status)))
    controls = discord.ui.ActionRow()
    if pages > 1:
        controls.add_item(PageButton(max(0, page - 1), emoji="◀️", disabled=page == 0))
    controls.add_item(ReleaseButton())
    if pages > 1:
        # on the last page ▶ points at the page itself (disabled), which still differs from ◀'s page - 1
        controls.add_item(PageButton(min(pages - 1, page + 1), emoji="▶️", disabled=page == pages - 1))
    container.add_item(controls)
    container.add_item(discord.ui.TextDisplay(bottom))
    view = discord.ui.LayoutView(timeout=None)
    view.add_item(container)
    return view


def _walk(components) -> list:
    """Every component of a received message, nested ones included (children and section accessories)."""
    found = []
    for component in components or []:
        found.append(component)
        found.extend(_walk(getattr(component, "children", None)))
        accessory = getattr(component, "accessory", None)
        if accessory is not None:
            found.append(accessory)
    return found


def is_own_post(message: discord.Message, bot_id: int) -> bool:
    """Whether ``message`` is one of this job's posts: sent by the bot, with its accent colour and its buttons."""
    if message.author.id != bot_id:
        return False
    components = _walk(message.components)
    coloured = any(getattr(component, "accent_colour", None) == ACCENT_COLOR for component in components)
    return coloured and any(
        str(getattr(component, "custom_id", "") or "").startswith(CUSTOM_ID_PREFIX) for component in components
    )


def claims_from_message(message: discord.Message) -> dict[str, list[int]]:
    """The claims written in a post (newcomer lines and the "on other pages" line).

    Returns:
        Newcomer id -> Discord ids of the members who took them, in the order written, without duplicates and
        at most MAX_CLAIMS each. Newcomers nobody took are left out.
    """
    claims: dict[str, list[int]] = {}
    for component in _walk(message.components):
        for user_id, tail in _CLAIM_PATTERN.findall(getattr(component, "content", None) or ""):
            members = claims.setdefault(user_id, [])
            for member_id in map(int, _MENTION_PATTERN.findall(tail)):
                if member_id not in members and len(members) < MAX_CLAIMS:
                    members.append(member_id)
    return {user_id: members for user_id, members in claims.items() if members}


class WelcomeGiftsJob(commands.Cog):
    """Background job that lists newcomers for welcome gifts with claim buttons (see the module docstring)."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # newcomer id -> Discord ids of the members who took them, in claim order (at most MAX_CLAIMS, never empty)
        self._claims: dict[str, list[int]] = {}
        # every listed newcomer, in display order (what the lines and buttons are rebuilt from), and the page shown
        self._newcomers: list[dict] = []
        self._page = 0
        self._message_id: int | None = None
        # when the list was last posted (or found empty); None until the first successful run. The views are not
        # kept: they hold only DynamicItems, which discord.py dispatches by custom id, and stopping an old view
        # would unregister those DynamicItem patterns for every post (ViewStore.remove_view in discord.py 2.7).
        self._posted_at: datetime | None = None
        # earlier posts still to delete (found after a restart, or a delete that failed)
        self._stale: set[int] = set()
        # whether the channel's history was read back after the start
        self._recovered = False
        self._warned_channel = False
        # serialises the hourly repost and the button presses, which both rewrite the claims and the post
        self._lock = asyncio.Lock()
        copy_text = Translator("ro")("welcome_gifts.copy_text", guide=GUIDE_URL)
        if len(copy_text) > GIFT_MESSAGE_LIMIT:
            logger.warning("Welcome gifts: the message to copy is %d characters; the game accepts %d",
                           len(copy_text), GIFT_MESSAGE_LIMIT)
        self.welcome_gifts.start()

    async def cog_load(self):
        """Register the persistent buttons, so presses on posts made before a restart still reach the job."""
        if self.bot is not None:
            self.bot.add_dynamic_items(ClaimButton, ReleaseButton, PageButton)

    async def cog_unload(self):
        """Stop the loop and unregister the buttons when the cog is unloaded."""
        self.welcome_gifts.cancel()
        if self.bot is not None:
            self.bot.remove_dynamic_items(ClaimButton, ReleaseButton, PageButton)

    @tasks.loop(minutes=CHECK_MINUTES)
    async def welcome_gifts(self):
        """Repost the newcomer list in the recruitment channel once an hour, retrying failed reads sooner.

        Errors are logged, not raised, so one bad run never stops the loop.
        """
        # a forced /run_job runs this body from the command's task, not the loop's own task
        forced = asyncio.current_task() is not self.welcome_gifts.get_task()
        try:
            problem = await self._run(forced)
        except Exception:
            if forced:
                raise
            logger.exception("Welcome gifts run failed")
            return
        if forced and problem:
            # /run_job reports an exception as a failed run, so the member sees why nothing was posted
            raise RuntimeError(problem)

    @welcome_gifts.before_loop
    async def before_welcome_gifts(self):
        """Wait until the bot is ready, so the guild and the channel are cached."""
        await self.bot.wait_until_ready()

    def _channel(self, guild: discord.Guild):
        """The configured recruitment channel (or thread), or None (logged once)."""
        channel_id = (config.get("channels") or {}).get("recruitment")
        channel = guild.get_channel_or_thread(int(channel_id)) if channel_id else None
        if channel is None and not self._warned_channel:
            logger.warning("Welcome gifts: channels.recruitment (%s) not found in the guild", channel_id)
            self._warned_channel = True
        return channel

    async def fetch_newcomers(self, now: datetime) -> list[dict] | None:
        """Read the current newcomers from the API.

        Args:
            now: Current time, timezone-aware UTC.

        Returns:
            The newcomers (see `select_newcomers`). None when Romania, its level ranking or any candidate
            player can't be read: a partial list would drop newcomers and their claims from the post.
        """
        countries = await warera.countries.get_all()
        country = next((c for c in countries or [] if c.get("name") == COUNTRY_NAME), None)
        if country is None:
            return None
        country_id = str(country["_id"])
        entries = await warera.game.get_ranking_entries("userLevel", country_id=country_id)
        if entries is None:
            return None
        ids = candidate_ids(entries, now)
        users = (await warera.users.get_many(ids) or {}) if ids else {}
        unread = [user_id for user_id in ids if user_id not in users]
        if unread:
            logger.warning("Welcome gifts: %d of %d candidate players could not be loaded", len(unread), len(ids))
            return None
        return select_newcomers(users, country_id, now)

    async def _run(self, forced: bool = False) -> str | None:
        """One run: read the newcomers, refresh the list, delete the old posts.

        The current post is edited when it is still the channel's latest message (see `_edit_in_place`);
        otherwise the list is sent as a new post and the old one is deleted.

        Args:
            forced: Run from /run_job: repost now even if the last post is less than REPOST_INTERVAL old.

        Returns:
            None when the run did its job (posted, found no newcomers, or the hour isn't up yet), else why
            nothing was posted; a forced run raises it so /run_job shows it.
        """
        guild = self.bot.get_guild(config["guild"])
        if guild is None:
            return "guild not found"
        channel = self._channel(guild)
        if channel is None:
            return "channels.recruitment not found in the guild"
        async with self._lock:
            if not self._recovered and not await self._recover(channel):
                return "could not read the recruitment channel history"
        now = datetime.now(timezone.utc)
        # the loop ticks every CHECK_MINUTES so a failed read is retried soon; a successful post waits
        # REPOST_INTERVAL
        if not forced and self._posted_at is not None and now - self._posted_at < REPOST_INTERVAL - CHECK_SLACK:
            return None
        newcomers = await self.fetch_newcomers(now)
        if newcomers is None:
            logger.warning("Welcome gifts: newcomers could not be read; the current post is kept")
            return "newcomers could not be read from the WarEra API; the current post is kept"
        async with self._lock:
            current = {newcomer["id"] for newcomer in newcomers}
            self._claims = {
                user_id: members for user_id, members in self._claims.items() if user_id in current
            }
            old = set(self._stale)
            if self._message_id is not None:
                old.add(self._message_id)
            if newcomers:
                tr = await get_translator(guild)
                view = build_layout(tr, Translator("ro"), newcomers, self._claims, 0)
                message_id = await self._edit_in_place(channel, view)
                if message_id is None:
                    try:
                        message = await channel.send(view=view, allowed_mentions=discord.AllowedMentions.none())
                    except discord.HTTPException as exc:
                        logger.exception("Welcome gifts: could not send the newcomer list; the old post is kept")
                        return f"could not send the newcomer list ({exc}); the old post is kept"
                    message_id = message.id
                # an edited post stays; only the posts it replaces are deleted
                old.discard(message_id)
                self._message_id, self._newcomers, self._page = message_id, newcomers, 0
            else:
                self._message_id, self._newcomers, self._page = None, [], 0
            self._posted_at = now
            self._stale = set()
            for message_id in old:
                await self._delete(channel, message_id)
        return None

    async def _recover(self, channel) -> bool:
        """After a start, adopt the bot's latest post and its claims, and mark every earlier post for deletion.

        The latest post becomes the current one, so the first run can edit it in place; its buttons answer
        "not ready" until that run has loaded the newcomers (see `_check_current`).

        Returns:
            False when the history can't be read; the run is then skipped, so no second list is posted.
        """
        try:
            posts = [
                message async for message in channel.history(limit=HISTORY_SCAN_LIMIT)
                if is_own_post(message, self.bot.user.id)
            ]
        except discord.HTTPException:
            logger.exception("Welcome gifts: could not read the channel history; skipping this run")
            return False
        if posts:
            # history is newest first; the latest post holds the current claims
            for user_id, members in claims_from_message(posts[0]).items():
                self._claims.setdefault(user_id, members)
            self._message_id = posts[0].id
            self._stale.update(message.id for message in posts[1:])
        self._recovered = True
        return True

    async def _edit_in_place(self, channel, view: discord.ui.LayoutView) -> int | None:
        """Edit the current post to show ``view`` if no message was sent in the channel after it.

        Any later message that still exists counts (a member's, a bot's or another job's). One deleted since
        doesn't, since the post is then back at the bottom of the channel.

        Returns:
            The post's id when it was edited; None when there is no current post, a message follows it, or
            the history read or the edit failed (the post was deleted, for example). The caller then sends
            a new post and deletes this one.
        """
        if self._message_id is None:
            return None
        try:
            later = [message async for message in channel.history(limit=1, after=discord.Object(self._message_id))]
        except discord.HTTPException:
            logger.warning("Welcome gifts: could not check for messages after the post; sending a new one",
                           exc_info=True)
            return None
        if later:
            return None
        try:
            await channel.get_partial_message(self._message_id).edit(
                view=view, allowed_mentions=discord.AllowedMentions.none(),
            )
        except discord.NotFound:
            return None
        except discord.HTTPException:
            logger.warning("Welcome gifts: could not edit post %s; sending a new one", self._message_id,
                           exc_info=True)
            return None
        return self._message_id

    async def _delete(self, channel, message_id: int):
        """Delete an old post; one that fails (other than already gone) is retried on the next run."""
        try:
            await channel.get_partial_message(message_id).delete()
        except discord.NotFound:
            pass
        except discord.HTTPException:
            logger.warning("Welcome gifts: could not delete old post %s; retrying next run", message_id)
            self._stale.add(message_id)

    async def _refresh_post(self, interaction: discord.Interaction, tr: Translator) -> bool:
        """Redraw the pressed post from the current claims and page; False when the edit failed."""
        view = build_layout(tr, Translator("ro"), self._newcomers, self._claims, self._page)
        try:
            await interaction.edit_original_response(view=view, allowed_mentions=discord.AllowedMentions.none())
        except discord.HTTPException:
            logger.warning("Welcome gifts: could not update the post after a button press", exc_info=True)
            return False
        return True

    async def _check_current(self, interaction: discord.Interaction, tr: Translator) -> bool:
        """Whether the press came from the current post; otherwise tell the member (ephemeral) and return False.

        Until the first run after a start has loaded the newcomers, every press answers "not ready", even on
        the adopted latest post: redrawing it then would show an empty list.
        """
        if self._message_id is None or not self._recovered or self._posted_at is None:
            await interaction.followup.send(tr("welcome_gifts.reply_not_ready"), ephemeral=True)
            return False
        if interaction.message is None or interaction.message.id != self._message_id:
            await interaction.followup.send(tr("welcome_gifts.reply_expired"), ephemeral=True)
            return False
        return True

    async def handle_claim(self, interaction: discord.Interaction, user_id: str):
        """A newcomer's 🎁 was pressed: give the presser a spot, unless they hold one or all MAX_CLAIMS are taken."""
        # acknowledge first: the hourly run may hold the lock longer than Discord's 3-second window
        await interaction.response.defer()
        tr = await get_translator(interaction.guild)
        async with self._lock:
            if not await self._check_current(interaction, tr):
                return
            newcomer = next((item for item in self._newcomers if item["id"] == user_id), None)
            if newcomer is None:
                await interaction.followup.send(tr("welcome_gifts.reply_expired"), ephemeral=True)
                return
            members = self._claims.get(user_id, [])
            if interaction.user.id in members:
                await interaction.followup.send(
                    tr("welcome_gifts.reply_already", player=newcomer["username"]), ephemeral=True,
                )
                return
            if len(members) >= MAX_CLAIMS:
                # the button is disabled once full, but a press can race the redraw
                await interaction.followup.send(
                    tr("welcome_gifts.reply_full", player=newcomer["username"], max=MAX_CLAIMS,
                       members=_mentions(members)),
                    ephemeral=True, allowed_mentions=discord.AllowedMentions.none(),
                )
                return
            self._claims[user_id] = members + [interaction.user.id]
            count = len(self._claims[user_id])
            await self._refresh_post(interaction, tr)
        await interaction.followup.send(
            tr("welcome_gifts.reply_claimed", player=newcomer["username"], url=USER_URL.format(user_id),
               count=count, max=MAX_CLAIMS),
            ephemeral=True,
        )

    async def handle_release(self, interaction: discord.Interaction):
        """↩️ was pressed: free the presser's spot on every newcomer they took."""
        await interaction.response.defer()
        tr = await get_translator(interaction.guild)
        async with self._lock:
            if not await self._check_current(interaction, tr):
                return
            presser = interaction.user.id
            mine = [user_id for user_id, members in self._claims.items() if presser in members]
            if not mine:
                await interaction.followup.send(tr("welcome_gifts.reply_nothing"), ephemeral=True)
                return
            for user_id in mine:
                others = [member_id for member_id in self._claims[user_id] if member_id != presser]
                if others:
                    self._claims[user_id] = others
                else:
                    del self._claims[user_id]
            names = [item["username"] for item in self._newcomers if item["id"] in mine]
            await self._refresh_post(interaction, tr)
        await interaction.followup.send(
            tr("welcome_gifts.reply_released", players=", ".join(names) or str(len(mine))), ephemeral=True,
        )

    async def handle_page(self, interaction: discord.Interaction, page: int):
        """◀ or ▶ was pressed: show ``page`` of the current post (for everyone)."""
        await interaction.response.defer()
        tr = await get_translator(interaction.guild)
        async with self._lock:
            if not await self._check_current(interaction, tr):
                return
            previous = self._page
            self._page = clamp_page(page, self._newcomers)
            if self._page != previous and not await self._refresh_post(interaction, tr):
                # the post still shows the old page, so the next redraw must keep showing it
                self._page = previous


async def setup(bot: commands.Bot):
    """Load the job (discord.py extension entry point)."""
    await bot.add_cog(WelcomeGiftsJob(bot))
