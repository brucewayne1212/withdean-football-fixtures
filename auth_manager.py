"""
Google OAuth Authentication Manager
Handles user authentication, registration, and session management with Google OAuth
"""

import json
import os
import hashlib
from datetime import datetime
from typing import Dict, Optional, List
from flask import session, current_app
from flask_login import UserMixin

class User(UserMixin):
    """User class for Flask-Login"""
    
    def __init__(self, user_id: str, email: str, name: str, picture: str = None, created_date: str = None):
        self.id = user_id
        self.email = email
        self.name = name
        self.picture = picture
        self.created_date = created_date or datetime.now().isoformat()
        self.is_active = True
        self.is_authenticated = True
        self.is_anonymous = False
    
    def get_id(self):
        return self.id
    
    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'name': self.name,
            'picture': self.picture,
            'created_date': self.created_date,
            'is_active': self.is_active
        }
    
    @classmethod
    def from_dict(cls, data):
        return cls(
            user_id=data['id'],
            email=data['email'],
            name=data['name'],
            picture=data.get('picture'),
            created_date=data.get('created_date')
        )

class AuthManager:
    """Manages user authentication and user data storage"""
    
    def __init__(self, users_file='users.json'):
        self.users_file = users_file
        self.users = {}
        self.load_users()
    
    def load_users(self):
        """Load users from JSON file"""
        if os.path.exists(self.users_file):
            try:
                with open(self.users_file, 'r') as f:
                    users_data = json.load(f)
                    self.users = {
                        user_id: User.from_dict(data) 
                        for user_id, data in users_data.items()
                    }
            except Exception as e:
                print(f"Error loading users: {e}")
                self.users = {}
    
    def save_users(self):
        """Save users to JSON file"""
        try:
            users_data = {
                user_id: user.to_dict() 
                for user_id, user in self.users.items()
            }
            with open(self.users_file, 'w') as f:
                json.dump(users_data, f, indent=2)
        except Exception as e:
            print(f"Error saving users: {e}")
    
    def create_user_id(self, email: str) -> str:
        """Create a consistent user ID from email"""
        return hashlib.md5(email.lower().encode()).hexdigest()[:12]
    
    def get_user(self, user_id: str) -> Optional[User]:
        """Get user by ID"""
        return self.users.get(user_id)
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email"""
        for user in self.users.values():
            if user.email.lower() == email.lower():
                return user
        return None
    
    def create_or_update_user(self, email: str, name: str, picture: str = None) -> User:
        """Create a new user or update existing user from Google OAuth data"""
        user_id = self.create_user_id(email)
        
        if user_id in self.users:
            # Update existing user
            user = self.users[user_id]
            user.name = name
            user.picture = picture
        else:
            # Create new user
            user = User(
                user_id=user_id,
                email=email,
                name=name,
                picture=picture
            )
            self.users[user_id] = user
            
            # Create user data directories
            self._create_user_directories(user_id)
            
            # Migrate existing data if this is the first user and old data exists
            if len(self.users) == 1:
                self._migrate_existing_data(user_id)
        
        self.save_users()
        return user
    
    def _create_user_directories(self, user_id: str):
        """Create directory structure for new user"""
        user_dir = f"user_data/{user_id}"
        os.makedirs(user_dir, exist_ok=True)
        
        # Create empty uploads directory for user
        uploads_dir = f"{user_dir}/uploads"
        os.makedirs(uploads_dir, exist_ok=True)
        
        # Create .gitkeep for uploads
        with open(f"{uploads_dir}/.gitkeep", 'w') as f:
            f.write("# User-specific uploads directory\n")
    
    def _migrate_existing_data(self, user_id: str):
        """Migrate existing single-user data to the first multi-user account"""
        user_dir = f"user_data/{user_id}"
        
        # Migrate user settings
        if os.path.exists('user_settings.json'):
            os.rename('user_settings.json', f"{user_dir}/user_settings.json")
            print(f"Migrated user_settings.json to {user_dir}/")
        
        # Migrate fixture tasks
        if os.path.exists('fixture_tasks.json'):
            os.rename('fixture_tasks.json', f"{user_dir}/fixture_tasks.json")
            print(f"Migrated fixture_tasks.json to {user_dir}/")
        
        # Create backup of uploads
        if os.path.exists('uploads') and os.listdir('uploads'):
            import shutil
            for item in os.listdir('uploads'):
                if item != '.gitkeep':
                    src = f"uploads/{item}"
                    dst = f"{user_dir}/uploads/{item}"
                    if os.path.isfile(src):
                        shutil.copy2(src, dst)
                    elif os.path.isdir(src):
                        shutil.copytree(src, dst)
            print(f"Migrated uploads to {user_dir}/uploads/")
    
    def get_user_data_path(self, user_id: str, filename: str) -> str:
        """Get path to user-specific data file"""
        return f"user_data/{user_id}/{filename}"
    
    def get_user_uploads_path(self, user_id: str) -> str:
        """Get path to user-specific uploads directory"""
        return f"user_data/{user_id}/uploads"
    
    def delete_user(self, user_id: str):
        """Delete a user and their data (admin function)"""
        if user_id in self.users:
            del self.users[user_id]
            self.save_users()
            
            # Remove user data directory
            import shutil
            user_dir = f"user_data/{user_id}"
            if os.path.exists(user_dir):
                shutil.rmtree(user_dir)
    
    def get_all_users(self) -> List[User]:
        """Get all users (admin function)"""
        return list(self.users.values())
    
    def get_user_count(self) -> int:
        """Get total number of users"""
        return len(self.users)