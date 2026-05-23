from discord.ext import commands, tasks
from utils.api import get_user, get_shared_session
from utils.computational import triangular
from config import config
import discord
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

ECONOMY_SKILLS = ['energy', 'companies', 'entrepreneurship', 'production']

class NewbiePromotionJob(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.cached_members = {}
        self.promotion_loop.start()

    def cog_unload(self):
        self.promotion_loop.cancel()

    @tasks.loop(hours=12)
    async def promotion_loop(self):
        """Checks Newbie members for promotion eligibility and compliance.

        - Promotion candidates: level >=15 and has entrepreneur role
        - Non-compliance: Newbies in fight mode at level <=15 OR newbies >=15 with no role assigned
        """
        guild = self.bot.get_guild(config['guild'])
        if guild is None:
            return

        newbie_role = guild.get_role(config['roles'].get('newbie'))
        members = newbie_role.members if newbie_role else []
        promotion_candidates = []
        fight_issues = []
        inactive_candidates = []
        data_issues = []

        session = await get_shared_session()
        for member in members:
            try:
                user = await get_user(member.display_name, session)
                if not user:
                    # unable to resolve user via API; treat as non-compliant
                    data_issues.append((member.display_name, 'No API data'))
                    continue

                leveling = user.get('leveling', {}) or {}
                level = leveling.get('level') if isinstance(leveling.get('level'), int) else None

                # ensure lastConnectionAt within 5 days
                last_conn = None
                try:
                    last_conn_str = (user.get('dates') or {}).get('lastConnectionAt')
                    if last_conn_str:
                        last_conn = datetime.fromisoformat(last_conn_str.replace('Z', '+00:00'))
                    now = datetime.now(timezone.utc)
                    delta = now - last_conn
                    if delta.total_seconds() >= 5 * 24 * 3600:
                        inactive_candidates.append((member.display_name, level, f'Last active: {last_conn_str}'))
                        continue
                except Exception:
                    last_conn = None

                if last_conn is None:
                    data_issues.append((member.display_name, level, 'No lastConnectionAt'))
                    continue

                # Compute economy vs fight skill points like skill_roles
                economy_skill_points = 0
                fight_skill_points = 0
                skills = user.get('skills', {}) or {}
                for skill_name, skill_data in skills.items():
                    lvl = skill_data.get('level', 0)
                    if not lvl:
                        continue
                    if skill_name in ECONOMY_SKILLS:
                        economy_skill_points += triangular(lvl)
                    else:
                        fight_skill_points += triangular(lvl)

                total_skill_points = leveling.get('totalSkillPoints')
                unspent_skill_points = leveling.get('availableSkillPoints', 0)

                percentage = ((economy_skill_points + unspent_skill_points) / total_skill_points) * 100
                is_economy = percentage > 50
                is_fighter_mode = not is_economy
                
                # Promotion criteria: level >=20 OR level >=15 and entrepreneur skills
                has_economy = is_economy
                if level >= 20 or (level >= 15 and has_economy):
                    promotion_candidates.append((member.display_name, level, 'Economy' if has_economy else 'Level'))

                # Fight-mode issues: Newbies in fighter mode at level ==15 or level <15
                if is_fighter_mode and level <= 15:
                    note = 'Level <= 15 in fight mode'
                    fight_issues.append((member.display_name, level, note))
                    continue

            except Exception as e:
                logger.exception('Error processing member %s: %s', getattr(member, 'display_name', 'unknown'), e)
                data_issues.append((getattr(member, 'display_name', 'unknown'), 'Exception'))

        # Send paginated embeds for promotion candidates and non-compliance
        channel = guild.get_channel(config['channels'].get('reports')) if guild else None
        if channel:
            if promotion_candidates:
                embeds = build_paginated_embeds('Newbie Promotion Candidates', promotion_candidates)
                await send_paginated(channel, self.bot, embeds)

            if fight_issues:
                embeds = build_paginated_embeds('Newbie Fight-Mode Issues', fight_issues)
                await send_paginated(channel, self.bot, embeds)

            if data_issues:
                embeds = build_paginated_embeds('Newbie Data Issues', data_issues)
                await send_paginated(channel, self.bot, embeds)

    @promotion_loop.before_loop
    async def before_promotion_loop(self):
        await self.bot.wait_until_ready()


def build_paginated_embeds(title: str, items: list, page_size: int = 10) -> list:
    pages = []
    # Format items into strings
    lines = []
    for it in items:
        if isinstance(it, tuple):
            # tuple variations: (name, level, note) or (name, 'No API data')
            if len(it) == 3:
                lines.append(f"{it[0]} — Level: {it[1]} — {it[2]}")
            elif len(it) == 2:
                lines.append(f"{it[0]} — {it[1]}")
            else:
                lines.append(str(it))
        else:
            lines.append(str(it))

    for i in range(0, len(lines), page_size):
        chunk = lines[i:i + page_size]
        embed = discord.Embed(title=title, color=discord.Color.blue())
        desc = "\n".join(f"* {l}" for l in chunk)
        embed.description = desc or 'None'
        embed.set_footer(text=f"Page {i // page_size + 1} of {((len(lines)-1)//page_size)+1} — Total: {len(lines)}")
        pages.append(embed)

    return pages


async def send_paginated(channel: discord.TextChannel, bot: commands.Bot, embeds: list, timeout: int = 120):
    """Send embeds paginated via reactions. Falls back to sending all pages if reactions fail."""
    if not embeds:
        return

    try:
        msg = await channel.send(embed=embeds[0])
        if len(embeds) == 1:
            return

        # add paginator reactions
        controls = ['⏮️', '◀️', '▶️', '⏭️']
        for r in controls:
            try:
                await msg.add_reaction(r)
            except Exception:
                # if adding reactions fails, just send remaining embeds
                for e in embeds[1:]:
                    await channel.send(embed=e)
                return

        current = 0

        def check(reaction, user):
            return user != bot.user and reaction.message.id == msg.id and str(reaction.emoji) in controls

        while True:
            try:
                reaction, user = await bot.wait_for('reaction_add', timeout=timeout, check=check)
            except Exception:
                break

            try:
                emoji = str(reaction.emoji)
                if emoji == '⏮️':
                    current = 0
                elif emoji == '◀️':
                    current = max(0, current - 1)
                elif emoji == '▶️':
                    current = min(len(embeds) - 1, current + 1)
                elif emoji == '⏭️':
                    current = len(embeds) - 1

                await msg.edit(embed=embeds[current])
                try:
                    await msg.remove_reaction(reaction.emoji, user)
                except Exception:
                    pass
            except Exception:
                break

    except Exception:
        # fallback: send all pages
        for e in embeds:
            try:
                await channel.send(embed=e)
            except Exception:
                pass


async def setup(bot: commands.Bot):
    await bot.add_cog(NewbiePromotionJob(bot))
# notify for promotion the newbies if they reach level 15/20 and if their skills match the criteria (economy)
