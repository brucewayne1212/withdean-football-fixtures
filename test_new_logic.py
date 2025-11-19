#!/usr/bin/env python3
"""
Test the new dashboard logic that prioritizes fixtures with tasks
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

def test_new_logic():
    """Test the new fixture selection logic"""
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

        print(f"=== TESTING NEW DASHBOARD LOGIC FOR U9 RED ===")
        print()

        # NEW LOGIC: Get next fixture that has tasks (from updated dashboard)
        next_fixture = None
        upcoming_fixtures_with_dates = session.query(Fixture).filter(
            Fixture.team_id == u9_red.id,
            Fixture.kickoff_datetime >= datetime.now()
        ).order_by(Fixture.kickoff_datetime.asc()).all()

        print(f"Checking upcoming fixtures in order:")
        # Find the first upcoming fixture that has tasks
        for i, fixture in enumerate(upcoming_fixtures_with_dates):
            fixture_tasks = session.query(Task).filter(
                Task.fixture_id == fixture.id,
                Task.organization_id == org.id,
                Task.is_archived != True
            ).first()

            has_tasks = fixture_tasks is not None
            print(f"  {i+1}. {fixture.opposition_name} ({fixture.kickoff_datetime.strftime('%Y-%m-%d')}) - Has tasks: {has_tasks}")

            if has_tasks and next_fixture is None:
                next_fixture = fixture
                print(f"     ✓ SELECTED as next_fixture")

        # If no fixtures have tasks, fall back to chronologically next fixture
        if not next_fixture and upcoming_fixtures_with_dates:
            next_fixture = upcoming_fixtures_with_dates[0]
            print(f"  No fixtures with tasks found, falling back to first fixture: {next_fixture.opposition_name}")

        print()
        print(f"RESULT - Next fixture selected:")
        if next_fixture:
            print(f"  Opposition: {next_fixture.opposition_name}")
            print(f"  Date/Time: {next_fixture.kickoff_datetime}")
            print(f"  Home/Away: {next_fixture.home_away}")
            print(f"  Fixture ID: {next_fixture.id}")

            # Get tasks for this fixture
            tasks = session.query(Task).filter(
                Task.fixture_id == next_fixture.id,
                Task.organization_id == org.id,
                Task.is_archived != True
            ).all()

            print(f"  Tasks for this fixture: {len(tasks)}")
            for task in tasks:
                print(f"    - {task.task_type}: {task.status}")

        else:
            print("  No next fixture found")

    finally:
        session.close()

if __name__ == "__main__":
    test_new_logic()