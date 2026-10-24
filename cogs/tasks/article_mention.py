import logging
import re
import time
import unicodedata

import discord
from discord.ext import commands, tasks
from bs4 import BeautifulSoup

from config import config
from utils.api import get_all_countries, get_articles, get_regions_object, get_shared_session
from utils.i18n import get_translator


logger = logging.getLogger(__name__)

ARTICLE_CHECK_INTERVAL_MINUTES = 5
ARTICLE_LIMIT = 100
ARTICLE_BASE_URL = "https://app.warera.io/article"
COUNTRY_NAME = "Romania"
# Romania's id and its regions; region owners change with wars, so they are re-read hourly (2 requests)
ROMANIA_IDS_TTL = 3600
# a post that keeps failing (missing permission, deleted channel) is given up after this many runs
MAX_SEND_ATTEMPTS = 3
EMBED_TITLE_LIMIT = 256

# Whole words naming Romania or Romanians in the languages articles are written in. Bare "roman", "romani" and
# "romane" are left out: in this feed they mean Roman, novel (de, ro) or Romance (fr, it) far more often than Romanian.
MENTION_WORDS = (
    r"rom[aâ]nia\w*", r"rom[aâ]niei",                                         # en, ro, it, fi ...
    r"român(?:[ăei]|ii|ilor|ul|ului|c\w*|esc\w*|easc\w*|e[șş]te|e[șş]ti)?",  # ro
    r"romanii", r"romanilor", r"romanesc", r"romaneasca", r"romanesti", r"romaneste",  # ro without diacritics
    r"romanian\w*",                                                           # en
    r"roumanie", r"roumain\w*",                                               # fr
    r"rumän\w*",                                                              # de, sv
    r"ruman[ií]a", r"ruman[ao]s?",                                            # es, id
    r"rumen[aeio]",                                                           # it
    r"rom[eéê]nia", r"romen[aeio]s?",                                         # pt, it
    r"roemen\w*", r"roemeen\w*", r"roemeens\w*",                              # nl
    r"rumun\w*",                                                              # pl, lt, hr, sr, bs, cs, sk
    r"romun\w*",                                                              # sl
    r"rumānij\w*", r"rumāņ\w*",                                               # lv
    r"rumeenia\w*",                                                           # et
    r"románia\w*", r"román", r"románok\w*", r"románul", r"románt",            # hu
    r"romanya\w*",                                                            # tr
    r"ρουμαν\w*", r"ρουμάν\w*",                                               # el
    r"румун\w*", r"румын\w*",                                                 # uk, sr, bg, ru
)
MENTION_PATTERN = re.compile(r"\b(?:" + "|".join(MENTION_WORDS) + r")\b")


def mentions_romania(title: str, content: str, romania_ids: frozenset[str]) -> bool:
    """Whether an article names Romania or Romanians, or tags or links Romania or one of its regions.

    Args:
        title: The article title, as plain text.
        content: The article body, as the HTML the API returns.
        romania_ids: Romania's country id and its region ids. A country or region tag is an empty
            ``<span data-content-link>`` carrying the id, so a tagged name never appears in the text.
    """
    # get_text drops attributes with the tags, so styles such as font-family "Times New Roman" never match
    text = f"{title} {BeautifulSoup(content, 'html.parser').get_text(' ')}"
    if MENTION_PATTERN.search(unicodedata.normalize("NFC", text).lower()):
        return True
    # ids are unique 24-hex ObjectIds, so finding one anywhere in the HTML means a tag or link to it
    return any(romania_id in content for romania_id in romania_ids)


class ArticleMentionJob(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # article id -> hash of the title and content last checked, so an edited article is checked again
        self.checked_articles: dict[str, int] = {}
        self.posted_article_ids: set[str] = set()
        self._send_failures: dict[str, int] = {}
        self._romania_ids: frozenset[str] | None = None
        self._romania_ids_at = 0.0
        # articles fetched by the first successful run after a restart are marked checked without posting
        self._seeded = False
        self.article_mention.start()

    def cog_unload(self):
        self.article_mention.cancel()

    async def _refresh_romania_ids(self, session) -> frozenset[str] | None:
        """Return Romania's id plus the ids of the regions it owns or started with; None if never loaded.

        The ids are re-read every ROMANIA_IDS_TTL seconds. A failed refresh keeps the previous ids and is
        retried on the next run.
        """
        if self._romania_ids is not None and time.monotonic() - self._romania_ids_at < ROMANIA_IDS_TTL:
            return self._romania_ids

        countries = await get_all_countries(session)
        regions = await get_regions_object(session)
        country_id = next(
            (
                str(country.get("_id"))
                for country in countries or []
                if str(country.get("name") or "").lower() == COUNTRY_NAME.lower() and country.get("_id")
            ),
            None,
        )
        if not country_id or regions is None:
            logger.warning("Could not load %s's country and region ids for article mentions", COUNTRY_NAME)
            return self._romania_ids

        region_ids = {
            str(region.get("_id") or region_id)
            for region_id, region in regions.items()
            if isinstance(region, dict) and country_id in (region.get("country"), region.get("initialCountry"))
        }
        self._romania_ids = frozenset({country_id, *region_ids})
        self._romania_ids_at = time.monotonic()
        return self._romania_ids

    @tasks.loop(minutes=ARTICLE_CHECK_INTERVAL_MINUTES)
    async def article_mention(self):
        """Post newly discovered or edited articles that mention Romania.

        An article mentions Romania when its title or text names Romania or Romanians as a whole word (in
        several languages), or when it tags or links Romania or one of its regions. Each article is posted at
        most once; one that does not match is checked again only after its title or content changes.

        The first successful run after a restart only marks the fetched articles as checked (and the matching
        ones as posted), so mentions posted before the restart are not posted again. A run is skipped while
        Romania's ids cannot be loaded, so tagged mentions are not marked checked unseen.
        """
        session = await get_shared_session()
        # only the newest ARTICLE_LIMIT are read, so the rest of the feed is not paged through
        articles = await get_articles(session, max_items=ARTICLE_LIMIT)
        if not articles:
            return
        romania_ids = await self._refresh_romania_ids(session)
        if romania_ids is None:
            return

        if not self._seeded:
            for article in articles[:ARTICLE_LIMIT]:
                if not article.get("_id"):
                    continue
                article_id = str(article["_id"])
                title = str(article.get("title") or "")
                content = str(article.get("content") or "")
                self.checked_articles[article_id] = hash((title, content))
                if mentions_romania(title, content, romania_ids):
                    self.posted_article_ids.add(article_id)
            self._seeded = True
            logger.info("Article mention monitor seeded with %d articles", len(self.checked_articles))
            return

        guild = self.bot.get_guild(config["guild"])
        channel = None
        tr = None

        for article in articles[:ARTICLE_LIMIT]:
            article_id = article.get("_id")
            if not article_id:
                continue

            article_id = str(article_id)
            if article_id in self.posted_article_ids:
                continue

            title = str(article.get("title") or "")
            content = str(article.get("content") or "")
            fingerprint = hash((title, content))
            if self.checked_articles.get(article_id) == fingerprint:
                continue
            if not mentions_romania(title, content, romania_ids):
                self.checked_articles[article_id] = fingerprint
                continue

            if channel is None:
                channel = guild.get_channel_or_thread(config["channels"]["articles"]) if guild else None
                if channel is None:
                    # left unchecked, so the article is posted once the channel can be found again
                    logger.warning("Articles channel %s not found; article mentions not posted", config["channels"]["articles"])
                    return
                tr = await get_translator(guild)

            article_url = f"{ARTICLE_BASE_URL}/{article_id}"
            embed_title = title.strip() or article_url
            if len(embed_title) > EMBED_TITLE_LIMIT:
                embed_title = embed_title[: EMBED_TITLE_LIMIT - 1] + "…"
            # the title is the embed's linked title, not a masked link, so brackets in it cannot break the link
            embed = discord.Embed(
                title=embed_title,
                url=article_url,
                description=tr("article_mention.mentioned"),
                color=discord.Color.blue(),
            )

            try:
                await channel.send(embed=embed)
            except discord.DiscordException:
                attempts = self._send_failures.get(article_id, 0) + 1
                logger.exception(
                    "Failed to post Romania mention for article %s (attempt %d of %d)",
                    article_id,
                    attempts,
                    MAX_SEND_ATTEMPTS,
                )
                if attempts < MAX_SEND_ATTEMPTS:
                    self._send_failures[article_id] = attempts
                    continue
                logger.error("Giving up on posting Romania mention for article %s", article_id)

            self._send_failures.pop(article_id, None)
            self.posted_article_ids.add(article_id)
            self.checked_articles[article_id] = fingerprint

    @article_mention.before_loop
    async def before_article_mention(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(ArticleMentionJob(bot))
