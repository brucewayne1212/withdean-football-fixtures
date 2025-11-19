#!/usr/bin/env python3
"""
Cross-check data sources: Dashboard vs Task Management vs Email Generation
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

def debug_data_sources():
    """Debug what each page should be showing"""
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

        print(f"=== CURRENT DATABASE STATE ===")
        print(f"Current time: {datetime.now()}")
        print()

        # 1. Check all current fixtures for U9 Red
        print(f"1. ALL FIXTURES FOR U9 RED (Raw Database):")
        all_fixtures = session.query(Fixture).filter(
            Fixture.team_id == u9_red.id
        ).order_by(Fixture.kickoff_datetime.asc()).all()

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
            print(f"  {i+1}. {fixture.opposition_name}")
            print(f"     ID: {fixture.id}")
            print(f"     Date/Time: {fixture.kickoff_datetime}")
            print(f"     Status: {status}")
            print(f"     Updated: {fixture.updated_at}")
            print()

        # 2. Check what DASHBOARD logic selects
        print(f"2. DASHBOARD LOGIC (What dashboard should show):")

        # Replicate exact dashboard logic
        next_fixture = None
        upcoming_fixtures_with_dates = session.query(Fixture).filter(
            Fixture.team_id == u9_red.id,
            Fixture.kickoff_datetime >= datetime.now()
        ).order_by(Fixture.kickoff_datetime.asc()).all()

        print(f"  Step 1: Found {len(upcoming_fixtures_with_dates)} future fixtures")
        for fixture in upcoming_fixtures_with_dates:
            print(f"    - {fixture.opposition_name}: {fixture.kickoff_datetime}")

        # Find the first upcoming fixture that has tasks
        print(f"  Step 2: Looking for fixtures with tasks...")
        for fixture in upcoming_fixtures_with_dates:
            fixture_tasks = session.query(Task).filter(
                Task.fixture_id == fixture.id,
                Task.organization_id == org.id,
                Task.is_archived != True
            ).first()
            has_tasks = fixture_tasks is not None
            print(f"    - {fixture.opposition_name}: has_tasks={has_tasks}")
            if has_tasks and next_fixture is None:
                next_fixture = fixture
                print(f"      ✓ SELECTED for dashboard")

        # If no fixtures have tasks, fall back to chronologically next fixture
        if not next_fixture and upcoming_fixtures_with_dates:
            next_fixture = upcoming_fixtures_with_dates[0]
            print(f"  Step 3: No fixtures with tasks, fallback to: {next_fixture.opposition_name}")

        if next_fixture:
            print(f"\n  DASHBOARD WILL SHOW:")
            print(f"    Opposition: {next_fixture.opposition_name}")
            print(f"    Date: {next_fixture.kickoff_datetime.strftime('%a %d %b')}")
            print(f"    Time: {next_fixture.kickoff_datetime.strftime('%I:%M %p')}")
            print(f"    Fixture ID: {next_fixture.id}")
        else:
            print(f"  DASHBOARD WILL SHOW: No fixtures")

        # 3. Check what TASK MANAGEMENT shows
        print(f"\n3. TASK MANAGEMENT LOGIC (view_tasks route):")

        # Get all tasks for U9 Red (this is what task management shows)
        all_tasks = session.query(Task).join(Fixture).filter(
            Fixture.team_id == u9_red.id,
            Task.organization_id == org.id,
            Task.is_archived != True
        ).order_by(Fixture.kickoff_datetime.asc()).all()

        print(f"  Found {len(all_tasks)} tasks for U9 Red:")
        for task in all_tasks:
            print(f"    Task ID: {task.id}")
            print(f"    Type: {task.task_type}, Status: {task.status}")
            print(f"    Fixture: {task.fixture.opposition_name}")
            print(f"    Date/Time: {task.fixture.kickoff_datetime}")
            print(f"    Formatted: {task.fixture.kickoff_datetime.strftime('%a %d %b at %I:%M %p') if task.fixture.kickoff_datetime else 'No date'}")
            print()

        # 4. Check what EMAIL GENERATION would show
        print(f"4. EMAIL GENERATION (what clicking dashboard row leads to):")
        if next_fixture:
            # Get the primary task for the selected fixture
            primary_task = session.query(Task).filter(
                Task.fixture_id == next_fixture.id,
                Task.organization_id == org.id,
                Task.is_archived != True
            ).first()

            if primary_task:
                print(f"  Primary task for email generation:")
                print(f"    Task ID: {primary_task.id}")
                print(f"    Fixture: {primary_task.fixture.opposition_name}")
                print(f"    Date/Time: {primary_task.fixture.kickoff_datetime}")
                print(f"    Email will show time as: {primary_task.fixture.kickoff_datetime.strftime('%I:%M %p') if primary_task.fixture.kickoff_datetime else 'TBC'}")
            else:
                print(f"  No tasks found for selected fixture - this is the problem!")

        # 5. Check for recent updates
        print(f"\n5. RECENT UPDATES (check for caching issues):")
        recent_fixtures = session.query(Fixture).filter(
            Fixture.team_id == u9_red.id,
            Fixture.updated_at >= datetime.now() - timedelta(hours=1)
        ).order_by(Fixture.updated_at.desc()).all()

        if recent_fixtures:
            print(f"  Found {len(recent_fixtures)} fixtures updated in last hour:")
            for fixture in recent_fixtures:
                print(f"    {fixture.opposition_name}: updated at {fixture.updated_at}")
        else:
            print(f"  No fixtures updated in last hour")

    finally:
        session.close()

if __name__ == "__main__":
    debug_data_sources()