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
from managed_teams import MANAGED_TEAMS

# Setup logger
logger = logging.getLogger(__name__)

teams_bp = Blueprint('teams', __name__)

@teams_bp.route('/teams')
@login_required
def teams_view():
    """Teams management page"""
    session = db_manager.get_session()
    try:
        org = get_user_organization()
        if not org:
            flash('No organization found.', 'error')
            return redirect(url_for('auth.logout'))
        
        # Get managed teams (Withdean teams the user is following)
        managed_teams_objs = session.query(Team).filter_by(
            organization_id=org.id,
            is_managed=True
        ).order_by(Team.name).all()
        
        # Get ALL teams for the organization plus teams from our master list
        db_teams = session.query(Team).filter_by(organization_id=org.id).all()
        db_team_names = {t.name for t in db_teams}
        all_teams_list = sorted(list(set(db_team_names) | set(MANAGED_TEAMS)))
        
        # Get team coaches for all teams in this org
        team_coaches_query = session.query(TeamCoach).filter_by(
            organization_id=org.id
        ).all()
        
        # Mock user_manager for template compatibility (similar to settings_view)
        class UserManagerMock:
            def __init__(self, coaches_data, teams_data):
                self.coaches_data = coaches_data
                self.teams_lookup = {team.id: team.name for team in teams_data}
                self.teams_data = teams_data

            def get_team_coaches(self, team_name):
                result = []
                for coach in self.coaches_data:
                    coach_team_name = self.teams_lookup.get(coach.team_id, '')
                    if coach_team_name == team_name:
                        result.append(coach)
                return result

        user_manager = UserManagerMock(team_coaches_query, managed_teams_objs)
        
        # Teams data for kit colours and details
        teams_data = []
        for team in managed_teams_objs:
            teams_data.append({
                'name': team.name,
                'id': str(team.id),
                'fa_fixtures_url': team.fa_fixtures_url or '',
                'home_shirt': team.home_shirt or '',
                'home_shorts': team.home_shorts or '',
                'home_socks': team.home_socks or '',
                'away_shirt': team.away_shirt or '',
                'away_shorts': team.away_shorts or '',
                'away_socks': team.away_socks or ''
            })
            
        return render_template('teams.html',
            user_info={'name': current_user.name, 'email': current_user.email},
            user_name=current_user.name,
            managed_teams=[team.name for team in managed_teams_objs],
            teams_data=teams_data,
            all_teams=all_teams_list,
            user_manager=user_manager
        )
    finally:
        session.close()

@teams_bp.route('/teams/selection', methods=['POST'])
@login_required
def save_team_selection():
    """Save team selection (which teams the user manages)"""
    session = db_manager.get_session()
    try:
        org = get_user_organization()
        if not org:
            return jsonify({'success': False, 'message': 'No organization found'}), 400

        # Get selected teams from form
        selected_team_names = request.form.getlist('teams')

        # Update all teams to not be managed
        session.query(Team).filter_by(organization_id=org.id).update({'is_managed': False})

        # Set selected teams to be managed
        if selected_team_names:
            for team_name in selected_team_names:
                if not team_name: continue
                # Use get_or_create_team to ensure team exists
                team = get_or_create_team(session, org.id, team_name)
                team.is_managed = True

        session.commit()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True, 'message': 'Team selection updated'})
            
        flash('Team selection saved successfully!', 'success')
        return redirect(url_for('teams.teams_view'))

    except Exception as e:
        session.rollback()
        logger.error(f"Error saving team selection: {str(e)}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': str(e)}), 500
        flash(f'Error saving team selection: {str(e)}', 'error')
        return redirect(url_for('teams.teams_view'))
    finally:
        session.close()

@teams_bp.route('/teams/delete/<path:team_name>', methods=['DELETE'])
@login_required
def delete_team(team_name):
    """Permanently delete a team from the organization"""
    session = db_manager.get_session()
    try:
        org = get_user_organization()
        if not org:
            return jsonify({'success': False, 'message': 'No organization found'}), 400

        # Find the team
        team = session.query(Team).filter_by(
            organization_id=org.id,
            name=team_name
        ).first()

        if not team:
            return jsonify({'success': False, 'message': 'Team not found'}), 404

        # Delete all related data in order
        # 1. Delete tasks associated with this team's fixtures
        session.query(Task).filter_by(organization_id=org.id).join(Fixture).filter(Fixture.team_id == team.id).delete(synchronize_session=False)

        # 2. Delete fixtures for this team
        session.query(Fixture).filter_by(team_id=team.id).delete(synchronize_session=False)

        # 3. Delete team coaches
        session.query(TeamCoach).filter_by(organization_id=org.id, team_id=team.id).delete(synchronize_session=False)

        # 4. Delete team contact (the internal one if exists)
        session.query(TeamContact).filter_by(organization_id=org.id, team_name=team.name).delete(synchronize_session=False)

        # 5. Finally delete the team itself
        session.delete(team)

        session.commit()

        return jsonify({
            'success': True,
            'message': f'Team "{team_name}" deleted successfully.'
        })

    except Exception as e:
        session.rollback()
        logger.error(f"Error deleting team: {str(e)}")
        return jsonify({'success': False, 'message': f'Error deleting team: {str(e)}'}), 500
    finally:
        session.close()

@teams_bp.route('/teams/bulk-delete', methods=['DELETE'])
@login_required
def bulk_delete_teams():
    """Permanently delete multiple teams from the organization"""
    session = db_manager.get_session()
    try:
        org = get_user_organization()
        if not org:
            return jsonify({'success': False, 'message': 'No organization found'}), 400

        data = request.get_json()
        team_names = data.get('teams', []) if data else []

        if not team_names:
            return jsonify({'success': False, 'message': 'No teams specified for deletion'}), 400

        teams_deleted = 0
        for team_name in team_names:
            team = session.query(Team).filter_by(organization_id=org.id, name=team_name).first()
            if not team: continue

            # Delete related data (coaches, fixtures, tasks)
            session.query(Task).filter_by(organization_id=org.id).join(Fixture).filter(Fixture.team_id == team.id).delete(synchronize_session=False)
            session.query(Fixture).filter_by(team_id=team.id).delete(synchronize_session=False)
            session.query(TeamCoach).filter_by(organization_id=org.id, team_id=team.id).delete(synchronize_session=False)
            session.query(TeamContact).filter_by(organization_id=org.id, team_name=team.name).delete(synchronize_session=False)
            session.delete(team)
            teams_deleted += 1

        session.commit()

        return jsonify({
            'success': True,
            'deleted_count': teams_deleted,
            'message': f'Successfully deleted {teams_deleted} teams.'
        })

    except Exception as e:
        session.rollback()
        logger.error(f"Error bulk deleting teams: {str(e)}")
        return jsonify({'success': False, 'message': f'Error bulk deleting teams: {str(e)}'}), 500
    finally:
        session.close()

@teams_bp.route('/teams/coaches', methods=['POST'])
@login_required
def add_or_update_coach():
    """Add or update team coach"""
    session = db_manager.get_session()
    try:
        org = get_user_organization()
        if not org:
            return jsonify({'success': False, 'message': 'No organization found'}), 400

        team_name = request.form.get('team_name')
        coach_name = request.form.get('coach_name')
        coach_id = request.form.get('coach_id')

        if not team_name or not coach_name:
            return jsonify({'success': False, 'message': 'Team and coach name are required'}), 400

        team = get_or_create_team(session, org.id, team_name)

        if coach_id:
            coach = session.query(TeamCoach).filter_by(id=coach_id, organization_id=org.id).first()
            if not coach:
                return jsonify({'success': False, 'message': 'Coach not found'}), 404
        else:
            coach = TeamCoach(organization_id=org.id, team_id=team.id)
            session.add(coach)

        coach.team_id = team.id
        coach.coach_name = coach_name
        coach.email = request.form.get('email', '')
        coach.phone = request.form.get('phone', '')
        coach.role = request.form.get('role', 'Coach')
        coach.notes = request.form.get('notes', '')
        coach.updated_at = datetime.utcnow()

        session.commit()
        
        return jsonify({
            'success': True, 
            'message': 'Coach saved',
            'coach': {
                'id': str(coach.id),
                'coach_name': coach.coach_name,
                'role': coach.role
            }
        })

    except Exception as e:
        session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        session.close()

@teams_bp.route('/teams/coaches/team/<path:team_name>')
@login_required
def get_coaches(team_name):
    """Get all coaches for a team"""
    session = db_manager.get_session()
    try:
        org = get_user_organization()
        team = session.query(Team).filter_by(organization_id=org.id, name=team_name).first()
        if not team:
            return jsonify([])

        coaches = session.query(TeamCoach).filter_by(organization_id=org.id, team_id=team.id).all()
        return jsonify([{
            'id': str(c.id),
            'coach_name': c.coach_name,
            'email': c.email or '',
            'phone': c.phone or '',
            'role': c.role or 'Coach',
            'notes': c.notes or ''
        } for c in coaches])
    finally:
        session.close()

@teams_bp.route('/teams/coaches/delete', methods=['POST'])
@login_required
def delete_coach():
    """Delete coach by ID"""
    session = db_manager.get_session()
    try:
        org = get_user_organization()
        data = request.get_json()
        coach_id = data.get('coach_id')

        if not coach_id:
            return jsonify({'success': False, 'message': 'No coach ID provided'}), 400

        coach = session.query(TeamCoach).filter_by(id=coach_id, organization_id=org.id).first()
        if not coach:
            return jsonify({'success': False, 'message': 'Coach not found'}), 404

        session.delete(coach)
        session.commit()
        return jsonify({'success': True, 'message': 'Coach removed'})
    except Exception as e:
        session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        session.close()

@teams_bp.route('/teams/kit/<path:team_name>')
@login_required
def get_kit(team_name):
    """Get kit colours for a team"""
    session = db_manager.get_session()
    try:
        org = get_user_organization()
        team = session.query(Team).filter_by(organization_id=org.id, name=team_name).first()
        if not team:
            return jsonify({})

        return jsonify({
            'home_shirt': team.home_shirt or '',
            'home_shorts': team.home_shorts or '',
            'home_socks': team.home_socks or '',
            'away_shirt': team.away_shirt or '',
            'away_shorts': team.away_shorts or '',
            'away_socks': team.away_socks or ''
        })
    finally:
        session.close()

@teams_bp.route('/teams/kit', methods=['POST'])
@login_required
def save_kit():
    """Save kit colours for a team"""
    session = db_manager.get_session()
    try:
        org = get_user_organization()
        team_name = request.form.get('team_name')
        if not team_name:
            return jsonify({'success': False, 'message': 'Team name required'}), 400

        team = get_or_create_team(session, org.id, team_name)
        team.home_shirt = request.form.get('home_shirt', '')
        team.home_shorts = request.form.get('home_shorts', '')
        team.home_socks = request.form.get('home_socks', '')
        team.away_shirt = request.form.get('away_shirt', '')
        team.away_shorts = request.form.get('away_shorts', '')
        team.away_socks = request.form.get('away_socks', '')
        
        session.commit()
        return jsonify({'success': True, 'message': 'Kit colours saved'})
    except Exception as e:
        session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        session.close()

@teams_bp.route('/teams/fa-url', methods=['POST'])
@login_required
def save_fa_url():
    """Save FA fixtures URL for a team"""
    session = db_manager.get_session()
    try:
        org = get_user_organization()
        team_name = request.form.get('team_name')
        fa_url = request.form.get('fa_url', '')

        if not team_name:
            return jsonify({'success': False, 'message': 'Team name required'}), 400

        team = get_or_create_team(session, org.id, team_name)
        team.fa_fixtures_url = fa_url
        session.commit()
        return jsonify({'success': True, 'message': 'FA URL saved'})
    except Exception as e:
        session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        session.close()
