import os
import sys
import requests
import csv
import io
from sqlalchemy import create_engine, text, func
from dotenv import load_dotenv

load_dotenv()

def debug_import_v2():
    print("--- DEBUG IMPORT V2 ---")
    
    # 1. Database Connection
    DATABASE_URL = os.environ.get('DATABASE_URL')
    if not DATABASE_URL:
        print("❌ Error: DATABASE_URL not found")
        return

    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as connection:
            print("✅ Connected to Database")
            
            # 2. Fetch Pitches & Aliases
            print("\n--- DB STATE ---")
            pitches = connection.execute(text("SELECT id, name FROM pitches")).fetchall()
            aliases = connection.execute(text("SELECT pitch_id, alias FROM pitch_aliases")).fetchall()
            
            pitch_map = {str(p[0]): p[1] for p in pitches}
            print(f"Found {len(pitches)} pitches:")
            for p in pitches:
                print(f"  - '{p[1]}'")
                
            print(f"\nFound {len(aliases)} aliases:")
            alias_map = {}
            for a in aliases:
                print(f"  - '{a[1]}' -> {pitch_map.get(str(a[0]), 'Unknown Pitch')}")
                alias_map[a[1].lower().strip()] = str(a[0])

            # 3. Fetch Sheet
            sheet_url = "https://docs.google.com/spreadsheets/d/1dtwQQgj1S8qa-GZQmROVVpbVpC0oYciX/export?format=csv&gid=568178147"
            print(f"\n--- FETCHING SHEET ---")
            print(f"URL: {sheet_url}")
            
            response = requests.get(sheet_url, timeout=30)
            if response.status_code != 200:
                print(f"❌ Failed to fetch sheet: {response.status_code}")
                return
                
            csv_content = response.content.decode('utf-8')
            csv_reader = csv.DictReader(io.StringIO(csv_content))
            rows = list(csv_reader)
            print(f"✅ Fetched {len(rows)} rows")
            
            # 4. Simulate Matching
            print("\n--- MATCHING SIMULATION ---")
            pitch_keys = ['pitch', 'venue', 'location', 'ground', 'field', 'stadium']
            
            for i, row in enumerate(rows[:10]): # Check first 10 rows
                print(f"\nRow {i+2}:")
                
                # Extract Pitch
                pitch_raw = None
                for key in row.keys():
                    key_lower = key.lower().strip()
                    if key_lower in pitch_keys and 'type' not in key_lower:
                        pitch_raw = row[key].strip()
                        break
                
                if not pitch_raw:
                    print("  ❌ No pitch column found or empty value")
                    continue
                    
                print(f"  Raw Pitch from Sheet: '{pitch_raw}'")
                pitch_lower = pitch_raw.lower().strip()
                
                # MATCHING LOGIC
                matched_pitch_name = None
                match_method = None
                
                # 1. Alias Match
                if pitch_lower in alias_map:
                    matched_pitch_id = alias_map[pitch_lower]
                    matched_pitch_name = pitch_map.get(matched_pitch_id)
                    match_method = "Alias"
                
                # 2. Exact Match
                if not matched_pitch_name:
                    for p in pitches:
                        if p[1].lower().strip() == pitch_lower:
                            matched_pitch_name = p[1]
                            match_method = "Exact"
                            break
                            
                # 3. Fuzzy Match (Simplified)
                if not matched_pitch_name:
                    for p in pitches:
                        if p[1].lower().strip() in pitch_lower or pitch_lower in p[1].lower().strip():
                            matched_pitch_name = p[1]
                            match_method = "Partial/Fuzzy"
                            break
                
                if matched_pitch_name:
                    print(f"  ✅ MATCHED: '{matched_pitch_name}' (Method: {match_method})")
                else:
                    print(f"  ❌ FAILED TO MATCH")
                    print(f"     Debug: '{pitch_lower}' not found in aliases or pitch names.")

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    debug_import_v2()
