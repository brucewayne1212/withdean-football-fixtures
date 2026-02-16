"""
Smart Email Generator with Date Intelligence and Spreadsheet Data Integration
Uses actual fixture data from spreadsheet to generate contextually accurate emails
"""

import re
from datetime import datetime, timedelta
from typing import Dict, Optional

class SmartEmailGenerator:
    def __init__(self, user_manager=None):
        self.user_manager = user_manager
    
    def generate_email(self, fixture_data: Dict) -> str:
        """Generate email using actual spreadsheet data with intelligent processing"""
        
        # Process the fixture data
        processed_data = self._process_fixture_data(fixture_data)
        
        # Get user preferences
        preferences = self._get_preferences()

        # Handle team-specific kit colours
        if fixture_data.get('team'):
            team_kit = self._get_team_kit_colours(fixture_data['team'])
            if team_kit and any(team_kit.values()):
                preferences['default_colours'] = self._format_kit_colours(team_kit, fixture_data['team'])

        # Build the email
        email_content = self._build_email_content(processed_data, preferences)

        return email_content.strip()
    
    def _process_fixture_data(self, fixture_data: Dict) -> Dict:
        """Process and enhance fixture data from spreadsheet"""
        processed = fixture_data.copy()
        
        # Process date and time
        processed['date_display'] = self._process_date(fixture_data.get('kickoff_time'))
        processed['time_display'] = self._process_time(fixture_data.get('kickoff_time'))
        
        # Get pitch information
        processed['pitch_info'] = self._get_pitch_information(fixture_data)
        
        # Process opposition
        processed['opposition_display'] = self._process_opposition(fixture_data.get('opposition'))
        
        # Process format and length
        processed['match_format'] = self._process_match_format(fixture_data)
        
        return processed
    
    def _process_date(self, kickoff_time: str) -> str:
        """Extract or calculate the match date"""
        if not kickoff_time:
            return self._get_next_sunday()
        
        # Try to extract date from kickoff_time
        # Look for common date patterns
        date_patterns = [
            r'(\d{1,2})/(\d{1,2})/(\d{4})',  # DD/MM/YYYY or MM/DD/YYYY
            r'(\d{1,2})-(\d{1,2})-(\d{4})',  # DD-MM-YYYY or MM-DD-YYYY
            r'(\d{4})-(\d{1,2})-(\d{1,2})',  # YYYY-MM-DD
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, kickoff_time)
            if match:
                try:
                    # Assume DD/MM/YYYY format for UK
                    day, month, year = match.groups()
                    if len(day) == 4:  # YYYY-MM-DD format
                        year, month, day = day, month, year
                    
                    date_obj = datetime(int(year), int(month), int(day))
                    return date_obj.strftime("%A %d %B %Y")  # e.g., "Sunday 15 October 2023"
                except ValueError:
                    continue
        
        # If no date found, default to next Sunday
        return self._get_next_sunday()
    
    def _get_next_sunday(self) -> str:
        """Get the next Sunday's date"""
        today = datetime.now()
        days_ahead = 6 - today.weekday()  # Sunday is 6
        if days_ahead <= 0:  # Today is Sunday or past
            days_ahead += 7
        next_sunday = today + timedelta(days=days_ahead)
        return next_sunday.strftime("%A %d %B %Y")
    
    def _process_time(self, kickoff_time: str) -> str:
        """Extract kickoff time from the kickoff_time field, picking the first time mentioned"""
        if not kickoff_time:
            return "TBC"
        
        # Look for time patterns in order of priority (most specific first)
        # but combined to find the EARLIEST occurrence in the string
        combined_pattern = r'(\d{1,2}[.:]\d{2}\s*(?:am|pm|AM|PM))|(\d{1,2}\s*(?:am|pm|AM|PM))|(\d{1,2}[.:]\d{2})'
        
        match = re.search(combined_pattern, kickoff_time, re.IGNORECASE)
        if match:
            g1, g2, g3 = match.groups()
            
            # 1. Matches 10:30am or 10.30 PM
            if g1:
                # Normalize to 10:30am
                m = re.match(r'(\d{1,2})[.:](\d{2})\s*(am|pm)', g1, re.IGNORECASE)
                if m:
                    hour, minutes, period = m.groups()
                    return f"{hour}:{minutes}{period.lower()}"
                return g1.lower().replace(' ', '')
            
            # 2. Matches 10am or 10 PM
            if g2:
                # Normalize to 10:00am
                m = re.match(r'(\d{1,2})\s*(am|pm)', g2, re.IGNORECASE)
                if m:
                    hour, period = m.groups()
                    return f"{hour}:00{period.lower()}"
                return g2.lower().replace(' ', '')
            
            # 3. Matches 14:30 or 2:30 (24h format)
            if g3:
                sep = ':' if ':' in g3 else '.'
                hour_str, minutes = g3.split(sep)
                try:
                    hour_int = int(hour_str)
                    if hour_int >= 12:
                        period = "pm"
                        # Handle 12:00 -> 12:00pm, 13:00 -> 1:00pm
                        hour_display = hour_int if hour_int == 12 else hour_int - 12
                    else:
                        period = "am"
                        # Handle 00:00 -> 12:00am
                        hour_display = 12 if hour_int == 0 else hour_int
                    return f"{hour_display}:{minutes}{period}"
                except ValueError:
                    return g3
        
        return str(kickoff_time)
    
    def _get_pitch_information(self, fixture_data: Dict) -> Dict:
        """Get pitch information from user settings or directly from fixture data"""
        pitch_name = fixture_data.get('pitch', 'TBC')

        if self.user_manager:
            return self.user_manager.get_pitch_config(pitch_name)
        else:
            # Use venue data passed directly in fixture_data
            return {
                'name': pitch_name,
                'address': fixture_data.get('venue_address', ''),
                'parking': fixture_data.get('venue_parking', ''),
                'toilets': fixture_data.get('venue_toilets', ''),
                'opening_notes': fixture_data.get('venue_arrival_setup', ''),
                'warm_up_notes': fixture_data.get('venue_warm_up', ''),
                'special_instructions': fixture_data.get('venue_special_instructions', '')
            }
    
    def _process_opposition(self, opposition: str) -> str:
        """Clean up opposition name"""
        if not opposition or str(opposition).lower() in ['nan', 'none', 'tbc', '']:
            return 'TBC'
        return str(opposition).strip()
    
    def _process_match_format(self, fixture_data: Dict) -> str:
        """Process match format information"""
        format_info = fixture_data.get('format', '')
        length_info = fixture_data.get('fixture_length', '')
        each_way_info = fixture_data.get('each_way', '')
        
        format_parts = []
        
        if format_info and str(format_info).lower() not in ['nan', 'none', '']:
            format_parts.append(str(format_info))
        
        if length_info and str(length_info).lower() not in ['nan', 'none', '']:
            format_parts.append(f"{length_info} minutes")
        
        if each_way_info and str(each_way_info).lower() not in ['nan', 'none', '']:
            format_parts.append(f"{each_way_info} each way")
        
        if format_parts:
            return ' - '.join(format_parts)
        else:
            return 'Standard format'
    
    def _get_team_kit_colours(self, team_name: str) -> Optional[Dict]:
        """Get team-specific kit colours from database"""
        if self.user_manager and hasattr(self.user_manager, 'get_team_kit_colours'):
            try:
                return self.user_manager.get_team_kit_colours(team_name)
            except Exception:
                pass
        return None

    def _format_kit_colours(self, kit_data: Dict, team_name: str = '') -> str:
        """Format kit colours into a readable string"""
        team_display = team_name if team_name else 'Withdean Youth FC'
        parts = []

        # Home kit
        home_parts = []
        if kit_data.get('home_shirt'):
            home_parts.append(kit_data['home_shirt'])
        if kit_data.get('home_shorts'):
            home_parts.append(kit_data['home_shorts'])
        if kit_data.get('home_socks'):
            home_parts.append(kit_data['home_socks'])

        if home_parts:
            parts.append(f"Home: {', '.join(home_parts)}")

        # Away kit
        away_parts = []
        if kit_data.get('away_shirt'):
            away_parts.append(kit_data['away_shirt'])
        if kit_data.get('away_shorts'):
            away_parts.append(kit_data['away_shorts'])
        if kit_data.get('away_socks'):
            away_parts.append(kit_data['away_socks'])

        if away_parts:
            parts.append(f"Away: {', '.join(away_parts)}")

        if parts:
            return f"{team_display} play in {', '.join(parts)}"
        else:
            return 'Withdean Youth FC play in Blue and Black Shirts, Black Shorts and Blue and Black Hooped Socks'

    def _get_preferences(self) -> Dict:
        """Get user preferences or return defaults"""
        if self.user_manager:
            return self.user_manager.get_preferences()
        else:
            return {
                'default_colours': 'Withdean Youth FC play in Blue and Black Shirts, Black Shorts and Blue and Black Hooped Socks',
                'default_referee_note': 'Referees have been requested for all fixtures but are as yet unconfirmed',
                'email_signature': 'Many thanks\n\nWithdean Youth FC',
                'default_day': 'Sunday'
            }
    
    def _build_email_content(self, processed_data: Dict, preferences: Dict) -> str:
        """Build the complete email content using custom template with merge field replacement"""
        
        # Get the custom template from user settings
        template = self.user_manager.get_email_template() if self.user_manager else self._get_fallback_template()
        
        # Build map section with priority: custom uploaded maps > Google Drive > Google Maps static
        map_section = ''
        custom_map_filename = processed_data['pitch_info'].get('custom_map_filename', '')
        map_image_url = processed_data['pitch_info'].get('map_image_url', '')

        if custom_map_filename:
            # Use custom uploaded map with highest priority
            custom_map_url = f"/static/uploads/maps/{custom_map_filename}"
            map_section = f'''
<div style="margin: 20px 0;">
    <h4>ESTATE WALKING MAP</h4>
    <p>Use this map to find your way around our estate:</p>
    <div style="text-align: center; margin: 15px 0;">
        <img src="{custom_map_url}" alt="Estate Walking Map" style="max-width: 100%; height: auto; border: 1px solid #ccc; border-radius: 5px;">
    </div>
</div>'''
            # Update the map_image_url for merge field use
            map_image_url = custom_map_url
        elif map_image_url:
            if 'drive.google.com' in map_image_url:
                # It's a Google Drive map
                map_section = f'''
<div style="margin: 20px 0;">
    <h4>ESTATE WALKING MAP</h4>
    <p>Use this map to find your way around our estate:</p>
    <div style="text-align: center; margin: 15px 0;">
        <img src="{map_image_url}" alt="Estate Walking Map" style="max-width: 100%; height: auto; border: 1px solid #ccc; border-radius: 5px;">
    </div>
</div>'''
            else:
                # It's a Google Maps static image
                map_section = f'''
<div style="margin: 20px 0;">
    <h4>LOCATION MAP</h4>
    <div style="text-align: center; margin: 15px 0;">
        <img src="{map_image_url}" alt="Location Map" style="max-width: 100%; height: auto; border: 1px solid #ccc; border-radius: 5px;">
    </div>
</div>'''

        # Build further instructions section
        instructions = processed_data.get('instructions', '')
        if instructions and instructions.strip():
            instructions_section = f'''
<h3>FURTHER INSTRUCTIONS FOR WITHDEAN MANAGEMENT</h3>

<p>{instructions}</p>
'''
        else:
            instructions_section = ''

        # Create merge field values
        merge_values = {
            'date_display': processed_data['date_display'],
            'time_display': processed_data['time_display'],
            'pitch_name': processed_data['pitch_info']['name'],
            'pitch_address': processed_data['pitch_info'].get('address', ''),
            'pitch_parking': processed_data['pitch_info'].get('parking', ''),
            'pitch_toilets': processed_data['pitch_info'].get('toilets', ''),
            'pitch_opening_notes': processed_data['pitch_info'].get('opening_notes', ''),
            'pitch_warm_up_notes': processed_data['pitch_info'].get('warm_up_notes', ''),
            'pitch_special_instructions': processed_data['pitch_info'].get('special_instructions', ''),
            'pitch_map_image': map_image_url,
            'pitch_google_maps_link': self._ensure_absolute_url(processed_data['pitch_info'].get('google_maps_link', '')),
            'pitch_map_section': map_section,
            'home_colours': preferences.get('default_colours', 'Withdean Youth FC play in Blue and Black Shirts, Black Shorts and Blue and Black Hooped Socks'),
            'match_format': processed_data['match_format'],
            'referee_note': preferences.get('default_referee_note', 'Referees have been requested for all fixtures but are as yet unconfirmed'),
            'further_instructions': processed_data.get('instructions', ''),
            'further_instructions_section': instructions_section,
            'manager_name': processed_data.get('manager_name', ''),
            'manager_email': processed_data.get('manager_email', ''),
            'manager_phone': processed_data.get('manager_phone', ''),
            'manager_contact': processed_data.get('manager_contact', ''),  # Keep for backward compatibility
            'email_signature': preferences.get('email_signature', 'Many thanks\n\nWithdean Youth FC'),
            'team_name': processed_data.get('team', ''),
            'opposition_name': processed_data['opposition_display']
        }
        
        # Replace merge fields in template
        # Handle both normal {{field}} and URL-encoded %7B%7Bfield%7D%7D patterns
        # (Quill editor URL-encodes merge fields when they appear in href attributes)
        email_content = template
        for field, value in merge_values.items():
            # Replace normal merge field pattern
            email_content = email_content.replace('{{' + field + '}}', str(value or ''))
            # Replace URL-encoded merge field pattern (for links)
            email_content = email_content.replace('%7B%7B' + field + '%7D%7D', str(value or ''))
            # Also handle mixed case encoding (just in case)
            email_content = email_content.replace('%7b%7b' + field + '%7d%7d', str(value or ''))
        
        # Post-processing: Fix Google Maps links where Quill stripped the href
        # (existing templates may have about:blank or empty href from Quill sanitization)
        google_maps_url = merge_values.get('pitch_google_maps_link', '')
        if google_maps_url:
            import re
            # Fix links with about:blank href that contain "Google Maps" in the text
            email_content = re.sub(
                r'<a\s+href=["\']about:blank["\']([^>]*)>([^<]*Google Maps[^<]*)</a>',
                f'<a href="{google_maps_url}"\\1>\\2</a>',
                email_content,
                flags=re.IGNORECASE
            )
            # Fix links with empty href that contain "Google Maps" in the text
            email_content = re.sub(
                r'<a\s+href=["\']["\']([^>]*)>([^<]*Google Maps[^<]*)</a>',
                f'<a href="{google_maps_url}"\\1>\\2</a>',
                email_content,
                flags=re.IGNORECASE
            )
        
        return email_content

    
    def _get_fallback_template(self):
        """Fallback template if no user manager available"""
        return """<p><strong><u>In the event of any issues impacting your fixture please communicate directly with your opposition manager - This email will NOT be monitored</u></strong></p>

<p>Dear Fixtures Secretary</p>

<p>Please find details of your upcoming fixture at <strong>Withdean Youth FC</strong></p>

<p><strong>Please confirm receipt:</strong> Please copy the relevant Withdean Youth FC manager to your response.</p>

<p><strong>Any issues:</strong> Managers please contact your opposition directly using the contact details supplied if you have any issues that will impact your attendance (ideally by phone call or text message).</p>

<p><strong>Please Contact Managers Directly:</strong> Our Fixtures secretaries will not pick up on late messages so it is vital you communicate directly with your opposition manager once you have been put in touch.</p>

<h3>FIXTURE DETAILS</h3>

<p><strong>Date:</strong> {{date_display}}</p>

<p><strong>Kick-off Time:</strong> {{time_display}}</p>

<p><strong>Pitch Location:</strong> {{pitch_name}} (see attached map for relevant pitch location)</p>

<p><strong>Home Colours:</strong> {{home_colours}}</p>

<p><strong>Match Format:</strong> {{match_format}}</p>

<p><strong>Referees:</strong> {{referee_note}}</p>

<h3>VENUE INFORMATION</h3>

<p><strong>Address:</strong> {{pitch_address}}</p>

<p><strong>Parking:</strong> {{pitch_parking}}</p>

<p><strong>Toilets:</strong> {{pitch_toilets}}</p>

<p><strong>Arrival & Setup:</strong> {{pitch_opening_notes}}</p>

<p><strong>Warm-up:</strong> {{pitch_warm_up_notes}}</p>

<p><strong>Special Instructions:</strong> {{pitch_special_instructions}}</p>

<p><strong>Google Maps Link:</strong> <a href="{{pitch_google_maps_link}}">{{pitch_name}} Google Maps</a></p>

{{pitch_map_section}}

{{further_instructions_section}}

<h3>CONTACT INFORMATION</h3>

<p><strong>Manager:</strong> {{manager_name}}</p>
<p><strong>Email:</strong> {{manager_email}}</p>
<p><strong>Phone:</strong> {{manager_phone}}</p>

<p>{{email_signature}}</p>"""

    def generate_subject_line(self, fixture_data: Dict) -> str:
        """Generate subject line using processed data"""
        team = fixture_data.get('team', 'Team')
        # Add Withdean Youth prefix if not already present
        if team and 'Withdean Youth' not in team:
            team = f"Withdean Youth {team}"
        opposition = self._process_opposition(fixture_data.get('opposition'))
        date_part = self._process_date(fixture_data.get('kickoff_time')).split()[1:3]  # Get day and month
        date_str = " ".join(date_part) if len(date_part) >= 2 else ""

        if date_str:
            return f"{team} vs {opposition} - {date_str} - Fixture Details"
        else:
            return f"{team} vs {opposition} - Fixture Details"

    def _ensure_absolute_url(self, url: str) -> str:
        """Ensure the URL is absolute to avoid relative link resolution issues"""
        if not url or not url.strip() or url.strip().lower() in ['nan', 'tbc']:
            return ''
        
        stripped_url = url.strip()
        
        # If it looks like a domain but doesn't have a protocol, add https://
        if not stripped_url.startswith(('http://', 'https://', 'mailto:', 'tel:')):
            # Special case for 127.0.0.1 or localhost which we want to avoid but if it's there
            # we should still treat it as the "intended" URL if it starts with them
            if stripped_url.startswith(('127.0.0.1', 'localhost')):
                return f"http://{stripped_url}"
            return f"https://{stripped_url}"
            
        return stripped_url
