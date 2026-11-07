"""Political party role sync: gives each member the server role of the in-game party they belong to.

Every ``PARTY_ROLES_INTERVAL_HOURS`` the job reads every party in ``config.json`` ``political_parties``
(one batched ``party.getById`` request: each party lists all its members' user ids), so no per-player
fetch is needed to know who is in which party. Each entry maps the party ``id`` to a member role
(``roleId``) and a leader role (``leaderId``):

* a member of a configured party gets its ``roleId`` and loses the roles of the other parties;
* the party's in-game leader also gets its ``leaderId``; anyone else loses it;
* a player in no configured party loses every party role.

Discord members are matched to players like ``military_unit_roles``: by database link first, by server
nickname otherwise. A linked member whose nickname differs from their player's current username loses
every party role. A party that fails to load is left alone that run (its roles are neither added nor
removed), and a member whose player can't be resolved keeps their roles, so an API outage never strips
roles.
"""

import asyncio
import logging

import discord
from discord.ext import commands, tasks

from config import config
from utils.api import warera
from utils.db import get_api_ids_by_discord_id
from utils.i18n import Translator, get_translator

logger = logging.getLogger(__name__)

PARTY_ROLES_INTERVAL_HOURS = 1
EMBED_LIMIT = 4000   # the user's cap per report embed (Discord allows 6000)
FIELD_LIMIT = 1024   # Discord's limit per field value
MAX_FIELDS = 25      # Discord's limit of fields per embed


async def _change_roles(member, roles: list, add: bool, reason: str) -> bool:
    """Add or remove several roles in one call, logging Discord errors instead of raising.

    An unhandled error would end the run early and stop the ``tasks.loop`` until the next restart.

    Args:
        member: Discord member to update.
        roles: Roles to add or remove.
        add: True to add the roles, False to remove them.
        reason: Audit-log reason.

    Returns:
        Whether the change went through.
    """
    try:
        if add:
            await member.add_roles(*roles, reason=reason)
        else:
            await member.remove_roles(*roles, reason=reason)
        return True
    except discord.HTTPException as exc:
        logger.warning("party_roles: could not %s %s for %s (%s): %s", "add" if add else "remove",
                       [r.name for r in roles], member.display_name, member.id, exc)
        return False


def desired_party_roles(api_id: str, member_party: dict, leaders: dict, member_role: dict,
                        leader_role: dict) -> set:
    """The party roles a player should hold, from the loaded parties only.

    Args:
        api_id: The player's user id.
        member_party: User id -> id of the (loaded) party they are a member of.
        leaders: Leader user id -> id of the (loaded) party they lead.
        member_role: Party id -> member role.
        leader_role: Party id -> leader role (missing when not configured or not in the guild).

    Returns:
        The set of roles to hold: the party's member role, plus its leader role for the leader. The
        leader always gets the member role too, even if the API ever leaves them out of ``members``.
    """
    desired = set()
    led = leaders.get(api_id)
    for party_id in (member_party.get(api_id), led):
        if party_id and member_role.get(party_id):
            desired.add(member_role[party_id])
    if led and leader_role.get(led):
        desired.add(leader_role[led])
    return desired


def build_summary_embeds(added: dict, removed: dict, tr: Translator) -> list:
    """Summary embeds of the role changes, split so none exceeds ``EMBED_LIMIT`` characters.

    Laid out like the ``skill_roles`` summary: an orange embed with, for every role that changed, a
    "<role> — Added" and a "<role> — Removed" field holding a ``* name`` list ("None" when empty), and
    the total in the footer. Unlike ``skill_roles``, no name is dropped: a long list continues in further
    fields (≤ ``FIELD_LIMIT``) and the fields in further embeds, numbered "(i/N)" in the title.

    Args:
        added: Role label (the party's full in-game name, "(leader)" for its leader role) -> display
            names that got the role.
        removed: Role label -> display names that lost it.
        tr: Translator for the guild's language.

    Returns:
        The embeds to post, or [] when nothing changed.
    """
    total = sum(len(v) for v in added.values()) + sum(len(v) for v in removed.values())
    if total == 0:
        return []

    fields = []
    for role_name in sorted(set(added) | set(removed)):
        for key, names in (("party_roles.role_added", added.get(role_name)),
                           ("party_roles.role_removed", removed.get(role_name))):
            field_name = tr(key, role=role_name)
            if not names:
                fields.append((field_name, tr("common.none")))
                continue
            value = ""
            for line in (f"* {n}" for n in names):
                if value and len(value) + 1 + len(line) > FIELD_LIMIT:
                    fields.append((field_name, value))
                    field_name = "​"  # continuation of the same list
                    value = line
                else:
                    value = f"{value}\n{line}" if value else line
            fields.append((field_name, value))

    title = tr("party_roles.title")
    description = tr("party_roles.description")
    footer = tr("common.total_changes", total=total)
    # Room for the title's " (10/10)" counter, the description and the footer on every page.
    budget = EMBED_LIMIT - len(title) - len(" (10/10)") - len(description) - len(footer)
    pages = [[]]
    used = 0
    for name, value in fields:
        size = len(name) + len(value)
        if pages[-1] and (used + size > budget or len(pages[-1]) >= MAX_FIELDS):
            pages.append([])
            used = 0
        pages[-1].append((name, value))
        used += size

    embeds = []
    for index, page in enumerate(pages, start=1):
        page_title = title if len(pages) == 1 else f"{title} ({index}/{len(pages)})"
        embed = discord.Embed(title=page_title, description=description, color=discord.Color.orange())
        for name, value in page:
            embed.add_field(name=name, value=value, inline=False)
        embed.set_footer(text=footer)
        embeds.append(embed)
    return embeds


class PartyRolesJob(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.party_roles.start()

    def cog_unload(self):
        """Stop the sync loop when the cog is unloaded."""
        self.party_roles.cancel()

    @tasks.loop(hours=PARTY_ROLES_INTERVAL_HOURS)
    async def party_roles(self):
        """Sync the configured party member and leader roles of every citizen, newbie and party-role holder.

        Holders of a party role are checked even without the Citizen/Newbie role, so someone who left the
        party loses its role either way. See the module docstring for the rules.
        """
        guild = self.bot.get_guild(config['guild'])
        if guild is None:
            return
        parties = config.get('political_parties', [])
        if not parties:
            return

        member_role = {}  # party id -> member role
        leader_role = {}  # party id -> leader role
        for party in parties:
            role = guild.get_role(party.get('roleId') or 0)
            if role:
                member_role[party['id']] = role
            else:
                logger.warning("party_roles: member role %s of party %s not found in the guild",
                               party.get('roleId'), party.get('friendly_name') or party['id'])
            if party.get('leaderId'):
                role = guild.get_role(party['leaderId'])
                if role:
                    leader_role[party['id']] = role
                else:
                    logger.warning("party_roles: leader role %s of party %s not found in the guild",
                                   party['leaderId'], party.get('friendly_name') or party['id'])
        all_roles = set(member_role.values()) | set(leader_role.values())
        if not all_roles:
            return

        tr = await get_translator(guild)
        party_data = await warera.parties.get_many([p['id'] for p in parties])
        # A party without a member list (degraded response) counts as failed: reading it as "no members"
        # would strip its role from everyone.
        party_data = {pid: party for pid, party in party_data.items()
                      if isinstance(party.get('members'), list) and party['members']}
        failed = [p.get('friendly_name') or p['id'] for p in parties if p['id'] not in party_data]
        if failed:
            logger.warning("party_roles: could not load parties %s; their roles are left alone this run", failed)

        # Only the roles of parties that loaded are added or removed on the normal path. A role that a
        # failed party also uses is left alone too, since that party's holders are unknown this run.
        role_pairs = (*member_role.items(), *leader_role.items())
        failed_roles = {role for pid, role in role_pairs if pid not in party_data}
        managed_roles = {role for pid, role in role_pairs if pid in party_data} - failed_roles

        # Summary labels: the party's full in-game name (not config's friendly_name), "(leader)" for its
        # leader role; a party that failed to load this run falls back to the Discord role name.
        role_label: dict = {}
        for party_id, role in member_role.items():
            name = (party_data.get(party_id) or {}).get('name')
            role_label[role] = name or role.name
        for party_id, role in leader_role.items():
            name = (party_data.get(party_id) or {}).get('name')
            role_label[role] = tr("party_roles.leader_label", party=name) if name else role.name

        member_party: dict = {}  # user id -> party id
        leaders: dict = {}       # leader user id -> party id
        for party_id, party in party_data.items():
            for user_id in party.get('members') or []:
                member_party[user_id] = party_id
            if party.get('leader'):
                leaders[party['leader']] = party_id

        members = set()
        for role_id in (config['roles'].get('citizen'), config['roles'].get('newbie')):
            role = guild.get_role(role_id) if role_id else None
            if role:
                members.update(role.members)
        for role in all_roles:
            members.update(role.members)

        # Discord id -> API user id from the database, read once. If the read fails,
        # every member is matched by nickname alone.
        try:
            linked_ids = await asyncio.to_thread(get_api_ids_by_discord_id)
        except Exception:
            logger.exception("party_roles: could not read the database links")
            linked_ids = {}
        linked = {m: linked_ids[str(m.id)] for m in members if linked_ids.get(str(m.id))}

        # Current usernames of the linked players (batched), to check their nickname still matches.
        # A player missing here failed to load, so that member is skipped rather than stripped.
        linked_users = await warera.users.get_many(linked.values()) if linked else {}
        # Unlinked members: nickname -> user id (cached names cost no request).
        user_ids = await warera.users.ids_by_name([m.display_name for m in members if m not in linked])

        added: dict = {}
        removed: dict = {}
        for member in sorted(members, key=lambda m: m.id):
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

            if name_matches:
                desired = desired_party_roles(api_id, member_party, leaders, member_role, leader_role)
                current = {r for r in member.roles if r in managed_roles}
            else:
                # Nickname differs from the linked player's username: drop every party role
                # (needs no party data, so it also covers parties that failed to load).
                desired = set()
                current = {r for r in member.roles if r in all_roles}

            to_add = [r for r in desired if r not in member.roles]
            if to_add and await _change_roles(member, to_add, True, tr("party_roles.reason_added")):
                for r in to_add:
                    added.setdefault(role_label.get(r, r.name), []).append(member.display_name)

            to_remove = [r for r in current if r not in desired]
            reason = tr("party_roles.reason_removed") if name_matches else tr("party_roles.reason_name_mismatch")
            if to_remove and await _change_roles(member, to_remove, False, reason):
                for r in to_remove:
                    removed.setdefault(role_label.get(r, r.name), []).append(member.display_name)

        changes = sum(len(v) for v in added.values()) + sum(len(v) for v in removed.values())
        logger.info("party_roles: %d role changes, %d parties loaded of %d", changes, len(party_data), len(parties))
        channel = guild.get_channel(config['channels']['reports'])
        if channel is None:
            return
        for embed in build_summary_embeds(added, removed, tr):
            try:
                await channel.send(embed=embed)
            except discord.HTTPException as exc:
                logger.warning("party_roles: could not post the summary: %s", exc)
                break

    @party_roles.before_loop
    async def before_party_roles(self):
        """Wait for the guild cache before the first run, so role member lists are filled."""
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    """Load the party role sync job."""
    await bot.add_cog(PartyRolesJob(bot))
