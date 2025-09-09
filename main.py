#!/usr/bin/env python3
"""
Football Fixtures Email Generator
Automates the process of generating emails for Withdean Youth FC fixtures
"""

import os
import sys
from typing import List, Dict
from fixture_parser import FixtureParser
from managed_teams import get_managed_teams
from email_template import generate_email, generate_subject_line

def main():
    """Main function to process fixtures and generate emails"""
    
    print("=== Withdean Youth FC Fixture Email Generator ===")
    print()
    
    # Get the spreadsheet file path
    if len(sys.argv) > 1:
        spreadsheet_path = sys.argv[1]
    else:
        spreadsheet_path = input("Enter the path to your fixtures spreadsheet: ").strip()
    
    # Validate file exists
    if not os.path.exists(spreadsheet_path):
        print(f"Error: File '{spreadsheet_path}' not found!")
        return
    
    # Initialize parser
    parser = FixtureParser()
    managed_teams = get_managed_teams()
    
    print(f"Loading spreadsheet: {spreadsheet_path}")
    print(f"Looking for {len(managed_teams)} managed teams...")
    print()
    
    # Read and process spreadsheet
    df = parser.read_spreadsheet(spreadsheet_path)
    if df.empty:
        print("Error: Could not read spreadsheet or it's empty!")
        return
    
    # Filter for managed teams
    filtered_df = parser.filter_teams(df, managed_teams)
    
    if filtered_df.empty:
        print("No fixtures found for your managed teams in this spreadsheet.")
        print("Teams we're looking for:")
        for team in managed_teams[:10]:  # Show first 10
            print(f"  - {team}")
        if len(managed_teams) > 10:
            print(f"  ... and {len(managed_teams) - 10} more")
        return
    
    # Convert to fixture data
    fixtures = parser.get_fixture_data(filtered_df)
    
    print(f"Found {len(fixtures)} fixture(s) for your managed teams:")
    print()
    
    # Generate emails for each fixture
    emails_generated = []
    
    for i, fixture in enumerate(fixtures, 1):
        print(f"--- FIXTURE {i} ---")
        print(f"Team: {fixture['team']}")
        print(f"vs {fixture['opposition']}")
        print(f"Pitch: {fixture['pitch']}")
        print(f"Time: {fixture['kickoff_time']}")
        print()
        
        # Generate email content
        email_content = generate_email(fixture)
        subject_line = generate_subject_line(fixture)
        
        emails_generated.append({
            'team': fixture['team'],
            'subject': subject_line,
            'content': email_content
        })
        
        print("SUBJECT:", subject_line)
        print()
        print("EMAIL CONTENT:")
        print("-" * 50)
        print(email_content)
        print("-" * 50)
        print()
        print("=" * 60)
        print()
    
    # Offer to save emails to files
    save_option = input("Would you like to save these emails to individual text files? (y/n): ").lower().strip()
    
    if save_option in ['y', 'yes']:
        output_dir = "generated_emails"
        os.makedirs(output_dir, exist_ok=True)
        
        for i, email in enumerate(emails_generated):
            # Create safe filename
            safe_team_name = email['team'].replace('/', '_').replace(' ', '_')
            filename = f"{output_dir}/email_{i+1}_{safe_team_name}.txt"
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(f"Subject: {email['subject']}\n\n")
                f.write(email['content'])
            
            print(f"Saved: {filename}")
        
        print(f"\nAll emails saved to '{output_dir}' directory!")
    
    print(f"\nGenerated {len(emails_generated)} email(s) successfully!")
    print("You can now copy and paste the email content into your mail application.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
    except Exception as e:
        print(f"\nError: {e}")
        print("Please check your spreadsheet format and try again.")