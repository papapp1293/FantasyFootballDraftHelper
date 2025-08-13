# Fantasy Football Draft Helper

A comprehensive fantasy football draft assistant that provides real-time player rankings, draft recommendations, and team analysis using advanced algorithms and machine learning.

## Features

- **Real-time Player Rankings**: ECR (Expert Consensus Rankings), ADP (Average Draft Position), VORP (Value Over Replacement Player), and scarcity analysis
- **Dynamic Draft Engine**: Live draft simulation with intelligent bot opponents that learn from completed drafts
- **Draft Recommendations**: AI-powered Draft Advantage Score (DAS) based on team needs and value
- **Team Analysis**: Post-draft team evaluation and Monte Carlo season simulation
- **Modern Web Interface**: Responsive React/Next.js frontend with real-time updates
- **Automated Data Pipeline**: Daily scraping and ingestion of latest player data

## 🚀 Quick Start (Docker - Recommended)

### Prerequisites
- Docker Desktop installed and running
- Git

### One-Command Setup

1. **Clone and start everything:**
```bash
git clone <repository-url>
cd FantasyFootballDraftHelper

# Windows users:
start.bat

# Mac/Linux users:
./start.sh
```

That's it! The script will:
- ✅ Build all Docker containers
- ✅ Start PostgreSQL database
- ✅ Initialize database tables
- ✅ Start backend API server
- ✅ Run data scraper to fetch latest player rankings
- ✅ Start frontend web application
- ✅ Set up daily automated data updates

## 🏗️ Architecture

### Backend (FastAPI + PostgreSQL)
```
backend/
├── app/
│   ├── api/           # REST API endpoints
│   │   ├── draft.py   # Draft recommendations and simulation
│   │   ├── analysis.py # Team evaluation and league analysis
│   │   └── data.py    # Player data and VORP rankings
│   ├── core/          # Core configuration and scoring
│   ├── data/          # Database models and CRUD operations
│   ├── services/      # Business logic and analysis engines
│   │   ├── scarcity.py      # Positional scarcity analysis
│   │   ├── vorp.py          # VORP calculation engine
│   │   ├── draft_simulation.py # Monte Carlo draft simulation
│   │   ├── season_simulation.py # Season outcome prediction
│   │   └── evaluation.py    # Team evaluation and comparison
│   └── utils/         # Utilities and helpers
```

### Frontend (Next.js + TypeScript)
```
frontend/
├── pages/             # Next.js pages
│   ├── index.tsx      # Fantasy Football Draft Helper

A comprehensive fantasy football draft assistant that provides real-time player rankings, draft recommendations, and team analysis using advanced algorithms and machine learning.

## Features

- **Real-time Player Rankings**: ECR (Expert Consensus Rankings), ADP (Average Draft Position), VORP (Value Over Replacement Player), and scarcity analysis
- **Dynamic Draft Engine**: Live draft simulation with intelligent bot opponents that learn from completed drafts
- **Draft Recommendations**: AI-powered Draft Advantage Score (DAS) based on team needs and value
- **Team Analysis**: Post-draft team evaluation and Monte Carlo season simulation
- **Modern Web Interface**: Responsive React/Next.js frontend with real-time updates
- **Automated Data Pipeline**: Daily scraping and ingestion of latest player data

## 🚀 Quick Start (Docker - Recommended)

### Prerequisites
- Docker Desktop installed and running
- Git

### One-Command Setup

1. **Clone and start everything:**
```bash
git clone <repository-url>
cd FantasyFootballDraftHelper

# Windows users:
start.bat

# Mac/Linux users:
./start.sh
```

That's it! The script will:
- ✅ Build all Docker containers
- ✅ Start PostgreSQL database
- ✅ Initialize database tables
- ✅ Start backend API server
- ✅ Run data scraper to fetch latest player rankings
- ✅ Start frontend web application
- ✅ Set up daily automated data updates

### Manual Docker Setup

If you prefer manual control:

```bash
# Start all services
docker-compose up --build -d

# View logs
docker-compose logs -f

# Stop all services
docker-compose down
```

### Access the Application

Once running, access:
- **🌐 Frontend**: http://localhost:3001
- **🔧 Backend API**: http://localhost:8001
- **📊 API Documentation**: http://localhost:8001/docs
- **📋 Service Status**: `docker-compose ps`

## 🔧 Services Overview

The Docker Compose setup includes:

1. **PostgreSQL Database** (port 5433)
   - Persistent storage for player data, drafts, and bot learning
   - Automatic initialization and health checks

2. **Backend API Server** (port 8001)
   - FastAPI with SQLAlchemy ORM
   - Real-time draft engine with bot AI
   - Draft Advantage Score (DAS) calculations
   - Team analysis and season simulation

3. **Data Scraper Service**
   - Runs automatically on startup
   - Daily updates at midnight
   - Scrapes FantasyPros for latest rankings
   - Preserves all historical draft data for bot learning

4. **Frontend Web App** (port 3001)
   - Next.js with TypeScript
   - Real-time draft interface
   - Player rankings and analysis
   - Team evaluation dashboard

## 📊 Data Pipeline

The automated data pipeline:
- **Scrapes** latest player data from FantasyPros (ECR, ADP, projections)
- **Calculates** VORP, scarcity, and composite scores
- **Updates** player rankings while preserving draft history
- **Learns** from completed user drafts to improve bot AI
- **Runs** daily to keep data fresh

## 🏈 Draft Features

- **Dynamic VORP**: Recalculated as players are drafted
- **Smart Bots**: Use ADP/ECR with positional needs and learning
- **Draft Advantage Score**: Pick-aware recommendations for users
- **Team Analysis**: Post-draft evaluation with Monte Carlo simulation
- **Persistent State**: Drafts survive server restarts

## 🛠️ Local Development (Optional)

For development without Docker:

### Backend
```bash
cd backend
pip install -r requirements.txt

# Set up PostgreSQL locally and update .env
# DATABASE_URL=postgresql://user:password@localhost:5432/fantasy_football

# Start server
uvicorn app.main:app --reload --port 8001
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Database
Ensure PostgreSQL is running with credentials from `.env` file.

## 📋 Configuration

Environment variables in `.env`:
```env
DATABASE_URL=postgresql://user:password@localhost:5432/fantasy_football
SCRAPING_DELAY=2
REQUEST_TIMEOUT=30
DEFAULT_LEAGUE_SIZE=12
DEFAULT_ROSTER_SIZE=16
MONTE_CARLO_ITERATIONS=1000
PLACKETT_LUCE_ITERATIONS=500
```

## 🧪 Testing

Run the complete workflow verification:
```bash
cd test
python test_draft_verification.py
```

This tests:
- Database connectivity
- Draft creation and progression
- Bot pick simulation
- API endpoints
- Data persistence

## 📈 API Endpoints

Key endpoints:
- `GET /health`: Health check
- `GET /api/players`: Player rankings with VORP/ECR/ADP
- `POST /api/dynamic-draft/drafts`: Create new draft
- `GET /api/dynamic-draft/drafts/{id}`: Get draft state
- `POST /api/dynamic-draft/drafts/{id}/pick`: Make draft pick
- `GET /api/dynamic-draft/drafts/{id}/advice`: Get DAS recommendations
- `GET /api/data/stats/summary`: League statistics

## 🔄 Maintenance

### View Logs
```bash
docker-compose logs -f [service_name]
# Services: db, backend, scraper, frontend
```

### Update Player Data
```bash
# Scraper runs automatically, but to force update:
docker-compose exec scraper python /app/app/scraping/scraper.py
```

### Backup Data
```bash
# Database backup
docker-compose exec db pg_dump -U user fantasy_football > backup.sql
```

## 🏗️ Architecture

- **Backend**: FastAPI + SQLAlchemy + PostgreSQL
- **Frontend**: Next.js + TypeScript + Axios
- **AI Engine**: Dynamic VORP + Plackett-Luce bot calibration
- **Data Pipeline**: FantasyPros scraper + automated ingestion
- **Deployment**: Docker Compose with health checks and persistence

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes and add tests
4. Run `python test/test_draft_verification.py` to verify
5. Submit a pull request

## 📄 License

MIT License - see LICENSE file for details.

---

**🎯 Ready to dominate your fantasy league? Run `start.bat` (Windows) or `./start.sh` (Mac/Linux) and start drafting!**

## 🚀 Quick Start

### Prerequisites
- Node.js 18+ and npm
- Python 3.11+
- PostgreSQL 15+
- Docker (optional but recommended)

### Option 1: Docker Setup (Recommended)

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd FantasyFootballDraftHelper
   ```

2. **Start all services**
   ```bash
   docker-compose up -d
   ```

3. **Access the application**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs

### Option 2: Localhost Setup (Current Development Workflow)

#### Initial Setup (One-time)

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd FantasyFootballDraftHelper
   ```

2. **Backend Setup**
   ```bash
   cd backend
   
   # Create virtual environment
   python -m venv venv
   venv\Scripts\activate  # On Windows
   # source venv/bin/activate  # On macOS/Linux
   
   # Install dependencies
   pip install -r requirements.txt
   ```

3. **Frontend Setup**
   ```bash
   cd ../frontend
   
   # Install dependencies
   npm install
   ```

4. **Database Setup**
   ```bash
   # Create PostgreSQL database
   createdb fantasy_football
   
   # Set environment variables in backend/.env
   DATABASE_URL="postgresql://user:password@localhost/fantasy_football"
   ```

5. **Initialize Database**
   ```bash
   cd ../backend
   python -c "from app.data.database import create_tables; create_tables()"
   ```

#### Daily Startup (After Reboot)

**Option A: Quick Start (Recommended)**
```bash
# Terminal 1: Start Backend
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload

# Terminal 2: Start Frontend
cd frontend
npm run dev
```

**Option B: With Virtual Environment**
```bash
# Terminal 1: Start Backend
cd backend
venv\Scripts\activate  # On Windows
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload

# Terminal 2: Start Frontend
cd frontend
npm run dev
```

#### Access Points
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8001
- **API Documentation**: http://localhost:8001/docs
- **Player Rankings**: http://localhost:3000/player-rankings
- **Dynamic Draft**: http://localhost:3000/dynamic-draft
- **Team Analysis**: http://localhost:3000/analysis

6. **Start the backend server**
   ```bash
   uvicorn app.main:app --reload
   ```

#### Frontend Setup

1. **Navigate to frontend directory**
   ```bash
   cd frontend
   ```

2. **Install dependencies**
   ```bash
   npm install
   ```

3. **Set environment variables**
   ```bash
   # Create .env.local file
   echo "NEXT_PUBLIC_API_URL=http://localhost:8000/api" > .env.local
   ```

4. **Start the development server**
   ```bash
   npm run dev
   ```

## 📊 Data Ingestion

### Initial Data Load

1. **Access the backend API documentation**
   - Go to http://localhost:8000/docs

2. **Use the data ingestion endpoint**
   ```bash
   # The scraper will automatically fetch data from FantasyPros
   curl -X POST "http://localhost:8000/api/data/ingest-data" \
        -H "Content-Type: application/json" \
        -d "[]"
   ```

3. **Verify data load**
   ```bash
   curl "http://localhost:8000/api/data/stats/summary"
   ```

### Automated Data Updates

The system includes a FantasyPros scraper that can be scheduled to run regularly:

```python
# Example: Update data daily
from app.utils.scraping import FantasyProsScraper
from app.data.ingestion import DataIngestionService

scraper = FantasyProsScraper()
data = scraper.scrape_all_data()

# Process and store data
ingestion_service = DataIngestionService(db)
results = ingestion_service.full_data_refresh(data)
```

## 🎯 Usage Guide

### Draft Recommendations

1. **Navigate to Draft Board** (http://localhost:3000/draft)
2. **Select scoring type** (PPR, Half-PPR, Standard)
3. **Filter by position** or search for specific players
4. **View player rankings** with VORP, scarcity scores, and projections

### Team Analysis

1. **Navigate to Analysis** (http://localhost:3000/analysis)
2. **View Team Rankings** - Power rankings with grades and projections
3. **Run Season Simulation** - Monte Carlo playoff and championship probabilities
4. **Compare teams** across multiple metrics

### API Integration

The REST API provides programmatic access to all features:

```javascript
// Get draft recommendations
const recommendation = await fetch(
  '/api/draft/recommendations/1/1/5?scoring_type=ppr'
);

// Get team evaluation
const evaluation = await fetch(
  '/api/analysis/team-evaluation/1?scoring_type=ppr'
);

// Run season simulation
const simulation = await fetch(
  '/api/analysis/season-simulation/1', 
  { method: 'POST' }
);
```

## 🔧 Configuration

### Backend Configuration

Edit `backend/app/core/config.py`:

```python
class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql://user:password@localhost/fantasy_football"
    
    # Scoring
    DEFAULT_SCORING_TYPE: ScoringType = ScoringType.PPR
    
    # Simulation parameters
    MONTE_CARLO_ITERATIONS: int = 10000
    DRAFT_SIMULATION_ITERATIONS: int = 1000
    
    # League settings
    DEFAULT_LEAGUE_SIZE: int = 12
    DEFAULT_ROSTER_SIZE: int = 16
```

### Frontend Configuration

Edit `frontend/next.config.js` for API routing and other settings.

## 🧪 Testing

### Backend Tests
```bash
cd backend
pytest tests/
```

### Frontend Tests
```bash
cd frontend
npm run test
```

## 📈 Key Algorithms

### VORP Calculation
```python
# Value Over Replacement Player
vorp = player_projected_points - replacement_level_points

# Replacement level varies by position:
# QB: ~QB15, RB: ~RB36, WR: ~WR42, TE: ~TE15
```

### Scarcity Analysis
```python
# Identifies tier breaks using:
# 1. Standard deviation gaps
# 2. Percentage drop-offs (>15%)
# 3. K-means clustering
# 4. Statistical significance testing
```

### Monte Carlo Draft Simulation
```python
# For each pick:
# 1. Calculate expected value = (projected_points + vorp) * need_multiplier
# 2. Estimate opportunity cost based on ADP
# 3. Run 1000+ simulations of remaining draft
# 4. Recommend pick with highest expected value
```

## 🚀 Deployment

### Production Deployment

1. **Build frontend**
   ```bash
   cd frontend
   npm run build
   ```

2. **Configure production database**
   ```bash
   export DATABASE_URL="postgresql://user:password@prod-db/fantasy_football"
   ```

3. **Deploy with Docker**
   ```bash
   docker-compose -f docker-compose.prod.yml up -d
   ```

### Environment Variables

**Backend (.env)**
```
DATABASE_URL=postgresql://user:password@localhost/fantasy_football
SCRAPING_DELAY=0.5
MONTE_CARLO_ITERATIONS=10000
```

**Frontend (.env.local)**
```
NEXT_PUBLIC_API_URL=http://localhost:8000/api
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- **FantasyPros** for player data and projections
- **FastAPI** for the excellent Python web framework
- **Next.js** for the React framework
- **Tailwind CSS** for the utility-first CSS framework

## 📞 Support

For support, please open an issue on GitHub or contact the development team.

---

**Built with ❤️ for fantasy football enthusiasts who want to dominate their leagues with data-driven decisions.**
