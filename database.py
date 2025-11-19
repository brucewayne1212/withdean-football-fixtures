import os
from models import DatabaseManager

# Database configuration
DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    # Fallback or raise error - for now we assume it exists as per app.py
    pass

db_manager = DatabaseManager(DATABASE_URL) if DATABASE_URL else None

def get_db():
    return db_manager
