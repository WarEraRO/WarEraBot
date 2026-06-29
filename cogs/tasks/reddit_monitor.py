import html
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

import discord
from aiohttp import ClientError
from discord.ext import commands, tasks

from config import config
from utils.api import get_shared_session


logger = logging.getLogger(__name__)

REDDIT_CHECK_INTERVAL_MINUTES = 5
SUBREDDIT = "RomaniaWarEra"
POST_LIMIT = 100
NOTIFIED_POST_CACHE_LIMIT = 100
POST_MAX_AGE = timedelta(days=1)
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
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.notified_posts: dict[str, float] = {}
        self.reddit_monitor.start()

    def cog_unload(self):
        self.reddit_monitor.cancel()

    @tasks.loop(minutes=REDDIT_CHECK_INTERVAL_MINUTES)
    async def reddit_monitor(self):
        """Post newly discovered r/RomaniaWarEra submissions to reddit."""
        now = datetime.now(timezone.utc)
        cutoff = now - POST_MAX_AGE
        self._prune_notified_posts(cutoff)

        posts = await self._fetch_recent_posts()
        if not posts:
            return

        guild = self.bot.get_guild(config["guild"])
        channel = guild.get_channel(config["channels"]["reddit"]) if guild else None
        if channel is None:
            return

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

    async def _fetch_recent_posts(self) -> list[dict]:
        session = await get_shared_session()
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
        session = await get_shared_session()
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
