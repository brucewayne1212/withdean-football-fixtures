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

def test_new_dashboard_logic():
    """Test the new dashboard logic"""
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

        print(f"=== TESTING NEW DASHBOARD LOGIC ===")
        print(f"Current time: {datetime.now()}")
        print()

        # Replicate the NEW dashboard logic exactly
        print(f"NEW DASHBOARD LOGIC:")

        # First, try to find any fixture with tasks (including those without dates)
        fixtures_with_tasks = session.query(Fixture).join(Task).filter(
            Fixture.team_id == u9_red.id,
            Task.organization_id == org.id,
            Task.is_archived != True
        ).order_by(Fixture.kickoff_datetime.asc().nullslast()).all()

        print(f"Step 1: Found {len(fixtures_with_tasks)} fixtures with tasks:")
        for fixture in fixtures_with_tasks:
            print(f"  - {fixture.opposition_name}: {fixture.kickoff_datetime}")

        next_fixture = None
        if fixtures_with_tasks:
            # Prefer future fixtures with tasks, but include fixtures without dates
            print(f"Step 2: Looking for future fixtures or fixtures without dates...")
            for fixture in fixtures_with_tasks:
                is_future_or_no_date = fixture.kickoff_datetime is None or fixture.kickoff_datetime >= datetime.now()
                print(f"  - {fixture.opposition_name}: is_future_or_no_date={is_future_or_no_date}")
                if is_future_or_no_date:
                    next_fixture = fixture
                    print(f"    ✓ SELECTED")
                    break

            # If no future fixtures with tasks, take the first fixture with tasks
            if not next_fixture:
                next_fixture = fixtures_with_tasks[0]
                print(f"Step 3: No future fixtures, taking first: {next_fixture.opposition_name}")

        # Fallback: if no fixtures have tasks, get chronologically next future fixture
        if not next_fixture:
            print(f"Step 4: No fixtures with tasks, looking for future fixtures...")
            upcoming_fixtures_with_dates = session.query(Fixture).filter(
                Fixture.team_id == u9_red.id,
                Fixture.kickoff_datetime >= datetime.now()
            ).order_by(Fixture.kickoff_datetime.asc()).first()

            if upcoming_fixtures_with_dates:
                next_fixture = upcoming_fixtures_with_dates
                print(f"  Selected fallback: {next_fixture.opposition_name}")

        print(f"\nFINAL RESULT - Dashboard will show:")
        if next_fixture:
            print(f"  Opposition: {next_fixture.opposition_name}")
            if next_fixture.kickoff_datetime:
                print(f"  Date: {next_fixture.kickoff_datetime.strftime('%a %d %b')}")
                print(f"  Time: {next_fixture.kickoff_datetime.strftime('%I:%M %p')}")
            else:
                print(f"  Date: TBC")
                print(f"  Time: TBC")
            print(f"  Fixture ID: {next_fixture.id}")

            # Check what tasks this fixture has
            fixture_tasks = session.query(Task).filter(
                Task.fixture_id == next_fixture.id,
                Task.organization_id == org.id,
                Task.is_archived != True
            ).all()
            print(f"  Tasks: {len(fixture_tasks)}")
            for task in fixture_tasks:
                print(f"    - {task.task_type}: {task.status}")
        else:
            print(f"  No fixtures to display")

    finally:
        session.close()

if __name__ == "__main__":
    test_new_dashboard_logic()