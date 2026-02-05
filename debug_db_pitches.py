import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

def debug_db():
    print("\n--- STAGE 2 & 3: DATABASE & RETRIEVAL DIAGNOSTIC ---")
    
    DATABASE_URL = os.environ.get('DATABASE_URL')
    # DATABASE_URL = 'sqlite:///debug_app_database.db'
    if not DATABASE_URL:
        print("Error: DATABASE_URL not found")
        return

    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as connection:
            # 1. List all Pitches
            print("\n1. Configured Pitches in DB:")
            result = connection.execute(text("SELECT id, name FROM pitches"))
            pitches = result.fetchall()
            if not pitches:
                print("⚠️ No pitches found in database!")
            else:
                for p in pitches:
                    print(f"   - ID: {p[0]}, Name: '{p[1]}'")

            # 2. Check Recent Fixtures
            print("\n2. Recent Fixtures (Last 5):")
            result = connection.execute(text("""
                SELECT 
                    f.id, 
                    t.name as team_name, 
                    f.opposition_name, 
                    f.home_away, 
                    f.pitch_id,
                    p.name as pitch_name
                FROM fixtures f
                JOIN teams t ON f.team_id = t.id
                LEFT JOIN pitches p ON f.pitch_id = p.id
                ORDER BY f.created_at DESC
                LIMIT 5
            """))
            fixtures = result.fetchall()
            
            if not fixtures:
                print("⚠️ No fixtures found.")
            else:
                for f in fixtures:
                    pitch_status = f"✅ Linked to '{f[5]}'" if f[5] else "❌ NULL (TBC)"
                    print(f"   - {f[1]} vs {f[2]} ({f[3]}): {pitch_status}")
                    if not f[5] and f[3] == 'Home':
                        print("     ⚠️ Home game with no pitch assigned!")

    except Exception as e:
        print(f"Database error: {e}")

if __name__ == "__main__":
    debug_db()
