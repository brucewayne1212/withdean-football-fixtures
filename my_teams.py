"""
Configuration for Mark Monahan's specific teams
Update this list to show only the teams you personally manage
"""

# Your personally managed teams - only these will be shown in the interface
MY_TEAMS = [
    "U9 Red",  # You're listed as Fixtures Sec for this team
    "U14 Red",  # You're listed as Fixtures Sec for this team
    "U14 Black",  # You're listed as Fixtures Sec for this team
    "U14 Girls Red",  # You're listed as Fixtures Sec for this team
    "U14 White",  # You're listed as Fixtures Sec for this team
    
    # Add any other teams you specifically want to track
    # Uncomment the ones below if you manage them too:
    
    # "U8 Black",
    # "U10 Black", 
    # "U11 Red",
    # "U12 Black",
    # "U15 Red",
    # "U16 Red",
    # "U16 Black",
    # "U17 Red",
]

def get_my_teams():
    """Return the list of teams you personally manage"""
    return MY_TEAMS

def is_my_team(team_name):
    """Check if a team is one of yours (case-insensitive)"""
    if not team_name:
        return False
    return team_name.strip().lower() in [team.lower() for team in MY_TEAMS]

def get_my_team_count():
    """Get the number of teams you manage"""
    return len(MY_TEAMS)