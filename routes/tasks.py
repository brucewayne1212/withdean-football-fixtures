from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import joinedload
import urllib.parse

from database import db_manager
from utils import get_user_organization
from models import Task, Fixture, Team, Pitch, EmailTemplate, TeamCoach, TeamContact

# Local imports
from smart_email_generator import SmartEmailGenerator
from services.email_service import TemplateManager
import re

tasks_bp = Blueprint('tasks', __name__)

@tasks_bp.route('/tasks')
@tasks_bp.route('/tasks/<status>')
@login_required
def view_tasks(status=None):
    """View tasks, optionally filtered by status"""
    session = db_manager.get_session()
    try:
        org = get_user_organization()
        if not org:
            flash('No organization found. Please contact support.', 'error')
            return redirect(url_for('auth.logout'))

        today = datetime.now().date()
        current_week_start = today - timedelta(days=today.weekday())

        def is_current_or_future_fixture(fixture):
            if not fixture or not fixture.kickoff_datetime:
                return True
            fixture_dt = fixture.kickoff_datetime
            if fixture_dt.tzinfo:
                fixture_dt = fixture_dt.astimezone(timezone.utc)
            return fixture_dt.date() >= current_week_start
        
        # Get filter parameters
        task_type = request.args.get('type', 'all')
        status_filter = request.args.get('status', status or 'all')
        show_all_teams = request.args.get('show_all', 'false').lower() == 'true'
        
        # Build query - exclude archived tasks by default
        query = session.query(Task).filter_by(organization_id=org.id).filter(Task.is_archived != True)
        
        # Apply status filter
        if status_filter and status_filter in ['pending', 'waiting', 'in_progress', 'completed']:
            query = query.filter_by(status=status_filter)
        
        # Apply task type filter
        if task_type != 'all':
            query = query.filter_by(task_type=task_type)
        
        # Get tasks with their associated fixtures and teams (specify explicit join)
        all_tasks = query.join(Fixture).join(Team, Fixture.team_id == Team.id).order_by(Task.created_at.desc()).all()
        all_tasks = [task for task in all_tasks if is_current_or_future_fixture(task.fixture)]
        
        # Apply team filtering - show only managed teams by default unless show_all is True
        if not show_all_teams:
            # Get managed team IDs
            managed_team_ids = [team.id for team in session.query(Team).filter_by(
                organization_id=org.id,
                is_managed=True
            ).all()]
            
            # Filter tasks to only show those for managed teams
            tasks = [task for task in all_tasks if task.fixture.team_id in managed_team_ids]
        else:
            tasks = all_tasks
        
        # Enrich tasks with computed properties for template compatibility
        for task in tasks:
            fixture = task.fixture
            team = session.query(Team).filter_by(id=fixture.team_id).first()
            
            # Add properties to task object for template compatibility
            task.team = team.name if team else 'Unknown Team'
            task.opposition = fixture.opposition_name or 'TBC'
            task.home_away = fixture.home_away
            task.pitch = fixture.pitch.name if fixture.pitch else 'TBC'
            task.kickoff_time = fixture.kickoff_time_text or 'TBC'
            task.kickoff_datetime = fixture.kickoff_datetime  # Add datetime for date display
            task.created_date = task.created_at.isoformat() if task.created_at else ''
            task.completed_date = task.completed_at.isoformat() if task.completed_at else None
            
            # Handle task_type and status as enums (template expects .value)
            class TaskTypeEnum:
                def __init__(self, value):
                    self.value = value
            
            class StatusEnum:
                def __init__(self, value):
                    self.value = value
            
            task.task_type = TaskTypeEnum(task.task_type)
            task.status = StatusEnum(task.status)

        # Get managed teams count
        managed_teams_count = session.query(Team).filter_by(
            organization_id=org.id,
            is_managed=True
        ).count()
        
        # Get task counts for summary - only include current/future fixtures
        pending_count = len([task for task in tasks if task.status.value == 'pending'])
        waiting_count = len([task for task in tasks if task.status.value == 'waiting'])
        in_progress_count = len([task for task in tasks if task.status.value == 'in_progress'])
        completed_count = len([task for task in tasks if task.status.value == 'completed'])
        
        # Create summary objects for template compatibility
        my_summary = {
            'total': len(tasks),
            'pending': pending_count,
            'waiting': waiting_count,
            'in_progress': in_progress_count,
            'completed': completed_count
        }
        
        return render_template('tasks.html', 
            tasks=tasks, 
            current_status=status_filter,
            current_type=task_type,
            show_all_teams=show_all_teams,
            total_tasks=len(all_tasks),
            user_name=current_user.name,
            my_teams_count=managed_teams_count,
            my_summary=my_summary
        )
        
    finally:
        session.close()

@tasks_bp.route('/task/<task_id>')
@login_required
def view_task(task_id):
    """View individual task details"""
    session = db_manager.get_session()
    try:
        org = get_user_organization()
        if not org:
            flash('No organization found.', 'error')
            return redirect(url_for('auth.logout'))
        
        # Get task with fixture and team information using eager loading
        task = session.query(Task).filter_by(
            id=task_id,
            organization_id=org.id
        ).join(Fixture).join(Team, Fixture.team_id == Team.id).first()
        
        if not task:
            flash('Task not found.', 'error')
            return redirect(url_for('dashboard.dashboard_view'))
        
        # Add computed properties for template compatibility
        # Access the related data through relationships
        fixture = task.fixture
        team = session.query(Team).filter_by(id=fixture.team_id).first()
        
        # Add properties to task object for template compatibility
        task.team = team.name if team else 'Unknown Team'
        task.opposition = fixture.opposition_name or 'TBC'
        task.home_away = fixture.home_away
        # Get pitch information if assigned
        if fixture.pitch:
            task.pitch = fixture.pitch.name
        else:
            task.pitch = 'TBC'
        task.kickoff_time = fixture.kickoff_time_text or 'TBC'
        task.created_date = task.created_at.isoformat() if task.created_at else ''
        task.completed_date = task.completed_at.isoformat() if task.completed_at else None
        
        # Handle task_type and status as enums (template expects .value)
        class TaskTypeEnum:
            def __init__(self, value):
                self.value = value
        
        class StatusEnum:
            def __init__(self, value):
                self.value = value
        
        task.task_type = TaskTypeEnum(task.task_type)
        task.status = StatusEnum(task.status)

        # Get available pitches for editing
        pitches = session.query(Pitch).filter_by(organization_id=org.id).all()

        template = '_task_detail_content.html' if request.args.get('modal') else 'task_detail.html'

        return render_template(template,
            task=task,
            user_name=current_user.name,
            pitches=pitches,
            fixture=fixture
        )
        
    finally:
        session.close()

@tasks_bp.route('/update_task_status', methods=['POST'])
@login_required
def update_task_status():
    """Update task status"""
    task_id = request.form.get('task_id')
    new_status = request.form.get('status')
    
    if not task_id or not new_status:
        flash('Invalid request.', 'error')
        return redirect(request.referrer or url_for('dashboard.dashboard_view'))
    
    session = db_manager.get_session()
    try:
        org = get_user_organization()
        if not org:
            flash('No organization found.', 'error')
            return redirect(url_for('auth.logout'))
        
        task = session.query(Task).filter_by(
            id=task_id,
            organization_id=org.id
        ).first()
        
        if not task:
            flash('Task not found.', 'error')
            return redirect(request.referrer or url_for('dashboard.dashboard_view'))
        
        task.status = new_status
        if new_status == 'completed':
            task.completed_at = datetime.utcnow()
        else:
            task.completed_at = None
            
        session.commit()
        flash(f'Task status updated to {new_status}.', 'success')
        
    except Exception as e:
        session.rollback()
        flash(f'Error updating task: {str(e)}', 'error')
    finally:
        session.close()
    
    return redirect(request.referrer or url_for('dashboard.dashboard_view'))

@tasks_bp.route('/mark_in_progress/<task_id>', methods=['POST'])
@login_required
def mark_in_progress(task_id):
    """Mark a task as in progress"""
    session = db_manager.get_session()
    try:
        org = get_user_organization()
        if not org:
            flash('No organization found.', 'error')
            return redirect(url_for('auth.logout'))
        
        task = session.query(Task).filter_by(
            id=task_id,
            organization_id=org.id
        ).first()
        
        if not task:
            flash('Task not found.', 'error')
            return redirect(request.referrer or url_for('dashboard.dashboard_view'))
        
        task.status = 'in_progress'
        task.completed_at = None
        session.commit()
        
        flash('Task marked as in progress.', 'success')
        
    except Exception as e:
        session.rollback()
        flash(f'Error updating task: {str(e)}', 'error')
    finally:
        session.close()
    
    return redirect(request.referrer or url_for('dashboard.dashboard_view'))

@tasks_bp.route('/mark_completed/<task_id>', methods=['POST'])
@login_required
def mark_task_completed(task_id):
    """Mark a task as completed"""
    session = db_manager.get_session()
    try:
        org = get_user_organization()
        if not org:
            return jsonify({'error': 'No organization found'}), 400
        
        # Get the task
        task = session.query(Task).filter_by(
            id=task_id,
            organization_id=org.id
        ).first()
        
        if not task:
            return jsonify({'error': 'Task not found'}), 404
        
        # Get notes from request
        notes = request.json.get('notes', '') if request.is_json else request.form.get('notes', '')
        
        # Update task
        task.status = 'completed'
        task.completed_at = datetime.utcnow()
        task.notes = notes
        
        session.commit()
        
        if request.is_json:
            return jsonify({'success': True, 'message': 'Task marked as completed'})
        else:
            flash('Task marked as completed!', 'success')
            return redirect(url_for('tasks.view_task', task_id=task_id))
            
    except Exception as e:
        session.rollback()
        print(f"Error marking task as completed: {e}")
        if request.is_json:
            return jsonify({'error': 'Failed to mark task as completed'}), 500
        else:
            flash('Error marking task as completed', 'error')
            return redirect(url_for('tasks.view_task', task_id=task_id))
    finally:
        session.close()

@tasks_bp.route('/mark_task_in_progress/<task_id>', methods=['POST']) # Renamed endpoint to avoid conflict if imported in same namespace
@login_required
def mark_task_in_progress(task_id):
    """Mark a task as in progress (JSON version)"""
    session = db_manager.get_session()
    try:
        org = get_user_organization()
        if not org:
            return jsonify({'error': 'No organization found'}), 400
        
        # Get the task
        task = session.query(Task).filter_by(
            id=task_id,
            organization_id=org.id
        ).first()
        
        if not task:
            return jsonify({'error': 'Task not found'}), 404
        
        # Update task status
        task.status = 'in_progress'
        session.commit()
        
        return jsonify({'success': True, 'message': 'Task marked as in progress'})
        
    except Exception as e:
        session.rollback()
        print(f"Error marking task as in progress: {e}")
        return jsonify({'error': 'Failed to mark task as in progress'}), 500
    finally:
        session.close()

@tasks_bp.route('/cancel_fixture', methods=['POST'])
@login_required
def cancel_fixture():
    """Cancel a fixture with reason"""
    try:
        data = request.get_json()
        fixture_id = data.get('fixture_id')
        reason = data.get('reason', '')

        if not fixture_id:
            return jsonify({'success': False, 'error': 'Fixture ID is required'})

        session = db_manager.get_session()
        try:
            org = get_user_organization()
            if not org:
                return jsonify({'success': False, 'error': 'No organization found'})

            # Find the fixture's task
            task = session.query(Task).filter_by(
                id=fixture_id,
                organization_id=org.id
            ).first()

            if not task:
                return jsonify({'success': False, 'error': 'Fixture not found'})

            # Find the associated fixture
            fixture = session.query(Fixture).filter_by(task_id=task.id).first()
            if not fixture:
                return jsonify({'success': False, 'error': 'Fixture details not found'})

            # Update fixture cancellation status
            fixture.is_cancelled = True
            fixture.cancellation_reason = reason
            fixture.cancelled_at = datetime.utcnow()
            fixture.status = 'cancelled'

            # Update task status
            task.status = 'cancelled'

            session.commit()

            return jsonify({
                'success': True,
                'message': 'Fixture cancelled successfully'
            })

        except Exception as e:
            session.rollback()
            return jsonify({'success': False, 'error': str(e)})
        finally:
            session.close()

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@tasks_bp.route('/uncancel_fixture', methods=['POST'])
@login_required
def uncancel_fixture():
    """Remove cancellation from a fixture"""
    try:
        data = request.get_json()
        fixture_id = data.get('fixture_id')

        if not fixture_id:
            return jsonify({'success': False, 'error': 'Fixture ID is required'})

        session = db_manager.get_session()
        try:
            org = get_user_organization()
            if not org:
                return jsonify({'success': False, 'error': 'No organization found'})

            # Find the fixture's task
            task = session.query(Task).filter_by(
                id=fixture_id,
                organization_id=org.id
            ).first()

            if not task:
                return jsonify({'success': False, 'error': 'Fixture not found'})

            # Find the associated fixture
            fixture = session.query(Fixture).filter_by(task_id=task.id).first()
            if not fixture:
                return jsonify({'success': False, 'error': 'Fixture details not found'})

            # Remove cancellation status
            fixture.is_cancelled = False
            fixture.cancellation_reason = None
            fixture.cancelled_at = None
            fixture.status = 'pending'

            # Update task status
            task.status = 'pending'

            session.commit()

            return jsonify({
                'success': True,
                'message': 'Fixture cancellation removed successfully'
            })

        except Exception as e:
            session.rollback()
            return jsonify({'success': False, 'error': str(e)})
        finally:
            session.close()

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@tasks_bp.route('/bulk_complete', methods=['POST'])
@login_required
def bulk_complete_tasks():
    """Mark multiple tasks as completed"""
    session = db_manager.get_session()
    try:
        org = get_user_organization()
        if not org:
            return jsonify({'error': 'No organization found'}), 400
        
        task_ids = request.json.get('task_ids', [])
        notes = request.json.get('notes', '')
        
        if not task_ids:
            return jsonify({'error': 'No tasks selected'}), 400
        
        # Update tasks
        completed_count = 0
        for task_id in task_ids:
            task = session.query(Task).filter_by(
                id=task_id,
                organization_id=org.id
            ).first()
            
            if task:
                task.status = 'completed'
                task.completed_at = datetime.utcnow()
                task.notes = notes
                completed_count += 1
        
        session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'Marked {completed_count} tasks as completed',
            'completed_count': completed_count
        })
        
    except Exception as e:
        session.rollback()
        print(f"Error bulk completing tasks: {e}")
        return jsonify({'error': 'Failed to complete tasks'}), 500
    finally:
        session.close()

@tasks_bp.route('/bulk_archive', methods=['POST'])
@login_required
def bulk_archive_tasks():
    """Archive multiple tasks (default bulk operation)"""
    session = db_manager.get_session()
    try:
        org = get_user_organization()
        if not org:
            return jsonify({'error': 'No organization found'}), 400

        task_ids = request.json.get('task_ids', [])

        if not task_ids:
            return jsonify({'error': 'No tasks selected'}), 400

        # Archive tasks - task_ids are UUID strings, not integers
        task_ids_str = task_ids  # Keep as strings since task IDs are UUIDs

        # Get all tasks for this org (not archived) to ensure we can only archive owned tasks
        existing_tasks = session.query(Task).filter(
            Task.organization_id == org.id,
            Task.id.in_(task_ids_str),
            Task.is_archived == False
        ).all()

        # Archive tasks
        archived_count = 0
        for task in existing_tasks:
            task.is_archived = True
            task.archived_at = datetime.utcnow()
            archived_count += 1

        session.commit()

        return jsonify({
            'success': True,
            'message': f'Archived {archived_count} tasks',
            'archived_count': archived_count
        })

    except Exception as e:
        session.rollback()
        print(f"Error bulk archiving tasks: {e}")
        return jsonify({'error': 'Failed to archive tasks'}), 500
    finally:
        session.close()

@tasks_bp.route('/bulk_delete', methods=['POST'])
@login_required
def bulk_delete_tasks():
    """Permanently delete multiple tasks (for matches added in error)"""
    session = db_manager.get_session()
    try:
        org = get_user_organization()
        if not org:
            return jsonify({'error': 'No organization found'}), 400

        task_ids = request.json.get('task_ids', [])
        permanent = request.json.get('permanent', False)

        if not task_ids:
            return jsonify({'error': 'No tasks selected'}), 400

        if not permanent:
            return jsonify({'error': 'Permanent deletion must be explicitly confirmed'}), 400

        # Task IDs are UUID strings, not integers
        task_ids_str = task_ids  # Keep as strings since task IDs are UUIDs

        # Get all tasks for this org to ensure we can only delete owned tasks
        existing_tasks = session.query(Task).filter(
            Task.organization_id == org.id,
            Task.id.in_(task_ids_str)
        ).all()

        # Permanently delete tasks and their fixtures
        deleted_count = 0
        fixtures_to_check = set()  # Track fixtures that might need deletion

        for task in existing_tasks:
            fixture_id = task.fixture_id
            if fixture_id:
                fixtures_to_check.add(fixture_id)

            session.delete(task)
            deleted_count += 1

        # Check which fixtures have no remaining tasks and delete them
        fixtures_deleted = 0
        for fixture_id in fixtures_to_check:
            remaining_tasks = session.query(Task).filter_by(fixture_id=fixture_id).count()
            if remaining_tasks == 0:
                fixture = session.query(Fixture).filter_by(id=fixture_id, organization_id=org.id).first()
                if fixture:
                    session.delete(fixture)
                    fixtures_deleted += 1

        session.commit()

        message_parts = [f'Permanently deleted {deleted_count} tasks']
        if fixtures_deleted > 0:
            message_parts.append(f'and {fixtures_deleted} orphaned fixtures')

        return jsonify({
            'success': True,
            'message': ', '.join(message_parts),
            'deleted_count': deleted_count,
            'fixtures_deleted': fixtures_deleted
        })

    except Exception as e:
        session.rollback()
        print(f"Error bulk deleting tasks: {e}")
        return jsonify({'error': 'Failed to delete tasks'}), 500
    finally:
        session.close()

@tasks_bp.route('/edit_fixture/<task_id>', methods=['GET', 'POST'])
@login_required
def edit_fixture(task_id):
    """Edit fixture details"""
    session = db_manager.get_session()
    try:
        org = get_user_organization()
        if not org:
            flash('No organization found.', 'error')
            return redirect(url_for('auth.logout'))

        # Get task and fixture
        task = session.query(Task).filter_by(
            id=task_id,
            organization_id=org.id
        ).first()

        if not task:
            flash('Task not found.', 'error')
            return redirect(url_for('tasks.view_tasks'))

        fixture = task.fixture
        if not fixture:
            flash('No fixture associated with this task.', 'error')
            return redirect(url_for('tasks.view_task', task_id=task_id))

        if request.method == 'POST':
            # Update fixture details
            fixture.opposition_name = request.form.get('opposition_name')

            # Handle pitch assignment
            pitch_name = request.form.get('pitch_name')
            if pitch_name:
                # Find the pitch by name and set the pitch_id
                selected_pitch = session.query(Pitch).filter_by(
                    organization_id=org.id,
                    name=pitch_name
                ).first()
                fixture.pitch_id = selected_pitch.id if selected_pitch else None
            else:
                fixture.pitch_id = None

            fixture.kickoff_time_text = request.form.get('kickoff_time')

            session.commit()
            flash('Fixture updated successfully!', 'success')
            return redirect(url_for('tasks.view_task', task_id=task_id))

        # GET request - show edit form
        pitches = session.query(Pitch).filter_by(organization_id=org.id).all()
        return render_template('edit_fixture.html',
            task=task,
            fixture=fixture,
            pitches=pitches
        )

    except Exception as e:
        session.rollback()
        flash(f'Error updating fixture: {str(e)}', 'error')
        return redirect(url_for('tasks.view_task', task_id=task_id))
    finally:
        session.close()

@tasks_bp.route('/generate_email/<task_id>')
@login_required
def generate_email_route(task_id):
    """Generate email for a task"""
    session = db_manager.get_session()
    try:
        org = get_user_organization()
        if not org:
            flash('No organization found.', 'error')
            return redirect(url_for('auth.logout'))
        
        # Get task with all related data
        task = session.query(Task).filter_by(
            id=task_id,
            organization_id=org.id
        ).first()
        
        if not task:
            flash('Task not found.', 'error')
            return redirect(url_for('dashboard.dashboard_view'))
        
        fixture = task.fixture
        team = fixture.team

        # Get pitch information from the relationship
        pitch = fixture.pitch

        # Debug pitch information
        pitch_debug = {
            'pitch_name': fixture.pitch.name if fixture.pitch else 'TBC',
            'pitch_address': fixture.pitch.address if fixture.pitch else 'TBC',
            'pitch_parking': fixture.pitch.parking_info if fixture.pitch else 'TBC',
            'pitch_toilets': fixture.pitch.toilet_info if fixture.pitch else 'TBC',
            'pitch_opening_notes': fixture.pitch.opening_notes if fixture.pitch else 'TBC',
        } if fixture.pitch else {}
        print(f"DEBUG: Pitch info for email: {pitch_debug}")

        # Get email template
        email_template = session.query(EmailTemplate).filter_by(
            organization_id=org.id,
            template_type='default',
            is_active=True
        ).first()

        # Debug fixture data
        debug_fixture_data = {
            'fixture_id': fixture.id,
            'kickoff_time_text': fixture.kickoff_time_text,
            'match_format': fixture.match_format,
            'fixture_length': fixture.fixture_length,
        }
        print(f"DEBUG: Fixture data for email generation: {debug_fixture_data}")

        # Get team coach/manager for this team
        team_coach = session.query(TeamCoach).filter_by(
            organization_id=org.id,
            team_id=team.id
        ).first()

        # Get team contact information
        team_contact = session.query(TeamContact).filter_by(
            organization_id=org.id,
            team_name=team.name
        ).first()

        # Get all opponent contacts once for reuse
        all_team_contacts = session.query(TeamContact).filter_by(
            organization_id=org.id
        ).all()

        template_manager = TemplateManager(
            email_template.content if email_template else None,
            pitch,
            team
        )

        # Use SmartEmailGenerator to generate the email
        email_generator = SmartEmailGenerator(user_manager=template_manager)

        # Create task data for email generation
        task_data = {
            'team': team.name,
            'opposition': fixture.opposition_name or '',
            'home_away': fixture.home_away,
            'pitch': pitch.name if pitch else '',
            'kickoff_time': fixture.kickoff_time_text or '',
            'format': fixture.match_format or '',
            'referee': fixture.referee_info or '',
            'instructions': fixture.instructions or '',
            # Manager/Contact information
            'manager_name': team_coach.coach_name if team_coach else (team_contact.contact_name if team_contact else ''),
            'manager_email': team_coach.email if team_coach else (team_contact.email if team_contact else ''),
            'manager_phone': team_coach.phone if team_coach else (team_contact.phone if team_contact else ''),
            'manager_contact': team_coach.email if team_coach else (team_contact.email if team_contact else '')  # Keep for backward compatibility
        }
        
        email_content = email_generator.generate_email(task_data)
        subject = email_generator.generate_subject_line(task_data)

        # Get available pitches for venue selection
        available_pitches = session.query(Pitch).filter_by(
            organization_id=org.id
        ).order_by(Pitch.name).all()

        # Get coaches for THIS specific team only
        current_team_coaches = session.query(TeamCoach).filter_by(
            organization_id=org.id,
            team_id=team.id
        ).all()

        # Helper to normalize contact names
        def _normalize_contact_name(value: str) -> str:
            if not value:
                return ''
            return re.sub(r'[^a-z0-9 ]+', ' ', value.lower()).strip()

        def _find_opposition_contact(opposition_name: str):
            if not opposition_name:
                return None

            normalized_target = _normalize_contact_name(opposition_name)
            if not normalized_target:
                return None

            target_tokens = set(normalized_target.split())
            best_match = None
            best_score = 0

            for contact in all_team_contacts:
                contact_normalized = _normalize_contact_name(contact.team_name)
                if not contact_normalized:
                    continue

                # Exact normalized match wins immediately
                if contact_normalized == normalized_target:
                    return contact

                # Prefer substring matches (handles age groups and suffixes)
                if (contact_normalized in normalized_target) or (normalized_target in contact_normalized):
                    score = max(len(contact_normalized), len(normalized_target))
                else:
                    contact_tokens = set(contact_normalized.split())
                    score = len(target_tokens & contact_tokens)

                if score > best_score:
                    best_match = contact
                    best_score = score

            return best_match

        # Get contact for the current opposition team using best-match logic
        opposition_contact = None
        if fixture.opposition_name and str(fixture.opposition_name).strip().lower() != 'nan':
            opposition_contact = _find_opposition_contact(fixture.opposition_name.strip())

        # Format contacts for template use (serializable)
        coaches_list = []
        for coach in current_team_coaches:
            coaches_list.append({
                'coach_name': coach.coach_name,
                'email': coach.email,
                'phone': coach.phone,
                'role': coach.role
            })

        # Create serializable contacts dict for JavaScript
        contacts_dict = {
            contact.team_name: {
                'contact_name': contact.contact_name,
                'email': contact.email,
                'phone': contact.phone,
                'notes': contact.notes
            } for contact in all_team_contacts
        }

        return render_template('email_preview.html',
            task=task,
            email_content=email_content,
            subject=subject,
            user_name=current_user.name,
            home_coach=team_coach,
            home_contact=team_contact,
            opposition_name=fixture.opposition_name,
            available_pitches=available_pitches,
            team_coaches=coaches_list,
            opposition_contact=opposition_contact,
            team_contacts=contacts_dict
        )
        
    finally:
        session.close()

@tasks_bp.route('/update_email_preview/<task_id>', methods=['POST'])
@login_required
def update_email_preview(task_id):
    """Update email preview with new match information"""
    try:
        org = get_user_organization()
        if not org:
            return jsonify({'success': False, 'error': 'No organization found'})

        data = request.get_json()
        session = db_manager.get_session()

        try:
            # Get task
            task = session.query(Task).filter_by(
                id=task_id,
                organization_id=org.id
            ).first()

            if not task:
                return jsonify({'success': False, 'error': 'Task not found'})

            fixture = task.fixture
            team = fixture.team

            # Get pitch information if venue selected
            pitch = None
            if data.get('pitch'):
                pitch = session.query(Pitch).filter_by(
                    organization_id=org.id,
                    name=data['pitch']
                ).first()

            # Get email template
            email_template = session.query(EmailTemplate).filter_by(
                organization_id=org.id
            ).first()

            # Get team coach/manager for this team
            team_coach = session.query(TeamCoach).filter_by(
                organization_id=org.id,
                team_id=team.id
            ).first()

            # Get team contact information
            team_contact = session.query(TeamContact).filter_by(
                organization_id=org.id,
                team_name=team.name
            ).first()

            template_manager = TemplateManager(
                email_template.content if email_template else None,
                pitch,
                team
            )
            email_generator = SmartEmailGenerator(user_manager=template_manager)

            # Create task data with updated information
            # Always use the team name from the database, not the form data
            task_data = {
                'team': team.name if team else 'Team',  # Always use database team name
                'opposition': data.get('opposition', fixture.opposition_name if fixture else ''),
                'pitch': data.get('pitch', fixture.pitch.name if (fixture and fixture.pitch) else ''),
                'kickoff_time': data.get('kickoff_time', fixture.kickoff_time_text or ''),
                'format': data.get('match_format', ''),
                'fixture_length': data.get('match_format', ''),
                'instructions': data.get('additional_instructions', ''),
                'manager_name': team_coach.coach_name if team_coach else (team_contact.contact_name if team_contact else ''),
                'manager_email': team_coach.email if team_coach else (team_contact.email if team_contact else ''),
                'manager_phone': team_coach.phone if team_coach else (team_contact.phone if team_contact else ''),
                'manager_contact': team_coach.email if team_coach else (team_contact.email if team_contact else '')
            }

            # Generate updated email
            email_content = email_generator.generate_email(task_data)
            subject = email_generator.generate_subject_line(task_data)

            return jsonify({
                'success': True,
                'email_content': email_content,
                'subject': subject
            })

        finally:
            session.close()

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@tasks_bp.route('/regenerate_email/<task_id>')
@login_required
def regenerate_email(task_id):
    """Regenerate email for a task with updated fixture information"""
    session = db_manager.get_session()
    try:
        org = get_user_organization()
        if not org:
            flash('No organization found.', 'error')
            return redirect(url_for('auth.logout'))

        # Get task and fixture
        task = session.query(Task).filter_by(
            id=task_id,
            organization_id=org.id
        ).first()

        if not task:
            flash('Task not found.', 'error')
            return redirect(url_for('tasks.view_tasks'))

        # Regenerate the email with current fixture data
        return redirect(url_for('tasks.generate_email_route', task_id=task_id))

    finally:
        session.close()

@tasks_bp.route('/cleanup_old_tasks', methods=['POST'])
@login_required
def cleanup_old_tasks():
    """Archive completed tasks older than X days"""
    session = db_manager.get_session()
    try:
        org = get_user_organization()
        if not org:
            flash('No organization found.', 'error')
            return redirect(url_for('auth.logout'))
            
        days = int(request.form.get('days', 30))
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Find old completed tasks
        old_tasks = session.query(Task).filter(
            Task.organization_id == org.id,
            Task.status.in_(['completed', 'cancelled']),
            Task.is_archived == False,
            Task.updated_at < cutoff_date
        ).all()
        
        count = 0
        for task in old_tasks:
            task.is_archived = True
            task.archived_at = datetime.utcnow()
            count += 1
            
        session.commit()
        
        if count > 0:
            flash(f'Successfully archived {count} old tasks.', 'success')
        else:
            flash('No old tasks found to clean up.', 'info')
            
        return redirect(url_for('dashboard.dashboard_view'))
        
    except Exception as e:
        session.rollback()
        flash(f'Error cleaning up tasks: {str(e)}', 'error')
        return redirect(url_for('dashboard.dashboard_view'))
    finally:
        session.close()

@tasks_bp.route('/away-match-response/<path:team_name>')
@login_required
def away_match_response_page(team_name):
    """Page to display away match response with copy functionality"""
    session = db_manager.get_session()
    try:
        org = get_user_organization()
        if not org:
            flash('No organization found.', 'error')
            return redirect(url_for('dashboard.dashboard_view'))
        
        # Decode URL-encoded team name
        team_name = urllib.parse.unquote(team_name)
        
        # Get team
        team_obj = session.query(Team).filter_by(organization_id=org.id, name=team_name).first()
        if not team_obj:
            flash(f'Team "{team_name}" not found.', 'error')
            return redirect(url_for('dashboard.dashboard_view'))
        
        # Get team coach
        team_coach = session.query(TeamCoach).filter_by(
            organization_id=org.id,
            team_id=team_obj.id
        ).first()
        
        # Generate response text using the same logic
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
        
        # Generate the response template
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
        
        response_text = "\n".join(response_parts)
        
        return render_template('away_match_response.html',
                             team_name=team_name,
                             response_text=response_text,
                             manager_name=manager_name,
                             manager_email=manager_email,
                             manager_phone=manager_phone,
                             kit_info=kit_info)
    finally:
        session.close()
