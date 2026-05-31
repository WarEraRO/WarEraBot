from discord.ext import commands, tasks
from utils.api import get_shared_session, get_military_unit, get_user_info
from utils.db import init_db, save_user, get_record_by_api_id, find_api_id_by_discord_id
from config import config
import discord

class CommanderRolesJob(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        try:
            init_db()
        except Exception:
            pass
        self.commander_roles.start()

    def cog_unload(self):
        self.commander_roles.cancel()
    
    @tasks.loop(hours=3)
    async def commander_roles(self):
        """Syncs the Discord commander role with commanders configured in all military units."""
        guild = self.bot.get_guild(config['guild'])
        if guild is None:
            return

        commander_role = guild.get_role(config['roles']['commander'])
        if commander_role is None:
            return

        session = await get_shared_session()
        military_units = config.get('military_units', [])
        commander_ids = set()

        # Gather commander api ids from all military units
        for unit in military_units:
            try:
                mu_data = await get_military_unit(unit['id'], session)
            except Exception:
                mu_data = None
            if not mu_data:
                continue
            try:
                commanders = (mu_data.get('roles') or {}).get('commanders') or []
            except Exception:
                commanders = []
            for cid in commanders:
                if cid:
                    commander_ids.add(cid)

        # Build lookup maps for guild members
        citizen = guild.get_role(config['roles']['citizen'])
        newbie = guild.get_role(config['roles']['newbie'])

        members = set()
        if citizen:
            members.update(citizen.members)
        if newbie:
            members.update(newbie.members)
        name_map = {m.name.lower(): m for m in members}
        display_map = {m.display_name.lower(): m for m in members}

        desired_members = set()
        added = []
        removed = []

        # For each commander api id, try to find the corresponding guild member
        for api_id in commander_ids:
            try:
                rec = get_record_by_api_id(api_id)
            except Exception:
                continue

            member = None
            if rec:
                discord_id = rec.get('discord_id')
                if discord_id:
                    member = guild.get_member(int(discord_id))
                if member is None:
                    discord_username = (rec.get('discord_username') or '').lower() if rec.get('discord_username') else None
                    display_name = (rec.get('display_name') or '').lower() if rec.get('display_name') else None
                    if discord_username and discord_username in name_map:
                        member = name_map[discord_username]
                    elif display_name and display_name in display_map:
                        member = display_map[display_name]

            # If not found via DB, try to resolve via API username and match display_name
            if member is None:
                try:
                    info = await get_user_info(api_id, session)
                except Exception:
                    continue
                if isinstance(info, dict):
                    username = (info.get('username') or '').lower()
                    if username and username in display_map:
                        member = display_map[username]
                        try:
                            save_user(member.name, member.display_name, api_id, member.id)
                        except Exception:
                            pass

            if member:
                desired_members.add(member)

        # Assign commander role to desired members (only if they have citizen or newbie role)
        for member in desired_members:
            has_base_role = (citizen and citizen in member.roles) or (newbie and newbie in member.roles)
            if not has_base_role:
                continue
            if commander_role not in member.roles:
                try:
                    await member.add_roles(commander_role, reason="Assigned commander role from MU config")
                    added.append(member.display_name)
                except Exception:
                    pass

        # Remove commander role from members that should no longer have it
        current_with_role = commander_role.members if commander_role else []
        for member in current_with_role:
            if member not in desired_members:
                try:
                    await member.remove_roles(commander_role, reason="Removed commander role (no longer MU commander)")
                    removed.append(member.display_name)
                except Exception:
                    pass

        # Send a summary if there were any changes
        channel = guild.get_channel(config.get('channels', {}).get('reports')) if guild else None
        if channel and (len(added) > 0 or len(removed) > 0):
            embed = self.build_commander_embed(added, removed)
            if embed:
                try:
                    await channel.send(embed=embed)
                except Exception:
                    pass

    @commander_roles.before_loop
    async def before_commander_roles(self):
        await self.bot.wait_until_ready()

    def build_commander_embed(self, added: list, removed: list) -> discord.Embed:
        total = len(added) + len(removed)
        if total == 0:
            return None
        embed = discord.Embed(
            title="Commander Roles Updated",
            description="Summary of commander role synchronization:",
            color=discord.Color.orange()
        )
        def fmt(lst: list) -> str:
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

        embed.add_field(name="Added", value=fmt(added), inline=False)
        embed.add_field(name="Removed", value=fmt(removed), inline=False)
        embed.set_footer(text=f"Total changes: {total}")
        return embed

async def setup(bot: commands.Bot):
    await bot.add_cog(CommanderRolesJob(bot))