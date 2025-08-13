@echo off
echo 🚀 Fantasy Football Draft Helper - Complete Setup
echo ==================================================

REM Check if Docker is running
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Docker is not running. Please start Docker Desktop first.
    pause
    exit /b 1
)

echo ✅ Docker is running

REM Stop any existing containers
echo 🛑 Stopping any existing containers...
docker-compose down

REM Build and start all services
echo 🏗️  Building and starting all services...
echo    - PostgreSQL Database
echo    - Backend API Server
echo    - Data Scraper
echo    - Frontend Web App

docker-compose up --build -d

echo.
echo ⏳ Waiting for services to be ready...
echo    This may take a few minutes on first run...

REM Wait for backend to be healthy (simplified for Windows)
echo    Waiting for backend API...
timeout /t 30 /nobreak >nul

echo.
echo 🎉 Fantasy Football Draft Helper is now running!
echo ==================================================
echo.
echo 📱 Access the application:
echo    🌐 Frontend:  http://localhost:3001
echo    🔧 Backend:   http://localhost:8001
echo    📊 API Docs:  http://localhost:8001/docs
echo.
echo 📊 Services Status:
docker-compose ps

echo.
echo 📋 To view logs:
echo    docker-compose logs -f [service_name]
echo    Available services: db, backend, scraper, frontend
echo.
echo 🛑 To stop all services:
echo    docker-compose down
echo.
echo 🔄 The data scraper runs automatically and will:
echo    - Fetch latest player data on startup
echo    - Update rankings daily at midnight
echo    - Preserve all draft history for bot learning
echo.
echo ✅ Setup complete! Happy drafting! 🏈
pause
