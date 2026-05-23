from discord.ext import commands, tasks
from utils.api import get_shared_session, get_user, get_user_info
from utils.db import init_db, save_user, find_api_id_by_display_name, find_api_id_by_discord_username
from config import config
import discord

class UnidentifiedMembersJob(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        try:
            init_db()
        except Exception:
            pass
        self.unidentified_members.start()

    def cog_unload(self):
        self.unidentified_members.cancel()
    
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
        session = await get_shared_session()
        for member in members:
            user = await get_user(member.display_name, session)
            if user is None:
                # try to find api_id in local DB by display name or discord username
                try:
                    api_id = find_api_id_by_display_name(member.display_name) or find_api_id_by_discord_username(member.name)
                    if api_id:
                        info = await get_user_info(api_id, session)
                        if info:
                            # Prefer the API username as the authoritative display name
                            new_display = info.get('username') or None
                            # If the API reports a different display name, try to update the member's server nickname
                            if new_display and new_display != member.display_name:
                                try:
                                    await member.edit(nick=new_display, reason="Sync WarEra username")
                                except Exception:
                                    # ignore failures (permissions, hierarchy, etc.)
                                    pass
                            # update stored mapping with the current discord username and latest display name
                            save_user(member.name, new_display or member.display_name, api_id)
                            continue
                except Exception:
                    pass
                unidentified.append(member)
            else:
                try:
                    api_id = user.get('_id') if isinstance(user, dict) else None
                    if api_id:
                        save_user(member.name, member.display_name, api_id)
                except Exception as e:
                    pass
                    unidentified.append(member)
        if len(unidentified) == 0:
            return None
        # Always send an embed, even if there are no unidentified players
        channel = guild.get_channel(config["channels"]["reports"]) if guild else None
        if channel:
            embeds = self.build_unidentified_embed(unidentified)
            # builder returns a list of embeds; send them sequentially
            if isinstance(embeds, list):
                for e in embeds:
                    try:
                        await channel.send(embed=e)
                    except Exception:
                        pass
            else:
                try:
                    await channel.send(embed=embeds)
                except Exception:
                    pass

    @unidentified_members.before_loop
    async def before_unidentified_members(self):
        await self.bot.wait_until_ready()

    def build_unidentified_embed(self, members: list[discord.Member]) -> list:
        """Return a list of embeds (one or more) that together list unidentified members.
        Splits content so no single embed exceeds Discord's embed size limits.
        """
        if not members:
            embed = discord.Embed(
                title="Unidentified Players Check",
                description="No unidentified players were found.",
                color=discord.Color.green()
            )
            embed.set_footer(text="Total: 0")
            return [embed]

        lines = [f"* {m.display_name} ('{m.id}')" for m in members]

        # First split into field-sized chunks (<=1000 chars per field)
        field_chunks: list[str] = []
        chunk = ""
        for line in lines:
            if len(chunk) + len(line) > 1000:
                field_chunks.append(chunk)
                chunk = ""
            chunk += line + "\n"
        if chunk:
            field_chunks.append(chunk)

        # Now group fields into embeds without exceeding a safe embed size limit
        EMBED_CHAR_LIMIT = 5800  # keep some headroom under 6000
        title = "Unidentified Players Found"
        description = "The following members could not be matched:"

        embeds: list[discord.Embed] = []
        current_embed = discord.Embed(title=title, description=description, color=discord.Color.orange())
        current_length = len(title) + len(description)

        for field_value in field_chunks:
            field_name = "Players"
            field_len = len(field_name) + len(field_value)
            # Start a new embed if adding this field would exceed the safe limit
            if current_length + field_len > EMBED_CHAR_LIMIT and len(current_embed.fields) > 0:
                current_embed.set_footer(text=f"Total: {len(members)}")
                embeds.append(current_embed)
                current_embed = discord.Embed(title=title, description=description, color=discord.Color.orange())
                current_length = len(title) + len(description)

            current_embed.add_field(name=field_name, value=field_value, inline=False)
            current_length += field_len

        # Append last embed
        current_embed.set_footer(text=f"Total: {len(members)}")
        embeds.append(current_embed)
        return embeds

async def setup(bot: commands.Bot):
    await bot.add_cog(UnidentifiedMembersJob(bot))