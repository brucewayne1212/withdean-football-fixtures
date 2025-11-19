#!/usr/bin/env python3
"""
Check what task status values are actually in the database
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models import DatabaseManager, Task
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database setup
DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is required. Please set it in your environment or .env file.")
db_manager = DatabaseManager(DATABASE_URL)

def check_task_status():
    """Check what task status values exist in the database"""
    session = db_manager.get_session()
    try:
        # Get all unique task status values
        unique_statuses = session.query(Task.status).distinct().all()

        print("Unique task status values in database:")
        for status in unique_statuses:
            print(f"  '{status[0]}'")

        print()

        # Get a few example tasks with their status
        sample_tasks = session.query(Task).limit(10).all()
        print("Sample tasks with their status:")
        for task in sample_tasks:
            print(f"  Task {task.id}: status='{task.status}', type='{task.task_type}', fixture_id={task.fixture_id}")

    finally:
        session.close()

if __name__ == "__main__":
    check_task_status()