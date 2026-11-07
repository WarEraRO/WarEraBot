import logging

logger = logging.getLogger(__name__)
_warned_missing_skills = False

# skills that count toward an economy build; WarEra v0.27 replaced Entrepreneurship with Management and Leadership.
# Loot Chance counts as an economy skill (user decision, 2026-11-06).
ECONOMY_SKILLS = ('energy', 'companies', 'management', 'leadership', 'production', 'lootChance')
# user.stats.wealth categories a player can spend on fighting; companies are left out
FIGHT_WEALTH_PARTS = ('money', 'items', 'equipments', 'weapons')
# fight wealth tiers, highest first: (tier, minimum fight wealth)
FIGHT_WEALTH_TIERS = (('gold', 15_000), ('silver', 10_000), ('bronze', 5_000), ('iron', 0))


def triangular(n: int) -> int:
    return n * (n + 1) // 2


def _has_skills(user: dict) -> bool:
    """Whether `user` carries a `skills` object; warns once per process when it does not.

    user.getUserLite stopped returning `skills` in v0.28.1 (2026-11-07). A user fetched that way
    would otherwise look like a build with no economy points, i.e. a fighter.
    """
    global _warned_missing_skills
    if isinstance(user.get('skills'), dict):
        return True
    if not _warned_missing_skills:
        _warned_missing_skills = True
        logger.warning("User %s has no 'skills' (fetched with getUserLite?); build left unclassified",
                       user.get('_id'))
    return False


def is_economy_build(user: dict) -> bool | None:
    """True when more than half of the user's skill points (unspent ones included) are in economy skills.

    None when the user has no skill points to judge by, or no `skills` object at all (a getUserLite
    user since v0.28.1); callers treat None as "not a fighter", so a wrongly fetched user is skipped
    rather than pinged or given a role.
    """
    leveling = user.get('leveling') or {}
    total_skill_points = leveling.get('totalSkillPoints') or 0
    if not total_skill_points or not _has_skills(user):
        return None
    economy_skill_points = sum(
        triangular(skill_data.get('level') or 0)
        for skill_name, skill_data in (user.get('skills') or {}).items()
        if skill_name in ECONOMY_SKILLS
    )
    unspent_skill_points = leveling.get('availableSkillPoints') or 0
    return (economy_skill_points + unspent_skill_points) / total_skill_points * 100 > 50


def fight_percent(user: dict) -> float | None:
    """Percentage of the user's skill points that are not in economy skills or unspent.

    The complement of the share is_economy_build compares with 50, so a fight build
    (is_economy_build(user) is False) has a fight percent of at least 50. None when the user has
    no skill points to judge by or no `skills` object.
    """
    leveling = user.get('leveling') or {}
    total_skill_points = leveling.get('totalSkillPoints') or 0
    if not total_skill_points or not _has_skills(user):
        return None
    economy_skill_points = sum(
        triangular(skill_data.get('level') or 0)
        for skill_name, skill_data in (user.get('skills') or {}).items()
        if skill_name in ECONOMY_SKILLS
    )
    unspent_skill_points = leveling.get('availableSkillPoints') or 0
    return 100 - (economy_skill_points + unspent_skill_points) / total_skill_points * 100


def fight_wealth(user: dict) -> dict | None:
    """The user's fight wealth: every user.stats.wealth category except companies.

    Returns the FIGHT_WEALTH_PARTS values plus their sum under 'total', or None when the user has no
    stats.wealth (user.getUserLite does not include it; user.getUserById does).
    """
    wealth = (user.get('stats') or {}).get('wealth')
    if not isinstance(wealth, dict):
        return None
    parts = {part: float(wealth.get(part) or 0) for part in FIGHT_WEALTH_PARTS}
    return {**parts, 'total': sum(parts.values())}


def fight_wealth_tier(value: float) -> str:
    """The FIGHT_WEALTH_TIERS tier ('gold', 'silver', 'bronze' or 'iron') of a fight wealth total."""
    return next((tier for tier, minimum in FIGHT_WEALTH_TIERS if value >= minimum), FIGHT_WEALTH_TIERS[-1][0])
