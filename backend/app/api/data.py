from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional

from ..data.database import get_db
from ..data.models import ScoringTypeEnum, PositionEnum
from ..data.crud import PlayerCRUD
from ..data.ingestion import DataIngestionService
from ..services.vorp import VORPCalculator

router = APIRouter()

@router.get("/players")
async def get_players(
    position: Optional[PositionEnum] = None,
    limit: Optional[int] = 100,
    scoring_type: ScoringTypeEnum = ScoringTypeEnum.PPR,
    db: Session = Depends(get_db)
):
    """
    Get players with filtering options
    """
    try:
        if position:
            players = PlayerCRUD.get_players_by_position(db, position, limit)
        else:
            players = PlayerCRUD.get_all_players(db, scoring_type)
            if limit:
                players = players[:limit]
        
        return {
            "players": [
                {
                    "id": player.id,
                    "name": player.name,
                    "position": player.position.value,
                    "team": player.team,
                    "bye_week": player.bye_week,
                    "projected_points": getattr(player, f"projected_points_{scoring_type.value}"),
                    "adp": getattr(player, f"adp_{scoring_type.value}"),
                    "vorp": getattr(player, f"vorp_{scoring_type.value}"),
                    "scarcity_score": player.scarcity_score,
                    "expert_consensus_rank": player.expert_consensus_rank,
                    "positional_rank": player.positional_rank
                }
                for player in players
            ],
            "count": len(players),
            "scoring_type": scoring_type.value
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/players/{player_id}")
async def get_player(
    player_id: int,
    scoring_type: ScoringTypeEnum = ScoringTypeEnum.PPR,
    db: Session = Depends(get_db)
):
    """
    Get detailed information for a specific player
    """
    try:
        player = PlayerCRUD.get_player(db, player_id)
        if not player:
            raise HTTPException(status_code=404, detail="Player not found")
        
        return {
            "id": player.id,
            "name": player.name,
            "position": player.position.value,
            "team": player.team,
            "bye_week": player.bye_week,
            "projections": {
                "ppr": player.projected_points_ppr,
                "half_ppr": player.projected_points_half_ppr,
                "standard": player.projected_points_standard
            },
            "adp": {
                "ppr": player.adp_ppr,
                "half_ppr": player.adp_half_ppr,
                "standard": player.adp_standard
            },
            "vorp": {
                "ppr": player.vorp_ppr,
                "half_ppr": player.vorp_half_ppr,
                "standard": player.vorp_standard
            },
            "scarcity_score": player.scarcity_score,
            "expert_consensus_rank": player.expert_consensus_rank,
            "positional_rank": player.positional_rank,
            "raw_projections": player.raw_projections,
            "created_at": player.created_at.isoformat() if player.created_at else None,
            "updated_at": player.updated_at.isoformat() if player.updated_at else None
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/players/search/{name}")
async def search_players(
    name: str,
    scoring_type: ScoringTypeEnum = ScoringTypeEnum.PPR,
    db: Session = Depends(get_db)
):
    """
    Search for players by name
    """
    try:
        # Simple name search - in production, you'd want fuzzy matching
        players = db.query(Player).filter(Player.name.ilike(f"%{name}%")).limit(20).all()
        
        return {
            "query": name,
            "players": [
                {
                    "id": player.id,
                    "name": player.name,
                    "position": player.position.value,
                    "team": player.team,
                    "projected_points": getattr(player, f"projected_points_{scoring_type.value}"),
                    "adp": getattr(player, f"adp_{scoring_type.value}")
                }
                for player in players
            ],
            "count": len(players)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/vorp-rankings")
async def get_vorp_rankings(
    position: Optional[PositionEnum] = None,
    limit: Optional[int] = 50,
    scoring_type: ScoringTypeEnum = ScoringTypeEnum.PPR,
    db: Session = Depends(get_db)
):
    """
    Get VORP rankings for players
    """
    try:
        calculator = VORPCalculator(db)
        
        if position:
            players = calculator.get_position_vorp_rankings(position, scoring_type)
        else:
            players = calculator.get_top_vorp_players(scoring_type, limit)
        
        if limit and not position:
            players = players[:limit]
        
        return {
            "rankings": [
                {
                    "rank": i + 1,
                    "player": {
                        "id": player.id,
                        "name": player.name,
                        "position": player.position.value,
                        "team": player.team
                    },
                    "vorp": getattr(player, f"vorp_{scoring_type.value}"),
                    "projected_points": getattr(player, f"projected_points_{scoring_type.value}"),
                    "adp": getattr(player, f"adp_{scoring_type.value}")
                }
                for i, player in enumerate(players)
            ],
            "position": position.value if position else "ALL",
            "scoring_type": scoring_type.value,
            "count": len(players)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/ingest-data")
async def ingest_player_data(
    scraped_data: List[dict],
    db: Session = Depends(get_db)
):
    """
    Ingest scraped player data into the database
    """
    try:
        ingestion_service = DataIngestionService(db)
        results = ingestion_service.full_data_refresh(scraped_data)
        
        return {
            "message": "Data ingestion completed successfully",
            "results": results
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/player-comparison")
async def compare_players(
    player_ids: str,  # Comma-separated player IDs
    scoring_type: ScoringTypeEnum = ScoringTypeEnum.PPR,
    db: Session = Depends(get_db)
):
    """
    Compare multiple players side by side
    """
    try:
        # Parse player IDs
        ids = [int(id.strip()) for id in player_ids.split(",")]
        
        calculator = VORPCalculator(db)
        comparison = calculator.compare_players(ids, scoring_type)
        
        return comparison
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats/summary")
async def get_data_summary(
    db: Session = Depends(get_db)
):
    """
    Get summary statistics about the data
    """
    try:
        from ..data.models import Player
        
        # Try to connect to database and get real data
        total_players = db.query(Player).count()
        
        # Count by position
        position_counts = {}
        for position in PositionEnum:
            count = db.query(Player).filter(Player.position == position).count()
            position_counts[position.value] = count
        
        # Players with projections
        players_with_ppr = db.query(Player).filter(Player.projected_points_ppr.isnot(None)).count()
        players_with_vorp = db.query(Player).filter(Player.vorp_ppr.isnot(None)).count()
        
        return {
            "total_players": total_players,
            "position_breakdown": position_counts,
            "data_completeness": {
                "players_with_ppr_projections": players_with_ppr,
                "players_with_vorp": players_with_vorp,
                "completion_rate": round((players_with_ppr / total_players * 100), 1) if total_players > 0 else 0
            }
        }
    except Exception as e:
        # Return fallback data if database connection fails
        return {
            "total_players": 0,
            "position_breakdown": {
                "QB": 0,
                "RB": 0,
                "WR": 0,
                "TE": 0,
                "K": 0,
                "DEF": 0
            },
            "data_completeness": {
                "players_with_ppr_projections": 0,
                "players_with_vorp": 0,
                "completion_rate": 0
            },
            "error": "Database not initialized - run data ingestion first",
            "status": "needs_setup"
        }
