import html
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

import aiohttp
import discord
from aiohttp import ClientError
from discord.ext import commands, tasks

from config import config


logger = logging.getLogger(__name__)

REDDIT_CHECK_INTERVAL_MINUTES = 5
SUBREDDIT = "RomaniaWarEra"
POST_LIMIT = 100
NOTIFIED_POST_CACHE_LIMIT = 100
POST_MAX_AGE = timedelta(days=1)
# messages read back from the Reddit channel to find the posts this bot already announced
HISTORY_SCAN_LIMIT = 100
POST_ID_PATTERN = re.compile(r"/comments/([A-Za-z0-9]+)")
REDDIT_JSON_URLS = (
    f"https://old.reddit.com/r/{SUBREDDIT}/new.json",
    f"https://www.reddit.com/r/{SUBREDDIT}/new/.json",
    f"https://www.reddit.com/r/{SUBREDDIT}/new.json",
)
REDDIT_RSS_URL = f"https://www.reddit.com/r/{SUBREDDIT}/new.rss"
REDDIT_HEADERS = {
    "User-Agent": "WarEraBot/1.0 (RomaniaWarEra Discord monitor)",
    "Accept": "application/json,text/plain,*/*",
    "Accept-Language": "en-US,en;q=0.9",
}

class RedditMonitorJob(commands.Cog):
    """Announce new r/RomaniaWarEra submissions in the configured Reddit channel."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.notified_posts: dict[str, float] = {}
        # posts fetched by the first successful run after a restart are recorded without posting
        self._seeded = False
        self._session: aiohttp.ClientSession | None = None
        self.reddit_monitor.start()

    async def cog_unload(self):
        """Stop the polling loop and close the cog's Reddit HTTP session."""
        self.reddit_monitor.cancel()
        if self._session is not None and not self._session.closed:
            await self._session.close()

    async def _get_session(self) -> aiohttp.ClientSession:
        """Return this cog's Reddit-only HTTP session, creating it if needed.

        Reddit requests must not go through ``utils.api.warera``: its session
        belongs to the WarEra client, which adds the WarEra ``X-API-Key``
        header to its requests, and the key must never reach a third-party host.
        """
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    @tasks.loop(minutes=REDDIT_CHECK_INTERVAL_MINUTES)
    async def reddit_monitor(self):
        """Post newly discovered r/RomaniaWarEra submissions to reddit.

        The first successful fetch after a restart only records the recent posts, so posts
        announced before the restart are not announced (and the social role not pinged) again.
        Because Reddit's listings can lag (a post missing from that first fetch would otherwise
        look new later), any post this bot already linked in the channel is skipped too.
        """
        now = datetime.now(timezone.utc)
        cutoff = now - POST_MAX_AGE
        self._prune_notified_posts(cutoff)

        posts = await self._fetch_recent_posts()
        if not posts:
            return

        if not self._seeded:
            for post in posts:
                post_id = str(post.get("id") or "")
                created_utc = post.get("created_utc")
                if post_id and isinstance(created_utc, (int, float)) and created_utc >= cutoff.timestamp():
                    self.notified_posts[post_id] = float(created_utc)
            self._trim_notified_posts()
            self._seeded = True
            logger.info("Reddit monitor seeded with %d posts", len(self.notified_posts))
            return

        guild = self.bot.get_guild(config["guild"])
        channel = guild.get_channel(config["channels"]["reddit"]) if guild else None
        if channel is None:
            return

        candidates = []
        for post in reversed(posts):
            post_id = str(post.get("id") or "")
            created_utc = post.get("created_utc")
            if not post_id or not isinstance(created_utc, (int, float)):
                continue

            created_at = datetime.fromtimestamp(created_utc, tz=timezone.utc)
            if created_at < cutoff:
                continue

            if post_id in self.notified_posts:
                continue

            candidates.append((post_id, created_utc, post))

        if not candidates:
            return

        announced = await self._announced_post_ids(channel)
        if announced is None:
            # without the channel history a repost cannot be ruled out; retry next run
            return

        for post_id, created_utc, post in candidates:
            if post_id in announced:
                self.notified_posts[post_id] = float(created_utc)
                self._trim_notified_posts()
                continue

            post_link = self._build_post_link(post)
            if not post_link:
                continue

            social_role_id = config.get("roles", {}).get("social")
            content = f"<@&{social_role_id}>\n{post_link}" if social_role_id else post_link
            try:
                await channel.send(
                    content=content,
                    allowed_mentions=discord.AllowedMentions(roles=True),
                )
            except discord.DiscordException:
                logger.exception("Failed to post Reddit submission %s", post_id)
                continue

            self.notified_posts[post_id] = float(created_utc)
            self._trim_notified_posts()

    async def _announced_post_ids(self, channel: discord.abc.Messageable) -> set[str] | None:
        """Return the IDs of the Reddit posts this bot linked in the channel's recent messages.

        The channel itself is the record that survives restarts, so this catches posts whose
        announcement the in-memory cache has lost.

        Args:
            channel: The configured Reddit announcement channel.

        Returns:
            The post IDs found in the bot's last ``HISTORY_SCAN_LIMIT`` channel messages,
            or ``None`` when the history cannot be read.
        """
        me = self.bot.user
        if me is None:
            return None

        announced: set[str] = set()
        try:
            async for message in channel.history(limit=HISTORY_SCAN_LIMIT):
                if message.author.id == me.id:
                    announced.update(POST_ID_PATTERN.findall(message.content))
        except discord.DiscordException:
            logger.exception("Could not read the Reddit channel history")
            return None
        return announced

    async def _fetch_recent_posts(self) -> list[dict]:
        session = await self._get_session()
        params = {"limit": str(POST_LIMIT), "raw_json": "1"}

        for url in REDDIT_JSON_URLS:
            try:
                async with session.get(url, headers=REDDIT_HEADERS, params=params) as response:
                    if response.status in {403, 429}:
                        logger.warning(
                            "Reddit blocked r/%s fetch from %s with HTTP %s",
                            SUBREDDIT,
                            url,
                            response.status,
                        )
                        continue

                    response.raise_for_status()
                    payload = await response.json(content_type=None)
                    return self._posts_from_json_payload(payload)
            except (ClientError, TimeoutError, ValueError):
                logger.warning("Failed to fetch r/%s posts from %s", SUBREDDIT, url)

        return await self._fetch_recent_posts_from_rss()

    def _posts_from_json_payload(self, payload: dict) -> list[dict]:
        children = payload.get("data", {}).get("children", [])
        posts = []
        for child in children:
            post = child.get("data") if isinstance(child, dict) else None
            if isinstance(post, dict):
                posts.append(post)
        return posts

    async def _fetch_recent_posts_from_rss(self) -> list[dict]:
        session = await self._get_session()
        params = {"limit": str(POST_LIMIT)}
        headers = {
            **REDDIT_HEADERS,
            "Accept": "application/atom+xml,application/xml,text/xml,*/*",
        }

        try:
            async with session.get(REDDIT_RSS_URL, headers=headers, params=params) as response:
                if response.status in {403, 429}:
                    logger.warning(
                        "Reddit blocked r/%s RSS fetch with HTTP %s",
                        SUBREDDIT,
                        response.status,
                    )
                    return []

                response.raise_for_status()
                text = await response.text()
        except (ClientError, TimeoutError):
            logger.warning("Failed to fetch r/%s posts from RSS", SUBREDDIT)
            return []

        try:
            root = ET.fromstring(text)
        except ET.ParseError:
            logger.warning("Failed to parse r/%s RSS response", SUBREDDIT)
            return []

        return self._posts_from_rss_root(root)

    def _posts_from_rss_root(self, root: ET.Element) -> list[dict]:
        posts = []
        namespace = {"atom": "http://www.w3.org/2005/Atom"}

        for entry in root.findall("atom:entry", namespace):
            title = entry.findtext("atom:title", default="", namespaces=namespace)
            author = entry.findtext("atom:author/atom:name", default="unknown", namespaces=namespace)
            published = entry.findtext("atom:published", default="", namespaces=namespace)
            summary = entry.findtext("atom:content", default="", namespaces=namespace)

            link = ""
            for link_node in entry.findall("atom:link", namespace):
                href = link_node.attrib.get("href", "")
                if "/comments/" in href:
                    link = href
                    break

            match = re.search(r"/comments/([^/]+)/", link)
            if not match:
                continue

            try:
                created_at = datetime.fromisoformat(published.replace("Z", "+00:00"))
            except ValueError:
                continue

            posts.append(
                {
                    "id": match.group(1),
                    "title": title,
                    "author": author,
                    "created_utc": created_at.timestamp(),
                    "permalink": link.replace("https://www.reddit.com", ""),
                    "selftext": self._clean_rss_content(summary),
                }
            )

        return posts

    def _clean_rss_content(self, content: str) -> str:
        text = re.sub(r"<[^>]+>", " ", content)
        text = html.unescape(text)
        text = re.sub(r"\s+", " ", text).strip()
        text = re.sub(
            r"\bsubmitted by\s+/u/.*?(?:\[link\]\s*)?(?:\[comments\]\s*)?$",
            "",
            text,
            flags=re.IGNORECASE,
        )
        return text.strip()

    def _build_post_link(self, post: dict) -> str:
        permalink = str(post.get("permalink") or "")
        url = f"https://www.reddit.com{permalink}" if permalink else str(post.get("url") or "")
        return f"{url}" if url else ""

    def _prune_notified_posts(self, cutoff: datetime):
        cutoff_timestamp = cutoff.timestamp()
        self.notified_posts = {
            post_id: created_utc
            for post_id, created_utc in self.notified_posts.items()
            if created_utc >= cutoff_timestamp
        }
        self._trim_notified_posts()

    def _trim_notified_posts(self):
        if len(self.notified_posts) <= NOTIFIED_POST_CACHE_LIMIT:
            return

        self.notified_posts = dict(
            sorted(
                self.notified_posts.items(),
                key=lambda item: item[1],
                reverse=True,
            )[:NOTIFIED_POST_CACHE_LIMIT]
        )

    @reddit_monitor.before_loop
    async def before_reddit_monitor(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(RedditMonitorJob(bot))
