#!/bin/bash

echo "🚀 Fantasy Football Draft Helper - Complete Setup"
echo "=================================================="

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker Desktop first."
    exit 1
fi

echo "✅ Docker is running"

# Stop any existing containers
echo "🛑 Stopping any existing containers..."
docker-compose down

# Build and start all services
echo "🏗️  Building and starting all services..."
echo "   - PostgreSQL Database"
echo "   - Backend API Server"
echo "   - Data Scraper"
echo "   - Frontend Web App"

docker-compose up --build -d

echo ""
echo "⏳ Waiting for services to be ready..."
echo "   This may take a few minutes on first run..."

# Wait for backend to be healthy
echo "   Waiting for backend API..."
timeout 300 bash -c 'until curl -f http://localhost:8001/health > /dev/null 2>&1; do sleep 5; done'

if [ $? -eq 0 ]; then
    echo "✅ Backend API is ready!"
else
    echo "❌ Backend API failed to start within 5 minutes"
    docker-compose logs backend
    exit 1
fi

# Wait for frontend to be ready
echo "   Waiting for frontend..."
timeout 180 bash -c 'until curl -f http://localhost:3001 > /dev/null 2>&1; do sleep 5; done'

if [ $? -eq 0 ]; then
    echo "✅ Frontend is ready!"
else
    echo "❌ Frontend failed to start within 3 minutes"
    docker-compose logs frontend
    exit 1
fi

echo ""
echo "🎉 Fantasy Football Draft Helper is now running!"
echo "=================================================="
echo ""
echo "📱 Access the application:"
echo "   🌐 Frontend:  http://localhost:3001"
echo "   🔧 Backend:   http://localhost:8001"
echo "   📊 API Docs:  http://localhost:8001/docs"
echo ""
echo "📊 Services Status:"
docker-compose ps

echo ""
echo "📋 To view logs:"
echo "   docker-compose logs -f [service_name]"
echo "   Available services: db, backend, scraper, frontend"
echo ""
echo "🛑 To stop all services:"
echo "   docker-compose down"
echo ""
echo "🔄 The data scraper runs automatically and will:"
echo "   - Fetch latest player data on startup"
echo "   - Update rankings daily at midnight"
echo "   - Preserve all draft history for bot learning"
echo ""
echo "✅ Setup complete! Happy drafting! 🏈"
