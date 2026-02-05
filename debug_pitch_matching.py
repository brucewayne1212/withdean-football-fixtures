import os
import sys
print("Importing sqlalchemy...")
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
print("Importing models...")
from models import Base, Organization, Pitch, Fixture
print("Importing weekly_sheet_refresher...")
from weekly_sheet_refresher import fetch_google_sheet_csv, parse_fixture_from_row
print("Importing dotenv...")
from dotenv import load_dotenv

print("Loading dotenv...")
# Load environment variables
load_dotenv()
print("Dotenv loaded.")

# Use local debug copy to avoid locks
DATABASE_URL = 'sqlite:///debug_app_database.db'
# if not DATABASE_URL:
#     print("Error: DATABASE_URL not found in environment variables")
#     sys.exit(1)

engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()

def debug_pitch_matching():
    print("--- Starting Pitch Matching Debug ---")
    
    # 1. Get Organization and Sheet URL
    # Assuming we want to debug for the first organization found, or a specific one if known
    # In a real scenario, we'd filter by the user's org.
    org = session.query(Organization).first()
    if not org:
        print("Error: No organization found in database.")
        return

    print(f"Organization: {org.name} (ID: {org.id})")
    
    weekly_sheet_url = org.settings.get('weekly_sheet_url') if org.settings else None
    if not weekly_sheet_url:
        print("Error: No weekly_sheet_url found in organization settings.")
        return
        
    print(f"Weekly Sheet URL: {weekly_sheet_url}")

    # 2. Fetch Pitches from DB
    pitches = session.query(Pitch).filter_by(organization_id=org.id).all()
    print(f"\nFound {len(pitches)} pitches in database:")
    for p in pitches:
        print(f" - ID: {p.id}, Name: '{p.name}'")

    # 3. Fetch Sheet Data
    # try:
    #     print("\nFetching sheet data...")
    #     rows = fetch_google_sheet_csv(weekly_sheet_url)
    #     print(f"Fetched {len(rows)} rows.")
    # except Exception as e:
    #     print(f"Error fetching sheet: {e}")
    #     return
    
    print("\nSkipping live fetch to avoid hang. Using mock rows based on common pitch names.")
    rows = [
        {'team': 'U12', 'opposition': 'Opp1', 'pitch': 'Withdean Stadium', 'home_away': 'Home'},
        {'team': 'U13', 'opposition': 'Opp2', 'pitch': 'Stanley Deason 3G', 'home_away': 'Home'},
        {'team': 'U14', 'opposition': 'Opp3', 'pitch': 'Waterhall Pitch 1', 'home_away': 'Home'},
        {'team': 'U15', 'opposition': 'Opp4', 'pitch': 'Patcham High School', 'home_away': 'Home'},
        {'team': 'U16', 'opposition': 'Opp5', 'pitch': 'Unknown Pitch', 'home_away': 'Home'},
        {'team': 'U11', 'opposition': 'Opp6', 'pitch': '', 'home_away': 'Home'}, # Should match default
        {'team': 'U10', 'opposition': 'Opp7', 'pitch': '3G', 'home_away': 'Home'},
    ]

    # 4. Simulate Matching
    print("\n--- Simulating Pitch Matching ---")
    
    unmatched_pitches = set()
    
    for i, row in enumerate(rows, start=2):
        fixture = parse_fixture_from_row(row)
        if not fixture:
            continue
            
        pitch_name = fixture.get('pitch', '').strip()
        team_name = fixture.get('team', 'Unknown')
        opp_name = fixture.get('opposition', 'Unknown')
        
        print(f"\nRow {i}: {team_name} vs {opp_name}")
        print(f"  Sheet Pitch Name: '{pitch_name}'")
        
        if not pitch_name:
            print("  -> No pitch specified in sheet.")
            continue

        # --- Matching Logic (copied from routes/settings.py) ---
        pitch = None
        
        # Special handling for home games
        home_away = fixture.get('home_away', 'Home')
        if home_away.lower() == 'home' and not pitch_name:
             default_pitches = ['3g', 'withdean', 'stanley deason', 'balfour', 'dorothy stringer', 'varndean']
             for dp in default_pitches:
                 default_pitch = session.query(Pitch).filter(
                     Pitch.organization_id == org.id,
                     Pitch.name.ilike(f'%{dp}%')
                 ).first()
                 if default_pitch:
                     pitch = default_pitch
                     print(f"  -> Matched Default Home Pitch: '{pitch.name}'")
                     break
        
        if pitch_name:
            exact_match = None
            partial_match = None
            fuzzy_matches = []
            
            pitch_lower = pitch_name.lower().strip()
            
            for p in pitches:
                pitch_db_lower = p.name.lower().strip()
                
                # Exact match
                if pitch_db_lower == pitch_lower:
                    exact_match = p
                    break
                
                # Partial match
                elif pitch_db_lower in pitch_lower or pitch_lower in pitch_db_lower:
                    partial_match = p
                    continue
                    
                # Fuzzy matching
                p_words = set(pitch_db_lower.split())
                fixture_words = set(pitch_lower.split())
                word_intersect = p_words.intersection(fixture_words)
                
                if word_intersect and len(word_intersect) >= max(1, min(len(p_words), len(fixture_words)) * 0.5):
                    fuzzy_matches.append((p, len(word_intersect)))
                
                # Abbreviations
                if "3g" in pitch_lower and "3g" in pitch_db_lower:
                    partial_match = p
                if any(word in pitch_lower for word in ["college", "coll", "col"]) and \
                   any(word in pitch_db_lower for word in ["college", "coll", "col"]):
                    partial_match = p

            if exact_match:
                pitch = exact_match
                print(f"  -> Exact Match: '{pitch.name}'")
            elif partial_match:
                pitch = partial_match
                print(f"  -> Partial Match: '{pitch.name}'")
            elif fuzzy_matches:
                pitch = max(fuzzy_matches, key=lambda x: x[1])[0]
                print(f"  -> Fuzzy Match: '{pitch.name}'")
            
            if not pitch:
                print(f"  -> NO MATCH FOUND for '{pitch_name}'")
                unmatched_pitches.add(pitch_name)

    if unmatched_pitches:
        print("\n--- Summary of Unmatched Pitches ---")
        for p in sorted(unmatched_pitches):
            print(f" - '{p}'")
    else:
        print("\nAll pitches matched successfully!")

if __name__ == "__main__":
    try:
        debug_pitch_matching()
    finally:
        session.close()
