-- Withdean Football Fixtures - Multi-Tenant SaaS Database Schema
-- PostgreSQL Schema for Neon Database

-- Enable UUID extension for generating unique IDs
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Users table - stores all authenticated users
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    picture_url TEXT,
    google_id VARCHAR(255) UNIQUE,
    role VARCHAR(50) DEFAULT 'user' CHECK (role IN ('user', 'admin')),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_login_at TIMESTAMP WITH TIME ZONE
);

-- Organizations/Clubs table - each user belongs to an organization
CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL, -- URL-friendly name
    description TEXT,
    owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    settings JSONB DEFAULT '{}', -- Flexible settings storage
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- User-Organization membership (for potential multi-org support later)
CREATE TABLE user_organizations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    role VARCHAR(50) DEFAULT 'member' CHECK (role IN ('owner', 'admin', 'member')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, organization_id)
);

-- Teams table - teams within each organization
CREATE TABLE teams (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    age_group VARCHAR(50),
    is_managed BOOLEAN DEFAULT false, -- Whether this org manages this team
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(organization_id, name)
);

-- Pitches/Venues table
CREATE TABLE pitches (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    address TEXT,
    parking_info TEXT,
    toilet_info TEXT,
    special_instructions TEXT,
    opening_notes TEXT,
    warm_up_notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(organization_id, name)
);

-- Fixtures table - main fixture data
CREATE TABLE fixtures (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    team_id UUID NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    opposition_team_id UUID REFERENCES teams(id), -- Can be null for external teams
    opposition_name VARCHAR(255), -- For external teams
    home_away VARCHAR(10) NOT NULL CHECK (home_away IN ('Home', 'Away')),
    pitch_id UUID REFERENCES pitches(id),
    kickoff_datetime TIMESTAMP WITH TIME ZONE,
    kickoff_time_text VARCHAR(100), -- Original text from import
    match_format VARCHAR(100),
    fixture_length VARCHAR(50),
    each_way VARCHAR(50),
    referee_info VARCHAR(255),
    instructions TEXT,
    
    -- Contact fields from original CSV structure
    home_manager VARCHAR(255),
    fixtures_sec VARCHAR(255),
    manager_mobile VARCHAR(50),
    contact_1 VARCHAR(255),
    contact_2 VARCHAR(255),
    contact_3 VARCHAR(255),
    contact_5 VARCHAR(255),
    
    -- Status tracking
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'waiting', 'in_progress', 'completed')),
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Tasks table - tracks what needs to be done for each fixture
CREATE TABLE tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    fixture_id UUID NOT NULL REFERENCES fixtures(id) ON DELETE CASCADE,
    task_type VARCHAR(50) NOT NULL CHECK (task_type IN ('home_email', 'away_forward')),
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'waiting', 'in_progress', 'completed')),
    notes TEXT,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Team contacts table - external team contact information
CREATE TABLE team_contacts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    team_name VARCHAR(100) NOT NULL,
    contact_name VARCHAR(100) NOT NULL,
    role VARCHAR(50),
    email VARCHAR(120),
    phone VARCHAR(20),
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(organization_id, team_name)
);

-- Team coaches table - internal team coaching staff
CREATE TABLE team_coaches (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    team_id UUID NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    coach_name VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    phone VARCHAR(50),
    role VARCHAR(100) DEFAULT 'Coach',
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Email templates table - custom email templates per organization
CREATE TABLE email_templates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    template_type VARCHAR(50) DEFAULT 'default' CHECK (template_type IN ('default', 'home_fixture')),
    name VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(organization_id, template_type)
);

-- User preferences table - per-organization user preferences
CREATE TABLE user_preferences (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    preferences JSONB DEFAULT '{}', -- Flexible JSON storage for preferences
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(organization_id, user_id)
);

-- Admin tables for system oversight

-- Support tickets table
CREATE TABLE support_tickets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    organization_id UUID REFERENCES organizations(id) ON DELETE SET NULL,
    subject VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    status VARCHAR(50) DEFAULT 'open' CHECK (status IN ('open', 'in_progress', 'resolved', 'closed')),
    priority VARCHAR(20) DEFAULT 'normal' CHECK (priority IN ('low', 'normal', 'high', 'urgent')),
    admin_response TEXT,
    admin_id UUID REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Usage analytics table
CREATE TABLE usage_analytics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID REFERENCES organizations(id) ON DELETE SET NULL,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50),
    resource_id UUID,
    event_metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_google_id ON users(google_id);
CREATE INDEX idx_organizations_slug ON organizations(slug);
CREATE INDEX idx_organizations_owner ON organizations(owner_id);
CREATE INDEX idx_user_organizations_user ON user_organizations(user_id);
CREATE INDEX idx_user_organizations_org ON user_organizations(organization_id);
CREATE INDEX idx_teams_org ON teams(organization_id);
CREATE INDEX idx_pitches_org ON pitches(organization_id);
CREATE INDEX idx_fixtures_org ON fixtures(organization_id);
CREATE INDEX idx_fixtures_team ON fixtures(team_id);
CREATE INDEX idx_fixtures_datetime ON fixtures(kickoff_datetime);
CREATE INDEX idx_tasks_org ON tasks(organization_id);
CREATE INDEX idx_tasks_fixture ON tasks(fixture_id);
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_team_contacts_org ON team_contacts(organization_id);
CREATE INDEX idx_team_coaches_org ON team_coaches(organization_id);
CREATE INDEX idx_team_coaches_team ON team_coaches(team_id);
CREATE INDEX idx_email_templates_org ON email_templates(organization_id);
CREATE INDEX idx_user_preferences_org_user ON user_preferences(organization_id, user_id);
CREATE INDEX idx_support_tickets_user ON support_tickets(user_id);
CREATE INDEX idx_support_tickets_status ON support_tickets(status);
CREATE INDEX idx_usage_analytics_org ON usage_analytics(organization_id);
CREATE INDEX idx_usage_analytics_user ON usage_analytics(user_id);
CREATE INDEX idx_usage_analytics_created ON usage_analytics(created_at);

-- Create functions for updated_at timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Add triggers for updated_at columns
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_organizations_updated_at BEFORE UPDATE ON organizations FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_teams_updated_at BEFORE UPDATE ON teams FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_pitches_updated_at BEFORE UPDATE ON pitches FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_fixtures_updated_at BEFORE UPDATE ON fixtures FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_tasks_updated_at BEFORE UPDATE ON tasks FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_team_contacts_updated_at BEFORE UPDATE ON team_contacts FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_team_coaches_updated_at BEFORE UPDATE ON team_coaches FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_email_templates_updated_at BEFORE UPDATE ON email_templates FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_user_preferences_updated_at BEFORE UPDATE ON user_preferences FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_support_tickets_updated_at BEFORE UPDATE ON support_tickets FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Insert default admin user (you can update this with your actual details)
INSERT INTO users (email, name, role) VALUES 
('monahan.mark@gmail.com', 'Mark Monahan', 'admin')
ON CONFLICT (email) DO UPDATE SET 
    role = 'admin',
    updated_at = CURRENT_TIMESTAMP;

-- Create your organization
INSERT INTO organizations (name, slug, description, owner_id) VALUES 
('Withdean Youth FC', 'withdean-youth-fc', 'Withdean Youth Football Club - Original fixture management system', 
 (SELECT id FROM users WHERE email = 'monahan.mark@gmail.com'))
ON CONFLICT (slug) DO NOTHING;

COMMIT;