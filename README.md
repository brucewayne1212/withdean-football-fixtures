# Withdean Football Fixtures

A comprehensive Flask web application for managing Withdean Youth FC football fixtures, generating emails, and tracking tasks.

## 🚀 Live Application
**Production URL:** https://withdean-football-fixtures-233242605158.us-central1.run.app

## ✨ Features
- **Fixture Management**: Import fixtures from CSV, Excel, or FA format files
- **Smart Email Generation**: Automatic email creation with venue details and contact info
- **Task Tracking**: Comprehensive task management with status tracking
- **Team Management**: User-specific team assignments and filtering
- **Responsive UI**: Modern Bootstrap-based interface
- **Production Ready**: Deployed on Google Cloud Run with Docker

## 🛠️ Technology Stack
- **Backend**: Flask, Python 3.11
- **Frontend**: Bootstrap 5, JavaScript
- **Data Processing**: Pandas, OpenPyXL
- **Deployment**: Docker, Google Cloud Run
- **File Parsing**: Custom parsers for CSV, Excel, and FA formats

## 📦 Installation

```bash
# Clone the repository
git clone https://github.com/monahan-mark/withdean-football-fixtures.git
cd withdean-football-fixtures

# Install dependencies
pip install -r requirements.txt

# Run locally
python app.py
```

## 🚀 Deployment

The application is configured for deployment on Google Cloud Run:

```bash
# Deploy to Cloud Run
gcloud run deploy withdean-football-fixtures \
    --source . \
    --platform managed \
    --region us-central1 \
    --allow-unauthenticated
```

## 🎯 Usage
1. **Import Fixtures**: Upload CSV, Excel, or FA format files
2. **Generate Emails**: Create professional emails for home fixtures
3. **Track Progress**: Monitor task completion and status
4. **Manage Teams**: Configure team assignments and preferences

## 🤖 AI-Powered Development
This project was developed with assistance from Claude Code, incorporating:
- Smart email templating with context-aware content
- Intelligent file parsing for multiple formats
- Automated task management workflows
- Production-ready deployment configuration

---
*Built for Withdean Youth FC • Deployed on Google Cloud Run*
