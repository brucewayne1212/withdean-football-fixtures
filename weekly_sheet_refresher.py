"""
Weekly Sheet Refresher - Fetch and parse Google Sheets CSV for weekly fixture updates
"""

import requests
import csv
import io
from datetime import datetime
from typing import List, Dict, Optional
import re


def convert_google_sheet_url_to_csv(url: str) -> str:
    """
    Convert a Google Sheets URL to a CSV export URL

    Handles multiple formats:
    - https://docs.google.com/spreadsheets/d/SHEET_ID/edit...
    - https://docs.google.com/spreadsheets/d/SHEET_ID/...

    Returns CSV export URL
    """
    # Extract sheet ID using regex
    match = re.search(r'/spreadsheets/d/([a-zA-Z0-9-_]+)', url)
    if not match:
        raise ValueError("Invalid Google Sheets URL. Could not extract sheet ID.")

    sheet_id = match.group(1)

    # Check if there's a specific gid (sheet tab)
    gid_match = re.search(r'[#&]gid=([0-9]+)', url)
    gid = gid_match.group(1) if gid_match else '0'

    # Return CSV export URL
    return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"


def fetch_google_sheet_csv(url: str) -> List[Dict[str, str]]:
    """
    Fetch a Google Sheet as CSV and parse it into a list of dictionaries

    Args:
        url: Google Sheets URL (will be converted to CSV export URL)

    Returns:
        List of dictionaries, one per row (excluding header)

    Raises:
        requests.RequestException: If the request fails
        ValueError: If the URL is invalid or the sheet is not publicly accessible
    """
    # Convert to CSV export URL
    csv_url = convert_google_sheet_url_to_csv(url)

    # Fetch the CSV data
    response = requests.get(csv_url, timeout=30)

    if response.status_code == 403:
        raise ValueError("Google Sheet is not publicly accessible. Please share the sheet with 'Anyone with the link can view'.")

    if response.status_code != 200:
        raise requests.RequestException(f"Failed to fetch Google Sheet. Status code: {response.status_code}")

    # Parse CSV
    csv_content = response.content.decode('utf-8')
    csv_reader = csv.DictReader(io.StringIO(csv_content))

    # Convert to list of dictionaries
    rows = list(csv_reader)

    return rows


def get_next_sunday():
    """
    Get the date of the next upcoming Sunday

    Returns:
        String date in format YYYY-MM-DD
    """
    from datetime import datetime, timedelta

    today = datetime.now()
    # In Python's weekday system: Monday=0, Tuesday=1, ..., Saturday=5, Sunday=6
    # Calculate days until next Sunday
    days_ahead = 6 - today.weekday()  # 6 = Sunday

    # If today is Sunday (weekday=6), get next Sunday (7 days from now)
    if days_ahead <= 0:
        days_ahead += 7

    next_sunday = today + timedelta(days=days_ahead)
    return next_sunday.strftime('%Y-%m-%d')


def parse_fixture_from_row(row: Dict[str, str]) -> Optional[Dict]:
    """
    Parse a single CSV row into a fixture dictionary

    Expected columns (flexible - will use what's available):
    - Team, Opposition, Home/Away, Pitch, Date, Time, etc.

    Returns:
        Dictionary with fixture data, or None if the row is invalid/empty
    """
    # Skip empty rows
    if not any(row.values()):
        return None

    # Try to extract key fields (case-insensitive matching)
    fixture = {}

    # Find team name (could be 'Team', 'Team Name', 'Your Team', etc.)
    # Also check for empty string key (first column with no header)
    team_keys = ['team', 'team name', 'your team', 'home team', 'our team', '']
    for key in row.keys():
        if key.lower() in team_keys or key == '':
            value = row[key].strip()
            if value:  # Only set if not empty
                fixture['team'] = value
                break

    # Find opposition
    opp_keys = ['opposition', 'opponent', 'away team', 'vs', 'against']
    for key in row.keys():
        if key.lower() in opp_keys:
            fixture['opposition'] = row[key].strip()
            break

    # Find home/away
    ha_keys = ['home/away', 'home away', 'h/a', 'venue type', 'location']
    for key in row.keys():
        if key.lower() in ha_keys:
            value = row[key].strip().lower()
            if 'home' in value or value == 'h':
                fixture['home_away'] = 'Home'
            elif 'away' in value or value == 'a':
                fixture['home_away'] = 'Away'
            break

    # Find pitch/venue
    pitch_keys = ['pitch', 'venue', 'location', 'ground', 'field', 'stadium']
    for key in row.keys():
        key_lower = key.lower().strip()
        # Check for exact matches first
        if key_lower in pitch_keys and 'type' not in key_lower:
            fixture['pitch'] = row[key].strip()
            break
        # Check for substring matches (e.g. "Pitch Name", "Venue Location")
        if any(pk in key_lower for pk in pitch_keys) and 'type' not in key_lower and 'fee' not in key_lower and 'cost' not in key_lower:
            fixture['pitch'] = row[key].strip()
            break

    # Find date
    date_keys = ['date', 'match date', 'fixture date', 'day']
    for key in row.keys():
        if key.lower() in date_keys:
            fixture['date'] = row[key].strip()
            break

    # Find time - keep the full text from KO&Finish time column as TEXT ONLY
    # This can contain times like "10:00 & 11:00" or text like "close" or "11.30-close"
    # Store as text without trying to parse into datetime
    time_keys = ['time', 'kick off', 'kickoff', 'ko', 'kick-off time', 'start time', 'ko&finish time', 'ko & finish time', 'ko&finish time', 'ko&finish time']
    for key in row.keys():
        normalized_key = key.lower().strip()
        if (normalized_key in time_keys or
            'ko&finish' in normalized_key or
            'ko & finish' in normalized_key or
            'ko&finish time' in normalized_key):
            time_value = row[key].strip()
            # Keep full text as-is, including complex formats like "11.30-close"
            fixture['time'] = time_value
            break

    # Additional fields
    fixture['match_format'] = row.get('Format', row.get('Match Format', '')).strip()
    fixture['fixture_length'] = row.get('Length', row.get('Match Length', '')).strip()
    fixture['each_way'] = row.get('Each Way', '').strip()
    fixture['referee_info'] = row.get('Referee', row.get('Ref', '')).strip()
    fixture['instructions'] = row.get('Instructions', row.get('Notes', '')).strip()

    # Contact fields
    fixture['home_manager'] = row.get('Home Manager', '').strip()
    fixture['fixtures_sec'] = row.get('Fixtures Sec', '').strip()
    fixture['manager_mobile'] = row.get('Manager Mobile', '').strip()
    fixture['contact_1'] = row.get('Contact 1', '').strip()
    fixture['contact_2'] = row.get('Contact 2', '').strip()
    fixture['contact_3'] = row.get('Contact 3', '').strip()
    fixture['contact_5'] = row.get('Contact 5', '').strip()

    # Debug: Print what we extracted
    print(f"DEBUG: Parsed fixture - Team: {fixture.get('team')}, Opposition: {fixture.get('opposition')}, Date: {fixture.get('date')}, Time: {fixture.get('time')}, Pitch: {fixture.get('pitch')}")

    # Must have at least team and opposition
    if 'team' not in fixture or 'opposition' not in fixture:
        return None

    if not fixture.get('team') or not fixture.get('opposition'):
        return None

    return fixture


def refresh_weekly_fixtures(sheet_url: str) -> tuple[List[Dict], List[str]]:
    """
    Refresh weekly fixtures from a Google Sheet

    Args:
        sheet_url: Google Sheets URL

    Returns:
        Tuple of (list of parsed fixtures, list of error messages)
    """
    fixtures = []
    errors = []

    try:
        # Fetch the sheet
        rows = fetch_google_sheet_csv(sheet_url)
        print(f"DEBUG: Fetched {len(rows)} rows from Google Sheet")

        # Get column names from first row
        column_names = list(rows[0].keys()) if rows else []
        print(f"DEBUG: Sheet columns: {column_names}")

        # Initialize last_seen_date with next Sunday as default
        last_seen_date = get_next_sunday()

        # Parse each row
        for i, row in enumerate(rows, start=2):  # Start at 2 (row 1 is header)
            try:
                fixture = parse_fixture_from_row(row)
                if fixture:
                    # Forward filling logic for date
                    if fixture.get('date'):
                        last_seen_date = fixture['date']
                    else:
                        fixture['date'] = last_seen_date
                        
                    fixtures.append(fixture)
                else:
                    print(f"DEBUG: Row {i} skipped - could not parse fixture. Row data: {row}")
            except Exception as e:
                print(f"DEBUG: Error parsing row {i}: {e}")
                errors.append(f"Row {i}: {str(e)}")

        if not fixtures and not errors:
            error_msg = "No valid fixtures found in the sheet. "
            error_msg += f"Found columns: {', '.join(column_names)}. "
            error_msg += "Expected columns: Team (or Team Name), Opposition (or Opponent), Date, Time, etc."
            errors.append(error_msg)

    except Exception as e:
        errors.append(f"Failed to fetch sheet: {str(e)}")

    return fixtures, errors
