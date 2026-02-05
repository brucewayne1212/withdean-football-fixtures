
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime, timezone, timedelta
import os
import tempfile
import io
import csv
import logging
import re
import pandas as pd
from werkzeug.utils import secure_filename

from database import db_manager
from utils import get_user_organization, allowed_file
from models import Team, Pitch, Fixture, Task, TeamCoach, get_or_create_team

# Local imports
from fixture_parser import FixtureParser
from fa_fixture_parser import FAFixtureParser
from text_fixture_parser import parse_fixture_text, TextFixtureParser
from google_sheets_helper import GoogleSheetsImporter
from services.pitch_matcher import PitchMatcher
import json

# Setup logger
logger = logging.getLogger(__name__)

imports_bp = Blueprint('imports', __name__)

# Helper to get the next Sunday's date
def get_next_sunday():
    today = datetime.now().date()
    # Calculate days until next Sunday (Sunday is 6 in weekday())
    days_until_sunday = (6 - today.weekday() + 7) % 7
    if days_until_sunday == 0: # If today is Sunday, get next Sunday
        days_until_sunday = 7
    return today + timedelta(days=days_until_sunday)

# Helper to parse generic tab-separated spreadsheet lines into fixture dicts
def parse_generic_spreadsheet_text(text):
    """Parse raw spreadsheet lines (tab-separated) into a list of fixture dicts.
    Expected columns order:
    Team, Competition, Coach, Manager, Opposition, Home/Away, Pitch, Time, Notes
    """
    rows = []
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = line.split('\t')
        if len(parts) < 9:
            # Not enough columns, skip
            continue
        team, competition, coach, manager, opposition, home_away, pitch, time, notes = parts[:9]
        # Use next Sunday as the fixture date
        from datetime import timedelta
        fixture_date = get_next_sunday().strftime('%Y-%m-%d')
        rows.append({
            'team': team.strip(),
            'opposition': opposition.strip(),
            'home_away': home_away.strip(),
            'date': fixture_date,
            'time': time.strip(),
            'pitch': pitch.strip(),
            'notes': notes.strip()
        })
    return rows

# Helper to convert list of fixture dicts to CSV string compatible with existing parser
def convert_generic_fixtures_to_csv(fixtures):
    """Convert generic fixture dict list to CSV format expected by parse_fixture_text.
    Columns: team, opposition, home_away, date, time, pitch, notes
    """
    output = io.StringIO()
    fieldnames = ['team', 'opposition', 'home_away', 'date', 'time', 'pitch', 'notes']
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for f in fixtures:
        writer.writerow(f)
    return output.getvalue()

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

def analyze_csv_columns(csv_data, mode='coaches'):
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
        if mode == 'contacts':
            field_patterns = {
                'team_name': ['team_name', 'team', 'team name', 'club', 'club_name', 'squad', 'opposition', 'opposing team'],
                'contact_name': ['contact_name', 'contact', 'name', 'manager', 'full_name', 'fullname', 'contact person'],
                'email': ['email', 'email_address', 'e-mail', 'mail', 'contact_email'],
                'phone': ['phone', 'phone_number', 'mobile', 'cell', 'telephone', 'contact_number'],
                'role': ['role', 'position', 'title', 'job_title', 'responsibility'],
                'notes': ['notes', 'comments', 'description', 'additional_info', 'remarks']
            }
        else:
            # Default to coaches
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

            # Specific check for 'role' if not already mapped with high confidence
            if not best_match or best_score < 90:
                if 'role' in header_lower or 'position' in header_lower or 'title' in header_lower:
                    if best_match != 'role' or best_score < 80: # Only override if current best match isn't role or confidence is low
                        best_match = 'role'
                        best_score = max(best_score, 80) # Give a decent score for role detection

            if best_match and best_score >= 70:
                suggested_mapping[header] = best_match
                confidence_scores[header] = best_score

        # Check if we have the required fields
        mapped_fields = set(suggested_mapping.values())
        if mode == 'contacts':
            required_fields = {'team_name', 'contact_name'}
        else:
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

def process_coach_csv(session, organization_id, csv_data, update_existing=False, column_mapping=None, selected_indices=None):
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
        # Convert reader to list to handle indexing if needed
        rows = list(reader)
        for row_num, row in enumerate(rows):
            actual_row_num = row_num + 2 # 1-based + header
            
            # Skip if not in selected_indices (if provided)
            if selected_indices is not None and row_num not in selected_indices:
                continue
                
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
                        'row': actual_row_num,
                        'message': 'Missing required fields: team_name and coach_name are required'
                    })
                    continue

                # Find team
                team_key = team_name.lower().strip()
                team = team_lookup.get(team_key)

                if not team:
                    result['errors'].append({
                        'row': actual_row_num,
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
                            'row': actual_row_num,
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
                    'row': actual_row_num,
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

def process_team_contact_csv(session, organization_id, csv_data, update_existing=False, column_mapping=None):
    """
    Process CSV data for bulk team contact upload
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
        from models import TeamContact
        
        # Parse CSV data
        csv_file = io.StringIO(csv_data.strip())
        reader = csv.DictReader(csv_file)

        # If no column mapping provided, try automatic detection
        if column_mapping is None:
            analysis = analyze_csv_columns(csv_data, mode='contacts')
            if analysis.get('needs_manual_mapping'):
                result['needs_mapping'] = True
                result['analysis'] = analysis
                return result
            column_mapping = analysis['suggested_mapping']

        # Process each row
        for row_num, row in enumerate(reader, start=2):
            try:
                # Extract fields using column mapping
                team_name = ''
                contact_name = ''
                role = None
                email = None
                phone = None
                notes = None

                # Map the fields
                for csv_header, our_field in column_mapping.items():
                    value = row.get(csv_header, '').strip()
                    if our_field == 'team_name':
                        team_name = value
                    elif our_field == 'contact_name':
                        contact_name = value
                    elif our_field == 'role':
                        role = value or None
                    elif our_field == 'email':
                        email = value or None
                    elif our_field == 'phone':
                        phone = value or None
                    elif our_field == 'notes':
                        notes = value or None

                if not team_name or not contact_name:
                    result['errors'].append({
                        'row': row_num,
                        'message': 'Missing required fields: team_name and contact_name are required'
                    })
                    continue

                # Check if contact already exists for this team (by team name and contact name)
                existing_contact = session.query(TeamContact).filter_by(
                    organization_id=organization_id,
                    team_name=team_name
                ).first()
                
                # Note: TeamContact constraint is unique on (organization_id, team_name)
                # So we can only have one contact per team name currently?
                # Let's check models.py: UniqueConstraint('organization_id', 'team_name')
                # Yes. So we update if exists.
                
                if existing_contact:
                    if update_existing:
                        existing_contact.contact_name = contact_name
                        existing_contact.role = role
                        existing_contact.email = email
                        existing_contact.phone = phone
                        existing_contact.notes = notes
                        existing_contact.updated_at = datetime.utcnow()
                        result['updated'] += 1
                    else:
                        result['errors'].append({
                            'row': row_num,
                            'message': f'Contact for team "{team_name}" already exists. Check "Update existing" to modify.'
                        })
                        continue
                else:
                    new_contact = TeamContact(
                        organization_id=organization_id,
                        team_name=team_name,
                        contact_name=contact_name,
                        role=role,
                        email=email,
                        phone=phone,
                        notes=notes,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    )
                    session.add(new_contact)
                    result['created'] += 1

            except Exception as e:
                result['errors'].append({
                    'row': row_num,
                    'message': f'Error processing row: {str(e)}'
                })
                continue

        session.commit()

        if result['errors']:
            result['success'] = False
            result['message'] = f'Processed with {len(result["errors"])} errors'
        else:
            result['message'] = 'All contacts processed successfully'

    except Exception as e:
        result['success'] = False
        result['message'] = f'CSV parsing error: {str(e)}'
        session.rollback()

    return result

def preview_contact_csv(csv_data, column_mapping):
    """Preview contact CSV data"""
    preview_data = {
        'contacts': [],
        'teams': set(),
        'total_rows': 0,
        'errors': []
    }

    try:
        csv_file = io.StringIO(csv_data.strip())
        reader = csv.DictReader(csv_file)

        for row_num, row in enumerate(reader, start=2):
            preview_data['total_rows'] += 1

            contact_data = {
                'row_num': row_num,
                'team_name': '',
                'contact_name': '',
                'role': '',
                'email': '',
                'phone': '',
                'notes': ''
            }

            for csv_header, our_field in column_mapping.items():
                value = row.get(csv_header, '').strip()
                if our_field in contact_data:
                    contact_data[our_field] = value or contact_data[our_field]

            if not contact_data['team_name'] or not contact_data['contact_name']:
                preview_data['errors'].append({
                    'row': row_num,
                    'message': 'Missing required fields',
                    'data': contact_data
                })
                continue

            preview_data['contacts'].append(contact_data)
            preview_data['teams'].add(contact_data['team_name'])

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
    session.flush()  # Get the fixture ID

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

def handle_paste_import_internal(session, org, managed_team_names, fa_fixture_text):
    """Handle pasted fixture data import, supporting FA format and generic tab-separated format.
    """
    fa_parser = FAFixtureParser()
    parsed_fixtures = fa_parser.parse_fa_fixture_lines(fa_fixture_text)
    
    # Determine which parsing succeeded
    used_generic = False
    if not parsed_fixtures:
        # Attempt generic parsing of tab-separated lines
        parsed_fixtures = parse_generic_spreadsheet_text(fa_fixture_text)
        used_generic = True
    
    if not parsed_fixtures:
        flash('No valid fixtures found in the provided text', 'error')
        return redirect(url_for('imports.import_fixtures'))
    
    # Convert to CSV format expected by parse_fixture_text
    if used_generic:
        csv_data = convert_generic_fixtures_to_csv(parsed_fixtures)
    else:
        csv_data = fa_parser.convert_to_standard_format(parsed_fixtures)
    
    results = parse_fixture_text(csv_data, session, org)
    
    created_count = sum(1 for r in results if r.get('status') == 'success')
    error_count = len(results) - created_count
    
    if created_count > 0:
        flash(f'Successfully imported {created_count} fixture(s)!', 'success')
    if error_count > 0:
        flash(f'{error_count} fixture(s) could not be imported', 'warning')
    
    return redirect(url_for('imports.import_fixtures'))
    """Handle pasted FA data import, with fallback for generic spreadsheet format.
    """
    fa_parser = FAFixtureParser()
    parsed_fixtures = fa_parser.parse_fa_fixture_lines(fa_fixture_text)
    
    # If FA parser yields no fixtures, try generic spreadsheet parsing
    if not parsed_fixtures:
        # Attempt generic parsing of tab-separated lines
        parsed_fixtures = parse_generic_spreadsheet_text(fa_fixture_text)
    
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

def parse_flexible_date(date_str):
    """
    Parse date string handling various formats including:
    - YYYY-MM-DD
    - DD/MM/YYYY
    - Day DDth Month (e.g. Sun 26th Nov)
    """
    if not date_str:
        return None
        
    date_str = str(date_str).strip()
    
    # Try ISO format first
    if 'T' in date_str:
        try:
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except:
            pass

    # Try standard formats
    for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y']:
        try:
            return datetime.strptime(date_str, fmt).replace(tzinfo=timezone.utc)
        except:
            continue
            
    # Try "Sun 26th Nov" style
    # Remove day name prefix if present (Sun, Mon, etc)
    clean_date = date_str
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday',
            'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    
    # Sort by length descending to match full names first
    days.sort(key=len, reverse=True)
    
    for day in days:
        if clean_date.lower().startswith(day.lower()):
            clean_date = clean_date[len(day):].strip()
            break
            
    # Remove ordinal suffixes (st, nd, rd, th)
    # Regex to replace 1st, 2nd, 3rd, 4th with 1, 2, 3, 4
    # But be careful not to break month names like August (though Aug is usually used)
    # Safer to just remove st, nd, rd, th if they follow a digit
    clean_date = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', clean_date)
    
    # Try parsing "26 Nov" or "26 November"
    # We need a year. If not present, assume current year or next occurrence?
    # Usually these sheets are for the current season.
    # Let's try adding current year
    current_year = datetime.now().year
    
    for fmt in ['%d %b', '%d %B']:
        try:
            # Parse with current year
            dt = datetime.strptime(f"{clean_date} {current_year}", f"{fmt} %Y")
            return dt.replace(tzinfo=timezone.utc)
        except:
            continue
            
    return None

def process_sheet_fixtures(session, org, fixtures_data):
    """Process fixtures from weekly sheet refresher"""
    new_fixtures = 0
    updated_fixtures = 0
    new_tasks = 0
    skipped_count = 0
    
    for fixture_data in fixtures_data:
        try:
            team_name = fixture_data.get('team', '').strip()
            if not team_name:
                print(f"DEBUG: Skipping fixture - no team name: {fixture_data}")
                skipped_count += 1
                continue
            
            # Get or create team
            team = get_or_create_team(session, org.id, team_name)
            
            # Parse date
            fixture_date = fixture_data.get('date')
            if not fixture_date:
                print(f"DEBUG: Skipping fixture - no date: {fixture_data}")
                skipped_count += 1
                continue
                
            kickoff_datetime = parse_flexible_date(fixture_date)
                
            if not kickoff_datetime:
                print(f"DEBUG: Skipping fixture - invalid date format: {fixture_date}")
                skipped_count += 1
                continue
            
            # Determine Home/Away
            home_away = fixture_data.get('home_away', 'Home').capitalize()
            if home_away not in ['Home', 'Away']:
                home_away = 'Home'
            
            # Check if fixture exists
            existing = session.query(Fixture).filter(
                Fixture.organization_id == org.id,
                Fixture.team_id == team.id,
                Fixture.kickoff_datetime == kickoff_datetime
            ).first()
            
            if existing:
                existing.opposition_name = fixture_data.get('opposition', existing.opposition_name) or 'TBC'
                existing.home_away = home_away
                existing.kickoff_time_text = fixture_data.get('time', existing.kickoff_time_text) or 'TBC'
                # existing.pitch_name = fixture_data.get('pitch', '') 
                updated_fixtures += 1
                fixture = existing
            else:
                fixture = Fixture(
                    organization_id=org.id,
                    team_id=team.id,
                    opposition_name=fixture_data.get('opposition', 'TBC') or 'TBC',
                    home_away=home_away,
                    kickoff_datetime=kickoff_datetime,
                    kickoff_time_text=fixture_data.get('time', 'TBC') or 'TBC'
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
            logger.warning(f"Error processing refreshed fixture: {e}")
            skipped_count += 1
            continue
            
    return new_fixtures, updated_fixtures, new_tasks, skipped_count

def handle_google_import(session, org, managed_team_names):
    """Handle Google Sheets import"""
    google_sheets_url = request.form.get('google_sheets_url', '').strip()
    if not google_sheets_url:
        flash('Please provide a Google Sheets URL', 'error')
        return redirect(url_for('imports.import_fixtures'))
    
    try:
        # Save the URL for future refreshes
        if not org.settings:
            org.settings = {}
        org.settings['google_sheet_url'] = google_sheets_url
        # Force SQLAlchemy to detect change in JSON field
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(org, "settings")
        session.commit()
        
        from weekly_sheet_refresher import refresh_weekly_fixtures
        fixtures_data, errors = refresh_weekly_fixtures(google_sheets_url)
        
        if errors:
            for error in errors:
                flash(error, 'error')
            if not fixtures_data:
                return redirect(url_for('imports.import_fixtures'))
        
        new_fixtures, updated_fixtures, new_tasks, skipped_count = process_sheet_fixtures(session, org, fixtures_data)
        session.commit()
        
        flash(f'Successfully imported {new_fixtures} new fixture(s), updated {updated_fixtures}.', 'success')
        return redirect(url_for('imports.import_fixtures'))

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

            # Get selected indices if present
            selected_indices = request.form.getlist('selected_indices')
            if selected_indices:
                selected_indices = [int(i) for i in selected_indices]
            else:
                selected_indices = None

            # Process CSV with mappings
            update_existing = 'update_existing' in request.form
            org = get_user_organization()
            result = process_coach_csv(session, org.id, csv_data, update_existing, mappings, selected_indices)

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
    """Bulk contact upload"""
    session = db_manager.get_session()
    try:
        org = get_user_organization()
        if not org:
            flash('No organization found.', 'error')
            return redirect(url_for('auth.logout'))

        if request.method == 'GET':
            return render_template('bulk_upload.html', upload_type='contacts', user_name=current_user.name)

        # Handle POST
        csv_data = None
        
        # Check if file upload
        if 'contact_file' in request.files:
            file = request.files['contact_file']
            if file and file.filename:
                filename = file.filename.lower()
                if filename.endswith('.csv'):
                    csv_data = file.read().decode('utf-8')
                elif filename.endswith(('.xlsx', '.xls')):
                    try:
                        # Read Excel file - sheet_name=None reads all sheets
                        # header=None to read raw first, or assume header is row 0
                        # We'll read with header=0 by default, but we need to handle merged cells
                        
                        # Use openpyxl engine which can help with some things, but pandas handles basic merge by filling NaN
                        # We need to explicitly forward fill (ffill) to handle "merged across multiple rows" behavior
                        # But standard read_excel puts NaN in merged cells after the first one.
                        
                        dfs = pd.read_excel(file, sheet_name=None, dtype=str)
                        
                        # Combine all sheets
                        all_data = []
                        for sheet_name, df in dfs.items():
                            if df.empty:
                                continue
                                
                            # 1. Handle Merged Cells (Forward Fill)
                            # "Club name is often only entered once and then merged across multiple columns" (rows likely meant)
                            # We forward fill all columns to propagate values down merged rows
                            df = df.ffill()
                            
                            # 2. Filter for "Fixture Secretary"
                            # We look for a column that might contain roles
                            role_col = None
                            for col in df.columns:
                                if 'role' in str(col).lower() or 'position' in str(col).lower() or 'title' in str(col).lower():
                                    role_col = col
                                    break
                            
                            # If we found a role column, filter for Fixture Secretary
                            if role_col:
                                # Normalize text for comparison
                                # We look for "Secretary" or "Fixture" to be safe, or exact match?
                                # User said "extract the fixture secretary".
                                # Let's try to be smart: if "Fixture Secretary" exists, keep only those.
                                
                                # Create a mask for rows that look like fixture secretaries
                                # We'll be lenient: contains "secretary" AND ("fixture" or "sec")
                                def is_fixture_sec(val):
                                    val = str(val).lower()
                                    return 'secretary' in val and ('fixture' in val or 'fix' in val)
                                
                                # Check if any row matches this strict criteria
                                has_fix_sec = df[role_col].apply(is_fixture_sec).any()
                                
                                if has_fix_sec:
                                    df = df[df[role_col].apply(is_fixture_sec)]
                                else:
                                    # Fallback: maybe just "Secretary"?
                                    if df[role_col].str.contains('Secretary', case=False, na=False).any():
                                         df = df[df[role_col].str.contains('Secretary', case=False, na=False)]
                            
                            # Add to collection
                            all_data.append(df)
                        
                        if all_data:
                            combined_df = pd.concat(all_data, ignore_index=True)
                            # Convert to CSV string
                            csv_data = combined_df.to_csv(index=False)
                        else:
                            flash('Excel file appears to be empty', 'error')
                            return redirect(url_for('imports.bulk_contact_upload'))
                            
                    except Exception as e:
                        flash(f'Error reading Excel file: {str(e)}', 'error')
                        return redirect(url_for('imports.bulk_contact_upload'))
                else:
                    flash('Invalid file type. Please upload CSV or Excel.', 'error')
                    return redirect(url_for('imports.bulk_contact_upload'))
        
        # Check if pasted text
        if not csv_data and request.form.get('preview_text'):
            csv_data = request.form.get('preview_text')
            
        # Check if passed from confirmation step
        if not csv_data and request.form.get('csv_data'):
            csv_data = request.form.get('csv_data')
            
        if not csv_data:
            flash('No data provided', 'error')
            return redirect(url_for('imports.bulk_contact_upload'))

        update_existing = request.form.get('update_existing') == 'on'
        
        # Check if this is a confirmation save
        if request.form.get('confirm_save') == 'true':
            # Reconstruct mapping from form
            mapping = {}
            for key, value in request.form.items():
                if key.startswith('mapping_') and value:
                    original_header = key.replace('mapping_', '')
                    mapping[original_header] = value
            
            # Get selected indices if present
            selected_indices = request.form.getlist('selected_indices')
            if selected_indices:
                selected_indices = [int(i) for i in selected_indices]
            else:
                selected_indices = None
            
            result = process_team_contact_csv(session, org.id, csv_data, update_existing, mapping, selected_indices)
            
            if result['success']:
                flash(f"Successfully imported {result['created']} new contacts and updated {result['updated']}.", 'success')
                if result['errors']:
                    flash(f"Some rows had errors: {len(result['errors'])} errors.", 'warning')
                return redirect(url_for('settings.settings_view'))
            else:
                flash(f"Import failed: {result['message']}", 'error')
                return redirect(url_for('imports.bulk_contact_upload'))

        # Check if this is a mapping step
        if request.form.get('mapping_step') == 'true':
             # Reconstruct mapping from form
            mapping = {}
            for key, value in request.form.items():
                if key.startswith('mapping_') and value:
                    original_header = key.replace('mapping_', '')
                    mapping[original_header] = value
                    
            preview = preview_contact_csv(csv_data, mapping)
            return render_template('bulk_upload.html', 
                                 upload_type='contacts',
                                 user_name=current_user.name,
                                 show_confirmation=True,
                                 preview_data=preview,
                                 csv_data=csv_data,
                                 mappings=mapping,
                                 update_existing=update_existing,
                                 auto_mapped=False)

        # Initial upload - analyze and show mapping
        analysis = analyze_csv_columns(csv_data, mode='contacts')
        
        # Always show mapping step to allow user to guide the import
        return render_template('bulk_upload.html',
                             upload_type='contacts',
                             user_name=current_user.name,
                             show_mapping=True,
                             analysis=analysis,
                             csv_data=csv_data,
                             update_existing=update_existing)

    except Exception as e:
        session.rollback()
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('imports.bulk_contact_upload'))
    finally:
        session.close()

@imports_bp.route('/refresh_fixtures')
@login_required
def refresh_fixtures():
    """Refresh fixtures from the saved Google Sheet"""
    session = db_manager.get_session()
    try:
        org = get_user_organization()
        if not org:
            flash('No organization found.', 'error')
            return redirect(url_for('auth.logout'))
            
        # Get saved sheet URL from settings
        # Try 'weekly_sheet_url' first (new standard), then 'google_sheet_url' (legacy)
        sheet_url = None
        if org.settings:
            sheet_url = org.settings.get('weekly_sheet_url') or org.settings.get('google_sheet_url')
        
        if not sheet_url:
            # If no URL saved, try to find one from previous usage or prompt user
            flash('No Google Sheet URL configured. Please import from Google Sheets first to save the URL.', 'warning')
            return redirect(url_for('imports.import_fixtures'))
            
        from weekly_sheet_refresher import refresh_weekly_fixtures
        fixtures_data, errors = refresh_weekly_fixtures(sheet_url)
        
        if errors:
            for error in errors:
                flash(error, 'error')
            if not fixtures_data:
                return redirect(url_for('dashboard.dashboard_view'))
        
        # Initialize PitchMatcher
        matcher = PitchMatcher(session, org.id)
        
        # Prepare preview data
        preview_data = []
        pitches = session.query(Pitch).filter_by(organization_id=org.id).order_by(Pitch.name).all()
        
        for fixture in fixtures_data:
            sheet_pitch = fixture.get('pitch', '').strip()
            pitch_obj, match_type, confidence = matcher.match_pitch(sheet_pitch)
            
            # If no pitch specified but it's a home game, try default home pitch
            if not sheet_pitch and fixture.get('home_away') == 'Home':
                default_pitch = matcher.find_default_home_pitch()
                if default_pitch:
                    pitch_obj = default_pitch
                    match_type = 'default'
            
            preview_data.append({
                'date': fixture.get('date'),
                'time': fixture.get('time'),
                'team': fixture.get('team'),
                'opposition': fixture.get('opposition'),
                'home_away': fixture.get('home_away'),
                'sheet_pitch': sheet_pitch,
                'suggested_pitch_id': pitch_obj.id if pitch_obj else None,
                'match_type': match_type,
                'is_exact_match': match_type == 'exact',
                'fixture_json': json.dumps(fixture)
            })
            
        return render_template('fixture_import_preview.html', 
                             preview_data=preview_data,
                             pitches=pitches)
        
    except Exception as e:
        session.rollback()
        flash(f'Error refreshing fixtures: {str(e)}', 'error')
        return redirect(url_for('dashboard.dashboard_view'))
    finally:
        session.close()

@imports_bp.route('/save_refreshed_fixtures', methods=['POST'])
@login_required
def save_refreshed_fixtures():
    """Save fixtures after review"""
    session = db_manager.get_session()
    try:
        org = get_user_organization()
        if not org:
            flash('No organization found.', 'error')
            return redirect(url_for('auth.logout'))
            
        # Process form data
        fixtures_to_save = []
        
        # Iterate through form keys to find fixtures
        # We expect keys like fixture_0_data, fixture_0_pitch_id, etc.
        # Find max index
        max_index = -1
        for key in request.form:
            if key.startswith('fixture_') and '_data' in key:
                try:
                    idx = int(key.split('_')[1])
                    if idx > max_index:
                        max_index = idx
                except:
                    pass
        
        new_fixtures = 0
        updated_fixtures = 0
        new_tasks = 0
        
        from models import PitchAlias
        # parse_flexible_date is defined in this module
        
        for i in range(max_index + 1):
            fixture_json = request.form.get(f'fixture_{i}_data')
            if not fixture_json:
                continue
                
            fixture_data = json.loads(fixture_json)
            pitch_id = request.form.get(f'fixture_{i}_pitch_id')
            save_alias = request.form.get(f'fixture_{i}_save_alias')
            sheet_pitch = request.form.get(f'fixture_{i}_sheet_pitch')
            
            # Handle Alias Saving
            if save_alias and sheet_pitch and pitch_id:
                # Check if alias exists
                existing_alias = session.query(PitchAlias).filter(
                    PitchAlias.organization_id == org.id,
                    PitchAlias.alias == sheet_pitch
                ).first()
                
                if not existing_alias:
                    new_alias = PitchAlias(
                        organization_id=org.id,
                        pitch_id=pitch_id,
                        alias=sheet_pitch
                    )
                    session.add(new_alias)
            
            # Save Fixture
            team_name = fixture_data.get('team', '').strip()
            if not team_name:
                continue
                
            team = get_or_create_team(session, org.id, team_name)
            
            fixture_date = fixture_data.get('date')
            kickoff_datetime = parse_flexible_date(fixture_date)
            
            if not kickoff_datetime:
                continue
                
            home_away = fixture_data.get('home_away', 'Home').capitalize()
            if home_away not in ['Home', 'Away']:
                home_away = 'Home'
                
            # Check if fixture exists
            existing = session.query(Fixture).filter(
                Fixture.organization_id == org.id,
                Fixture.team_id == team.id,
                Fixture.kickoff_datetime == kickoff_datetime
            ).first()
            
            if existing:
                existing.opposition_name = fixture_data.get('opposition', existing.opposition_name) or 'TBC'
                existing.home_away = home_away
                existing.kickoff_time_text = fixture_data.get('time', existing.kickoff_time_text) or 'TBC'
                if pitch_id:
                    existing.pitch_id = pitch_id
                updated_fixtures += 1
                fixture = existing
            else:
                fixture = Fixture(
                    organization_id=org.id,
                    team_id=team.id,
                    opposition_name=fixture_data.get('opposition', 'TBC') or 'TBC',
                    home_away=home_away,
                    kickoff_datetime=kickoff_datetime,
                    kickoff_time_text=fixture_data.get('time', 'TBC') or 'TBC',
                    pitch_id=pitch_id if pitch_id else None
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
                
        session.commit()
        flash(f'Successfully processed fixtures: {new_fixtures} new, {updated_fixtures} updated.', 'success')
        return redirect(url_for('dashboard.dashboard_view'))
        
    except Exception as e:
        session.rollback()
        flash(f'Error saving fixtures: {str(e)}', 'error')
        return redirect(url_for('dashboard.dashboard_view'))
    finally:
        session.close()
@imports_bp.route('/bulk_team_upload', methods=['GET', 'POST'])
@login_required
def bulk_team_upload():
    """Bulk team upload for master team list"""
    session = db_manager.get_session()
    try:
        org = get_user_organization()
        if not org:
            flash('No organization found.', 'error')
            return redirect(url_for('auth.logout'))

        if request.method == 'GET':
            return render_template('bulk_team_upload.html', user_name=current_user.name)

        # Handle POST
        csv_data = None
        
        # Check if file upload
        if 'team_file' in request.files:
            file = request.files['team_file']
            if file and file.filename:
                filename = file.filename.lower()
                if filename.endswith('.csv'):
                    csv_data = file.read().decode('utf-8')
                elif filename.endswith(('.xlsx', '.xls')):
                    try:
                        dfs = pd.read_excel(file, sheet_name=None, dtype=str)
                        all_data = []
                        for sheet_name, df in dfs.items():
                            if not df.empty:
                                all_data.append(df)
                        
                        if all_data:
                            combined_df = pd.concat(all_data, ignore_index=True)
                            csv_data = combined_df.to_csv(index=False)
                        else:
                            flash('Excel file appears to be empty', 'error')
                            return redirect(url_for('imports.bulk_team_upload'))
                    except Exception as e:
                        flash(f'Error reading Excel file: {str(e)}', 'error')
                        return redirect(url_for('imports.bulk_team_upload'))
                else:
                    flash('Invalid file type. Please upload CSV or Excel.', 'error')
                    return redirect(url_for('imports.bulk_team_upload'))
        
        # Check if pasted text
        if not csv_data and request.form.get('preview_text'):
            csv_data = request.form.get('preview_text')
            
        if not csv_data:
            flash('No data provided', 'error')
            return redirect(url_for('imports.bulk_team_upload'))

        # Check if this is a confirmation save
        if request.form.get('confirm_save') == 'true':
            # Reconstruct mapping from form
            mapping = {}
            for key, value in request.form.items():
                if key.startswith('mapping_') and value:
                    original_header = key.replace('mapping_', '')
                    mapping[original_header] = value
            
            result = process_team_csv(session, org.id, csv_data, mapping)
            
            if result['success']:
                flash(f"Successfully imported {result['created']} new teams. {result['updated']} teams already existed.", 'success')
                if result['errors']:
                    flash(f"Some rows had errors: {len(result['errors'])} errors.", 'warning')
                return redirect(url_for('settings.settings_view'))
            else:
                flash(f"Import failed: {result['message']}", 'error')
                return redirect(url_for('imports.bulk_team_upload'))

        # Check if this is a mapping step
        if request.form.get('mapping_step') == 'true':
            # Reconstruct mapping from form
            mapping = {}
            for key, value in request.form.items():
                if key.startswith('mapping_') and value:
                    original_header = key.replace('mapping_', '')
                    mapping[original_header] = value
                    
            preview = preview_team_csv(csv_data, mapping)
            return render_template('bulk_team_upload.html',
                                 user_name=current_user.name,
                                 show_confirmation=True,
                                 preview_data=preview,
                                 csv_data=csv_data,
                                 mappings=mapping,
                                 auto_mapped=False)

        # Initial upload - analyze and show mapping
        analysis = analyze_team_csv_columns(csv_data)
        
        # Always show mapping step to allow user to guide the import
        return render_template('bulk_team_upload.html',
                             user_name=current_user.name,
                             show_mapping=True,
                             analysis=analysis,
                             csv_data=csv_data)

    except Exception as e:
        session.rollback()
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('imports.bulk_team_upload'))
    finally:
        session.close()


def process_team_contact_csv(session, organization_id, csv_data, update_existing=False, mapping=None, selected_indices=None):
    """
    Process CSV data for team contacts
    """
    try:
        # Parse CSV
        if isinstance(csv_data, str):
            df = pd.read_csv(io.StringIO(csv_data), dtype=str)
        else:
            df = csv_data
            
        # Apply mapping if provided
        if mapping:
            # Invert mapping to rename columns: {csv_col: db_field} -> rename(columns={csv_col: db_field})
            # But we need to be careful if multiple csv cols map to same db field (not allowed in UI but possible)
            df = df.rename(columns=mapping)
            
        # Normalize columns
        df.columns = [c.lower().strip() for c in df.columns]
        
        created_count = 0
        updated_count = 0
        errors = []
        
        # Iterate rows
        for index, row in df.iterrows():
            # Skip if not in selected_indices (if provided)
            if selected_indices is not None and index not in selected_indices:
                continue
                
            try:
                # Get team name
                team_name = None
                if 'team_name' in row:
                    team_name = str(row['team_name']).strip()
                elif 'team' in row:
                    team_name = str(row['team']).strip()
                    
                if not team_name or pd.isna(team_name) or team_name.lower() == 'nan':
                    # Try to find a column that looks like a team name
                    for key in row.keys():
                        if key and ('team' in key.lower() or 'name' in key.lower()):
                            val = str(row[key]).strip()
                            if val and val.lower() != 'nan':
                                team_name = val
                                break
                    
                    if not team_name:
                        continue

                # Get or create team
                team = session.query(Team).filter_by(
                    organization_id=organization_id, 
                    name=team_name
                ).first()
                
                if not team:
                    team = Team(
                        organization_id=organization_id,
                        name=team_name,
                        is_managed=False
                    )
                    session.add(team)
                    session.flush() # Get ID
                
                # Get contact details
                contact_name = row.get('contact_name') or row.get('name') or row.get('contact') or ''
                email = row.get('email') or row.get('email_address') or ''
                phone = row.get('phone') or row.get('phone_number') or row.get('mobile') or ''
                role = row.get('role') or row.get('position') or row.get('title') or ''
                notes = row.get('notes') or row.get('comments') or ''
                
                # Clean up data
                if pd.isna(contact_name): contact_name = ''
                if pd.isna(email): email = ''
                if pd.isna(phone): phone = ''
                if pd.isna(role): role = ''
                if pd.isna(notes): notes = ''
                
                contact_name = str(contact_name).strip()
                email = str(email).strip()
                phone = str(phone).strip()
                role = str(role).strip()
                notes = str(notes).strip()
                
                if not contact_name and not email:
                    continue
                    
                # Check for existing contact
                contact = session.query(TeamContact).filter_by(
                    organization_id=organization_id,
                    team_id=team.id
                ).first()
                
                if contact:
                    if update_existing:
                        contact.contact_name = contact_name or contact.contact_name
                        contact.email = email or contact.email
                        contact.phone = phone or contact.phone
                        contact.role = role or contact.role
                        contact.notes = notes or contact.notes
                        updated_count += 1
                else:
                    contact = TeamContact(
                        organization_id=organization_id,
                        team_id=team.id,
                        contact_name=contact_name,
                        email=email,
                        phone=phone,
                        role=role,
                        notes=notes
                    )
                    session.add(contact)
                    created_count += 1
                    
            except Exception as e:
                errors.append({
                    'row': index + 2, # 1-based + header
                    'message': str(e)
                })
                
        session.commit()
        
        return {
            'success': True,
            'created': created_count,
            'updated': updated_count,
            'errors': errors
        }
        
    except Exception as e:
        session.rollback()
        return {
            'success': False,
            'message': str(e),
            'created': 0,
            'updated': 0,
            'errors': []
        }
                    
def process_team_csv(session, organization_id, csv_data, column_mapping=None):
    """Process CSV data for bulk team upload"""
    result = {
        'success': True,
        'created': 0,
        'updated': 0,
        'errors': [],
        'message': ''
    }

    try:
        from models import Team
        
        csv_file = io.StringIO(csv_data.strip())
        reader = csv.DictReader(csv_file)

        for row_num, row in enumerate(reader, start=2):
            try:
                team_name = ''
                age_group = None

                # Use column mapping if provided
                if column_mapping:
                    for csv_header, our_field in column_mapping.items():
                        value = row.get(csv_header, '').strip()
                        if our_field == 'team_name':
                            team_name = value
                        elif our_field == 'age_group':
                            age_group = value or None
                else:
                    # Fallback to auto-detection
                    for key in row.keys():
                        if key and ('team' in key.lower() or 'name' in key.lower()):
                            team_name = row[key].strip()
                            if team_name:
                                break
                    
                    if not team_name:
                        team_name = list(row.values())[0].strip() if row.values() else None
                    
                    for key in row.keys():
                        if key and ('age' in key.lower() or 'group' in key.lower()):
                            age_group = row[key].strip() or None
                            break
                
                if not team_name:
                    result['errors'].append({
                        'row': row_num,
                        'message': 'No team name found'
                    })
                    continue

                # Check if team already exists
                existing_team = session.query(Team).filter_by(
                    organization_id=organization_id,
                    name=team_name
                ).first()
                
                if existing_team:
                    result['updated'] += 1
                else:
                    new_team = Team(
                        organization_id=organization_id,
                        name=team_name,
                        age_group=age_group,
                        is_managed=False,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    )
                    session.add(new_team)
                    result['created'] += 1

            except Exception as e:
                result['errors'].append({
                    'row': row_num,
                    'message': f'Error processing row: {str(e)}'
                })
                continue

        session.commit()

        if result['errors']:
            result['message'] = f'Processed with {len(result["errors"])} errors'
        else:
            result['message'] = 'All teams processed successfully'

    except Exception as e:
        result['success'] = False
        result['message'] = f'CSV parsing error: {str(e)}'
        session.rollback()

    return result


def analyze_team_csv_columns(csv_data):
    """Analyze CSV columns for team data"""
    analysis = {
        'headers': [],
        'sample_rows': [],
        'suggested_mapping': {},
        'confidence_scores': {},
        'needs_manual_mapping': False
    }
    
    try:
        csv_file = io.StringIO(csv_data.strip())
        reader = csv.DictReader(csv_file)
        
        # Get headers
        analysis['headers'] = reader.fieldnames or []
        
        # Get sample rows
        for i, row in enumerate(reader):
            if i < 3:
                analysis['sample_rows'].append(row)
            else:
                break
        
        # Suggest mappings
        for header in analysis['headers']:
            header_lower = header.lower()
            
            if 'team' in header_lower and 'name' in header_lower:
                analysis['suggested_mapping'][header] = 'team_name'
                analysis['confidence_scores'][header] = 95
            elif 'team' in header_lower or header_lower == 'name':
                analysis['suggested_mapping'][header] = 'team_name'
                analysis['confidence_scores'][header] = 85
            elif 'age' in header_lower or 'group' in header_lower:
                analysis['suggested_mapping'][header] = 'age_group'
                analysis['confidence_scores'][header] = 90
        
        # Check if we have team_name mapped
        if 'team_name' not in analysis['suggested_mapping'].values():
            analysis['needs_manual_mapping'] = True
            
    except Exception as e:
        analysis['error'] = str(e)
        analysis['needs_manual_mapping'] = True
    
    return analysis


def preview_team_csv(csv_data, column_mapping):
    """Preview team CSV data"""
    preview_data = {
        'teams': [],
        'total_rows': 0,
        'errors': []
    }

    try:
        csv_file = io.StringIO(csv_data.strip())
        reader = csv.DictReader(csv_file)

        for row_num, row in enumerate(reader, start=2):
            preview_data['total_rows'] += 1

            team_data = {
                'row_num': row_num,
                'team_name': '',
                'age_group': ''
            }

            for csv_header, our_field in column_mapping.items():
                value = row.get(csv_header, '').strip()
                if our_field in team_data:
                    team_data[our_field] = value or team_data[our_field]

            if not team_data['team_name']:
                preview_data['errors'].append({
                    'row': row_num,
                    'message': 'Missing team name',
                    'data': team_data
                })
                continue

            preview_data['teams'].append(team_data)

    except Exception as e:
        preview_data['errors'].append({
            'row': 'Unknown',
            'message': f'CSV parsing error: {str(e)}',
            'data': {}
        })

    return preview_data
