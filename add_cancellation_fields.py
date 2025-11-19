#!/usr/bin/env python3
"""
Migration script to add cancellation fields to fixtures table
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models import DatabaseManager
from sqlalchemy import text
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database setup
DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is required. Please set it in your environment or .env file.")
db_manager = DatabaseManager(DATABASE_URL)

def add_cancellation_fields():
    """Add cancellation fields to fixtures table"""
    print("Adding cancellation fields to fixtures table...")

    session = db_manager.get_session()
    try:
        # Add the new columns
        print("Adding is_cancelled column...")
        session.execute(text("""
            ALTER TABLE fixtures
            ADD COLUMN IF NOT EXISTS is_cancelled BOOLEAN DEFAULT FALSE
        """))

        print("Adding cancellation_reason column...")
        session.execute(text("""
            ALTER TABLE fixtures
            ADD COLUMN IF NOT EXISTS cancellation_reason TEXT
        """))

        print("Adding cancelled_at column...")
        session.execute(text("""
            ALTER TABLE fixtures
            ADD COLUMN IF NOT EXISTS cancelled_at TIMESTAMP WITH TIME ZONE
        """))

        # Update the check constraint to include 'cancelled' status
        print("Updating status check constraint...")
        session.execute(text("""
            ALTER TABLE fixtures
            DROP CONSTRAINT IF EXISTS check_fixture_status
        """))

        session.execute(text("""
            ALTER TABLE fixtures
            ADD CONSTRAINT check_fixture_status
            CHECK (status IN ('pending', 'waiting', 'in_progress', 'completed', 'cancelled'))
        """))

        session.commit()
        print("✅ Cancellation fields added successfully!")

    except Exception as e:
        session.rollback()
        print(f"❌ Error adding cancellation fields: {e}")
        raise
    finally:
        session.close()

if __name__ == "__main__":
    add_cancellation_fields()