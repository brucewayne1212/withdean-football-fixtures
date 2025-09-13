#!/usr/bin/env python3
"""
Database reset script for Withdean Football Fixtures
Drops all tables and recreates the schema
"""

import psycopg2
import os

# Database connection string
DATABASE_URL = "postgresql://neondb_owner:npg_V1zDyIcxCOv9@ep-falling-shape-abr14uib-pooler.eu-west-2.aws.neon.tech/neondb?sslmode=require"

def reset_database():
    """Drop all tables and recreate schema"""
    try:
        # Connect to database
        print("Connecting to Neon database...")
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        cursor = conn.cursor()
        
        # Drop all tables (order matters due to foreign keys)
        print("Dropping existing tables...")
        drop_tables = [
            "usage_analytics",
            "support_tickets", 
            "user_preferences",
            "email_templates",
            "team_coaches",
            "team_contacts", 
            "tasks",
            "fixtures",
            "pitches",
            "teams",
            "user_organizations",
            "organizations",
            "users"
        ]
        
        for table in drop_tables:
            try:
                cursor.execute(f"DROP TABLE IF EXISTS {table} CASCADE;")
                print(f"  - Dropped {table}")
            except Exception as e:
                print(f"  - Warning: Could not drop {table}: {e}")
        
        # Drop the UUID extension and recreate it
        cursor.execute("DROP EXTENSION IF EXISTS \"uuid-ossp\" CASCADE;")
        
        # Read and execute schema file
        print("Creating database schema...")
        with open('database_schema.sql', 'r') as f:
            schema_sql = f.read()
        
        cursor.execute(schema_sql)
        print("✅ Database schema created successfully!")
        
        # Verify tables were created
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name;
        """)
        tables = cursor.fetchall()
        
        print(f"\n📊 Created {len(tables)} tables:")
        for table in tables:
            print(f"  - {table[0]}")
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"❌ Error resetting database: {e}")
        return False

if __name__ == "__main__":
    success = reset_database()
    if success:
        print("\n🎉 Database reset completed successfully!")
    else:
        print("\n💥 Database reset failed!")
        exit(1)