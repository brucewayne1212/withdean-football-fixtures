#!/usr/bin/env python3
"""
Import opposing team contacts from all_contacts.json into the database
"""

import json
import os
from dotenv import load_dotenv
from models import DatabaseManager, TeamContact, Organization
from sqlalchemy.orm import sessionmaker

# Load environment variables
load_dotenv()

def import_contacts():
    """Import contacts from all_contacts.json into TeamContact table"""

    # Get database URL
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL environment variable is required")

    # Initialize database
    db_manager = DatabaseManager(database_url)
    session = db_manager.get_session()

    try:
        # Read the JSON file
        with open('all_contacts.json', 'r', encoding='utf-8') as f:
            contacts_data = json.load(f)

        # Get the organization (assume we want the first one, or match by slug)
        # For Withdean Youth FC, the slug should be 'withdean-youth-fc'
        org = session.query(Organization).filter_by(slug='withdean-youth-fc').first()
        if not org:
            print("Organization 'withdean-youth-fc' not found. Please check your database setup.")
            return

        print(f"Importing contacts for organization: {org.name}")

        # Group contacts by team name to handle the unique constraint
        contacts_by_team = {}
        for contact_data in contacts_data:
            team_name = contact_data.get('club', '').strip()
            if not team_name:
                continue

            if team_name not in contacts_by_team:
                contacts_by_team[team_name] = []
            contacts_by_team[team_name].append(contact_data)

        imported_count = 0
        updated_count = 0
        skipped_count = 0

        # Process each team
        for team_name, team_contacts in contacts_by_team.items():
            print(f"Processing team: {team_name} ({len(team_contacts)} contacts)")

            # Select the best contact for this team
            selected_contact = select_best_contact(team_contacts)

            contact_name = selected_contact.get('name', '').strip()
            email = selected_contact.get('email', '').strip()
            phone = selected_contact.get('phone', '').strip()
            role = selected_contact.get('role', '').strip()

            # Combine contact name and role for better contact info
            full_contact_info = contact_name
            if role and role.lower() not in ['contact', 'club secretary', 'fixture secretary']:
                full_contact_info = f"{contact_name} ({role})"

            # Build notes field with role information and additional contact info if we have multiple contacts
            notes = ""
            if role:
                notes = f"Role: {role}"

            if len(team_contacts) > 1:
                all_contacts_info = []
                for contact in team_contacts:
                    contact_info = contact.get('name', '').strip()
                    if contact.get('role') and contact.get('role').lower() not in ['contact', 'club secretary', 'fixture secretary']:
                        contact_info += f" ({contact.get('role')})"
                    if contact.get('phone'):
                        contact_info += f" - {contact.get('phone')}"
                    if contact.get('email'):
                        contact_info += f" - {contact.get('email')}"
                    all_contacts_info.append(contact_info)

                notes += f"\n\nAll contacts for this team:\n" + "\n".join(all_contacts_info)

            # Check if contact already exists for this team
            existing_contact = session.query(TeamContact).filter_by(
                organization_id=org.id,
                team_name=team_name
            ).first()

            if existing_contact:
                # Update existing contact
                print(f"  Updating existing contact for {team_name}: {full_contact_info}")
                existing_contact.contact_name = full_contact_info
                existing_contact.email = email or None
                existing_contact.phone = phone or None
                existing_contact.notes = notes
                updated_count += 1
            else:
                # Create new contact
                print(f"  Creating new contact for {team_name}: {full_contact_info}")
                new_contact = TeamContact(
                    organization_id=org.id,
                    team_name=team_name,
                    contact_name=full_contact_info,
                    email=email or None,
                    phone=phone or None,
                    notes=notes
                )
                session.add(new_contact)
                imported_count += 1

        # Commit all changes
        session.commit()

        print(f"\nImport completed successfully!")
        print(f"- New contacts imported: {imported_count}")
        print(f"- Existing contacts updated: {updated_count}")
        print(f"- Contacts skipped: {skipped_count}")
        print(f"- Total teams processed: {len(contacts_by_team)}")

    except FileNotFoundError:
        print("Error: all_contacts.json file not found in current directory")
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON file: {e}")
    except Exception as e:
        session.rollback()
        print(f"Error during import: {e}")
        raise
    finally:
        session.close()


def select_best_contact(team_contacts):
    """Select the best contact for a team based on priority rules"""
    if len(team_contacts) == 1:
        return team_contacts[0]

    # Priority order: Fixture Secretary > Manager > Club Secretary > others
    role_priority = {
        'fixture secretary': 1,
        'manager': 2,
        'club secretary': 3,
        'secretary': 4,
        'contact': 5,
        'coach': 6,
        'assistant': 7
    }

    # Sort contacts by priority
    sorted_contacts = sorted(team_contacts, key=lambda x: role_priority.get(x.get('role', '').strip().lower(), 99))

    # Return the highest priority contact
    return sorted_contacts[0]

if __name__ == '__main__':
    import_contacts()
