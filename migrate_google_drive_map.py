#!/usr/bin/env python3
"""
Migration script to add google_drive_map_url column to pitches table
"""
import os
import sys
from sqlalchemy import text

# Add current directory to path to import app modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db

def run_migration():
    """Add google_drive_map_url column to pitches table"""
    with app.app_context():
        try:
            # Check if column already exists
            result = db.session.execute(text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'pitches'
                AND column_name = 'google_drive_map_url'
            """))

            if result.fetchone():
                print("Column 'google_drive_map_url' already exists in pitches table")
                return

            # Add the column
            db.session.execute(text("""
                ALTER TABLE pitches ADD COLUMN google_drive_map_url TEXT
            """))

            # Add comment
            db.session.execute(text("""
                COMMENT ON COLUMN pitches.google_drive_map_url IS 'URL to Google Drive walking/estate map image'
            """))

            db.session.commit()
            print("Successfully added google_drive_map_url column to pitches table")

        except Exception as e:
            db.session.rollback()
            print(f"Migration failed: {e}")
            raise

if __name__ == "__main__":
    run_migration()