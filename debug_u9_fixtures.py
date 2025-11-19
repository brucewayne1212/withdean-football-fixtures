#!/usr/bin/env python3
"""
Debug U9 Red fixture data mismatch
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models import DatabaseManager, Fixture, Task, Team, Organization
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database setup
DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is required. Please set it in your environment or .env file.")
db_manager = DatabaseManager(DATABASE_URL)

def debug_u9_fixtures():
    """Debug U9 Red fixture data to understand the mismatch"""
    session = db_manager.get_session()
    try:
        # Get organization
        org = session.query(Organization).first()
        if not org:
            print("No organization found!")
            return

        # Get U9 Red team
        u9_red = session.query(Team).filter_by(
            organization_id=org.id,
            name="U9 Red"
        ).first()

        if not u9_red:
            print("U9 Red team not found!")
            return

        print(f"=== DEBUGGING U9 RED FIXTURE DATA ===")
        print(f"Team ID: {u9_red.id}")
        print(f"Current time: {datetime.now()}")
        print()

        # Get ALL fixtures for U9 Red (not just upcoming)
        all_fixtures = session.query(Fixture).filter(
            Fixture.team_id == u9_red.id
        ).order_by(Fixture.kickoff_datetime.asc()).all()

        print(f"ALL fixtures for U9 Red ({len(all_fixtures)} total):")
        for i, fixture in enumerate(all_fixtures):
            if fixture.kickoff_datetime:
                # Handle timezone-aware comparison
                now = datetime.now()
                if fixture.kickoff_datetime.tzinfo is not None:
                    from datetime import timezone
                    now = now.replace(tzinfo=timezone.utc)
                is_future = fixture.kickoff_datetime >= now
                status = "FUTURE" if is_future else "PAST"
            else:
                status = "NO DATE"
            print(f"  {i+1}. {fixture.opposition_name} - {fixture.kickoff_datetime} - {status} - {fixture.home_away}")
        print()

        # Get next fixture using dashboard logic
        next_fixture = session.query(Fixture).filter(
            Fixture.team_id == u9_red.id,
            Fixture.kickoff_datetime >= datetime.now()
        ).order_by(Fixture.kickoff_datetime.asc()).first()

        print(f"Next fixture (dashboard logic):")
        if next_fixture:
            print(f"  Opposition: {next_fixture.opposition_name}")
            print(f"  Date/Time: {next_fixture.kickoff_datetime}")
            print(f"  Home/Away: {next_fixture.home_away}")
            print(f"  Location: {getattr(next_fixture, 'venue', getattr(next_fixture, 'location', 'No venue'))}")
            print(f"  Fixture ID: {next_fixture.id}")
        else:
            print("  No next fixture found")
        print()

        # Get upcoming fixtures (next 4 weeks) - dashboard logic
        upcoming_fixtures = session.query(Fixture).filter(
            Fixture.team_id == u9_red.id,
            Fixture.kickoff_datetime >= datetime.now(),
            Fixture.kickoff_datetime <= datetime.now() + timedelta(weeks=4)
        ).order_by(Fixture.kickoff_datetime.asc()).all()

        print(f"Upcoming fixtures (next 4 weeks) - {len(upcoming_fixtures)} fixtures:")
        for fixture in upcoming_fixtures:
            print(f"  {fixture.opposition_name} - {fixture.kickoff_datetime} - {fixture.home_away}")
        print()

        # Check tasks for next fixture
        if next_fixture:
            next_fixture_tasks = session.query(Task).filter(
                Task.fixture_id == next_fixture.id,
                Task.organization_id == org.id,
                Task.is_archived != True
            ).all()

            print(f"Tasks for next fixture ({next_fixture.opposition_name}):")
            for task in next_fixture_tasks:
                print(f"  Task {task.id}: {task.task_type} - {task.status}")
            print()

        # Check ALL tasks for U9 Red
        all_tasks = session.query(Task).join(Fixture).filter(
            Fixture.team_id == u9_red.id,
            Task.organization_id == org.id,
            Task.is_archived != True
        ).all()

        print(f"ALL tasks for U9 Red ({len(all_tasks)} total):")
        for task in all_tasks:
            print(f"  Task {task.id}: {task.task_type} - {task.status} - Fixture: {task.fixture.opposition_name if task.fixture else 'None'} ({task.fixture.kickoff_datetime if task.fixture else 'No date'})")

    finally:
        session.close()

if __name__ == "__main__":
    debug_u9_fixtures()