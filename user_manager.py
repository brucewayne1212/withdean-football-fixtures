"""
User and Settings Management System
Handles user preferences, managed teams, and pitch configurations
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Optional

class UserManager:
    def __init__(self, data_file='user_settings.json', user_id=None):
        # Support both single-user (legacy) and multi-user modes
        if user_id:
            self.data_file = f"user_data/{user_id}/user_settings.json"
            self.user_id = user_id
        else:
            self.data_file = data_file
            self.user_id = None
            
        self.settings = {}
        self.load_settings()
        
        # Initialize default user if none exists (legacy mode only)
        if not self.settings and not user_id:
            self.create_default_user()
    
    def load_settings(self):
        """Load user settings from JSON file"""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r') as f:
                    self.settings = json.load(f)
            except Exception as e:
                print(f"Error loading user settings: {e}")
                self.settings = {}
    
    def save_settings(self):
        """Save user settings to JSON file"""
        try:
            with open(self.data_file, 'w') as f:
                json.dump(self.settings, f, indent=2)
        except Exception as e:
            print(f"Error saving user settings: {e}")
    
    def create_default_user(self):
        """Create default user with sample teams and pitches"""
        self.settings = {
            'user': {
                'name': 'Mark Monahan',
                'email': '',
                'role': 'Fixtures Secretary',
                'created_date': datetime.now().isoformat()
            },
            'managed_teams': [
                'U9 Blue',
                'U14 Blue', 
                'U14 Black',
                'U14 Girls Blue',
                'U14 White'
            ],
            'pitches': {
                'Stanley Deason 3G': {
                    'name': 'Stanley Deason 3G',
                    'address': 'Stanley Deason Leisure Centre, 120 Wilson Avenue, BN2 5BP',
                    'parking': 'Stanley Deason Leisure Centre (120 Wilson Avenue, BN2 5BP) - this is NOT at the Dorothy Stringer campus. Parking will be obvious when you arrive at the centre.',
                    'toilets': 'Toilets can be found within the main leisure centre building',
                    'special_instructions': '''Stanley Deason 3G: Please pay special attention to the details about footwear below.

Strict Boot Policy: Stanley Deason 3G pitch has strict boot rules and centre staff that will be doing a boot check before kick-off.

The following footwear is Not Allowed (including coaches and anyone entering the playing area)
• Any Dirty Boots
• Trainers
• Old Style Blades
• Astro Boots

The Following Footwear is Allowed
• All Screw in Studs (including metal studs)
• Modern Moulded Stud Football Boots''',
                    'opening_notes': '3G Opens at 9am. Mark pitch out with cones and push goals into place. Push goals off pitch after match. Be strict with timings.',
                    'warm_up_notes': '20 minutes warm up on 3G. Be strict with timings.'
                },
                'Dorothy Stringer 3G': {
                    'name': 'Dorothy Stringer 3G',
                    'address': 'Dorothy Stringer School, Loder Road, BN1 6PL',
                    'parking': 'Parking for all of these pitches is at Dorothy Stringer School, Loder Road, BN1 6PL. Follow the blue lines on the map below to reach your designated pitch.',
                    'toilets': 'Toilet Access for all attendees to Stringer/Varndean/Balfour is in Dorothy Stringer opposite the 3G entrance.',
                    'special_instructions': 'Map for Dorothy Stringer / Varndean / Balfour only (Stanley Deason 3G users please see info above and use the other postcode)\n\n[Note: Withdean Pitches.png map would be attached to email]',
                    'opening_notes': '3G Opens at 9:30am. Push 9v9 Goals into place (may need to push other goals off the pitch). Push 9v9 goals to the side after match.',
                    'warm_up_notes': '20 minutes warm up on 3G. Push 11v11 goals into place and keep them on the pitch for match after you.'
                },
                'Balfour School Pitch': {
                    'name': 'Balfour School Pitch',
                    'address': 'Balfour School, Brighton',
                    'parking': 'Parking for all of these pitches is at Dorothy Stringer School, Loder Road, BN1 6PL. Follow the blue lines on the map below to reach your designated pitch.',
                    'toilets': 'Toilet Access for all attendees to Stringer/Varndean/Balfour is in Dorothy Stringer opposite the 3G entrance.',
                    'special_instructions': 'Map for Dorothy Stringer / Varndean / Balfour only (Stanley Deason 3G users please see info above and use the other postcode)',
                    'opening_notes': 'Push goals into place (unlocked by Jordan). Keep goals out.',
                    'warm_up_notes': '20 minutes warm up on pitch. Put goals away after match (next to each other on school-side fence, where the chain lock is located)'
                },
                'Varndean College': {
                    'name': 'Varndean College',
                    'address': 'Varndean College, Brighton',
                    'parking': 'Parking for all of these pitches is at Dorothy Stringer School, Loder Road, BN1 6PL. Follow the blue lines on the map below to reach your designated pitch.',
                    'toilets': 'Toilet Access for all attendees to Stringer/Varndean/Balfour is in Dorothy Stringer opposite the 3G entrance.',
                    'special_instructions': 'Map for Dorothy Stringer / Varndean / Balfour only (Stanley Deason 3G users please see info above and use the other postcode)',
                    'opening_notes': 'Push goals into place (unlocked by Jordan). Push goals back (next to other 11v11 goals) after match.',
                    'warm_up_notes': ''
                }
            },
            'preferences': {
                'default_referee_note': 'Referees have been requested for all fixtures but are as yet unconfirmed',
                'default_colours': 'Withdean Youth FC play in Blue and Black Shirts, Black Shorts and Blue and Black Hooped Socks',
                'email_signature': 'Many thanks\n\nWithdean Youth FC',
                'default_day': 'Sunday'
            }
        }
        self.save_settings()
    
    # User management methods
    def get_user_name(self):
        """Get the user's name"""
        return self.settings.get('user', {}).get('name', 'User')
    
    def update_user_info(self, name=None, email=None, role=None):
        """Update user information"""
        if 'user' not in self.settings:
            self.settings['user'] = {}
        
        if name:
            self.settings['user']['name'] = name
        if email:
            self.settings['user']['email'] = email
        if role:
            self.settings['user']['role'] = role
        
        self.save_settings()
    
    # Team management methods
    def get_managed_teams(self):
        """Get list of managed teams"""
        return self.settings.get('managed_teams', [])
    
    def set_managed_teams(self, teams: List[str]):
        """Set the list of managed teams"""
        self.settings['managed_teams'] = teams
        self.save_settings()
    
    def add_managed_team(self, team_name: str):
        """Add a team to managed teams"""
        if 'managed_teams' not in self.settings:
            self.settings['managed_teams'] = []
        
        if team_name not in self.settings['managed_teams']:
            self.settings['managed_teams'].append(team_name)
            self.save_settings()
    
    def remove_managed_team(self, team_name: str):
        """Remove a team from managed teams"""
        if 'managed_teams' in self.settings and team_name in self.settings['managed_teams']:
            self.settings['managed_teams'].remove(team_name)
            self.save_settings()
    
    def is_managed_team(self, team_name: str):
        """Check if team is managed by user"""
        managed_teams = self.get_managed_teams()
        return team_name.strip().lower() in [team.lower() for team in managed_teams]
    
    # Pitch management methods
    def get_all_pitches(self):
        """Get all pitch configurations"""
        return self.settings.get('pitches', {})
    
    def get_pitch_config(self, pitch_name: str):
        """Get configuration for a specific pitch"""
        pitches = self.get_all_pitches()
        
        # Try exact match first
        if pitch_name in pitches:
            return pitches[pitch_name]
        
        # Try partial matches
        pitch_lower = pitch_name.lower().strip()
        for name, config in pitches.items():
            if pitch_lower in name.lower() or name.lower() in pitch_lower:
                return config
        
        # Return default if no match
        return self.get_default_pitch_config(pitch_name)
    
    def get_default_pitch_config(self, pitch_name: str):
        """Get default configuration for unknown pitches"""
        return {
            'name': pitch_name,
            'address': 'Please contact the club for address details',
            'parking': 'Please contact the club for parking information',
            'toilets': 'Please contact the club for toilet facilities information',
            'special_instructions': 'Please contact the club for specific pitch information',
            'opening_notes': '',
            'warm_up_notes': ''
        }
    
    def add_or_update_pitch(self, pitch_config: Dict):
        """Add or update a pitch configuration"""
        if 'pitches' not in self.settings:
            self.settings['pitches'] = {}
        
        pitch_name = pitch_config.get('name', '')
        if pitch_name:
            self.settings['pitches'][pitch_name] = pitch_config
            self.save_settings()
    
    def delete_pitch(self, pitch_name: str):
        """Delete a pitch configuration"""
        if 'pitches' in self.settings and pitch_name in self.settings['pitches']:
            del self.settings['pitches'][pitch_name]
            self.save_settings()
    
    # Preferences methods
    def get_preferences(self):
        """Get user preferences"""
        return self.settings.get('preferences', {})
    
    def update_preferences(self, preferences: Dict):
        """Update user preferences"""
        if 'preferences' not in self.settings:
            self.settings['preferences'] = {}
        
        self.settings['preferences'].update(preferences)
        self.save_settings()
    
    def get_preference(self, key: str, default=None):
        """Get a specific preference"""
        return self.settings.get('preferences', {}).get(key, default)
    
    # Contact management methods
    def get_all_contacts(self):
        """Get all team contacts"""
        return self.settings.get('team_contacts', {})
    
    def get_team_contact(self, team_name: str):
        """Get contact information for a specific team with fuzzy matching"""
        contacts = self.get_all_contacts()
        
        # Try exact match first
        if team_name in contacts:
            return contacts[team_name]
        
        # Normalize team name for better matching
        def normalize_team_name(name):
            """Normalize team name for better matching"""
            if not name:
                return ""
            # Convert to lowercase and remove common suffixes/prefixes
            normalized = name.lower().strip()
            # Remove common football terms
            for term in ['fc', 'football club', 'afc', 'united', 'youth', 'junior', 'senior']:
                normalized = normalized.replace(term, '').strip()
            # Remove extra whitespace
            normalized = ' '.join(normalized.split())
            return normalized
        
        team_normalized = normalize_team_name(team_name)
        
        # Try normalized matches
        for name, contact in contacts.items():
            name_normalized = normalize_team_name(name)
            
            # Exact match after normalization
            if team_normalized == name_normalized:
                return contact
            
            # Partial match (both directions)
            if team_normalized and name_normalized:
                if team_normalized in name_normalized or name_normalized in team_normalized:
                    return contact
        
        # Fallback to original partial matching logic
        team_lower = team_name.lower().strip()
        for name, contact in contacts.items():
            if team_lower in name.lower() or name.lower() in team_lower:
                return contact
        
        return None
    
    def add_or_update_team_contact(self, team_name: str, contact_info: Dict):
        """Add or update contact information for a team"""
        if 'team_contacts' not in self.settings:
            self.settings['team_contacts'] = {}
        
        # Ensure contact_info has required fields
        default_contact = {
            'team_name': team_name,
            'contact_name': '',
            'email': '',
            'phone': '',
            'notes': ''
        }
        default_contact.update(contact_info)
        
        self.settings['team_contacts'][team_name] = default_contact
        self.save_settings()
    
    def delete_team_contact(self, team_name: str):
        """Delete contact information for a team"""
        if 'team_contacts' in self.settings and team_name in self.settings['team_contacts']:
            del self.settings['team_contacts'][team_name]
            self.save_settings()
    
    def get_contacts_for_teams(self, team_names: List[str]) -> Dict[str, Dict]:
        """Get contact information for multiple teams"""
        result = {}
        for team_name in team_names:
            contact = self.get_team_contact(team_name)
            if contact:
                result[team_name] = contact
        return result
    
    # Coach/Manager management methods for internal teams
    def get_all_coaches(self):
        """Get all coach/manager contacts for internal teams"""
        return self.settings.get('team_coaches', {})
    
    def get_team_coach(self, team_name: str):
        """Get coach/manager information for a specific internal team with fuzzy matching"""
        coaches = self.get_all_coaches()
        
        # Try exact match first
        if team_name in coaches:
            return coaches[team_name]
        
        # Try partial matches using the same logic as team contacts
        team_lower = team_name.lower().strip()
        for name, coach in coaches.items():
            if team_lower in name.lower() or name.lower() in team_lower:
                return coach
        
        return None
    
    def add_or_update_team_coach(self, team_name: str, coach_info: Dict):
        """Add or update coach/manager information for an internal team"""
        if 'team_coaches' not in self.settings:
            self.settings['team_coaches'] = {}
        
        # Ensure coach_info has required fields
        default_coach = {
            'team_name': team_name,
            'coach_name': '',
            'email': '',
            'phone': '',
            'role': 'Coach',  # Coach, Manager, Assistant Coach, etc.
            'notes': ''
        }
        default_coach.update(coach_info)
        
        self.settings['team_coaches'][team_name] = default_coach
        self.save_settings()
    
    def delete_team_coach(self, team_name: str):
        """Delete coach/manager information for an internal team"""
        if 'team_coaches' in self.settings and team_name in self.settings['team_coaches']:
            del self.settings['team_coaches'][team_name]
            self.save_settings()
    
    def get_coaches_for_teams(self, team_names: List[str]) -> Dict[str, Dict]:
        """Get coach/manager information for multiple internal teams"""
        result = {}
        for team_name in team_names:
            coach = self.get_team_coach(team_name)
            if coach:
                result[team_name] = coach
        return result
    
    def get_team_coaches(self, team_name: str):
        """Get coaches for a specific team (returns list for template compatibility)"""
        coach = self.get_team_coach(team_name)
        if coach:
            # Return as list with single coach for template compatibility
            return [coach]
        return []
    
    # Email template management methods
    def get_email_template(self):
        """Get custom email template or return default"""
        return self.settings.get('email_template', self._get_default_email_template())
    
    def update_email_template(self, template_content: str):
        """Update custom email template"""
        self.settings['email_template'] = template_content
        self.save_settings()
    
    def reset_email_template(self):
        """Reset email template to default"""
        if 'email_template' in self.settings:
            del self.settings['email_template']
            self.save_settings()
    
    def _get_default_email_template(self):
        """Get the default email template with merge fields"""
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

<h3>CONTACT INFORMATION</h3>

<p><strong>Manager:</strong> {{manager_name}}</p>
<p><strong>Manager Contact:</strong> {{manager_contact}}</p>

<p>{{email_signature}}</p>"""
    
    def get_available_merge_fields(self):
        """Get list of available merge fields for email templates"""
        return [
            '{{date_display}}',
            '{{time_display}}', 
            '{{pitch_name}}',
            '{{pitch_address}}',
            '{{pitch_parking}}',
            '{{pitch_toilets}}',
            '{{pitch_opening_notes}}',
            '{{pitch_warm_up_notes}}',
            '{{pitch_special_instructions}}',
            '{{home_colours}}',
            '{{match_format}}',
            '{{referee_note}}',
            '{{manager_name}}',
            '{{manager_contact}}',
            '{{email_signature}}',
            '{{team_name}}',
            '{{opposition_name}}'
        ]