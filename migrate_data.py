#!/usr/bin/env python3
"""
Data migration script for Withdean Football Fixtures
Migrates existing JSON data to PostgreSQL database
"""

import json
import os
import math
from datetime import datetime
from models import DatabaseManager, User, Organization, Team, Pitch, Fixture, Task, TeamContact, TeamCoach, EmailTemplate, UserPreference, get_or_create_organization, get_or_create_team
from task_manager import TaskType, TaskStatus

def safe_string(value, default=''):
    """Safely convert value to string, handling NaN and None values"""
    if value is None:
        return default
    if isinstance(value, float) and math.isnan(value):
        return default
    return str(value)

# Database connection
DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is required. Please set it in your environment or .env file.")

def migrate_existing_data():
    """Migrate existing JSON data to PostgreSQL"""
    print("🚀 Starting data migration...")
    
    # Initialize database
    db_manager = DatabaseManager(DATABASE_URL)
    session = db_manager.get_session()
    
    try:
        # 1. Create/verify admin user
        print("👤 Setting up admin user...")
        admin_user = session.query(User).filter_by(email='monahan.mark@gmail.com').first()
        if not admin_user:
            admin_user = User(
                email='monahan.mark@gmail.com',
                name='Mark Monahan',
                role='admin',
                is_active=True
            )
            session.add(admin_user)
            session.commit()
            print(f"✅ Created admin user: {admin_user.email}")
        else:
            print(f"✅ Found existing admin user: {admin_user.email}")
        
        # 2. Create/verify organization
        print("🏢 Setting up organization...")
        org = get_or_create_organization(
            session,
            str(admin_user.id),
            "Withdean Youth FC",
            "withdean-youth-fc"
        )
        print(f"✅ Organization ready: {org.name}")
        
        # 3. Migrate user settings and preferences
        print("⚙️  Migrating user settings...")
        user_settings_path = 'user_data/378c69282f91/user_settings.json'
        if os.path.exists(user_settings_path):
            with open(user_settings_path, 'r') as f:
                user_settings = json.load(f)
            
            # Migrate user preferences
            preferences = user_settings.get('preferences', {})
            user_pref = session.query(UserPreference).filter_by(
                organization_id=org.id,
                user_id=admin_user.id
            ).first()
            
            if not user_pref:
                user_pref = UserPreference(
                    organization_id=org.id,
                    user_id=admin_user.id,
                    preferences=preferences
                )
                session.add(user_pref)
            else:
                user_pref.preferences = preferences
            
            # Migrate managed teams
            managed_teams = user_settings.get('managed_teams', [])
            teams_created = 0
            for team_name in managed_teams:
                team = get_or_create_team(session, str(org.id), team_name, is_managed=True)
                teams_created += 1
            
            print(f"✅ Created {teams_created} managed teams")
            
            # Migrate pitches
            pitches = user_settings.get('pitches', {})
            pitches_created = 0
            for pitch_name, pitch_data in pitches.items():
                existing_pitch = session.query(Pitch).filter_by(
                    organization_id=org.id,
                    name=pitch_name
                ).first()
                
                if not existing_pitch:
                    pitch = Pitch(
                        organization_id=org.id,
                        name=pitch_name,
                        address=pitch_data.get('address', ''),
                        parking_info=pitch_data.get('parking', ''),
                        toilet_info=pitch_data.get('toilets', ''),
                        special_instructions=pitch_data.get('special_instructions', ''),
                        opening_notes=pitch_data.get('opening_notes', ''),
                        warm_up_notes=pitch_data.get('warm_up_notes', '')
                    )
                    session.add(pitch)
                    pitches_created += 1
            
            print(f"✅ Created {pitches_created} pitches")
            
            # Migrate team contacts
            team_contacts = user_settings.get('team_contacts', {})
            contacts_created = 0
            for team_name, contact_data in team_contacts.items():
                existing_contact = session.query(TeamContact).filter_by(
                    organization_id=org.id,
                    team_name=team_name
                ).first()
                
                if not existing_contact:
                    contact = TeamContact(
                        organization_id=org.id,
                        team_name=team_name,
                        contact_name=contact_data.get('contact_name', ''),
                        email=contact_data.get('email', ''),
                        phone=contact_data.get('phone', ''),
                        notes=contact_data.get('notes', '')
                    )
                    session.add(contact)
                    contacts_created += 1
            
            print(f"✅ Created {contacts_created} team contacts")
            
            # Migrate team coaches
            team_coaches = user_settings.get('team_coaches', {})
            coaches_created = 0
            for team_name, coach_data in team_coaches.items():
                # Find the team
                team = session.query(Team).filter_by(
                    organization_id=org.id,
                    name=team_name
                ).first()
                
                if team:
                    existing_coach = session.query(TeamCoach).filter_by(
                        organization_id=org.id,
                        team_id=team.id,
                        coach_name=coach_data.get('coach_name', '')
                    ).first()
                    
                    if not existing_coach and coach_data.get('coach_name'):
                        coach = TeamCoach(
                            organization_id=org.id,
                            team_id=team.id,
                            coach_name=coach_data.get('coach_name', ''),
                            email=coach_data.get('email', ''),
                            phone=coach_data.get('phone', ''),
                            role=coach_data.get('role', 'Coach'),
                            notes=coach_data.get('notes', '')
                        )
                        session.add(coach)
                        coaches_created += 1
            
            print(f"✅ Created {coaches_created} team coaches")
            
            session.commit()
        else:
            print("⚠️  No user settings file found, using defaults")
        
        # 4. Migrate fixtures and tasks
        print("📅 Migrating fixtures and tasks...")
        fixture_tasks_path = 'user_data/378c69282f91/fixture_tasks.json'
        if os.path.exists(fixture_tasks_path):
            with open(fixture_tasks_path, 'r') as f:
                tasks_data = json.load(f)
            
            fixtures_created = 0
            tasks_created = 0
            
            for task_id, task_data in tasks_data.items():
                # Create or find the team
                team_name = task_data.get('team', '')
                if team_name:
                    team = get_or_create_team(session, str(org.id), team_name)
                    
                    # Create or find opposition team if it's an internal team
                    opposition_team = None
                    opposition_name = task_data.get('opposition', '')
                    if opposition_name and str(opposition_name).lower() not in ['nan', 'tbc', 'none']:
                        # For now, treat all opposition as external
                        opposition_name = str(opposition_name)
                    else:
                        opposition_name = None
                    
                    # Find or create pitch
                    pitch = None
                    pitch_name = safe_string(task_data.get('pitch', ''))
                    if pitch_name:
                        pitch = session.query(Pitch).filter_by(
                            organization_id=org.id,
                            name=pitch_name
                        ).first()
                    
                    # Create fixture
                    kickoff_time_safe = safe_string(task_data.get('kickoff_time', ''))
                    existing_fixture = session.query(Fixture).filter_by(
                        organization_id=org.id,
                        team_id=team.id
                    ).filter(
                        Fixture.kickoff_time_text == kickoff_time_safe
                    ).first()
                    
                    if not existing_fixture:
                        fixture = Fixture(
                            organization_id=org.id,
                            team_id=team.id,
                            opposition_name=opposition_name,
                            home_away=safe_string(task_data.get('home_away', 'Home')),
                            pitch_id=pitch.id if pitch else None,
                            kickoff_time_text=kickoff_time_safe,
                            match_format=safe_string(task_data.get('format', '')),
                            fixture_length=safe_string(task_data.get('fixture_length', '')),
                            each_way=safe_string(task_data.get('each_way', '')),
                            referee_info=safe_string(task_data.get('referee', '')),
                            instructions=safe_string(task_data.get('instructions', '')),
                            home_manager=safe_string(task_data.get('home_manager', '')),
                            fixtures_sec=safe_string(task_data.get('fixtures_sec', '')),
                            manager_mobile=safe_string(task_data.get('manager_mobile', '')),
                            contact_1=safe_string(task_data.get('contact_1', '')),
                            contact_2=safe_string(task_data.get('contact_2', '')),
                            contact_3=safe_string(task_data.get('contact_3', '')),
                            contact_5=safe_string(task_data.get('contact_5', '')),
                            status=safe_string(task_data.get('status', 'pending'))
                        )
                        session.add(fixture)
                        session.flush()  # Get the fixture ID
                        fixtures_created += 1
                        
                        # Create corresponding task
                        task_type_map = {
                            'HOME_EMAIL': 'home_email',
                            'AWAY_FORWARD': 'away_forward'
                        }
                        
                        task_type = task_type_map.get(task_data.get('task_type', ''), 'home_email')
                        
                        task = Task(
                            organization_id=org.id,
                            fixture_id=fixture.id,
                            task_type=task_type,
                            status=task_data.get('status', 'pending'),
                            notes=task_data.get('notes', ''),
                            completed_at=datetime.fromisoformat(task_data['completed_date']) if task_data.get('completed_date') else None
                        )
                        session.add(task)
                        tasks_created += 1
            
            session.commit()
            print(f"✅ Created {fixtures_created} fixtures and {tasks_created} tasks")
        else:
            print("⚠️  No fixture tasks file found")
        
        # 5. Create default email template
        print("📧 Creating default email template...")
        existing_template = session.query(EmailTemplate).filter_by(
            organization_id=org.id,
            template_type='default'
        ).first()
        
        if not existing_template:
            default_template_content = """<p><strong><u>In the event of any issues impacting your fixture please communicate directly with your opposition manager - This email will NOT be monitored</u></strong></p>

<p>Dear Fixtures Secretary</p>

<p>Please find details of your upcoming fixture at <strong>Withdean Youth FC</strong></p>

<p><strong>Please confirm receipt:</strong> Please copy the relevant Withdean Youth FC manager to your response.</p>

<p><strong>Any issues:</strong> Managers please contact your opposition directly using the contact details supplied if you have any issues that will impact your attendance (ideally by phone call or text message).</p>

<p><strong>Please Contact Managers Directly:</strong> Our Fixtures secretaries will not pick up on late messages so it is vital you communicate directly with your opposition manager once you have been put in touch.</p>

<h3>FIXTURE DETAILS</h3>

<p><strong>Date:</strong> {{date_display}}</p>

<p><strong>Kick-off Time:</strong> {{time_display}}</p>

<p><strong>Pitch Location:</strong> {{pitch_name}} (see attached map for relevant pitch location)</p>

<p><strong>Home Colours:</strong> {{home_colours}}</p>

<p><strong>Match Format:</strong> {{match_format}}</p>

<p><strong>Referees:</strong> {{referee_note}}</p>

<h3>VENUE INFORMATION</h3>

<p><strong>Address:</strong> {{pitch_address}}</p>

<p><strong>Parking:</strong> {{pitch_parking}}</p>

<p><strong>Toilets:</strong> {{pitch_toilets}}</p>

<p><strong>Arrival & Setup:</strong> {{pitch_opening_notes}}</p>

<p><strong>Warm-up:</strong> {{pitch_warm_up_notes}}</p>

<p><strong>Special Instructions:</strong> {{pitch_special_instructions}}</p>

<h3>CONTACT INFORMATION</h3>

<p><strong>Manager:</strong> {{manager_name}}</p>
<p><strong>Manager Contact:</strong> {{manager_contact}}</p>

<p>{{email_signature}}</p>"""
            
            template = EmailTemplate(
                organization_id=org.id,
                template_type='default',
                name='Default Home Fixture Email',
                content=default_template_content,
                is_active=True
            )
            session.add(template)
            session.commit()
            print("✅ Created default email template")
        else:
            print("✅ Email template already exists")
        
        print("\n🎉 Data migration completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error during migration: {e}")
        session.rollback()
        return False
    finally:
        session.close()

if __name__ == "__main__":
    success = migrate_existing_data()
    if success:
        print("\n✨ Your existing data has been successfully migrated to PostgreSQL!")
        print("🔄 Next step: Update the Flask app to use the database models")
    else:
        print("\n💥 Migration failed!")
        exit(1)