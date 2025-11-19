from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime, timezone
import os
import tempfile
import io
import csv
import logging
import re

from database import db_manager
from utils import get_user_organization, allowed_file
from models import Team, Pitch, Fixture, Task, TeamCoach, get_or_create_team

# Local imports
from fixture_parser import FixtureParser
from fa_fixture_parser import FAFixtureParser
from text_fixture_parser import parse_fixture_text, TextFixtureParser
from google_sheets_helper import GoogleSheetsImporter

# Setup logger
logger = logging.getLogger(__name__)

imports_bp = Blueprint('imports', __name__)

def _analyze_column_content(column_name, sample_rows):
    """
    Analyze column content to detect email/phone patterns
    Returns tuple of (field_type, confidence_score) or None
    """
    email_pattern = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
    phone_patterns = [
        re.compile(r'\b\d{11}\b'),  # 07123456789
        re.compile(r'\b\d{3}\s?\d{4}\s?\d{4}\b'),  # 071 2345 6789
        re.compile(r'\b\+44\s?\d{10}\b'),  # +44 7123456789
        re.compile(r'\b0\d{4}\s?\d{6}\b'),  # 01234 567890 (landline)
        re.compile(r'\b\(\d{4}\)\s?\d{6}\b'),  # (01234) 567890
    ]

    email_count = 0
    phone_count = 0
    total_values = 0

    for row in sample_rows:
        value = str(row.get(column_name, '')).strip()
        if value:
            total_values += 1

            # Check for email pattern
            if email_pattern.search(value):
                email_count += 1

            # Check for phone patterns
            elif any(pattern.search(value) for pattern in phone_patterns):
                phone_count += 1

    if total_values == 0:
        return None

    email_ratio = email_count / total_values
    phone_ratio = phone_count / total_values

    # Return the field type with highest confidence if above threshold
    if email_ratio >= 0.7:
        return ('email', min(95, 70 + int(email_ratio * 25)))
    elif phone_ratio >= 0.7:
        return ('phone', min(95, 70 + int(phone_ratio * 25)))

    return None

def analyze_csv_columns(csv_data):
    """
    Analyze CSV columns and attempt to map them to expected fields

    Returns:
        dict with analysis results including suggested mappings
    """
    try:
        csv_file = io.StringIO(csv_data.strip())
        reader = csv.DictReader(csv_file)

        # Get the headers from the CSV
        headers = list(reader.fieldnames) if reader.fieldnames else []

        # Read first few rows to get sample data
        sample_rows = []
        for i, row in enumerate(reader):
            if i >= 3:  # Only get first 3 rows for preview
                break
            sample_rows.append(row)

        # Define mapping patterns for automatic detection
        field_patterns = {
            'team_name': ['team_name', 'team', 'team name', 'club', 'club_name', 'squad'],
            'coach_name': ['coach_name', 'coach', 'name', 'coach name', 'full_name', 'fullname', 'manager'],
            'email': ['email', 'email_address', 'e-mail', 'mail', 'contact_email'],
            'phone': ['phone', 'phone_number', 'mobile', 'cell', 'telephone', 'contact_number'],
            'role': ['role', 'position', 'title', 'job_title', 'coach_role'],
            'notes': ['notes', 'comments', 'description', 'additional_info', 'remarks']
        }

        # Attempt automatic mapping
        suggested_mapping = {}
        confidence_scores = {}

        for header in headers:
            header_lower = header.lower().strip()
            best_match = None
            best_score = 0

            # First try header name matching
            for field, patterns in field_patterns.items():
                for pattern in patterns:
                    if pattern == header_lower:
                        # Exact match
                        score = 100
                    elif pattern in header_lower or header_lower in pattern:
                        # Partial match
                        score = 70
                    else:
                        continue

                    if score > best_score:
                        best_score = score
                        best_match = field

            # If no good header match, try content pattern matching for email/phone
            if best_score < 90 and sample_rows:
                content_scores = _analyze_column_content(header, sample_rows)
                if content_scores:
                    field, score = content_scores
                    if score > best_score:
                        best_score = score
                        best_match = field

            if best_match and best_score >= 70:
                suggested_mapping[header] = best_match
                confidence_scores[header] = best_score

        # Check if we have the required fields
        mapped_fields = set(suggested_mapping.values())
        required_fields = {'team_name', 'coach_name'}
        has_required = required_fields.issubset(mapped_fields)

        # Calculate overall confidence
        if suggested_mapping:
            avg_confidence = sum(confidence_scores.values()) / len(confidence_scores)
        else:
            avg_confidence = 0

        return {
            'headers': headers,
            'sample_rows': sample_rows,
            'suggested_mapping': suggested_mapping,
            'confidence_scores': confidence_scores,
            'has_required_fields': has_required,
            'missing_required': required_fields - mapped_fields,
            'overall_confidence': avg_confidence,
            'needs_manual_mapping': not has_required or avg_confidence < 80
        }

    except Exception as e:
        return {
            'error': f'CSV analysis error: {str(e)}',
            'needs_manual_mapping': True
        }

def process_coach_csv(session, organization_id, csv_data, update_existing=False, column_mapping=None):
    """
    Process CSV data for bulk coach upload

    Args:
        session: Database session
        organization_id: Organization UUID
        csv_data: CSV string data
        update_existing: Whether to update existing coaches

    Returns:
        dict with success status, counts, and errors
    """
    result = {
        'success': True,
        'created': 0,
        'updated': 0,
        'errors': [],
        'message': '',
        'needs_mapping': False
    }

    try:
        # Parse CSV data
        csv_file = io.StringIO(csv_data.strip())
        reader = csv.DictReader(csv_file)

        # If no column mapping provided, try automatic detection
        if column_mapping is None:
            analysis = analyze_csv_columns(csv_data)
            if analysis.get('needs_manual_mapping'):
                result['needs_mapping'] = True
                result['analysis'] = analysis
                return result
            column_mapping = analysis['suggested_mapping']

        # Create reverse mapping (original_header -> our_field)
        reverse_mapping = {v: k for k, v in column_mapping.items()}

        # Get all teams for this organization for lookup
        teams = session.query(Team).filter_by(organization_id=organization_id).all()
        team_lookup = {team.name.lower().strip(): team for team in teams}

        # Track which teams are referenced
        referenced_teams = set()

        # Process each row
        for row_num, row in enumerate(reader, start=2):  # Start at 2 since row 1 is headers
            try:
                # Extract fields using column mapping
                team_name = ''
                coach_name = ''
                email = None
                phone = None
                role = 'Coach'
                notes = None

                # Map the fields from the row using our column mapping
                for csv_header, our_field in column_mapping.items():
                    value = row.get(csv_header, '').strip()
                    if our_field == 'team_name':
                        team_name = value
                    elif our_field == 'coach_name':
                        coach_name = value
                    elif our_field == 'email':
                        email = value or None
                    elif our_field == 'phone':
                        phone = value or None
                    elif our_field == 'role':
                        role = value or 'Coach'
                    elif our_field == 'notes':
                        notes = value or None

                if not team_name or not coach_name:
                    result['errors'].append({
                        'row': row_num,
                        'message': 'Missing required fields: team_name and coach_name are required'
                    })
                    continue

                # Find team
                team_key = team_name.lower().strip()
                team = team_lookup.get(team_key)

                if not team:
                    result['errors'].append({
                        'row': row_num,
                        'message': f'Team "{team_name}" not found. Make sure it matches exactly.'
                    })
                    continue

                referenced_teams.add(team.name)

                # Check if coach already exists for this team
                existing_coach = session.query(TeamCoach).filter_by(
                    organization_id=organization_id,
                    team_id=team.id,
                    coach_name=coach_name
                ).first()

                if existing_coach:
                    if update_existing:
                        # Update existing coach
                        existing_coach.email = email
                        existing_coach.phone = phone
                        existing_coach.role = role
                        existing_coach.notes = notes
                        existing_coach.updated_at = datetime.utcnow()
                        result['updated'] += 1
                    else:
                        result['errors'].append({
                            'row': row_num,
                            'message': f'Coach "{coach_name}" already exists for team "{team_name}". Check "Update existing" to modify.'
                        })
                        continue
                else:
                    # Create new coach
                    new_coach = TeamCoach(
                        organization_id=organization_id,
                        team_id=team.id,
                        coach_name=coach_name,
                        email=email,
                        phone=phone,
                        role=role,
                        notes=notes,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    )
                    session.add(new_coach)
                    result['created'] += 1

            except Exception as e:
                result['errors'].append({
                    'row': row_num,
                    'message': f'Error processing row: {str(e)}'
                })
                continue

        # Commit changes
        session.commit()

        # Set success message
        if result['errors']:
            result['success'] = False
            result['message'] = f'Processed with {len(result["errors"])} errors'
        else:
            result['message'] = 'All coaches processed successfully'

        if referenced_teams:
            result['message'] += f'. Teams updated: {", ".join(sorted(referenced_teams))}'

    except Exception as e:
        result['success'] = False
        result['message'] = f'CSV parsing error: {str(e)}'
        session.rollback()

    return result

def preview_coach_csv(csv_data, column_mapping):
    """
    Preview CSV data without saving - for confirmation step
    Returns parsed data for user review
    """
    preview_data = {
        'coaches': [],
        'teams': set(),
        'total_rows': 0,
        'errors': []
    }

    try:
        csv_file = io.StringIO(csv_data.strip())
        reader = csv.DictReader(csv_file)

        for row_num, row in enumerate(reader, start=2):
            preview_data['total_rows'] += 1

            # Extract fields using column mapping
            coach_data = {
                'row_num': row_num,
                'team_name': '',
                'coach_name': '',
                'email': '',
                'phone': '',
                'role': 'Coach',
                'notes': ''
            }

            # Map the fields from the row
            for csv_header, our_field in column_mapping.items():
                value = row.get(csv_header, '').strip()
                if our_field in coach_data:
                    coach_data[our_field] = value or coach_data[our_field]

            # Validate required fields
            if not coach_data['team_name'] or not coach_data['coach_name']:
                preview_data['errors'].append({
                    'row': row_num,
                    'message': 'Missing required fields: team_name and coach_name are required',
                    'data': coach_data
                })
                continue

            preview_data['coaches'].append(coach_data)
            preview_data['teams'].add(coach_data['team_name'])

    except Exception as e:
        preview_data['errors'].append({
            'row': 'Unknown',
            'message': f'CSV parsing error: {str(e)}',
            'data': {}
        })

    # Convert set to sorted list
    preview_data['teams'] = sorted(list(preview_data['teams']))

    return preview_data

def handle_manual_import(session, org, managed_team_names):
    """Handle manual fixture entry"""
    manual_team = request.form.get('manual_team', '').strip()
    manual_opposition = request.form.get('manual_opposition', '').strip()
    manual_home_away = request.form.get('manual_home_away', '').strip()
    manual_date = request.form.get('manual_date', '').strip()
    manual_time = request.form.get('manual_time', 'TBC').strip() or 'TBC'
    manual_pitch = request.form.get('manual_pitch', '').strip()
    
    if not all([manual_team, manual_opposition, manual_home_away, manual_date]):
        flash('Please fill in all required fields', 'error')
        return redirect(url_for('imports.import_fixtures'))
    
    # Get team
    team = session.query(Team).filter_by(
        organization_id=org.id,
        name=manual_team
    ).first()
    
    if not team:
        flash(f'Team "{manual_team}" not found', 'error')
        return redirect(url_for('imports.import_fixtures'))
    
    # Parse date
    try:
        if 'T' in manual_date:
            kickoff_datetime = datetime.fromisoformat(manual_date.replace('Z', '+00:00'))
        else:
            date_obj = datetime.strptime(manual_date, '%Y-%m-%d')
            # If time is provided, add it
            if manual_time and manual_time != 'TBC' and ':' in manual_time:
                hour, minute = manual_time.split(':')
                date_obj = date_obj.replace(hour=int(hour), minute=int(minute))
            kickoff_datetime = date_obj.replace(tzinfo=timezone.utc)
    except Exception as e:
        flash(f'Invalid date format: {str(e)}', 'error')
        return redirect(url_for('imports.import_fixtures'))
    
    # Get pitch if specified
    pitch = None
    if manual_pitch:
        pitch = session.query(Pitch).filter_by(
            organization_id=org.id,
            name=manual_pitch
        ).first()
    
    # Create fixture
    fixture = Fixture(
        organization_id=org.id,
        team_id=team.id,
        opposition_name=manual_opposition,
        home_away=manual_home_away,
        kickoff_datetime=kickoff_datetime,
        kickoff_time_text=manual_time,
        pitch_id=pitch.id if pitch else None
    )
    session.add(fixture)
    
    # Create task
    task_type = 'home_email' if manual_home_away == 'Home' else 'away_email'
    task_status = 'pending' if manual_home_away == 'Home' else 'waiting'
    task = Task(
        organization_id=org.id,
        fixture_id=fixture.id,
        task_type=task_type,
        status=task_status
    )
    session.add(task)
    
    session.commit()
    flash(f'Fixture added successfully for {manual_team}!', 'success')
    return redirect(url_for('imports.import_fixtures'))

def upload_file_internal(session, org, managed_team_names):
    """Internal handler for CSV upload"""
    if 'file' not in request.files:
        flash('No file selected', 'error')
        return redirect(url_for('imports.import_fixtures'))
    
    file = request.files['file']
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('imports.import_fixtures'))
    
    if not allowed_file(file.filename):
        flash('Invalid file type. Please upload CSV or Excel files only.', 'error')
        return redirect(url_for('imports.import_fixtures'))
    
    try:
        parser = FixtureParser()
        file_content = file.read()
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as temp_file:
            temp_file.write(file_content)
            temp_file_path = temp_file.name
        
        try:
            df = parser.read_spreadsheet(temp_file_path)
            if df.empty:
                flash('No data found in the uploaded file', 'error')
                return redirect(url_for('imports.import_fixtures'))
            
            fixtures_data = parser.get_fixture_data(df)
            
            new_fixtures = 0
            updated_fixtures = 0
            new_tasks = 0
            skipped_count = 0
            
            for fixture_data in fixtures_data:
                try:
                    team_name = fixture_data.get('team', '').strip() if fixture_data.get('team') else ''
                    if not team_name:
                        skipped_count += 1
                        continue
                    
                    home_away_raw = fixture_data.get('home_away', '').strip() if fixture_data.get('home_away') else ''
                    if not home_away_raw:
                        skipped_count += 1
                        continue
                    
                    # Normalize home_away
                    if home_away_raw.lower() in ['home', 'h']:
                        home_away = 'Home'
                    elif home_away_raw.lower() in ['away', 'a']:
                        home_away = 'Away'
                    else:
                        skipped_count += 1
                        continue
                    
                    # Get or create team
                    team = get_or_create_team(session, org.id, team_name)
                    
                    # Parse date - handle various formats
                    fixture_date = fixture_data.get('date') or fixture_data.get('kickoff_datetime') or fixture_data.get('fixture_date')
                    
                    if not fixture_date:
                        skipped_count += 1
                        continue
                    
                    kickoff_datetime = None
                    if isinstance(fixture_date, str):
                        try:
                            # Try ISO format
                            if 'T' in fixture_date:
                                kickoff_datetime = datetime.fromisoformat(fixture_date.replace('Z', '+00:00'))
                            # Try date format
                            else:
                                # Common formats
                                for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y']:
                                    try:
                                        kickoff_datetime = datetime.strptime(fixture_date, fmt).replace(tzinfo=timezone.utc)
                                        break
                                    except:
                                        continue
                                else:
                                    skipped_count += 1
                                    continue
                        except:
                            skipped_count += 1
                            continue
                    elif isinstance(fixture_date, datetime):
                        kickoff_datetime = fixture_date
                        if kickoff_datetime.tzinfo is None:
                            kickoff_datetime = kickoff_datetime.replace(tzinfo=timezone.utc)
                    else:
                        skipped_count += 1
                        continue
                    
                    # Check if fixture exists
                    existing = session.query(Fixture).filter(
                        Fixture.organization_id == org.id,
                        Fixture.team_id == team.id,
                        Fixture.kickoff_datetime == kickoff_datetime
                    ).first()
                    
                    if existing:
                        existing.opposition_name = fixture_data.get('opposition', existing.opposition_name) or 'TBC'
                        existing.home_away = home_away
                        existing.kickoff_time_text = fixture_data.get('time', existing.kickoff_time_text) or fixture_data.get('kickoff_time', 'TBC') or 'TBC'
                        updated_fixtures += 1
                        fixture = existing
                    else:
                        fixture = Fixture(
                            organization_id=org.id,
                            team_id=team.id,
                            opposition_name=fixture_data.get('opposition', 'TBC') or 'TBC',
                            home_away=home_away,
                            kickoff_datetime=kickoff_datetime,
                            kickoff_time_text=fixture_data.get('time', 'TBC') or fixture_data.get('kickoff_time', 'TBC') or 'TBC'
                        )
                        session.add(fixture)
                        session.flush()
                        new_fixtures += 1
                    
                    # Create task if doesn't exist
                    existing_task = session.query(Task).filter_by(fixture_id=fixture.id).first()
                    if not existing_task:
                        task_type = 'home_email' if home_away == 'Home' else 'away_email'
                        task_status = 'pending' if home_away == 'Home' else 'waiting'
                        task = Task(
                            organization_id=org.id,
                            fixture_id=fixture.id,
                            task_type=task_type,
                            status=task_status
                        )
                        session.add(task)
                        new_tasks += 1
                    
                except Exception as e:
                    logger.warning(f"Error processing fixture data: {e}")
                    skipped_count += 1
                    continue
            
            session.commit()
            
            flash_msg = f'Successfully imported {new_fixtures} new fixture(s)'
            if updated_fixtures > 0:
                flash_msg += f', updated {updated_fixtures} existing fixture(s)'
            if skipped_count > 0:
                flash_msg += f', skipped {skipped_count} fixture(s)'
            flash(flash_msg + '!', 'success')
            return redirect(url_for('imports.import_fixtures'))
            
        finally:
            os.unlink(temp_file_path)
            
    except Exception as e:
        flash(f'Error processing file: {str(e)}', 'error')
        return redirect(url_for('imports.import_fixtures'))

def handle_csv_import(session, org, managed_team_names):
    """Handle CSV/Excel file import"""
    return upload_file_internal(session, org, managed_team_names)

def handle_paste_import_internal(session, org, managed_team_names, text):
    """Internal handler for paste import"""
    fa_parser = FAFixtureParser()
    parsed_fixtures = fa_parser.parse_fa_fixture_lines(text)
    
    if not parsed_fixtures:
        flash('No valid fixtures found in the provided text', 'error')
        return redirect(url_for('imports.import_fixtures'))
    
    csv_data = fa_parser.convert_to_standard_format(parsed_fixtures)
    results = parse_fixture_text(csv_data, session, org)
    
    created_count = sum(1 for r in results if r.get('status') == 'success')
    error_count = len(results) - created_count
    
    if created_count > 0:
        flash(f'Successfully imported {created_count} fixture(s)!', 'success')
    if error_count > 0:
        flash(f'{error_count} fixture(s) could not be imported', 'warning')
    
    return redirect(url_for('imports.import_fixtures'))

def handle_google_import(session, org, managed_team_names):
    """Handle Google Sheets import"""
    google_sheets_url = request.form.get('google_sheets_url', '').strip()
    if not google_sheets_url:
        flash('Please provide a Google Sheets URL', 'error')
        return redirect(url_for('imports.import_fixtures'))
    
    try:
        sheets_importer = GoogleSheetsImporter()
        df = sheets_importer.fetch_sheet_as_csv(google_sheets_url)
        pasted_text = sheets_importer.convert_to_fixture_format(df)
        
        # Process using paste import logic
        return handle_paste_import_internal(session, org, managed_team_names, pasted_text)
    except Exception as e:
        flash(f'Error importing from Google Sheets: {str(e)}', 'error')
        return redirect(url_for('imports.import_fixtures'))

def handle_paste_import(session, org, managed_team_names):
    """Handle pasted FA data import"""
    fa_fixture_text = request.form.get('fa_fixture_text', '').strip()
    if not fa_fixture_text:
        flash('Please paste fixture data', 'error')
        return redirect(url_for('imports.import_fixtures'))
    
    return handle_paste_import_internal(session, org, managed_team_names, fa_fixture_text)

def handle_url_import(session, org, managed_team_names):
    """Handle FA URL import - auto-detect single vs multi-team"""
    fa_url = request.form.get('fa_url', '').strip()
    specified_team = request.form.get('url_team', '').strip()
    
    if not fa_url:
        if request.is_json or request.content_type == 'application/json':
            return jsonify({'error': 'Please provide an FA URL'}), 400
        flash('Please provide an FA URL', 'error')
        return redirect(url_for('imports.import_fixtures'))
    
    try:
        from refresh_fa_fixtures import refresh_club_fixtures, refresh_team_fixtures
        
        # Check if URL looks like a single team URL (has selectedTeam parameter) vs club URL (has selectedClub)
        is_club_url = 'selectedClub=' in fa_url and 'selectedTeam=' not in fa_url
        is_team_url = 'selectedTeam=' in fa_url
        
        result = None
        url_saved_to = None
        
        if specified_team:
            # User specified a team - treat as single team URL
            team = session.query(Team).filter_by(
                organization_id=org.id,
                name=specified_team,
                is_managed=True
            ).first()
            
            if team:
                # Save URL to team
                team.fa_fixtures_url = fa_url
                session.commit()
                url_saved_to = f"Team: {specified_team}"
                
                # Import fixtures for this team - use non-headless for CAPTCHA solving
                result = refresh_team_fixtures(team, headless=False)
            else:
                if request.is_json:
                    return jsonify({'error': f'Team "{specified_team}" not found'}), 404
                flash(f'Team "{specified_team}" not found', 'error')
                return redirect(url_for('imports.import_fixtures'))
        
        elif is_team_url and not is_club_url:
            # Single team URL - try to detect which team
            # Extract team ID from URL if possible
            team_match = re.search(r'selectedTeam=(\d+)', fa_url)
            if team_match:
                # This is a single team URL but we don't know which team
                # Import as club-wide and let matching logic handle it
                if not org.settings:
                    org.settings = {}
                org.settings['club_fixtures_url'] = fa_url
                session.commit()
                url_saved_to = "Club-wide URL (auto-detected)"
                result = refresh_club_fixtures(org, fa_url, headless=False)
            else:
                # Can't determine - use club-wide import
                if not org.settings:
                    org.settings = {}
                org.settings['club_fixtures_url'] = fa_url
                session.commit()
                url_saved_to = "Club-wide URL"
                result = refresh_club_fixtures(org, fa_url, headless=False)
        
        elif is_club_url or not is_team_url:
            # Club-wide URL
            if not org.settings:
                org.settings = {}
            org.settings['club_fixtures_url'] = fa_url
            session.commit()
            url_saved_to = "Club-wide URL"
            result = refresh_club_fixtures(org, fa_url, headless=False)
        
        else:
            # Default to club-wide
            if not org.settings:
                org.settings = {}
            org.settings['club_fixtures_url'] = fa_url
            session.commit()
            url_saved_to = "Club-wide URL"
            result = refresh_club_fixtures(org, fa_url, headless=False)
        
        if result and result.get('success'):
            response_data = {
                'success': True,
                'total_fixtures': result.get('total_fixtures', 0),
                'fixtures_imported': result.get('fixtures_imported', 0),
                'teams_matched': result.get('teams_matched', []),
                'url_saved': url_saved_to
            }
            
            if request.is_json or request.content_type == 'application/json':
                return jsonify(response_data)
            
            teams_str = ', '.join(result.get('teams_matched', [])) if result.get('teams_matched') else 'None'
            flash(f'Successfully imported {result.get("fixtures_imported", 0)} fixture(s) for {teams_str}. URL saved to {url_saved_to}', 'success')
        else:
            error_msg = result.get('error', 'Unknown error') if result else 'Import failed'
            
            # Provide helpful message if CAPTCHA is the issue
            if 'captcha' in error_msg.lower():
                error_msg = error_msg + " Tip: Try using the 'Paste FA Data' method instead - visit the FA website manually, solve CAPTCHA, then copy/paste the fixture data."
            
            if request.is_json:
                return jsonify({'error': error_msg}), 500
            flash(f'Error: {error_msg}', 'error')
        
        return redirect(url_for('imports.import_fixtures'))
        
    except Exception as e:
        session.rollback()
        logger.error(f"Error in handle_url_import: {e}")
        import traceback
        logger.error(traceback.format_exc())
        if request.is_json:
            return jsonify({'error': str(e)}), 500
        flash(f'Error importing from URL: {str(e)}', 'error')
        return redirect(url_for('imports.import_fixtures'))

@imports_bp.route('/import-fixtures', methods=['GET', 'POST'])
@login_required
def import_fixtures():
    """Unified fixture import page - handles all import methods"""
    session = db_manager.get_session()
    try:
        org = get_user_organization()
        if not org:
            flash('No organization found.', 'error')
            return redirect(url_for('auth.logout'))
        
        # Get context data
        managed_teams = session.query(Team).filter_by(
            organization_id=org.id,
            is_managed=True
        ).all()
        managed_team_names = [team.name for team in managed_teams]
        
        pitches = session.query(Pitch).filter_by(organization_id=org.id).all()
        pitches_dict = {pitch.name: {'name': pitch.name} for pitch in pitches}
        
        if request.method == 'GET':
            return render_template('import_fixtures.html',
                                 user_name=current_user.name,
                                 managed_teams=managed_team_names,
                                 pitches=pitches_dict)
        
        # Handle POST - route to appropriate handler based on import_method
        import_method = request.form.get('import_method', 'manual')
        
        if import_method == 'manual':
            return handle_manual_import(session, org, managed_team_names)
        elif import_method == 'csv':
            return handle_csv_import(session, org, managed_team_names)
        elif import_method == 'google':
            return handle_google_import(session, org, managed_team_names)
        elif import_method == 'paste':
            return handle_paste_import(session, org, managed_team_names)
        elif import_method == 'url':
            return handle_url_import(session, org, managed_team_names)
        else:
            flash('Invalid import method', 'error')
            return redirect(url_for('imports.import_fixtures'))
            
    except Exception as e:
        session.rollback()
        logger.error(f"Error in import_fixtures: {e}")
        import traceback
        logger.error(traceback.format_exc())
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('imports.import_fixtures'))
    finally:
        session.close()

@imports_bp.route('/upload', methods=['GET', 'POST'])
@login_required
def upload_file():
    """Upload fixture files and process them - redirects to unified import page"""
    # Redirect to unified import page
    return redirect(url_for('imports.import_fixtures') + '?method=csv')

@imports_bp.route('/parse_fixture', methods=['GET', 'POST'])
@login_required
def parse_fixture():
    """Parse fixture text and create tasks - redirects to unified import page"""
    # Redirect to unified import page (paste tab)
    return redirect(url_for('imports.import_fixtures') + '?method=paste')

@imports_bp.route('/bulk_fa_fixtures', methods=['GET', 'POST'])
@login_required
def bulk_fa_fixtures():
    """Bulk FA fixture upload - redirects to unified import page"""
    # Redirect to unified import page (paste tab)
    return redirect(url_for('imports.import_fixtures') + '?method=paste')

@imports_bp.route('/bulk_coach_upload', methods=['GET', 'POST'])
@login_required
def bulk_coach_upload():
    """Bulk coach upload with CSV parsing"""
    session = db_manager.get_session()
    try:
        if request.method == 'GET':
            # Get user organization and managed teams
            org = get_user_organization()
            if not org:
                return render_template('bulk_upload.html',
                                     upload_type='coaches',
                                     user_name=current_user.name,
                                     managed_teams=[],
                                     error_message="No organization found. Please contact support.")

            # Get teams that this user manages by querying teams directly
            managed_teams = []
            teams_with_coaches = session.query(Team).join(TeamCoach).filter(
                TeamCoach.organization_id == org.id
            ).distinct().all()

            for team in teams_with_coaches:
                if team.name not in managed_teams:
                    managed_teams.append(team.name)

            return render_template('bulk_upload.html',
                                 upload_type='coaches',
                                 user_name=current_user.name,
                                 managed_teams=managed_teams)

        # Handle POST request for CSV upload
        if 'confirm_save' in request.form:
            # User confirmed - save the data
            csv_data = request.form.get('csv_data', '')
            if not csv_data:
                flash('No CSV data found. Please try uploading again.', 'error')
                return redirect(url_for('settings.settings_view'))

            # Get column mappings
            mappings = {}
            for key in request.form:
                if key.startswith('mapping_'):
                    csv_column = key[8:]  # Remove 'mapping_' prefix
                    db_field = request.form[key]
                    if db_field:
                        mappings[csv_column] = db_field

            # Process CSV with mappings
            update_existing = 'update_existing' in request.form
            org = get_user_organization()
            result = process_coach_csv(session, org.id, csv_data, update_existing, mappings)

            if result['errors']:
                for error in result['errors']:
                    flash(f"Row {error['row']}: {error['message']}", 'error')

            total_processed = result['created'] + result['updated']
            if total_processed > 0:
                flash(f'Successfully processed {total_processed} coach records! ({result["created"]} created, {result["updated"]} updated)', 'success')

            return redirect(url_for('settings.settings_view'))

        elif 'mapping_step' in request.form:
            # User has completed column mapping - show preview/confirmation
            csv_data = request.form.get('csv_data', '')
            if not csv_data:
                flash('No CSV data found. Please try uploading again.', 'error')
                return redirect(url_for('settings.settings_view'))

            # Get column mappings
            mappings = {}
            for key in request.form:
                if key.startswith('mapping_'):
                    csv_column = key[8:]  # Remove 'mapping_' prefix
                    db_field = request.form[key]
                    if db_field:
                        mappings[csv_column] = db_field

            # Generate preview data
            preview_data = preview_coach_csv(csv_data, mappings)
            update_existing = 'update_existing' in request.form

            return render_template('bulk_upload.html',
                                 upload_type='coaches',
                                 user_name=current_user.name,
                                 managed_teams=[],
                                 show_confirmation=True,
                                 csv_data=csv_data,
                                 mappings=mappings,
                                 preview_data=preview_data,
                                 update_existing=update_existing)

        else:
            # Initial upload - analyze CSV and show mapping interface if needed
            csv_data = ''

            if 'coach_file' in request.files and request.files['coach_file'].filename:
                file = request.files['coach_file']
                if file.filename.endswith('.csv'):
                    csv_data = file.read().decode('utf-8')
                else:
                    flash('Please upload a CSV file.', 'error')
                    return redirect(url_for('settings.settings_view'))
            elif 'preview_text' in request.form and request.form['preview_text'].strip():
                csv_data = request.form['preview_text'].strip()
            else:
                flash('Please provide CSV data either by file upload or text input.', 'error')
                return redirect(url_for('settings.settings_view'))

            # Analyze the CSV structure
            analysis = analyze_csv_columns(csv_data)

            if not analysis['needs_manual_mapping']:
                # We can auto-map - show confirmation with preview
                update_existing = 'update_existing' in request.form
                preview_data = preview_coach_csv(csv_data, analysis['suggested_mapping'])

                return render_template('bulk_upload.html',
                                     upload_type='coaches',
                                     user_name=current_user.name,
                                     managed_teams=[],
                                     show_confirmation=True,
                                     csv_data=csv_data,
                                     mappings=analysis['suggested_mapping'],
                                     preview_data=preview_data,
                                     update_existing=update_existing,
                                     auto_mapped=True)
            else:
                # Show mapping interface
                update_existing = 'update_existing' in request.form
                return render_template('bulk_upload.html',
                                     upload_type='coaches',
                                     user_name=current_user.name,
                                     managed_teams=[],
                                     show_mapping=True,
                                     csv_data=csv_data,
                                     analysis=analysis,
                                     update_existing=update_existing)

    except Exception as e:
        flash(f'Error during bulk upload: {str(e)}', 'error')
        return redirect(url_for('settings.settings_view'))
    finally:
        session.close()

@imports_bp.route('/bulk_contact_upload', methods=['GET', 'POST'])
@login_required
def bulk_contact_upload():
    """Bulk contact upload - placeholder for now"""
    if request.method == 'GET':
        return render_template('bulk_upload.html', upload_type='contacts', user_name=current_user.name)
    
    # For now, just flash a message - full implementation can be added later
    flash('Bulk contact upload functionality will be available soon.', 'info')
    return redirect(url_for('settings.settings_view'))
