#!/usr/bin/env python3
"""
Test to verify the exact values being calculated for dashboard
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

def test_dashboard_values():
    """Test the exact values being calculated for dashboard"""
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

        # Use the first organization
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

        print(f"DEBUG: Found {len(managed_teams)} managed teams")
        print()

        # Process each team (replicating dashboard logic exactly)
        result = []
        for team in managed_teams:
            print(f"=== PROCESSING TEAM: {team.name} ===")

            # Get upcoming fixtures (next 4 weeks) - for calendar view
            upcoming_fixtures = session.query(Fixture).filter(
                Fixture.team_id == team.id,
                Fixture.kickoff_datetime >= datetime.now(),
                Fixture.kickoff_datetime <= datetime.now() + timedelta(weeks=4)
            ).order_by(Fixture.kickoff_datetime.asc()).all()

            print(f"Upcoming fixtures (next 4 weeks): {len(upcoming_fixtures)}")

            # Map fixtures to Sundays for calendar
            fixture_calendar = {}
            for fixture in upcoming_fixtures:
                if fixture.kickoff_datetime:
                    fixture_date = fixture.kickoff_datetime.date()
                    for sunday in upcoming_sundays:
                        if abs((fixture_date - sunday).days) <= 3:
                            fixture_calendar[sunday] = fixture
                            break

            print(f"Fixture calendar entries: {len(fixture_calendar)}")
            print(f"Has next Sunday fixture: {next_sunday in fixture_calendar}")

            # Get all tasks for this team - THIS IS THE KEY FOR LIST VIEW
            all_tasks = session.query(Task).join(Fixture).filter(
                Fixture.team_id == team.id,
                Task.organization_id == org.id,
                Task.is_archived != True
            ).all()

            print(f"All tasks: {len(all_tasks)}")

            # Calculate task statistics
            pending_tasks = [task for task in all_tasks if task.status == 'pending']
            waiting_tasks = [task for task in all_tasks if task.status == 'waiting']
            in_progress_tasks = [task for task in all_tasks if task.status == 'in_progress']
            completed_tasks = [task for task in all_tasks if task.status == 'completed']

            print(f"Task breakdown:")
            print(f"  Pending: {len(pending_tasks)}")
            print(f"  Waiting: {len(waiting_tasks)}")
            print(f"  In Progress: {len(in_progress_tasks)}")
            print(f"  Completed: {len(completed_tasks)}")

            # Use all tasks count for consistency with list view display
            total_fixtures = len(all_tasks)
            print(f"Total fixtures (for list view): {total_fixtures}")

            # Determine overall status
            if len(completed_tasks) == len(all_tasks) and len(all_tasks) > 0:
                overall_status = 'all_completed'
            elif len(in_progress_tasks) > 0 or len(waiting_tasks) > 0:
                overall_status = 'in_progress'
            elif len(pending_tasks) > 0:
                overall_status = 'pending'
            else:
                overall_status = 'no_tasks'

            print(f"Overall status: {overall_status}")

            # Calculate completion percentage
            completion_percentage = (len(completed_tasks) / len(all_tasks) * 100) if len(all_tasks) > 0 else 0
            print(f"Completion percentage: {completion_percentage:.1f}%")

            # Check what List view will show
            will_show_in_list = total_fixtures > 0
            print(f"Will show in List view (total_fixtures > 0): {will_show_in_list}")

            result.append({
                'team': team.name,
                'total_tasks': len(all_tasks),
                'total_fixtures': total_fixtures,
                'pending': len(pending_tasks),
                'waiting': len(waiting_tasks),
                'in_progress': len(in_progress_tasks),
                'completed': len(completed_tasks),
                'overall_status': overall_status,
                'completion_percentage': completion_percentage,
                'will_show_in_list': will_show_in_list,
                'has_next_sunday_fixture': next_sunday in fixture_calendar
            })
            print()

        print("=== SUMMARY ===")
        for team_data in result:
            print(f"{team_data['team']}:")
            print(f"  Total tasks: {team_data['total_tasks']}")
            print(f"  Total fixtures (for list): {team_data['total_fixtures']}")
            print(f"  Will show in List view: {team_data['will_show_in_list']}")
            print(f"  Overall status: {team_data['overall_status']}")
            print(f"  Completion: {team_data['completion_percentage']:.1f}%")
            print()

    finally:
        session.close()

if __name__ == "__main__":
    test_dashboard_values()