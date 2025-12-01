# Quick Deployment Guide - Neon PostgreSQL + Google Cloud

## ✅ Connection Status: VERIFIED

Your Neon PostgreSQL database is **fully compatible** with Google Cloud App Engine and ready for deployment!

### Current Setup:
- **Database**: Neon PostgreSQL (Serverless)
- **Region**: eu-west-2 (London) ✅ Matches App Engine region
- **Connection**: SSL enabled with connection pooling
- **Tables**: 13 tables detected
- **Users**: 1 user in database

---

## Deployment Steps (Simplified for Neon)

### 1. Prepare Environment Variables

Create `env_vars.yaml` with your credentials:

```yaml
env_variables:
  DATABASE_URL: "postgresql://neondb_owner:npg_V1zDyIcxCOv9@ep-falling-shape-abr14uib-pooler.eu-west-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
  SECRET_KEY: "your-secret-key-from-local-env"
  GOOGLE_OAUTH_CLIENT_ID: "your-client-id.apps.googleusercontent.com"
  GOOGLE_OAUTH_CLIENT_SECRET: "your-client-secret"
  FLASK_ENV: "production"
```

**⚠️ IMPORTANT**: Get SECRET_KEY, GOOGLE_OAUTH_CLIENT_ID, and GOOGLE_OAUTH_CLIENT_SECRET from your local `.env` file.

### 2. Update Google OAuth Redirect URIs

Before deploying, add these to your [Google Cloud Console OAuth credentials](https://console.cloud.google.com/apis/credentials):

**Authorized redirect URIs:**
- `https://withdean-football-fixtures.ew.r.appspot.com/login/google/authorized`
- `https://withdean-football-fixtures.ew.r.appspot.com/oauth2callback`

(The exact URL will be confirmed after first deployment)

### 3. Deploy to Google Cloud

```bash
# Run pre-flight check
./deploy_preflight.sh

# Deploy with environment variables
gcloud app deploy app.yaml \
  --project=withdean-football-fixtures

# When prompted, choose region: europe-west2 (London)
```

**Alternative**: Deploy with env_vars.yaml:
```bash
# Merge app.yaml with env_vars.yaml
cat env_vars.yaml >> app.yaml

# Then deploy
gcloud app deploy
```

### 4. Verify Deployment

```bash
# View logs
gcloud app logs tail -s default

# Open in browser
gcloud app browse
```

---

## Why Neon + App Engine is Great

✅ **No Cloud SQL needed** - Saves ~$7-10/month
✅ **Serverless-to-serverless** - Both scale automatically
✅ **Connection pooling built-in** - Optimal for App Engine
✅ **No VPC configuration** - Simple setup
✅ **Same region** - Low latency (both in London/eu-west-2)
✅ **SSL by default** - Secure connections

---

## Cost Estimate

- **App Engine**: ~$0.05/hour when active (28 free hours/day)
- **Neon PostgreSQL**: Free tier or ~$19/month for Pro
- **Total**: Potentially **FREE** with both free tiers!

---

## Quick Deploy Command

```bash
# One-command deployment (after setting up env_vars.yaml)
gcloud app deploy app.yaml --quiet
```

---

## Troubleshooting

### If deployment fails:
```bash
# Check logs
gcloud app logs tail -s default

# Verify environment variables
gcloud app describe
```

### If database connection fails:
1. Verify DATABASE_URL is correct in env_vars.yaml
2. Check Neon dashboard for connection limits
3. Ensure SSL mode is set to `require`

---

## Next Steps

1. ✅ Database connection verified
2. 📝 Create `env_vars.yaml` with your credentials
3. 🔑 Update Google OAuth redirect URIs
4. 🚀 Run: `gcloud app deploy`
5. ✨ Test your deployed app!

**Ready to deploy?** Your database is already set up and working!