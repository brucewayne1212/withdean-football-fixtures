#!/usr/bin/env python3
"""
Test script to debug FA data parsing issues
"""

from text_fixture_parser import TextFixtureParser

# Example FA fixture text (similar to what would be pasted)
test_text = """28/09/25 10:00    Hassocks Juniors U9 Robins        VS        Withdean Youth U9 Red    Hassocks Juniors U8 Robins    Under 9 Autumn Group B"""

# Your managed teams
managed_teams = ["Withdean Youth U9 Red"]

# Create parser
parser = TextFixtureParser(managed_teams)

# Parse the text
print("Original text:")
print(repr(test_text))
print()

# Test the cleaning
cleaned = parser._clean_text(test_text)
print("Cleaned text:")
print(repr(cleaned))
print()

# Parse the fixture
parsed_data = parser.parse_fa_fixture_text(test_text)
print("Parsed data:")
for key, value in parsed_data.items():
    print(f"  {key}: {repr(value)}")

print()
print("Issue Analysis:")
if parsed_data:
    team = parsed_data.get('team', '')
    opposition = parsed_data.get('opposition', '')
    print(f"Our team: '{team}'")
    print(f"Opposition: '{opposition}'")

    # Check for duplicates
    if team in opposition or opposition in team:
        print("❌ DUPLICATE DETECTED: Team name appears in opposition name or vice versa")
    else:
        print("✅ No duplicates detected")
