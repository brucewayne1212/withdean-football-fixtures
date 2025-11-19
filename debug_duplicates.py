#!/usr/bin/env python3
"""
Debug duplicate removal step by step
"""

from text_fixture_parser import TextFixtureParser

test_text = "28/09/25 14:00    Withdean Youth U14 White    Withdean Youth U14 White    VS    Clinical Training FC U14    Clinical Training FC U14    Withdean Youth U11 White"

parser = TextFixtureParser(["Withdean Youth U14 White"])

print("Step 1: Original text")
print(repr(test_text))

print("\nStep 2: After _clean_text")
cleaned = parser._clean_text(test_text)
print(repr(cleaned))

print("\nStep 3: After _remove_duplicate_team_names")
deduplicated = parser._remove_duplicate_team_names(cleaned)
print(repr(deduplicated))

print("\nStep 4: Testing _deduplicate_team_side individually")
# Test each side
vs_parts = deduplicated.split(' vs ')
if len(vs_parts) == 2:
    print(f"Left side before: {repr(vs_parts[0])}")
    left_clean = parser._deduplicate_team_side(vs_parts[0])
    print(f"Left side after: {repr(left_clean)}")
    
    print(f"Right side before: {repr(vs_parts[1])}")
    right_clean = parser._deduplicate_team_side(vs_parts[1])
    print(f"Right side after: {repr(right_clean)}")
