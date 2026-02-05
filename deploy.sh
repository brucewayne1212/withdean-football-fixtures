#!/bin/bash

# Configuration
PROJECT_ID="withdean-football-fixtures"
REGION="europe-west2"
SERVICE_NAME="football-fixtures"

echo "Using project: $PROJECT_ID"
gcloud config set project $PROJECT_ID

# Deploy using Cloud Build
gcloud builds submit --config cloudbuild.yaml .

echo ""
echo "Deployment triggered via Cloud Build."
echo "You can check the progress in the Google Cloud Console."
