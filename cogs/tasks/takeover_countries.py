from discord.ext import commands, tasks
import discord
from utils.api import get_shared_session, get_country_government, get_all_countries
from utils.db import init_db
from config import config

class TakeoverCountriesJob(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.countries = None
        try:
            init_db()
        except Exception:
            pass
        self.takeover_countries.start()

    def cog_unload(self):
        self.takeover_countries.cancel()

    async def get_countries(self):
        session = await get_shared_session()
        return await get_all_countries(session)
    
    @tasks.loop(minutes=5)
    async def takeover_countries(self):
        """Parses all countries of the server and posts any country that can be taken over.
        """
        if self.countries is None:
            self.countries = await self.get_countries()

        guild = self.bot.get_guild(config['guild'])
        active_countries = config.get('active_countries', [])
        session = await get_shared_session()
        empty_countries = []
        countries_list = self.countries or []
        for country in countries_list:
            if active_countries is not None and len(active_countries) != 0:
                if country['name'] in active_countries:
                    continue
            government = await get_country_government(country['_id'], session)
            # country is empty, api displays only _id, country, __v, and congressMembers keys .
            if government is not None and len(government.keys()) == 4 and len(government['congressMembers']) == 0:
                empty_countries.append((country['name'], country['_id']))
        # Always send an embed reporting the results (may be empty)
        if len(empty_countries) == 0:
            return
        channel = guild.get_channel(config["channels"]["public"]) if guild else None
        if channel:
            embed = self.build_takeover_embed(empty_countries)
            await channel.send(embed=embed)

    @takeover_countries.before_loop
    async def before_takeover_countries(self):
        await self.bot.wait_until_ready()

    def build_takeover_embed(self, countries) -> discord.Embed:
        if not countries:
            embed = discord.Embed(
                title="Takeover Countries Check",
                description="No takeover countries were found.",
                color=discord.Color.green()
            )
            embed.set_footer(text="Total: 0")
            return embed

        embed = discord.Embed(
            title="Takeover Countries Found",
            description="The following countries can be captured:",
            color=discord.Color.orange()
        )
        lines = [f"* {c[0]} ('https://app.warera.io/country/{c[1]}')" for c in countries]
        chunk = ""
        for line in lines:
            if len(chunk) + len(line) > 1000:
                embed.add_field(name="Countries", value=chunk, inline=False)
                chunk = ""
            chunk += line + "\n"
        if chunk:
            embed.add_field(name="Countries", value=chunk, inline=False)
        embed.set_footer(text=f"Total: {len(countries)}")
        return embed

async def setup(bot: commands.Bot):
    await bot.add_cog(TakeoverCountriesJob(bot))