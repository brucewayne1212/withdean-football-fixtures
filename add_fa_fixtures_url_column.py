"""
Migration script to add fa_fixtures_url column to teams table
"""

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load environment variables
load_dotenv()

def run_migration():
    """Run the migration to add fa_fixtures_url column"""
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL environment variable is required")
    
    # Create engine
    engine = create_engine(database_url)
    
    # Run migration
    with engine.connect() as conn:
        # Check if column already exists
        check_query = text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='teams' AND column_name='fa_fixtures_url'
        """)
        result = conn.execute(check_query)
        exists = result.fetchone()
        
        if exists:
            print("Column 'fa_fixtures_url' already exists in teams table. Skipping migration.")
        else:
            # Add the column
            migration_query = text("""
                ALTER TABLE teams ADD COLUMN fa_fixtures_url TEXT;
            """)
            conn.execute(migration_query)
            conn.commit()
            print("Successfully added 'fa_fixtures_url' column to teams table.")
    
    print("Migration completed successfully!")

if __name__ == '__main__':
    try:
        run_migration()
    except Exception as e:
        print(f"Error running migration: {e}")
        import traceback
        traceback.print_exc()
        exit(1)

