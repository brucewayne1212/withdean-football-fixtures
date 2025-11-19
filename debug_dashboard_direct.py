#!/usr/bin/env python3
"""
Debug dashboard by simulating the exact dashboard route logic
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

def debug_dashboard_route():
    """Simulate the exact dashboard route logic"""
    session = db_manager.get_session()
    try:
        # Get organization (simulating get_user_organization())
        org = session.query(Organization).first()
        if not org:
            print("No organization found!")
            return

        print(f"Using organization: {org.name}")

        # Get managed teams
        managed_teams = session.query(Team).filter_by(
            organization_id=org.id,
            is_managed=True
        ).all()

        print(f"Found {len(managed_teams)} managed teams")

        # Calculate next Sunday
        today = datetime.now().date()
        days_ahead = 6 - today.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        next_sunday = today + timedelta(days=days_ahead)

        # Get the following 4 Sundays for calendar view
        upcoming_sundays = []
        for i in range(4):
            sunday = next_sunday + timedelta(weeks=i)
            upcoming_sundays.append(sunday)

        print(f"Next Sunday: {next_sunday}")
        print()

        # EXACT copy of dashboard route logic
        team_status_data = []
        for team in managed_teams:
            print(f"=== Processing Team: {team.name} ===")

            # Get upcoming fixtures (next 4 weeks)
            upcoming_fixtures = session.query(Fixture).filter(
                Fixture.team_id == team.id,
                Fixture.kickoff_datetime >= datetime.now(),
                Fixture.kickoff_datetime <= datetime.now() + timedelta(weeks=4)
            ).order_by(Fixture.kickoff_datetime.asc()).all()

            print(f"Upcoming fixtures: {len(upcoming_fixtures)}")

            # Get all tasks for this team (matching dashboard logic exactly)
            all_tasks = session.query(Task).join(Fixture).filter(
                Fixture.team_id == team.id,
                Task.organization_id == org.id,
                Task.is_archived != True
            ).all()

            print(f"All tasks: {len(all_tasks)}")

            # Calculate task statistics (exact copy from dashboard)
            # Use all tasks count for consistency with list view display
            total_fixtures = len(all_tasks)
            pending_tasks = [t for t in all_tasks if t.status == 'pending']
            waiting_tasks = [t for t in all_tasks if t.status == 'waiting']
            in_progress_tasks = [t for t in all_tasks if t.status == 'in_progress']
            completed_tasks = [t for t in all_tasks if t.status == 'completed']

            total_tasks = len(all_tasks)
            completion_percentage = (len(completed_tasks) / total_tasks * 100) if total_tasks > 0 else 0

            print(f"total_fixtures = {total_fixtures}")
            print(f"pending_tasks = {len(pending_tasks)}")
            print(f"waiting_tasks = {len(waiting_tasks)}")
            print(f"in_progress_tasks = {len(in_progress_tasks)}")
            print(f"completed_tasks = {len(completed_tasks)}")
            print(f"completion_percentage = {completion_percentage}")

            # Calculate home/away splits (exact copy)
            home_fixtures = [f for f in upcoming_fixtures if f.home_away == 'Home']
            away_fixtures = [f for f in upcoming_fixtures if f.home_away == 'Away']

            home_tasks = [t for t in all_tasks if t.fixture and t.fixture.home_away == 'Home']
            away_tasks = [t for t in all_tasks if t.fixture and t.fixture.home_away == 'Away']

            # Calculate totals (exact copy)
            total_pending = len(pending_tasks)
            total_waiting = len(waiting_tasks)
            total_in_progress = len(in_progress_tasks)
            total_completed = len(completed_tasks)

            print(f"total_pending = {total_pending}")
            print(f"total_waiting = {total_waiting}")
            print(f"total_in_progress = {total_in_progress}")
            print(f"total_completed = {total_completed}")

            # Determine overall status (exact copy)
            if total_pending > 0:
                overall_status = 'action_needed'
            elif total_waiting + total_in_progress > 0:
                overall_status = 'in_progress'
            elif total_completed > 0:
                overall_status = 'complete'
            else:
                overall_status = 'no_fixtures'

            print(f"overall_status = '{overall_status}'")

            # Create team data object like dashboard does
            class TeamData:
                def __init__(self):
                    self.team = team
                    self.total_fixtures = total_fixtures
                    self.completion_percentage = completion_percentage
                    self.overall_status = overall_status

            team_data = TeamData()

            # What template will show
            template_status = "No Fixtures"
            if team_data.overall_status == 'action_needed':
                template_status = "Action Needed"
            elif team_data.overall_status == 'in_progress':
                template_status = "In Progress"
            elif team_data.overall_status == 'complete':
                template_status = "Complete"

            template_progress = "-"
            if team_data.total_fixtures > 0:
                template_progress = f"{team_data.completion_percentage:.0f}%"

            print(f"Template will show:")
            print(f"  Status: {template_status}")
            print(f"  Progress: {template_progress}")
            print(f"  total_fixtures > 0: {team_data.total_fixtures > 0}")
            print()

    finally:
        session.close()

if __name__ == "__main__":
    debug_dashboard_route()