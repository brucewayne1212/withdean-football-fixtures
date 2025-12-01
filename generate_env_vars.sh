#!/bin/bash

echo "🔧 Generating env_vars.yaml for Google Cloud deployment"
echo "========================================================"
echo ""

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "❌ .env file not found"
    exit 1
fi

# Extract values from .env
DATABASE_URL=$(grep "^DATABASE_URL=" .env | cut -d'=' -f2-)
SECRET_KEY=$(grep "^SECRET_KEY=" .env | cut -d'=' -f2-)
GOOGLE_OAUTH_CLIENT_ID=$(grep "^GOOGLE_OAUTH_CLIENT_ID=" .env | cut -d'=' -f2-)
GOOGLE_OAUTH_CLIENT_SECRET=$(grep "^GOOGLE_OAUTH_CLIENT_SECRET=" .env | cut -d'=' -f2-)

# Create env_vars.yaml
cat > env_vars.yaml << EOF
env_variables:
  DATABASE_URL: "$DATABASE_URL"
  SECRET_KEY: "$SECRET_KEY"
  GOOGLE_OAUTH_CLIENT_ID: "$GOOGLE_OAUTH_CLIENT_ID"
  GOOGLE_OAUTH_CLIENT_SECRET: "$GOOGLE_OAUTH_CLIENT_SECRET"
  FLASK_ENV: "production"
EOF

echo "✅ env_vars.yaml created successfully!"
echo ""
echo "📋 Environment variables configured:"
echo "   ✅ DATABASE_URL (Neon PostgreSQL)"
echo "   ✅ SECRET_KEY"
echo "   ✅ GOOGLE_OAUTH_CLIENT_ID"
echo "   ✅ GOOGLE_OAUTH_CLIENT_SECRET"
echo "   ✅ FLASK_ENV: production"
echo ""
echo "⚠️  SECURITY NOTE:"
echo "   env_vars.yaml contains sensitive credentials"
echo "   It is already in .gitignore - DO NOT commit it to git"
echo ""
echo "Next step: Run 'gcloud app deploy' to deploy your app"
