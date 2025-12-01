#!/bin/bash

# Deployment Pre-flight Checklist for Google Cloud App Engine

echo "🚀 Google Cloud Deployment Pre-flight Checklist"
echo "================================================"
echo ""

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "❌ gcloud CLI is not installed"
    echo "   Install from: https://cloud.google.com/sdk/docs/install"
    exit 1
fi
echo "✅ gcloud CLI is installed"

# Check if logged in
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" &> /dev/null; then
    echo "❌ Not logged in to gcloud"
    echo "   Run: gcloud auth login"
    exit 1
fi
echo "✅ Logged in to gcloud"

# Check project
PROJECT=$(gcloud config get-value project 2>/dev/null)
if [ -z "$PROJECT" ]; then
    echo "❌ No project configured"
    echo "   Run: gcloud config set project withdean-football-fixtures"
    exit 1
fi
echo "✅ Project configured: $PROJECT"

# Check if App Engine app exists
if ! gcloud app describe &> /dev/null; then
    echo "⚠️  App Engine app not created yet"
    echo "   You'll need to create it during first deployment"
    echo "   Recommended region: europe-west2 (London)"
else
    echo "✅ App Engine app exists"
fi

# Check for required files
echo ""
echo "📋 Checking required files..."
FILES=("app.yaml" "requirements.txt" "app.py" ".gcloudignore")
for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "✅ $file exists"
    else
        echo "❌ $file is missing"
        exit 1
    fi
done

# Check for Cloud SQL instance
echo ""
echo "🗄️  Database Configuration"
echo "   You need to configure Cloud SQL (PostgreSQL) for production"
echo "   Current options:"
echo "   1. Use existing Cloud SQL instance"
echo "   2. Create new Cloud SQL instance"
echo ""

# Environment variables reminder
echo "⚙️  Environment Variables Needed in Google Cloud:"
echo "   - SECRET_KEY (Flask secret key)"
echo "   - DATABASE_URL (Cloud SQL connection string)"
echo "   - GOOGLE_OAUTH_CLIENT_ID"
echo "   - GOOGLE_OAUTH_CLIENT_SECRET"
echo ""
echo "   Set these with:"
echo "   gcloud app deploy --set-env-vars KEY=VALUE"
echo ""

# Final checks
echo "📦 Dependencies Check"
if [ -f "requirements.txt" ]; then
    echo "   Total packages: $(wc -l < requirements.txt)"
    echo "   ✅ requirements.txt is ready"
fi

echo ""
echo "✨ Pre-flight check complete!"
echo ""
echo "Next steps:"
echo "1. Ensure Cloud SQL PostgreSQL instance is set up"
echo "2. Configure environment variables"
echo "3. Update OAuth redirect URIs in Google Console"
echo "4. Run: gcloud app deploy"
echo ""
