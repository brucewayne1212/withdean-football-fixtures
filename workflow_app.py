#!/usr/bin/env python3
"""
Football Fixtures Workflow Management App
Complete task tracking for home games (send emails) and away games (forward emails)
"""

import os
import sys
from typing import List, Dict
from fixture_parser import FixtureParser
from managed_teams import get_managed_teams
from email_template import generate_email, generate_subject_line
from task_manager import TaskManager, FixtureTask, TaskType, TaskStatus

def display_header():
    """Display application header"""
    print("=" * 60)
    print("🏈 WITHDEAN YOUTH FC FIXTURE WORKFLOW MANAGER 🏈")
    print("=" * 60)
    print()

def display_main_menu():
    """Display main menu options"""
    print("📋 MAIN MENU:")
    print("1. 📥 Import new fixtures from CSV")
    print("2. ✅ View and manage current tasks")
    print("3. 📧 Generate emails for home games")
    print("4. 📨 Mark away game emails as received/forwarded")
    print("5. 📊 View task summary")
    print("6. 🧹 Clean up old completed tasks")
    print("7. ❌ Exit")
    print()

def import_fixtures(task_manager: TaskManager):
    """Import new fixtures and create tasks"""
    print("📥 IMPORT NEW FIXTURES")
    print("-" * 30)
    
    # Get CSV file path
    csv_path = input("Enter path to your downloaded CSV file: ").strip()
    if not os.path.exists(csv_path):
        print("❌ File not found!")
        return
    
    # Parse fixtures
    parser = FixtureParser()
    managed_teams = get_managed_teams()
    
    print(f"📊 Loading fixtures from: {csv_path}")
    df = parser.read_spreadsheet(csv_path)
    
    if df.empty:
        print("❌ No data found in CSV file!")
        return
    
    # Filter for managed teams (by team name OR by "Mark Monahan" in Fixtures Sec column)
    filtered_df = parser.filter_teams(df, managed_teams, manager_name="Mark Monahan")
    
    if filtered_df.empty:
        print("ℹ️ No fixtures found for your managed teams.")
        return
    
    fixtures = parser.get_fixture_data(filtered_df)
    
    print(f"✅ Found {len(fixtures)} fixture(s) for your teams:")
    print()
    
    new_tasks = 0
    updated_tasks = 0
    
    for fixture in fixtures:
        task = task_manager.create_task_from_fixture(fixture)
        
        if task.id in task_manager.tasks:
            print(f"🔄 Updated: {task.team} vs {task.opposition}")
            updated_tasks += 1
        else:
            print(f"✨ New: {task.team} vs {task.opposition} ({task.home_away})")
            new_tasks += 1
        
        task_manager.add_or_update_task(task)
    
    print()
    print(f"📈 Import Summary:")
    print(f"   New tasks: {new_tasks}")
    print(f"   Updated tasks: {updated_tasks}")
    print()

def view_and_manage_tasks(task_manager: TaskManager):
    """View and manage current tasks"""
    while True:
        print("✅ TASK MANAGEMENT")
        print("-" * 30)
        
        pending = task_manager.get_pending_tasks()
        waiting = task_manager.get_waiting_tasks()
        in_progress = task_manager.get_in_progress_tasks()
        
        print(f"📋 Pending Tasks (Home games to send): {len(pending)}")
        for i, task in enumerate(pending, 1):
            print(f"   {i}. {task.team} vs {task.opposition} - {task.kickoff_time}")
        
        print(f"\n⏳ Waiting Tasks (Away games - waiting for emails): {len(waiting)}")
        for i, task in enumerate(waiting, 1):
            print(f"   {i}. {task.team} vs {task.opposition} - {task.kickoff_time}")
        
        print(f"\n🔄 In Progress: {len(in_progress)}")
        for i, task in enumerate(in_progress, 1):
            print(f"   {i}. {task.team} vs {task.opposition} - {task.kickoff_time}")
        
        print("\nActions:")
        print("1. Mark pending task as completed")
        print("2. Mark waiting task as received & forwarded")
        print("3. Mark task as in progress")
        print("4. View task details")
        print("5. Back to main menu")
        
        choice = input("\nSelect action: ").strip()
        
        if choice == '1':
            mark_task_completed(task_manager, pending, "home email sent")
        elif choice == '2':
            mark_task_completed(task_manager, waiting, "email received and forwarded")
        elif choice == '3':
            mark_task_in_progress(task_manager, pending + waiting)
        elif choice == '4':
            view_task_details(task_manager, pending + waiting + in_progress)
        elif choice == '5':
            break
        
        print()

def mark_task_completed(task_manager: TaskManager, tasks: List[FixtureTask], action_desc: str):
    """Mark a task as completed"""
    if not tasks:
        print(f"❌ No tasks available for this action.")
        return
    
    print(f"\nSelect task to mark as completed ({action_desc}):")
    for i, task in enumerate(tasks, 1):
        print(f"{i}. {task.team} vs {task.opposition}")
    
    try:
        choice = int(input("Task number: ")) - 1
        if 0 <= choice < len(tasks):
            task = tasks[choice]
            notes = input("Add notes (optional): ").strip()
            
            task_manager.mark_completed(task.id, notes)
            print(f"✅ Marked as completed: {task.team} vs {task.opposition}")
        else:
            print("❌ Invalid choice")
    except ValueError:
        print("❌ Invalid input")

def mark_task_in_progress(task_manager: TaskManager, tasks: List[FixtureTask]):
    """Mark a task as in progress"""
    if not tasks:
        print("❌ No tasks available.")
        return
    
    print("\nSelect task to mark as in progress:")
    for i, task in enumerate(tasks, 1):
        print(f"{i}. {task.team} vs {task.opposition}")
    
    try:
        choice = int(input("Task number: ")) - 1
        if 0 <= choice < len(tasks):
            task = tasks[choice]
            task_manager.mark_in_progress(task.id)
            print(f"🔄 Marked as in progress: {task.team} vs {task.opposition}")
        else:
            print("❌ Invalid choice")
    except ValueError:
        print("❌ Invalid input")

def view_task_details(task_manager: TaskManager, tasks: List[FixtureTask]):
    """View detailed information about a task"""
    if not tasks:
        print("❌ No tasks available.")
        return
    
    print("\nSelect task to view details:")
    for i, task in enumerate(tasks, 1):
        print(f"{i}. {task.team} vs {task.opposition}")
    
    try:
        choice = int(input("Task number: ")) - 1
        if 0 <= choice < len(tasks):
            task = tasks[choice]
            print(f"\n📄 TASK DETAILS:")
            print(f"   Team: {task.team}")
            print(f"   Opposition: {task.opposition}")
            print(f"   Home/Away: {task.home_away}")
            print(f"   Venue: {task.pitch}")
            print(f"   Time: {task.kickoff_time}")
            print(f"   Type: {'Send Email' if task.task_type == TaskType.HOME_EMAIL else 'Forward Email'}")
            print(f"   Status: {task.status.value}")
            print(f"   Created: {task.created_date}")
            if task.completed_date:
                print(f"   Completed: {task.completed_date}")
            if task.notes:
                print(f"   Notes: {task.notes}")
        else:
            print("❌ Invalid choice")
    except ValueError:
        print("❌ Invalid input")

def generate_home_emails(task_manager: TaskManager):
    """Generate emails for home games"""
    home_tasks = [task for task in task_manager.get_pending_tasks() 
                  if task.task_type == TaskType.HOME_EMAIL]
    
    if not home_tasks:
        print("ℹ️ No pending home games to send emails for.")
        return
    
    print("📧 GENERATE HOME GAME EMAILS")
    print("-" * 40)
    
    parser = FixtureParser()
    
    for task in home_tasks:
        print(f"\n--- {task.team} vs {task.opposition} ---")
        
        # Convert task back to fixture format for email generation
        fixture_data = {
            'team': task.team,
            'opposition': task.opposition,
            'home_away': task.home_away,
            'pitch': task.pitch,
            'kickoff_time': task.kickoff_time,
            'league': '',  # Not stored in task
            'home_manager': '',
            'fixtures_sec': '',
            'instructions': '',
            'format': '',
            'fixture_length': '',
            'referee': '',
            'manager_mobile': '',
            'contact_1': ''
        }
        
        email_content = generate_email(fixture_data)
        subject_line = generate_subject_line(fixture_data)
        
        print(f"SUBJECT: {subject_line}")
        print("\nEMAIL CONTENT:")
        print("-" * 50)
        print(email_content)
        print("-" * 50)
        print()
        
        # Ask if email was sent
        sent = input("Mark this email as sent? (y/n): ").lower().strip()
        if sent in ['y', 'yes']:
            task_manager.mark_completed(task.id, "Email sent to opposition")
            print("✅ Marked as completed!")
        
        print("=" * 60)

def view_task_summary(task_manager: TaskManager):
    """View summary of all tasks"""
    summary = task_manager.get_task_summary()
    
    print("📊 TASK SUMMARY")
    print("-" * 20)
    print(f"Total fixtures: {summary['total']}")
    print(f"Home games: {summary['home_games']}")
    print(f"Away games: {summary['away_games']}")
    print()
    print("Status breakdown:")
    print(f"  ⏳ Pending: {summary['pending']}")
    print(f"  ⏰ Waiting: {summary['waiting']}")
    print(f"  🔄 In Progress: {summary['in_progress']}")
    print(f"  ✅ Completed: {summary['completed']}")
    print()

def cleanup_old_tasks(task_manager: TaskManager):
    """Clean up old completed tasks"""
    print("🧹 CLEANUP OLD TASKS")
    print("-" * 25)
    
    days = input("Remove completed tasks older than how many days? (default: 30): ").strip()
    try:
        days = int(days) if days else 30
    except ValueError:
        days = 30
    
    removed = task_manager.clear_old_completed_tasks(days)
    print(f"🗑️ Removed {removed} old completed tasks (older than {days} days)")
    print()

def main():
    """Main application loop"""
    task_manager = TaskManager()
    
    while True:
        display_header()
        
        # Show quick summary
        summary = task_manager.get_task_summary()
        print(f"📊 Quick Status: {summary['pending']} pending | {summary['waiting']} waiting | {summary['completed']} completed")
        print()
        
        display_main_menu()
        
        choice = input("Select option (1-7): ").strip()
        
        if choice == '1':
            import_fixtures(task_manager)
        elif choice == '2':
            view_and_manage_tasks(task_manager)
        elif choice == '3':
            generate_home_emails(task_manager)
        elif choice == '4':
            view_and_manage_tasks(task_manager)  # Same interface, different focus
        elif choice == '5':
            view_task_summary(task_manager)
        elif choice == '6':
            cleanup_old_tasks(task_manager)
        elif choice == '7':
            print("👋 Goodbye! Thanks for using Withdean Youth FC Workflow Manager!")
            break
        else:
            print("❌ Invalid choice. Please select 1-7.")
        
        input("\nPress Enter to continue...")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Operation cancelled. Goodbye!")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("Please report this issue if it persists.")