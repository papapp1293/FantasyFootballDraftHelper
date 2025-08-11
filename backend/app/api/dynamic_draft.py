"""
REST API endpoints for dynamic draft system with VORP and scarcity
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import logging

from ..data.database import get_db
from ..data.models import ScoringTypeEnum, PositionEnum
from ..services.dynamic_draft_engine import DynamicDraftEngine, DraftState

router = APIRouter()
logger = logging.getLogger(__name__)

# In-memory storage for active drafts
active_drafts: Dict[str, DraftState] = {}
draft_engines: Dict[str, DynamicDraftEngine] = {}

class CreateDraftRequest(BaseModel):
    num_teams: int = 12
    draft_spot: int = 1  # 1-based position
    snake: bool = True
    scoring_mode: str = "ppr"

class MakePickRequest(BaseModel):
    player_id: int

class AdviceRequest(BaseModel):
    team_id: int = 1
    mode: str = "robust"  # best_vorp, fill_need, upside, robust

@router.post("/drafts")
async def create_draft(
    request: CreateDraftRequest,
    db: Session = Depends(get_db)
):
    """Create a new dynamic draft with VORP and scarcity tracking"""
    try:
        # Validate inputs
        if not (1 <= request.draft_spot <= request.num_teams):
            raise HTTPException(status_code=400, detail="Invalid draft spot")
        
        scoring_mode = ScoringTypeEnum(request.scoring_mode.lower())
        
        # Create draft engine
        engine = DynamicDraftEngine(db)
        
        # Create draft state
        draft_state = engine.create_draft(
            num_teams=request.num_teams,
            draft_spot=request.draft_spot,
            scoring_mode=scoring_mode
        )
        
        # Store in memory
        active_drafts[draft_state.draft_id] = draft_state
        draft_engines[draft_state.draft_id] = engine
        
        logger.info(f"Created dynamic draft {draft_state.draft_id}")
        
        return {
            "draft_id": draft_state.draft_id,
            "num_teams": draft_state.num_teams,
            "draft_spot": draft_state.draft_spot,
            "scoring_mode": draft_state.scoring_mode.value,
            "current_pick_index": draft_state.current_pick_index,
            "current_team_id": draft_state.get_current_team_id(),
            "total_picks": len(draft_state.draft_order),
            "message": f"Dynamic draft created with {request.num_teams} teams"
        }
        
    except Exception as e:
        logger.error(f"Error creating draft: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/drafts/{draft_id}/state")
async def get_draft_state(draft_id: str):
    """Get current draft state snapshot"""
    if draft_id not in active_drafts:
        raise HTTPException(status_code=404, detail="Draft not found")
    
    draft_state = active_drafts[draft_id]
    
    # Convert to serializable format
    return {
        "draft_id": draft_state.draft_id,
        "num_teams": draft_state.num_teams,
        "draft_spot": draft_state.draft_spot,
        "snake": draft_state.snake,
        "scoring_mode": draft_state.scoring_mode.value,
        "current_pick_index": draft_state.current_pick_index,
        "current_team_id": draft_state.get_current_team_id(),
        "total_picks": draft_state.num_teams * 16,  # 16 rounds per team
        "picks_made": len(draft_state.picks),
        "user_next_pick_index": draft_state.get_user_next_pick_index(),
        "picks": [
            {
                "pick_index": pick.pick_index,
                "team_id": pick.team_id,
                "player_id": pick.player_id,
                "round_number": pick.round_number,
                "pick_in_round": pick.pick_in_round,
                "timestamp": pick.timestamp
            }
            for pick in draft_state.picks
        ],
        "rosters": {
            str(team_id): {
                "team_id": roster.team_id,
                "picks": roster.picks,
                "positional_counts": {pos.value: count for pos, count in roster.positional_counts.items()},
                "need_scores": {pos.value: score for pos, score in roster.need_scores.items()}
            }
            for team_id, roster in draft_state.rosters.items()
        },
        "scarcity_metrics": {
            pos.value: {
                "position": metrics.position.value,
                "avg_vorp_remaining": metrics.avg_vorp_remaining,
                "dropoff_at_next_tier": metrics.dropoff_at_next_tier,
                "scarcity_score": metrics.scarcity_score,
                "urgency_flag": metrics.urgency_flag,
                "replacement_level": metrics.replacement_level,
                "players_remaining": metrics.players_remaining
            }
            for pos, metrics in draft_state.scarcity_cache.items()
        }
    }

@router.get("/players")
async def get_players_with_vorp(
    draft_id: str = Query(..., description="Draft ID for VORP context"),
    scoring_mode: str = Query("ppr", description="Scoring mode"),
    position: Optional[str] = Query(None, description="Filter by position"),
    limit: int = Query(100, description="Limit results")
):
    """Get players with current VORP and scarcity data"""
    if draft_id not in active_drafts:
        raise HTTPException(status_code=404, detail="Draft not found")
    
    draft_state = active_drafts[draft_id]
    engine = draft_engines[draft_id]
    
    # Get available players
    available_players = [
        engine.players_cache[pid] for pid in draft_state.remaining_players
        if pid in engine.players_cache
    ]
    
    # Filter by position if specified
    if position:
        try:
            pos_enum = PositionEnum(position.upper())
            available_players = [p for p in available_players if p.position == pos_enum]
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid position")
    
    # Sort by VORP descending
    available_players.sort(
        key=lambda p: draft_state.vorp_cache.get(p.id, 0),
        reverse=True
    )
    
    # Limit results
    available_players = available_players[:limit]
    
    # Format response with lazy VORP calculation
    players_data = []
    for player in available_players:
        # Ensure VORP is calculated for this player's position
        engine.ensure_vorp_calculated(draft_state, player.position)
        
        vorp = draft_state.vorp_cache.get(player.id, 0)
        projected_points = engine._get_projected_points(player, draft_state.scoring_mode)
        adp = engine._get_adp(player)
        scarcity_metrics = draft_state.scarcity_cache.get(player.position)
        
        players_data.append({
            "id": player.id,
            "name": player.name,
            "position": player.position.value,
            "team": player.team,
            "bye_week": player.bye_week,
            "projected_points": projected_points,
            "adp": adp,
            "vorp": vorp,
            "ecr": player.expert_consensus_rank,
            "injury_risk": 0.0,  # Default value since column doesn't exist in DB
            "scarcity_flag": scarcity_metrics.urgency_flag if scarcity_metrics else False,
            "replacement_level": scarcity_metrics.replacement_level if scarcity_metrics else 0.0
        })
    
    return {
        "players": players_data,
        "total_available": len(draft_state.remaining_players),
        "scoring_mode": draft_state.scoring_mode.value
    }

@router.post("/drafts/{draft_id}/pick")
async def make_pick(
    draft_id: str,
    request: MakePickRequest
):
    """Make a draft pick and update VORP/scarcity"""
    if draft_id not in active_drafts:
        raise HTTPException(status_code=404, detail="Draft not found")
    
    draft_state = active_drafts[draft_id]
    engine = draft_engines[draft_id]
    
    try:
        # Debug logging before pick
        logger.info(f"Before pick - Current pick index: {draft_state.current_pick_index}, Current team: {draft_state.get_current_team_id()}")
        
        # Make the pick
        result = engine.make_pick(draft_state, request.player_id)
        
        # Debug logging after pick
        logger.info(f"After pick - Current pick index: {draft_state.current_pick_index}, Current team: {draft_state.get_current_team_id()}")
        
        # Get player info
        player = engine.players_cache[request.player_id]
        
        return {
            "success": True,
            "pick": {
                "pick_index": result["pick"].pick_index,
                "team_id": result["pick"].team_id,
                "player": {
                    "id": player.id,
                    "name": player.name,
                    "position": player.position.value,
                    "team": player.team,
                    "projected_points": engine._get_projected_points(player, draft_state.scoring_mode),
                    "vorp": draft_state.vorp_cache.get(player.id, 0)
                },
                "round_number": result["pick"].round_number,
                "pick_in_round": result["pick"].pick_in_round
            },
            "updated_metrics": {
                "vorp_updates_count": len(result["updated_vorp"]),
                "scarcity_updated": result["updated_scarcity"].position.value,
                "team_needs": result["team_needs"]
            },
            "next_pick": {
                "pick_index": draft_state.current_pick_index,
                "team_id": draft_state.get_current_team_id() if draft_state.current_pick_index < len(draft_state.draft_order) else None
            }
        }
        
    except Exception as e:
        logger.error(f"Error making pick: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/drafts/{draft_id}/advice")
async def get_draft_advice(
    draft_id: str,
    team_id: int = Query(1, description="Team ID for advice"),
    mode: str = Query("robust", description="Advice mode")
):
    """Get draft advice for a team"""
    if draft_id not in active_drafts:
        raise HTTPException(status_code=404, detail="Draft not found")
    
    draft_state = active_drafts[draft_id]
    engine = draft_engines[draft_id]
    
    try:
        advice = engine.get_advice(draft_state, team_id, mode)
        
        return {
            "advice_mode": mode,
            "team_id": team_id,
            "advice": advice,
            "suggestions": advice,  # Keep both for compatibility
            "current_pick_index": draft_state.current_pick_index,
            "user_next_pick_index": draft_state.get_user_next_pick_index()
        }
        
    except Exception as e:
        logger.error(f"Error getting advice: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/drafts/{draft_id}/availability")
async def get_availability_forecast(
    draft_id: str,
    team_id: int = Query(1, description="Team ID"),
    num_sims: int = Query(500, description="Number of simulations")
):
    """Get player availability forecast for user's next pick"""
    if draft_id not in active_drafts:
        raise HTTPException(status_code=404, detail="Draft not found")
    
    draft_state = active_drafts[draft_id]
    engine = draft_engines[draft_id]
    
    try:
        availability = engine.simulate_availability(draft_state, team_id, num_sims)
        
        # Get player details for likely available players
        likely_available_details = []
        for pid in availability.get("likely_available", [])[:20]:  # Top 20
            if pid in engine.players_cache:
                player = engine.players_cache[pid]
                likely_available_details.append({
                    "id": player.id,
                    "name": player.name,
                    "position": player.position.value,
                    "vorp": draft_state.vorp_cache.get(pid, 0),
                    "projected_points": engine._get_projected_points(player, draft_state.scoring_mode)
                })
        
        return {
            "team_id": team_id,
            "picks_until_user": availability["picks_until_user"],
            "likely_available": likely_available_details,
            "confidence": availability["confidence"],
            "user_next_pick_index": draft_state.get_user_next_pick_index()
        }
        
    except Exception as e:
        logger.error(f"Error forecasting availability: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/drafts/{draft_id}/next-pick-line")
async def get_next_pick_line(draft_id: str):
    """Get data for rendering the next-pick line in player list"""
    if draft_id not in active_drafts:
        raise HTTPException(status_code=404, detail="Draft not found")
    
    draft_state = active_drafts[draft_id]
    user_next_pick = draft_state.get_user_next_pick_index()
    
    if user_next_pick is None:
        return {
            "has_next_pick": False,
            "message": "Draft complete or no more user picks"
        }
    
    picks_until_user = user_next_pick - draft_state.current_pick_index
    round_num, pick_in_round = draft_state.get_round_and_pick(user_next_pick)
    
    # Estimate cutoff for likely available players
    engine = draft_engines[draft_id]
    availability = engine.simulate_availability(draft_state, draft_state.draft_spot, 100)
    
    return {
        "has_next_pick": True,
        "user_next_pick_index": user_next_pick,
        "picks_until_user": picks_until_user,
        "round_number": round_num,
        "pick_in_round": pick_in_round,
        "likely_available_count": len(availability.get("likely_available", [])),
        "message": f"Your next pick: Round {round_num} Pick {pick_in_round} (in ~{picks_until_user} picks)"
    }

@router.delete("/drafts/{draft_id}")
async def delete_draft(draft_id: str):
    """Delete a draft from memory"""
    if draft_id in active_drafts:
        del active_drafts[draft_id]
    if draft_id in draft_engines:
        del draft_engines[draft_id]
    
    return {"message": f"Draft {draft_id} deleted"}

@router.get("/drafts")
async def list_active_drafts():
    """List all active drafts"""
    drafts = []
    for draft_id, draft_state in active_drafts.items():
        drafts.append({
            "draft_id": draft_id,
            "num_teams": draft_state.num_teams,
            "scoring_mode": draft_state.scoring_mode.value,
            "current_pick_index": draft_state.current_pick_index,
            "picks_made": len(draft_state.picks),
            "total_picks": len(draft_state.draft_order)
        })
    
    return {"active_drafts": drafts}
