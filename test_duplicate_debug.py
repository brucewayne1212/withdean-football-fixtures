#!/usr/bin/env python3
"""
Test to reproduce duplicate team name issue
"""

from text_fixture_parser import TextFixtureParser

# Different test cases that might cause duplicates
test_cases = [
    "28/09/25 10:00    Hassocks Juniors U9 Robins        VS        Withdean Youth U9 Red    Hassocks Juniors U8 Robins    Under 9 Autumn Group B",
    "28/09/25 10:00 Withdean Youth U9 Red VS Hassocks Juniors U9 Robins Withdean Youth Pitch Under 9 Group B",
    "28/09/25 10:00 Withdean Youth U9 Red vs Withdean Youth U9 Blue Away Ground Under 9",
    "Withdean Youth U9 Red v Hassocks Juniors FC U9 Robins 28/09/2025 10:00"
]

managed_teams = ["Withdean Youth U9 Red", "Withdean Youth"]

parser = TextFixtureParser(managed_teams)

for i, test_text in enumerate(test_cases, 1):
    print(f"\n=== Test Case {i} ===")
    print(f"Input: {test_text}")
    
    parsed_data = parser.parse_fa_fixture_text(test_text)
    
    if parsed_data:
        team = parsed_data.get('team', '')
        opposition = parsed_data.get('opposition', '')
        
        print(f"Our team: '{team}'")
        print(f"Opposition: '{opposition}'")
        
        # Check for various duplicate patterns
        issues = []
        if team.lower() in opposition.lower():
            issues.append("Our team name appears in opposition")
        if opposition.lower() in team.lower():
            issues.append("Opposition name appears in our team") 
        if team == opposition:
            issues.append("Team names are identical")
        
        # Check for repeated words
        team_words = team.lower().split()
        opp_words = opposition.lower().split()
        common_words = set(team_words) & set(opp_words)
        if len(common_words) > 2:  # More than just "U9" type words
            issues.append(f"Too many common words: {common_words}")
        
        if issues:
            print(f"❌ ISSUES DETECTED: {', '.join(issues)}")
        else:
            print("✅ No duplicate issues detected")
    else:
        print("❌ Failed to parse")
