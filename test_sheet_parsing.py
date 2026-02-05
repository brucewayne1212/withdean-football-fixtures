
import sys
import os
from datetime import datetime, timezone

# Add current directory to path
sys.path.append(os.getcwd())

from weekly_sheet_refresher import parse_fixture_from_row, get_next_sunday

def test_parsing():
    print("Testing fixture parsing...")
    
    # Test case 1: Standard row
    row1 = {
        'Team': 'U12 Warriors',
        'Opposition': 'Hove Rivervale',
        'Home/Away': 'Home',
        'Date': '2023-11-26',
        'Time': '10:00'
    }
    result1 = parse_fixture_from_row(row1)
    print(f"Row 1 result: {result1}")
    
    # Test case 2: Missing date (should use next Sunday)
    row2 = {
        'Team': 'U13 Dynamos',
        'Opposition': 'Patcham',
        'Home/Away': 'Away',
        'Time': '11:00'
    }
    result2 = parse_fixture_from_row(row2)
    print(f"Row 2 result: {result2}")
    print(f"Next Sunday is: {get_next_sunday()}")
    
    # Test case 3: Date format DD/MM/YYYY
    row3 = {
        'Team': 'U14 United',
        'Opposition': 'Worthing',
        'Home/Away': 'Home',
        'Date': '26/11/2023',
        'Time': '12:00'
    }
    result3 = parse_fixture_from_row(row3)
    print(f"Row 3 result: {result3}")

    # Test case 4: Date format with text (might fail in routes/imports.py)
    row4 = {
        'Team': 'U15 City',
        'Opposition': 'Lancing',
        'Home/Away': 'Home',
        'Date': 'Sun 26th Nov',
        'Time': '14:00'
    }
    result4 = parse_fixture_from_row(row4)
    print(f"Row 4 result: {result4}")
    
import re

def parse_flexible_date(date_str):
    """
    Parse date string handling various formats including:
    - YYYY-MM-DD
    - DD/MM/YYYY
    - Day DDth Month (e.g. Sun 26th Nov)
    """
    if not date_str:
        return None
        
    date_str = str(date_str).strip()
    
    # Try ISO format first
    if 'T' in date_str:
        try:
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except:
            pass

    # Try standard formats
    for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y']:
        try:
            return datetime.strptime(date_str, fmt).replace(tzinfo=timezone.utc)
        except:
            continue
            
    # Try "Sun 26th Nov" style
    # Remove day name prefix if present (Sun, Mon, etc)
    clean_date = date_str
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday',
            'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    
    # Sort by length descending to match full names first
    days.sort(key=len, reverse=True)
    
    for day in days:
        if clean_date.lower().startswith(day.lower()):
            clean_date = clean_date[len(day):].strip()
            break
            
    # Remove ordinal suffixes (st, nd, rd, th)
    # Regex to replace 1st, 2nd, 3rd, 4th with 1, 2, 3, 4
    # But be careful not to break month names like August (though Aug is usually used)
    # Safer to just remove st, nd, rd, th if they follow a digit
    clean_date = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', clean_date)
    
    # Try parsing "26 Nov" or "26 November"
    # We need a year. If not present, assume current year or next occurrence?
    # Usually these sheets are for the current season.
    # Let's try adding current year
    current_year = datetime.now().year
    
    for fmt in ['%d %b', '%d %B']:
        try:
            # Parse with current year
            dt = datetime.strptime(f"{clean_date} {current_year}", f"{fmt} %Y")
            return dt.replace(tzinfo=timezone.utc)
        except:
            continue
            
    return None

def test_parsing():
    print("Testing fixture parsing...")
    
    # Test case 1: Standard row
    row1 = {
        'Team': 'U12 Warriors',
        'Opposition': 'Hove Rivervale',
        'Home/Away': 'Home',
        'Date': '2023-11-26',
        'Time': '10:00'
    }
    result1 = parse_fixture_from_row(row1)
    print(f"Row 1 result: {result1}")
    
    # Test case 2: Missing date (should use next Sunday)
    row2 = {
        'Team': 'U13 Dynamos',
        'Opposition': 'Patcham',
        'Home/Away': 'Away',
        'Time': '11:00'
    }
    result2 = parse_fixture_from_row(row2)
    print(f"Row 2 result: {result2}")
    print(f"Next Sunday is: {get_next_sunday()}")
    
    # Test case 3: Date format DD/MM/YYYY
    row3 = {
        'Team': 'U14 United',
        'Opposition': 'Worthing',
        'Home/Away': 'Home',
        'Date': '26/11/2023',
        'Time': '12:00'
    }
    result3 = parse_fixture_from_row(row3)
    print(f"Row 3 result: {result3}")

    # Test case 4: Date format with text (might fail in routes/imports.py)
    row4 = {
        'Team': 'U15 City',
        'Opposition': 'Lancing',
        'Home/Away': 'Home',
        'Date': 'Sun 26th Nov',
        'Time': '14:00'
    }
    result4 = parse_fixture_from_row(row4)
    print(f"Row 4 result: {result4}")
    
    # Test case 5: Forward filling (missing date should use previous)
    # Note: The forward filling logic is in refresh_weekly_fixtures, not parse_fixture_from_row
    # But we can simulate it here to verify the concept
    
    print("\nTesting forward filling concept:")
    last_seen_date = "2023-11-26"
    row5 = {
        'Team': 'U16 Rovers',
        'Opposition': 'Brighton',
        'Home/Away': 'Away',
        'Time': '15:00'
        # No Date column
    }
    
    result5 = parse_fixture_from_row(row5)
    # In the real code, result5['date'] would be empty (or default next Sunday if we didn't remove it), 
    # and then overwritten by last_seen_date in the loop.
    # Let's verify what parse_fixture_from_row returns now that we removed the default.
    print(f"Row 5 raw result: {result5}")
    
    if result5:
        if not result5.get('date'):
            result5['date'] = last_seen_date
            print(f"Row 5 after forward fill: {result5}")
        else:
            print(f"Row 5 has date: {result5['date']}")
    
    # Verify date parsing logic
    print("\nTesting NEW date parsing logic:")
    dates_to_test = [
        '2023-11-26',
        '26/11/2023',
        'Sun 26th Nov',
        'Sunday 26th November',
        '26th Nov',
        'Nov 26th' # This one might fail with current logic, let's see
    ]
    
    for date_str in dates_to_test:
        print(f"Testing date string: '{date_str}'")
        result = parse_flexible_date(date_str)
        if result:
            print(f"  SUCCESS: {result}")
        else:
            print("  FAILED to parse date")

if __name__ == "__main__":
    test_parsing()
