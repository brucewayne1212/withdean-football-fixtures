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
import re

# Load environment variables from .env file
load_dotenv()

# CRITICAL: Allow OAuth2 over HTTP for local development only - MUST be set before importing OAuth libraries
if os.environ.get('FLASK_ENV') == 'development' or 'localhost' in os.environ.get('SERVER_NAME', ''):
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'

# Authentication imports
from flask_login import LoginManager, login_required, logout_user, current_user, login_user
from flask_dance.contrib.google import make_google_blueprint, google
from flask_dance.consumer import oauth_authorized

# Database imports
from models import (
    DatabaseManager, User, Organization, Team, Pitch, Fixture, Task, 
    TeamContact, TeamCoach, EmailTemplate, UserPreference,
    get_or_create_organization, get_or_create_team
)
from sqlalchemy import and_, or_
from sqlalchemy.orm import sessionmaker

# Local imports (keeping existing parsers and utilities)
from fixture_parser import FixtureParser
from email_template import generate_email, generate_subject_line
from smart_email_generator import SmartEmailGenerator
from text_fixture_parser import TextFixtureParser
from contact_parser import ContactParser

app = Flask(__name__)
# Use a different secret key to force session clearing for database migration
app.secret_key = os.environ.get('SECRET_KEY', 'withdean-youth-fc-database-2024')
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Database configuration
DATABASE_URL = "postgresql://neondb_owner:npg_V1zDyIcxCOv9@ep-falling-shape-abr14uib-pooler.eu-west-2.aws.neon.tech/neondb?sslmode=require"
db_manager = DatabaseManager(DATABASE_URL)

# Configure for HTTPS when deployed (Cloud Run sets X-Forwarded-Proto header)
if os.environ.get('FLASK_ENV') != 'development':
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Google OAuth Configuration
app.config['GOOGLE_OAUTH_CLIENT_ID'] = os.environ.get('GOOGLE_OAUTH_CLIENT_ID')
app.config['GOOGLE_OAUTH_CLIENT_SECRET'] = os.environ.get('GOOGLE_OAUTH_CLIENT_SECRET')

# Create uploads directory
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Create temporary directory for bulk contact storage
TEMP_DIR = os.path.join(tempfile.gettempdir(), 'bulk_contacts')
os.makedirs(TEMP_DIR, exist_ok=True)

# Database User Management
class DatabaseUser:
    """Database-backed user object for Flask-Login"""
    def __init__(self, user_record):
        self.id = str(user_record.id)
        self.email = user_record.email
        self.name = user_record.name
        self.picture_url = user_record.picture_url
        self.role = user_record.role
        self.is_active_user = user_record.is_active
        self._user_record = user_record
    
    def is_authenticated(self):
        return True
    
    def is_active(self):
        return self.is_active_user
    
    def is_anonymous(self):
        return False
    
    def get_id(self):
        return self.id

def get_user_organization():
    """Get the current user's organization"""
    if current_user.is_authenticated:
        session = db_manager.get_session()
        try:
            user = session.query(User).filter_by(id=current_user.id).first()
            if user and user.owned_organizations:
                return user.owned_organizations[0]
            return None
        finally:
            session.close()
    return None

def get_current_user_db():
    """Get current user's database record"""
    if current_user.is_authenticated:
        session = db_manager.get_session()
        try:
            return session.query(User).filter_by(id=current_user.id).first()
        finally:
            session.close()
    return None

# Bulk contact helper functions (keep existing logic but could be enhanced with database)
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

# Similar functions for bulk coaches
def store_bulk_coaches(user_id, coaches):
    """Store bulk coaches in a temporary file"""
    coach_data = []
    for coach in coaches:
        coach_dict = {
            'team_name': coach.team_name,
            'coach_name': coach.coach_name,
            'email': coach.email,
            'phone': coach.phone,
            'role': coach.role,
            'notes': coach.notes,
            'original_text': coach.original_text
        }
        coach_data.append(coach_dict)
    
    bulk_id = str(uuid.uuid4())
    filename = f"{user_id}_coaches_{bulk_id}.pkl"
    filepath = os.path.join(TEMP_DIR, filename)
    
    with open(filepath, 'wb') as f:
        pickle.dump(coach_data, f)
    
    return bulk_id

def get_bulk_coaches(user_id, bulk_id):
    """Retrieve bulk coaches from temporary file"""
    filename = f"{user_id}_coaches_{bulk_id}.pkl"
    filepath = os.path.join(TEMP_DIR, filename)
    
    try:
        with open(filepath, 'rb') as f:
            return pickle.load(f)
    except FileNotFoundError:
        return None

def cleanup_bulk_coaches(user_id, bulk_id):
    """Remove temporary bulk coach file"""
    filename = f"{user_id}_coaches_{bulk_id}.pkl"
    filepath = os.path.join(TEMP_DIR, filename)
    
    try:
        os.remove(filepath)
    except FileNotFoundError:
        pass

ALLOWED_EXTENSIONS = {'csv', 'txt'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Flask-Login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please sign in with Google to access this page.'
login_manager.login_message_category = 'info'

def is_valid_uuid(user_id):
    """Check if string is a valid UUID format"""
    uuid_pattern = re.compile(
        r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', 
        re.IGNORECASE
    )
    return bool(uuid_pattern.match(str(user_id)))

@login_manager.user_loader
def load_user(user_id):
    # If user_id is not a valid UUID format (old session), return None to force re-login
    if not is_valid_uuid(user_id):
        return None
    
    session = db_manager.get_session()
    try:
        user_record = session.query(User).filter_by(id=user_id).first()
        if user_record:
            return DatabaseUser(user_record)
        return None
    except Exception:
        # Any other database error, return None to force re-login
        return None
    finally:
        session.close()

# Google OAuth setup
google_bp = make_google_blueprint(
    client_id=app.config['GOOGLE_OAUTH_CLIENT_ID'],
    client_secret=app.config['GOOGLE_OAUTH_CLIENT_SECRET'],
    scope=["openid", "email", "profile"]
)
app.register_blueprint(google_bp, url_prefix='/login')

def get_user_upload_folder():
    """Get user-specific upload folder"""
    if current_user.is_authenticated:
        user_folder = os.path.join(app.config['UPLOAD_FOLDER'], current_user.id)
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

@oauth_authorized.connect_via(google_bp)
def google_logged_in(blueprint, token):
    """Handle Google OAuth callback"""
    if not token:
        flash('Failed to log in with Google.', 'error')
        return False
    
    resp = blueprint.session.get("/oauth2/v2/userinfo")
    if not resp.ok:
        flash('Failed to fetch user info from Google.', 'error')
        return False
    
    google_info = resp.json()
    session = db_manager.get_session()
    
    try:
        # Check if user exists
        user = session.query(User).filter_by(email=google_info['email']).first()
        
        if not user:
            # Create new user
            user = User(
                email=google_info['email'],
                name=google_info['name'],
                picture_url=google_info.get('picture'),
                google_id=google_info['id'],
                role='user',
                is_active=True
            )
            session.add(user)
            session.flush()  # Get the user ID
            
            # Create organization for new user
            org_name = f"{google_info['name']}'s Organization"
            org_slug = f"org-{user.id}"
            
            organization = Organization(
                name=org_name,
                slug=org_slug,
                owner_id=user.id,
                is_active=True
            )
            session.add(organization)
            session.commit()
            
            flash(f'Welcome {user.name}! Your account has been created.', 'success')
        else:
            # Update existing user info
            user.name = google_info['name']
            user.picture_url = google_info.get('picture')
            user.google_id = google_info['id']
            user.last_login_at = datetime.utcnow()
            session.commit()
            
            flash(f'Welcome back {user.name}!', 'success')
        
        # Log in the user
        user_obj = DatabaseUser(user)
        login_user(user_obj)
        return False  # Don't redirect automatically
        
    except Exception as e:
        session.rollback()
        flash(f'Error during login: {str(e)}', 'error')
        return False
    finally:
        session.close()

@app.route('/logout')
@login_required
def logout():
    """Log out the current user"""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

# Main Routes
@app.route('/')
@login_required
def dashboard():
    """Main dashboard showing fixture overview"""
    session = db_manager.get_session()
    try:
        org = get_user_organization()
        if not org:
            flash('No organization found. Please contact support.', 'error')
            return redirect(url_for('logout'))
        
        # Get task counts by status
        pending_count = session.query(Task).filter_by(
            organization_id=org.id, 
            status='pending'
        ).count()
        
        waiting_count = session.query(Task).filter_by(
            organization_id=org.id,
            status='waiting'
        ).count()
        
        in_progress_count = session.query(Task).filter_by(
            organization_id=org.id,
            status='in_progress'
        ).count()
        
        completed_count = session.query(Task).filter_by(
            organization_id=org.id,
            status='completed'
        ).count()
        
        # Get managed teams count
        managed_teams_count = session.query(Team).filter_by(
            organization_id=org.id,
            is_managed=True
        ).count()
        
        # Get total tasks count
        total_tasks = pending_count + waiting_count + in_progress_count + completed_count
        
        # Get recent fixtures
        recent_fixtures = session.query(Fixture).filter_by(
            organization_id=org.id
        ).order_by(Fixture.created_at.desc()).limit(5).all()
        
        # Create summary object for template compatibility
        summary = {
            'total': total_tasks,
            'pending': pending_count,
            'waiting': waiting_count,
            'in_progress': in_progress_count,
            'completed': completed_count
        }
        
        return render_template('dashboard.html',
            pending_count=pending_count,
            waiting_count=waiting_count,
            in_progress_count=in_progress_count,
            completed_count=completed_count,
            recent_fixtures=recent_fixtures,
            user_name=current_user.name,
            my_teams_count=managed_teams_count,
            total_tasks=total_tasks,
            summary=summary
        )
        
    finally:
        session.close()

@app.route('/tasks')
@app.route('/tasks/<status>')
@login_required
def view_tasks(status=None):
    """View tasks, optionally filtered by status"""
    session = db_manager.get_session()
    try:
        org = get_user_organization()
        if not org:
            flash('No organization found. Please contact support.', 'error')
            return redirect(url_for('logout'))
        
        # Build query
        query = session.query(Task).filter_by(organization_id=org.id)
        
        if status and status in ['pending', 'waiting', 'in_progress', 'completed']:
            query = query.filter_by(status=status)
        
        # Get tasks with their associated fixtures and teams (specify explicit join)
        tasks = query.join(Fixture).join(Team, Fixture.team_id == Team.id).order_by(Task.created_at.desc()).all()
        
        # Get managed teams count
        managed_teams_count = session.query(Team).filter_by(
            organization_id=org.id,
            is_managed=True
        ).count()
        
        # Get task counts for summary
        pending_count = session.query(Task).filter_by(organization_id=org.id, status='pending').count()
        waiting_count = session.query(Task).filter_by(organization_id=org.id, status='waiting').count()
        in_progress_count = session.query(Task).filter_by(organization_id=org.id, status='in_progress').count()
        completed_count = session.query(Task).filter_by(organization_id=org.id, status='completed').count()
        
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
            current_status=status,
            user_name=current_user.name,
            my_teams_count=managed_teams_count,
            my_summary=my_summary
        )
        
    finally:
        session.close()

@app.route('/update_task_status', methods=['POST'])
@login_required
def update_task_status():
    """Update task status"""
    task_id = request.form.get('task_id')
    new_status = request.form.get('status')
    
    if not task_id or not new_status:
        flash('Invalid request.', 'error')
        return redirect(request.referrer or url_for('dashboard'))
    
    session = db_manager.get_session()
    try:
        org = get_user_organization()
        if not org:
            flash('No organization found.', 'error')
            return redirect(url_for('logout'))
        
        task = session.query(Task).filter_by(
            id=task_id,
            organization_id=org.id
        ).first()
        
        if not task:
            flash('Task not found.', 'error')
            return redirect(request.referrer or url_for('dashboard'))
        
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
    
    return redirect(request.referrer or url_for('dashboard'))

@app.route('/mark_completed/<task_id>', methods=['POST'])
@login_required  
def mark_completed(task_id):
    """Mark a task as completed"""
    session = db_manager.get_session()
    try:
        org = get_user_organization()
        if not org:
            flash('No organization found.', 'error')
            return redirect(url_for('logout'))
        
        task = session.query(Task).filter_by(
            id=task_id,
            organization_id=org.id
        ).first()
        
        if not task:
            flash('Task not found.', 'error')
            return redirect(request.referrer or url_for('dashboard'))
        
        task.status = 'completed'
        task.completed_at = datetime.utcnow()
        session.commit()
        
        flash('Task marked as completed.', 'success')
        
    except Exception as e:
        session.rollback()
        flash(f'Error completing task: {str(e)}', 'error')
    finally:
        session.close()
    
    return redirect(request.referrer or url_for('dashboard'))

@app.route('/mark_in_progress/<task_id>', methods=['POST'])
@login_required
def mark_in_progress(task_id):
    """Mark a task as in progress"""
    session = db_manager.get_session()
    try:
        org = get_user_organization()
        if not org:
            flash('No organization found.', 'error')
            return redirect(url_for('logout'))
        
        task = session.query(Task).filter_by(
            id=task_id,
            organization_id=org.id
        ).first()
        
        if not task:
            flash('Task not found.', 'error')
            return redirect(request.referrer or url_for('dashboard'))
        
        task.status = 'in_progress'
        task.completed_at = None
        session.commit()
        
        flash('Task marked as in progress.', 'success')
        
    except Exception as e:
        session.rollback()
        flash(f'Error updating task: {str(e)}', 'error')
    finally:
        session.close()
    
    return redirect(request.referrer or url_for('dashboard'))

@app.route('/settings')
@login_required
def settings():
    """Settings page"""
    session = db_manager.get_session()
    try:
        org = get_user_organization()
        if not org:
            flash('No organization found.', 'error')
            return redirect(url_for('logout'))
        
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
        
        return render_template('settings.html',
            user_name=current_user.name,
            user_email=current_user.email,
            managed_teams=[team.name for team in managed_teams],
            pitches={pitch.name: {
                'address': pitch.address or '',
                'parking': pitch.parking_info or '',
                'toilets': pitch.toilet_info or '', 
                'special_instructions': pitch.special_instructions or '',
                'opening_notes': pitch.opening_notes or '',
                'warm_up_notes': pitch.warm_up_notes or ''
            } for pitch in pitches},
            team_contacts={contact.team_name: {
                'contact_name': contact.contact_name or '',
                'email': contact.email or '',
                'phone': contact.phone or '',
                'notes': contact.notes or ''
            } for contact in team_contacts},
            preferences=preferences,
            email_template=email_template.content if email_template else ''
        )
        
    finally:
        session.close()

@app.route('/task/<task_id>')
@login_required
def view_task(task_id):
    """View individual task details"""
    session = db_manager.get_session()
    try:
        org = get_user_organization()
        if not org:
            flash('No organization found.', 'error')
            return redirect(url_for('logout'))
        
        # Get task with fixture and team information
        task = session.query(Task).filter_by(
            id=task_id,
            organization_id=org.id
        ).join(Fixture).join(Team, Fixture.team_id == Team.id).first()
        
        if not task:
            flash('Task not found.', 'error')
            return redirect(url_for('dashboard'))
        
        return render_template('task_detail.html',
            task=task,
            user_name=current_user.name
        )
        
    finally:
        session.close()

@app.route('/generate_email/<task_id>')
@login_required
def generate_email_route(task_id):
    """Generate email for a task"""
    session = db_manager.get_session()
    try:
        org = get_user_organization()
        if not org:
            flash('No organization found.', 'error')
            return redirect(url_for('logout'))
        
        # Get task with all related data
        task = session.query(Task).filter_by(
            id=task_id,
            organization_id=org.id
        ).first()
        
        if not task:
            flash('Task not found.', 'error')
            return redirect(url_for('dashboard'))
        
        fixture = task.fixture
        team = fixture.team
        pitch = fixture.pitch
        
        # Get email template
        email_template = session.query(EmailTemplate).filter_by(
            organization_id=org.id,
            template_type='default',
            is_active=True
        ).first()
        
        # Get team coach for this team
        team_coach = session.query(TeamCoach).filter_by(
            organization_id=org.id,
            team_id=team.id
        ).first()
        
        # Use SmartEmailGenerator to generate the email
        email_generator = SmartEmailGenerator(
            template=email_template.content if email_template else '',
            user_preferences={},  # Could load from user preferences
            managed_teams=[team.name],
            pitches={pitch.name: {
                'address': pitch.address or '',
                'parking': pitch.parking_info or '',
                'toilets': pitch.toilet_info or '',
                'special_instructions': pitch.special_instructions or '',
                'opening_notes': pitch.opening_notes or '',
                'warm_up_notes': pitch.warm_up_notes or ''
            }} if pitch else {},
            team_coaches={team.name: [{
                'coach_name': team_coach.coach_name,
                'email': team_coach.email,
                'phone': team_coach.phone,
                'role': team_coach.role
            }]} if team_coach else {}
        )
        
        # Create task data in expected format
        task_data = {
            'team': team.name,
            'opposition': fixture.opposition_name or '',
            'home_away': fixture.home_away,
            'pitch': pitch.name if pitch else '',
            'kickoff_time': fixture.kickoff_time_text or '',
            'format': fixture.match_format or '',
            'referee': fixture.referee_info or ''
        }
        
        email_content = email_generator.generate_email(task_data)
        subject = email_generator.generate_subject(task_data)
        
        return render_template('email_preview.html',
            task=task,
            email_content=email_content,
            subject=subject,
            user_name=current_user.name
        )
        
    finally:
        session.close()

@app.route('/api/summary')
@login_required
def api_summary():
    """API endpoint for dashboard summary"""
    session = db_manager.get_session()
    try:
        org = get_user_organization()
        if not org:
            return jsonify({'error': 'No organization found'}), 404
        
        # Get counts by status
        pending = session.query(Task).filter_by(organization_id=org.id, status='pending').count()
        waiting = session.query(Task).filter_by(organization_id=org.id, status='waiting').count()
        in_progress = session.query(Task).filter_by(organization_id=org.id, status='in_progress').count()
        completed = session.query(Task).filter_by(organization_id=org.id, status='completed').count()
        
        return jsonify({
            'pending': pending,
            'waiting': waiting,  
            'in_progress': in_progress,
            'completed': completed
        })
        
    finally:
        session.close()

@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload_file():
    """Upload fixture files - placeholder for now"""
    if request.method == 'GET':
        return render_template('upload.html', user_name=current_user.name)
    
    # For now, just flash a message - full implementation can be added later
    flash('File upload functionality will be available soon with database integration.', 'info')
    return redirect(url_for('dashboard'))

@app.route('/add_fixture', methods=['GET', 'POST'])
@login_required
def add_fixture():
    """Add fixture manually - placeholder for now"""
    if request.method == 'GET':
        return render_template('add_fixture.html', user_name=current_user.name)
    
    # For now, just flash a message - full implementation can be added later
    flash('Add fixture functionality will be available soon with database integration.', 'info')
    return redirect(url_for('dashboard'))

@app.route('/parse_fixture', methods=['GET', 'POST'])
@login_required
def parse_fixture():
    """Parse fixture text - placeholder for now"""
    if request.method == 'GET':
        return render_template('parse_fixture.html', user_name=current_user.name)
    
    # For now, just flash a message - full implementation can be added later
    flash('Parse fixture functionality will be available soon with database integration.', 'info')
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)