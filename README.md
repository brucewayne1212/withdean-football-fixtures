# 🏈 Withdean Youth FC Fixture Manager - Web Application

Modern web-based workflow management system for handling football fixtures. Upload CSV files, track tasks, generate emails, and manage your weekly fixture workflow through a beautiful web interface.

## 🚀 Quick Start Options

### Option 1: Run Locally
```bash
pip install -r requirements.txt
python app.py
```
Then open: http://localhost:8080

### Option 2: Deploy Online (Recommended)
See `DEPLOYMENT.md` for step-by-step deployment to **Railway**, **Render**, or **Vercel**. 

**🎯 Best choice: Railway** - Deploy in 2 minutes for $5/month!

## 🎯 What This System Does

### Home Games (You Send Emails):
- ✅ Automatically generates formatted emails using your Withdean Youth FC template
- 🏟️ Includes pitch-specific info (Stanley Deason boot policy, Dorothy Stringer parking, etc.)
- 📋 Tracks which emails you've sent to opposition teams
- ✅ Mark tasks as completed when emails are sent

### Away Games (You Forward Emails):  
- ⏳ Creates "waiting" tasks for emails you need to receive from opposition
- 📨 Track when you receive and forward emails to your teams
- ✅ Mark tasks as completed when forwarding is done

### Task Management:
- 📊 Dashboard showing pending, waiting, in-progress, and completed tasks
- 🔄 Never lose track of which teams need attention
- 📈 Weekly import of new fixtures creates tasks automatically
- 🧹 Automatic cleanup of old completed tasks

## 🗂️ File Structure

### Main Applications:
- `workflow_app.py` - **🎯 Main interactive workflow manager (USE THIS!)**
- `main.py` - Simple email generator (for one-off use)

### Core System:
- `fixture_parser.py` - Handles CSV/Excel reading and data extraction
- `managed_teams.py` - Configuration of your 33 managed teams
- `email_template.py` - Email generation with pitch-specific information
- `task_manager.py` - Task tracking and persistence system

### Configuration & Guides:
- `google_sheets_guide.md` - How to download Google Sheets as CSV
- `fixture_tasks.json` - Auto-created task storage (don't edit manually)
- `requirements.txt` - Python dependencies

## 📋 Weekly Workflow (Now Web-Based!)

1. **📥 Monday/Tuesday**: Download fixtures CSV from Google Sheets
2. **🌐 Open your web app**: Access from any device with internet
3. **📤 Upload CSV**: Drag and drop your file - automatic import!
4. **📧 Home Games**: Click to generate emails, copy-paste to send  
5. **📨 Away Games**: Mark as received/forwarded when emails arrive
6. **✅ Track Progress**: One-click task completion with notes
7. **📊 Monitor**: Beautiful dashboard shows what needs attention

## ✨ Web Interface Features

- **📊 Interactive Dashboard**: Visual cards showing pending, waiting, completed tasks
- **📤 Drag & Drop Upload**: No more file path errors - just drag your CSV file
- **📧 Email Preview**: Generate and copy emails with one click
- **📱 Mobile Friendly**: Works perfectly on phone, tablet, desktop
- **🔄 Auto-Refresh**: Dashboard updates automatically 
- **📋 Smart Filtering**: Filter tasks by type, status, team
- **📝 Task Notes**: Add completion notes for better tracking
- **🎨 Modern UI**: Clean, professional interface with Withdean colors

## ⚙️ Configuration

### Adding/Removing Teams
Edit `managed_teams.py` to update the list of teams you manage.

### Customizing Email Template  
Edit `email_template.py` to modify the email format or add new pitch types.

## 🎮 Interactive Features

The workflow app provides:

- **📋 Task Dashboard**: See all pending work at a glance
- **📧 Email Generation**: Generate properly formatted emails for home games
- **✅ Task Completion**: Mark tasks as done with notes
- **📊 Progress Tracking**: See completion statistics
- **🧹 Housekeeping**: Clean up old completed tasks

## 💡 Smart Features

- **🏠 Home/Away Detection**: Automatically creates different task types
- **🏟️ Venue Intelligence**: Includes correct parking, toilets, and special instructions
- **📱 Mobile-Friendly**: Works in terminal/command prompt on any device
- **💾 Persistent Storage**: Remembers your progress between sessions
- **🔄 Update Handling**: Re-importing fixtures updates existing tasks safely

## 📞 Support

- Check `google_sheets_guide.md` for CSV download instructions
- All your managed teams are configured in `managed_teams.py`
- Task data is stored in `fixture_tasks.json` (auto-managed)

---

**🏈 Never lose track of fixture communications again! 🏈**