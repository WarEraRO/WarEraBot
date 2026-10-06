ECONOMY_SKILLS = ('energy', 'companies', 'entrepreneurship', 'production')


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
