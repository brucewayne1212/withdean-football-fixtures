#!/bin/bash

echo "🔍 Checking Neon PostgreSQL compatibility with Google Cloud App Engine"
echo "========================================================================"
echo ""

# Extract database details
DB_URL=$(grep "DATABASE_URL=" .env | cut -d'=' -f2)

if [[ $DB_URL == *"neon.tech"* ]]; then
    echo "✅ Neon PostgreSQL detected"
    echo ""
    
    # Extract region
    if [[ $DB_URL == *"eu-west-2"* ]]; then
        echo "✅ Database region: eu-west-2 (London)"
        echo "   This matches well with App Engine europe-west2"
    else
        echo "⚠️  Database region: Check if it matches your App Engine region"
    fi
    
    # Check SSL mode
    if [[ $DB_URL == *"sslmode=require"* ]]; then
        echo "✅ SSL mode: Required (secure connection)"
    fi
    
    # Check connection pooling
    if [[ $DB_URL == *"pooler"* ]]; then
        echo "✅ Connection pooling: Enabled"
        echo "   This is optimal for serverless environments like App Engine"
    fi
    
    echo ""
    echo "📋 Neon + Google Cloud App Engine Compatibility:"
    echo "   ✅ External connections: Supported"
    echo "   ✅ SSL/TLS: Supported"
    echo "   ✅ Connection pooling: Supported"
    echo "   ✅ Serverless-friendly: Yes"
    echo "   ✅ No VPC configuration needed: Yes"
    echo ""
    
    echo "💡 Benefits of using Neon with App Engine:"
    echo "   • No Cloud SQL costs (~$7-10/month saved)"
    echo "   • Automatic scaling with your app"
    echo "   • Built-in connection pooling"
    echo "   • Serverless architecture (pay for what you use)"
    echo "   • No complex VPC setup required"
    echo ""
    
    echo "⚙️  Configuration for deployment:"
    echo "   Your DATABASE_URL can be used as-is in App Engine"
    echo "   Just set it as an environment variable during deployment"
    echo ""
    
else
    echo "❌ Neon PostgreSQL not detected in DATABASE_URL"
fi

# Test connection
echo "🧪 Testing database connection..."
python3 -c "
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()
db_url = os.getenv('DATABASE_URL')

try:
    engine = create_engine(db_url, pool_pre_ping=True)
    with engine.connect() as conn:
        conn.execute(text('SELECT 1'))
    print('✅ Connection test: PASSED')
    print('   Database is accessible and ready for deployment')
except Exception as e:
    print(f'❌ Connection test: FAILED')
    print(f'   Error: {str(e)}')
" 2>&1

echo ""
echo "✨ Compatibility check complete!"
