from discord.ext import commands, tasks
from utils.api import get_user, get_all_countries, get_shared_session
from utils.db import init_db
from utils.computational import triangular
from config import config
import discord

ECONOMY_SKILLS = ['energy', 'companies', 'entrepreneurship', 'production']

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
            economy_skill_points = 0
            fight_skill_points = 0
            for skill_name, skill_data in user['skills'].items():
                level = skill_data['level']
                if level != 0:
                    if skill_name in ECONOMY_SKILLS:
                        economy_skill_points += triangular(level)
                    else:
                        fight_skill_points += triangular(level)
            total_skill_points = user['leveling']['totalSkillPoints']
            unspent_skill_points = user['leveling']['availableSkillPoints']

            # division by zero, should not be possible (level 1 = 4 points already)
            if total_skill_points == 0:
                continue

            percentage = ((economy_skill_points + unspent_skill_points) / total_skill_points) * 100
            is_economy = percentage > 50
            previous = self.cached_members.get(member.id)
            if previous is not None and previous == is_economy:
                continue

            if is_economy:
                if economy_role and economy_role not in member.roles:
                    await member.add_roles(economy_role, reason="Economy skill > 50")
                    stats['economy_added'].append(member.display_name)
                if fight_role and fight_role in member.roles:
                    await member.remove_roles(fight_role, reason="Economy > 50, remove fighter role")
                    stats['fight_removed'].append(member.display_name)
            else:
                if fight_role and fight_role not in member.roles:
                    await member.add_roles(fight_role, reason="Economy skill <= 50")
                    stats['fight_added'].append(member.display_name)
                if economy_role and economy_role in member.roles:
                    await member.remove_roles(economy_role, reason="Economy <= 50, remove economy role")
                    stats['economy_removed'].append(member.display_name)
            
            self.cached_members[member.id] = is_economy

        # Send a summary embed for the run only if there were changes
        channel = guild.get_channel(config["channels"]["reports"]) if guild else None
        if channel:
            total_changes = sum(len(stats.get(k, [])) for k in ('economy_added', 'economy_removed', 'fight_added', 'fight_removed'))
            if total_changes > 0:
                embed = self.build_skill_roles_embed(stats)
                if embed:
                    await channel.send(embed=embed)

    @skill_roles.before_loop
    async def before_skill_roles(self):
        await self.bot.wait_until_ready()

    def build_skill_roles_embed(self, stats: dict) -> discord.Embed:
        economy_added = stats.get('economy_added', [])
        economy_removed = stats.get('economy_removed', [])
        fight_added = stats.get('fight_added', [])
        fight_removed = stats.get('fight_removed', [])
        total = len(economy_added) + len(economy_removed) + len(fight_added) + len(fight_removed)

        # If there are no changes, return None so callers can skip sending an embed
        if total == 0:
            return None

        embed = discord.Embed(
            title="Skill Roles Updated",
            description="Summary of skill role changes:",
            color=discord.Color.orange()
        )

        def format_list(lst: list) -> str:
            if not lst:
                return "None"
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
                cur += f"\n... and {remaining} more"
            return cur

        embed.add_field(name="Economy Roles — Added", value=format_list(economy_added), inline=False)
        embed.add_field(name="Economy Roles — Removed", value=format_list(economy_removed), inline=False)
        embed.add_field(name="Fight Roles — Added", value=format_list(fight_added), inline=False)
        embed.add_field(name="Fight Roles — Removed", value=format_list(fight_removed), inline=False)
        embed.set_footer(text=f"Total changes: {total}")
        return embed


async def setup(bot: commands.Bot):
    await bot.add_cog(SkillRolesJob(bot))