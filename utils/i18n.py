"""Translations for every user-facing text the bot sends.

Strings live in locales/<code>.json as nested objects and are looked up by dotted key
("fight_status.title"). Each server picks its language with /setlang; it is stored per guild in the
guild_settings table (utils/db.py) and read back from there whenever a message is built, so a change
applies to the next message. English is the default and the fallback for any key a language lacks.

Usage:
    tr = await get_translator(interaction.guild_id)   # or a discord.Guild; None means config["guild"]
    tr("fight_status.title")
    tr("common.page_total", page=1, pages=3, total=40)
    tr.plural("pills.footer_economy", count)            # picks the .one / .few / .other form
    tr.strftime(when, tr("formats.day_month"))          # %a %A %b %B come from the locale

Slash-command descriptions are written in English in the decorators (Discord needs a default) and are
localized for Romanian Discord clients from the "slash" section of ro.json by CommandTranslator.
"""
import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path

import discord
from discord import app_commands

from config import config
from utils import db

logger = logging.getLogger(__name__)

DEFAULT_LANGUAGE = "en"
# language code -> name offered by /setlang
LANGUAGES: dict[str, str] = {"en": "English", "ro": "Romanian"}
# other names /setlang accepts when typed by hand
_LANGUAGE_ALIASES = {"română": "ro", "romana": "ro", "româna": "ro", "engleza": "en", "engleză": "en"}
# Discord client locales that get localized slash-command descriptions
_DISCORD_LOCALES = {discord.Locale.romanian: "ro"}
# Discord's limit for command and option descriptions
_DESCRIPTION_LIMIT = 100

LOCALES_DIR = Path(__file__).resolve().parent.parent / "locales"


def _flatten(node: dict, prefix: str = "") -> dict:
    flat = {}
    for key, value in node.items():
        path = f"{prefix}{key}"
        if isinstance(value, dict):
            flat.update(_flatten(value, f"{path}."))
        else:
            flat[path] = value
    return flat


def _load() -> dict[str, dict]:
    strings = {}
    for code in LANGUAGES:
        path = LOCALES_DIR / f"{code}.json"
        try:
            with open(path, "r", encoding="utf-8") as file:
                strings[code] = _flatten(json.load(file))
        except (OSError, ValueError):
            logger.exception("Could not load translations from %s", path)
            strings[code] = {}
    return strings


_STRINGS = _load()


def _lookup(lang: str | None, key: str):
    for code in (lang, DEFAULT_LANGUAGE):
        value = _STRINGS.get(code or "", {}).get(key)
        if value is not None:
            return value
    logger.warning("Missing translation key %r", key)
    return None


def t(lang: str | None, key: str, **kwargs) -> str:
    """The text for `key` in `lang` (English when missing there), with {placeholders} filled from kwargs."""
    template = _lookup(lang, key)
    if not isinstance(template, str):
        return key
    try:
        return template.format(**kwargs)
    except (KeyError, IndexError, ValueError):
        logger.warning("Bad placeholders in %r for language %r", key, lang)
        english = _STRINGS[DEFAULT_LANGUAGE].get(key)
        try:
            return english.format(**kwargs) if isinstance(english, str) else key
        except (KeyError, IndexError, ValueError):
            return template


def _plural_form(lang: str, count) -> str:
    try:
        n = abs(int(count))
    except (TypeError, ValueError):
        return "other"
    if lang == "ro":
        # Romanian (CLDR): 1 membru; 0, 2-19 membri (also 102-119, …); 20+ de membri
        if n == 1:
            return "one"
        if n == 0 or 2 <= n % 100 <= 19:
            return "few"
        return "other"
    return "one" if n == 1 else "other"


def normalize_language(value: str | None) -> str | None:
    """The language code for a code or name such as "ro", "Romanian" or "română"; None if unsupported."""
    wanted = (value or "").strip().casefold()
    if wanted in LANGUAGES:
        return wanted
    for code, name in LANGUAGES.items():
        if wanted == name.casefold():
            return code
    return _LANGUAGE_ALIASES.get(wanted)


class Translator:
    """t() bound to one language, so builders can take a single `tr` argument."""

    __slots__ = ("lang",)

    def __init__(self, lang: str | None = None):
        self.lang = lang if lang in LANGUAGES else DEFAULT_LANGUAGE

    def __call__(self, key: str, **kwargs) -> str:
        return t(self.lang, key, **kwargs)

    def plural(self, key: str, count, **kwargs) -> str:
        """`key.one` / `key.few` / `key.other` for `count` ({count} is filled in); falls back to `.other`."""
        form = _plural_form(self.lang, count)
        if _STRINGS.get(self.lang, {}).get(f"{key}.{form}") is None and _STRINGS[DEFAULT_LANGUAGE].get(f"{key}.{form}") is None:
            form = "other"
        return t(self.lang, f"{key}.{form}", count=count, **kwargs)

    def strftime(self, value: datetime, fmt: str) -> str:
        """datetime.strftime with day and month names (%a %A %b %B) in this language."""
        names = {
            "%a": ("dates.days_short", value.weekday()),
            "%A": ("dates.days", value.weekday()),
            "%b": ("dates.months_short", value.month - 1),
            "%B": ("dates.months", value.month - 1),
        }
        for directive, (key, index) in names.items():
            if directive in fmt:
                values = _lookup(self.lang, key)
                if isinstance(values, list) and index < len(values):
                    fmt = fmt.replace(directive, str(values[index]).replace("%", "%%"))
        return value.strftime(fmt)


def _guild_id(guild) -> int | None:
    if guild is None:
        return config.get("guild")
    if isinstance(guild, discord.Guild):
        return guild.id
    try:
        return int(guild)
    except (TypeError, ValueError):
        return config.get("guild")


async def get_guild_language(guild=None) -> str:
    """The language saved for a guild (a discord.Guild or an id); None means the configured guild.

    Read from the database on every call, so it is never stale; English when nothing is saved
    or the database cannot be read."""
    guild_id = _guild_id(guild)
    if guild_id is None:
        return DEFAULT_LANGUAGE
    try:
        language = await asyncio.to_thread(db.get_guild_language, guild_id)
    except Exception:
        logger.exception("Could not read the language of guild %s, using %s", guild_id, DEFAULT_LANGUAGE)
        return DEFAULT_LANGUAGE
    return language if language in LANGUAGES else DEFAULT_LANGUAGE


async def set_guild_language(guild_id: int, language: str) -> None:
    if language not in LANGUAGES:
        raise ValueError(f"Unsupported language {language!r}")
    await asyncio.to_thread(db.set_guild_language, guild_id, language)


async def get_translator(guild=None) -> Translator:
    """A Translator in the guild's saved language. Interactions without a guild (DMs) and background jobs
    pass None and use the configured guild, which is the server that triggered them."""
    return Translator(await get_guild_language(guild))


class CommandTranslator(app_commands.Translator):
    """Localizes slash-command and option descriptions from the "slash" section of the locale files.

    Keys: slash.<command path>.description and slash.<command path>.params.<option>, where the path is the
    command's qualified name with dots ("slash.nap.add.description"). Names are never translated, so
    commands keep working the same everywhere."""

    async def translate(
        self, string: app_commands.locale_str, locale: discord.Locale, context: app_commands.TranslationContext
    ) -> str | None:
        lang = _DISCORD_LOCALES.get(locale)
        if lang is None:
            return None
        location = context.location
        if location in (
            app_commands.TranslationContextLocation.command_description,
            app_commands.TranslationContextLocation.group_description,
        ):
            key = f"slash.{context.data.qualified_name.replace(' ', '.')}.description"
        elif location is app_commands.TranslationContextLocation.parameter_description:
            parameter = context.data
            key = f"slash.{parameter.command.qualified_name.replace(' ', '.')}.params.{parameter.name}"
        else:
            return None
        value = _STRINGS.get(lang, {}).get(key)
        return value[:_DESCRIPTION_LIMIT] if isinstance(value, str) and value else None
