#!/usr/bin/env python3
"""
Test the overall_status logic with actual database data
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models import DatabaseManager, Fixture, Task, Team, Organization
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database setup
DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is required. Please set it in your environment or .env file.")
db_manager = DatabaseManager(DATABASE_URL)

def test_overall_status_logic():
    """Test the overall status logic with actual data"""
    session = db_manager.get_session()
    try:
        # Get organization
        org = session.query(Organization).first()
        if not org:
            print("No organization found!")
            return

        # Get managed teams
        managed_teams = session.query(Team).filter_by(
            organization_id=org.id,
            is_managed=True
        ).all()

        print(f"Testing overall status logic for {len(managed_teams)} teams...")
        print()

        for team in managed_teams:
            print(f"=== TEAM: {team.name} ===")

            # Get all tasks for this team
            all_tasks = session.query(Task).join(Fixture).filter(
                Fixture.team_id == team.id,
                Task.organization_id == org.id,
                Task.is_archived != True
            ).all()

            print(f"Total tasks: {len(all_tasks)}")

            if len(all_tasks) == 0:
                print("No tasks found - should be 'no_fixtures'")
                print()
                continue

            # Show all task statuses
            task_statuses = [t.status for t in all_tasks]
            print(f"Task statuses: {task_statuses}")

            # Apply the dashboard logic exactly
            pending_tasks = [t for t in all_tasks if t.status == 'pending']
            waiting_tasks = [t for t in all_tasks if t.status == 'waiting']
            in_progress_tasks = [t for t in all_tasks if t.status == 'in_progress']
            completed_tasks = [t for t in all_tasks if t.status == 'completed']

            total_pending = len(pending_tasks)
            total_waiting = len(waiting_tasks)
            total_in_progress = len(in_progress_tasks)
            total_completed = len(completed_tasks)

            print(f"Counts: pending={total_pending}, waiting={total_waiting}, in_progress={total_in_progress}, completed={total_completed}")

            # Apply the exact logic from dashboard
            if total_pending > 0:
                overall_status = 'action_needed'
                reason = f"Has {total_pending} pending tasks"
            elif total_waiting + total_in_progress > 0:
                overall_status = 'in_progress'
                reason = f"Has {total_waiting} waiting + {total_in_progress} in progress tasks"
            elif total_completed > 0:
                overall_status = 'complete'
                reason = f"Has {total_completed} completed tasks, no pending/waiting/in_progress"
            else:
                overall_status = 'no_fixtures'
                reason = "No tasks found"

            print(f"Overall status: '{overall_status}' ({reason})")

            # What template will show
            if overall_status == 'action_needed':
                template_display = "Action Needed"
            elif overall_status == 'in_progress':
                template_display = "In Progress"
            elif overall_status == 'complete':
                template_display = "Complete"
            else:
                template_display = "No Fixtures"

            print(f"Template will show: '{template_display}'")
            print()

    finally:
        session.close()

if __name__ == "__main__":
    test_overall_status_logic()