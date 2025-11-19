"""
SQLAlchemy models for Withdean Football Fixtures Multi-Tenant SaaS
"""

from sqlalchemy import create_engine, Column, String, Text, Boolean, DateTime, ForeignKey, CheckConstraint, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.sql import func
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

Base = declarative_base()

class User(Base):
    """User model for authentication and user management"""
    __tablename__ = 'users'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    picture_url = Column(Text)
    google_id = Column(String(255), unique=True)
    role = Column(String(50), default='user', nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_login_at = Column(DateTime(timezone=True))
    
    __table_args__ = (
        CheckConstraint("role IN ('user', 'admin')", name='check_user_role'),
    )
    
    # Relationships
    owned_organizations = relationship("Organization", back_populates="owner", cascade="all, delete-orphan")
    user_organizations = relationship("UserOrganization", back_populates="user")
    support_tickets = relationship("SupportTicket", foreign_keys="SupportTicket.user_id", back_populates="user")
    
    def __repr__(self):
        return f"<User(email='{self.email}', name='{self.name}')>"

class Organization(Base):
    """Organization/Club model"""
    __tablename__ = 'organizations'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False)
    description = Column(Text)
    owner_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    settings = Column(JSONB, default={})
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    owner = relationship("User", back_populates="owned_organizations")
    user_organizations = relationship("UserOrganization", back_populates="organization", cascade="all, delete-orphan")
    teams = relationship("Team", back_populates="organization", cascade="all, delete-orphan")
    pitches = relationship("Pitch", back_populates="organization", cascade="all, delete-orphan")
    fixtures = relationship("Fixture", back_populates="organization", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="organization", cascade="all, delete-orphan")
    team_contacts = relationship("TeamContact", back_populates="organization", cascade="all, delete-orphan")
    team_coaches = relationship("TeamCoach", back_populates="organization", cascade="all, delete-orphan")
    email_templates = relationship("EmailTemplate", back_populates="organization", cascade="all, delete-orphan")
    user_preferences = relationship("UserPreference", back_populates="organization", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Organization(name='{self.name}', slug='{self.slug}')>"

class UserOrganization(Base):
    """User-Organization membership model"""
    __tablename__ = 'user_organizations'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    organization_id = Column(UUID(as_uuid=True), ForeignKey('organizations.id'), nullable=False)
    role = Column(String(50), default='member')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    __table_args__ = (
        UniqueConstraint('user_id', 'organization_id'),
        CheckConstraint("role IN ('owner', 'admin', 'member')", name='check_user_org_role'),
    )
    
    # Relationships
    user = relationship("User", back_populates="user_organizations")
    organization = relationship("Organization", back_populates="user_organizations")

class Team(Base):
    """Team model"""
    __tablename__ = 'teams'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey('organizations.id'), nullable=False)
    name = Column(String(255), nullable=False)
    age_group = Column(String(50))
    is_managed = Column(Boolean, default=False)
    # Kit colours fields
    home_shirt = Column(String(255))
    home_shorts = Column(String(255))
    home_socks = Column(String(255))
    away_shirt = Column(String(255))
    away_shorts = Column(String(255))
    away_socks = Column(String(255))
    # FA Full-Time fixtures URL
    fa_fixtures_url = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        UniqueConstraint('organization_id', 'name'),
    )
    
    # Relationships
    organization = relationship("Organization", back_populates="teams")
    fixtures = relationship("Fixture", foreign_keys="Fixture.team_id", back_populates="team")
    opposition_fixtures = relationship("Fixture", foreign_keys="Fixture.opposition_team_id", back_populates="opposition_team")
    team_coaches = relationship("TeamCoach", back_populates="team", cascade="all, delete-orphan")
    
    def __repr__(self):
        # Avoid accessing organization relationship to prevent DetachedInstanceError
        return f"<Team(name='{self.name}', org_id='{self.organization_id}')>"

class Pitch(Base):
    """Pitch/Venue model"""
    __tablename__ = 'pitches'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey('organizations.id'), nullable=False)
    name = Column(String(255), nullable=False)
    address = Column(Text)
    parking_address = Column(Text)  # Separate parking address
    parking_info = Column(Text)
    toilet_info = Column(Text)
    special_instructions = Column(Text)
    opening_notes = Column(Text)
    warm_up_notes = Column(Text)
    map_image_url = Column(Text)  # URL to static map image for emails
    google_maps_link = Column(Text)  # Link to Google Maps
    custom_map_filename = Column(Text)  # Filename of uploaded custom map image
    parking_map_image_url = Column(Text)  # URL to parking map image for emails
    parking_google_maps_link = Column(Text)  # Link to parking location on Google Maps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        UniqueConstraint('organization_id', 'name'),
    )
    
    # Relationships
    organization = relationship("Organization", back_populates="pitches")
    fixtures = relationship("Fixture", back_populates="pitch")
    
    def __repr__(self):
        return f"<Pitch(name='{self.name}')>"

class Fixture(Base):
    """Fixture model"""
    __tablename__ = 'fixtures'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey('organizations.id'), nullable=False)
    team_id = Column(UUID(as_uuid=True), ForeignKey('teams.id'), nullable=False)
    opposition_team_id = Column(UUID(as_uuid=True), ForeignKey('teams.id'))
    opposition_name = Column(String(255))
    home_away = Column(String(10), nullable=False)
    pitch_id = Column(UUID(as_uuid=True), ForeignKey('pitches.id'))
    kickoff_datetime = Column(DateTime(timezone=True))
    kickoff_time_text = Column(String(100))
    match_format = Column(String(100))
    fixture_length = Column(String(50))
    each_way = Column(String(50))
    referee_info = Column(String(255))
    instructions = Column(Text)
    
    # Contact fields from CSV
    home_manager = Column(String(255))
    fixtures_sec = Column(String(255))
    manager_mobile = Column(String(50))
    contact_1 = Column(String(255))
    contact_2 = Column(String(255))
    contact_3 = Column(String(255))
    contact_5 = Column(String(255))
    
    status = Column(String(50), default='pending')
    is_cancelled = Column(Boolean, default=False)
    cancellation_reason = Column(Text)
    cancelled_at = Column(DateTime(timezone=True))
    is_archived = Column(Boolean, default=False)
    archived_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint("home_away IN ('Home', 'Away')", name='check_home_away'),
        CheckConstraint("status IN ('pending', 'waiting', 'in_progress', 'completed', 'cancelled')", name='check_fixture_status'),
    )
    
    # Relationships
    organization = relationship("Organization", back_populates="fixtures")
    team = relationship("Team", foreign_keys=[team_id], back_populates="fixtures")
    opposition_team = relationship("Team", foreign_keys=[opposition_team_id], back_populates="opposition_fixtures")
    pitch = relationship("Pitch", back_populates="fixtures")
    tasks = relationship("Task", back_populates="fixture", cascade="all, delete-orphan")
    
    def __repr__(self):
        opposition = self.opposition_team.name if self.opposition_team else self.opposition_name
        return f"<Fixture(team='{self.team.name if self.team else None}' vs '{opposition}')>"

class Task(Base):
    """Task model for fixture management"""
    __tablename__ = 'tasks'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey('organizations.id'), nullable=False)
    fixture_id = Column(UUID(as_uuid=True), ForeignKey('fixtures.id'), nullable=False)
    task_type = Column(String(50), nullable=False)
    status = Column(String(50), default='pending')
    notes = Column(Text)
    completed_at = Column(DateTime(timezone=True))
    is_archived = Column(Boolean, default=False)
    archived_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        CheckConstraint("task_type IN ('home_email', 'away_email')", name='check_task_type'),
        CheckConstraint("status IN ('pending', 'waiting', 'in_progress', 'completed')", name='check_task_status'),
    )
    
    # Relationships
    organization = relationship("Organization", back_populates="tasks")
    fixture = relationship("Fixture", back_populates="tasks")
    
    def __repr__(self):
        return f"<Task(type='{self.task_type}', status='{self.status}')>"

class TeamContact(Base):
    """Team contact model for external team contacts"""
    __tablename__ = 'team_contacts'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey('organizations.id'), nullable=False)
    team_name = Column(String(255), nullable=False)
    contact_name = Column(String(255))
    email = Column(String(255))
    phone = Column(String(50))
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        UniqueConstraint('organization_id', 'team_name'),
    )
    
    # Relationships
    organization = relationship("Organization", back_populates="team_contacts")
    
    def __repr__(self):
        return f"<TeamContact(team='{self.team_name}', contact='{self.contact_name}')>"

class TeamCoach(Base):
    """Team coach model for internal coaching staff"""
    __tablename__ = 'team_coaches'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey('organizations.id'), nullable=False)
    team_id = Column(UUID(as_uuid=True), ForeignKey('teams.id'), nullable=False)
    coach_name = Column(String(255), nullable=False)
    email = Column(String(255))
    phone = Column(String(50))
    role = Column(String(100), default='Coach')
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    organization = relationship("Organization", back_populates="team_coaches")
    team = relationship("Team", back_populates="team_coaches")
    
    def __repr__(self):
        return f"<TeamCoach(name='{self.coach_name}', role='{self.role}')>"

class EmailTemplate(Base):
    """Email template model"""
    __tablename__ = 'email_templates'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey('organizations.id'), nullable=False)
    template_type = Column(String(50), default='default')
    name = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        UniqueConstraint('organization_id', 'template_type'),
        CheckConstraint("template_type IN ('default', 'home_fixture')", name='check_template_type'),
    )
    
    # Relationships
    organization = relationship("Organization", back_populates="email_templates")
    
    def __repr__(self):
        return f"<EmailTemplate(name='{self.name}', type='{self.template_type}')>"

class UserPreference(Base):
    """User preferences model"""
    __tablename__ = 'user_preferences'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey('organizations.id'), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    preferences = Column(JSONB, default={})
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        UniqueConstraint('organization_id', 'user_id'),
    )
    
    # Relationships
    organization = relationship("Organization", back_populates="user_preferences")
    user = relationship("User")
    
    def __repr__(self):
        return f"<UserPreference(user_id='{self.user_id}', org_id='{self.organization_id}')>"

class SupportTicket(Base):
    """Support ticket model for admin oversight"""
    __tablename__ = 'support_tickets'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    organization_id = Column(UUID(as_uuid=True), ForeignKey('organizations.id'))
    subject = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    status = Column(String(50), default='open')
    priority = Column(String(20), default='normal')
    admin_response = Column(Text)
    admin_id = Column(UUID(as_uuid=True), ForeignKey('users.id'))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        CheckConstraint("status IN ('open', 'in_progress', 'resolved', 'closed')", name='check_ticket_status'),
        CheckConstraint("priority IN ('low', 'normal', 'high', 'urgent')", name='check_ticket_priority'),
    )
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id], back_populates="support_tickets")
    admin = relationship("User", foreign_keys=[admin_id])
    organization = relationship("Organization")
    
    def __repr__(self):
        return f"<SupportTicket(subject='{self.subject}', status='{self.status}')>"

class UsageAnalytics(Base):
    """Usage analytics model for tracking user behavior"""
    __tablename__ = 'usage_analytics'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey('organizations.id'))
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'))
    action = Column(String(100), nullable=False)
    resource_type = Column(String(50))
    resource_id = Column(UUID(as_uuid=True))
    event_metadata = Column(JSONB, default={})
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    organization = relationship("Organization")
    user = relationship("User")
    
    def __repr__(self):
        return f"<UsageAnalytics(action='{self.action}', user_id='{self.user_id}')>"


# Database configuration and session setup
class DatabaseManager:
    """Database manager for handling connections and sessions"""
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.engine = create_engine(database_url, echo=False)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
    
    def create_tables(self):
        """Create all tables"""
        Base.metadata.create_all(bind=self.engine)
    
    def get_session(self):
        """Get a database session"""
        return self.SessionLocal()
    
    def close(self):
        """Close database connection"""
        self.engine.dispose()


# Utility functions for working with the database
def get_or_create_organization(session, user_id: str, org_name: str, org_slug: str) -> Organization:
    """Get or create an organization for a user"""
    org = session.query(Organization).filter_by(slug=org_slug).first()
    if not org:
        org = Organization(
            name=org_name,
            slug=org_slug,
            owner_id=user_id,
            description=f"{org_name} - Football fixture management"
        )
        session.add(org)
        session.commit()
    return org

def get_or_create_team(session, organization_id: str, team_name: str, is_managed: bool = False) -> Team:
    """Get or create a team within an organization"""
    # Validate team name - must not be None or empty
    if not team_name or not team_name.strip():
        raise ValueError(f"Team name cannot be empty or None. Got: {repr(team_name)}")
    
    team_name = team_name.strip()
    team = session.query(Team).filter_by(
        organization_id=organization_id,
        name=team_name
    ).first()
    
    if not team:
        team = Team(
            organization_id=organization_id,
            name=team_name,
            is_managed=is_managed
        )
        session.add(team)
        session.commit()
    
    return team
