
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

def migrate():
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print("DATABASE_URL not found in environment")
        return

    # Workaround for older sqlalchemy versions that don't like postgresql://
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)

    engine = create_engine(database_url)
    
    with engine.connect() as conn:
        print("Checking for existing columns in 'teams' table...")
        
        # PostgreSQL specific check for columns
        check_query = text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'teams'
        """)
        
        result = conn.execute(check_query)
        columns = [row[0] for row in result]
        
        if 'league' not in columns:
            print("Adding 'league' column...")
            conn.execute(text("ALTER TABLE teams ADD COLUMN league VARCHAR(255)"))
        
        if 'division' not in columns:
            print("Adding 'division' column...")
            conn.execute(text("ALTER TABLE teams ADD COLUMN division VARCHAR(255)"))
            
        if 'fa_fixtures_url' not in columns:
            print("Adding 'fa_fixtures_url' column...")
            conn.execute(text("ALTER TABLE teams ADD COLUMN fa_fixtures_url TEXT"))

        conn.commit()
        print("Migration completed successfully.")

if __name__ == "__main__":
    migrate()
