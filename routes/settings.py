from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from sqlalchemy import func
from datetime import datetime
import os
import logging
import json

from database import db_manager
from utils import get_user_organization, get_user_organization_id
from models import Team, Pitch, TeamContact, TeamCoach, UserPreference, EmailTemplate, Fixture, Task, get_or_create_team
from weekly_sheet_refresher import refresh_weekly_fixtures
from dateutil import parser as date_parser

# Setup logger
logger = logging.getLogger(__name__)

settings_bp = Blueprint('settings', __name__)

def generate_google_maps_url(address, api_key, parking_address=None):
    """Generate Google Static Maps API URL from address with optional parking location"""
    import urllib.parse
    if not address or not api_key:
        return None

    base_url = "https://maps.googleapis.com/maps/api/staticmap?"

    # Build markers
    markers = [f'color:green|label:⚽|{address}']

    if parking_address and parking_address.strip() and parking_address.strip() != address.strip():
        markers.append(f'color:blue|label:🅿️|{parking_address}')

    # Determine center and zoom based on whether we have parking
    if len(markers) > 1:
        # When we have both pitch and parking, center on pitch but zoom out slightly
        center = address
        zoom = 15  # Slightly wider view to show both locations
    else:
        center = address
        zoom = 16  # Standard zoom for single location

    params = {
        'center': center,
        'zoom': zoom,
        'size': '600x400',
        'maptype': 'roadmap',
        'key': api_key
    }

    # Add all markers
    for i, marker in enumerate(markers):
        params[f'markers{i}' if i > 0 else 'markers'] = marker

    return base_url + urllib.parse.urlencode(params)

def generate_google_maps_link(address):
    """Generate Google Maps link from address"""
    import urllib.parse
    if not address:
        return None

    base_url = "https://www.google.com/maps/search/?"
    params = {'query': address}
    return base_url + urllib.parse.urlencode(params)

def get_default_email_template():
    """Get the default email template content"""
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

<p><strong>Google Maps Link:</strong> <a href="{{pitch_google_maps_link}}">{{pitch_google_maps_link}}</a></p>

{{pitch_map_section}}

{{further_instructions_section}}

<h3>CONTACT INFORMATION</h3>

<p><strong>Manager:</strong> {{manager_name}}</p>
<p><strong>Email:</strong> {{manager_email}}</p>
<p><strong>Phone:</strong> {{manager_phone}}</p>

<p>{{email_signature}}</p>"""

@settings_bp.route('/settings/teams', methods=['POST'])
@login_required
def save_team_selection():
    """Save team selection (which teams the user manages)"""
    session = db_manager.get_session()
    try:
        org = get_user_organization()
        if not org:
            flash('No organization found.', 'error')
            return redirect(url_for('auth.logout'))

        # Get selected teams from form
        selected_team_names = request.form.getlist('teams')

        # Update all teams to not be managed
        session.query(Team).filter_by(organization_id=org.id).update({'is_managed': False})

        # Set selected teams to be managed
        if selected_team_names:
            session.query(Team).filter(
                Team.organization_id == org.id,
                Team.name.in_(selected_team_names)
            ).update({'is_managed': True})

        session.commit()
        flash('Team selection saved successfully!', 'success')

    except Exception as e:
        session.rollback()
        flash(f'Error saving team selection: {str(e)}', 'error')
    finally:
        session.close()

    return redirect(url_for('settings.settings_view'))

@settings_bp.route('/settings/teams/<path:team_name>', methods=['DELETE'])
# @csrf.exempt - Removed decorator, handle via app config or blueprint if needed, but keeping standard protection where possible. 
# Actually CSRF protection is global in app.py. For AJAX calls, we need headers.
# Assuming AJAX calls include X-CSRFToken.
@login_required
def delete_team(team_name):
    """Permanently delete a team from the organization"""
    session = db_manager.get_session()
    try:
        org = get_user_organization()
        if not org:
            return jsonify({'error': 'No organization found'}), 400

        # Find the team
        team = session.query(Team).filter_by(
            organization_id=org.id,
            name=team_name
        ).first()

        if not team:
            return jsonify({'error': 'Team not found'}), 404

        # Get counts before deletion for reporting
        fixture_count = session.query(Fixture).filter_by(team_id=team.id).count()
        task_count = session.query(Task).filter_by(organization_id=org.id).join(Fixture).filter(Fixture.team_id == team.id).count()
        coach_count = session.query(TeamCoach).filter_by(organization_id=org.id, team_id=team.id).count()
        contact_count = session.query(TeamContact).filter_by(organization_id=org.id, team_name=team.name).count()

        # Delete all related data in order (respecting foreign key constraints)

        # 1. Delete tasks associated with this team's fixtures
        tasks_to_delete = session.query(Task).filter_by(organization_id=org.id).join(Fixture).filter(Fixture.team_id == team.id).all()
        for task in tasks_to_delete:
            session.delete(task)

        # 2. Delete fixtures for this team
        fixtures_to_delete = session.query(Fixture).filter_by(team_id=team.id).all()
        for fixture in fixtures_to_delete:
            # Also delete any opposition team if it was created just for this fixture and has no other references
            if fixture.opposition_team_id:
                opposition_count = session.query(Fixture).filter_by(opposition_team_id=fixture.opposition_team_id).count()
                if opposition_count <= 1:  # This is the only fixture for this opposition team
                    opposition_team = session.query(Team).filter_by(id=fixture.opposition_team_id).first()
                    if opposition_team:
                        session.delete(opposition_team)
            session.delete(fixture)

        # 3. Delete team coaches
        coaches_to_delete = session.query(TeamCoach).filter_by(organization_id=org.id, team_id=team.id).all()
        for coach in coaches_to_delete:
            session.delete(coach)

        # 4. Delete team contact
        contact_to_delete = session.query(TeamContact).filter_by(organization_id=org.id, team_name=team.name).first()
        if contact_to_delete:
            session.delete(contact_to_delete)

        # 5. Finally delete the team itself
        session.delete(team)

        session.commit()

        return jsonify({
            'success': True,
            'message': f'Team "{team_name}" deleted successfully. Removed {fixture_count} fixtures, {task_count} tasks, {coach_count} coaches, and {contact_count} contacts.'
        })

    except Exception as e:
        session.rollback()
        return jsonify({'success': False, 'message': f'Error deleting team: {str(e)}'}), 500
    finally:
        session.close()

@settings_bp.route('/settings/teams/bulk-delete', methods=['DELETE'])
@login_required
def bulk_delete_teams():
    """Permanently delete multiple teams from the organization"""
    session = db_manager.get_session()
    try:
        org = get_user_organization()
        if not org:
            return jsonify({'error': 'No organization found'}), 400

        # Get the list of teams to delete
        data = request.get_json()
        team_names = data.get('teams', []) if data else []

        if not team_names:
            return jsonify({'error': 'No teams specified for deletion'}), 400

        total_fixture_count = 0
        total_task_count = 0
        total_coach_count = 0
        total_contact_count = 0
        teams_deleted = 0

        # Process each team
        for team_name in team_names:
            # Find the team
            team = session.query(Team).filter_by(
                organization_id=org.id,
                name=team_name
            ).first()

            if not team:
                continue  # Skip if team not found

            # Get counts before deletion
            fixture_count = session.query(Fixture).filter_by(team_id=team.id).count()
            task_count = session.query(Task).filter_by(organization_id=org.id).join(Fixture).filter(Fixture.team_id == team.id).count()
            coach_count = session.query(TeamCoach).filter_by(organization_id=org.id, team_id=team.id).count()
            contact_count = session.query(TeamContact).filter_by(organization_id=org.id, team_name=team.name).count()

            # Delete all related data in order (respecting foreign key constraints)
            # ... (Same logic as single delete) ...
             # 1. Delete tasks associated with this team's fixtures
            tasks_to_delete = session.query(Task).filter_by(organization_id=org.id).join(Fixture).filter(Fixture.team_id == team.id).all()
            for task in tasks_to_delete:
                session.delete(task)

            # 2. Delete fixtures for this team
            fixtures_to_delete = session.query(Fixture).filter_by(team_id=team.id).all()
            for fixture in fixtures_to_delete:
                # Also delete any opposition team if it was created just for this fixture and has no other references
                if fixture.opposition_team_id:
                    opposition_count = session.query(Fixture).filter_by(opposition_team_id=fixture.opposition_team_id).count()
                    if opposition_count <= 1:  # This is the only fixture for this opposition team
                        opposition_team = session.query(Team).filter_by(id=fixture.opposition_team_id).first()
                        if opposition_team:
                            session.delete(opposition_team)
                session.delete(fixture)

            # 3. Delete team coaches
            coaches_to_delete = session.query(TeamCoach).filter_by(organization_id=org.id, team_id=team.id).all()
            for coach in coaches_to_delete:
                session.delete(coach)

            # 4. Delete team contact
            contact_to_delete = session.query(TeamContact).filter_by(organization_id=org.id, team_name=team.name).first()
            if contact_to_delete:
                session.delete(contact_to_delete)

            # 5. Finally delete the team itself
            session.delete(team)

            # Accumulate counts
            total_fixture_count += fixture_count
            total_task_count += task_count
            total_coach_count += coach_count
            total_contact_count += contact_count
            teams_deleted += 1

        session.commit()

        return jsonify({
            'success': True,
            'deleted_count': teams_deleted,
            'message': f'Successfully deleted {teams_deleted} teams. Total removed: {total_fixture_count} fixtures, {total_task_count} tasks, {total_coach_count} coaches, and {total_contact_count} contacts.'
        })

    except Exception as e:
        session.rollback()
        return jsonify({'success': False, 'message': f'Error bulk deleting teams: {str(e)}'}), 500
    finally:
        session.close()

@settings_bp.route('/settings')
@login_required
def settings_view():
    """Settings page"""
    session = db_manager.get_session()
    try:
        org = get_user_organization()
        if not org:
            flash('No organization found.', 'error')
            return redirect(url_for('auth.logout'))
        
        # Get managed teams
        managed_teams = session.query(Team).filter_by(
            organization_id=org.id,
            is_managed=True
        ).all()
        
        # Get pitches
        pitches = session.query(Pitch).filter_by(
            organization_id=org.id
        ).all()
        
        # Get team contacts
        team_contacts = session.query(TeamContact).filter_by(
            organization_id=org.id
        ).all()
        
        # Get user preferences
        user_prefs = session.query(UserPreference).filter_by(
            organization_id=org.id,
            user_id=current_user.id
        ).first()
        
        preferences = user_prefs.preferences if user_prefs else {}
        
        # Get email template
        email_template = session.query(EmailTemplate).filter_by(
            organization_id=org.id,
            template_type='default',
            is_active=True
        ).first()
        
        # Get team coaches for all teams
        team_coaches_query = session.query(TeamCoach).filter_by(
            organization_id=org.id
        ).all()
        
        # Create a simple mock user_manager object for template compatibility
        class UserManagerMock:
            def __init__(self, coaches_data, teams_data):
                self.coaches_data = coaches_data
                self.teams_lookup = {team.id: team.name for team in teams_data}
                self.teams_data = teams_data  # Add teams data for kit colours

            def get_team_coaches(self, team_name):
                # Find coaches for the given team name
                result = []
                for coach in self.coaches_data:
                    coach_team_name = self.teams_lookup.get(coach.team_id, '')
                    if coach_team_name == team_name:
                        result.append(coach)
                return result

            def get_team_kit_colours(self, team_name):
                """Get kit colours for a specific team"""
                # Find team by name
                team = None
                for t in self.teams_data:
                    if t.name == team_name:
                        team = t
                        break

                if not team:
                    return None

                # Return kit colours as dict
                return {
                    'home_shirt': team.home_shirt or '',
                    'home_shorts': team.home_shorts or '',
                    'home_socks': team.home_socks or '',
                    'away_shirt': team.away_shirt or '',
                    'away_shorts': team.away_shorts or '',
                    'away_socks': team.away_socks or ''
                }
        
        user_manager = UserManagerMock(team_coaches_query, managed_teams)
        
        # Pass team objects with their data instead of just names
        teams_data = [{'name': team.name, 'id': str(team.id), 'fa_fixtures_url': team.fa_fixtures_url or ''} for team in managed_teams]
        
        return render_template('settings.html',
            user_info={'name': current_user.name, 'email': current_user.email},
            user_name=current_user.name,
            user_email=current_user.email,
            user_manager=user_manager,
            managed_teams=[team.name for team in managed_teams],
            teams_data=teams_data,
            pitches={pitch.name: {
                'name': pitch.name,
                'address': pitch.address or '',
                'parking': pitch.parking_info or '',
                'toilets': pitch.toilet_info or '',
                'special_instructions': pitch.special_instructions or '',
                'opening_notes': pitch.opening_notes or '',
                'warm_up_notes': pitch.warm_up_notes or '',
                'map_image_url': pitch.map_image_url or '',
                'google_maps_link': pitch.google_maps_link or ''
            } for pitch in pitches},
            team_contacts={contact.team_name: {
                'contact_name': contact.contact_name or '',
                'email': contact.email or '',
                'phone': contact.phone or '',
                'notes': contact.notes or ''
            } for contact in team_contacts},
            team_coaches={
                user_manager.teams_lookup.get(coach.team_id, 'Unknown Team'): coach
                for coach in team_coaches_query
            },
            preferences=preferences,
            email_template=email_template.content if email_template else '',
            org_settings=org.settings or {}
        )

    finally:
        session.close()

@settings_bp.route('/settings/pitch', methods=['POST'])
@login_required
def add_or_update_pitch():
    """Add or update pitch configuration"""
    session = db_manager.get_session()
    try:
        org = get_user_organization()
        if not org:
            flash('No organization found.', 'error')
            return redirect(url_for('auth.logout'))

        pitch_name = request.form.get('name')  # Form field is named 'name'
        if not pitch_name:
            flash('Pitch name is required.', 'error')
            return redirect(url_for('settings.settings_view'))

        # Get form data
        address = request.form.get('address', '')
        parking_address = request.form.get('parking_address', '')
        map_image_url = request.form.get('map_image_url', '')
        google_maps_link = request.form.get('google_maps_link', '')

        # Handle custom map upload
        custom_map_filename = None
        if 'custom_map_upload' in request.files:
            file = request.files['custom_map_upload']
            if file and file.filename and file.filename != '':
                # Validate file type
                allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
                if '.' in file.filename:
                    extension = file.filename.rsplit('.', 1)[1].lower()
                    if extension in allowed_extensions:
                        # Create unique filename
                        import uuid
                        unique_filename = f"{pitch_name.replace(' ', '_').lower()}_{uuid.uuid4().hex[:8]}.{extension}"

                        # Ensure upload directory exists
                        # Fix: Use current_app.config['UPLOAD_FOLDER'] or relative path
                        # For maps, we want them in static/uploads/maps
                        upload_dir = os.path.join(os.getcwd(), 'static', 'uploads', 'maps')
                        os.makedirs(upload_dir, exist_ok=True)

                        # Save file
                        file_path = os.path.join(upload_dir, unique_filename)
                        file.save(file_path)
                        custom_map_filename = unique_filename
                    else:
                        flash('Invalid file type. Please upload PNG, JPG, JPEG, GIF, or WebP images only.', 'error')
                        return redirect(url_for('settings.settings_view'))

        # Auto-generate map URLs if address is provided and URLs are empty
        api_key = os.environ.get('GOOGLE_MAPS_API_KEY')

        if address and not map_image_url:
            if api_key and api_key != 'your_google_maps_api_key_here':
                map_image_url = generate_google_maps_url(address, api_key, parking_address)

        if address and not google_maps_link:
            google_maps_link = generate_google_maps_link(address)

        # Generate parking-specific maps if parking address is different
        parking_map_image_url = ''
        parking_google_maps_link = ''

        if (parking_address and parking_address.strip() and
            parking_address.strip().lower() != address.strip().lower()):

            if api_key and api_key != 'your_google_maps_api_key_here':
                parking_map_image_url = generate_google_maps_url(parking_address, api_key)
            parking_google_maps_link = generate_google_maps_link(parking_address)

        # Check if pitch exists
        existing_pitch = session.query(Pitch).filter_by(
            organization_id=org.id,
            name=pitch_name
        ).first()

        if existing_pitch:
            # Update existing pitch
            existing_pitch.address = address
            existing_pitch.parking_address = parking_address
            existing_pitch.parking_info = request.form.get('parking', '')
            existing_pitch.toilet_info = request.form.get('toilets', '')
            existing_pitch.special_instructions = request.form.get('special_instructions', '')
            existing_pitch.opening_notes = request.form.get('opening_notes', '')
            existing_pitch.warm_up_notes = request.form.get('warm_up_notes', '')
            existing_pitch.map_image_url = map_image_url
            existing_pitch.google_maps_link = google_maps_link
            if custom_map_filename:
                existing_pitch.custom_map_filename = custom_map_filename
            existing_pitch.parking_map_image_url = parking_map_image_url
            existing_pitch.parking_google_maps_link = parking_google_maps_link
            existing_pitch.updated_at = datetime.utcnow()
        else:
            # Create new pitch
            new_pitch = Pitch(
                organization_id=org.id,
                name=pitch_name,
                address=address,
                parking_address=parking_address,
                parking_info=request.form.get('parking', ''),
                toilet_info=request.form.get('toilets', ''),
                special_instructions=request.form.get('special_instructions', ''),
                opening_notes=request.form.get('opening_notes', ''),
                warm_up_notes=request.form.get('warm_up_notes', ''),
                map_image_url=map_image_url,
                google_maps_link=google_maps_link,
                custom_map_filename=custom_map_filename,
                parking_map_image_url=parking_map_image_url,
                parking_google_maps_link=parking_google_maps_link,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            session.add(new_pitch)

        # Handle Aliases
        aliases_str = request.form.get('aliases', '').strip()
        
        # Determine which pitch object we are working with
        target_pitch = existing_pitch if existing_pitch else new_pitch
        
        # If it's a new pitch, we need to add it to session and flush to get an ID
        if not existing_pitch:
            session.add(new_pitch)
            session.flush()
            
        # Clear existing aliases
        from models import PitchAlias
        session.query(PitchAlias).filter_by(
            organization_id=org.id,
            pitch_id=target_pitch.id
        ).delete()
        
        # Add new aliases
        if aliases_str:
            alias_list = [a.strip() for a in aliases_str.split(',') if a.strip()]
            for alias_name in alias_list:
                # Check for duplicates to avoid unique constraint errors
                existing_alias = session.query(PitchAlias).filter_by(
                    organization_id=org.id,
                    alias=alias_name
                ).first()
                
                if existing_alias:
                    # If alias exists for another pitch, we might want to warn or overwrite
                    # For now, we'll skip to avoid errors, or maybe reassign?
                    # Let's reassign if it belongs to a different pitch
                    if existing_alias.pitch_id != target_pitch.id:
                        existing_alias.pitch_id = target_pitch.id
                else:
                    new_alias = PitchAlias(
                        organization_id=org.id,
                        pitch_id=target_pitch.id,
                        alias=alias_name
                    )
                    session.add(new_alias)

        session.commit()
        flash(f'Pitch configuration for "{pitch_name}" saved successfully!', 'success')

    except Exception as e:
        session.rollback()
        flash(f'Error saving pitch: {str(e)}', 'error')
    finally:
        session.close()

    return redirect(url_for('settings.settings_view'))

@settings_bp.route('/settings/pitch/<pitch_name>')
@login_required
def get_pitch_config(pitch_name):
    """Get pitch configuration as JSON"""
    session = db_manager.get_session()
    try:
        org = get_user_organization()
        if not org:
            return jsonify({'error': 'No organization found'}), 404

        pitch = session.query(Pitch).filter_by(
            organization_id=org.id,
            name=pitch_name
        ).first()

        if not pitch:
            return jsonify({'error': 'Pitch not found'}), 404

        # Get aliases
        from models import PitchAlias
        aliases = session.query(PitchAlias).filter_by(
            organization_id=org.id,
            pitch_id=pitch.id
        ).all()
        alias_list = [a.alias for a in aliases]

        return jsonify({
            'name': pitch.name,
            'aliases': alias_list,
            'address': pitch.address or '',
            'parking_address': pitch.parking_address or '',
            'parking': pitch.parking_info or '',
            'toilets': pitch.toilet_info or '',
            'special_instructions': pitch.special_instructions or '',
            'opening_notes': pitch.opening_notes or '',
            'warm_up_notes': pitch.warm_up_notes or '',
            'map_image_url': pitch.map_image_url or '',
            'google_maps_link': pitch.google_maps_link or '',
            'custom_map_filename': pitch.custom_map_filename or '',
            'parking_map_image_url': pitch.parking_map_image_url or '',
            'parking_google_maps_link': pitch.parking_google_maps_link or ''
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

@settings_bp.route('/settings/pitch/<pitch_name>', methods=['DELETE'])
@login_required
def delete_pitch(pitch_name):
    """Delete pitch configuration"""
    session = db_manager.get_session()
    try:
        org = get_user_organization()
        if not org:
            return jsonify({'error': 'No organization found'}), 400

        pitch = session.query(Pitch).filter_by(
            organization_id=org.id,
            name=pitch_name
        ).first()

        if not pitch:
            return jsonify({'error': 'Pitch not found'}), 404

        session.delete(pitch)
        session.commit()

        return jsonify({'success': True, 'message': f'Pitch "{pitch_name}" deleted successfully'})

    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

@settings_bp.route('/settings/coaches', methods=['POST'])
@login_required
def add_or_update_coach():
    """Add or update team coach"""
    session = db_manager.get_session()
    try:
        org = get_user_organization()
        if not org:
            flash('No organization found.', 'error')
            return redirect(url_for('auth.logout'))

        wants_json = 'application/json' in (request.headers.get('Accept', '') or '').lower() or \
            request.headers.get('X-Requested-With') == 'XMLHttpRequest'

        team_name = request.form.get('team_name')
        coach_name = request.form.get('coach_name')
        coach_id = request.form.get('coach_id')

        if not team_name or not coach_name:
            message = 'Team name and coach name are required.'
            if wants_json:
                return jsonify({'success': False, 'message': message}), 400
            flash(message, 'error')
            return redirect(url_for('settings.settings_view'))

        # Get or create team
        team = get_or_create_team(session, org.id, team_name)

        # Check if this is an update (coach_id provided) or new coach
        if coach_id:
            # Update existing coach by ID
            existing_coach = session.query(TeamCoach).filter_by(
                id=coach_id,
                organization_id=org.id
            ).first()

            if existing_coach:
                existing_coach.team_id = team.id
                existing_coach.coach_name = coach_name
                existing_coach.email = request.form.get('email', '')
                existing_coach.phone = request.form.get('phone', '')
                existing_coach.role = request.form.get('role', 'Coach')
                existing_coach.notes = request.form.get('notes', '')
                existing_coach.updated_at = datetime.utcnow()
                success_message = f'Coach "{coach_name}" updated successfully!'
                saved_coach = existing_coach
            else:
                message = 'Coach not found for update.'
                if wants_json:
                    return jsonify({'success': False, 'message': message}), 404
                flash(message, 'error')
                return redirect(url_for('settings.settings_view'))
        else:
            # Create new coach
            new_coach = TeamCoach(
                organization_id=org.id,
                team_id=team.id,
                coach_name=coach_name,
                email=request.form.get('email', ''),
                phone=request.form.get('phone', ''),
                role=request.form.get('role', 'Coach'),
                notes=request.form.get('notes', ''),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            session.add(new_coach)
            success_message = f'Coach "{coach_name}" added successfully!'
            saved_coach = new_coach

        session.commit()

        coach_payload = {
            'id': str(saved_coach.id),
            'team_name': team.name,
            'coach_name': saved_coach.coach_name,
            'email': saved_coach.email or '',
            'phone': saved_coach.phone or '',
            'role': saved_coach.role or 'Coach',
            'notes': saved_coach.notes or ''
        }

        if wants_json:
            return jsonify({'success': True, 'coach': coach_payload})

        flash(success_message, 'success')
        return redirect(url_for('settings.settings_view'))

    except ValueError as ve:
        session.rollback()
        message = str(ve)
        if wants_json:
            return jsonify({'success': False, 'message': message}), 400
        flash(f'Error saving coach: {message}', 'error')
        return redirect(url_for('settings.settings_view'))
    except Exception as e:
        session.rollback()
        message = str(e)
        if wants_json:
            return jsonify({'success': False, 'message': message}), 500
        flash(f'Error saving coach: {message}', 'error')
        return redirect(url_for('settings.settings_view'))
    finally:
        session.close()

@settings_bp.route('/settings/coaches/<team_name>')
@login_required
def get_coach_config(team_name):
    """Get coach configuration as JSON - returns first coach for backwards compatibility"""
    session = db_manager.get_session()
    try:
        org = get_user_organization()
        if not org:
            return jsonify({'error': 'No organization found'}), 404

        # Get team
        team = session.query(Team).filter_by(
            organization_id=org.id,
            name=team_name
        ).first()

        if not team:
            return jsonify({})

        # Get first coach for this team (for backwards compatibility)
        coach = session.query(TeamCoach).filter_by(
            organization_id=org.id,
            team_id=team.id
        ).first()

        if not coach:
            return jsonify({})

        return jsonify({
            'id': coach.id,
            'coach_name': coach.coach_name,
            'email': coach.email or '',
            'phone': coach.phone or '',
            'role': coach.role or 'Coach',
            'notes': coach.notes or ''
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

@settings_bp.route('/settings/coaches/id/<int:coach_id>')
@login_required
def get_coach_by_id(coach_id):
    """Get specific coach configuration by ID"""
    session = db_manager.get_session()
    try:
        org = get_user_organization()
        if not org:
            return jsonify({'error': 'No organization found'}), 404

        # Get coach by ID
        coach = session.query(TeamCoach).filter_by(
            id=coach_id,
            organization_id=org.id
        ).first()

        if not coach:
            return jsonify({'error': 'Coach not found'}), 404

        # Get team name
        team = session.query(Team).filter_by(id=coach.team_id).first()
        team_name = team.name if team else 'Unknown Team'

        return jsonify({
            'id': coach.id,
            'team_name': team_name,
            'coach_name': coach.coach_name,
            'email': coach.email or '',
            'phone': coach.phone or '',
            'role': coach.role or 'Coach',
            'notes': coach.notes or ''
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

@settings_bp.route('/settings/coaches/team/<team_name>')
@login_required
def get_team_coaches(team_name):
    """Get all coaches for a team"""
    session = db_manager.get_session()
    try:
        org = get_user_organization()
        if not org:
            return jsonify({'error': 'No organization found'}), 404

        # Get team
        team = session.query(Team).filter_by(
            organization_id=org.id,
            name=team_name
        ).first()

        if not team:
            return jsonify([])

        # Get all coaches for this team
        coaches = session.query(TeamCoach).filter_by(
            organization_id=org.id,
            team_id=team.id
        ).all()

        return jsonify([{
            'id': str(coach.id),
            'coach_name': coach.coach_name,
            'email': coach.email or '',
            'phone': coach.phone or '',
            'role': coach.role or 'Coach',
            'notes': coach.notes or ''
        } for coach in coaches])

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

@settings_bp.route('/settings/coaches/<team_name>', methods=['DELETE'])
@login_required
def delete_coach(team_name):
    """Delete team coach"""
    session = db_manager.get_session()
    try:
        org = get_user_organization()
        if not org:
            return jsonify({'error': 'No organization found'}), 400

        # Get team
        team = session.query(Team).filter_by(
            organization_id=org.id,
            name=team_name
        ).first()

        if not team:
            return jsonify({'error': 'Team not found'}), 404

        # Delete coach
        coach = session.query(TeamCoach).filter_by(
            organization_id=org.id,
            team_id=team.id
        ).first()

        if not coach:
            return jsonify({'error': 'Coach not found'}), 404

        session.delete(coach)
        session.commit()

        return jsonify({'status': 'success', 'message': f'Coach for "{team_name}" deleted successfully'})

    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

@settings_bp.route('/settings/coaches/delete', methods=['POST'])
@login_required
def delete_coach_by_id():
    """Delete coach by ID"""
    session = db_manager.get_session()
    try:
        org = get_user_organization()
        if not org:
            return jsonify({'error': 'No organization found'}), 404

        data = request.get_json(silent=True) or {}
        coach_id = data.get('coach_id') or request.form.get('coach_id')
        team_name = data.get('team_name') or request.form.get('team_name')
        coach_name = data.get('coach_name') or request.form.get('coach_name')

        coach = None

        if coach_id:
            coach = session.query(TeamCoach).filter_by(
                id=coach_id,
                organization_id=org.id
            ).first()
        elif team_name and coach_name:
            team = session.query(Team).filter_by(
                organization_id=org.id,
                name=team_name
            ).first()

            if not team:
                return jsonify({'error': f'Team "{team_name}" not found'}), 404

            coach = session.query(TeamCoach).filter_by(
                organization_id=org.id,
                team_id=team.id,
                coach_name=coach_name
            ).first()
        else:
            return jsonify({'error': 'Coach identifier is required'}), 400

        if not coach:
            return jsonify({'error': 'Coach not found'}), 404

        session.delete(coach)
        session.commit()

        return jsonify({'success': True, 'message': 'Coach deleted successfully'})

    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

@settings_bp.route('/settings/weekly-sheet', methods=['POST'])
@login_required
def save_weekly_sheet_url():
    """Save the weekly fixture sheet URL"""
    session = db_manager.get_session()
    try:
        # Get organization ID first
        org_id = get_user_organization_id()
        if not org_id:
            return jsonify({'error': 'No organization found'}), 404

        # Query the organization within this session to ensure we have fresh data
        org = session.query(Organization).filter_by(id=org_id).first()
        if not org:
            return jsonify({'error': 'No organization found'}), 404

        weekly_sheet_url = request.form.get('weekly_sheet_url', '').strip()
        print(f"DEBUG: Received weekly_sheet_url: '{weekly_sheet_url}'")

        if not weekly_sheet_url:
            print("DEBUG: URL is empty")
            return jsonify({'error': 'URL is required'}), 400

        # Update organization settings - handle JSONB properly
        # Get current settings as a dict
        current_settings = {}
        if org.settings:
            print(f"DEBUG: Current settings type: {type(org.settings)}")
            print(f"DEBUG: Current settings value: {org.settings}")
            if isinstance(org.settings, dict):
                current_settings = dict(org.settings)
            else:
                # Handle JSONB type - convert to dict
                try:
                    current_settings = dict(org.settings)
                except (TypeError, ValueError):
                    # If it's a string or other type, try to parse it
                    try:
                        import json
                        if isinstance(org.settings, str):
                            current_settings = json.loads(org.settings)
                        else:
                            current_settings = {}
                    except:
                        current_settings = {}
        
        print(f"DEBUG: Settings before update: {current_settings}")
        # Update the settings
        current_settings['weekly_sheet_url'] = weekly_sheet_url
        
        # Set the updated settings back to the org
        org.settings = current_settings
        print(f"DEBUG: Settings assigned to org: {org.settings}")

        # Force flag modified just in case
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(org, 'settings')

        session.commit()
        print("DEBUG: Session committed")
        
        # Verify persistence
        session.refresh(org)
        print(f"DEBUG: Settings after refresh: {org.settings}")

        flash('Google Sheet URL saved successfully.', 'success')
        return redirect(url_for('settings.settings_view'))

    except Exception as e:
        session.rollback()
        logger.error(f"DEBUG: Error saving URL: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

@settings_bp.route('/settings/contacts', methods=['POST'])
@login_required
def add_or_update_contact():
    """Add or update team contact"""
    session = db_manager.get_session()
    try:
        org = get_user_organization()
        if not org:
            flash('No organization found.', 'error')
            return redirect(url_for('settings.settings_view'))

        team_name = request.form.get('team_name')
        contact_name = request.form.get('contact_name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        notes = request.form.get('notes')

        if not team_name:
            flash('Team name is required.', 'error')
            return redirect(url_for('settings.settings_view'))

        # Get team
        team = session.query(Team).filter_by(
            organization_id=org.id,
            name=team_name
        ).first()

        if not team:
            flash(f'Team "{team_name}" not found.', 'error')
            return redirect(url_for('settings.settings_view'))

        # Check if contact already exists
        existing_contact = session.query(TeamContact).filter_by(
            organization_id=org.id,
            team_name=team_name
        ).first()

        if existing_contact:
            # Update existing contact
            existing_contact.contact_name = contact_name
            existing_contact.email = email
            existing_contact.phone = phone
            existing_contact.notes = notes
            flash(f'Contact for "{team_name}" updated successfully!', 'success')
        else:
            # Create new contact
            new_contact = TeamContact(
                organization_id=org.id,
                team_name=team_name,
                contact_name=contact_name,
                email=email,
                phone=phone,
                notes=notes
            )
            session.add(new_contact)
            flash(f'Contact for "{team_name}" added successfully!', 'success')

        session.commit()

    except Exception as e:
        session.rollback()
        flash(f'Error saving contact: {str(e)}', 'error')
    finally:
        session.close()

    return redirect(url_for('settings.settings_view'))

@settings_bp.route('/settings/contacts/<team_name>')
@login_required
def get_contact_config(team_name):
    """Get contact configuration as JSON"""
    session = db_manager.get_session()
    try:
        org = get_user_organization()
        if not org:
            return jsonify({'error': 'No organization found'}), 404

        # Get contact for this team
        contact = session.query(TeamContact).filter_by(
            organization_id=org.id,
            team_name=team_name
        ).first()

        if not contact:
            return jsonify({})

        return jsonify({
            'team_name': contact.team_name,
            'contact_name': contact.contact_name,
            'email': contact.email or '',
            'phone': contact.phone or '',
            'notes': contact.notes or ''
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

@settings_bp.route('/settings/contacts/<team_name>', methods=['DELETE'])
@login_required
def delete_contact(team_name):
    """Delete team contact"""
    session = db_manager.get_session()
    try:
        org = get_user_organization()
        if not org:
            return jsonify({'error': 'No organization found'}), 404

        # Find and delete contact
        contact = session.query(TeamContact).filter_by(
            organization_id=org.id,
            team_name=team_name
        ).first()

        if not contact:
            return jsonify({'error': 'Contact not found'}), 404

        session.delete(contact)
        session.commit()

        return jsonify({'status': 'success', 'message': f'Contact for "{team_name}" deleted successfully'})

    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

@settings_bp.route('/settings/team-kit/<path:team_name>')
@login_required
def get_team_kit(team_name):
    """Get team kit configuration as JSON"""
    session = db_manager.get_session()
    try:
        org = get_user_organization()
        if not org:
            return jsonify({'error': 'No organization found'}), 404

        # Get or create team
        team = get_or_create_team(session, org.id, team_name, is_managed=True)

        # Get kit data
        kit = {
            'home_shirt': team.home_shirt or '',
            'home_shorts': team.home_shorts or '',
            'home_socks': team.home_socks or '',
            'away_shirt': team.away_shirt or '',
            'away_shorts': team.away_shorts or '',
            'away_socks': team.away_socks or ''
        }

        return jsonify(kit)

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

@settings_bp.route('/settings/team-kit', methods=['POST'])
@login_required
def save_team_kit():
    """Save team kit configuration"""
    session = db_manager.get_session()
    try:
        org = get_user_organization()
        if not org:
            flash('No organization found.', 'error')
            return redirect(url_for('auth.logout'))

        team_name = request.form.get('team_name')
        if not team_name:
            flash('Team name is required.', 'error')
            return redirect(url_for('settings.settings_view'))

        # Get or create team
        team = get_or_create_team(session, org.id, team_name, is_managed=True)

        # Update kit fields
        team.home_shirt = request.form.get('home_shirt', '').strip() or None
        team.home_shorts = request.form.get('home_shorts', '').strip() or None
        team.home_socks = request.form.get('home_socks', '').strip() or None
        team.away_shirt = request.form.get('away_shirt', '').strip() or None
        team.away_shorts = request.form.get('away_shorts', '').strip() or None
        team.away_socks = request.form.get('away_socks', '').strip() or None

        team.updated_at = datetime.utcnow()

        session.commit()
        flash(f'Kit colours for "{team_name}" saved successfully!', 'success')

    except Exception as e:
        session.rollback()
        flash(f'Error saving kit colours: {str(e)}', 'error')
    finally:
        session.close()

    return redirect(url_for('settings.settings_view'))

@settings_bp.route('/settings/club-fixtures/url', methods=['POST'])
@login_required
def save_club_fixtures_url():
    """Save club-wide fixtures URL in organization settings"""
    session = db_manager.get_session()
    try:
        org = get_user_organization()
        if not org:
            if request.is_json or request.content_type == 'application/json':
                return jsonify({'error': 'No organization found'}), 400
            flash('No organization found.', 'error')
            return redirect(url_for('auth.logout'))

        club_fixtures_url = request.form.get('club_fixtures_url', '').strip() or None

        # Update organization settings - handle JSONB properly
        # Get current settings as a dict
        current_settings = {}
        if org.settings:
            if isinstance(org.settings, dict):
                current_settings = dict(org.settings)
            else:
                # Handle JSONB type - convert to dict
                try:
                    current_settings = dict(org.settings)
                except (TypeError, ValueError):
                    # If it's a string or other type, try to parse it
                    try:
                        import json
                        if isinstance(org.settings, str):
                            current_settings = json.loads(org.settings)
                        else:
                            current_settings = {}
                    except:
                        current_settings = {}
        
        # Update the settings
        if club_fixtures_url:
            current_settings['club_fixtures_url'] = club_fixtures_url
        else:
            current_settings.pop('club_fixtures_url', None)
        
        # Set the updated settings back to the org
        org.settings = current_settings
        
        session.commit()
        
        # Explicitly refresh to ensure the change is persisted
        session.refresh(org)
        
        # Verify the save worked
        session.expire_all()  # Force reload from database
        org_check = session.query(Organization).filter_by(id=org.id).first()
        saved_url = org_check.settings.get('club_fixtures_url') if org_check.settings else None
        
        logger.info(f"Saved club URL: {saved_url}, Request URL: {club_fixtures_url}")

        if request.is_json or request.content_type == 'application/json':
            return jsonify({
                'success': True,
                'message': 'Club fixtures URL saved successfully',
                'url': club_fixtures_url
            })
        
        if club_fixtures_url:
            flash('Club fixtures URL saved successfully.', 'success')
        else:
            flash('Club fixtures URL removed.', 'success')

        return redirect(url_for('settings.settings_view'))

    except Exception as e:
        session.rollback()
        logger.error(f"Error saving club fixtures URL: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        if request.is_json or request.content_type == 'application/json':
            return jsonify({'error': f'Error saving URL: {str(e)}'}), 500
        flash(f'Error saving club fixtures URL: {str(e)}', 'error')
        return redirect(url_for('settings.settings_view'))
    finally:
        session.close()

@settings_bp.route('/settings/teams/fa-url', methods=['POST'])
@login_required
def save_team_fa_url():
    """Save FA fixtures URL for a team"""
    session = db_manager.get_session()
    try:
        org = get_user_organization()
        if not org:
            flash('No organization found.', 'error')
            return redirect(url_for('auth.logout'))

        team_id = request.form.get('team_id')
        fa_fixtures_url = request.form.get('fa_fixtures_url', '').strip() or None

        if not team_id:
            flash('Team ID is required.', 'error')
            return redirect(url_for('settings.settings_view'))

        # Find the team
        try:
            from uuid import UUID
            team_uuid = UUID(team_id)
        except ValueError:
            flash('Invalid team ID.', 'error')
            return redirect(url_for('settings.settings_view'))

        team = session.query(Team).filter_by(
            organization_id=org.id,
            id=team_uuid
        ).first()

        if not team:
            flash('Team not found.', 'error')
            return redirect(url_for('settings.settings_view'))

        # Update FA fixtures URL
        team.fa_fixtures_url = fa_fixtures_url
        session.commit()

        if fa_fixtures_url:
            flash(f'FA fixtures URL saved for {team.name}.', 'success')
        else:
            flash(f'FA fixtures URL removed for {team.name}.', 'success')

        return redirect(url_for('settings.settings_view'))

    except Exception as e:
        session.rollback()
        flash(f'Error saving FA fixtures URL: {str(e)}', 'error')
        return redirect(url_for('settings.settings_view'))
    finally:
        session.close()

@settings_bp.route('/manage_email_template', methods=['GET', 'POST'])
@login_required
def manage_email_template():
    """Manage email template with contact information"""
    try:
        org_id = get_user_organization_id()
        session = db_manager.get_session()

        if request.method == 'POST':
            action = request.form.get('action')

            if action == 'save':
                template_content = request.form.get('template_content', '')

                # Save or update email template
                email_template = session.query(EmailTemplate).filter_by(
                    organization_id=org_id
                ).first()

                if email_template:
                    email_template.content = template_content
                    email_template.updated_at = func.now()
                else:
                    email_template = EmailTemplate(
                        organization_id=org_id,
                        content=template_content
                    )
                    session.add(email_template)

                session.commit()
                flash('Email template saved successfully', 'success')

            elif action == 'reset':
                # Reset to default template
                email_template = session.query(EmailTemplate).filter_by(
                    organization_id=org_id
                ).first()

                if email_template:
                    session.delete(email_template)
                    session.commit()

                flash('Email template reset to default', 'success')

            return redirect(url_for('settings.manage_email_template'))

        # GET request - show template editor
        email_template = session.query(EmailTemplate).filter_by(
            organization_id=org_id
        ).first()

        # Get contact information
        team_coaches = session.query(TeamCoach).filter_by(
            organization_id=org_id
        ).order_by(TeamCoach.coach_name).all()

        team_contacts = session.query(TeamContact).filter_by(
            organization_id=org_id
        ).order_by(TeamContact.team_name).all()

        # Get template content or use default
        template_content = email_template.content if email_template else get_default_email_template()

        return render_template('email_template_editor.html',
                             template_content=template_content,
                             team_coaches=team_coaches,
                             team_contacts=team_contacts,
                             user_name=current_user.name)

    except Exception as e:
        flash(f'Error loading email template: {str(e)}', 'error')
        return redirect(url_for('settings.settings_view'))
    finally:
        session.close()

@settings_bp.route('/api/refresh-weekly-fixtures', methods=['POST'])
@login_required
def refresh_weekly_fixtures_route():
    """Refresh fixtures from the weekly Google Sheet"""
    session = db_manager.get_session()
    try:
        # Get organization ID first
        org_id = get_user_organization_id()
        if not org_id:
            return jsonify({'error': 'No organization found'}), 404

        # Query the organization within this session to ensure we have fresh data
        # Use expire_on_commit=False to prevent detachment
        org = session.query(Organization).filter_by(id=org_id).first()
        if not org:
            return jsonify({'error': 'No organization found'}), 404

        # Refresh the object to get latest data from database
        session.refresh(org)

        # Get the weekly sheet URL from settings
        weekly_sheet_url = org.settings.get('weekly_sheet_url') if org.settings else None

        if not weekly_sheet_url:
            return jsonify({'error': 'No weekly fixture sheet URL configured. Please add one in Settings.'}), 400

        # Fetch and parse fixtures from the sheet
        fixtures_data, errors = refresh_weekly_fixtures(weekly_sheet_url)

        if errors and not fixtures_data:
            return jsonify({'error': 'Failed to fetch fixtures', 'details': errors}), 400

        # Process each fixture
        added_count = 0
        updated_count = 0
        skipped_count = 0
        processing_errors = []
        unmatched_pitches = set()  # Track pitches that couldn't be matched

        for fixture_data in fixtures_data:
            try:
                # Get or create team
                team_name = fixture_data.get('team')
                if not team_name:
                    processing_errors.append(f"Missing team name in row")
                    continue

                team = get_or_create_team(session, org.id, team_name, is_managed=True)

                # Get or create opposition team
                opp_name = fixture_data.get('opposition')
                if not opp_name:
                    processing_errors.append(f"Missing opposition for {team_name}")
                    continue

                opposition_team = get_or_create_team(session, org.id, opp_name, is_managed=False)

                # Get pitch if specified - use improved fuzzy matching logic
                pitch = None
                pitch_name = fixture_data.get('pitch', '').strip()

                # Special handling for home games - try to assign a default "Withdean" pitch
                home_away = fixture_data.get('home_away', 'Home')
                if home_away.lower() == 'home' and not pitch_name:
                    # Look for common Withdean/3G pitches for home games
                    default_pitches = ['3g', 'withdean', 'stanley deason', 'balfour', 'dorothy stringer', 'varndean']
                    for dp in default_pitches:
                        default_pitch = session.query(Pitch).filter(
                            Pitch.organization_id == org.id,
                            Pitch.name.ilike(f'%{dp}%')
                        ).first()
                        if default_pitch:
                            pitch = default_pitch
                            break

                if pitch_name:
                    # 1. Check for Alias Match first
                    from models import PitchAlias
                    alias_match = session.query(PitchAlias).filter(
                        PitchAlias.organization_id == org.id,
                        func.lower(PitchAlias.alias) == pitch_name.lower().strip()
                    ).first()
                    
                    if alias_match:
                        pitch = session.query(Pitch).get(alias_match.pitch_id)
                    
                    # 2. If no alias, try standard matching
                    if not pitch:
                        # Enhanced pitch matching with fuzzy logic
                        pitches = session.query(Pitch).filter_by(organization_id=org.id).all()
                        
                        exact_match = None
                        partial_match = None
                        fuzzy_matches = []
    
                        # Clean the pitch name for better matching
                        pitch_lower = pitch_name.lower().strip()
    
                        for p in pitches:
                            pitch_db_lower = p.name.lower().strip()
    
                            # Exact match (case-insensitive, whitespace normalized)
                            if pitch_db_lower == pitch_lower:
                                exact_match = p
                                break
    
                            # Partial match - one name contains the other
                            elif pitch_db_lower in pitch_lower or pitch_lower in pitch_db_lower:
                                partial_match = p
                                continue
    
                            # Fuzzy matching for common variations
                            p_words = set(pitch_db_lower.split())
                            fixture_words = set(pitch_lower.split())
                            word_intersect = p_words.intersection(fixture_words)
    
                            # If we have at least 1 common word and reasonable word overlap
                            if word_intersect and len(word_intersect) >= max(1, min(len(p_words), len(fixture_words)) * 0.5):
                                fuzzy_matches.append((p, len(word_intersect)))
                        
                        # Select best match
                        if exact_match:
                            pitch = exact_match
                        elif partial_match:
                            pitch = partial_match
                        elif fuzzy_matches:
                            # Sort by number of matching words (descending)
                            fuzzy_matches.sort(key=lambda x: x[1], reverse=True)
                            pitch = fuzzy_matches[0][0]


                    # If still no match found, we'll log it for user notification
                    if not pitch:
                        # We'll collect unmatched pitches for later reporting
                        unmatched_pitches.add(pitch_name)
                        logger.warning(f"Pitch matching failed for: '{pitch_name}'")
                else:
                    # Pitch name is empty/None
                    logger.warning(f"No pitch name found for fixture: {fixture_data.get('team', 'Unknown')} vs {fixture_data.get('opposition', 'Unknown')}")
                    # Try to log available keys to debug parsing issues
                    logger.debug(f"Fixture keys available: {list(fixture_data.keys())}")

                    # print(f"DEBUG: Pitch matching for '{pitch_name}' -> Found: {'Yes' if pitch else 'No'} {'(' + pitch.name + ')' if pitch else ''}")

                # For weekly sheets, all fixtures are for the upcoming Sunday
                # The weekly_sheet_refresher already sets date to next Sunday
                # We just need to parse the time from the time field
                kickoff_datetime = None
                date_str = fixture_data.get('date', '')  # This is already set to next Sunday by refresher
                time_str = fixture_data.get('time', '')  # Keep full time text for display

                if date_str:
                    try:
                        # Parse the date (which should be next Sunday)
                        base_date = date_parser.parse(date_str)  # Remove dayfirst=True for YYYY-MM-DD format

                        if time_str and time_str.lower() not in ['tbc', 'close', 'closed', '']:
                            # Try to extract the kickoff time from complex time formats
                            kickoff_time = time_str.strip()
                            if '&' in kickoff_time:
                                kickoff_time = kickoff_time.split('&')[0].strip()
                            elif '-' in kickoff_time:
                                kickoff_time = kickoff_time.split('-')[0].strip()

                            # Try to parse just the time part
                            try:
                                from datetime import datetime
                                # Parse time like "10:00", "10.00", "11:15" etc.
                                kickoff_time = kickoff_time.replace('.', ':')  # Handle 10.00 format
                                time_parts = kickoff_time.split(':')
                                if len(time_parts) >= 2:
                                    hour = int(time_parts[0])
                                    minute = int(time_parts[1])
                                    # Create datetime by combining date and time
                                    kickoff_datetime = base_date.replace(hour=hour, minute=minute)
                                else:
                                    # If time parsing fails, just use the date at a reasonable time
                                    kickoff_datetime = base_date.replace(hour=10, minute=0)
                            except:
                                # Fallback: use base date at 10:00 AM
                                kickoff_datetime = base_date.replace(hour=10, minute=0)
                        else:
                            # No time specified or it's "close"/"tbc" - use base date at 10:00 AM
                            kickoff_datetime = base_date.replace(hour=10, minute=0)
                    except:
                        # If date parsing fails completely, try to create datetime from next Sunday
                        try:
                            from datetime import datetime
                            next_sunday = datetime.strptime(date_str, '%Y-%m-%d').date()
                            kickoff_datetime = datetime.combine(next_sunday, datetime.min.time().replace(hour=10))
                        except:
                            pass  # Leave as None if all parsing fails

                # Check if fixture already exists (same team, opposition, and date)
                existing_fixture = None
                if kickoff_datetime:
                    existing_fixture = session.query(Fixture).filter_by(
                        organization_id=org.id,
                        team_id=team.id,
                        opposition_team_id=opposition_team.id,
                        kickoff_datetime=kickoff_datetime
                    ).first()

                if existing_fixture:
                    # Update ALL existing fixture fields with new data from spreadsheet
                    existing_fixture.opposition_team_id = opposition_team.id
                    existing_fixture.opposition_name = opp_name
                    existing_fixture.home_away = fixture_data.get('home_away', 'Home')
                    existing_fixture.pitch_id = pitch.id if pitch else None
                    existing_fixture.kickoff_datetime = kickoff_datetime
                    existing_fixture.kickoff_time_text = time_str
                    existing_fixture.match_format = fixture_data.get('match_format', '')
                    existing_fixture.fixture_length = fixture_data.get('fixture_length', '')
                    existing_fixture.each_way = fixture_data.get('each_way', '')
                    existing_fixture.referee_info = fixture_data.get('referee_info', '')
                    existing_fixture.instructions = fixture_data.get('instructions', '')
                    existing_fixture.home_manager = fixture_data.get('home_manager', '')
                    existing_fixture.fixtures_sec = fixture_data.get('fixtures_sec', '')
                    existing_fixture.manager_mobile = fixture_data.get('manager_mobile', '')
                    existing_fixture.contact_1 = fixture_data.get('contact_1', '')
                    existing_fixture.contact_2 = fixture_data.get('contact_2', '')
                    existing_fixture.contact_3 = fixture_data.get('contact_3', '')
                    existing_fixture.contact_5 = fixture_data.get('contact_5', '')

                    # Also un-archive the fixture if it was archived
                    existing_fixture.is_archived = False
                    existing_fixture.archived_at = None

                    updated_count += 1
                else:
                    # Create new fixture
                    new_fixture = Fixture(
                        organization_id=org.id,
                        team_id=team.id,
                        opposition_team_id=opposition_team.id,
                        opposition_name=opp_name,
                        home_away=fixture_data.get('home_away', 'Home'),
                        pitch_id=pitch.id if pitch else None,
                        kickoff_datetime=kickoff_datetime,
                        kickoff_time_text=time_str,
                        match_format=fixture_data.get('match_format', ''),
                        fixture_length=fixture_data.get('fixture_length', ''),
                        each_way=fixture_data.get('each_way', ''),
                        referee_info=fixture_data.get('referee_info', ''),
                        instructions=fixture_data.get('instructions', ''),
                        home_manager=fixture_data.get('home_manager', ''),
                        fixtures_sec=fixture_data.get('fixtures_sec', ''),
                        manager_mobile=fixture_data.get('manager_mobile', ''),
                        contact_1=fixture_data.get('contact_1', ''),
                        contact_2=fixture_data.get('contact_2', ''),
                        contact_3=fixture_data.get('contact_3', ''),
                        contact_5=fixture_data.get('contact_5', ''),
                        status='pending'
                    )
                    session.add(new_fixture)
                    session.flush()  # Get the fixture ID

                    # Create corresponding task
                    home_away = fixture_data.get('home_away', 'Home')
                    task_type = 'home_email' if home_away == 'Home' else 'away_email'
                    task_status = 'pending' if home_away == 'Home' else 'waiting'

                    new_task = Task(
                        organization_id=org.id,
                        fixture_id=new_fixture.id,
                        task_type=task_type,
                        status=task_status
                    )
                    session.add(new_task)
                    added_count += 1

            except Exception as e:
                    processing_errors.append(f"Error processing {fixture_data.get('team', 'unknown')} vs {fixture_data.get('opposition', 'unknown')}: {str(e)}")
                    continue
        # After processing all fixtures, add any unmatched pitches to the warnings
        if unmatched_pitches:
            pitch_warning = f"Unmatched pitches found in sheet that don't exist in your settings: {', '.join(sorted(unmatched_pitches))}. These fixture will have no pitch assigned. Please check your pitch settings or add these pitches if they are new venues."
            processing_errors.append(pitch_warning)
            
            # Log to file for debugging
            try:
                with open('unmatched_pitches.log', 'a') as f:
                    f.write(f"[{datetime.now()}] Unmatched pitches: {', '.join(sorted(unmatched_pitches))}\n")
            except Exception as e:
                logger.error(f"Failed to write to unmatched_pitches.log: {e}")

        session.commit()

        response_data = {
            'success': True,
            'added': added_count,
            'updated': updated_count,
            'total': added_count + updated_count
        }

        if processing_errors:
            response_data['warnings'] = processing_errors

        return jsonify(response_data)

    except Exception as e:
        session.rollback()
        logger.error(f"Error in refresh_weekly_fixtures_route: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'error': f'Failed to refresh fixtures: {str(e)}'}), 500
    finally:
        session.close()
