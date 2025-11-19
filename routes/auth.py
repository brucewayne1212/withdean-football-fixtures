from flask import Blueprint, render_template, redirect, url_for, flash, current_app
from flask_login import LoginManager, login_required, logout_user, current_user, login_user
from flask_dance.contrib.google import make_google_blueprint, google
from flask_dance.consumer import oauth_authorized
from datetime import datetime
import re
import os

from models import User, Organization

auth_bp = Blueprint('auth', __name__)

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

def is_valid_uuid(user_id):
    """Check if string is a valid UUID format"""
    uuid_pattern = re.compile(
        r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', 
        re.IGNORECASE
    )
    return bool(uuid_pattern.match(str(user_id)))

def init_auth(app, db_manager):
    """Initialize authentication components"""
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please sign in with Google to access this page.'
    login_manager.login_message_category = 'info'

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

    # Define the oauth callback here to access db_manager closure
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

@auth_bp.route('/login')
def login():
    """Display login page"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.dashboard_view'))
    return render_template('login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    """Log out the current user"""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))
