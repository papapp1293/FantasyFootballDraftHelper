# Fantasy Football Draft Helper

A comprehensive fantasy football draft analysis tool powered by advanced analytics, VORP calculations, scarcity analysis, and Monte Carlo simulations.

## 🏆 Features

### Core Analytics
- **VORP (Value Over Replacement Player)** - Calculate true player value relative to replacement level
- **Positional Scarcity Analysis** - Identify tier breaks and drop-offs by position
- **Monte Carlo Draft Simulation** - Optimal pick recommendations based on thousands of simulations
- **Season Simulation** - Predict playoff probabilities and championship odds
- **Team Evaluation** - Comprehensive post-draft analysis with depth scoring

### Data Sources
- **FantasyPros Integration** - Scrapes latest player projections, ADP, and expert consensus rankings
- **Multi-Scoring Support** - PPR, Half-PPR, and Standard scoring systems
- **Real-time Updates** - Automated data refresh and analysis recalculation

### User Interface
- **Modern Web Dashboard** - Built with Next.js and Tailwind CSS
- **Interactive Draft Board** - Live draft recommendations and player rankings
- **Team Comparison** - Power rankings and competitive advantage analysis
- **Responsive Design** - Works on desktop, tablet, and mobile devices

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
│   ├── index.tsx      # Landing page
│   ├── draft.tsx      # Draft board and recommendations
│   └── analysis.tsx   # Team analysis and league comparison
├── components/        # Reusable UI components
├── services/          # API integration
├── types/             # TypeScript type definitions
└── styles/            # Global styles and Tailwind config
```

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

### Option 2: Manual Setup

#### Backend Setup

1. **Navigate to backend directory**
   ```bash
   cd backend
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up PostgreSQL database**
   ```bash
   # Create database
   createdb fantasy_football
   
   # Set environment variable
   export DATABASE_URL="postgresql://user:password@localhost/fantasy_football"
   ```

5. **Initialize database**
   ```python
   # In Python shell
   from app.data.database import create_tables
   create_tables()
   ```

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
