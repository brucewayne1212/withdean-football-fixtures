"""
Email template generator for football fixtures
Based on Withdean Youth FC standard template
"""

def get_pitch_specific_info(pitch_name):
    """
    Return pitch-specific information based on pitch name
    """
    pitch_name_lower = str(pitch_name).lower().strip()
    
    if 'stanley deason' in pitch_name_lower or 'deason' in pitch_name_lower:
        return {
            'location': 'Stanley Deason 3G',
            'parking': 'Stanley Deason Leisure Centre (120 Wilson Avenue, BN2 5BP) - this is NOT at the Dorothy Stringer campus. Parking will be obvious when you arrive at the centre.',
            'toilets': 'Toilets can be found within the main leisure centre building',
            'special_info': '''Stanley Deason 3G: Please pay special attention to the details about footwear below.

Strict Boot Policy: Stanley Deason 3G pitch has strict boot rules and centre staff that will be doing a boot check before kick-off.

The following footwear is Not Allowed (including coaches and anyone entering the playing area)
• Any Dirty Boots
• Trainers
• Old Style Blades
• Astro Boots

The Following Footwear is Allowed
• All Screw in Studs (including metal studs)
• Modern Moulded Stud Football Boots'''
        }
    
    elif any(pitch in pitch_name_lower for pitch in ['dorothy stringer', 'stringer', 'balfour', 'varndean']):
        return {
            'location': 'Dorothy Stringer/Balfour/Varndean',
            'parking': 'Parking for all of these pitches is at Dorothy Stringer School, Loder Road, BN1 6PL. Follow the blue lines on the map below to reach your designated pitch.',
            'toilets': 'Toilet Access for all attendees to Stringer/Varndean/Balfour is in Dorothy Stringer opposite the 3G entrance.',
            'special_info': 'Map for Dorothy Stringer / Varndean / Balfour only (Stanley Deason 3G users please see info above and use the other postcode)\n\n[Note: Withdean Pitches.png map would be attached to email]'
        }
    
    else:
        return {
            'location': pitch_name,
            'parking': 'Please contact the club for parking information.',
            'toilets': 'Please contact the club for toilet facilities information.',
            'special_info': 'Please contact the club for specific pitch information.'
        }

def generate_email(fixture_data, user_manager=None):
    """
    Generate email content for a fixture using Withdean Youth FC template
    
    Args:
        fixture_data (dict): Dictionary containing fixture information
        user_manager: UserManager instance for custom pitch configs
    
    Returns:
        str: Formatted email content
    """
    
    # Use user's custom pitch configuration if available
    if user_manager:
        pitch_config = user_manager.get_pitch_config(fixture_data['pitch'])
        preferences = user_manager.get_preferences()
    else:
        pitch_info = get_pitch_specific_info(fixture_data['pitch'])
        preferences = {
            'default_referee_note': 'Referees have been requested for all fixtures but are as yet unconfirmed',
            'default_colours': 'Withdean Youth FC play in Red and Black Shirts, Black Shorts and Red and Black Hooped Socks',
            'email_signature': 'Many thanks\n\nWithdean Youth FC',
            'default_day': 'Sunday'
        }
    
    # Extract date from kickoff time if possible, otherwise use the full field
    kickoff_display = fixture_data['kickoff_time'] if fixture_data['kickoff_time'] else "TBC"
    
    if user_manager:
        # Build email using user's custom configurations
        pitch_section = f"""Date: {kickoff_display}

KO Time & Pitch Location: {fixture_data['pitch']} (see attached map for relevant pitch location)

Home Colours: {preferences.get('default_colours', 'Withdean Youth FC play in Red and Black Shirts, Black Shorts and Red and Black Hooped Socks')}

Referees: {preferences.get('default_referee_note', 'Referees have been requested for all fixtures but are as yet unconfirmed')}"""

        # Add parking information
        if pitch_config.get('parking'):
            pitch_section += f"\n\n{pitch_config['name']} Parking: {pitch_config['parking']}"

        # Add toilet information  
        if pitch_config.get('toilets'):
            pitch_section += f"\n\nToilets Access: {pitch_config['toilets']}"

        # Add special instructions
        if pitch_config.get('special_instructions'):
            pitch_section += f"\n\n{pitch_config['special_instructions']}"

        # Add setup notes if available
        if pitch_config.get('opening_notes'):
            pitch_section += f"\n\nSetup Notes: {pitch_config['opening_notes']}"

        default_day = preferences.get('default_day', 'Sunday')
        email_signature = preferences.get('email_signature', 'Many thanks\n\nWithdean Youth FC')
        
        template = f"""In the event of any issues impacting your fixture please communicate directly with your opposition manager - This email will NOT be monitored

Dear Fixtures Secretary

Please find details of your upcoming fixture at Withdean Youth FC  

Please confirm receipt: Please copy the relevant Withdean Youth FC manager to your response.

Any issues: Managers please contact your opposition directly using the contact details supplied if you have any issues that will impact your attendance (ideally by phone call or text message).

Please Contact Managers Directly: Our Fixtures secretaries will not pick up on late messages so it is vital you communicate directly with your opposition manager once you have been put in touch.

{pitch_section}

We look forward to hosting you on {default_day}

{email_signature}"""

    else:
        # Fallback to original template
        pitch_info = get_pitch_specific_info(fixture_data['pitch'])
        template = f"""In the event of any issues impacting your fixture please communicate directly with your opposition manager - This email will NOT be monitored

Dear Fixtures Secretary

Please find details of your upcoming fixture at Withdean Youth FC  

Please confirm receipt: Please copy the relevant Withdean Youth FC manager to your response.

Any issues: Managers please contact your opposition directly using the contact details supplied if you have any issues that will impact your attendance (ideally by phone call or text message).

Please Contact Managers Directly: Our Fixtures secretaries will not pick up on late messages so it is vital you communicate directly with your opposition manager once you have been put in touch.

Date: {kickoff_display}

KO Time & Pitch Location: {fixture_data['pitch']} (see attached map for relevant pitch location)

Home Colours: Withdean Youth FC play in Red and Black Shirts, Black Shorts and Red and Black Hooped Socks

Referees: Referees have been requested for all fixtures but are as yet unconfirmed

{pitch_info['location']} Parking: {pitch_info['parking']}

Toilets Access: {pitch_info['toilets']}

{pitch_info['special_info']}

We look forward to hosting you on Sunday

Many thanks

Withdean Youth FC"""
    
    return template.strip()

def generate_subject_line(fixture_data):
    """Generate email subject line"""
    return f"{fixture_data['team']} vs {fixture_data['opposition']} - Fixture Details"