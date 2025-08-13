#!/bin/bash
set -e

echo "🚀 Starting Fantasy Football Draft Helper Backend"

# Wait for database to be ready
echo "⏳ Waiting for PostgreSQL to be ready..."
while ! pg_isready -h db -p 5432 -U user -d fantasy_football; do
  echo "   PostgreSQL is unavailable - sleeping"
  sleep 2
done
echo "✅ PostgreSQL is ready!"

# Initialize database tables
echo "📋 Initializing database tables..."
python -c "
from app.data.database import create_tables
try:
    create_tables()
    print('✅ Database tables created successfully')
except Exception as e:
    print(f'⚠️  Database tables may already exist: {e}')
"

# Create directories for persistent data
echo "📁 Creating data directories..."
mkdir -p /app/draft_states
mkdir -p /app/learning_data

# Start the backend server
echo "🌐 Starting backend server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
