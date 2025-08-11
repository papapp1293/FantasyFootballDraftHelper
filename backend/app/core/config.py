from pydantic_settings import BaseSettings
from typing import Dict, Any
from enum import Enum

class ScoringType(str, Enum):
    PPR = "ppr"
    HALF_PPR = "half_ppr"
    STANDARD = "standard"

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql://user:password@localhost:5432/fantasy_football"
    
    # Scoring configuration
    DEFAULT_SCORING_TYPE: ScoringType = ScoringType.PPR
    
    # Scraping configuration
    SCRAPING_DELAY: float = 0.5  # Seconds between requests
    REQUEST_TIMEOUT: int = 30
    
    # Simulation parameters
    MONTE_CARLO_ITERATIONS: int = 10000
    DRAFT_SIMULATION_ITERATIONS: int = 1000
    
    # League settings
    DEFAULT_LEAGUE_SIZE: int = 12
    DEFAULT_ROSTER_SIZE: int = 16
    DEFAULT_STARTING_LINEUP: Dict[str, int] = {
        "QB": 1,
        "RB": 2,
        "WR": 2,
        "TE": 1,
        "FLEX": 1,  # RB/WR/TE
        "K": 1,
        "DEF": 1
    }
    
    # VORP calculation
    REPLACEMENT_LEVEL_PERCENTILE: float = 0.75  # 75th percentile as replacement level
    
    # API settings
    API_V1_STR: str = "/api/v1"
    
    class Config:
        env_file = ".env"

settings = Settings()
