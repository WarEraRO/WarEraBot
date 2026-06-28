import discord
from discord.ext import commands
from config import config
import utils.api as api
from datetime import datetime, timezone

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

class WarEraBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='!', intents=intents)
        self._startup_embed_sent = False
        self._shutdown_embed_sent = False

    async def send_lifecycle_embed(self, title: str, color: discord.Color, description: str | None = None):
        guild = self.get_guild(config["guild"])
        channel = guild.get_channel(config["channels"]["reports"]) if guild else None
        if channel is None:
            return

        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
            timestamp=datetime.now(timezone.utc),
        )
        if self.user:
            embed.set_footer(text=str(self.user))
        try:
            await channel.send(embed=embed)
        except discord.DiscordException:
            pass

    async def close(self):
        if not self._shutdown_embed_sent and not self.is_closed():
            self._shutdown_embed_sent = True
            await self.send_lifecycle_embed(
                "WarEraBot stopped",
                discord.Color.red(),
                "The bot client is closing or disconnected unexpectedly.",
            )
        try:
            await super().close()
        finally:
            await api.close_shared_session()

    async def setup_hook(self):
        await self.load_extension("cogs.tasks.military_unit_roles")
        await self.load_extension("cogs.tasks.commander_roles")
        await self.load_extension("cogs.tasks.skill_roles")
        await self.load_extension("cogs.tasks.takeover_countries")
        await self.load_extension("cogs.tasks.bounty_monitor")
        await self.load_extension("cogs.tasks.unidentified_members")
        await self.load_extension("cogs.tasks.buff_monitor")
        await self.load_extension("cogs.tasks.mercenary_contracts")
        await self.load_extension("cogs.tasks.article_mention")
        await self.load_extension("cogs.tasks.reddit_monitor")
        await self.load_extension("cogs.tasks.monitor_nap")

        await self.load_extension("cogs.commands.fight_status")
        await self.load_extension("cogs.commands.diplomacy")
        await self.load_extension("cogs.commands.naps")
        await self.load_extension("cogs.commands.mu_stray")
        await self.load_extension("cogs.commands.inactive_players")
        await self.load_extension("cogs.commands.promotions")
        await self.load_extension("cogs.commands.country_strays")
        await self.load_extension("cogs.commands.discordless")
        await self.load_extension("cogs.commands.help")
        await self.load_extension("cogs.commands.top_user_weekly_damages")
        await self.load_extension("cogs.commands.top_user_weekly_donations")
        await self.load_extension("cogs.commands.get_region_upgrade_cost")

        guild = discord.Object(id=config["guild"])

        # Initialize shared aiohttp session used by API helpers
        try:
            await api.get_shared_session()
        except Exception:
            pass

        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)
        await self.tree.sync()

bot = WarEraBot()

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    if not bot._startup_embed_sent:
        bot._startup_embed_sent = True
        await bot.send_lifecycle_embed(
            "WarEraBot started",
            discord.Color.green(),
            "The bot is online and background jobs are running.",
        )

token = config["token"]
if not token:
    raise RuntimeError("Missing DISCORD_TOKEN environment variable.")

api_key = config["api"]
if not api_key:
    raise RuntimeError("Missing WARERA_API_KEY environment variable.")

bot.run(token)
