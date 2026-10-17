# RBAC as data: action -> {role: rule}. can() is used by the /audit/v1/rbac probes and the /api/v1 routes
# (FR-5.1, spec §5.13). A role missing from an action's dict is denied. Adding a role = one line per action.

POLICY = {
    "create_tenant":   {"super_admin": "always"},
    "manage_fixtures": {"super_admin": "always", "league_organizer": "own_league"},
    "manage_roster":   {"super_admin": "always", "club_manager": "own_club"},
    "manage_products": {"super_admin": "always", "club_manager": "own_club"},
    "edit_player":     {"super_admin": "always", "club_manager": "own_club_player", "player": "self"},
    "view_club":       {"super_admin": "always", "league_organizer": "same_tenant", "club_manager": "same_tenant",
                        "player": "same_tenant", "viewer": "same_tenant"},
    "platform_config": {"super_admin": "always"},
}


def _same_tenant(user, target):
    return user["tenant_id"] is not None and user["tenant_id"] == target.get("tenant_id")


# rule name -> check(user, target). target = {"tenant_id", "league_id"?, "club_id"?, "player_id"?}
RULES = {
    "always": lambda user, target: True,
    "same_tenant": _same_tenant,
    "own_league": lambda user, target: _same_tenant(user, target) and target.get("league_id") == user["league_id"],
    "own_club": lambda user, target: _same_tenant(user, target) and target.get("club_id") == user["club_id"],
    "own_club_player": lambda user, target: (_same_tenant(user, target) and user["club_id"] is not None
                                             and target.get("club_id") == user["club_id"]),
    "self": lambda user, target: (_same_tenant(user, target) and user["player_id"] is not None
                                  and target.get("player_id") == user["player_id"]),
}


def can(user, action, target=None):
    rule = POLICY.get(action, {}).get(user["role"])
    if rule is None:
        return False
    return RULES[rule](user, target or {})
