from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
import os
import pandas as pd
from werkzeug.utils import secure_filename
from datetime import datetime
import json

from fixture_parser import FixtureParser
from managed_teams import get_managed_teams
from user_manager import UserManager
from email_template import generate_email, generate_subject_line
from smart_email_generator import SmartEmailGenerator
from task_manager import TaskManager, TaskType, TaskStatus
from text_fixture_parser import TextFixtureParser

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'withdean-youth-fc-fixtures-2024-dev')
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Create uploads directory
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize managers
task_manager = TaskManager()
user_manager = UserManager()

ALLOWED_EXTENSIONS = {'csv', 'xlsx', 'xls'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def dashboard():
    """Main dashboard showing task summary"""
    # Filter tasks to show only my teams
    my_team_tasks = [t for t in task_manager.tasks.values() if user_manager.is_managed_team(t.team)]
    
    # Create summary for my teams only
    summary = {
        'total': len(my_team_tasks),
        'pending': len([t for t in my_team_tasks if t.status.value == 'pending']),
        'waiting': len([t for t in my_team_tasks if t.status.value == 'waiting']),
        'in_progress': len([t for t in my_team_tasks if t.status.value == 'in_progress']),
        'completed': len([t for t in my_team_tasks if t.status.value == 'completed']),
        'home_games': len([t for t in my_team_tasks if t.task_type.value == 'home_email']),
        'away_games': len([t for t in my_team_tasks if t.task_type.value == 'away_forward'])
    }
    
    # Get recent tasks for display (my teams only)
    pending_tasks = [t for t in my_team_tasks if t.status.value == 'pending'][:5]
    waiting_tasks = [t for t in my_team_tasks if t.status.value == 'waiting'][:5]
    completed_tasks = [t for t in my_team_tasks if t.status.value == 'completed'][:5]
    
    # Sort by creation date (newest first)
    pending_tasks.sort(key=lambda x: x.created_date, reverse=True)
    waiting_tasks.sort(key=lambda x: x.created_date, reverse=True)
    completed_tasks.sort(key=lambda x: x.completed_date or x.created_date, reverse=True)
    
    return render_template('dashboard.html', 
                         summary=summary,
                         pending_tasks=pending_tasks,
                         waiting_tasks=waiting_tasks,
                         completed_tasks=completed_tasks,
                         my_teams_count=len(user_manager.get_managed_teams()),
                         user_name=user_manager.get_user_name(),
                         total_tasks=len(task_manager.tasks))

@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    """Handle CSV file upload and fixture import"""
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file selected', 'error')
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{timestamp}_{filename}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            # Process the uploaded file
            try:
                parser = FixtureParser()
                managed_teams = get_managed_teams()
                
                df = parser.read_spreadsheet(filepath)
                if df.empty:
                    flash('No data found in the uploaded file', 'error')
                    return redirect(url_for('upload_file'))
                
                # Filter for managed teams (including "Mark Monahan" filter)
                filtered_df = parser.filter_teams(df, managed_teams, manager_name="Mark Monahan")
                
                if filtered_df.empty:
                    flash('No fixtures found for your managed teams', 'warning')
                    return redirect(url_for('upload_file'))
                
                fixtures = parser.get_fixture_data(filtered_df)
                
                # Create/update tasks
                new_tasks = 0
                updated_tasks = 0
                
                for fixture in fixtures:
                    task = task_manager.create_task_from_fixture(fixture)
                    
                    if task.id in task_manager.tasks:
                        updated_tasks += 1
                    else:
                        new_tasks += 1
                    
                    task_manager.add_or_update_task(task)
                
                flash(f'Import successful! {new_tasks} new tasks, {updated_tasks} updated tasks', 'success')
                
                # Clean up uploaded file
                os.remove(filepath)
                
                return redirect(url_for('dashboard'))
                
            except Exception as e:
                flash(f'Error processing file: {str(e)}', 'error')
                if os.path.exists(filepath):
                    os.remove(filepath)
                return redirect(url_for('upload_file'))
        else:
            flash('Invalid file type. Please upload CSV or Excel files only.', 'error')
    
    return render_template('upload.html')

@app.route('/tasks')
def view_tasks():
    """View and manage all tasks"""
    task_type = request.args.get('type', 'all')
    status_filter = request.args.get('status', 'all')
    show_all_teams = request.args.get('show_all', 'false').lower() == 'true'
    
    all_tasks = list(task_manager.tasks.values())
    
    # Apply team filter first (show only my teams by default)
    if not show_all_teams:
        all_tasks = [t for t in all_tasks if user_manager.is_managed_team(t.team)]
    
    # Apply other filters
    filtered_tasks = all_tasks
    
    if task_type != 'all':
        filtered_tasks = [t for t in filtered_tasks if t.task_type.value == task_type]
    
    if status_filter != 'all':
        filtered_tasks = [t for t in filtered_tasks if t.status.value == status_filter]
    
    # Sort by creation date (newest first)
    filtered_tasks.sort(key=lambda x: x.created_date, reverse=True)
    
    # Get summary for my teams only
    my_team_tasks = [t for t in task_manager.tasks.values() if user_manager.is_managed_team(t.team)]
    my_summary = {
        'total': len(my_team_tasks),
        'pending': len([t for t in my_team_tasks if t.status.value == 'pending']),
        'waiting': len([t for t in my_team_tasks if t.status.value == 'waiting']),
        'in_progress': len([t for t in my_team_tasks if t.status.value == 'in_progress']),
        'completed': len([t for t in my_team_tasks if t.status.value == 'completed']),
    }
    
    return render_template('tasks.html', 
                         tasks=filtered_tasks,
                         current_type=task_type,
                         current_status=status_filter,
                         show_all_teams=show_all_teams,
                         my_summary=my_summary,
                         total_tasks=len(task_manager.tasks))

@app.route('/task/<task_id>')
def task_detail(task_id):
    """View detailed information about a specific task"""
    task = task_manager.tasks.get(task_id)
    if not task:
        flash('Task not found', 'error')
        return redirect(url_for('view_tasks'))
    
    return render_template('task_detail.html', task=task)

@app.route('/generate_email/<task_id>')
def generate_task_email(task_id):
    """Generate email for a specific home game task"""
    task = task_manager.tasks.get(task_id)
    if not task:
        flash('Task not found', 'error')
        return redirect(url_for('view_tasks'))
    
    if task.task_type != TaskType.HOME_EMAIL:
        flash('Email generation is only available for home games', 'error')
        return redirect(url_for('task_detail', task_id=task_id))
    
    # Convert task back to fixture format for email generation
    fixture_data = {
        'team': task.team,
        'opposition': task.opposition if str(task.opposition) != 'nan' else 'TBC',
        'home_away': task.home_away,
        'pitch': task.pitch if str(task.pitch) != 'nan' else 'TBC',
        'kickoff_time': task.kickoff_time if str(task.kickoff_time) != 'nan' else 'TBC',
        'league': task.league or '',
        'home_manager': task.home_manager or '',
        'fixtures_sec': task.fixtures_sec or '',
        'instructions': task.instructions or '',
        'format': task.format or '',
        'each_way': task.each_way or '',
        'fixture_length': task.fixture_length or '',
        'referee': task.referee or '',
        'manager_mobile': task.manager_mobile or '',
        'contact_1': task.contact_1 or '',
        'contact_2': task.contact_2 or '',
        'contact_3': task.contact_3 or '',
        'contact_5': task.contact_5 or ''
    }
    
    # Use smart email generator for better spreadsheet data integration
    smart_generator = SmartEmailGenerator(user_manager)
    email_content = smart_generator.generate_email(fixture_data)
    subject_line = smart_generator.generate_subject_line(fixture_data)
    
    return render_template('email_preview.html', 
                         task=task,
                         subject=subject_line,
                         email_content=email_content)

@app.route('/mark_completed/<task_id>', methods=['POST'])
def mark_task_completed(task_id):
    """Mark a task as completed"""
    task = task_manager.tasks.get(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    
    notes = request.json.get('notes', '') if request.is_json else request.form.get('notes', '')
    
    success = task_manager.mark_completed(task_id, notes)
    
    if success:
        if request.is_json:
            return jsonify({'success': True, 'message': 'Task marked as completed'})
        else:
            flash('Task marked as completed!', 'success')
            return redirect(url_for('task_detail', task_id=task_id))
    else:
        if request.is_json:
            return jsonify({'error': 'Failed to mark task as completed'}), 500
        else:
            flash('Error marking task as completed', 'error')
            return redirect(url_for('task_detail', task_id=task_id))

@app.route('/mark_in_progress/<task_id>', methods=['POST'])
def mark_task_in_progress(task_id):
    """Mark a task as in progress"""
    task = task_manager.tasks.get(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    
    success = task_manager.mark_in_progress(task_id)
    
    if success:
        if request.is_json:
            return jsonify({'success': True, 'message': 'Task marked as in progress'})
        else:
            flash('Task marked as in progress!', 'success')
            return redirect(url_for('task_detail', task_id=task_id))
    else:
        if request.is_json:
            return jsonify({'error': 'Failed to mark task as in progress'}), 500
        else:
            flash('Error marking task as in progress', 'error')
            return redirect(url_for('task_detail', task_id=task_id))

@app.route('/api/summary')
def api_summary():
    """API endpoint for dashboard summary data"""
    summary = task_manager.get_task_summary()
    return jsonify(summary)

@app.route('/cleanup', methods=['POST'])
def cleanup_old_tasks():
    """Clean up old completed tasks"""
    days = int(request.form.get('days', 30))
    removed = task_manager.clear_old_completed_tasks(days)
    flash(f'Removed {removed} old completed tasks (older than {days} days)', 'success')
    return redirect(url_for('dashboard'))

@app.route('/settings')
def settings():
    """Settings page for user and pitch management"""
    all_teams = get_managed_teams()  # Get all possible teams from fixture data
    
    return render_template('settings.html',
                         user_info=user_manager.settings.get('user', {}),
                         managed_teams=user_manager.get_managed_teams(),
                         pitches=user_manager.get_all_pitches(),
                         preferences=user_manager.get_preferences(),
                         all_teams=all_teams)

@app.route('/settings/user', methods=['POST'])
def update_user():
    """Update user information"""
    name = request.form.get('name')
    email = request.form.get('email')
    role = request.form.get('role')
    
    user_manager.update_user_info(name=name, email=email, role=role)
    flash('User information updated successfully!', 'success')
    return redirect(url_for('settings'))

@app.route('/settings/teams', methods=['POST'])
def update_teams():
    """Update managed teams"""
    selected_teams = request.form.getlist('teams')
    user_manager.set_managed_teams(selected_teams)
    flash(f'Team selection updated! Now managing {len(selected_teams)} teams.', 'success')
    return redirect(url_for('settings'))

@app.route('/settings/pitch', methods=['POST'])
def add_or_update_pitch():
    """Add or update pitch configuration"""
    pitch_config = {
        'name': request.form.get('name'),
        'address': request.form.get('address', ''),
        'parking': request.form.get('parking', ''),
        'toilets': request.form.get('toilets', ''),
        'special_instructions': request.form.get('special_instructions', ''),
        'opening_notes': request.form.get('opening_notes', ''),
        'warm_up_notes': request.form.get('warm_up_notes', '')
    }
    
    user_manager.add_or_update_pitch(pitch_config)
    flash(f'Pitch configuration for "{pitch_config["name"]}" saved successfully!', 'success')
    return redirect(url_for('settings'))

@app.route('/settings/pitch/<pitch_name>')
def get_pitch_config(pitch_name):
    """Get pitch configuration as JSON"""
    config = user_manager.get_pitch_config(pitch_name)
    return jsonify(config)

@app.route('/settings/pitch/<pitch_name>', methods=['DELETE'])
def delete_pitch(pitch_name):
    """Delete pitch configuration"""
    user_manager.delete_pitch(pitch_name)
    return jsonify({'success': True, 'message': f'Pitch "{pitch_name}" deleted successfully'})

@app.route('/settings/preferences', methods=['POST'])
def update_preferences():
    """Update email preferences"""
    preferences = {
        'default_referee_note': request.form.get('default_referee_note', ''),
        'default_colours': request.form.get('default_colours', ''),
        'email_signature': request.form.get('email_signature', ''),
        'default_day': request.form.get('default_day', 'Sunday')
    }
    
    user_manager.update_preferences(preferences)
    flash('Email preferences updated successfully!', 'success')
    return redirect(url_for('settings'))

@app.route('/add_fixture', methods=['GET', 'POST'])
def add_fixture():
    """Add a manual fixture entry"""
    if request.method == 'POST':
        # Create fixture data from form
        fixture_data = {
            'team': request.form.get('team'),
            'opposition': request.form.get('opposition'),
            'home_away': request.form.get('home_away'),
            'pitch': request.form.get('pitch'),
            'kickoff_time': request.form.get('kickoff_time'),
            'league': request.form.get('league'),
            'home_manager': request.form.get('home_manager'),
            'fixtures_sec': request.form.get('fixtures_sec'),
            'instructions': request.form.get('instructions'),
            'format': request.form.get('format'),
            'each_way': request.form.get('each_way'),
            'fixture_length': request.form.get('fixture_length'),
            'referee': request.form.get('referee'),
            'manager_mobile': request.form.get('manager_mobile'),
            'contact_1': request.form.get('contact_1'),
            'contact_2': request.form.get('contact_2'),
            'contact_3': request.form.get('contact_3'),
            'contact_5': request.form.get('contact_5')
        }
        
        # Create and add task
        try:
            task = task_manager.create_task_from_fixture(fixture_data)
            task_manager.add_or_update_task(task)
            flash(f'Fixture added successfully: {task.team} vs {task.opposition}', 'success')
            return redirect(url_for('view_tasks'))
        except Exception as e:
            flash(f'Error adding fixture: {str(e)}', 'error')
    
    # Get managed teams for dropdown
    managed_teams = user_manager.get_managed_teams()
    
    return render_template('add_fixture.html', managed_teams=managed_teams)

@app.route('/parse_fixture', methods=['GET', 'POST'])
def parse_fixture():
    """Parse fixture information from pasted text"""
    if request.method == 'POST':
        pasted_text = request.form.get('pasted_text', '').strip()
        
        if not pasted_text:
            flash('No text provided to parse', 'error')
            return redirect(url_for('parse_fixture'))
        
        # Get managed teams for parsing
        managed_teams = user_manager.get_managed_teams()
        parser = TextFixtureParser(managed_teams)
        
        # Parse the text
        parsed_data = parser.parse_fa_fixture_text(pasted_text)
        validation_result = parser.validate_parsed_data(parsed_data)
        
        if not validation_result['valid']:
            flash('Could not parse fixture data. Please check the text and try again.', 'error')
            for warning in validation_result['warnings']:
                flash(warning, 'warning')
            return render_template('parse_fixture.html', 
                                 pasted_text=pasted_text, 
                                 managed_teams=managed_teams)
        
        # Show preview for confirmation
        return render_template('parse_fixture.html', 
                             pasted_text=pasted_text,
                             parsed_data=validation_result['data'],
                             validation=validation_result,
                             managed_teams=managed_teams)
    
    # GET request - show the paste form
    managed_teams = user_manager.get_managed_teams()
    return render_template('parse_fixture.html', managed_teams=managed_teams)

@app.route('/confirm_parsed_fixture', methods=['POST'])
def confirm_parsed_fixture():
    """Confirm and save a parsed fixture"""
    # Get the data from the form (either parsed or manually edited)
    fixture_data = {
        'team': request.form.get('team'),
        'opposition': request.form.get('opposition'),
        'home_away': request.form.get('home_away'),
        'pitch': request.form.get('pitch'),
        'kickoff_time': request.form.get('kickoff_time'),
        'league': request.form.get('league'),
        'home_manager': request.form.get('home_manager'),
        'fixtures_sec': request.form.get('fixtures_sec'),
        'instructions': request.form.get('instructions'),
        'format': request.form.get('format'),
        'each_way': request.form.get('each_way'),
        'fixture_length': request.form.get('fixture_length'),
        'referee': request.form.get('referee'),
        'manager_mobile': request.form.get('manager_mobile'),
        'contact_1': request.form.get('contact_1'),
        'contact_2': request.form.get('contact_2'),
        'contact_3': request.form.get('contact_3'),
        'contact_5': request.form.get('contact_5')
    }
    
    # Create and add task
    try:
        task = task_manager.create_task_from_fixture(fixture_data)
        task_manager.add_or_update_task(task)
        flash(f'Fixture added successfully: {task.team} vs {task.opposition}', 'success')
        return redirect(url_for('view_tasks'))
    except Exception as e:
        flash(f'Error adding fixture: {str(e)}', 'error')
        return redirect(url_for('parse_fixture'))

@app.route('/bulk_complete', methods=['POST'])
def bulk_complete_tasks():
    """Mark multiple tasks as completed"""
    task_ids = request.json.get('task_ids', [])
    notes = request.json.get('notes', '')
    
    if not task_ids:
        return jsonify({'error': 'No tasks selected'}), 400
    
    completed_count = 0
    for task_id in task_ids:
        if task_manager.mark_completed(task_id, notes):
            completed_count += 1
    
    return jsonify({
        'success': True, 
        'message': f'Marked {completed_count} tasks as completed',
        'completed_count': completed_count
    })

@app.route('/delete_task/<task_id>', methods=['DELETE'])
def delete_task(task_id):
    """Delete a specific task"""
    if task_id in task_manager.tasks:
        del task_manager.tasks[task_id]
        task_manager.save_tasks()
        return jsonify({'success': True, 'message': 'Task deleted successfully'})
    else:
        return jsonify({'error': 'Task not found'}), 404

@app.route('/bulk_delete', methods=['POST'])
def bulk_delete_tasks():
    """Delete multiple tasks"""
    task_ids = request.json.get('task_ids', [])
    
    if not task_ids:
        return jsonify({'error': 'No tasks selected'}), 400
    
    deleted_count = 0
    for task_id in task_ids:
        if task_id in task_manager.tasks:
            del task_manager.tasks[task_id]
            deleted_count += 1
    
    if deleted_count > 0:
        task_manager.save_tasks()
    
    return jsonify({
        'success': True, 
        'message': f'Deleted {deleted_count} tasks',
        'deleted_count': deleted_count
    })

@app.errorhandler(413)
def too_large(e):
    flash('File is too large. Maximum size is 16MB.', 'error')
    return redirect(url_for('upload_file'))

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 8080))
    debug_mode = os.environ.get('FLASK_ENV') == 'development'
    app.run(debug=debug_mode, host='0.0.0.0', port=port)