#!/usr/bin/env python3
"""
Debug datetime display issues across dashboard, tasks, and email pages
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

def debug_datetime_issues():
    """Debug datetime display issues"""
    session = db_manager.get_session()
    try:
        # Get organization
        org = session.query(Organization).first()
        if not org:
            print("No organization found!")
            return

        print(f"=== DEBUGGING DATETIME DISPLAY ISSUES ===")
        print(f"Current server time: {datetime.now()}")
        print(f"Current UTC time: {datetime.utcnow()}")
        print()

        # Get U9 Red team first
        u9_red = session.query(Team).filter_by(
            organization_id=org.id,
            name="U9 Red"
        ).first()

        if not u9_red:
            print("U9 Red team not found!")
            return

        # Check the specific fixtures mentioned
        fixtures = session.query(Fixture).filter(
            Fixture.team_id == u9_red.id
        ).order_by(Fixture.kickoff_datetime.asc()).all()

        print(f"All U9 Red fixtures in database:")
        for i, fixture in enumerate(fixtures):
            print(f"  {i+1}. ID: {fixture.id}")
            print(f"     Opposition: {fixture.opposition_name}")
            print(f"     Raw kickoff_datetime: {fixture.kickoff_datetime}")
            print(f"     Raw kickoff_datetime type: {type(fixture.kickoff_datetime)}")
            if fixture.kickoff_datetime:
                print(f"     Timezone info: {fixture.kickoff_datetime.tzinfo}")
                print(f"     Formatted date: {fixture.kickoff_datetime.strftime('%Y-%m-%d')}")
                print(f"     Formatted time: {fixture.kickoff_datetime.strftime('%H:%M')}")
                print(f"     Formatted day: {fixture.kickoff_datetime.strftime('%a %d %b')}")

            # Check if this fixture has any other time fields
            for attr in dir(fixture):
                if 'time' in attr.lower() or 'date' in attr.lower():
                    if not attr.startswith('_') and attr != 'kickoff_datetime':
                        value = getattr(fixture, attr, None)
                        if value is not None:
                            print(f"     {attr}: {value} (type: {type(value)})")
            print()

        # Test the new dashboard logic for next fixture selection
        print(f"=== DASHBOARD NEXT FIXTURE SELECTION ===")

        if u9_red:
            # Replicate the dashboard logic exactly
            next_fixture = None
            upcoming_fixtures_with_dates = session.query(Fixture).filter(
                Fixture.team_id == u9_red.id,
                Fixture.kickoff_datetime >= datetime.now()
            ).order_by(Fixture.kickoff_datetime.asc()).all()

            print(f"Upcoming fixtures in chronological order:")
            for fixture in upcoming_fixtures_with_dates:
                has_tasks = session.query(Task).filter(
                    Task.fixture_id == fixture.id,
                    Task.organization_id == org.id,
                    Task.is_archived != True
                ).first() is not None
                print(f"  {fixture.opposition_name}: {fixture.kickoff_datetime} (has tasks: {has_tasks})")

            # Find the first upcoming fixture that has tasks
            for fixture in upcoming_fixtures_with_dates:
                fixture_tasks = session.query(Task).filter(
                    Task.fixture_id == fixture.id,
                    Task.organization_id == org.id,
                    Task.is_archived != True
                ).first()
                if fixture_tasks:
                    next_fixture = fixture
                    break

            if next_fixture:
                print(f"\nSelected next_fixture:")
                print(f"  Opposition: {next_fixture.opposition_name}")
                print(f"  Raw datetime: {next_fixture.kickoff_datetime}")
                print(f"  Dashboard would display:")
                print(f"    Date: {next_fixture.kickoff_datetime.strftime('%a %d %b')}")
                print(f"    Time: {next_fixture.kickoff_datetime.strftime('%H:%M')}")

        # Check task data that links to fixtures
        print(f"\n=== TASK DATA INSPECTION ===")
        all_tasks = session.query(Task).join(Fixture).filter(
            Fixture.team_id == u9_red.id,
            Task.organization_id == org.id,
            Task.is_archived != True
        ).all()

        for task in all_tasks:
            print(f"Task {task.id}:")
            print(f"  Type: {task.task_type}")
            print(f"  Status: {task.status}")
            print(f"  Fixture: {task.fixture.opposition_name}")
            print(f"  Fixture datetime: {task.fixture.kickoff_datetime}")
            print()

    finally:
        session.close()

if __name__ == "__main__":
    debug_datetime_issues()