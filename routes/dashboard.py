from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload
from sqlalchemy import or_
from datetime import datetime, timedelta, timezone
from database import db_manager
from utils import get_user_organization
from models import Task, Fixture, Team, Organization

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
@login_required
def dashboard_view():
    """Main dashboard showing fixture overview"""
    session = db_manager.get_session()
    try:
        org = get_user_organization()
        if not org:
            flash('No organization found. Please contact support.', 'error')
            return redirect(url_for('auth.logout'))
        
        # Establish current week boundaries (start on Monday)
        today = datetime.now().date()
        current_week_start = today - timedelta(days=today.weekday())
        
        # Calculate next Sunday
        days_ahead = 6 - today.weekday()  # Sunday is 6
        if days_ahead <= 0:  # Today is Sunday or past
            days_ahead += 7
        next_sunday = today + timedelta(days=days_ahead)

        # Get the following 4 Sundays for calendar view
        upcoming_sundays = []
        for i in range(4):
            sunday = next_sunday + timedelta(weeks=i)
            upcoming_sundays.append(sunday)

        def is_current_or_future_fixture(fixture):
            """Return True if fixture has no date or is scheduled this week or later."""
            if not fixture or not fixture.kickoff_datetime:
                return True
            fixture_dt = fixture.kickoff_datetime
            if fixture_dt.tzinfo:
                fixture_dt = fixture_dt.astimezone(timezone.utc)
            return fixture_dt.date() >= current_week_start
            
        # 1. Optimize: Get managed teams in one query
        managed_teams = session.query(Team).filter_by(
            organization_id=org.id,
            is_managed=True
        ).all()
        managed_team_ids = [t.id for t in managed_teams]
        managed_teams_count = len(managed_teams)

        # 2. Optimize: Fetch ALL tasks for organization in one query with eager loading
        all_tasks_query = session.query(Task).filter_by(organization_id=org.id).filter(Task.is_archived != True)
        # Join with Fixture and Team to avoid N+1 later
        all_tasks = all_tasks_query.options(
            joinedload(Task.fixture).joinedload(Fixture.team),
            joinedload(Task.fixture).joinedload(Fixture.pitch),
            joinedload(Task.fixture).joinedload(Fixture.tasks)
        ).order_by(Task.created_at.desc()).all()
        
        # Filter for current/future
        all_current_tasks = [task for task in all_tasks if is_current_or_future_fixture(task.fixture)]
        
        # Separate into 'my tasks' (managed teams) and total
        my_tasks = [task for task in all_current_tasks if task.fixture.team_id in managed_team_ids]
        
        # 3. Optimize: Calculate global counts in memory (faster than multiple COUNT queries)
        summary = {
            'total': len(my_tasks),
            'pending': 0,
            'waiting': 0,
            'in_progress': 0,
            'completed': 0
        }
        
        for task in my_tasks:
            if task.status == 'pending':
                summary['pending'] += 1
            elif task.status == 'waiting':
                summary['waiting'] += 1
            elif task.status == 'in_progress':
                summary['in_progress'] += 1
            elif task.status == 'completed':
                summary['completed'] += 1

        # Enrich tasks for template compatibility (helper class for Enums)
        class TaskTypeEnum:
            def __init__(self, value):
                self.value = value
        
        class StatusEnum:
            def __init__(self, value):
                self.value = value

        # Helper to enrich a task object
        def enrich_task(task):
            if not hasattr(task, 'team'): # Only enrich if not already done
                fixture = task.fixture
                team = fixture.team
                
                task.team = team.name if team else 'Unknown Team'
                task.opposition = fixture.opposition_name or 'TBC'
                task.home_away = fixture.home_away
                task.pitch = fixture.pitch.name if fixture.pitch else 'TBC'
                task.kickoff_time = fixture.kickoff_time_text or 'TBC'
                task.match_date = fixture.kickoff_datetime.strftime('%a %d %b') if fixture.kickoff_datetime else 'TBC'
                task.created_date = task.created_at.isoformat() if task.created_at else ''
                task.completed_date = task.completed_at.isoformat() if task.completed_at else None
                
                # Wrapper for enums if string
                if isinstance(task.task_type, str):
                    task.task_type = TaskTypeEnum(task.task_type)
                if isinstance(task.status, str):
                    task.status = StatusEnum(task.status)
            return task

        # Enrich 'my_tasks' for the recent tasks lists
        for t in my_tasks:
            enrich_task(t)

        pending_tasks = [t for t in my_tasks if t.status.value == 'pending'][:5]
        waiting_tasks = [t for t in my_tasks if t.status.value == 'waiting'][:5]
        in_progress_tasks = [t for t in my_tasks if t.status.value == 'in_progress'][:5]
        completed_tasks = [t for t in my_tasks if t.status.value == 'completed'][:5]

        # 4. Optimize: Fetch relevant upcoming fixtures for managed teams in ONE query
        # Get fixtures for managed teams that are upcoming or undated
        try:
            from datetime import timezone as tz
            now_utc = datetime.now(tz.utc)
        except:
            now_utc = datetime.utcnow()

        upcoming_fixtures = session.query(Fixture).filter(
            Fixture.organization_id == org.id,
            Fixture.team_id.in_(managed_team_ids),
            or_(Fixture.kickoff_datetime >= now_utc, Fixture.kickoff_datetime == None)
        ).options(
            joinedload(Fixture.team),
            joinedload(Fixture.tasks) # Eager load tasks to avoid N+1 later
        ).order_by(Fixture.kickoff_datetime.asc().nullslast()).all()

        # Group fixtures by team_id in memory for O(1) access
        fixtures_by_team = {}
        for f in upcoming_fixtures:
            if f.team_id not in fixtures_by_team:
                fixtures_by_team[f.team_id] = []
            fixtures_by_team[f.team_id].append(f)

        # Group tasks by team_id in memory
        tasks_by_team = {}
        for t in all_current_tasks:
            # Ensure task is enriched (though mainly needed for filtered list)
            enrich_task(t)
            
            fid = t.fixture.team_id
            if fid not in tasks_by_team:
                tasks_by_team[fid] = []
            tasks_by_team[fid].append(t)

        # Build team status data using pre-fetched data
        team_status_data = []
        
        for team in managed_teams:
            team_fixtures = fixtures_by_team.get(team.id, [])
            team_tasks = tasks_by_team.get(team.id, [])

            # Determine next fixture
            next_fixture = None
            # Prioritize fixtures with tasks
            fixtures_with_tasks = [f for f in team_fixtures if f.tasks]
            if fixtures_with_tasks:
                # Logic: Undated or future dated
                for f in fixtures_with_tasks:
                     if f.kickoff_datetime is None:
                         next_fixture = f
                         break
                     # Compare (already filtered by query but double check)
                     if f.kickoff_datetime.tzinfo:
                         if f.kickoff_datetime >= now_utc:
                             next_fixture = f
                             break
                     elif f.kickoff_datetime >= datetime.now():
                         next_fixture = f
                         break
                if not next_fixture and fixtures_with_tasks:
                    next_fixture = fixtures_with_tasks[0]
            
            # Fallback to chronologically next
            if not next_fixture and team_fixtures:
                 next_fixture = team_fixtures[0]

            # Map fixtures to calendar
            fixture_calendar = {}
            for fixture in team_fixtures[:10]: # Limit to 10 upcoming
                if fixture.kickoff_datetime:
                    fixture_date = fixture.kickoff_datetime.date()
                    for sunday in upcoming_sundays:
                        days_diff = abs((fixture_date - sunday).days)
                        if days_diff <= 3:
                            fixture_calendar[sunday] = fixture
                            break
                else:
                    if next_fixture and fixture.id == next_fixture.id:
                        fixture_calendar[next_sunday] = fixture

            # Calculate Stats
            home_tasks = [t for t in team_tasks if t.fixture.home_away == 'Home']
            away_tasks = [t for t in team_tasks if t.fixture.home_away == 'Away']
            
            stats = {
                'total_fixtures': len(team_tasks),
                'total_tasks': len(team_tasks),
                'pending': len([t for t in team_tasks if t.status.value == 'pending']),
                'waiting': len([t for t in team_tasks if t.status.value == 'waiting']),
                'in_progress': len([t for t in team_tasks if t.status.value == 'in_progress']),
                'completed': len([t for t in team_tasks if t.status.value == 'completed']),
                
                'home_pending': len([t for t in home_tasks if t.status.value == 'pending']),
                'home_waiting': len([t for t in home_tasks if t.status.value == 'waiting']),
                'home_in_progress': len([t for t in home_tasks if t.status.value == 'in_progress']),
                'home_completed': len([t for t in home_tasks if t.status.value == 'completed']),
                
                'away_pending': len([t for t in away_tasks if t.status.value == 'pending']),
                'away_waiting': len([t for t in away_tasks if t.status.value == 'waiting']),
                'away_in_progress': len([t for t in away_tasks if t.status.value == 'in_progress']),
                'away_completed': len([t for t in away_tasks if t.status.value == 'completed']),
            }
            
            completion_percentage = (stats['completed'] / stats['total_tasks'] * 100) if stats['total_tasks'] > 0 else 0

            # Overall Status
            if stats['total_tasks'] == 0:
                overall_status = 'no_fixtures'
            elif stats['pending'] > 0:
                overall_status = 'action_needed'
            elif stats['waiting'] + stats['in_progress'] > 0:
                overall_status = 'in_progress'
            elif stats['completed'] > 0:
                overall_status = 'complete'
            else:
                overall_status = 'no_fixtures'

            # Communication Status & Primary Task
            comm_status = 'no_fixture'
            primary_task = None
            
            if next_fixture:
                # We already eager loaded tasks for upcoming fixtures
                next_fixture_tasks = next_fixture.tasks
                # Enrich them just in case
                for t in next_fixture_tasks: 
                     enrich_task(t)
                
                next_pending = [t for t in next_fixture_tasks if t.status.value == 'pending']
                next_waiting = [t for t in next_fixture_tasks if t.status.value in ['waiting', 'in_progress']]
                next_completed = [t for t in next_fixture_tasks if t.status.value == 'completed']
                
                if next_pending:
                    comm_status = 'action_needed'
                    primary_task = next_pending[0]
                elif next_waiting:
                    comm_status = 'in_progress'
                    primary_task = next_waiting[0]
                elif next_completed:
                    comm_status = 'complete'
                    primary_task = next_completed[0]
                else:
                    comm_status = 'pending'

            team_status_data.append({
                'team': team,
                'next_fixture': next_fixture,
                'upcoming_fixtures': team_fixtures[:10],
                'fixture_calendar': fixture_calendar,
                'next_sunday': next_sunday,
                'upcoming_sundays': upcoming_sundays,
                'comm_status': comm_status,
                'primary_task': primary_task,
                'has_next_sunday_fixture': next_sunday in fixture_calendar,
                # Stats
                'total_fixtures': stats['total_fixtures'],
                'total_tasks': stats['total_tasks'],
                'completion_percentage': completion_percentage,
                'overall_status': overall_status,
                'home_pending': stats['home_pending'],
                'home_waiting': stats['home_waiting'],
                'home_in_progress': stats['home_in_progress'],
                'home_completed': stats['home_completed'],
                'away_pending': stats['away_pending'],
                'away_waiting': stats['away_waiting'],
                'away_in_progress': stats['away_in_progress'],
                'away_completed': stats['away_completed'],
                'total_pending': stats['pending'],
                'total_waiting': stats['waiting'],
                'total_in_progress': stats['in_progress'],
                'total_completed': stats['completed']
            })

        # Get weekly sheet URL from org settings
        weekly_sheet_url = org.settings.get('weekly_sheet_url') if org.settings else None
        total_all_tasks = len(all_current_tasks)

        return render_template('dashboard.html',
            summary=summary,
            my_teams_count=managed_teams_count,
            total_tasks=total_all_tasks,
            pending_tasks=pending_tasks,
            waiting_tasks=waiting_tasks,
            completed_tasks=completed_tasks,
            team_status_data=team_status_data,
            user_name=current_user.name,
            weekly_sheet_url=weekly_sheet_url
        )
        
    finally:
        session.close()

@dashboard_bp.route('/debug_dates')
@login_required
def debug_dates():
    """Debug all dates in the system"""
    session = db_manager.get_session()
    try:
        org = get_user_organization()
        if not org:
            return "No organization found"

        from weekly_sheet_refresher import get_next_sunday as weekly_next_sunday
        
        # Calculate dashboard next Sunday (app logic)
        today = datetime.now().date()
        days_ahead = 6 - today.weekday()  # Sunday is 6
        if days_ahead <= 0:  # Today is Sunday or past
            days_ahead += 7
        app_next_sunday = today + timedelta(days=days_ahead)

        # Calculate refresher next Sunday
        refresh_next_sunday_str = weekly_next_sunday()
        refresh_next_sunday = datetime.strptime(refresh_next_sunday_str, '%Y-%m-%d').date()

        result = []
        result.append(f"<h2>Date Analysis</h2>")
        result.append(f"<p>Today: {today} ({today.strftime('%A')})</p>")
        result.append(f"<p>App next Sunday: {app_next_sunday} ({app_next_sunday.strftime('%A')})</p>")
        result.append(f"<p>Refresher next Sunday: {refresh_next_sunday} ({refresh_next_sunday.strftime('%A')})</p>")
        result.append(f"<p>Difference: {app_next_sunday - refresh_next_sunday}</p>")

        # Get all fixtures with dates
        fixtures = session.query(Fixture).filter_by(organization_id=org.id).all()

        result.append(f"<h3>All Fixtures ({len(fixtures)} total):</h3>")
        for fixture in fixtures:
            fixture_date = fixture.kickoff_datetime.date() if fixture.kickoff_datetime else None
            result.append(f"<li>{fixture.team.name if fixture.team else 'No Team'} vs {fixture.opposition_name}: {fixture_date} | {fixture.kickoff_datetime}</li>")

        # Check managed teams
        managed_teams = session.query(Team).filter_by(organization_id=org.id, is_managed=True).all()
        result.append(f"<h3>Managed Teams ({len(managed_teams)}):</h3>")
        for team in managed_teams:
            result.append(f"<li>{team.name} (ID: {team.id})</li>")

        return f"<html><body>{''.join(result)}</body></html>"

    finally:
        session.close()

@dashboard_bp.route('/debug_dashboard')
@login_required
def debug_dashboard():
    """Debug route to check dashboard data"""
    session = db_manager.get_session()
    try:
        org = get_user_organization()
        if not org:
            return f"No organization found"

        # Get managed teams
        managed_teams = session.query(Team).filter_by(
            organization_id=org.id,
            is_managed=True
        ).all()

        result = []
        for team in managed_teams:
            # Get all tasks for this team
            all_tasks = session.query(Task).join(Fixture).filter(
                Fixture.team_id == team.id,
                Task.organization_id == org.id,
                Task.is_archived != True
            ).all()

            pending_tasks = [t for t in all_tasks if t.status == 'pending']
            waiting_tasks = [t for t in all_tasks if t.status == 'waiting']
            in_progress_tasks = [t for t in all_tasks if t.status == 'in_progress']
            completed_tasks = [t for t in all_tasks if t.status == 'completed']

            total_fixtures = len(all_tasks)

            # Determine overall status
            if len(pending_tasks) > 0:
                overall_status = 'action_needed'
            elif len(waiting_tasks) + len(in_progress_tasks) > 0:
                overall_status = 'in_progress'
            elif len(completed_tasks) > 0:
                overall_status = 'complete'
            else:
                overall_status = 'no_fixtures'

            result.append({
                'team': team.name,
                'total_tasks': len(all_tasks),
                'total_fixtures': total_fixtures,
                'pending': len(pending_tasks),
                'waiting': len(waiting_tasks),
                'in_progress': len(in_progress_tasks),
                'completed': len(completed_tasks),
                'overall_status': overall_status
            })

        return f"<pre>{result}</pre>"

    finally:
        session.close()
