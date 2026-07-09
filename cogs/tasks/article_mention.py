import logging
from turtle import title

import discord
from discord.ext import commands, tasks
from bs4 import BeautifulSoup

from config import config
from utils.api import get_articles, get_shared_session


logger = logging.getLogger(__name__)

ARTICLE_CHECK_INTERVAL_MINUTES = 5
ARTICLE_LIMIT = 100
ARTICLE_BASE_URL = "https://app.warera.io/article"
MENTIONS = (
    "romania",
    "românia",
    "romaniei",
    "româniei",
    "român",
    "românii",
    "românilor",
    "roman",
    "romanii",
    "romanilor",
)

class ArticleMentionJob(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.checked_article_ids: set[str] = set()
        self.article_mention.start()

    def cog_unload(self):
        self.article_mention.cancel()

    @tasks.loop(minutes=ARTICLE_CHECK_INTERVAL_MINUTES)
    async def article_mention(self):
        """Post newly discovered articles that mention Romania."""
        session = await get_shared_session()
        articles = await get_articles(session)
        if not articles:
            return

        guild = self.bot.get_guild(config["guild"])
        channel = (
            guild.get_channel(config["channels"]["articles"])
            if guild
            else None
        )

        for article in articles[:ARTICLE_LIMIT]:
            article_id = article.get("_id")
            if not article_id:
                continue

            article_id = str(article_id)
            if article_id in self.checked_article_ids:
                continue

            title = str(article.get("title") or "").lower()
            content = str(article.get("content") or "").lower()
            plain_content = BeautifulSoup(content, "html.parser").get_text(" ")
            text = f"{title} {plain_content}".lower()
            if not any(mention in title or mention in text for mention in MENTIONS):
                self.checked_article_ids.add(article_id)
                continue

            article_url = f"{ARTICLE_BASE_URL}/{article_id}"
            embed = discord.Embed(
                description=(
                    "Romania was mentioned in an article, you might want to "
                    f"check it out -> [{article.get('title')}]({article_url})"
                ),
                color=discord.Color.blue(),
            )

            try:
                await channel.send(embed=embed)
            except discord.DiscordException:
                logger.exception(
                    "Failed to post Romania mention for article %s",
                    article_id,
                )
                continue

            self.checked_article_ids.add(article_id)

    @article_mention.before_loop
    async def before_article_mention(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(ArticleMentionJob(bot))
