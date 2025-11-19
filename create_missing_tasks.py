"""
Create tasks for fixtures that don't have any tasks
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
    # Find all fixtures
    fixtures = session.query(Fixture).all()

    created_count = 0
    for fixture in fixtures:
        # Check if fixture has any tasks
        if not fixture.tasks or len(fixture.tasks) == 0:
            # Determine task type and status based on home/away
            task_type = 'home_email' if fixture.home_away == 'Home' else 'away_email'
            task_status = 'pending' if fixture.home_away == 'Home' else 'waiting'

            # Create task
            new_task = Task(
                organization_id=fixture.organization_id,
                fixture_id=fixture.id,
                task_type=task_type,
                status=task_status
            )
            session.add(new_task)
            created_count += 1
            print(f"Created task for fixture: {fixture.team.name if fixture.team else 'Unknown'} vs {fixture.opposition_name}")

    session.commit()
    print(f"\nTotal tasks created: {created_count}")

except Exception as e:
    session.rollback()
    print(f"Error: {str(e)}")
    import traceback
    traceback.print_exc()
finally:
    session.close()
