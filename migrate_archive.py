#!/usr/bin/env python3
"""
Migration script to add archive columns to the database
"""

import os
import psycopg2
from datetime import datetime

def run_migration():
    # Get connection details
    connection_url = os.environ.get('DATABASE_URL')
    if not connection_url:
        raise ValueError("DATABASE_URL environment variable is required. Please set it in your environment or .env file.")
    
    try:
        conn = psycopg2.connect(connection_url)
        cursor = conn.cursor()
        
        print("Connected to database...")
        
        # Check if columns already exist
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='fixtures' AND column_name='is_archived';
        """)
        
        if cursor.fetchone():
            print("Archive columns already exist. Skipping migration.")
            return
        
        print("Adding archive columns to fixtures table...")
        cursor.execute("""
            ALTER TABLE fixtures 
            ADD COLUMN is_archived BOOLEAN DEFAULT FALSE,
            ADD COLUMN archived_at TIMESTAMP WITH TIME ZONE;
        """)
        
        print("Adding archive columns to tasks table...")
        cursor.execute("""
            ALTER TABLE tasks
            ADD COLUMN is_archived BOOLEAN DEFAULT FALSE,
            ADD COLUMN archived_at TIMESTAMP WITH TIME ZONE;
        """)
        
        print("Setting existing records to not archived...")
        cursor.execute("UPDATE fixtures SET is_archived = FALSE WHERE is_archived IS NULL;")
        cursor.execute("UPDATE tasks SET is_archived = FALSE WHERE is_archived IS NULL;")
        
        conn.commit()
        print("Migration completed successfully!")
        
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