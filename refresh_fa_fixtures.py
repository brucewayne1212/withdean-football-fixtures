"""
Periodic refresh of FA fixtures for teams with configured FA URLs
This can be run as a scheduled task (cron job, background worker, etc.)
"""

import os
import sys
import logging
import time
import re
from datetime import datetime, timedelta
from typing import List, Optional
import traceback

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
from models import DatabaseManager, Team, Fixture, Organization, Task
from fa_fixtures_scraper import scrape_team_fixtures, FAFixturesScraper
from uuid import UUID

# Load environment variables
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_teams_with_fa_urls():
    """Get all teams that have FA fixtures URLs configured"""
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL environment variable is required")
    
    db_manager = DatabaseManager(database_url)
    session = db_manager.get_session()
    
    try:
        teams = session.query(Team).filter(
            Team.fa_fixtures_url.isnot(None),
            Team.fa_fixtures_url != ''
        ).all()
        
        logger.info(f"Found {len(teams)} teams with FA URLs configured")
        return teams
    except Exception as e:
        logger.error(f"Error fetching teams with FA URLs: {e}")
        return []
    finally:
        session.close()


def create_or_update_fixture(session, org_id: str, team_id: str, fixture_data: dict) -> Optional[Fixture]:
    """
    Create or update a fixture from scraped data
    
    Args:
        session: Database session
        org_id: Organization ID
        team_id: Team ID
        fixture_data: Fixture data dictionary
        
    Returns:
        Created or updated Fixture object, or None if failed
    """
    try:
        from uuid import UUID
        team_uuid = UUID(team_id)
        
        # Look for existing fixture by date and teams
        # The Fixture model uses kickoff_datetime
        if 'date' in fixture_data and fixture_data['date']:
            kickoff_datetime = fixture_data['date']
            
            # Handle different date formats
            if isinstance(kickoff_datetime, str):
                try:
                    # Try ISO format first
                    kickoff_datetime = datetime.fromisoformat(kickoff_datetime.replace('Z', '+00:00'))
                except:
                    try:
                        # Try date only format
                        kickoff_datetime = datetime.strptime(kickoff_datetime, '%Y-%m-%d')
                    except:
                        logger.warning(f"Could not parse date: {fixture_data['date']}")
                        return None
            elif isinstance(kickoff_datetime, datetime):
                # Already a datetime object, use as is
                pass
            else:
                logger.warning(f"Unexpected date type: {type(kickoff_datetime)}")
                return None
            
            # Ensure datetime is timezone-aware (UTC)
            if kickoff_datetime.tzinfo is None:
                from datetime import timezone as tz
                kickoff_datetime = kickoff_datetime.replace(tzinfo=tz.utc)
            
            # Simple logic: first team (home_team) = home, second team (away_team) = away
            # Determine which team is the managed team and set home_away accordingly
            home_away = None
            opposition_name = None
            
            team = session.query(Team).filter_by(id=team_uuid).first()
            if not team:
                logger.warning(f"Team not found: {team_id}")
                return None
            
            # Get team names and location
            home_team = fixture_data.get('home_team', '').strip()
            away_team = fixture_data.get('away_team', '').strip()
            location = fixture_data.get('location', '').strip() or fixture_data.get('competition', '').strip()  # Location field
            
            # IMPORTANT: The location field is NOT the opponent!
            # FA format: Home Team | VS | Away Team | Location
            # Location can be another age group name (e.g., "Withdean Youth U11 White") which is the venue
            # We should ONLY use home_team and away_team when determining opponents
            # Location is stored separately and NOT used for opponent identification
            
            # Validate that we have both home and away teams
            if not home_team or not away_team:
                logger.warning(f"Missing team names in fixture data: home={home_team}, away={away_team}")
                return None
            
            # Clean team names to extract just the core team identifier
            # Remove common prefixes like "Withdean Youth" if present
            def clean_team_name(name):
                """Remove common prefixes to get just the team identifier (e.g., 'U14 White')"""
                if not name:
                    return ""
                name = name.strip()
                # Remove "Withdean Youth" prefix if present
                name = re.sub(r'^Withdean\s+Youth\s+', '', name, flags=re.IGNORECASE)
                name = re.sub(r'^Withdean\s+', '', name, flags=re.IGNORECASE)
                # Also remove duplicate team names (FA sometimes duplicates)
                # Split by multiple spaces and take first meaningful part
                parts = re.split(r'\s{2,}', name)
                if parts:
                    name = parts[0].strip()
                return name.strip()
            
            # Extract just the team identifier (e.g., "U14 White" from "Withdean Youth U14 White")
            def extract_team_identifier(name):
                """Extract the core team identifier like 'U14 White'"""
                if not name:
                    return ""
                # Pattern: U\d+ followed by optional color
                match = re.search(r'(U\d+\s*(?:Black|White|Red|Blue|Green)?)', name, re.IGNORECASE)
                if match:
                    return match.group(1).strip()
                # Fallback: clean and return
                return clean_team_name(name)
            
            # Clean both team names for comparison
            home_team_clean = clean_team_name(home_team)
            away_team_clean = clean_team_name(away_team)
            team_name_clean = clean_team_name(team.name)
            
            # Get team identifiers for better matching
            home_id = extract_team_identifier(home_team)
            away_id = extract_team_identifier(away_team)
            team_id = extract_team_identifier(team.name)
            
            # Check if managed team is home or away using exact or better matching
            # First try exact match on cleaned names
            # Then try if cleaned team name is contained in the cleaned fixture team name
            # But avoid substring matches like "U14 White" matching "U14 White" within longer names
            
            home_away = None
            opposition_name = None
            
            # Check if managed team matches home team using identifier
            # Compare using the team identifier (e.g., "U14 White")
            home_match = (
                team_id.lower() == home_id.lower() if (team_id and home_id) else False
            ) or (
                team_name_clean.lower() == home_team_clean.lower()
            ) or (
                team_name_clean.lower() in home_team_clean.lower() and len(team_name_clean) >= 5
            )
            
            # Check if managed team matches away team using identifier
            away_match = (
                team_id.lower() == away_id.lower() if (team_id and away_id) else False
            ) or (
                team_name_clean.lower() == away_team_clean.lower()
            ) or (
                team_name_clean.lower() in away_team_clean.lower() and len(team_name_clean) >= 5
            )
            
            if home_match and not away_match:
                # Managed team is home
                home_away = 'Home'
                # Use the away team as opposition, but clean it
                opposition_name = clean_team_name(away_team)
            elif away_match and not home_match:
                # Managed team is away
                home_away = 'Away'
                # Use the home team as opposition, but clean it
                opposition_name = clean_team_name(home_team)
            elif home_match and away_match:
                # Both teams match - this shouldn't happen, but handle it
                # This can happen when both teams have similar names (e.g., U14 White vs U11 White)
                # Use the team identifier to distinguish
                logger.warning(f"Both teams match managed team '{team.name}'. Using team identifier to distinguish.")
                if team_id and team_id.lower() == home_id.lower():
                    home_away = 'Home'
                    opposition_name = clean_team_name(away_team)
                elif team_id and team_id.lower() == away_id.lower():
                    home_away = 'Away'
                    opposition_name = clean_team_name(home_team)
                else:
                    # Fallback: use first team as home
                    logger.warning(f"Using fallback: assuming managed team is home")
                    home_away = 'Home'
                    opposition_name = clean_team_name(away_team)
            else:
                # Neither team matches clearly - this is unexpected for FA fixtures
                logger.warning(f"Could not identify managed team '{team.name}' in fixture: {home_team} vs {away_team}")
                # Try fuzzy matching
                if team_id:
                    if team_id.lower() in home_id.lower() if home_id else False:
                        home_away = 'Home'
                        opposition_name = clean_team_name(away_team)
                    elif team_id.lower() in away_id.lower() if away_id else False:
                        home_away = 'Away'
                        opposition_name = clean_team_name(home_team)
                    else:
                        # Last resort: assume home
                        home_away = 'Home'
                        opposition_name = clean_team_name(away_team)
                else:
                    home_away = 'Home'
                    opposition_name = clean_team_name(away_team)
            
            # Final cleanup of opposition name - remove any "Withdean" references
            if opposition_name:
                # Remove "Withdean Youth" prefix if it somehow got included
                opposition_name = re.sub(r'^Withdean\s+Youth\s+', '', opposition_name, flags=re.IGNORECASE)
                opposition_name = re.sub(r'^Withdean\s+', '', opposition_name, flags=re.IGNORECASE)
                # Remove duplicate team name references
                parts = re.split(r'\s{2,}', opposition_name)
                if parts:
                    opposition_name = parts[0].strip()
                # Remove any remaining extra spaces
                opposition_name = re.sub(r'\s+', ' ', opposition_name).strip()
            
            # Validate opposition name
            if not opposition_name:
                logger.warning(f"Opposition name is empty after cleaning")
                return None
            
            # CRITICAL: Make sure we didn't accidentally use location as opponent
            # Check if opposition name matches the location (should never happen)
            if location:
                location_clean = clean_team_name(location)
                opposition_clean = clean_team_name(opposition_name)
                if opposition_clean.lower() == location_clean.lower():
                    logger.error(f"Opposition name '{opposition_name}' matches location '{location}' - this should not happen!")
                    logger.error(f"  home_team: {home_team}, away_team: {away_team}, location: {location}")
                    logger.error(f"  This suggests parsing error - skipping fixture")
                    return None
            
            # Check if opposition name is the same as managed team (shouldn't happen)
            opposition_clean = clean_team_name(opposition_name)
            if opposition_clean.lower() == team_name_clean.lower() or (team_id and extract_team_identifier(opposition_name).lower() == team_id.lower()):
                logger.warning(f"Opposition name '{opposition_name}' matches managed team '{team.name}' - skipping")
                return None
            
            # Find existing fixture by kickoff_datetime and team
            existing = session.query(Fixture).filter(
                Fixture.organization_id == UUID(org_id),
                Fixture.team_id == team_uuid,
                Fixture.kickoff_datetime == kickoff_datetime
            ).first()
            
            if existing:
                # Update existing fixture
                if opposition_name:
                    existing.opposition_name = opposition_name
                # Update datetime - preserve time from parsed datetime
                existing.kickoff_datetime = kickoff_datetime  # This includes the time!
                # Update time text - use provided time or default to TBC
                kickoff_time = fixture_data.get('kickoff_time', 'TBC')
                if not kickoff_time or kickoff_time.strip() == '':
                    kickoff_time = 'TBC'
                existing.kickoff_time_text = kickoff_time
                existing.home_away = home_away
                if location:
                    existing.instructions = location  # Store location in instructions field
                existing.updated_at = datetime.now(timezone.utc)
                logger.debug(f"Updated fixture for {kickoff_datetime}")
                return existing
            else:
                # Create new fixture
                # Get kickoff time, default to TBC if not provided
                kickoff_time = fixture_data.get('kickoff_time', 'TBC')
                if not kickoff_time or kickoff_time.strip() == '':
                    kickoff_time = 'TBC'
                
                fixture = Fixture(
                    organization_id=UUID(org_id),
                    team_id=team_uuid,
                    kickoff_datetime=kickoff_datetime,  # This includes the time if parsed correctly
                    opposition_name=opposition_name,
                    home_away=home_away,
                    kickoff_time_text=kickoff_time,
                    instructions=location if location else None,  # Store location in instructions field
                )
                session.add(fixture)
                logger.debug(f"Created new fixture for {kickoff_datetime}")
                return fixture
        else:
            logger.warning("Fixture data missing date, skipping")
            return None
            
    except Exception as e:
        logger.error(f"Error creating/updating fixture: {e}")
        logger.debug(traceback.format_exc())
        return None


def refresh_team_fixtures(team: Team, headless: bool = True) -> dict:
    """
    Refresh fixtures for a single team
    
    Args:
        team: Team object with fa_fixtures_url
        headless: Whether to run scraper in headless mode
        
    Returns:
        Dictionary with results
    """
    result = {
        'team_name': team.name,
        'team_id': str(team.id),
        'success': False,
        'fixtures_found': 0,
        'fixtures_created': 0,
        'fixtures_updated': 0,
        'error': None
    }
    
    if not team.fa_fixtures_url:
        result['error'] = "No FA URL configured"
        return result
    
    logger.info(f"Refreshing fixtures for team: {team.name}")
    
    try:
        # Scrape fixtures
        scraped_fixtures = scrape_team_fixtures(
            team.fa_fixtures_url,
            team_name=team.name,
            headless=headless
        )
        
        result['fixtures_found'] = len(scraped_fixtures)
        logger.info(f"Scraped {len(scraped_fixtures)} fixtures for {team.name}")
        
        if not scraped_fixtures:
            result['success'] = True
            result['error'] = "No fixtures found on page"
            return result
        
        # Save fixtures to database
        database_url = os.environ.get('DATABASE_URL')
        if not database_url:
            raise ValueError("DATABASE_URL environment variable is required")
        
        db_manager = DatabaseManager(database_url)
        session = db_manager.get_session()
        
        try:
            org_id = str(team.organization_id)
            team_id = str(team.id)
            
            for fixture_data in scraped_fixtures:
                fixture = create_or_update_fixture(session, org_id, team_id, fixture_data)
                if fixture:
                    # Check if fixture has tasks, create if missing
                    from models import Task
                    existing_task = session.query(Task).filter_by(
                        fixture_id=fixture.id
                    ).first()
                    
                    if not existing_task:
                        # Create task for this fixture
                        task_type = 'home_email' if fixture.home_away == 'Home' else 'away_email'
                        task_status = 'pending' if fixture.home_away == 'Home' else 'waiting'
                        
                        new_task = Task(
                            organization_id=UUID(org_id),
                            fixture_id=fixture.id,
                            task_type=task_type,
                            status=task_status
                        )
                        session.add(new_task)
                        logger.debug(f"Created task for fixture {fixture.id}")
                    
                    if fixture.created_at == fixture.updated_at:
                        result['fixtures_created'] += 1
                    else:
                        result['fixtures_updated'] += 1
            
            session.commit()
            result['success'] = True
            logger.info(f"Successfully saved fixtures for {team.name}: {result['fixtures_created']} created, {result['fixtures_updated']} updated")
            
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()
            
    except Exception as e:
        result['error'] = str(e)
        logger.error(f"Error refreshing fixtures for {team.name}: {e}")
        logger.debug(traceback.format_exc())
    
    return result


def refresh_all_teams_fixtures(headless: bool = True) -> List[dict]:
    """
    Refresh fixtures for all teams with FA URLs configured
    
    Args:
        headless: Whether to run scraper in headless mode
        
    Returns:
        List of result dictionaries
    """
    teams = get_teams_with_fa_urls()
    
    if not teams:
        logger.info("No teams with FA URLs configured")
        return []
    
    results = []
    
    for team in teams:
        result = refresh_team_fixtures(team, headless=headless)
        results.append(result)
        
        # Add a small delay between teams to avoid overwhelming the server
        time.sleep(2)
    
    # Summary
    total_success = sum(1 for r in results if r['success'])
    total_fixtures = sum(r['fixtures_found'] for r in results)
    total_created = sum(r['fixtures_created'] for r in results)
    total_updated = sum(r['fixtures_updated'] for r in results)
    
    logger.info(f"Refresh completed: {total_success}/{len(teams)} teams successful, "
                f"{total_fixtures} fixtures found, {total_created} created, {total_updated} updated")
    
    return results


def refresh_club_fixtures(organization: Organization, club_url: str, headless: bool = True) -> dict:
    """
    Refresh fixtures from a club-wide URL and match them to managed teams
    
    Args:
        organization: Organization object
        club_url: URL containing all club fixtures
        headless: Whether to run scraper in headless mode
        
    Returns:
        Dictionary with results
    """
    result = {
        'success': False,
        'total_fixtures': 0,
        'fixtures_imported': 0,
        'teams_matched': [],
        'error': None
    }
    
    logger.info(f"Refreshing club fixtures for organization: {organization.name}")
    
    try:
        # Scrape all fixtures from the club URL
        scraped_fixtures = scrape_team_fixtures(
            club_url,
            team_name=None,  # No specific team - scrape all
            headless=headless
        )
        
        result['total_fixtures'] = len(scraped_fixtures)
        logger.info(f"Scraped {len(scraped_fixtures)} fixtures from club URL")
        
        if not scraped_fixtures:
            result['success'] = True
            result['error'] = "No fixtures found on page"
            return result
        
        # Get all managed teams for this organization
        database_url = os.environ.get('DATABASE_URL')
        if not database_url:
            raise ValueError("DATABASE_URL environment variable is required")
        
        db_manager = DatabaseManager(database_url)
        session = db_manager.get_session()
        
        try:
            managed_teams = session.query(Team).filter_by(
                organization_id=organization.id,
                is_managed=True
            ).all()
            
            logger.info(f"Found {len(managed_teams)} managed teams to match against")
            
            if not managed_teams:
                result['error'] = "No managed teams found"
                return result
            
            org_id = str(organization.id)
            
            # Helper function to extract team identifier
            def extract_team_identifier(name):
                if not name:
                    return ""
                match = re.search(r'(U\d+\s*(?:Black|White|Red|Blue|Green)?)', name, re.IGNORECASE)
                if match:
                    return match.group(1).strip().lower()
                return name.lower()
            
            def clean_team_name(name):
                if not name:
                    return ""
                name = name.strip()
                name = re.sub(r'^Withdean\s+Youth\s+', '', name, flags=re.IGNORECASE)
                name = re.sub(r'^Withdean\s+', '', name, flags=re.IGNORECASE)
                parts = re.split(r'\s{2,}', name)
                if parts:
                    name = parts[0].strip()
                return name.strip()
            
            # Match each fixture to a managed team
            matched_teams = set()
            
            for fixture_data in scraped_fixtures:
                home_team = fixture_data.get('home_team', '').strip()
                away_team = fixture_data.get('away_team', '').strip()
                
                # Try to match against each managed team
                matched_team = None
                
                for team in managed_teams:
                    team_name_clean = clean_team_name(team.name)
                    team_id = extract_team_identifier(team.name)
                    
                    home_team_clean = clean_team_name(home_team)
                    away_team_clean = clean_team_name(away_team)
                    
                    home_id = extract_team_identifier(home_team)
                    away_id = extract_team_identifier(away_team)
                    
                    # Check if managed team matches home or away team
                    home_match = (
                        team_id == home_id if (team_id and home_id) else False
                    ) or (
                        team_name_clean.lower() == home_team_clean.lower()
                    ) or (
                        team_name_clean.lower() in home_team_clean.lower() and len(team_name_clean) >= 5
                    )
                    
                    away_match = (
                        team_id == away_id if (team_id and away_id) else False
                    ) or (
                        team_name_clean.lower() == away_team_clean.lower()
                    ) or (
                        team_name_clean.lower() in away_team_clean.lower() and len(team_name_clean) >= 5
                    )
                    
                    if home_match or away_match:
                        matched_team = team
                        matched_teams.add(team.name)
                        break
                
                # If matched, create/update fixture for that team
                if matched_team:
                    fixture = create_or_update_fixture(session, org_id, str(matched_team.id), fixture_data)
                    if fixture:
                        # Check if fixture has tasks, create if missing
                        from models import Task
                        existing_task = session.query(Task).filter_by(
                            fixture_id=fixture.id
                        ).first()
                        
                        if not existing_task:
                            # Create task for this fixture
                            task_type = 'home_email' if fixture.home_away == 'Home' else 'away_email'
                            task_status = 'pending' if fixture.home_away == 'Home' else 'waiting'
                            
                            new_task = Task(
                                organization_id=UUID(org_id),
                                fixture_id=fixture.id,
                                task_type=task_type,
                                status=task_status
                            )
                            session.add(new_task)
                            logger.debug(f"Created task for fixture {fixture.id}")
                        
                        if fixture.created_at == fixture.updated_at:
                            result['fixtures_imported'] += 1
            
            session.commit()
            result['teams_matched'] = sorted(list(matched_teams))
            result['success'] = True
            logger.info(f"Successfully imported {result['fixtures_imported']} fixtures for {len(matched_teams)} teams")
            
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()
            
    except Exception as e:
        result['error'] = str(e)
        logger.error(f"Error refreshing club fixtures: {e}")
        logger.debug(traceback.format_exc())
    
    return result


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Refresh FA fixtures for configured teams')
    parser.add_argument('--team-name', help='Refresh fixtures for specific team only')
    parser.add_argument('--headless', action='store_true', default=True, help='Run browser in headless mode')
    parser.add_argument('--no-headless', dest='headless', action='store_false', help='Run browser with GUI (for CAPTCHA solving)')
    
    args = parser.parse_args()
    
    if args.team_name:
        # Refresh specific team
        teams = get_teams_with_fa_urls()
        team = next((t for t in teams if t.name == args.team_name), None)
        
        if team:
            result = refresh_team_fixtures(team, headless=args.headless)
            print(f"Result: {result}")
        else:
            print(f"Team '{args.team_name}' not found or has no FA URL configured")
    else:
        # Refresh all teams
        results = refresh_all_teams_fixtures(headless=args.headless)
        for result in results:
            print(f"{result['team_name']}: {result['success']} - {result['fixtures_found']} fixtures found")

