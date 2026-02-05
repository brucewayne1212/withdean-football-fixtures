#!/usr/bin/env python3
"""
Migration script to fix task_type constraint from 'away_forward' to 'away_email'
"""

import os
import psycopg2
from datetime import datetime
from dotenv import load_dotenv

def run_migration():
    # Load environment variables from .env file
    load_dotenv()

    # Get connection details
    connection_url = os.environ.get('DATABASE_URL')
    if not connection_url:
        raise ValueError("DATABASE_URL environment variable is required. Please set it in your environment or .env file.")

    try:
        conn = psycopg2.connect(connection_url)
        cursor = conn.cursor()

        print("Connected to database...")

        # Check current constraint
        cursor.execute("""
            SELECT conname, pg_get_constraintdef(oid)
            FROM pg_constraint
            WHERE conname = 'check_task_type';
        """)

        constraint = cursor.fetchone()
        if constraint:
            print(f"Current constraint: {constraint[1]}")
        else:
            print("No task_type constraint found - it may not exist yet")

        # Drop the old constraint if it exists
        cursor.execute("""
            ALTER TABLE tasks DROP CONSTRAINT IF EXISTS check_task_type;
        """)
        print("Dropped old constraint...")

        # Add the correct constraint
        cursor.execute("""
            ALTER TABLE tasks ADD CONSTRAINT check_task_type
                CHECK (task_type IN ('home_email', 'away_email'));
        """)
        print("Added new constraint...")

        # Update any existing 'away_forward' task_types to 'away_email'
        cursor.execute("""
            UPDATE tasks SET task_type = 'away_email' WHERE task_type = 'away_forward';
        """)

        # Check how many rows were updated
        print("Updated existing away_forward task types...")

        conn.commit()
        print("Migration completed successfully!")

        # Verify the new constraint
        cursor.execute("""
            SELECT COUNT(*) FROM tasks WHERE task_type NOT IN ('home_email', 'away_email');
        """)

        invalid_count = cursor.fetchone()[0]
        if invalid_count > 0:
            print(f"WARNING: {invalid_count} tasks still have invalid task_type values!")
        else:
            print("All tasks now have valid task_type values.")

    except Exception as e:
        print(f"Error running migration: {e}")
        if conn:
            conn.rollback()
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

if __name__ == '__main__':
    run_migration()
