from discord.ext import commands, tasks
from utils.api import get_user, get_all_countries, get_shared_session
from utils.db import init_db
from utils.computational import is_economy_build
from utils.i18n import Translator, get_translator
from config import config
import discord

class SkillRolesJob(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.cached_members = {}
        self.countries = None
        # Ensure database/table exists
        try:
            init_db()
        except Exception:
            pass
        self.skill_roles.start()

    def cog_unload(self):
        self.skill_roles.cancel()

    async def get_countries(self):
        session = await get_shared_session()
        return await get_all_countries(session)
    
    @tasks.loop(hours=1)
    async def skill_roles(self):
        """Parses all members of the server that hold the citizen role and assigns
           roles based on their assigned skills (economy or fighter)
        """
        guild = self.bot.get_guild(config['guild'])
        if guild is None:
            return
        citizen = guild.get_role(config['roles']['citizen'])
        economy_role = guild.get_role(config['roles']['economy'])
        fight_role = guild.get_role(config['roles']['fight'])
        
        members = citizen.members if citizen else []
        tr = await get_translator(guild)
        stats = {
            'economy_added': [],
            'economy_removed': [],
            'fight_added': [],
            'fight_removed': [],
        }
        session = await get_shared_session()
        for member in members:
            user = await get_user(member.display_name, session)
            if user is None:
                continue
            is_economy = is_economy_build(user)
            # no skill points, should not be possible (level 1 = 4 points already)
            if is_economy is None:
                continue
            previous = self.cached_members.get(member.id)
            if previous is not None and previous == is_economy:
                continue

            if is_economy:
                if economy_role and economy_role not in member.roles:
                    await member.add_roles(economy_role, reason=tr("skill_roles.reason_economy_added"))
                    stats['economy_added'].append(member.display_name)
                if fight_role and fight_role in member.roles:
                    await member.remove_roles(fight_role, reason=tr("skill_roles.reason_fight_removed"))
                    stats['fight_removed'].append(member.display_name)
            else:
                if fight_role and fight_role not in member.roles:
                    await member.add_roles(fight_role, reason=tr("skill_roles.reason_fight_added"))
                    stats['fight_added'].append(member.display_name)
                if economy_role and economy_role in member.roles:
                    await member.remove_roles(economy_role, reason=tr("skill_roles.reason_economy_removed"))
                    stats['economy_removed'].append(member.display_name)
            
            self.cached_members[member.id] = is_economy

        # Send a summary embed for the run only if there were changes
        channel = guild.get_channel(config["channels"]["reports"]) if guild else None
        if channel:
            total_changes = sum(len(stats.get(k, [])) for k in ('economy_added', 'economy_removed', 'fight_added', 'fight_removed'))
            if total_changes > 0:
                embed = self.build_skill_roles_embed(stats, tr)
                if embed:
                    await channel.send(embed=embed)

    @skill_roles.before_loop
    async def before_skill_roles(self):
        await self.bot.wait_until_ready()

    def build_skill_roles_embed(self, stats: dict, tr: Translator) -> discord.Embed:
        economy_added = stats.get('economy_added', [])
        economy_removed = stats.get('economy_removed', [])
        fight_added = stats.get('fight_added', [])
        fight_removed = stats.get('fight_removed', [])
        total = len(economy_added) + len(economy_removed) + len(fight_added) + len(fight_removed)

        # If there are no changes, return None so callers can skip sending an embed
        if total == 0:
            return None

        embed = discord.Embed(
            title=tr("skill_roles.title"),
            description=tr("skill_roles.description"),
            color=discord.Color.orange()
        )

        def format_list(lst: list) -> str:
            if not lst:
                return tr("common.none")
            lines = [f"* {n}" for n in lst]
            cur = ""
            count = 0
            for line in lines:
                if len(cur) + len(line) + 1 > 1000:
                    break
                cur += line + "\n"
                count += 1
            remaining = len(lines) - count
            if remaining > 0:
                cur = cur.rstrip("\n")
                cur += "\n" + tr("common.and_more", count=remaining)
            return cur

        embed.add_field(name=tr("skill_roles.economy_added"), value=format_list(economy_added), inline=False)
        embed.add_field(name=tr("skill_roles.economy_removed"), value=format_list(economy_removed), inline=False)
        embed.add_field(name=tr("skill_roles.fight_added"), value=format_list(fight_added), inline=False)
        embed.add_field(name=tr("skill_roles.fight_removed"), value=format_list(fight_removed), inline=False)
        embed.set_footer(text=tr("common.total_changes", total=total))
        return embed


async def setup(bot: commands.Bot):
    await bot.add_cog(SkillRolesJob(bot))