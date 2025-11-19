#!/usr/bin/env python3
"""
Test FA duplicate text parsing
"""

from text_fixture_parser import TextFixtureParser

# Your actual problematic text
test_text = "28/09/25 14:00    Withdean Youth U14 White    Withdean Youth U14 White    VS    Clinical Training FC U14    Clinical Training FC U14    Withdean Youth U11 White"

managed_teams = ["Withdean Youth U14 White", "Withdean Youth"]

parser = TextFixtureParser(managed_teams)

print("Original problematic text:")
print(repr(test_text))
print()

print("Cleaned text:")
cleaned = parser._clean_text(test_text)
print(repr(cleaned))
print()

print("Parsed data:")
parsed_data = parser.parse_fa_fixture_text(test_text)
if parsed_data:
    for key, value in parsed_data.items():
        print(f"  {key}: {repr(value)}")
else:
    print("  Failed to parse")

print()
print("Issues identified:")
print("1. Team names are duplicated in source")
print("2. Venue shows U11 but teams are U14")
print("3. Opposition team name is also duplicated")
