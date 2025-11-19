from flask import Flask, render_template, redirect, url_for, flash
from flask_wtf.csrf import CSRFProtect
import os
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# CRITICAL: Allow OAuth2 over HTTP for local development only
if os.environ.get('FLASK_ENV') == 'development' or 'localhost' in os.environ.get('SERVER_NAME', ''):
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'

# Import database manager (initialized in database.py)
from database import db_manager
from utils import escapejs

# Import blueprints and auth init
from routes.auth import auth_bp, init_auth
from routes.dashboard import dashboard_bp
from routes.tasks import tasks_bp
from routes.settings import settings_bp
from routes.api import api_bp
from routes.imports import imports_bp

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Initialize CSRF Protection
csrf = CSRFProtect(app)

# Security: Require a secure secret key
SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    raise ValueError("SECRET_KEY environment variable is required.")
if len(SECRET_KEY) < 32:
    raise ValueError("SECRET_KEY must be at least 32 characters long for security.")
app.secret_key = SECRET_KEY
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Check Database URL
if not os.environ.get('DATABASE_URL'):
    raise ValueError("DATABASE_URL environment variable is required.")

# Developer convenience: ensure template changes hot-reload locally
if os.environ.get('FLASK_ENV') != 'production':
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    app.jinja_env.auto_reload = True
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
    app.jinja_env.cache = None

# Register custom filter
app.jinja_env.filters['escapejs'] = escapejs

# Configure for HTTPS when deployed
if os.environ.get('FLASK_ENV') != 'development':
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Google OAuth Configuration
app.config['GOOGLE_OAUTH_CLIENT_ID'] = os.environ.get('GOOGLE_OAUTH_CLIENT_ID')
app.config['GOOGLE_OAUTH_CLIENT_SECRET'] = os.environ.get('GOOGLE_OAUTH_CLIENT_SECRET')

# Create uploads directory
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
import tempfile
TEMP_DIR = os.path.join(tempfile.gettempdir(), 'bulk_contacts')
os.makedirs(TEMP_DIR, exist_ok=True)

# Initialize Authentication
init_auth(app, db_manager)

# Register Blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(tasks_bp)
app.register_blueprint(settings_bp)
app.register_blueprint(api_bp)
app.register_blueprint(imports_bp)

# Security Headers
@app.after_request
def set_security_headers(response):
    """Add security headers to all responses"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; img-src 'self' data: https:; font-src 'self' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com;"
    response.headers['Server'] = 'Football Fixtures App'
    if not app.debug:
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
