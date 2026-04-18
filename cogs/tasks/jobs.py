import aiohttp
import discord
from discord.ext import commands, tasks
from utils.api import get_user, get_all_countries, get_country_government, get_user_info
from utils.db import init_db, save_user, find_api_id_by_display_name, find_api_id_by_discord_username
from utils.computational import triangular
from config import config

ECONOMY_SKILLS = ['energy', 'companies', 'entrepreneurship', 'production']
HEADERS = {'X-API-Key': config['api']}
from datetime import datetime, timezone, timedelta

# minutes before buff end to notify the user
NOTIFY_THRESHOLD_MINUTES = 30
# how long to wait before re-checking users with no active buff/debuff
DEFAULT_SKIP_HOURS = 1
# how often the buff monitor runs (minutes) — keep in sync with @tasks.loop(minutes=...)
BUFF_MONITOR_INTERVAL_MINUTES = 10
# effective notify threshold to account for the monitor interval so users are
# guaranteed to be notified at least NOTIFY_THRESHOLD_MINUTES before expiry
EFFECTIVE_NOTIFY_MINUTES = NOTIFY_THRESHOLD_MINUTES

class Jobs(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.cached_members = {}
        # cache for buff checks: api_id -> { next_check: datetime, notified_for_end_at: str|None }
        self.buff_check_cache: dict = {}
        self.countries = None
        # Ensure database/table exists
        try:
            init_db()
        except Exception:
            pass
        self.skill_roles.start()
        self.military_unit_roles.start()
        self.unidentified_members.start()
        self.takeover_countries.start()
        self.buff_monitor.start()

    def cog_unload(self):
        self.skill_roles.cancel()
        self.military_unit_roles.cancel()
        self.unidentified_members.cancel()
        self.takeover_countries.cancel()
        self.buff_monitor.cancel()
    async def get_countries(self):
        async with aiohttp.ClientSession(headers=HEADERS) as session:
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
        async with aiohttp.ClientSession(headers=HEADERS) as session:
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

        members = set()
        if citizen:
            members.update(citizen.members)
        if newbie:
            members.update(newbie.members)
            
        # track player display names added/removed per role
        added_members: dict = {}
        removed_members: dict = {}
        async with aiohttp.ClientSession(headers=HEADERS) as session:
            for member in members:
                user = await get_user(member.display_name, session)
                if user is None or "mu" not in user.keys():
                    continue
                role = mu_to_role.get(user["mu"])
                if role is None:
                    continue
                if role in member.roles:
                    continue
                roles_to_remove = [
                    r for r in mu_to_role.values()
                    if r and r in member.roles and r != role
                ]
                await member.add_roles(role, reason="Assigned Military Unit role.")
                name = role.name if role else str(role.id)
                added_members.setdefault(name, []).append(member.display_name)
                if roles_to_remove:
                    await member.remove_roles(*roles_to_remove, reason="Removed unused Military Unit roles.")
                    for r in roles_to_remove:
                        rname = r.name if r else str(r.id)
                        removed_members.setdefault(rname, []).append(member.display_name)

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

    @tasks.loop(hours=6)
    async def unidentified_members(self):
        """Parses all members of the server that hold the citizen role and checks
           if their server nickname matches the one from the game.
        """
        guild = self.bot.get_guild(config['guild'])
        citizen = guild.get_role(config['roles']['citizen'])
        newbie = guild.get_role(config['roles']['newbie'])

        members = set()
        if citizen:
            members.update(citizen.members)
        if newbie:
            members.update(newbie.members)

        unidentified = []
        async with aiohttp.ClientSession(headers=HEADERS) as session:
            for member in members:
                user = await get_user(member.display_name, session)
                if user is None:
                    # try to find api_id in local DB by display name or discord username
                    try:
                        api_id = find_api_id_by_display_name(member.display_name) or find_api_id_by_discord_username(member.name)
                        if api_id:
                            info = await get_user_info(api_id, session)
                            if info:
                                # update stored mapping with the current display name
                                save_user(member.name, member.display_name, api_id)
                                continue
                    except Exception:
                        pass
                    unidentified.append(member)
                else:
                    try:
                        api_id = user.get('_id') if isinstance(user, dict) else None
                        if api_id:
                            save_user(member.name, member.display_name, api_id)
                    except Exception:
                        pass
            if len(unidentified) == 0:
                return None
            # Always send an embed, even if there are no unidentified players
            channel = guild.get_channel(config["channels"]["reports"]) if guild else None
            if channel:
                embed = self.build_unidentified_embed(unidentified)
                await channel.send(embed=embed)

    @unidentified_members.before_loop
    async def before_unidentified_members(self):
        await self.bot.wait_until_ready()

    @tasks.loop(minutes=5)
    async def takeover_countries(self):
        """Parses all countries of the server and posts any country that can be taken over.
        """
        if self.countries is None:
            self.countries = await self.get_countries()

        guild = self.bot.get_guild(config['guild'])
        active_countries = config.get('active_countries', [])
        async with aiohttp.ClientSession(headers=HEADERS) as session:
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
            channel = guild.get_channel(config["channels"]["reports"]) if guild else None
            if channel:
                embed = self.build_takeover_embed(empty_countries)
                await channel.send(embed=embed)

    @takeover_countries.before_loop
    async def before_takeover_countries(self):
        await self.bot.wait_until_ready()

    @tasks.loop(minutes=10)
    async def buff_monitor(self):
        """Checks fighter members for active buffs and notifies users when their
        buff is nearing expiration (within NOTIFY_THRESHOLD_MINUTES).
        The method uses an in-memory cache (`self.buff_check_cache`) to avoid
        scanning all fighters every run; entries store the earliest `next_check`.
        """
        guild = self.bot.get_guild(config['guild'])
        if guild is None:
            return
        fight_role = guild.get_role(config['roles']['fight'])
        if fight_role is None:
            return

        now = datetime.now(timezone.utc)
        members = fight_role.members if fight_role else []
        seen_api_ids = set()

        async with aiohttp.ClientSession(headers=HEADERS) as session:
            for member in members:
                api_id = None
                try:
                    api_id = find_api_id_by_display_name(member.display_name) or find_api_id_by_discord_username(member.name)
                except Exception:
                    api_id = None

                # If we already know the next time to check this API id, skip for now
                if api_id:
                    entry = self.buff_check_cache.get(api_id)
                    if entry:
                        next_check = entry.get('next_check')
                        if next_check and next_check > now:
                            seen_api_ids.add(api_id)
                            continue

                # Retrieve user info. Prefer get_user_info when we already have api_id
                user_obj = None
                if api_id:
                    try:
                        user_obj = await get_user_info(api_id, session)
                    except Exception:
                        user_obj = None

                if not user_obj:
                    user_obj = await get_user(member.display_name, session)
                    if isinstance(user_obj, dict):
                        api_id = user_obj.get('_id') or api_id
                        if api_id:
                            try:
                                save_user(member.name, member.display_name, api_id)
                            except Exception:
                                pass

                if not user_obj:
                    continue

                # Parse buff/debuff information from the user object
                buffs = user_obj.get('buffs') or {}
                buff_end_at = None
                buff_type = None
                buff_active = False
                if isinstance(buffs, dict) and buffs:
                    if 'debuffEndAt' in buffs and buffs.get('debuffEndAt'):
                        buff_end_at = buffs.get('debuffEndAt')
                        buff_type = 'Debuff'
                    elif 'buffEndAt' in buffs and buffs.get('buffEndAt'):
                        buff_end_at = buffs.get('buffEndAt')
                        buff_type = 'Buff'

                    if buff_end_at:
                        try:
                            buff_dt = datetime.fromisoformat(buff_end_at.replace('Z', '+00:00'))
                            remaining = buff_dt - now
                            buff_active = remaining.total_seconds() > 0
                        except Exception:
                            buff_active = False

                cache_entry = self.buff_check_cache.get(api_id, {})

                # No active buff/debuff
                if not buff_end_at or not buff_active:
                    cache_entry['next_check'] = now + timedelta(hours=DEFAULT_SKIP_HOURS)
                    cache_entry['notified_for_end_at'] = None
                    self.buff_check_cache[api_id] = cache_entry
                    seen_api_ids.add(api_id)
                    continue

                # Currently on debuff -> avoid until debuff ends
                if buff_type == 'Debuff':
                    cache_entry['next_check'] = buff_dt + timedelta(minutes=1)
                    cache_entry['notified_for_end_at'] = None
                    self.buff_check_cache[api_id] = cache_entry
                    seen_api_ids.add(api_id)
                    continue

                # Active buff: notify when within effective threshold (accounts for poll delay)
                remaining_seconds = (buff_dt - now).total_seconds()
                notified_token = cache_entry.get('notified_for_end_at')
                if remaining_seconds <= EFFECTIVE_NOTIFY_MINUTES * 60:
                    # Determine current health/hunger values (safe parsing)
                    skills = user_obj.get('skills') or {}
                    health = skills.get('health') or {}
                    hunger = skills.get('hunger') or {}
                    try:
                        health_curr = int(health.get('currentBarValue') or 0)
                    except Exception:
                        health_curr = 0
                    try:
                        hunger_curr = int(hunger.get('currentBarValue') or 0)
                    except Exception:
                        hunger_curr = 0

                    has_resources = (health_curr > 0) or (hunger_curr > 0)

                    # Check if a top-of-hour (o'clock) occurs between now and buff end —
                    # if so, health/hunger will be regenerated by 10% and we should notify.
                    next_top = now.replace(minute=0, second=0, microsecond=0)
                    if next_top <= now:
                        next_top = next_top + timedelta(hours=1)
                    oclock_within_window = next_top <= buff_dt

                    should_notify = has_resources or oclock_within_window

                    # Only send notification when conditions are met and we haven't
                    # already notified for this buff end timestamp.
                    if should_notify and notified_token != buff_end_at:
                        minutes = max(1, int(remaining_seconds // 60))
                        text = f"Hi {member.display_name}, your pill buff expires in about {minutes} minute{'s' if minutes != 1 else ''}. Please empty into a fight if possible."
                        try:
                            await member.send(text)
                        except Exception:
                            channel = guild.get_channel(config.get('channels', {}).get('reports')) if guild else None
                            if channel:
                                try:
                                    await channel.send(f"{member.mention} — {text}")
                                except Exception:
                                    pass
                        cache_entry['notified_for_end_at'] = buff_end_at
                        cache_entry['next_check'] = buff_dt + timedelta(minutes=1)
                    else:
                        # Don't notify now — schedule a re-check after buff end
                        cache_entry['next_check'] = buff_dt + timedelta(minutes=1)
                    self.buff_check_cache[api_id] = cache_entry
                    seen_api_ids.add(api_id)
                    continue

                # Schedule next check at buff_dt - (effective threshold)
                next_check = buff_dt - timedelta(minutes=EFFECTIVE_NOTIFY_MINUTES)
                if next_check <= now:
                    next_check = now + timedelta(minutes=BUFF_MONITOR_INTERVAL_MINUTES)
                cache_entry['next_check'] = next_check
                cache_entry['notified_for_end_at'] = cache_entry.get('notified_for_end_at')
                self.buff_check_cache[api_id] = cache_entry
                seen_api_ids.add(api_id)

        # Prune cache entries for API ids we did not see during this run
        to_prune = [k for k in list(self.buff_check_cache.keys()) if k not in seen_api_ids]
        for k in to_prune:
            try:
                entry = self.buff_check_cache.get(k)
                if not entry:
                    del self.buff_check_cache[k]
                    continue
                next_check = entry.get('next_check')
                if not next_check or (isinstance(next_check, datetime) and next_check < datetime.now(timezone.utc) - timedelta(hours=24)):
                    del self.buff_check_cache[k]
            except Exception:
                pass

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
        
    def build_unidentified_embed(self, members: list[discord.Member]) -> discord.Embed:
        if not members:
            embed = discord.Embed(
                title="Unidentified Players Check",
                description="No unidentified players were found.",
                color=discord.Color.green()
            )
            embed.set_footer(text="Total: 0")
            return embed

        embed = discord.Embed(
            title="Unidentified Players Found",
            description="The following members could not be matched:",
            color=discord.Color.orange()
        )
        lines = [f"* {m.display_name} ('{m.id}')" for m in members]
        chunk = ""
        for line in lines:
            if len(chunk) + len(line) > 1000:
                embed.add_field(name="Players", value=chunk, inline=False)
                chunk = ""
            chunk += line + "\n"
        if chunk:
            embed.add_field(name="Players", value=chunk, inline=False)
        embed.set_footer(text=f"Total: {len(members)}")
        return embed
    
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
    await bot.add_cog(Jobs(bot))