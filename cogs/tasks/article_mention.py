import asyncio
import logging
import re
import time
import unicodedata

import discord
from discord.ext import commands, tasks
from bs4 import BeautifulSoup

from config import config
from utils.api import get_all_countries, get_articles, get_regions_object, get_shared_session, get_users_info
from utils.common import country_with_flag
from utils.db import get_api_ids_by_discord_id
from utils.i18n import get_translator


logger = logging.getLogger(__name__)

ARTICLE_CHECK_INTERVAL_MINUTES = 5
ARTICLE_LIMIT = 100
ARTICLE_BASE_URL = "https://app.warera.io/article"
USER_BASE_URL = "https://app.warera.io/user"
COUNTRY_NAME = "Romania"
# Romania's id and its regions; region owners change with wars, so they are re-read hourly (2 requests)
ROMANIA_IDS_TTL = 3600
# the Discord id -> player links of the users table, re-read hourly because in DynamoDB mode the read is a full scan
LINKS_TTL = 3600
# an article that keeps failing (author not loaded, missing permission, deleted channel) is given up after this many runs
MAX_SEND_ATTEMPTS = 3
EMBED_TITLE_LIMIT = 256
# Romanian authors below this level get a tip hint under their article
NEW_PLAYER_LEVEL = 25

INTERNATIONAL = "international"
ROMANIAN = "romanian"

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


def is_romanian_author(author: dict, romania_id: str, member_ids: set[str], member_names: set[str]) -> bool:
    """Whether an article's author counts as a Romanian player.

    A Romanian citizen always counts. So does a player who left Romania but is still on the server with the
    Citizen or Newbie role, recognised by the database link or, for members without one, by nickname.

    Args:
        author: The author's ``user.getUserLite`` object.
        romania_id: Romania's country id.
        member_ids: Player ids linked in the database to a Citizen or Newbie member.
        member_names: Lowercased nicknames of the Citizen or Newbie members without a database link.
    """
    if author.get("country") == romania_id:
        return True
    if str(author.get("_id")) in member_ids:
        return True
    username = str(author.get("username") or "").lower()
    return bool(username) and username in member_names


def article_kind(
    title: str,
    content: str,
    author: dict,
    romania_ids: frozenset[str],
    romania_id: str,
    member_ids: set[str],
    member_names: set[str],
) -> str | None:
    """Which embed an article gets: ROMANIAN, INTERNATIONAL, or None for no post.

    Every article by a Romanian author (see is_romanian_author) is ROMANIAN, whatever its subject. An article by
    anyone else is INTERNATIONAL when it mentions Romania (see mentions_romania).
    """
    if is_romanian_author(author, romania_id, member_ids, member_names):
        return ROMANIAN
    if mentions_romania(title, content, romania_ids):
        return INTERNATIONAL
    return None


def build_article_embed(
    tr,
    kind: str,
    article_id: str,
    title: str,
    author: dict,
    countries: dict[str, dict],
    romania_id: str | None,
) -> discord.Embed:
    """Build the embed announcing an article.

    Args:
        tr: The guild's translator.
        kind: ROMANIAN or INTERNATIONAL, as returned by article_kind.
        article_id: The article id, used for the article link.
        title: The article title; the article link is used when it is blank.
        author: The author's ``user.getUserLite`` object.
        countries: Country objects by id, for the author's citizenship. The INTERNATIONAL embed always names it;
            the ROMANIAN embed names it as the country the author resides in when it is not Romania.
        romania_id: Romania's country id.
    """
    article_url = f"{ARTICLE_BASE_URL}/{article_id}"
    embed_title = title.strip() or article_url
    if len(embed_title) > EMBED_TITLE_LIMIT:
        embed_title = embed_title[: EMBED_TITLE_LIMIT - 1] + "…"
    username = str(author.get("username") or tr("common.unknown"))
    # player names are API data, so markdown characters in them are escaped rather than translated
    player = discord.utils.escape_markdown(username)

    country_id = str(author.get("country") or "")
    country = countries.get(country_id, {}).get("name")
    if kind == INTERNATIONAL:
        description = tr(
            "article_mention.international.description",
            player=player,
            country=country_with_flag(country, True, unknown=tr("common.unknown")),
        )
        color = discord.Color.orange()
    elif country and country_id != romania_id:
        # a Romanian server member who holds another citizenship, e.g. after moving to another country
        description = tr(
            "article_mention.romanian.description_abroad",
            player=player,
            country=country_with_flag(country, True),
        )
        color = discord.Color.blue()
    else:
        description = tr("article_mention.romanian.description", player=player)
        color = discord.Color.blue()

    # the title is the embed's linked title, not a masked link, so brackets in it cannot break the link
    embed = discord.Embed(title=embed_title, url=article_url, description=description, color=color)
    author_id = author.get("_id")
    embed.set_author(
        name=username,
        url=f"{USER_BASE_URL}/{author_id}" if author_id else None,
        icon_url=author.get("avatarUrl") or None,
    )

    level = (author.get("leveling") or {}).get("level")
    if kind == ROMANIAN and isinstance(level, int) and level < NEW_PLAYER_LEVEL:
        embed.add_field(
            name=tr("article_mention.romanian.tip_name", level=level),
            value=tr("article_mention.romanian.tip_value", player=player),
            inline=False,
        )
    return embed


class ArticleMentionJob(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # article id -> hash of the title and content last checked, so an edited article is checked again
        self.checked_articles: dict[str, int] = {}
        self.posted_article_ids: set[str] = set()
        # article id -> runs that failed to load its author or to post it
        self._send_failures: dict[str, int] = {}
        self._romania_ids: frozenset[str] | None = None
        self._romania_id: str | None = None
        self._countries: dict[str, dict] = {}
        self._romania_ids_at = 0.0
        self._links: dict[str, str] | None = None
        self._links_at = 0.0
        # articles fetched by the first successful run after a restart are marked checked without posting
        self._seeded = False
        self.article_mention.start()

    def cog_unload(self):
        self.article_mention.cancel()

    async def _refresh_romania_ids(self, session) -> frozenset[str] | None:
        """Return Romania's id plus the ids of the regions it owns or started with; None if never loaded.

        The same refresh keeps ``_romania_id`` and the ``_countries`` map (id -> country) up to date. The ids are
        re-read every ROMANIA_IDS_TTL seconds. A failed refresh keeps the previous ids and is retried on the next run.
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
        self._romania_id = country_id
        self._countries = {str(country["_id"]): country for country in countries if country.get("_id")}
        self._romania_ids_at = time.monotonic()
        return self._romania_ids

    async def _romanian_members(self, guild) -> tuple[set[str], set[str]]:
        """Return the player ids and the nicknames that identify the server's Citizen and Newbie members.

        Returns:
            ``(member_ids, member_names)``: the player ids linked in the database to a Citizen or Newbie member,
            and the lowercased nicknames of the members without a link. Linked members are matched by id only,
            so a nickname that differs from the linked player cannot make another player count.

        The database links are cached for LINKS_TTL seconds. When they cannot be read, every member is matched by
        nickname for this run.
        """
        if guild is None:
            return set(), set()
        members = set()
        for role_id in (config["roles"].get("citizen"), config["roles"].get("newbie")):
            role = guild.get_role(role_id) if role_id else None
            if role:
                members.update(role.members)
        if not members:
            return set(), set()

        if self._links is None or time.monotonic() - self._links_at >= LINKS_TTL:
            try:
                self._links = await asyncio.to_thread(get_api_ids_by_discord_id)
                self._links_at = time.monotonic()
            except Exception:
                logger.exception("Could not read the linked players for article authors")
        links = self._links or {}

        member_ids, member_names = set(), set()
        for member in members:
            api_id = links.get(str(member.id))
            if api_id:
                member_ids.add(str(api_id))
            else:
                member_names.add(member.display_name.lower())
        return member_ids, member_names

    @tasks.loop(minutes=ARTICLE_CHECK_INTERVAL_MINUTES)
    async def article_mention(self):
        """Post newly discovered or edited articles by Romanian players, or by others about Romania.

        An article by a Romanian player (a Romanian citizen, or a Citizen or Newbie member of the server) is posted
        whatever its subject, with a tip hint when the author is below NEW_PLAYER_LEVEL. An article by anyone else
        is posted when its title or text names Romania or Romanians as a whole word (in several languages), or when
        it tags or links Romania or one of its regions. Each article is posted at most once; one that is not posted
        is checked again only after its title or content changes. The authors of the articles to check are fetched
        in one batched request; an article whose author cannot be loaded is retried on the next runs.

        The first successful run after a restart only marks the fetched articles as checked (and the ones it would
        post as posted), so articles posted before the restart are not posted again. A run is skipped while
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

        pending = []
        for article in articles[:ARTICLE_LIMIT]:
            if not article.get("_id"):
                continue
            article_id = str(article["_id"])
            if article_id in self.posted_article_ids:
                continue
            title = str(article.get("title") or "")
            content = str(article.get("content") or "")
            fingerprint = hash((title, content))
            if self.checked_articles.get(article_id) == fingerprint:
                continue
            pending.append((article_id, title, content, fingerprint, str(article.get("author") or "")))
        if not pending:
            self._seeded = True
            return

        guild = self.bot.get_guild(config["guild"])
        authors = await get_users_info([author_id for *_, author_id in pending if author_id], session)
        member_ids, member_names = await self._romanian_members(guild)

        if not self._seeded:
            for article_id, title, content, fingerprint, author_id in pending:
                self.checked_articles[article_id] = fingerprint
                author = authors.get(author_id)
                if author is None:
                    # an unknown author is posted only for a Romania mention, as the old monitor did
                    if mentions_romania(title, content, romania_ids):
                        self.posted_article_ids.add(article_id)
                elif article_kind(title, content, author, romania_ids, self._romania_id, member_ids, member_names):
                    self.posted_article_ids.add(article_id)
            self._seeded = True
            logger.info("Article mention monitor seeded with %d articles", len(self.checked_articles))
            return

        channel = None
        tr = None

        for article_id, title, content, fingerprint, author_id in pending:
            author = authors.get(author_id)
            if author is None:
                attempts = self._send_failures.get(article_id, 0) + 1
                logger.warning(
                    "Could not load author %s of article %s (attempt %d of %d)",
                    author_id or "(none)",
                    article_id,
                    attempts,
                    MAX_SEND_ATTEMPTS,
                )
                if attempts < MAX_SEND_ATTEMPTS:
                    self._send_failures[article_id] = attempts
                    continue
                logger.error("Giving up on article %s, its author could not be loaded", article_id)
                self._send_failures.pop(article_id, None)
                self.checked_articles[article_id] = fingerprint
                continue

            kind = article_kind(title, content, author, romania_ids, self._romania_id, member_ids, member_names)
            if kind is None:
                self.checked_articles[article_id] = fingerprint
                continue

            if channel is None:
                channel = guild.get_channel_or_thread(config["channels"]["articles"]) if guild else None
                if channel is None:
                    # left unchecked, so the article is posted once the channel can be found again
                    logger.warning("Articles channel %s not found; articles not posted", config["channels"]["articles"])
                    return
                tr = await get_translator(guild)

            embed = build_article_embed(tr, kind, article_id, title, author, self._countries, self._romania_id)
            try:
                await channel.send(embed=embed)
            except discord.DiscordException:
                attempts = self._send_failures.get(article_id, 0) + 1
                logger.exception(
                    "Failed to post %s article %s (attempt %d of %d)",
                    kind,
                    article_id,
                    attempts,
                    MAX_SEND_ATTEMPTS,
                )
                if attempts < MAX_SEND_ATTEMPTS:
                    self._send_failures[article_id] = attempts
                    continue
                logger.error("Giving up on posting %s article %s", kind, article_id)

            self._send_failures.pop(article_id, None)
            self.posted_article_ids.add(article_id)
            self.checked_articles[article_id] = fingerprint

    @article_mention.before_loop
    async def before_article_mention(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(ArticleMentionJob(bot))
