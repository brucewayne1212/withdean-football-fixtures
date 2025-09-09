"""
Configuration file for managed teams
Update this list whenever you start or stop managing teams
"""

MANAGED_TEAMS = [
    # Boys Teams
    "U8 Black",
    "U9 Black",
    "U9 Red",
    "U9 White",
    "U10 Black",
    "U10 Red",
    "U11 Red",
    "U11 Black",
    "U11 White",
    "U12 Red",
    "U12 Black",
    "U13 Black",
    "U14 Red",
    "U14 Black",
    "U14 Girls Red",  # Mixed team
    "U14 White",
    "U15 Red",
    "U15 Black",
    "U16 Red",
    "U16 Black",
    "U17 Red",
    "U17 Brighton Electricty",  # Note: keeping original spelling as provided
    "U18 Brighton Electricity",
    
    # Girls Teams
    "U9 Girls Red",
    "U10 Girls Blue",
    "U10 Girls Red",
    "U11 Girls",
    "U12 Girls Red",
    "U12 Girls Blue",
    "U13 Girls Red",
    "U13 Girls Blue",
    "U14 Girls Blue",
    "U15 Girls Red"
]

def get_managed_teams():
    """Return the list of managed teams"""
    return MANAGED_TEAMS

def is_managed_team(team_name):
    """Check if a team name is in the managed teams list (case-insensitive)"""
    return team_name.strip().lower() in [team.lower() for team in MANAGED_TEAMS]