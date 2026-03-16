import discord
from discord.ext import commands
from config import config

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

class WarEraBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='!', intents=intents)

    async def setup_hook(self):
        await self.load_extension("cogs.tasks.jobs")
        await self.load_extension("cogs.commands.fight_status")
        guild = discord.Object(id=config["guild"])

        self.tree.clear_commands(guild=guild)   # remove guild commands
        await self.tree.sync(guild=guild)       # apply removal

        await self.tree.sync()

bot = WarEraBot()

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

token = config["token"]
if not token:
    raise RuntimeError("Missing DISCORD_TOKEN environment variable.")

api_key = config["api"]
if not api_key:
    raise RuntimeError("Missing WARERA_API_KEY environment variable.")

bot.run(token)