import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import json

load_dotenv()

def debug_settings():
    print("--- DEBUG SETTINGS URL ---")
    
    DATABASE_URL = os.environ.get('DATABASE_URL')
    if not DATABASE_URL:
        print("❌ Error: DATABASE_URL not found")
        return

    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as connection:
            print("✅ Connected to Database")
            
            # Fetch Organizations and their settings
            result = connection.execute(text("SELECT id, name, settings FROM organizations")).fetchall()
            
            print(f"\nFound {len(result)} organizations:")
            for row in result:
                org_id, name, settings = row
                print(f"\nOrganization: {name} (ID: {org_id})")
                print(f"Settings Type: {type(settings)}")
                print(f"Settings Value: {settings}")
                
                if isinstance(settings, str):
                    try:
                        settings = json.loads(settings)
                    except:
                        print("  ❌ Could not parse settings string as JSON")
                
                if isinstance(settings, dict):
                    print(f"  - weekly_sheet_url: {settings.get('weekly_sheet_url', 'NOT SET')}")
                    print(f"  - google_sheet_url: {settings.get('google_sheet_url', 'NOT SET')}")
                else:
                    print("  ❌ Settings is not a dict")

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    debug_settings()
