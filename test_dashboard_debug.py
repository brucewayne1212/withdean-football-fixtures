#!/usr/bin/env python3
"""
Quick test to see the dashboard debug output
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models import DatabaseManager, Fixture, Task, Team, Organization
from sqlalchemy import text
from datetime import datetime, timedelta

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Database setup
DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is required. Please set it in your environment or .env file.")
db_manager = DatabaseManager(DATABASE_URL)

def test_dashboard_logic():
    """Test the dashboard fixture mapping logic directly"""
    session = db_manager.get_session()
    try:
        # Calculate next Sunday
        today = datetime.now().date()
        days_ahead = 6 - today.weekday()  # Sunday is 6
        if days_ahead <= 0:  # Today is Sunday or past
            days_ahead += 7
        next_sunday = today + timedelta(days=days_ahead)

        # Get the following 4 Sundays for calendar view
        upcoming_sundays = []
        for i in range(4):
            sunday = next_sunday + timedelta(weeks=i)
            upcoming_sundays.append(sunday)

        print(f"DEBUG: Today is {today}, next Sunday is {next_sunday}")
        print(f"DEBUG: Upcoming Sundays: {upcoming_sundays}")

        # Check organization
        organizations = session.query(Organization).all()
        print(f"DEBUG: Found {len(organizations)} organizations")
        for org in organizations:
            print(f"  Org {org.id}: {org.name}")

        # Use the first organization (assuming there's one for this test)
        org = organizations[0] if organizations else None
        if not org:
            print("ERROR: No organization found!")
            return

        print(f"DEBUG: Using organization: {org.name}")

        # Get managed teams for this organization
        managed_teams = session.query(Team).filter_by(
            organization_id=org.id,
            is_managed=True
        ).all()

        print(f"DEBUG: Found {len(managed_teams)} managed teams for org {org.name}")

        for team in managed_teams:
            print(f"DEBUG: Processing Team {team.name}")

            # Get upcoming fixtures (next 4 weeks)
            upcoming_fixtures = session.query(Fixture).filter(
                Fixture.team_id == team.id,
                Fixture.kickoff_datetime >= datetime.now(),
                Fixture.kickoff_datetime <= datetime.now() + timedelta(weeks=4)
            ).order_by(Fixture.kickoff_datetime.asc()).all()

            print(f"DEBUG: Team {team.name} - Processing {len(upcoming_fixtures)} upcoming fixtures")

            # Map fixtures to Sundays
            fixture_calendar = {}
            for fixture in upcoming_fixtures:
                if fixture.kickoff_datetime:
                    fixture_date = fixture.kickoff_datetime.date()
                    print(f"DEBUG: Fixture {fixture.id} on {fixture_date} vs {fixture.opposition_name}")
                    # Find the closest Sunday to this fixture
                    for sunday in upcoming_sundays:
                        days_diff = abs((fixture_date - sunday).days)
                        print(f"DEBUG: Checking Sunday {sunday}, days diff: {days_diff}")
                        if days_diff <= 3:  # Within 3 days of Sunday
                            fixture_calendar[sunday] = fixture
                            print(f"DEBUG: Mapped fixture to Sunday {sunday}")
                            break
                    else:
                        print(f"DEBUG: No Sunday match found for fixture on {fixture_date}")

            print(f"DEBUG: Final fixture_calendar has {len(fixture_calendar)} entries")
            print(f"DEBUG: has_next_sunday_fixture = {next_sunday in fixture_calendar}")

            # Also check tasks for this team (with organization filter like in dashboard)
            all_tasks = session.query(Task).join(Fixture).filter(
                Fixture.team_id == team.id,
                Task.organization_id == org.id,
                Task.is_archived != True
            ).all()

            print(f"DEBUG: Found {len(all_tasks)} tasks for team {team.name}")
            for task in all_tasks:
                print(f"  Task {task.id}: {task.status} - {task.fixture.opposition_name if task.fixture else 'No fixture'}")
            print()

    finally:
        session.close()

if __name__ == "__main__":
    test_dashboard_logic()