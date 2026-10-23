import asyncio
from discord.ext import commands, tasks
from utils.api import get_shared_session, get_military_units_by_ids, get_user_ids_by_name, get_users_info
from utils.db import init_db, get_api_ids_by_discord_id
from utils.i18n import Translator, get_translator
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
        """Sync the configured MU server roles of every citizen and newbie member.

           A member linked to a player in the database (by Discord id) is checked
           against that player's current in-game username: if their server nickname
           matches it, they get the roles of the MU they belong to or manage and lose
           the others; if it doesn't, every MU role is removed. Members without a
           database link are matched by nickname as before. A member whose player
           could not be loaded this run is left untouched.
        """
        guild = self.bot.get_guild(config['guild'])
        if guild is None:
            return
        citizen = guild.get_role(config['roles']['citizen'])
        newbie = guild.get_role(config['roles']['newbie'])
        military_units = config.get('military_units', [])
        mu_to_role = {unit['id'] : guild.get_role(unit['roleId']) for unit in military_units}

        # One batched request for every configured MU. Each MU carries its `members`
        # (user ids, matches each user's `mu` field) and `roles.managers`, so no
        # per-member user fetch is needed.
        session = await get_shared_session()
        tr = await get_translator(guild)
        mu_data_by_id = await get_military_units_by_ids(mu_to_role.keys(), session)

        # A nickname that doesn't match the linked player loses every configured MU
        # role; that decision needs no MU data, so it also covers MUs that failed to load.
        configured_roles = {role for role in mu_to_role.values() if role}

        # An MU that failed to load is left alone this run: without its member list
        # we would otherwise strip its role from all of its members.
        mu_to_role = {mu_id: role for mu_id, role in mu_to_role.items() if role and mu_id in mu_data_by_id}
        managed_roles = set(mu_to_role.values())

        member_mu: dict = {}  # user id -> MU id they belong to
        owners: dict = {}     # manager user id -> set of MU ids they manage
        for mu_id, mu_data in mu_data_by_id.items():
            for user_id in mu_data.get('members') or []:
                member_mu[user_id] = mu_id
            for mgr in (mu_data.get('roles') or {}).get('managers') or []:
                owners.setdefault(mgr, set()).add(mu_id)

        members = set()
        if citizen:
            members.update(citizen.members)
        if newbie:
            members.update(newbie.members)

        # Discord id -> API user id from the database, read once. If the read fails,
        # every member is matched by nickname alone.
        try:
            linked_ids = await asyncio.to_thread(get_api_ids_by_discord_id)
        except Exception:
            linked_ids = {}
        linked = {m: linked_ids[str(m.id)] for m in members if linked_ids.get(str(m.id))}

        # Current in-game usernames of the linked players (batched). A player missing
        # here failed to load, so that member is skipped rather than stripped.
        linked_users = await get_users_info(linked.values(), session) if linked else {}

        # Unlinked members: Discord display name -> API user id (cached names cost no request)
        user_ids = await get_user_ids_by_name([m.display_name for m in members if m not in linked], session)

        # track player display names added/removed per role
        added_members: dict = {}
        removed_members: dict = {}

        # For each member, determine the desired MU-related roles (their current MU
        # plus any MU(s) they own/manage) then add/remove server roles to match.
        for member in members:
            name_matches = True
            if member in linked:
                api_id = linked[member]
                user = linked_users.get(api_id)
                if not user or not user.get('username'):
                    continue
                name_matches = user['username'] == member.display_name
            else:
                api_id = user_ids.get(member.display_name)
                if api_id is None:
                    continue

            # Desired roles set (discord.Role objects)
            desired_roles = set()

            if name_matches:
                # 1) Current MU role (if the user belongs to one)
                r = mu_to_role.get(member_mu.get(api_id))
                if r:
                    desired_roles.add(r)

                # 2) Owner/manager MU roles (if the user's api id is a manager)
                for owned_mu in owners.get(api_id, set()):
                    r = mu_to_role.get(owned_mu)
                    if r:
                        desired_roles.add(r)

                # Roles currently on the member that are MU roles we manage
                current_mu_roles = {r for r in member.roles if r in managed_roles}
            else:
                # Nickname differs from the linked player's username: drop every MU role
                current_mu_roles = {r for r in member.roles if r in configured_roles}

            # Add roles that are desired but missing
            to_add = [r for r in desired_roles if r not in member.roles]
            if to_add:
                try:
                    await member.add_roles(*to_add, reason=tr("mu_roles.reason_added"))
                    for r in to_add:
                        name = r.name if r else str(getattr(r, 'id', 'unknown'))
                        added_members.setdefault(name, []).append(member.display_name)
                except Exception:
                    pass

            # Remove MU roles that the member should no longer have (managed set minus desired)
            roles_to_remove = [r for r in current_mu_roles if r not in desired_roles]
            if roles_to_remove:
                try:
                    reason = tr("mu_roles.reason_removed") if name_matches else tr("mu_roles.reason_name_mismatch")
                    await member.remove_roles(*roles_to_remove, reason=reason)
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
            embed = self.build_military_unit_embed(added_members, removed_members, tr)
            if embed:
                await channel.send(embed=embed)

    @military_unit_roles.before_loop
    async def before_military_unit_roles(self):
        await self.bot.wait_until_ready()

    def build_military_unit_embed(self, added: dict, removed: dict, tr: Translator) -> discord.Embed:
        all_roles = set(list(added.keys()) + list(removed.keys()))
        total = sum(len(v) for v in added.values()) + sum(len(v) for v in removed.values())

        if total == 0:
            return None

        embed = discord.Embed(
            title=tr("mu_roles.title"),
            description=tr("mu_roles.description"),
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
                cur += "\n" + tr("common.and_more", count=remaining)
            return cur

        for role_name in sorted(all_roles):
            a_list = added.get(role_name, [])
            r_list = removed.get(role_name, [])
            a_formatted = format_players(a_list)
            r_formatted = format_players(r_list)
            if a_formatted is None and r_formatted is None:
                continue
            if a_formatted is not None:
                embed.add_field(name=role_name, value=f"{tr('mu_roles.added')}\n{a_formatted}\n", inline=False)
            if r_formatted is not None:
                embed.add_field(name=role_name, value=f"{tr('mu_roles.removed')}\n{r_formatted}\n", inline=False)
        embed.set_footer(text=tr("common.total_changes", total=total))
        return embed  

async def setup(bot: commands.Bot):
    await bot.add_cog(MilitaryUnitRolesJob(bot))