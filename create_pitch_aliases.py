import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

def run_migration():
    print("Running migration: Create pitch_aliases table")
    
    DATABASE_URL = os.environ.get('DATABASE_URL')
    if not DATABASE_URL:
        print("Error: DATABASE_URL not found")
        return

    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as connection:
            # Check if table exists
            result = connection.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'pitch_aliases'
                );
            """))
            exists = result.scalar()
            
            if exists:
                print("Table 'pitch_aliases' already exists.")
            else:
                print("Creating table 'pitch_aliases'...")
                connection.execute(text("""
                    CREATE TABLE pitch_aliases (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        organization_id UUID NOT NULL REFERENCES organizations(id),
                        pitch_id UUID NOT NULL REFERENCES pitches(id),
                        alias VARCHAR(255) NOT NULL,
                        created_at TIMESTAMPTZ DEFAULT NOW(),
                        UNIQUE(organization_id, alias)
                    );
                """))
                connection.commit()
                print("✅ Table created successfully.")

    except Exception as e:
        print(f"Migration failed: {e}")

if __name__ == "__main__":
    run_migration()
