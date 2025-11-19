"""
Task Management System for Football Fixtures
Tracks home games (emails to send) and away games (emails to forward)
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum

class TaskType(Enum):
    HOME_EMAIL = "home_email"  # Send email to opposition
    AWAY_EMAIL = "away_email"  # Send email to opposition with our team details

class TaskStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress" 
    COMPLETED = "completed"
    WAITING = "waiting"  # Waiting for opposition email (away games)

@dataclass
class FixtureTask:
    id: str
    team: str
    opposition: str
    home_away: str
    pitch: str
    kickoff_time: str
    task_type: TaskType
    status: TaskStatus
    created_date: str
    completed_date: Optional[str] = None
    notes: str = ""
    # Additional fields for smart email generation
    league: Optional[str] = None
    home_manager: Optional[str] = None
    fixtures_sec: Optional[str] = None
    instructions: Optional[str] = None
    format: Optional[str] = None
    each_way: Optional[str] = None
    fixture_length: Optional[str] = None
    referee: Optional[str] = None
    manager_mobile: Optional[str] = None
    contact_1: Optional[str] = None
    contact_2: Optional[str] = None
    contact_3: Optional[str] = None
    contact_5: Optional[str] = None
    
    def to_dict(self):
        return {
            'id': self.id,
            'team': self.team,
            'opposition': self.opposition,
            'home_away': self.home_away,
            'pitch': self.pitch,
            'kickoff_time': self.kickoff_time,
            'task_type': self.task_type.value,
            'status': self.status.value,
            'created_date': self.created_date,
            'completed_date': self.completed_date,
            'notes': self.notes,
            'league': self.league,
            'home_manager': self.home_manager,
            'fixtures_sec': self.fixtures_sec,
            'instructions': self.instructions,
            'format': self.format,
            'each_way': self.each_way,
            'fixture_length': self.fixture_length,
            'referee': self.referee,
            'manager_mobile': self.manager_mobile,
            'contact_1': self.contact_1,
            'contact_2': self.contact_2,
            'contact_3': self.contact_3,
            'contact_5': self.contact_5
        }
    
    @classmethod
    def from_dict(cls, data):
        return cls(
            id=data['id'],
            team=data['team'],
            opposition=data['opposition'],
            home_away=data['home_away'],
            pitch=data['pitch'],
            kickoff_time=data['kickoff_time'],
            task_type=TaskType(data['task_type']),
            status=TaskStatus(data['status']),
            created_date=data['created_date'],
            completed_date=data.get('completed_date'),
            notes=data.get('notes', ''),
            league=data.get('league'),
            home_manager=data.get('home_manager'),
            fixtures_sec=data.get('fixtures_sec'),
            instructions=data.get('instructions'),
            format=data.get('format'),
            each_way=data.get('each_way'),
            fixture_length=data.get('fixture_length'),
            referee=data.get('referee'),
            manager_mobile=data.get('manager_mobile'),
            contact_1=data.get('contact_1'),
            contact_2=data.get('contact_2'),
            contact_3=data.get('contact_3'),
            contact_5=data.get('contact_5')
        )

class TaskManager:
    def __init__(self, data_file='fixture_tasks.json', user_id=None):
        # Support both single-user (legacy) and multi-user modes
        if user_id:
            self.data_file = f"user_data/{user_id}/fixture_tasks.json"
            self.user_id = user_id
        else:
            self.data_file = data_file
            self.user_id = None
            
        self.tasks: Dict[str, FixtureTask] = {}
        self.load_tasks()
    
    def load_tasks(self):
        """Load tasks from JSON file"""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r') as f:
                    data = json.load(f)
                    self.tasks = {
                        task_id: FixtureTask.from_dict(task_data)
                        for task_id, task_data in data.items()
                    }
            except Exception as e:
                print(f"Error loading tasks: {e}")
                self.tasks = {}
    
    def save_tasks(self):
        """Save tasks to JSON file"""
        try:
            data = {task_id: task.to_dict() for task_id, task in self.tasks.items()}
            with open(self.data_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving tasks: {e}")
    
    def create_task_from_fixture(self, fixture_data: Dict) -> FixtureTask:
        """Create a task from fixture data"""
        # Handle NaN values in task ID generation
        team = str(fixture_data['team']) if fixture_data['team'] is not None else 'unknown_team'
        opposition = str(fixture_data['opposition']) if fixture_data['opposition'] is not None and str(fixture_data['opposition']) != 'nan' else 'TBC'
        kickoff = str(fixture_data['kickoff_time']) if fixture_data['kickoff_time'] is not None and str(fixture_data['kickoff_time']) != 'nan' else 'TBC'
        
        task_id = f"{team}_{opposition}_{kickoff}"
        task_id = task_id.replace(' ', '_').replace('/', '_').replace(':', '_').replace('.', '_')
        
        # Determine task type based on home/away
        home_away_str = str(fixture_data['home_away']).lower().strip() if fixture_data['home_away'] is not None else ''
        if home_away_str in ['home', 'h']:
            task_type = TaskType.HOME_EMAIL
            initial_status = TaskStatus.PENDING
        else:
            task_type = TaskType.AWAY_EMAIL
            initial_status = TaskStatus.WAITING  # Waiting for opposition email
        
        task = FixtureTask(
            id=task_id,
            team=fixture_data['team'],
            opposition=fixture_data['opposition'],
            home_away=fixture_data['home_away'],
            pitch=fixture_data['pitch'],
            kickoff_time=fixture_data['kickoff_time'],
            task_type=task_type,
            status=initial_status,
            created_date=datetime.now().isoformat(),
            league=fixture_data.get('league'),
            home_manager=fixture_data.get('home_manager'),
            fixtures_sec=fixture_data.get('fixtures_sec'),
            instructions=fixture_data.get('instructions'),
            format=fixture_data.get('format'),
            each_way=fixture_data.get('each_way'),
            fixture_length=fixture_data.get('fixture_length'),
            referee=fixture_data.get('referee'),
            manager_mobile=fixture_data.get('manager_mobile'),
            contact_1=fixture_data.get('contact_1'),
            contact_2=fixture_data.get('contact_2'),
            contact_3=fixture_data.get('contact_3'),
            contact_5=fixture_data.get('contact_5')
        )
        
        return task
    
    def add_or_update_task(self, task: FixtureTask):
        """Add or update a task"""
        self.tasks[task.id] = task
        self.save_tasks()
    
    def mark_completed(self, task_id: str, notes: str = ""):
        """Mark a task as completed"""
        if task_id in self.tasks:
            self.tasks[task_id].status = TaskStatus.COMPLETED
            self.tasks[task_id].completed_date = datetime.now().isoformat()
            if notes:
                self.tasks[task_id].notes = notes
            self.save_tasks()
            return True
        return False
    
    def mark_in_progress(self, task_id: str):
        """Mark a task as in progress"""
        if task_id in self.tasks:
            self.tasks[task_id].status = TaskStatus.IN_PROGRESS
            self.save_tasks()
            return True
        return False
    
    def get_pending_tasks(self) -> List[FixtureTask]:
        """Get all pending tasks"""
        return [task for task in self.tasks.values() 
                if task.status == TaskStatus.PENDING]
    
    def get_waiting_tasks(self) -> List[FixtureTask]:
        """Get all tasks waiting for opposition emails"""
        return [task for task in self.tasks.values() 
                if task.status == TaskStatus.WAITING]
    
    def get_in_progress_tasks(self) -> List[FixtureTask]:
        """Get all in-progress tasks"""
        return [task for task in self.tasks.values() 
                if task.status == TaskStatus.IN_PROGRESS]
    
    def get_completed_tasks(self) -> List[FixtureTask]:
        """Get all completed tasks"""
        return [task for task in self.tasks.values() 
                if task.status == TaskStatus.COMPLETED]
    
    def get_tasks_by_type(self, task_type: TaskType) -> List[FixtureTask]:
        """Get all tasks of a specific type"""
        return [task for task in self.tasks.values() 
                if task.task_type == task_type]
    
    def get_task_summary(self) -> Dict:
        """Get a summary of all tasks"""
        summary = {
            'total': len(self.tasks),
            'pending': len(self.get_pending_tasks()),
            'waiting': len(self.get_waiting_tasks()),
            'in_progress': len(self.get_in_progress_tasks()),
            'completed': len(self.get_completed_tasks()),
            'home_games': len(self.get_tasks_by_type(TaskType.HOME_EMAIL)),
            'away_games': len(self.get_tasks_by_type(TaskType.AWAY_EMAIL))
        }
        return summary
    
    def clear_old_completed_tasks(self, days_old: int = 30):
        """Remove completed tasks older than specified days"""
        from datetime import datetime, timedelta
        cutoff_date = datetime.now() - timedelta(days=days_old)
        
        tasks_to_remove = []
        for task_id, task in self.tasks.items():
            if (task.status == TaskStatus.COMPLETED and 
                task.completed_date and 
                datetime.fromisoformat(task.completed_date) < cutoff_date):
                tasks_to_remove.append(task_id)
        
        for task_id in tasks_to_remove:
            del self.tasks[task_id]
        
        if tasks_to_remove:
            self.save_tasks()
        
        return len(tasks_to_remove)