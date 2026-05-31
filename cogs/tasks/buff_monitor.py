from discord.ext import commands, tasks
from utils.api import get_shared_session, get_user, get_user_info
from utils.db import init_db, find_api_id_by_display_name, find_api_id_by_discord_username, find_api_id_by_discord_id, save_user
from config import config
from datetime import datetime, timezone, timedelta

# how long to wait before re-checking users with no active buff/debuff
DEFAULT_SKIP_HOURS = 1
# minutes before buff end to notify the user
NOTIFY_THRESHOLD_MINUTES = 30
# how often the buff monitor runs (minutes) — keep in sync with @tasks.loop(minutes=...)
BUFF_MONITOR_INTERVAL_MINUTES = 10
# effective notify threshold to account for the monitor interval so users are
# guaranteed to be notified at least NOTIFY_THRESHOLD_MINUTES before expiry
EFFECTIVE_NOTIFY_MINUTES = NOTIFY_THRESHOLD_MINUTES

class BuffMonitorJob(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # cache for buff checks: api_id -> { next_check: datetime, notified_for_end_at: str|None }
        self.buff_check_cache: dict = {}
        try:
            init_db()
        except Exception:
            pass
        self.buff_monitor.start()

    def cog_unload(self):
        self.buff_monitor.cancel()

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
        session = await get_shared_session()
        for member in members:
                api_id = None
                try:
                    api_id = find_api_id_by_discord_id(member.id) or find_api_id_by_display_name(member.display_name) or find_api_id_by_discord_username(member.name)
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
                                save_user(member.name, member.display_name, api_id, member.id)
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
                            channel = guild.get_channel(config.get('channels', {}).get('public')) if guild else None
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

async def setup(bot: commands.Bot):
    await bot.add_cog(BuffMonitorJob(bot))