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
    
    def _process_time(self, kickoff_time: str) -> str:
        """Extract kick-off time from the time string"""
        if not kickoff_time:
            return "TBC"
        
        # Look for time patterns
        time_patterns = [
            r'(\d{1,2}):(\d{2})\s*(am|pm)',  # 10:30am, 2:45pm
            r'(\d{1,2}):(\d{2})',           # 10:30, 14:45
            r'(\d{1,2})\s*(am|pm)',         # 10am, 2pm
        ]
        
        for pattern in time_patterns:
            match = re.search(pattern, kickoff_time.lower())
            if match:
                if len(match.groups()) == 3:  # With am/pm
                    hour, minute, period = match.groups()
                    return f"{hour}:{minute}{period}"
                elif len(match.groups()) == 2:
                    if match.groups()[1] in ['am', 'pm']:  # Hour only with am/pm
                        hour, period = match.groups()
                        return f"{hour}:00{period}"
                    else:  # Hour:minute in 24h format
                        hour, minute = match.groups()
                        hour_int = int(hour)
                        if hour_int > 12:
                            return f"{hour_int-12}:{minute}pm"
                        elif hour_int == 12:
                            return f"12:{minute}pm"
                        else:
                            return f"{hour}:{minute}am"
        
        return kickoff_time  # Return original if no pattern found
    
    def _get_next_sunday(self) -> str:
        """Get the next Sunday's date"""
        today = datetime.now()
        days_until_sunday = (6 - today.weekday()) % 7
        if days_until_sunday == 0:  # Today is Sunday
            days_until_sunday = 7  # Next Sunday
        
        next_sunday = today + timedelta(days=days_until_sunday)
        return next_sunday.strftime("%A %d %B %Y")
    
    def _process_opposition(self, opposition: str) -> str:
        """Process opposition team name"""
        if not opposition:
            return "TBC"
        
        # Clean up common placeholder text
        opposition_str = str(opposition).strip()
        if opposition_str.lower() in ['friendly - manager to sort', 'manager to sort', 'tbc', 'nan']:
            return "TBC"
        
        return opposition_str
    
    def _process_match_format(self, fixture_data: Dict) -> str:
        """Process match format information"""
        format_info = fixture_data.get('format', '')
        length_info = fixture_data.get('fixture_length', '')
        each_way = fixture_data.get('each_way', '')
        
        parts = []
        if format_info:
            parts.append(format_info)
        if each_way:
            parts.append(f"{each_way} each way")
        if length_info:
            parts.append(f"({length_info} total)")
        
        return " - ".join(parts) if parts else "Standard format"
    
    def _get_pitch_information(self, fixture_data: Dict) -> Dict:
        """Get comprehensive pitch information"""
        pitch_name = fixture_data.get('pitch')
        instructions = fixture_data.get('instructions')
        
        # Get user's custom pitch config if available
        if self.user_manager and pitch_name:
            pitch_config = self.user_manager.get_pitch_config(pitch_name)
        else:
            pitch_config = self._get_default_pitch_config(pitch_name)
        
        # Add spreadsheet instructions to pitch config
        if instructions:
            if pitch_config.get('special_instructions'):
                pitch_config['special_instructions'] += f"\n\nAdditional Instructions: {instructions}"
            else:
                pitch_config['special_instructions'] = f"Additional Instructions: {instructions}"
        
        return pitch_config
    
    def _get_default_pitch_config(self, pitch_name: str) -> Dict:
        """Get default pitch configuration"""
        return {
            'name': pitch_name or 'TBC',
            'address': 'Please contact the club for address details',
            'parking': 'Please contact the club for parking information',
            'toilets': 'Please contact the club for toilet facilities information',
            'special_instructions': '',
            'opening_notes': '',
            'warm_up_notes': ''
        }
    
    def _get_preferences(self) -> Dict:
        """Get user preferences or defaults"""
        if self.user_manager:
            return self.user_manager.get_preferences()
        else:
            return {
                'default_referee_note': 'Referees have been requested for all fixtures but are as yet unconfirmed',
                'default_colours': 'Withdean Youth FC play in Red and Black Shirts, Black Shorts and Red and Black Hooped Socks',
                'email_signature': 'Many thanks\n\nWithdean Youth FC',
                'default_day': 'Sunday'
            }
    
    def _build_email_content(self, processed_data: Dict, preferences: Dict) -> str:
        """Build the complete email content with HTML formatting"""
        
        # Header section with formatting
        header = """<p><strong><u>In the event of any issues impacting your fixture please communicate directly with your opposition manager - This email will NOT be monitored</u></strong></p>

<p>Dear Fixtures Secretary</p>

<p>Please find details of your upcoming fixture at <strong>Withdean Youth FC</strong></p>

<p><strong>Please confirm receipt:</strong> Please copy the relevant Withdean Youth FC manager to your response.</p>

<p><strong>Any issues:</strong> Managers please contact your opposition directly using the contact details supplied if you have any issues that will impact your attendance (ideally by phone call or text message).</p>

<p><strong>Please Contact Managers Directly:</strong> Our Fixtures secretaries will not pick up on late messages so it is vital you communicate directly with your opposition manager once you have been put in touch.</p>"""
        
        # Match details section with formatting
        match_details = f"""<h3>FIXTURE DETAILS</h3>

<p><strong>Date:</strong> {processed_data['date_display']}</p>

<p><strong>Kick-off Time:</strong> {processed_data['time_display']}</p>

<p><strong>Pitch Location:</strong> {processed_data['pitch_info']['name']} (see attached map for relevant pitch location)</p>

<p><strong>Home Colours:</strong> {preferences.get('default_colours', 'Withdean Youth FC play in Red and Black Shirts, Black Shorts and Red and Black Hooped Socks')}</p>

<p><strong>Match Format:</strong> {processed_data['match_format']}</p>

<p><strong>Referees:</strong> {preferences.get('default_referee_note', 'Referees have been requested for all fixtures but are as yet unconfirmed')}</p>"""
        
        # Pitch information section with formatting
        pitch_section = ""
        pitch_info = processed_data['pitch_info']
        
        # Start pitch information section
        if any(pitch_info.get(key) for key in ['address', 'parking', 'toilets', 'opening_notes', 'warm_up_notes', 'special_instructions']):
            pitch_section += "<h3>VENUE INFORMATION</h3>"
        
        if pitch_info.get('address'):
            pitch_section += f"<p><strong>Address:</strong> {pitch_info['address']}</p>"
        
        if pitch_info.get('parking'):
            pitch_section += f"<p><strong>Parking:</strong> {pitch_info['parking']}</p>"
        
        if pitch_info.get('toilets'):
            pitch_section += f"<p><strong>Toilets:</strong> {pitch_info['toilets']}</p>"
        
        if pitch_info.get('opening_notes'):
            pitch_section += f"<p><strong>Arrival & Setup:</strong> {pitch_info['opening_notes']}</p>"
        
        if pitch_info.get('warm_up_notes'):
            pitch_section += f"<p><strong>Warm-up:</strong> {pitch_info['warm_up_notes']}</p>"
        
        if pitch_info.get('special_instructions'):
            pitch_section += f"<p><strong>Special Instructions:</strong><br>{pitch_info['special_instructions'].replace(chr(10), '<br>')}</p>"
        
        # Contact details and additional information section
        contact_section = self._build_contact_details_section(processed_data)
        
        # Footer section with formatting
        day_name = processed_data['date_display'].split()[0] if processed_data['date_display'] else preferences.get('default_day', 'Sunday')
        signature = preferences.get('email_signature', 'Many thanks\n\nWithdean Youth FC').replace('\n', '<br>')
        
        footer = f"""<p>We look forward to hosting you on <strong>{day_name}</strong></p>

<p>{signature}</p>"""
        
        # Combine all sections
        full_email = f"{header}<br>{match_details}<br>{pitch_section}<br>{contact_section}<br>{footer}"
        
        return full_email
    
    def _build_contact_details_section(self, processed_data: Dict) -> str:
        """Build comprehensive match details and contact information section"""
        
        # All fields in the order specified, using exact spreadsheet headings
        all_fields = [
            ('home_manager', 'Home Manager'),
            ('fixtures_sec', 'Fixtures Sec'),
            ('opposition', 'Opposition'),
            ('home_away', 'Home/Away'),
            ('pitch', 'Pitch'),
            ('kickoff_time', 'KO&Finish time'),
            ('instructions', 'Further Instructions for Withdean Management'),
            ('format', 'Format'),
            ('each_way', 'Each Way'),
            ('fixture_length', 'Fixture Length'),
            ('referee', 'Referee?'),
            ('manager_mobile', 'Home Manager Mobile'),
            ('contact_1', 'Home Team Contact 1'),
            ('contact_2', 'Home Team Contact 2'),
            ('contact_3', 'Home Team Contact 3'),
            ('contact_5', 'Home Team Contact 5')
        ]
        
        # Collect all available information
        available_info = []
        
        for field_key, field_label in all_fields:
            value = processed_data.get(field_key)
            if value and str(value).strip() and str(value).lower() not in ['nan', 'none', 'tbc', '']:
                # Handle multi-line instructions
                if field_key == 'instructions' and '\n' in str(value):
                    formatted_value = str(value).replace('\n', '<br>')
                else:
                    formatted_value = str(value)
                
                available_info.append((field_label, formatted_value))
        
        # Build the section HTML
        section_html = ""
        
        if available_info:
            section_html += "<h3>MATCH & CONTACT DETAILS</h3>"
            section_html += '<table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse; width: 100%; margin-bottom: 15px;">'
            section_html += '<tr style="background-color: #f0f0f0;"><th style="text-align: left; padding: 8px; width: 30%;"><strong>Detail</strong></th><th style="text-align: left; padding: 8px;"><strong>Information</strong></th></tr>'
            
            for label, value in available_info:
                section_html += f'<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>{label}</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{value}</td></tr>'
            
            section_html += '</table>'
        
        return section_html
    
    def generate_subject_line(self, fixture_data: Dict) -> str:
        """Generate subject line using processed data"""
        team = fixture_data.get('team', 'Team')
        opposition = self._process_opposition(fixture_data.get('opposition'))
        date_part = self._process_date(fixture_data.get('kickoff_time')).split()[1:3]  # Get day and month
        date_str = " ".join(date_part) if len(date_part) >= 2 else ""
        
        if date_str:
            return f"{team} vs {opposition} - {date_str} - Fixture Details"
        else:
            return f"{team} vs {opposition} - Fixture Details"