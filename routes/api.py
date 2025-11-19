from flask import Blueprint, jsonify, request, send_from_directory, current_app
from flask_login import login_required, current_user
from sqlalchemy import func
from datetime import datetime
import os
import urllib.parse

from database import db_manager
from utils import get_user_organization, get_user_organization_id
from models import Task, Team, TeamCoach, Fixture, Organization

api_bp = Blueprint('api', __name__)

def generate_google_maps_url(address, api_key, parking_address=None):
    """Generate Google Static Maps API URL from address with optional parking location"""
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
    if not address:
        return None

    base_url = "https://www.google.com/maps/search/?"
    params = {'query': address}
    return base_url + urllib.parse.urlencode(params)

@api_bp.route('/api/summary')
@login_required
def api_summary():
    """API endpoint for dashboard summary"""
    session = db_manager.get_session()
    try:
        org = get_user_organization()
        if not org:
            return jsonify({'error': 'No organization found'}), 404
        
        # Get counts by status - exclude archived tasks
        pending = session.query(Task).filter_by(organization_id=org.id, status='pending').filter(Task.is_archived != True).count()
        waiting = session.query(Task).filter_by(organization_id=org.id, status='waiting').filter(Task.is_archived != True).count()
        in_progress = session.query(Task).filter_by(organization_id=org.id, status='in_progress').filter(Task.is_archived != True).count()
        completed = session.query(Task).filter_by(organization_id=org.id, status='completed').filter(Task.is_archived != True).count()
        
        return jsonify({
            'pending': pending,
            'waiting': waiting,  
            'in_progress': in_progress,
            'completed': completed
        })
        
    finally:
        session.close()

@api_bp.route('/api/managed-teams')
@login_required
def get_managed_teams():
    """Get list of managed teams for the current user"""
    session = db_manager.get_session()
    try:
        org = get_user_organization()
        if not org:
            return jsonify({'error': 'No organization found'}), 404

        managed_teams = session.query(Team).filter_by(
            organization_id=org.id,
            is_managed=True
        ).order_by(Team.name).all()

        teams = [{'name': team.name, 'id': str(team.id)} for team in managed_teams]

        return jsonify({'teams': teams})

    except Exception as e:
        print(f"Error getting managed teams: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to fetch teams'}), 500
    finally:
        session.close()

@api_bp.route('/api/generate-away-match-response', methods=['POST'])
@login_required
def generate_away_match_response():
    """Generate template response text for away match emails - handles both simple template and text parsing modes"""
    try:
        data = request.get_json()
        team_name = data.get('team_name', '').strip()
        input_text = data.get('input_text', '').strip()

        # Handle new simplified template generation (tasks page)
        if team_name:
            # Get user organization
            session = db_manager.get_session()
            try:
                org = get_user_organization()
                if not org:
                    return jsonify({'success': False, 'message': 'No organization found'})

                # Get team coach info
                team_obj = session.query(Team).filter_by(organization_id=org.id, name=team_name).first()
                if not team_obj:
                    return jsonify({'success': False, 'message': f'Team "{team_name}" not found'})

                # Get team coach
                team_coach = session.query(TeamCoach).filter_by(
                    organization_id=org.id,
                    team_id=team_obj.id
                ).first()

                # Get contact info - format as requested
                manager_name = team_coach.coach_name if team_coach and team_coach.coach_name else "INSERT MANAGER'S NAME"
                manager_email = team_coach.email if team_coach and team_coach.email else "INSERT MANAGER'S EMAIL"
                manager_phone = team_coach.phone if team_coach and team_coach.phone else "INSERT MANAGER'S PHONE"

                # Get kit colors - extract just the color names
                kit_colors = []
                if team_obj.home_shirt:
                    # Extract color name (e.g., "RED" from "RED shirt" or just "RED")
                    shirt_color = team_obj.home_shirt.upper().strip()
                    # Remove common words like "shirt", "top", etc.
                    for word in ['SHIRT', 'TOP', 'JERSEY', 'KIT']:
                        shirt_color = shirt_color.replace(word, '').strip()
                    if shirt_color:
                        kit_colors.append(shirt_color.split()[0])  # Take first word (the color)
                
                if team_obj.home_shorts:
                    shorts_color = team_obj.home_shorts.upper().strip()
                    for word in ['SHORTS', 'BOTTOMS', 'TROUSERS']:
                        shorts_color = shorts_color.replace(word, '').strip()
                    if shorts_color:
                        color_name = shorts_color.split()[0]
                        if color_name not in kit_colors:
                            kit_colors.append(color_name)
                
                if team_obj.home_socks:
                    socks_color = team_obj.home_socks.upper().strip()
                    for word in ['SOCKS', 'STOCKINGS']:
                        socks_color = socks_color.replace(word, '').strip()
                    if socks_color:
                        color_name = socks_color.split()[0]
                        if color_name not in kit_colors:
                            kit_colors.append(color_name)
                
                # Format kit colors nicely
                if kit_colors:
                    # Remove duplicates while preserving order
                    unique_colors = []
                    for color in kit_colors:
                        if color and color not in unique_colors:
                            unique_colors.append(color)
                    kit_info = " and ".join(unique_colors) if unique_colors else "RED and BLUE"
                else:
                    kit_info = "RED and BLUE"

                # Generate the response template in the exact format requested
                response_parts = [
                    "Many thanks for the fixtures information.",
                    "",
                    "Our match day contact is:",
                    "",
                    f"{manager_name},",
                    f"{manager_email},",
                    f"{manager_phone}",
                    "",
                    f"Our team plays in {kit_info}."
                ]

                formatted_response = "\n".join(response_parts)

                return jsonify({
                    'success': True,
                    'response_text': formatted_response,
                    'team_name': team_name
                })

            finally:
                session.close()
        # Handle old text parsing mode (task detail page)
        elif input_text:
            # This is the old functionality from task_detail.html
            # For now, just return a simple message indicating this method is deprecated
            return jsonify({
                'success': False,
                'message': 'This method is no longer supported. Please use the new template generator in the tasks page.'
            })

        # No valid input
        return jsonify({'success': False, 'message': 'Either team_name or input_text must be provided'}), 400

    except Exception as e:
        print(f"Error generating away match response: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Error generating response: {str(e)}'}), 500

@api_bp.route('/api/generate-map-urls', methods=['POST'])
@login_required
def generate_map_urls():
    """Generate map URLs from address for preview"""
    try:
        data = request.get_json()
        address = data.get('address', '').strip()
        parking_address = data.get('parking_address', '').strip()

        if not address:
            return jsonify({'error': 'Address is required'}), 400

        # Generate map image URL
        map_image_url = None
        api_key = os.environ.get('GOOGLE_MAPS_API_KEY')
        if api_key and api_key != 'your_google_maps_api_key_here':
            map_image_url = generate_google_maps_url(address, api_key, parking_address)

        # Generate Google Maps link (primary address)
        google_maps_link = generate_google_maps_link(address)

        # Generate parking-specific maps if parking address is different
        parking_map_image_url = ''
        parking_google_maps_link = ''

        if (parking_address and parking_address.strip() and
            parking_address.strip().lower() != address.strip().lower()):

            if api_key and api_key != 'your_google_maps_api_key_here':
                parking_map_image_url = generate_google_maps_url(parking_address, api_key)
            parking_google_maps_link = generate_google_maps_link(parking_address)

        return jsonify({
            'map_image_url': map_image_url,
            'google_maps_link': google_maps_link,
            'parking_map_image_url': parking_map_image_url,
            'parking_google_maps_link': parking_google_maps_link,
            'address': address,
            'parking_address': parking_address
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_bp.route('/static/uploads/maps/<filename>')
@login_required
def serve_uploaded_map(filename):
    """Serve uploaded map images - SECURED"""
    # FIX: Validate filename to prevent path traversal
    if '..' in filename or '/' in filename or '\\' in filename:
        return "Invalid filename", 400

    upload_dir = os.path.join(os.getcwd(), 'static', 'uploads', 'maps')
    return send_from_directory(upload_dir, filename)

@api_bp.route('/admin/clear-sample-data', methods=['POST'])
@login_required
def clear_sample_data():
    """Clear sample/placeholder data from the database"""
    session = db_manager.get_session()
    try:
        org = get_user_organization()
        if not org:
            return jsonify({'error': 'No organization found'}), 400

        # Define placeholder patterns to clear
        placeholder_oppositions = ['Rovers FC', 'City United', 'Wanderers', 'Athletic FC', 'Rangers']
        sample_emails = ['coach@roversfc@example.com', 'coach@cityunited@example.com']

        removed_fixtures = 0
        removed_teams = 0
        removed_coaches = 0

        # Remove fixtures with placeholder opposition names
        for opp_name in placeholder_oppositions:
            fixtures_to_remove = session.query(Fixture).filter_by(
                organization_id=org.id,
                opposition_name=opp_name
            ).all()

            for fixture in fixtures_to_remove:
                # Remove associated tasks
                tasks_to_remove = session.query(Task).filter_by(fixture_id=fixture.id).all()
                for task in tasks_to_remove:
                    session.delete(task)

                # Remove the fixture itself
                session.delete(fixture)
                removed_fixtures += 1

        # Remove sample coaches by email pattern
        for email_pattern in sample_emails:
            coaches_to_remove = session.query(TeamCoach).filter_by(
                organization_id=org.id,
                email=email_pattern
            ).all()

            for coach in coaches_to_remove:
                session.delete(coach)
                removed_coaches += 1

        # Remove empty opposition teams (teams that are not managed and have no fixtures)
        all_teams = session.query(Team).filter_by(organization_id=org.id).all()
        for team in all_teams:
            if not team.is_managed:
                fixture_count = session.query(Fixture).filter(
                    (Fixture.team_id == team.id) | (Fixture.opposition_team_id == team.id)
                ).count()

                if fixture_count == 0:
                    session.delete(team)
                    removed_teams += 1

        session.commit()

        return jsonify({
            'success': True,
            'message': f'Cleared {removed_fixtures} sample fixtures, {removed_coaches} sample coaches, and {removed_teams} empty opposition teams'
        })

    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()
