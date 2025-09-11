# Google OAuth Setup Guide

This guide walks you through setting up Google OAuth authentication for the Withdean Football Fixtures application.

## 1. Create Google OAuth Credentials

### Step 1: Go to Google Cloud Console
1. Visit [Google Cloud Console](https://console.cloud.google.com/)
2. Select your project `withdean-football-fixtures` (or create a new one)

### Step 2: Enable Google+ API
1. Go to **APIs & Services** > **Library**
2. Search for "Google+ API" and enable it
3. Also enable "Google OAuth2 API" if not already enabled

### Step 3: Create OAuth Credentials
1. Go to **APIs & Services** > **Credentials**
2. Click **+ CREATE CREDENTIALS** > **OAuth client ID**
3. If prompted, configure the OAuth consent screen first:
   - Application type: **External**
   - Application name: `Withdean Youth FC Fixture Manager`
   - User support email: Your email
   - Developer contact information: Your email
   - Save and continue through the scopes and test users sections

### Step 4: Configure OAuth Client
1. Application type: **Web application**
2. Name: `Withdean Football Fixtures`
3. **Authorized JavaScript origins:**
   - `http://localhost:8080` (for local development)
   - `https://withdean-football-fixtures-233242605158.us-central1.run.app` (production)
4. **Authorized redirect URIs:**
   - `http://localhost:8080/login/google/authorized` (for local development)
   - `https://withdean-football-fixtures-233242605158.us-central1.run.app/login/google/authorized` (production)
5. Click **CREATE**

### Step 5: Get Your Credentials
1. Copy the **Client ID** and **Client Secret**
2. Keep these secure - you'll need them for deployment

## 2. Set Environment Variables

### For Local Development:
Create a `.env` file (don't commit this to Git):
```bash
GOOGLE_OAUTH_CLIENT_ID=your_client_id_here
GOOGLE_OAUTH_CLIENT_SECRET=your_client_secret_here
SECRET_KEY=your-secure-secret-key-here
FLASK_ENV=development
```

### For Google Cloud Run Production:
Update your deployment command:
```bash
gcloud run deploy withdean-football-fixtures \
    --source . \
    --platform managed \
    --region us-central1 \
    --allow-unauthenticated \
    --set-env-vars="SECRET_KEY=withdean-youth-fc-production-secret-2024,GOOGLE_OAUTH_CLIENT_ID=your_client_id_here,GOOGLE_OAUTH_CLIENT_SECRET=your_client_secret_here"
```

## 3. Test the Authentication

### Local Testing:
```bash
# Install dependencies
pip install -r requirements.txt

# Run the app
python app.py
```

### Access the Application:
1. Visit `http://localhost:8080` (local) or your Cloud Run URL
2. You should be redirected to the login page
3. Click "Sign in with Google"
4. Complete the OAuth flow
5. You should be logged in and see your personalized dashboard

## 4. Multi-User Features

Once authentication is working, users will have:

✅ **Personal Accounts**: Each Google account gets separate data
✅ **Team Management**: Users configure their own managed teams  
✅ **Task Isolation**: Users only see their own fixtures and tasks
✅ **Settings**: Personal preferences and pitch configurations
✅ **File Uploads**: User-specific upload directories
✅ **Secure Sessions**: Google OAuth handles authentication

## 5. Troubleshooting

### Common Issues:

**"Redirect URI mismatch"**
- Ensure your redirect URIs in Google Console exactly match your app URLs
- Local: `http://localhost:8080/login/google/authorized`  
- Production: `https://your-app-url/login/google/authorized`

**"OAuth Error"**
- Check that Google+ API is enabled
- Verify your Client ID and Client Secret are set correctly
- Ensure environment variables are properly configured

**"User not found"**
- The AuthManager will automatically create new users on first login
- Check that the `user_data` directory is writable

### Migration Notes:
- Existing single-user data will be automatically migrated to the first user account
- Original files will be moved to `user_data/[user_id]/`
- The migration happens automatically when the first user signs in

## 6. Next Steps

After authentication is working:
1. Test with multiple Google accounts
2. Verify data isolation between users
3. Configure team assignments for each user
4. Test the complete workflow from login to email generation

---
**Security Note**: Never commit your Client ID and Client Secret to version control. Always use environment variables for sensitive configuration.