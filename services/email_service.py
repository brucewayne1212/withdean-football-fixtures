from typing import Dict, Optional
from models import Team, Pitch

class TemplateManager:
    """Adapter class to provide a consistent interface for SmartEmailGenerator"""
    def __init__(self, template_content, pitch_obj=None, team_obj=None):
        self.template_content = template_content or self._get_default_template()
        self.pitch_obj = pitch_obj
        self.team_obj = team_obj

    def get_email_template(self):
        return self.template_content

    def get_pitch_config(self, pitch_name):
        """Return pitch configuration"""
        if self.pitch_obj:
            return {
                'name': self.pitch_obj.name,
                'address': self.pitch_obj.address or '',
                'parking': self.pitch_obj.parking_info or '',
                'toilets': self.pitch_obj.toilet_info or '',
                'opening_notes': self.pitch_obj.opening_notes or '',
                'warm_up_notes': self.pitch_obj.warm_up_notes or '',
                'special_instructions': self.pitch_obj.special_instructions or '',
                'map_image_url': self.pitch_obj.map_image_url or '',
                'google_maps_link': self.pitch_obj.google_maps_link or '',
                'custom_map_filename': self.pitch_obj.custom_map_filename or ''
            }
        else:
            # Return default configuration for unknown/unassigned pitches
            # This ensures merge fields are not just empty strings
            return {
                'name': pitch_name,
                'address': 'Please contact the club for address details',
                'parking': 'Please contact the club for parking information',
                'toilets': 'Please contact the club for toilet facilities information',
                'special_instructions': 'Please contact the club for specific pitch information',
                'opening_notes': '',
                'warm_up_notes': '',
                'map_image_url': '',
                'google_maps_link': '',
                'custom_map_filename': ''
            }

    def get_team_kit_colours(self, team_name):
        """Return stored kit colours for the team in context"""
        if not self.team_obj or not team_name:
            return None

        if self.team_obj.name.strip().lower() != team_name.strip().lower():
            return None

        return {
            'home_shirt': self.team_obj.home_shirt or '',
            'home_shorts': self.team_obj.home_shorts or '',
            'home_socks': self.team_obj.home_socks or '',
            'away_shirt': self.team_obj.away_shirt or '',
            'away_shorts': self.team_obj.away_shorts or '',
            'away_socks': self.team_obj.away_socks or ''
        }

    def get_preferences(self):
        """Return default preferences"""
        return {
            'default_colours': 'Withdean Youth FC play in Blue and Black Shirts, Black Shorts and Blue and Black Hooped Socks',
            'default_referee_note': 'Referees have been requested for all fixtures but are as yet unconfirmed',
            'email_signature': 'Many thanks\n\nWithdean Youth FC',
            'default_day': 'Sunday'
        }

    def _get_default_template(self):
        return """<p><strong><u>In the event of any issues impacting your fixture please communicate directly with your opposition manager - This email will NOT be monitored</u></strong></p>

<p>Dear Fixtures Secretary</p>

<p>Please find details of your upcoming fixture at <strong>Withdean Youth FC</strong></p>

<p><strong>Please confirm receipt:</strong> Please copy the relevant Withdean Youth FC manager to your response.</p>

<p><strong>Any issues:</strong> Managers please contact your opposition directly using the contact details supplied if you have any issues that will impact your attendance (ideally by phone call or text message).</p>

<p><strong>Please Contact Managers Directly:</strong> Our Fixtures secretaries will not pick up on late messages so it is vital you communicate directly with your opposition manager once you have been put in touch.</p>

<h3>FIXTURE DETAILS</h3>

<p><strong>Date:</strong> {{date_display}}</p>

<p><strong>Kick-off Time:</strong> {{time_display}}</p>

<p><strong>Pitch Location:</strong> {{pitch_name}}</p>

<div style="margin: 20px 0; text-align: center;">
    <img src="{{pitch_map_image}}" alt="{{pitch_name}} Estate Map" style="max-width: 100%; height: auto; border: 1px solid #ccc; border-radius: 5px;">
    <br><small>Estate Map - How to find {{pitch_name}}</small>
</div>

<p><strong>Google Maps:</strong> <a href="{{pitch_google_maps_link}}">{{pitch_name}} Google Maps</a></p>

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
