"""
FA Fixture Parser Module
Handles parsing multiple fixture lines from FA website format
"""

import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

class FAFixtureParser:
    """Parser for FA website fixture format"""

    def __init__(self):
        # Common patterns for team name variations
        self.withdean_patterns = [
            r'Withdean Youth U\d+\s*(Black|White|Red|Blue|Green)?',
            r'Withdean Youth FC U\d+\s*(Black|White|Red|Blue|Green)?',
            r'Withdean.*U\d+\s*(Black|White|Red|Blue|Green)?'
        ]

    def parse_fa_fixture_lines(self, fixture_text: str) -> List[Dict]:
        """
        Parse multiple FA fixture lines

        Args:
            fixture_text: Multi-line text from FA website

        Returns:
            List of parsed fixture dictionaries
        """
        fixtures = []
        lines = fixture_text.strip().split('\n')

        for line_num, line in enumerate(lines, 1):
            try:
                line = line.strip()
                if not line:
                    continue

                parsed_fixture = self.parse_single_fa_line(line)
                if parsed_fixture:
                    parsed_fixture['line_number'] = line_num
                    fixtures.append(parsed_fixture)
                else:
                    logger.warning(f"Could not parse line {line_num}: {line}")

            except Exception as e:
                logger.error(f"Error parsing line {line_num}: {line}. Error: {str(e)}")
                continue

        return fixtures

    def parse_single_fa_line(self, line: str) -> Optional[Dict]:
        """
        Parse a single FA fixture line

        Expected format:
        L    05/10/25 10:00    Home Team    VS    Away Team    Additional Info...
        Cup  05/10/25 10:00    Home Team    VS    Away Team    Additional Info...
        """
        # Split by multiple spaces/tabs to get main components
        parts = re.split(r'\s{2,}', line.strip())

        if len(parts) < 5:
            return None

        try:
            # Extract components
            competition_type = parts[0].strip()  # L, Cup, etc.
            date_time_str = parts[1].strip()     # 05/10/25 10:00

            # Find the VS separator - look for standalone VS or part containing VS
            vs_index = None
            for i, part in enumerate(parts):
                if part.strip().upper() == 'VS' or 'VS' in part.upper():
                    vs_index = i
                    break

            if vs_index is None:
                return None

            # Extract home team (everything between date_time and VS)
            home_team_parts = parts[2:vs_index]
            home_team = ' '.join(home_team_parts).strip()

            # Handle VS part and extract away team
            # FA format: Home Team | VS | Away Team | Location
            vs_part = parts[vs_index].strip()
            
            if vs_part.upper() == 'VS':
                # VS is standalone
                # Away team is the part immediately after VS (index vs_index + 1)
                away_team_start_idx = vs_index + 1
                away_team = ""
                if away_team_start_idx < len(parts):
                    away_team = parts[away_team_start_idx].strip()
                
                # Location is everything AFTER the away team (index vs_index + 2 onwards)
                location_start_idx = vs_index + 2
            else:
                # VS is combined with away team text
                away_team = re.sub(r'^.*?VS\s*', '', vs_part, flags=re.IGNORECASE).strip()
                # Location would be in the next part after this
                location_start_idx = vs_index + 1

            # Clean up team names - remove duplicated parts and extract first team name
            home_team = self.extract_first_team_name(home_team)
            away_team = self.extract_first_team_name(away_team)

            # Extract location/venue info (remaining parts after away team)
            # This is the location/venue name, NOT the opponent!
            location_parts = []
            if location_start_idx < len(parts):
                location_parts = parts[location_start_idx:]
            location = ' '.join(location_parts).strip()
            
            # The competition field will contain the location/venue
            competition = location

            # Parse date and time
            # If time is provided, combine with date; otherwise use date at midnight
            date_only = self.parse_fa_date(date_time_str)
            if not date_only:
                return None

            # Extract time if present
            time_str = self.extract_time_from_datetime_str(date_time_str)
            
            # Combine date and time if time is available
            if time_str and time_str != 'TBC':
                try:
                    hour, minute = time_str.split(':')
                    combined_datetime = date_only.replace(hour=int(hour), minute=int(minute), second=0, microsecond=0)
                except:
                    combined_datetime = date_only
                    time_str = 'TBC'
            else:
                combined_datetime = date_only
                time_str = 'TBC'

            # Simple logic: first team = home, second team = away
            # The location field (competition) is NOT the opponent - ignore it!
            # The team we're managing will be determined when saving the fixture
            return {
                'competition_type': competition_type,
                'date': combined_datetime,  # Date with time if available, otherwise date at midnight
                'kickoff_time': time_str,  # Time string or TBC
                'home_team': home_team,
                'away_team': away_team,
                'location': location,  # Store location separately (this is the venue, not opponent)
                'competition': competition,
                'raw_line': line
            }

        except Exception as e:
            logger.error(f"Error parsing FA line: {line}. Error: {str(e)}")
            return None

    def parse_fa_date(self, date_time_str: str) -> Optional[datetime]:
        """
        Parse FA date format: DD/MM/YY or DD/MM/YYYY
        Returns date with time set to midnight
        """
        try:
            # Extract just the date part (before any time)
            date_part = date_time_str.split()[0] if ' ' in date_time_str else date_time_str
            
            # Handle format like "05/10/25" (DD/MM/YY)
            try:
                parsed_date = datetime.strptime(date_part, '%d/%m/%y')
                # Ensure year is in 2000s (not 1900s or 3000s)
                if parsed_date.year < 2000:
                    parsed_date = parsed_date.replace(year=parsed_date.year + 100)
                elif parsed_date.year > 2100:
                    # Handle years like 2510 -> 2025, 2610 -> 2026
                    # This happens when DD/MM/YY gets parsed incorrectly
                    year_str = str(parsed_date.year)
                    if len(year_str) == 4:
                        # Extract last two digits and correct the century
                        last_two = year_str[2:]
                        try:
                            correct_year = 2000 + int(last_two)
                            if 2000 <= correct_year <= 2100:
                                parsed_date = parsed_date.replace(year=correct_year)
                        except:
                            pass
                return parsed_date
            except ValueError:
                try:
                    # Try format like "05/10/2025" (DD/MM/YYYY)
                    parsed_date = datetime.strptime(date_part, '%d/%m/%Y')
                    return parsed_date
                except ValueError:
                    logger.error(f"Could not parse date: {date_time_str}")
                    return None
        except Exception as e:
            logger.error(f"Error parsing date: {date_time_str}, {e}")
            return None
    
    def extract_time_from_datetime_str(self, date_time_str: str) -> Optional[str]:
        """
        Extract time from date/time string, return None if no time found
        """
        try:
            # Look for time pattern HH:MM
            time_match = re.search(r'(\d{1,2}):(\d{2})', date_time_str)
            if time_match:
                hour, minute = time_match.groups()
                return f"{hour}:{minute}"
        except:
            pass
        return None

    def identify_our_team(self, home_team: str, away_team: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Identify which team is ours (Withdean) and determine home/away

        Returns:
            (our_team_name, opposition_name, home_away)
        """
        home_is_ours = self.is_withdean_team(home_team)
        away_is_ours = self.is_withdean_team(away_team)

        if home_is_ours and not away_is_ours:
            return home_team, away_team, 'Home'
        elif away_is_ours and not home_is_ours:
            return away_team, home_team, 'Away'
        elif home_is_ours and away_is_ours:
            # Both teams are ours - this shouldn't happen but handle it
            logger.warning(f"Both teams appear to be Withdean: {home_team} vs {away_team}")
            return home_team, away_team, 'Home'  # Default to home team as "ours"
        else:
            # Neither team is ours
            return None, None, None

    def clean_team_name(self, team_name: str) -> str:
        """
        Clean up team name by removing duplicated parts
        """
        if not team_name:
            return ""

        # Split team name into words
        words = team_name.strip().split()

        # Remove consecutive duplicates
        cleaned_words = []
        prev_word = None
        for word in words:
            if word != prev_word:
                cleaned_words.append(word)
            prev_word = word

        return ' '.join(cleaned_words)

    def extract_first_team_name(self, team_section: str) -> str:
        """
        Extract the first complete team name from a section that might contain multiple team references

        FA data often duplicates team names in the format:
        "Withdean Youth U14 White    Withdean Youth U14 White"

        This method extracts just the first occurrence.
        """
        if not team_section:
            return ""

        # Clean up the section
        cleaned = team_section.strip()

        # Common team name patterns to look for
        team_patterns = [
            r'([A-Za-z\s]+Youth\s+U\d+\s*(?:Black|White|Red|Blue|Green)?)',
            r'([A-Za-z\s]+FC\s+U\d+\s*(?:Black|White|Red|Blue|Green)?)',
            r'([A-Za-z\s]+Town\s+U\d+\s*(?:Black|White|Red|Blue|Green)?)',
            r'([A-Za-z\s]+United\s+U\d+\s*(?:Black|White|Red|Blue|Green)?)',
            r'([A-Za-z\s]+\s+U\d+\s*(?:Black|White|Red|Blue|Green)?)',
        ]

        # Try each pattern to find a team name
        for pattern in team_patterns:
            match = re.search(pattern, cleaned, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        # If no pattern matches, try to extract first reasonable team name
        # Split by multiple spaces and take the first reasonable chunk
        parts = re.split(r'\s{2,}', cleaned)
        if parts:
            first_part = parts[0].strip()
            # If it's a reasonable length and contains letters, use it
            if len(first_part) > 3 and re.search(r'[A-Za-z]', first_part):
                return first_part

        # Last resort - just clean and return
        return self.clean_team_name(cleaned)

    def is_withdean_team(self, team_name: str) -> bool:
        """
        Check if a team name is one of our Withdean teams
        """
        if not team_name:
            return False

        team_name_clean = team_name.strip()

        for pattern in self.withdean_patterns:
            if re.search(pattern, team_name_clean, re.IGNORECASE):
                return True

        return False

    def get_next_sunday(self, from_date: datetime = None) -> datetime:
        """
        Get the next Sunday from the given date (or today)
        """
        if from_date is None:
            from_date = datetime.now()

        # Calculate days until next Sunday (0=Monday, 6=Sunday)
        days_ahead = 6 - from_date.weekday()
        if days_ahead <= 0:  # Target day already happened this week
            days_ahead += 7

        next_sunday = from_date + timedelta(days=days_ahead)
        return next_sunday.replace(hour=0, minute=0, second=0, microsecond=0)

    def convert_to_standard_format(self, parsed_fixtures: List[Dict]) -> str:
        """
        Convert parsed FA fixtures to the standard CSV format expected by text_fixture_parser
        """
        if not parsed_fixtures:
            return ""

        # CSV header
        lines = ["Team,Opposition,Date,Time,Home/Away,Venue,Age Group,Competition"]

        for fixture in parsed_fixtures:
            # Format the data
            team = fixture['our_team']
            opposition = fixture['opposition']
            date_str = fixture['datetime'].strftime('%d/%m/%Y')
            time_str = fixture['datetime'].strftime('%H:%M')
            home_away = fixture['home_away']
            venue = ""  # Will be filled in later
            age_group = self.extract_age_group(team)
            competition = fixture['competition']

            # Create CSV line
            csv_line = f'"{team}","{opposition}","{date_str}","{time_str}","{home_away}","{venue}","{age_group}","{competition}"'
            lines.append(csv_line)

        return '\n'.join(lines)

    def extract_age_group(self, team_name: str) -> str:
        """
        Extract age group from team name (e.g., "U14" from "Withdean Youth U14 Black")
        """
        match = re.search(r'U(\d+)', team_name, re.IGNORECASE)
        return f"U{match.group(1)}" if match else ""

    def filter_upcoming_fixtures(self, parsed_fixtures: List[Dict], weeks_ahead: int = 4) -> List[Dict]:
        """
        Filter fixtures to only include those in the next few weeks
        """
        now = datetime.now()
        cutoff_date = now + timedelta(weeks=weeks_ahead)

        return [
            fixture for fixture in parsed_fixtures
            if fixture['datetime'] >= now and fixture['datetime'] <= cutoff_date
        ]

def test_fa_parser():
    """Test function for the FA parser"""
    sample_text = """L    05/10/25 10:00    Worthing United Youth U14        VS    Withdean Youth U14 Black    Withdean Youth U14 Black    Worthing United Youth U14    Under 14 Division Two Red
Cup    05/10/25 10:00    Withdean Youth U14 White    Withdean Youth U14 White    VS    Haywards Heath Town Youth U14    Haywards Heath Town Youth U14    Withdean Youth U11 White    U14 League Trophy
L    19/10/25 10:00    Withdean Youth U14 Black    Withdean Youth U14 Black    VS        Whitehawk U14 White    Withdean Youth U11 Black    Under 14 Division Two Red
L    19/10/25 10:00    Withdean Youth U14 White    Withdean Youth U14 White    VS        Mile Oak Youth U14 White    Withdean Youth U11 White    Under 14 Division Three
Cup    19/10/25 10:00    Whitehawk U14 Red        VS    Withdean Youth U14 Black    Withdean Youth U14 Black    Whitehawk U14 Red    Under 14 League Cup"""

    parser = FAFixtureParser()
    fixtures = parser.parse_fa_fixture_lines(sample_text)

    print(f"Parsed {len(fixtures)} fixtures:")
    for fixture in fixtures:
        print(f"  {fixture['our_team']} ({fixture['home_away']}) vs {fixture['opposition']} - {fixture['datetime']}")

    # Convert to standard format
    csv_output = parser.convert_to_standard_format(fixtures)
    print("\nCSV Output:")
    print(csv_output)

if __name__ == "__main__":
    test_fa_parser()