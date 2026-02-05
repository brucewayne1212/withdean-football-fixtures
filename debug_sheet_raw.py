import os
import sys
from dotenv import load_dotenv
from weekly_sheet_refresher import fetch_google_sheet_csv
from sqlalchemy import create_engine, text

# Load environment variables
load_dotenv()

def debug_import():
    print("--- STAGE 1: IMPORT DIAGNOSTIC ---")
    
    # 1. Get URL from DB
    DATABASE_URL = os.environ.get('DATABASE_URL')
    if not DATABASE_URL:
        print("Error: DATABASE_URL not found")
        return

    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as connection:
            # Get the first organization's settings
            result = connection.execute(text("SELECT settings FROM organizations LIMIT 1"))
            row = result.fetchone()
            if not row:
                print("No organization found in DB.")
                return
            
            settings = row[0]
            print(f"Settings found in DB: {settings}")
            
            url = settings.get('weekly_sheet_url')
            if not url:
                print("❌ No 'weekly_sheet_url' found in settings.")
                return
            
            print(f"✅ Found Sheet URL: {url}")
            
            # 2. Fetch Sheet
            print("\nFetching sheet data...")
            try:
                rows = fetch_google_sheet_csv(url)
                print(f"✅ Successfully fetched {len(rows)} rows.")
                
                if len(rows) > 0:
                    print("\n--- HEADER ANALYSIS ---")
                    headers = list(rows[0].keys())
                    print(f"Raw Headers found: {headers}")
                    
                    pitch_keys = ['pitch', 'venue', 'location', 'ground', 'field', 'stadium']
                    found_pitch_key = None
                    for key in headers:
                        if any(pk in key.lower() for pk in pitch_keys):
                            found_pitch_key = key
                            break
                    
                    if found_pitch_key:
                        print(f"✅ Identified Pitch Column: '{found_pitch_key}'")
                    else:
                        print("❌ COULD NOT IDENTIFY PITCH COLUMN. Looked for: " + ", ".join(pitch_keys))
                    
                    print("\n--- ROW SAMPLE (First 3 rows) ---")
                    for i, row in enumerate(rows[:3]):
                        print(f"Row {i+1}:")
                        print(f"  Team: {row.get('Team', 'N/A')}")
                        print(f"  Opposition: {row.get('Opposition', 'N/A')}")
                        if found_pitch_key:
                            print(f"  Pitch Value: '{row.get(found_pitch_key, 'N/A')}'")
                        else:
                            print("  Pitch Value: <Column not found>")
                else:
                    print("⚠️ Sheet is empty.")
                    
            except Exception as e:
                print(f"❌ Error fetching sheet: {e}")

    except Exception as e:
        print(f"Database error: {e}")

if __name__ == "__main__":
    debug_import()
