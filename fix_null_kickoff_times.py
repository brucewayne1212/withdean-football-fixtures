#!/usr/bin/env python3
"""
Fix fixtures with NULL kickoff_datetime values
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models import DatabaseManager, Fixture, Task
from sqlalchemy import text
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database setup
DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is required. Please set it in your environment or .env file.")
db_manager = DatabaseManager(DATABASE_URL)

def fix_null_kickoff_times():
    """Fix fixtures with NULL kickoff_datetime by setting reasonable default times"""
    print("Fixing fixtures with NULL kickoff_datetime...")

    session = db_manager.get_session()
    try:
        # Get fixtures with NULL kickoff_datetime
        fixtures_to_fix = session.query(Fixture).filter(
            Fixture.kickoff_datetime.is_(None)
        ).all()

        print(f"Found {len(fixtures_to_fix)} fixtures with NULL kickoff times")

        if not fixtures_to_fix:
            print("No fixtures need fixing!")
            return

        # Set default kickoff times based on next few Sundays
        next_sunday = get_next_sunday()
        default_time_10am = datetime.strptime("10:00", "%H:%M").time()
        default_time_2pm = datetime.strptime("14:00", "%H:%M").time()

        fixed_count = 0
        for i, fixture in enumerate(fixtures_to_fix):
            # Alternate between 10:00 AM and 2:00 PM
            default_time = default_time_10am if i % 2 == 0 else default_time_2pm

            # Spread fixtures across next 4 Sundays
            sunday_offset = i % 4
            fixture_sunday = next_sunday + timedelta(weeks=sunday_offset)

            # Combine date and time
            fixture.kickoff_datetime = datetime.combine(fixture_sunday.date(), default_time)

            fixed_count += 1
            print(f"  Fixed fixture {fixture.id}: {fixture.opposition_name} -> {fixture.kickoff_datetime}")

        session.commit()
        print(f"✅ Successfully fixed {fixed_count} fixtures!")

    except Exception as e:
        session.rollback()
        print(f"❌ Error fixing fixtures: {e}")
        raise
    finally:
        session.close()

def get_next_sunday(from_date: datetime = None) -> datetime:
    """Get the next Sunday from the given date (or today)"""
    if from_date is None:
        from_date = datetime.now()

    # Calculate days until next Sunday (0=Monday, 6=Sunday)
    days_ahead = 6 - from_date.weekday()
    if days_ahead <= 0:  # Target day already happened this week
        days_ahead += 7

    next_sunday = from_date + timedelta(days=days_ahead)
    return next_sunday.replace(hour=0, minute=0, second=0, microsecond=0)

if __name__ == "__main__":
    fix_null_kickoff_times()