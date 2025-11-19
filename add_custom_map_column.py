#!/usr/bin/env python3
"""
Migration script to add custom_map_filename column to pitches table
"""
import os
import sys
from sqlalchemy import create_engine, text

def run_migration():
    """Add custom_map_filename column to pitches table"""
    # Get database URL - use the same connection as the app
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL environment variable is required. Please set it in your environment or .env file.")
    print(f'Using database: {database_url}')

    try:
        # Create engine and execute migration
        engine = create_engine(database_url)
        with engine.connect() as connection:
            # Check if column exists
            result = connection.execute(text('''
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'pitches'
                AND column_name = 'custom_map_filename'
            '''))

            if result.fetchone():
                print('✅ Column custom_map_filename already exists')
            else:
                # Add the column
                connection.execute(text('ALTER TABLE pitches ADD COLUMN custom_map_filename TEXT'))
                connection.commit()
                print('✅ Successfully added custom_map_filename column to pitches table')

    except Exception as e:
        print(f'❌ Migration error: {e}')

if __name__ == "__main__":
    run_migration()