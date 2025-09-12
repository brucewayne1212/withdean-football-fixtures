from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory, session
import os
import pandas as pd
from werkzeug.utils import secure_filename
from datetime import datetime
import json
import tempfile
import pickle
import uuid
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# CRITICAL: Allow OAuth2 over HTTP for local development - MUST be set before importing OAuth libraries
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'

# Authentication imports
from flask_login import LoginManager, login_required, logout_user, current_user, login_user
from flask_dance.contrib.google import make_google_blueprint, google
from flask_dance.consumer import oauth_authorized

# Local imports
from fixture_parser import FixtureParser
from managed_teams import get_managed_teams
from user_manager import UserManager
from email_template import generate_email, generate_subject_line
from smart_email_generator import SmartEmailGenerator
from task_manager import TaskManager, TaskType, TaskStatus
from text_fixture_parser import TextFixtureParser
from auth_manager import AuthManager, User
from contact_parser import ContactParser

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'withdean-youth-fc-fixtures-2024-dev')
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Google OAuth Configuration
app.config['GOOGLE_OAUTH_CLIENT_ID'] = os.environ.get('GOOGLE_OAUTH_CLIENT_ID')
app.config['GOOGLE_OAUTH_CLIENT_SECRET'] = os.environ.get('GOOGLE_OAUTH_CLIENT_SECRET')

# Create uploads directory
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Create user_data directory for multi-user storage
os.makedirs('user_data', exist_ok=True)

# Create temporary directory for bulk contact storage
TEMP_DIR = os.path.join(tempfile.gettempdir(), 'bulk_contacts')
os.makedirs(TEMP_DIR, exist_ok=True)

def store_bulk_contacts(user_id, contacts):
    """Store bulk contacts in a temporary file"""
    contact_data = []
    for contact in contacts:
        contact_dict = {
            'team_name': contact.team_name,
            'contact_name': contact.contact_name,
            'email': contact.email,
            'phone': contact.phone,
            'notes': contact.notes,
            'original_text': contact.original_text
        }
        contact_data.append(contact_dict)
    
    # Generate unique filename for this user and session
    bulk_id = str(uuid.uuid4())
    filename = f"{user_id}_{bulk_id}.pkl"
    filepath = os.path.join(TEMP_DIR, filename)
    
    with open(filepath, 'wb') as f:
        pickle.dump(contact_data, f)
    
    return bulk_id

def get_bulk_contacts(user_id, bulk_id):
    """Retrieve bulk contacts from temporary file"""
    filename = f"{user_id}_{bulk_id}.pkl"
    filepath = os.path.join(TEMP_DIR, filename)
    
    try:
        with open(filepath, 'rb') as f:
            return pickle.load(f)
    except FileNotFoundError:
        return None

def cleanup_bulk_contacts(user_id, bulk_id):
    """Remove temporary bulk contact file"""
    filename = f"{user_id}_{bulk_id}.pkl"
    filepath = os.path.join(TEMP_DIR, filename)
    
    try:
        os.remove(filepath)
    except FileNotFoundError:
        pass

def store_bulk_coaches(user_id, coaches):
    """Store bulk coaches in a temporary file"""
    coach_data = []
    for coach in coaches:
        if coach.contact_type == "coach":  # Only store coaches
            coach_dict = {
                'name': coach.contact_name,
                'email': coach.email,
                'phone': coach.phone,
                'role': coach.role,
                'team': coach.team_name,
                'original_text': coach.original_text
            }
            coach_data.append(coach_dict)
    
    # Generate unique filename for this user and session
    bulk_id = str(uuid.uuid4())
    filename = f"coaches_{user_id}_{bulk_id}.pkl"
    filepath = os.path.join(TEMP_DIR, filename)
    
    with open(filepath, 'wb') as f:
        pickle.dump(coach_data, f)
    
    return bulk_id

def get_bulk_coaches(user_id, bulk_id):
    """Retrieve bulk coaches from temporary file"""
    filename = f"coaches_{user_id}_{bulk_id}.pkl"
    filepath = os.path.join(TEMP_DIR, filename)
    
    try:
        with open(filepath, 'rb') as f:
            return pickle.load(f)
    except FileNotFoundError:
        return None

def cleanup_bulk_coaches(user_id, bulk_id):
    """Remove temporary bulk coach file"""
    filename = f"coaches_{user_id}_{bulk_id}.pkl"
    filepath = os.path.join(TEMP_DIR, filename)
    
    try:
        os.remove(filepath)
    except FileNotFoundError:
        pass

# Initialize authentication
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please sign in with Google to access this page.'
login_manager.login_message_category = 'info'

# Google OAuth Blueprint
google_bp = make_google_blueprint(
    client_id=os.environ.get('GOOGLE_OAUTH_CLIENT_ID'),
    client_secret=os.environ.get('GOOGLE_OAUTH_CLIENT_SECRET'),
    scope=['openid', 'email', 'https://www.googleapis.com/auth/userinfo.email', 'https://www.googleapis.com/auth/userinfo.profile']
)
app.register_blueprint(google_bp, url_prefix='/login')

# Initialize managers
auth_manager = AuthManager()

@login_manager.user_loader
def load_user(user_id):
    return auth_manager.get_user(user_id)

ALLOWED_EXTENSIONS = {'csv', 'xlsx', 'xls'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_user_managers():
    """Get user-specific managers for the current user"""
    if current_user.is_authenticated:
        user_id = current_user.id
        task_manager = TaskManager(user_id=user_id)
        user_manager = UserManager(user_id=user_id)
        return task_manager, user_manager
    else:
        # Fallback to legacy single-user mode for testing
        return TaskManager(), UserManager()

def get_user_upload_folder():
    """Get user-specific upload folder"""
    if current_user.is_authenticated:
        user_folder = auth_manager.get_user_uploads_path(current_user.id)
        os.makedirs(user_folder, exist_ok=True)
        return user_folder
    else:
        return app.config['UPLOAD_FOLDER']

# Authentication Routes
@app.route('/login')
def login():
    """Display login page"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    """Logout user"""
    logout_user()
    flash('You have been logged out successfully.', 'success')
    return redirect(url_for('login'))

@oauth_authorized.connect_via(google_bp)
def google_logged_in(blueprint, token):
    """Handle successful Google OAuth login"""
    if not token:
        flash('Failed to log in with Google.', 'error')
        return False

    resp = blueprint.session.get('/oauth2/v2/userinfo')
    if not resp.ok:
        flash('Failed to fetch user info from Google.', 'error')
        return False

    info = resp.json()
    
    # Create or update user
    user = auth_manager.create_or_update_user(
        email=info['email'],
        name=info['name'],
        picture=info.get('picture')
    )
    
    # Log in the user
    login_user(user, remember=True)
    flash(f'Welcome, {user.name}!', 'success')
    return False  # Don't redirect automatically, let Flask-Login handle it

@app.route('/')
@login_required
def dashboard():
    """Main dashboard showing task summary"""
    # Get user-specific managers
    task_manager, user_manager = get_user_managers()
    
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
    task_manager, user_manager = get_user_managers()
    
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
    task_manager, user_manager = get_user_managers()
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
    task_manager, user_manager = get_user_managers()
    task = task_manager.tasks.get(task_id)
    if not task:
        flash('Task not found', 'error')
        return redirect(url_for('view_tasks'))
    
    return render_template('task_detail.html', task=task)

@app.route('/generate_email/<task_id>')
def generate_task_email(task_id):
    """Generate email for a specific home game task"""
    task_manager, user_manager = get_user_managers()
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
    
    # Get contact information for teams involved
    teams_to_check = [task.team, task.opposition] if str(task.opposition) != 'nan' else [task.team]
    team_contacts = user_manager.get_contacts_for_teams(teams_to_check)
    
    # Get coach/manager information for internal teams
    internal_teams = [task.team]  # Only get coaches for our own team
    team_coaches = user_manager.get_coaches_for_teams(internal_teams)
    
    return render_template('email_preview.html', 
                         task=task,
                         subject=subject_line,
                         email_content=email_content,
                         team_contacts=team_contacts,
                         team_coaches=team_coaches)

@app.route('/mark_completed/<task_id>', methods=['POST'])
def mark_task_completed(task_id):
    """Mark a task as completed"""
    task_manager, user_manager = get_user_managers()
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
    task_manager, user_manager = get_user_managers()
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
    task_manager, user_manager = get_user_managers()
    all_teams = get_managed_teams()  # Get all possible teams from fixture data
    
    return render_template('settings.html',
                         user_info=user_manager.settings.get('user', {}),
                         managed_teams=user_manager.get_managed_teams(),
                         pitches=user_manager.get_all_pitches(),
                         preferences=user_manager.get_preferences(),
                         team_contacts=user_manager.get_all_contacts(),
                         team_coaches=user_manager.get_all_coaches(),
                         all_teams=all_teams,
                         user_manager=user_manager)

@app.route('/settings/user', methods=['POST'])
def update_user():
    """Update user information"""
    task_manager, user_manager = get_user_managers()
    name = request.form.get('name')
    email = request.form.get('email')
    role = request.form.get('role')
    
    user_manager.update_user_info(name=name, email=email, role=role)
    flash('User information updated successfully!', 'success')
    return redirect(url_for('settings'))

@app.route('/settings/teams', methods=['POST'])
def update_teams():
    """Update managed teams"""
    task_manager, user_manager = get_user_managers()
    selected_teams = request.form.getlist('teams')
    user_manager.set_managed_teams(selected_teams)
    flash(f'Team selection updated! Now managing {len(selected_teams)} teams.', 'success')
    return redirect(url_for('settings'))

@app.route('/settings/pitch', methods=['POST'])
def add_or_update_pitch():
    """Add or update pitch configuration"""
    task_manager, user_manager = get_user_managers()
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
    task_manager, user_manager = get_user_managers()
    config = user_manager.get_pitch_config(pitch_name)
    return jsonify(config)

@app.route('/settings/pitch/<pitch_name>', methods=['DELETE'])
def delete_pitch(pitch_name):
    """Delete pitch configuration"""
    task_manager, user_manager = get_user_managers()
    user_manager.delete_pitch(pitch_name)
    return jsonify({'success': True, 'message': f'Pitch "{pitch_name}" deleted successfully'})

@app.route('/settings/preferences', methods=['POST'])
def update_preferences():
    """Update email preferences"""
    task_manager, user_manager = get_user_managers()
    preferences = {
        'default_referee_note': request.form.get('default_referee_note', ''),
        'default_colours': request.form.get('default_colours', ''),
        'email_signature': request.form.get('email_signature', ''),
        'default_day': request.form.get('default_day', 'Sunday')
    }
    
    user_manager.update_preferences(preferences)
    flash('Email preferences updated successfully!', 'success')
    return redirect(url_for('settings'))

# Contact management routes
@app.route('/settings/contacts', methods=['POST'])
@login_required
def add_or_update_contact():
    """Add or update team contact information"""
    task_manager, user_manager = get_user_managers()
    team_name = request.form.get('team_name')
    contact_info = {
        'contact_name': request.form.get('contact_name', ''),
        'email': request.form.get('email', ''),
        'phone': request.form.get('phone', ''),
        'notes': request.form.get('notes', '')
    }
    
    user_manager.add_or_update_team_contact(team_name, contact_info)
    flash(f'Contact information for {team_name} updated successfully!', 'success')
    return redirect(url_for('settings'))

@app.route('/settings/contacts/<team_name>')
@login_required
def get_team_contact(team_name):
    """Get team contact information as JSON"""
    task_manager, user_manager = get_user_managers()
    contact = user_manager.get_team_contact(team_name)
    if contact:
        return jsonify(contact)
    return jsonify({'error': 'Contact not found'}), 404

@app.route('/settings/contacts/<team_name>', methods=['DELETE'])
@login_required
def delete_team_contact(team_name):
    """Delete team contact information"""
    task_manager, user_manager = get_user_managers()
    user_manager.delete_team_contact(team_name)
    return jsonify({'success': True, 'message': f'Contact for "{team_name}" deleted successfully'})

# Bulk contact upload routes
@app.route('/settings/contacts/bulk', methods=['GET', 'POST'])
@login_required
def bulk_contact_upload():
    """Bulk upload contacts from text, CSV, or Excel"""
    print("Bulk contact upload route called")  # Debug
    
    if request.method == 'POST':
        print("POST request received")  # Debug
        task_manager, user_manager = get_user_managers()
        parser = ContactParser()
        contacts = []
        
        try:
            # Check if it's a file upload or text paste
            if 'contact_file' in request.files and request.files['contact_file'].filename:
                file = request.files['contact_file']
                filename = secure_filename(file.filename)
                file_content = file.read()
                
                print(f"Processing file: {filename}")  # Debug
                
                if filename.lower().endswith(('.csv', '.txt')):
                    contacts = parser.parse_csv_file(file_content)
                elif filename.lower().endswith(('.xlsx', '.xls')):
                    contacts = parser.parse_excel_file(file_content)
                else:
                    flash('Please upload a CSV, TXT, or Excel file', 'error')
                    return redirect(url_for('bulk_contact_upload'))
                    
            elif request.form.get('contact_text', '').strip():
                text = request.form.get('contact_text', '').strip()
                print(f"Processing text input: {len(text)} characters")  # Debug
                contacts = parser.parse_text(text)
                print(f"Parsed {len(contacts)} contacts")  # Debug
            else:
                print("No file or text provided")  # Debug
                flash('Please provide either text or upload a file', 'error')
                return redirect(url_for('bulk_contact_upload'))
            
            if not contacts:
                print("No contacts found after parsing")  # Debug
                flash('No valid contacts found in the provided data. Please check that your data contains email addresses or phone numbers.', 'warning')
                return redirect(url_for('bulk_contact_upload'))
            
            # Store contacts in temporary file
            user_id = current_user.id
            bulk_id = store_bulk_contacts(user_id, contacts)
            
            print(f"Stored {len(contacts)} contacts in temporary file with ID: {bulk_id}")  # Debug
            
            # Redirect to preview with bulk_id parameter
            return redirect(url_for('bulk_contact_preview', bulk_id=bulk_id))
            
        except Exception as e:
            print(f"Error parsing contacts: {str(e)}")  # Debug
            import traceback
            traceback.print_exc()  # Debug
            flash(f'Error parsing contacts: {str(e)}', 'error')
            return redirect(url_for('bulk_contact_upload'))
    
    print("Rendering bulk contact upload template")  # Debug
    return render_template('bulk_contact_upload.html')

@app.route('/settings/contacts/bulk/preview/<bulk_id>', methods=['GET', 'POST'])
@login_required
def bulk_contact_preview(bulk_id):
    """Preview and confirm bulk contact import"""
    print(f"Preview route called with bulk_id: {bulk_id}")  # Debug
    
    # Get contacts from temporary file
    user_id = current_user.id
    bulk_contacts = get_bulk_contacts(user_id, bulk_id)
    
    if bulk_contacts is None:
        print("No bulk_contacts found in temporary file")  # Debug
        flash('No contacts to preview. Please upload contacts first.', 'error')
        return redirect(url_for('bulk_contact_upload'))
    
    print(f"Found {len(bulk_contacts)} contacts in temporary file")  # Debug
    
    if request.method == 'POST':
        task_manager, user_manager = get_user_managers()
        
        # Get the contacts from temporary file
        bulk_contacts = get_bulk_contacts(user_id, bulk_id)
        
        # Process the form data to get user modifications
        imported_count = 0
        skipped_count = 0
        
        for i, contact_data in enumerate(bulk_contacts):
            # Check if this contact should be imported
            if request.form.get(f'import_{i}') == 'on':
                team_name = request.form.get(f'team_name_{i}', '').strip()
                contact_name = request.form.get(f'contact_name_{i}', '').strip()
                email = request.form.get(f'email_{i}', '').strip()
                phone = request.form.get(f'phone_{i}', '').strip()
                notes = request.form.get(f'notes_{i}', '').strip()
                
                if team_name:  # Only import if team name is provided
                    contact_info = {
                        'contact_name': contact_name,
                        'email': email,
                        'phone': phone,
                        'notes': notes
                    }
                    
                    user_manager.add_or_update_team_contact(team_name, contact_info)
                    imported_count += 1
                else:
                    skipped_count += 1
            else:
                skipped_count += 1
        
        # Clean up temporary file
        cleanup_bulk_contacts(user_id, bulk_id)
        
        # Show results
        if imported_count > 0:
            flash(f'Successfully imported {imported_count} contacts! {skipped_count} skipped.', 'success')
        else:
            flash('No contacts were imported.', 'warning')
        
        return redirect(url_for('settings'))
    
    # GET request - show preview
    return render_template('bulk_contact_preview.html', contacts=bulk_contacts)

# Coach/Manager management routes for internal teams
@app.route('/settings/coaches', methods=['POST'])
@login_required
def add_or_update_coach():
    """Add or update a coach/manager for an internal team"""
    task_manager, user_manager = get_user_managers()
    
    team_name = request.form.get('team_name', '').strip()
    coach_name = request.form.get('coach_name', '').strip()
    email = request.form.get('email', '').strip()
    phone = request.form.get('phone', '').strip()
    role = request.form.get('role', 'Coach').strip()
    notes = request.form.get('notes', '').strip()
    
    if team_name:
        coach_info = {
            'coach_name': coach_name,
            'email': email,
            'phone': phone,
            'role': role,
            'notes': notes
        }
        
        user_manager.add_or_update_team_coach(team_name, coach_info)
        
        # Check if this is a fetch/AJAX request (look for Accept header)
        if request.headers.get('Accept', '').find('application/json') != -1:
            return jsonify({'success': True, 'message': f'Coach/Manager updated for {team_name}'})
        else:
            flash(f'Coach/Manager updated for {team_name}', 'success')
            return redirect(url_for('settings'))
    else:
        # Check if this is a fetch/AJAX request
        if request.headers.get('Accept', '').find('application/json') != -1:
            return jsonify({'success': False, 'message': 'Team name is required'})
        else:
            flash('Team name is required', 'error')
            return redirect(url_for('settings'))

@app.route('/settings/coaches/<team_name>')
@login_required
def get_team_coach(team_name):
    """Get coach/manager information for a team (AJAX)"""
    task_manager, user_manager = get_user_managers()
    coach = user_manager.get_team_coach(team_name)
    
    if coach:
        return jsonify(coach)
    else:
        return jsonify({})

@app.route('/settings/coaches/<team_name>', methods=['DELETE'])
@login_required
def delete_team_coach(team_name):
    """Delete coach/manager information for a team"""
    task_manager, user_manager = get_user_managers()
    user_manager.delete_team_coach(team_name)
    return jsonify({'status': 'success'})

@app.route('/settings/coaches/team/<team_name>', methods=['GET'])
@login_required
def get_team_coaches(team_name):
    """Get all coaches for a specific team"""
    task_manager, user_manager = get_user_managers()
    coaches = user_manager.get_team_coaches(team_name)
    
    # Convert to list of dictionaries for JSON response
    coach_list = []
    if coaches:
        for coach in coaches:
            coach_dict = {
                'coach_name': coach.coach_name,
                'role': coach.role or 'Coach',
                'email': coach.email or '',
                'phone': coach.phone or '',
                'notes': coach.notes or ''
            }
            coach_list.append(coach_dict)
    
    return jsonify(coach_list)

@app.route('/settings/coaches/delete', methods=['POST'])
@login_required
def delete_specific_coach():
    """Delete a specific coach from a team"""
    task_manager, user_manager = get_user_managers()
    
    team_name = request.form.get('team_name', '').strip()
    coach_name = request.form.get('coach_name', '').strip()
    
    if not team_name or not coach_name:
        return jsonify({'success': False, 'message': 'Team name and coach name are required'})
    
    # Get current coaches for the team
    current_coaches = user_manager.get_team_coaches(team_name)
    
    if current_coaches:
        # Remove the specified coach
        updated_coaches = [coach for coach in current_coaches if coach.coach_name != coach_name]
        
        # Update the team coaches list
        user_manager.settings['team_coaches'] = user_manager.settings.get('team_coaches', {})
        user_manager.settings['team_coaches'][team_name] = updated_coaches
        user_manager.save_settings()
        
        return jsonify({'success': True, 'message': f'Coach "{coach_name}" removed from "{team_name}"'})
    else:
        return jsonify({'success': False, 'message': 'No coaches found for this team'})

# Email template management routes
@app.route('/settings/email-template', methods=['GET', 'POST'])
@login_required
def manage_email_template():
    """Manage custom email template"""
    task_manager, user_manager = get_user_managers()
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'save':
            template_content = request.form.get('template_content', '').strip()
            if template_content:
                user_manager.update_email_template(template_content)
                flash('Email template updated successfully!', 'success')
            else:
                flash('Template content cannot be empty', 'error')
        
        elif action == 'reset':
            user_manager.reset_email_template()
            flash('Email template reset to default', 'success')
        
        return redirect(url_for('manage_email_template'))
    
    # GET request - show template editor
    template_content = user_manager.get_email_template()
    merge_fields = user_manager.get_available_merge_fields()
    
    return render_template('email_template_editor.html',
                         template_content=template_content,
                         merge_fields=merge_fields)

# Bulk coach upload routes
@app.route('/settings/coaches/bulk', methods=['GET', 'POST'])
@login_required
def bulk_coach_upload():
    """Bulk upload coaches from text, CSV, or Excel"""
    if request.method == 'POST':
        task_manager, user_manager = get_user_managers()
        parser = ContactParser()
        contacts = []
        
        try:
            # Check if it's a file upload or text paste
            if 'coach_file' in request.files and request.files['coach_file'].filename:
                file = request.files['coach_file']
                filename = secure_filename(file.filename)
                file_content = file.read()
                
                if filename.lower().endswith(('.csv', '.txt')):
                    contacts = parser.parse_csv_file(file_content)
                elif filename.lower().endswith(('.xlsx', '.xls')):
                    contacts = parser.parse_excel_file(file_content)
                else:
                    flash('Please upload a CSV, TXT, or Excel file', 'error')
                    return redirect(url_for('bulk_coach_upload'))
                    
            elif request.form.get('coach_text', '').strip():
                text = request.form.get('coach_text', '').strip()
                contacts = parser.parse_text(text)
            else:
                flash('Please provide coach data via file upload or text input', 'error')
                return redirect(url_for('bulk_coach_upload'))
            
            if contacts:
                # Store coaches in temporary file
                user_id = current_user.id
                bulk_id = store_bulk_coaches(user_id, contacts)
                
                flash(f'Successfully parsed {len(contacts)} coaches!', 'success')
                return redirect(url_for('bulk_coach_preview', bulk_id=bulk_id))
            else:
                flash('No coach information found in the provided data', 'warning')
                return redirect(url_for('bulk_coach_upload'))
        
        except Exception as e:
            flash(f'Error parsing coaches: {str(e)}', 'error')
            return redirect(url_for('bulk_coach_upload'))
    
    return render_template('bulk_coach_upload.html', available_teams=get_managed_teams())

@app.route('/settings/coaches/bulk/preview/<bulk_id>', methods=['GET', 'POST'])
@login_required  
def bulk_coach_preview(bulk_id):
    """Preview and confirm bulk coach import"""
    # Get coaches from temporary file
    user_id = current_user.id
    bulk_coaches = get_bulk_coaches(user_id, bulk_id)
    
    if bulk_coaches is None:
        flash('No coaches to preview. Please upload coaches first.', 'error')
        return redirect(url_for('bulk_coach_upload'))
    
    if request.method == 'POST':
        task_manager, user_manager = get_user_managers()
        
        imported_count = 0
        skipped_count = 0
        
        for i, coach_data in enumerate(bulk_coaches):
            # Check if this coach should be imported
            if request.form.get(f'import_{i}') == 'on':
                team_name = request.form.get(f'team_name_{i}', '').strip()
                coach_name = request.form.get(f'coach_name_{i}', '').strip()
                email = request.form.get(f'email_{i}', '').strip()
                phone = request.form.get(f'phone_{i}', '').strip()
                role = request.form.get(f'role_{i}', 'Coach').strip()
                notes = request.form.get(f'notes_{i}', '').strip()
                
                if team_name:  # Only import if team name is provided
                    coach_info = {
                        'coach_name': coach_name,
                        'email': email,
                        'phone': phone,
                        'role': role,
                        'notes': notes
                    }
                    
                    user_manager.add_or_update_team_coach(team_name, coach_info)
                    imported_count += 1
                else:
                    skipped_count += 1
            else:
                skipped_count += 1
        
        # Clean up temporary file
        cleanup_bulk_coaches(user_id, bulk_id)
        
        # Show results
        if imported_count > 0:
            flash(f'Successfully imported {imported_count} coaches! {skipped_count} skipped.', 'success')
        else:
            flash('No coaches were imported.', 'warning')
        
        return redirect(url_for('settings'))
    
    # GET request - show preview
    managed_teams = get_managed_teams()
    # Convert bulk coaches to enumerated list for template
    coaches_with_indices = list(enumerate(bulk_coaches))
    
    return render_template('bulk_coach_preview.html', 
                         coaches=coaches_with_indices, 
                         available_teams=managed_teams,
                         default_team='')

@app.route('/add_fixture', methods=['GET', 'POST'])
def add_fixture():
    """Add a manual fixture entry"""
    task_manager, user_manager = get_user_managers()
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
    task_manager, user_manager = get_user_managers()
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