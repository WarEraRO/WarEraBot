ECONOMY_SKILLS = ('energy', 'companies', 'entrepreneurship', 'production')
# user.stats.wealth categories a player can spend on fighting; companies are left out
FIGHT_WEALTH_PARTS = ('money', 'items', 'equipments', 'weapons')
# fight wealth tiers, highest first: (tier, minimum fight wealth)
FIGHT_WEALTH_TIERS = (('gold', 15_000), ('silver', 10_000), ('bronze', 5_000), ('iron', 0))


def triangular(n: int) -> int:
    return n * (n + 1) // 2


def is_economy_build(user: dict) -> bool | None:
    """True when more than half of the user's skill points (unspent ones included) are in economy skills.

    None when the user has no skill points to judge by.
    """
    leveling = user.get('leveling') or {}
    total_skill_points = leveling.get('totalSkillPoints') or 0
    if not total_skill_points:
        return None
    economy_skill_points = sum(
        triangular(skill_data.get('level') or 0)
        for skill_name, skill_data in (user.get('skills') or {}).items()
        if skill_name in ECONOMY_SKILLS
    )
    unspent_skill_points = leveling.get('availableSkillPoints') or 0
    return (economy_skill_points + unspent_skill_points) / total_skill_points * 100 > 50


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
