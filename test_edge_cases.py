#!/usr/bin/env python3
"""
Test edge cases for duplicate removal
"""

from text_fixture_parser import TextFixtureParser

test_cases = [
    # Original problematic case
    "28/09/25 14:00    Withdean Youth U14 White    Withdean Youth U14 White    VS    Clinical Training FC U14    Clinical Training FC U14    Withdean Youth U11 White",
    
    # Away game with duplicates  
    "28/09/25 10:00    Brighton FC U14 Red    Brighton FC U14 Red    VS    Withdean Youth U14 White    Withdean Youth U14 White    Brighton FC U14 Pitch",
    
    # No duplicates (normal case)
    "28/09/25 15:00    Withdean Youth U14 White    VS    Hove FC U14 Blue    Neutral Ground    Under 14 League",
    
    # Partial duplicates
    "28/09/25 11:00    Withdean Youth U14 White    VS    Clinical Training FC U14    Clinical Training FC    Local Pitch"
]

managed_teams = ["Withdean Youth U14 White", "Withdean Youth"]

for i, test_text in enumerate(test_cases, 1):
    print(f"\n=== Test Case {i} ===")
    print(f"Input: {test_text}")
    
    parser = TextFixtureParser(managed_teams)
    parsed_data = parser.parse_fa_fixture_text(test_text)
    
    if parsed_data:
        print(f"✅ Team: '{parsed_data.get('team', '')}'")
        print(f"✅ Opposition: '{parsed_data.get('opposition', '')}'") 
        print(f"✅ Home/Away: '{parsed_data.get('home_away', '')}'")
        print(f"✅ Venue: '{parsed_data.get('pitch', '')}'")
        print(f"✅ Task Type: '{parsed_data.get('task_type', '')}'")
    else:
        print("❌ Failed to parse")
