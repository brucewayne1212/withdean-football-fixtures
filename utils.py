from flask_login import current_user
from database import db_manager
from models import User

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

def get_user_organization_id():
    """Get the current user's organization ID"""
    org = get_user_organization()
    return org.id if org else None

ALLOWED_EXTENSIONS = {'csv', 'txt', 'xlsx', 'xls'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def escapejs(value):
    """
    Escape characters for use in JavaScript strings.
    Similar to Django's escapejs filter.
    """
    if value is None:
        return ''
    # Convert to string if not already
    value = str(value)
    # Escape backslashes first (must be first)
    value = value.replace('\\', '\\\\')
    # Escape single quotes
    value = value.replace("'", "\\'")
    # Escape double quotes
    value = value.replace('"', '\\"')
    # Escape newlines
    value = value.replace('\n', '\\n')
    # Escape carriage returns
    value = value.replace('\r', '\\r')
    # Escape tabs
    value = value.replace('\t', '\\t')
    return value
