from discord.ext import commands, tasks
from utils.api import get_user, get_shared_session, get_military_unit
from utils.db import init_db
from config import config
import discord

class MilitaryUnitRolesJob(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        try:
            init_db()
        except Exception:
            pass
        self.military_unit_roles.start()

    def cog_unload(self):
        self.military_unit_roles.cancel()

    @tasks.loop(hours=3)
    async def military_unit_roles(self):
        """Parses all members of the server that hold the citizen role and assigns
           military unit roles based on the available MU server roles available.
        """
        guild = self.bot.get_guild(config['guild'])
        if guild is None:
            return
        citizen = guild.get_role(config['roles']['citizen'])
        newbie = guild.get_role(config['roles']['newbie'])
        military_units = config.get('military_units', [])
        mu_to_role = {unit['id'] : guild.get_role(unit['roleId']) for unit in military_units}

        # Build a mapping of manager_api_id -> set of MU ids they manage.
        # We need an active session to call the API.
        session = await get_shared_session()
        owners: dict = {}
        for unit in military_units:
            try:
                mu_data = await get_military_unit(unit['id'], session)
            except Exception:
                mu_data = None
            if not mu_data:
                continue
            # The API returns role.managers as an array of api user ids
            managers = []
            try:
                managers = (mu_data.get('roles') or {}).get('managers') or []
            except Exception:
                managers = []
            for mgr in managers:
                # map manager api id to a set of unit ids (support multiple)
                if mgr in owners:
                    owners[mgr].add(unit['id'])
                else:
                    owners[mgr] = {unit['id']}

        members = set()
        if citizen:
            members.update(citizen.members)
        if newbie:
            members.update(newbie.members)

        # track player display names added/removed per role
        added_members: dict = {}
        removed_members: dict = {}

        # For each member, determine the desired MU-related roles (their current MU
        # plus any MU(s) they own/manage) then add/remove server roles to match.
        for member in members:
            try:
                user = await get_user(member.display_name, session)
            except Exception:
                user = None
            if user is None:
                continue

            api_id = user.get('_id') if isinstance(user, dict) else None

            # Desired roles set (discord.Role objects)
            desired_roles = set()

            # 1) Current MU role (if the user belongs to one)
            mu_id = user.get('mu')
            if mu_id:
                r = mu_to_role.get(mu_id)
                if r:
                    desired_roles.add(r)

            # 2) Owner/manager MU roles (if the user's api id is a manager)
            if api_id and api_id in owners:
                for owned_mu in owners.get(api_id, set()):
                    r = mu_to_role.get(owned_mu)
                    if r:
                        desired_roles.add(r)

            # Roles currently on the member that are MU roles we manage
            current_mu_roles = {r for r in mu_to_role.values() if r and r in member.roles}

            # Add roles that are desired but missing
            to_add = [r for r in desired_roles if r not in member.roles]
            if to_add:
                try:
                    await member.add_roles(*to_add, reason="Assigned Military Unit role.")
                    for r in to_add:
                        name = r.name if r else str(getattr(r, 'id', 'unknown'))
                        added_members.setdefault(name, []).append(member.display_name)
                except Exception:
                    pass

            # Remove MU roles that the member should no longer have (managed set minus desired)
            roles_to_remove = [r for r in current_mu_roles if r not in desired_roles]
            if roles_to_remove:
                try:
                    await member.remove_roles(*roles_to_remove, reason="Removed unused Military Unit roles.")
                    for r in roles_to_remove:
                        rname = r.name if r else str(getattr(r, 'id', 'unknown'))
                        removed_members.setdefault(rname, []).append(member.display_name)
                except Exception:
                    pass

        # Send a summary embed for military unit role changes — only if there were changes
        channel = guild.get_channel(config["channels"]["reports"]) if guild else None
        if channel:
            total_changes = sum(len(v) for v in added_members.values()) + sum(len(v) for v in removed_members.values())
            if total_changes == 0:
                return
            embed = self.build_military_unit_embed(added_members, removed_members)
            if embed:
                await channel.send(embed=embed)

    @military_unit_roles.before_loop
    async def before_military_unit_roles(self):
        await self.bot.wait_until_ready()

    def build_military_unit_embed(self, added: dict, removed: dict) -> discord.Embed:
        all_roles = set(list(added.keys()) + list(removed.keys()))
        total = sum(len(v) for v in added.values()) + sum(len(v) for v in removed.values())

        if total == 0:
            return None

        embed = discord.Embed(
            title="Military Unit Roles Updated",
            description="Summary of military unit role changes:",
            color=discord.Color.orange()
        )

        def format_players(lst: list) -> str:
            if not lst:
                return None
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

        for role_name in sorted(all_roles):
            a_list = added.get(role_name, [])
            r_list = removed.get(role_name, [])
            a_formatted = format_players(a_list)
            r_formatted = format_players(r_list)
            if a_formatted is None and r_formatted is None:
                continue
            if a_formatted is not None:
                embed.add_field(name=role_name, value=f"Added:\n{a_formatted}\n", inline=False)
            if r_formatted is not None:
                embed.add_field(name=role_name, value=f"Removed:\n{r_formatted}\n", inline=False)
        embed.set_footer(text=f"Total changes: {total}")
        return embed  

async def setup(bot: commands.Bot):
    await bot.add_cog(MilitaryUnitRolesJob(bot))