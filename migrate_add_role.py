import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    print("DATABASE_URL not found")
    exit(1)

engine = create_engine(DATABASE_URL)

with engine.connect() as connection:
    try:
        # Check if column exists first to avoid error
        result = connection.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='team_contacts' AND column_name='role';"))
        if result.rowcount > 0:
            print("'role' column already exists in 'team_contacts'")
        else:
            connection.execute(text("ALTER TABLE team_contacts ADD COLUMN role VARCHAR(100);"))
            connection.commit()
            print("Successfully added 'role' column to 'team_contacts'")
    except Exception as e:
        print(f"Error: {e}")
