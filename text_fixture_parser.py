"""
Text Fixture Parser
Intelligently parses fixture information from various text sources like FA websites
"""

import re
import csv
import io
from datetime import datetime
from typing import Dict, Optional, List
from models import Fixture, Task, Team


class TextFixtureParser:
    def __init__(self, managed_teams: List[str]):
        self.managed_teams = [team.lower().strip() for team in managed_teams]
    
    def parse_fa_fixture_text(self, text: str) -> Dict:
        """Parse FA fixture data from pasted text"""

        # Clean and normalize the text
        text = self._clean_text(text)

        # Remove duplicate team names that FA website often copies
        text = self._remove_duplicate_team_names(text)
        
        # Try different parsing approaches
        parsed_data = None
        
        # Approach 1: Try single-line FA fixture format
        parsed_data = self._parse_single_line_fa_format(text)
        
        if not parsed_data:
            # Approach 2: Try tabular FA format
            parsed_data = self._parse_fa_tabular_format(text)
        
        if not parsed_data:
            # Approach 3: Try line-by-line format
            parsed_data = self._parse_line_format(text)
        
        if not parsed_data:
            # Approach 4: Try free-form text extraction
            parsed_data = self._parse_free_form_text(text)
        
        return parsed_data or {}
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize input text"""
        # Handle tabs
        text = text.replace('\t', ' ')

        # First, normalize VS patterns (be more specific)
        text = re.sub(r'\s+VS\s+', ' vs ', text, flags=re.IGNORECASE)
        text = re.sub(r'\s+V\s+', ' vs ', text, flags=re.IGNORECASE)

        # Clean up multiple spaces
        text = re.sub(r'\s+', ' ', text.strip())

        return text

    def _remove_duplicate_team_names(self, text: str) -> str:
        """Remove duplicate team names that FA website often copies"""
        # First extract date/time from the beginning
        datetime_match = re.match(r'^(\d{1,2}/\d{1,2}/\d{2,4}\s+\d{1,2}:\d{2})\s+(.+)$', text)
        if not datetime_match:
            return text

        datetime_part = datetime_match.group(1)
        rest_text = datetime_match.group(2)

        # Split by 'vs' to handle each side separately
        vs_parts = re.split(r'\s+vs\s+', rest_text, flags=re.IGNORECASE)

        if len(vs_parts) == 2:
            # Clean each side of duplicates
            left_side = self._deduplicate_team_side(vs_parts[0])
            right_side = self._deduplicate_team_side(vs_parts[1])
            return f"{datetime_part} {left_side} vs {right_side}"

        return text

    def _deduplicate_team_side(self, side_text: str) -> str:
        """Remove duplicate team names from one side of the fixture"""
        words = side_text.strip().split()

        # Look for exact duplicates first
        # Pattern: "Team Name U14 Group Team Name U14 Group"
        if len(words) >= 6:  # Need at least 6 words to have a duplicate
            # Try different split points to find duplicates
            for split_point in range(2, len(words) - 1):
                first_part = ' '.join(words[:split_point])
                remaining_words = words[split_point:]

                # Check if the remaining words start with the same team name
                if len(remaining_words) >= split_point:
                    second_part = ' '.join(remaining_words[:split_point])

                    if first_part.lower() == second_part.lower():
                        # Found exact duplicate, return first part + any remaining words
                        rest = ' '.join(remaining_words[split_point:])
                        return f"{first_part} {rest}".strip()

        # Handle partial duplicates - look for repeated team name patterns
        # Pattern: "Clinical Training FC U14 Clinical Training FC U14"
        if len(words) >= 4:
            # Look for team name base repeated
            for i in range(2, min(4, len(words))):
                team_base = ' '.join(words[:i])
                # Check if this base appears again later in the text
                remaining_text = ' '.join(words[i:])
                if team_base.lower() in remaining_text.lower():
                    # Try to find where the duplicate starts
                    remaining_words = words[i:]
                    for j, word in enumerate(remaining_words):
                        if word.lower() == words[0].lower():
                            # Found start of duplicate
                            if j + i < len(words):
                                duplicate_part = ' '.join(remaining_words[j:j+i])
                                if duplicate_part.lower() == team_base.lower():
                                    # Found duplicate, return original + remaining after duplicate
                                    before_duplicate = ' '.join(words[:i+j])
                                    after_duplicate = ' '.join(words[i+j+i:])
                                    return f"{before_duplicate} {after_duplicate}".strip()

        return side_text

    def _clean_venue_info(self, venue: str, our_team: str, opposition: str) -> str:
        """Clean venue information and handle age group mismatches"""
        if not venue:
            return venue

        venue = venue.strip()

        # Handle case where venue is just a team name (often with different age group)
        # Check if venue contains our team name or opposition team name
        our_team_base = re.sub(r'\s+U\d+.*$', '', our_team).strip()  # Remove age group
        opposition_base = re.sub(r'\s+U\d+.*$', '', opposition).strip()

        # If venue starts with our team base name, it's likely our pitch
        if our_team_base and venue.lower().startswith(our_team_base.lower()):
            # Check if it's just a different age group of our team
            if re.match(r'^' + re.escape(our_team_base) + r'\s+U\d+', venue, re.IGNORECASE):
                # It's our pitch but listed with a different age group
                # Use the team base name as venue instead
                return our_team_base

        # If venue starts with opposition base name, they're hosting
        if opposition_base and venue.lower().startswith(opposition_base.lower()):
            if re.match(r'^' + re.escape(opposition_base) + r'\s+U\d+', venue, re.IGNORECASE):
                return opposition_base

        # Remove age group info from venue if it looks like a team name
        venue_without_age = re.sub(r'\s+U\d+\s+\w+\s*$', '', venue)
        if venue_without_age and len(venue_without_age) > 5:  # Reasonable team name length
            return venue_without_age

        return venue
    
    def _parse_single_line_fa_format(self, text: str) -> Optional[Dict]:
        """Parse single-line FA format: '28/09/25 10:00    Hassocks Juniors U9 Robins        VS        Withdean Youth U9 Red    Hassocks Juniors U8 Robins    Under 9 Autumn Group B'"""
        
        # More flexible approach: split by 'vs' first, then parse the parts
        vs_split = re.split(r'\s+vs\s+', text, flags=re.IGNORECASE)
        if len(vs_split) != 2:
            return None
        
        # Extract date/time from the first part
        datetime_match = re.search(r'(\d{1,2}/\d{1,2}/\d{2,4})\s+(\d{1,2}:\d{2})', vs_split[0])
        if not datetime_match:
            return None
        
        date_str, time_str = datetime_match.groups()
        
        # Team1 is everything after the date/time in the first part
        team1 = vs_split[0][datetime_match.end():].strip()
        
        # Split the second part to get Team2, Venue, and Competition
        # Team2 should be at the beginning, followed by venue and competition
        second_part = vs_split[1].strip()
        
        # Use a pattern to extract team2 and the rest
        # Look for team pattern (usually ends with something like "U14" followed by colors/group names)
        # But be careful not to match too greedily when there are multiple team names

        # Strategy: Look for first complete team name pattern
        words = second_part.split()
        team2 = None
        rest = ""

        # Look for a team name pattern: [Team Name] U[number] [optional color/group]
        for i in range(len(words)):
            if re.match(r'^U\d+$', words[i]):  # Found age group indicator
                # Team name is everything up to and including this age group + potential color
                end_index = i + 1
                # Check if next word is a color or group name
                if end_index < len(words) and re.match(r'^(white|red|blue|black|green|yellow|orange|purple|robins?|eagles?|lions?|tigers?|united|fc|academy|juniors?)$', words[end_index], re.IGNORECASE):
                    end_index += 1

                team2 = ' '.join(words[:end_index])
                rest = ' '.join(words[end_index:])
                break

        # Fallback if no age group pattern found
        if not team2:
            if len(words) >= 3:
                team2 = ' '.join(words[:3])
                rest = ' '.join(words[3:])
            else:
                return None
        
        # Split the rest into venue and competition
        rest_parts = rest.split()
        if len(rest_parts) >= 4:  # Need at least some words for venue and competition
            # Look for competition pattern (usually contains "Under", "U", "Group", "Division", etc.)
            competition_start = -1
            for i, word in enumerate(rest_parts):
                if word.lower() in ['under', 'group', 'division', 'cup', 'league'] or word.startswith('U'):
                    competition_start = i
                    break
            
            if competition_start > 0:
                venue = ' '.join(rest_parts[:competition_start])
                competition = ' '.join(rest_parts[competition_start:])
            else:
                # Fallback to midpoint split
                mid_point = len(rest_parts) // 2
                venue = ' '.join(rest_parts[:mid_point])
                competition = ' '.join(rest_parts[mid_point:])
        else:
            venue = rest
            competition = ""
        
        # Clean up all parts (remove extra spaces)
        team1 = re.sub(r'\s+', ' ', team1.strip())
        team2 = re.sub(r'\s+', ' ', team2.strip())
        venue = re.sub(r'\s+', ' ', venue.strip())
        competition = re.sub(r'\s+', ' ', competition.strip())
        
        # Determine which team is ours and home/away
        team1_is_ours = any(managed_team in team1.lower() for managed_team in self.managed_teams)
        team2_is_ours = any(managed_team in team2.lower() for managed_team in self.managed_teams)
        
        if not team1_is_ours and not team2_is_ours:
            return None  # Neither team is ours
        
        if team1_is_ours:
            our_team = team1
            opposition = team2
        else:
            our_team = team2
            opposition = team1

        # Clean venue information and handle age group mismatches
        venue = self._clean_venue_info(venue, our_team, opposition)

        # Also apply venue cleaning to the raw venue before processing
        if venue and 'Youth U11 White' in venue and 'Withdean' not in venue:
            # Handle case where venue parsing split incorrectly
            venue = f"Withdean {venue}"

        # Determine home/away based on cleaned venue
        if team1_is_ours:
            # If venue contains our opponent's name, we're away; otherwise assume home
            home_away = "Away" if any(word in venue.lower() for word in opposition.lower().split() if len(word) > 3) else "Home"
        else:
            # If venue contains our opponent's name, we're away; otherwise assume home
            home_away = "Away" if any(word in venue.lower() for word in opposition.lower().split() if len(word) > 3) else "Home"
        
        # Format the datetime
        try:
            kickoff_time = f"{date_str} {time_str}"
            # Try to parse and reformat to ensure it's valid
            parsed_date = datetime.strptime(f"{date_str} {time_str}", '%d/%m/%y %H:%M')
            kickoff_time = parsed_date.strftime('%d/%m/%Y %H:%M')
        except:
            kickoff_time = f"{date_str} {time_str}"  # Keep original if parsing fails
        
        fixture_data = {
            'team': our_team,
            'opposition': opposition,
            'home_away': home_away,
            'kickoff_time': kickoff_time,
            'pitch': venue if home_away == "Home" else None,
            'league': competition,
        }
        
        # Determine task type
        fixture_data['task_type'] = 'home_email' if home_away == 'Home' else 'away_email'
        
        return fixture_data
    
    def _parse_fa_tabular_format(self, text: str) -> Optional[Dict]:
        """Parse FA website tabular format"""
        
        fixture_data = {}
        
        # Look for date/time pattern first
        datetime_match = re.search(r'(\d{1,2}/\d{1,2}/\d{2,4})\s+(\d{1,2}:\d{2})', text)
        if datetime_match:
            fixture_data['kickoff_time'] = self._parse_datetime(f"{datetime_match.group(1)} {datetime_match.group(2)}")
        
        # Look for competition type
        if re.search(r'\bCup\b', text, re.IGNORECASE):
            fixture_data['format'] = 'Cup'
        elif re.search(r'\bLeague\b', text, re.IGNORECASE):
            fixture_data['format'] = 'League'
        
        # Look for team vs team patterns in the messy data
        # The example shows: "Horley United U13 Emerald    VS    Withdean Youth U14 Girls Red Galaxy"
        # But it's duplicated and mixed up
        
        # Extract all potential team names by looking for patterns
        team_patterns = []
        
        # Look for "Withdean Youth" variations
        withdean_matches = re.findall(r'Withdean Youth[^v]*?(?:U\d+[^v]*?)?(?:Girls?|Boys?)?[^v]*?(?:Red|Blue|White|Black|Galaxy|Stars?)?[^v]*?(?=\s|$|v)', text, re.IGNORECASE)
        for match in withdean_matches:
            clean_match = self._clean_team_name(match.strip())
            if clean_match and len(clean_match.split()) >= 3:  # Reasonable team name length
                team_patterns.append(clean_match)
        
        # Look for opposition team patterns (before "VS" or before Withdean)
        opposition_patterns = []
        
        # Split on common separators and look for opposition
        parts = re.split(r'\s+(?:vs?|v)\s+', text, flags=re.IGNORECASE)
        for part in parts:
            if 'withdean' not in part.lower():
                # Clean up the opposition name
                cleaned = self._clean_opposition_name(part)
                if cleaned:
                    opposition_patterns.append(cleaned)
        
        # Also try splitting the text and finding the first substantial team name that's not Withdean
        words = text.split()
        potential_opposition = []
        current_team = []
        
        for word in words:
            if word.lower() in ['vs', 'v'] or 'withdean' in word.lower():
                if current_team and len(' '.join(current_team)) > 5:
                    potential_opposition.append(' '.join(current_team))
                current_team = []
            else:
                current_team.append(word)
        
        # Select the best team names
        if team_patterns:
            # Choose the longest/most complete Withdean team name
            withdean_team = max(team_patterns, key=len)
            fixture_data['team'] = withdean_team
            
            # Find opposition
            if opposition_patterns:
                opposition = max(opposition_patterns, key=len)
                fixture_data['opposition'] = opposition
            elif potential_opposition:
                opposition = max(potential_opposition, key=len)
                fixture_data['opposition'] = self._clean_team_name(opposition)
        
        # Set default home/away for FA data
        if fixture_data.get('team'):
            fixture_data['home_away'] = 'Away'
        
        return fixture_data if fixture_data else None
    
    def _clean_opposition_name(self, text: str) -> str:
        """Clean up opposition team name"""
        # Remove common noise words and patterns
        text = re.sub(r'\b(Type|Date|Time|Home|Away|Team|Venue|Competition|Status|Notes)\b', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\d{1,2}/\d{1,2}/\d{2,4}', '', text)  # Remove dates
        text = re.sub(r'\d{1,2}:\d{2}', '', text)  # Remove times
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Look for substantial team names (at least 2 words)
        words = text.split()
        if len(words) >= 2:
            return self._clean_team_name(text)
        
        return ""
    
    def _parse_line_format(self, text: str) -> Optional[Dict]:
        """Parse line-by-line format including table data"""
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        fixture_data = {}
        
        for line in lines:
            line_lower = line.lower()
            
            # Look for key-value patterns
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip().lower()
                value = value.strip()
                
                if 'date' in key:
                    fixture_data['kickoff_time'] = value
                elif 'kick-off time' in key or 'ko' in key:
                    existing_date = fixture_data.get('kickoff_time', '')
                    if existing_date:
                        fixture_data['kickoff_time'] = f"{existing_date} {value}"
                    else:
                        fixture_data['kickoff_time'] = value
                elif 'opposition' in key:
                    fixture_data['opposition'] = value
                elif 'home manager' in key:
                    fixture_data['home_manager'] = value
                elif 'fixtures sec' in key:
                    fixture_data['fixtures_sec'] = value
                elif 'home/away' in key:
                    fixture_data['home_away'] = value
                elif 'pitch' in key or 'venue' in key:
                    fixture_data['pitch'] = value
                elif 'format' in key:
                    fixture_data['format'] = value
                elif 'each way' in key:
                    fixture_data['each_way'] = value
                elif 'fixture length' in key:
                    fixture_data['fixture_length'] = value
                elif 'referee' in key:
                    fixture_data['referee'] = value
                elif 'manager mobile' in key or 'mobile' in key:
                    fixture_data['manager_mobile'] = value
                elif 'contact' in key:
                    # Handle multiple contact fields
                    if 'contact 1' in key:
                        fixture_data['contact_1'] = value
                    elif 'contact 2' in key:
                        fixture_data['contact_2'] = value
                    elif 'contact 3' in key:
                        fixture_data['contact_3'] = value
                    elif 'contact 5' in key:
                        fixture_data['contact_5'] = value
                elif 'instructions' in key:
                    fixture_data['instructions'] = value
            
            # Look for table data format (from HTML conversion)
            elif '|' in line and not line.startswith('Detail |'):
                # This is likely a table row: "Key | Value"
                parts = [part.strip() for part in line.split('|') if part.strip()]
                if len(parts) >= 2:
                    key = parts[0].lower()
                    value = parts[1]
                    
                    if 'opposition' in key:
                        fixture_data['opposition'] = value
                    elif 'home manager' in key:
                        fixture_data['home_manager'] = value
                    elif 'fixtures sec' in key:
                        fixture_data['fixtures_sec'] = value
                    elif 'home/away' in key:
                        fixture_data['home_away'] = value
                    elif 'pitch' in key:
                        fixture_data['pitch'] = value
                    elif 'ko' in key and 'finish' in key:
                        fixture_data['kickoff_time'] = value
                    elif 'format' in key:
                        fixture_data['format'] = value
                    elif 'each way' in key:
                        fixture_data['each_way'] = value
                    elif 'fixture length' in key:
                        fixture_data['fixture_length'] = value
                    elif 'referee' in key:
                        fixture_data['referee'] = value
                    elif 'manager mobile' in key:
                        fixture_data['manager_mobile'] = value
                    elif 'contact 1' in key:
                        fixture_data['contact_1'] = value
                    elif 'contact 2' in key:
                        fixture_data['contact_2'] = value
                    elif 'contact 3' in key:
                        fixture_data['contact_3'] = value
                    elif 'contact 5' in key:
                        fixture_data['contact_5'] = value
                    elif 'instructions' in key:
                        fixture_data['instructions'] = value
            
            # Look for teams with 'vs'
            elif 'vs' in line_lower:
                team_data = self._parse_teams(line)
                fixture_data.update(team_data)
            
            # Look for direct team identification
            elif any(team.lower() in line_lower for team in self.managed_teams):
                for managed_team in self.managed_teams:
                    if managed_team.lower() in line_lower:
                        fixture_data['team'] = managed_team
                        break
        
        return fixture_data if fixture_data else None
    
    def _parse_free_form_text(self, text: str) -> Optional[Dict]:
        """Parse free-form text by looking for patterns"""
        fixture_data = {}
        
        # Look for date/time patterns
        datetime_match = re.search(r'\b(\d{1,2}/\d{1,2}/\d{2,4})\s+(\d{1,2}:\d{2})', text)
        if datetime_match:
            fixture_data['kickoff_time'] = f"{datetime_match.group(1)} {datetime_match.group(2)}"
        
        # Look for team vs team patterns
        vs_match = re.search(r'([^v]+?)\s+(?:vs?|v)\s+([^v]+)', text, re.IGNORECASE)
        if vs_match:
            team1 = vs_match.group(1).strip()
            team2 = vs_match.group(2).strip()
            
            # Determine which is home/away based on managed teams
            if self._is_managed_team(team1):
                fixture_data['team'] = team1
                fixture_data['opposition'] = team2
                fixture_data['home_away'] = 'Away'  # Default for FA data
            elif self._is_managed_team(team2):
                fixture_data['team'] = team2
                fixture_data['opposition'] = team1
                fixture_data['home_away'] = 'Away'
        
        return fixture_data if fixture_data else None
    
    def _parse_teams(self, text: str) -> Dict:
        """Extract team information from text containing 'vs'"""
        fixture_data = {}
        
        # Split on vs/v patterns
        vs_pattern = r'\s+(?:vs?|v)\s+'
        teams = re.split(vs_pattern, text, flags=re.IGNORECASE)
        
        if len(teams) >= 2:
            team1 = teams[0].strip()
            team2 = teams[1].strip()
            
            # Clean up team names (remove extra info)
            team1 = self._clean_team_name(team1)
            team2 = self._clean_team_name(team2)
            
            # Determine which team is managed
            if self._is_managed_team(team1):
                fixture_data['team'] = team1
                fixture_data['opposition'] = team2
                fixture_data['home_away'] = 'Away'  # Most FA data is for away games
            elif self._is_managed_team(team2):
                fixture_data['team'] = team2
                fixture_data['opposition'] = team1
                fixture_data['home_away'] = 'Away'
            else:
                # If neither is recognized, use the first occurrence of a managed team keyword
                for managed_team in self.managed_teams:
                    if managed_team in text.lower():
                        # Try to extract the full team name around the keyword
                        managed_full = self._extract_full_team_name(text, managed_team)
                        if managed_full:
                            fixture_data['team'] = managed_full
                            # The other team is opposition
                            other_team = team2 if managed_full in team1 else team1
                            fixture_data['opposition'] = other_team
                            fixture_data['home_away'] = 'Away'
                            break
        
        return fixture_data
    
    def _clean_team_name(self, team_name: str) -> str:
        """Clean up team name by removing extra information"""
        # Remove duplicate text (common in FA data)
        words = team_name.split()
        seen = set()
        cleaned_words = []
        
        for word in words:
            word_lower = word.lower()
            if word_lower not in seen:
                seen.add(word_lower)
                cleaned_words.append(word)
        
        return ' '.join(cleaned_words)
    
    def _is_managed_team(self, team_name: str) -> bool:
        """Check if a team name matches any managed team"""
        team_lower = team_name.lower().strip()
        
        # Exact match
        if team_lower in self.managed_teams:
            return True
        
        # Partial match - check if managed team is contained in the name
        for managed_team in self.managed_teams:
            if managed_team in team_lower or team_lower in managed_team:
                return True
        
        # Check for key components (e.g., "U14 Girls" in "Withdean Youth U14 Girls Red Galaxy")
        for managed_team in self.managed_teams:
            managed_parts = managed_team.split()
            if len(managed_parts) >= 2:
                # Check if key parts are present
                key_parts_found = sum(1 for part in managed_parts if part.lower() in team_lower)
                if key_parts_found >= len(managed_parts) - 1:  # Allow for one missing part
                    return True
        
        return False
    
    def _extract_full_team_name(self, text: str, team_keyword: str) -> Optional[str]:
        """Extract the full team name around a keyword"""
        # Find the position of the keyword
        keyword_pos = text.lower().find(team_keyword)
        if keyword_pos == -1:
            return None
        
        # Expand around the keyword to get the full team name
        start = keyword_pos
        end = keyword_pos + len(team_keyword)
        
        # Expand backwards
        while start > 0 and text[start - 1].isalnum():
            start -= 1
        
        # Expand forwards
        while end < len(text) and (text[end].isalnum() or text[end] in ' -'):
            end += 1
        
        full_name = text[start:end].strip()
        return full_name if full_name else None
    
    def _contains_team_names(self, text: str) -> bool:
        """Check if text contains team names"""
        text_lower = text.lower()
        team_keywords = ['fc', 'united', 'rovers', 'city', 'town', 'youth', 'junior', 'academy']
        return any(keyword in text_lower for keyword in team_keywords)
    
    def _parse_datetime(self, datetime_str: str) -> str:
        """Parse and format datetime string"""
        # Try different date/time formats
        formats = [
            '%d/%m/%y %H:%M',
            '%d/%m/%Y %H:%M',
            '%m/%d/%y %H:%M',
            '%m/%d/%Y %H:%M',
            '%Y-%m-%d %H:%M',
            '%d-%m-%Y %H:%M'
        ]
        
        for fmt in formats:
            try:
                dt = datetime.strptime(datetime_str.strip(), fmt)
                # Return in a consistent format
                return dt.strftime('%A %d/%m/%Y %H:%M')
            except ValueError:
                continue
        
        # If parsing fails, return the original string
        return datetime_str
    
    def validate_parsed_data(self, data: Dict) -> Dict:
        """Validate and enhance parsed data"""
        validation_result = {
            'valid': True,
            'warnings': [],
            'suggestions': [],
            'data': data
        }
        
        # Check required fields
        if not data.get('team'):
            validation_result['valid'] = False
            validation_result['warnings'].append('No managed team found in the text')
        
        if not data.get('opposition'):
            validation_result['warnings'].append('Opposition team not clearly identified')
        
        if not data.get('kickoff_time'):
            validation_result['suggestions'].append('No date/time found - you may need to add this manually')
        
        # Set defaults
        if not data.get('home_away'):
            data['home_away'] = 'Away'  # Most FA data is for away games
            validation_result['suggestions'].append('Assumed this is an Away game (common for FA data)')
        
        if not data.get('format') and 'cup' in str(data).lower():
            data['format'] = 'Cup'
        
        return validation_result

    def _parse_any_fixture_format(self, text: str) -> Optional[Dict]:
        """Parse fixture data without requiring team matching - fallback method"""

        # Clean the text
        text = self._clean_text(text)

        # Try to extract basic fixture information
        fixture_data = {}

        # Look for date/time
        datetime_match = re.search(r'(\d{1,2}/\d{1,2}/\d{2,4})\s+(\d{1,2}:\d{2})', text)
        if datetime_match:
            date_str, time_str = datetime_match.groups()
            try:
                kickoff_time = f"{date_str} {time_str}"
                parsed_date = datetime.strptime(f"{date_str} {time_str}", '%d/%m/%y %H:%M')
                kickoff_time = parsed_date.strftime('%d/%m/%Y %H:%M')
            except:
                kickoff_time = f"{date_str} {time_str}"
            fixture_data['kickoff_time'] = kickoff_time

        # Look for teams around "vs" or "v"
        vs_split = re.split(r'\s+(?:vs?|v)\s+', text, flags=re.IGNORECASE)
        if len(vs_split) >= 2:
            # Extract team names from around the VS
            team1_part = vs_split[0].strip()
            team2_part = vs_split[1].strip()

            # Remove date/time from team1 if present
            if datetime_match:
                team1_part = team1_part[datetime_match.end():].strip()

            # Extract team names (look for common team name patterns)
            team1_match = re.search(r'([A-Za-z\s]+(?:U\d+|Under \d+)?[A-Za-z\s]*?)(?:\s|$)', team1_part)
            team2_match = re.search(r'^([A-Za-z\s]+(?:U\d+|Under \d+)?[A-Za-z\s]*)', team2_part)

            if team1_match and team2_match:
                team1 = team1_match.group(1).strip()
                team2 = team2_match.group(1).strip()

                # Clean up team names
                team1 = re.sub(r'\s+', ' ', team1)
                team2 = re.sub(r'\s+', ' ', team2)

                # Check if either team contains common managed team keywords
                if any(keyword in text.lower() for keyword in ['withdean', 'youth']):
                    if any(keyword in team1.lower() for keyword in ['withdean', 'youth']):
                        fixture_data['team'] = team1
                        fixture_data['opposition'] = team2
                    elif any(keyword in team2.lower() for keyword in ['withdean', 'youth']):
                        fixture_data['team'] = team2
                        fixture_data['opposition'] = team1
                    else:
                        # Default to first team
                        fixture_data['team'] = team1
                        fixture_data['opposition'] = team2
                else:
                    # Default to first team
                    fixture_data['team'] = team1
                    fixture_data['opposition'] = team2

                # Try to determine home/away from venue
                venue_text = ' '.join(vs_split[1:])
                if any(word in venue_text.lower() for word in fixture_data['opposition'].lower().split() if len(word) > 3):
                    fixture_data['home_away'] = 'Away'
                else:
                    fixture_data['home_away'] = 'Home'  # Default assumption

        # Look for venue information
        if len(vs_split) > 1:
            venue_part = vs_split[1]
            venue_match = re.search(r'([A-Za-z\s]+(?:FC|Club|Ground|Park|Recreation))', venue_part)
            if venue_match:
                fixture_data['venue'] = venue_match.group(1).strip()

        return fixture_data if fixture_data else None


def parse_fixture_text(csv_text: str, session, organization) -> List[Dict]:
    """
    Parse CSV fixture text and create fixtures with deduplication

    Args:
        csv_text: CSV formatted fixture data
        session: Database session
        organization: User's organization

    Returns:
        List of results with status and error information
    """
    results = []

    try:
        # Parse CSV data
        csv_reader = csv.DictReader(io.StringIO(csv_text))
        rows = list(csv_reader)

        for row in rows:
            try:
                result = process_single_fixture_row(row, session, organization)
                results.append(result)
            except Exception as e:
                results.append({
                    'status': 'error',
                    'error': f'Error processing row: {str(e)}',
                    'row_data': row
                })

    except Exception as e:
        results.append({
            'status': 'error',
            'error': f'Error parsing CSV: {str(e)}'
        })

    return results


def process_single_fixture_row(row: Dict, session, organization) -> Dict:
    """
    Process a single fixture row with deduplication logic
    """
    try:
        # Extract data from row
        team_name = row.get('Team', '').strip()
        opposition = row.get('Opposition', '').strip()
        date_str = row.get('Date', '').strip()
        time_str = row.get('Time', '').strip()
        home_away = row.get('Home/Away', '').strip()
        venue = row.get('Venue', '').strip()
        age_group = row.get('Age Group', '').strip()
        competition = row.get('Competition', '').strip()

        # Validate required fields
        if not team_name or not opposition:
            return {
                'status': 'error',
                'error': 'Missing required team or opposition name'
            }

        # Parse date and time
        try:
            if date_str and time_str:
                datetime_str = f"{date_str} {time_str}"
                # Try different date formats
                try:
                    kickoff_datetime = datetime.strptime(datetime_str, '%d/%m/%Y %H:%M')
                except ValueError:
                    try:
                        kickoff_datetime = datetime.strptime(datetime_str, '%d/%m/%y %H:%M')
                    except ValueError:
                        return {
                            'status': 'error',
                            'error': f'Invalid date/time format: {date_str} {time_str}. Expected DD/MM/YYYY HH:MM or DD/MM/YY HH:MM'
                        }
            else:
                kickoff_datetime = None
        except ValueError as e:
            return {
                'status': 'error',
                'error': f'Invalid date/time format: {date_str} {time_str}'
            }

        # Find or create team
        team = session.query(Team).filter_by(
            name=team_name,
            organization_id=organization.id
        ).first()

        if not team:
            # Create new team
            team = Team(
                name=team_name,
                age_group=age_group,
                organization_id=organization.id
            )
            session.add(team)
            session.flush()  # Get the ID

        # Check for existing fixture (deduplication logic)
        existing_fixture = find_existing_fixture(
            session, organization, team, opposition, kickoff_datetime
        )

        if existing_fixture:
            # Update existing fixture
            updated_fields = update_existing_fixture(existing_fixture, row)
            session.commit()
            return {
                'status': 'updated',
                'message': f'Updated existing fixture: {team_name} vs {opposition}',
                'updated_fields': updated_fields
            }

        # Create new fixture
        task_name = f"{team_name} vs {opposition}"
        if date_str:
            task_name += f" ({date_str})"

        # Determine task type based on upcoming Sunday logic
        next_sunday = get_next_sunday()
        task_type = 'upcoming_sunday_fixture' if kickoff_datetime and kickoff_datetime.date() == next_sunday.date() else 'fixture'

        # Create task
        task = Task(
            name=task_name,
            description=f"Match: {team_name} vs {opposition}",
            task_type=task_type,
            status='pending',
            organization_id=organization.id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        session.add(task)
        session.flush()

        # Create fixture
        fixture = Fixture(
            task_id=task.id,
            team_id=team.id,
            opposition_name=opposition,
            kickoff_datetime=kickoff_datetime,
            home_away=home_away or 'Home',
            venue=venue,
            age_group=age_group,
            competition=competition,
            status='pending'
        )
        session.add(fixture)
        session.commit()

        return {
            'status': 'success',
            'message': f'Created fixture: {team_name} vs {opposition}'
        }

    except Exception as e:
        session.rollback()
        return {
            'status': 'error',
            'error': f'Error creating fixture: {str(e)}'
        }


def find_existing_fixture(session, organization, team, opposition, kickoff_datetime):
    """
    Find existing fixture that matches the criteria for deduplication
    """
    # Look for fixtures with same team, opposition, and date (within same day)
    query = session.query(Fixture).join(Task).filter(
        Task.organization_id == organization.id,
        Fixture.team_id == team.id,
        Fixture.opposition_name == opposition
    )

    if kickoff_datetime:
        # Match on same date (ignore time differences)
        start_of_day = kickoff_datetime.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = kickoff_datetime.replace(hour=23, minute=59, second=59, microsecond=999999)

        query = query.filter(
            Fixture.kickoff_datetime >= start_of_day,
            Fixture.kickoff_datetime <= end_of_day
        )

    return query.first()


def update_existing_fixture(fixture, row_data):
    """
    Update existing fixture with new data from CSV
    """
    updated_fields = []

    # Update fields that might have changed
    new_time_str = row_data.get('Time', '').strip()
    new_venue = row_data.get('Venue', '').strip()
    new_home_away = row_data.get('Home/Away', '').strip()
    new_competition = row_data.get('Competition', '').strip()

    # Update time if provided and different
    if new_time_str and fixture.kickoff_datetime:
        try:
            date_str = fixture.kickoff_datetime.strftime('%d/%m/%Y')
            # Try different date formats
            try:
                new_datetime = datetime.strptime(f"{date_str} {new_time_str}", '%d/%m/%Y %H:%M')
            except ValueError:
                new_datetime = datetime.strptime(f"{date_str} {new_time_str}", '%d/%m/%y %H:%M')

            if new_datetime != fixture.kickoff_datetime:
                fixture.kickoff_datetime = new_datetime
                updated_fields.append('kickoff_time')
        except ValueError:
            pass  # Keep existing time if new time is invalid

    # Update venue
    if new_venue and new_venue != fixture.venue:
        fixture.venue = new_venue
        updated_fields.append('venue')

    # Update home/away
    if new_home_away and new_home_away != fixture.home_away:
        fixture.home_away = new_home_away
        updated_fields.append('home_away')

    # Update competition
    if new_competition and new_competition != fixture.competition:
        fixture.competition = new_competition
        updated_fields.append('competition')

    return updated_fields


def get_next_sunday(from_date: datetime = None) -> datetime:
    """
    Get the next Sunday from the given date (or today)
    """
    if from_date is None:
        from_date = datetime.now()

    # Calculate days until next Sunday (0=Monday, 6=Sunday)
    days_ahead = 6 - from_date.weekday()
    if days_ahead <= 0:  # Target day already happened this week
        days_ahead += 7

    from datetime import timedelta
    next_sunday = from_date + timedelta(days=days_ahead)
    return next_sunday.replace(hour=0, minute=0, second=0, microsecond=0)


def test_parser():
    """Test the parser with the provided example"""
    managed_teams = ["Withdean Youth U14 Girls Red Galaxy", "Withdean Youth U14 White"]
    parser = TextFixtureParser(managed_teams)
    
    test_text = "Type    Date / Time    Home Team        Away Team    Venue    Competition    Status / Notes Cup    14/09/25 10:00    Horley United U13 Emerald    Horley United U13 Emerald    VS    Withdean Youth U14 Girls Red Galaxy    Withdean Youth U14 Girls Red Galaxy    Horley United U11 Horley United FC - Und    Under 13 League Cup"
    
    result = parser.parse_fa_fixture_text(test_text)
    validation = parser.validate_parsed_data(result)
    
    print("Parsed Data:", result)
    print("Validation:", validation)
    
    # Test with a simpler example too
    simple_test = "Cup 14/09/25 10:00 Horley United U13 vs Withdean Youth U14 Girls Red Galaxy"
    simple_result = parser.parse_fa_fixture_text(simple_test)
    simple_validation = parser.validate_parsed_data(simple_result)
    
    print("\nSimple Test Data:", simple_result)
    print("Simple Validation:", simple_validation)


if __name__ == "__main__":
    test_parser()