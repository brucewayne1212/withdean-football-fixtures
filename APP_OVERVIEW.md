# Application Overview & Technical Documentation

## 1. Executive Summary
This application is a **Multi-Tenant SaaS platform** designed for football clubs (originally built for Withdean Youth FC) to streamline the administration of match fixtures. It automates the ingestion of fixture data from various sources (FA Full-Time, Spreadsheets), manages pitch/venue allocations, tracks team contacts, and generates professional, context-aware pre-match emails to opposition managers and referees.

## 2. Core Features
- **Multi-Tenancy:** Supports multiple organizations/clubs, with users scoped to specific organizations via Role-Based Access Control (RBAC).
- **Fixture Management:**
  - **Importing:** Ingests fixtures via CSV, Excel, Google Sheets, or direct scraping of FA Full-Time URLs.
  - **Parsing:** Intelligent parsing of free-text and various date/time formats.
  - **Management:** Dashboard to view pending, upcoming, and historical fixtures.
- **Venue & Pitch Management:**
  - Database of home pitches with specific details (parking, toilets, warm-up areas).
  - Integration with Google Maps (Static API and Links) and custom map uploads.
- **Automated Communications:**
  - **Smart Email Generation:** Generates "Home" and "Away" fixture confirmation emails.
  - **Context-Aware:** Includes specific kit colors, pitch maps, and manager contact details dynamically.
  - **Templating:** Customizable email templates per organization.
- **Task System:**
  - fixtures generate associated "Tasks" (e.g., "Send Home Email").
  - Tracks status (Pending, Waiting, In Progress, Completed) to ensure no fixture is missed.
- **Team Management:**
  - Internal "Managed Teams" (the user's club teams).
  - External "Opposition Teams" and their contact details (directory of managers/secretaries).

## 3. Technology Stack

### Backend
- **Language:** Python 3.11+
- **Framework:** Flask (Microframework)
- **ORM:** SQLAlchemy (with PostgreSQL in production, SQLite support for dev).
- **Authentication:** Flask-Login & Flask-Dance (Google OAuth2 for simplified sign-in).
- **Data Processing:** Pandas & OpenPyXL for heavy-lifting spreadsheet parsing.
- **Scraping:** Selenium (for FA Full-Time interaction where necessary).

### Frontend
- **Templating:** Jinja2 (Server-side rendering).
- **UI Framework:** Bootstrap 5 (Responsive design).
- **JavaScript:** Vanilla JS for dynamic dashboard interactions and async API calls.

### Database Schema (Key Models)
- **User:** Authentication and profile info.
- **Organization:** The tenant (Club) root entity.
- **Team:** Internal teams (e.g., "U12 Hawks") and Opposition teams.
- **Fixture:** Central entity linking two teams, a pitch, and a time.
- **Pitch:** Venue details including specific location instructions and maps.
- **Task:** Workflow items linked to fixtures.
- **TeamContact/TeamCoach:** Directory of internal coaches and external opposition contacts.

### Integrations & APIs
- **Google Maps Platform:**
  - Static Maps API (generating visual map images for emails).
  - Maps Embed/Links.
- **Google Sheets:** For reading live fixture spreadsheets.
- **Google OAuth:** For user authentication.

## 4. Project Structure
```
├── app.py                  # Application entry point & configuration
├── models.py               # SQLAlchemy Database Models
├── database.py             # Database connection manager
├── auth_manager.py         # Authentication logic
├── smart_email_generator.py# Core logic for email templating
├── routes/                 # Blueprint definitions
│   ├── api.py              # AJAX endpoints for frontend
│   ├── auth.py             # Login/Logout routes
│   ├── dashboard.py        # Main view logic
│   ├── imports.py          # Fixture import workflows
│   ├── tasks.py            # Task management views
│   └── settings.py         # Org & User settings
├── templates/              # Jinja2 HTML templates
├── static/                 # CSS, JS, Images, Uploads
├── utils.py                # Helper functions
├── Dockerfile              # Container definition
└── requirements.txt        # Python dependencies
```

## 5. Deployment & Infrastructure
- **Containerization:** Dockerized application for consistent environments.
- **Platform:** Configured for **Google Cloud Run** (Serverless container platform).
- **Database:** Designed for connection to a managed PostgreSQL instance (e.g., Cloud SQL or Neon).
- **Environment:**
  - Uses `.env` for local secrets.
  - Uses Environment Variables in production (Cloud Run revision settings).
- **Serving:** Uses `gunicorn` as the production WSGI HTTP server.

## 6. Key Workflows for Developers
1.  **Fixture Import:**
    -   *Source:* `routes/imports.py`
    -   Users upload a file or paste a URL.
    -   The system parses this into a standard format (`FixtureParser` / `FAFixtureParser`).
    -   It attempts to match "Teams" and "Pitches" against the database.
    -   New `Fixture` records are created, and associated `Task` records are generated automatically.

2.  **Email Generation:**
    -   *Source:* `smart_email_generator.py`
    -   When a user clicks "Generate Email" for a task.
    -   The system pulls the Fixture, Team (Kit colors), Pitch (Maps, Parking), and Coach (Contact info).
    -   It injects these into a template to produce the final email body text.

## 7. Setup for New Developers
1.  **Prerequisites:** Python 3.11+, PostgreSQL (optional, can use SQLite), Google Cloud SDK (for deployment).
2.  **Installation:**
    ```bash
    git clone <repo_url>
    cd footballFixtures
    python -m venv .venv
    source .venv/bin/activate  # or .venv\Scripts\activate on Windows
    pip install -r requirements.txt
    ```
3.  **Configuration:**
    -   Copy `.env.example` to `.env`.
    -   Set `SECRET_KEY` and database credentials.
    -   (Optional) Set `GOOGLE_MAPS_API_KEY` for map features.
4.  **Running:**
    ```bash
    python app.py
    ```

## 8. Areas for Attention / Roadmap
-   **FA Scraper Reliability:** The FA Full-Time website structure changes occasionally, which can break the `selenium`/`beautifulsoup` parsers in `fa_fixture_parser.py`.
-   **Data Hygiene:** Duplicate team names (e.g., "Hawks" vs "U12 Hawks") can occur during imports. The system has some matching logic, but edge cases exist.
-   **Email Sending:** Currently, the system *generates* the email text for the user to copy/paste into their client. Direct SMTP/API integration (SendGrid/Mailgun) could be a future enhancement.
