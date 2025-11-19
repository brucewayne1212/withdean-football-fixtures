#!/usr/bin/env python3
"""
Migration script to add parking map fields to the pitches table.
Run this script after deploying the updated models.py and app.py code.

Usage:
python migrate_parking_maps.py
"""

import os
import sys
from sqlalchemy import create_engine, text

def run_migration():
    """Add parking map fields to pitches table"""
    try:
        # Get database URL from environment
        database_url = os.environ.get('DATABASE_URL')
        if not database_url:
            print("Error: DATABASE_URL environment variable not set")
            return False

        print(f"Connecting to database...")
        engine = create_engine(database_url)

        with engine.connect() as conn:
            # Read migration SQL
            with open('add_parking_map_fields.sql', 'r') as f:
                sql = f.read()

            print("Running migration...")
            conn.execute(text(sql))
            conn.commit()

        print("✅ Parking map fields added successfully!")
        print("\nNext steps:")
        print("1. Uncomment parking map fields in models.py (lines 133-134)")
        print("2. Uncomment parking map logic in app.py (search for 'TODO: Uncomment after running database migration')")
        print("3. Restart the application")

        return True

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False

if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)