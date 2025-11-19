"""
Delete all fixtures and tasks for a fresh re-import
"""

import os
from dotenv import load_dotenv
from models import Fixture, Task, DatabaseManager

# Load environment variables
load_dotenv()

DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is required")

db_manager = DatabaseManager(DATABASE_URL)
session = db_manager.get_session()

try:
    # Count fixtures and tasks
    fixture_count = session.query(Fixture).count()
    task_count = session.query(Task).count()

    print(f"Found {fixture_count} fixtures and {task_count} tasks")
    print("\nDeleting all tasks...")

    # Delete all tasks first (due to foreign key constraint)
    session.query(Task).delete()

    print("Deleting all fixtures...")

    # Delete all fixtures
    session.query(Fixture).delete()

    session.commit()
    print(f"\nSuccessfully deleted {fixture_count} fixtures and {task_count} tasks")
    print("\nYou can now re-import from the Google Sheet")

except Exception as e:
    session.rollback()
    print(f"Error: {str(e)}")
    import traceback
    traceback.print_exc()
finally:
    session.close()
