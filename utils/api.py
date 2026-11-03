"""The bot's shared WarEra API client.

Every cog reads WarEra data through `warera`, for example `await warera.users.get_many(ids)`. The
client, its endpoint groups, batching, caching and errors live in the `warera` package (see
warera/README.md); this module only configures the one instance the bot uses. `run.py` closes it
on shutdown.
"""
from config import config
from warera import WarEraClient

warera = WarEraClient(api_key=config.get('api') or None)
