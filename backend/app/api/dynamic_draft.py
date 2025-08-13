"""
REST API endpoints for dynamic draft system with VORP and scarcity
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import logging
from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import random
import pickle
import os
from pathlib import Path

from ..services.dynamic_draft_engine import DynamicDraftEngine, DraftState
from ..data.models import ScoringTypeEnum, PositionEnum
from ..data.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter()

# In-memory storage for active drafts
active_drafts: Dict[str, DraftState] = {}
draft_engines: Dict[str, DynamicDraftEngine] = {}

# Persistence directory
DRAFT_STATE_DIR = Path("draft_states")
DRAFT_STATE_DIR.mkdir(exist_ok=True)

def save_draft_state(draft_id: str, draft_state: DraftState, engine: DynamicDraftEngine):
    """Save draft state to disk. Do NOT pickle engine (contains DB session)."""
    try:
        state_file = DRAFT_STATE_DIR / f"{draft_id}_state.pkl"
        with open(state_file, 'wb') as f:
            pickle.dump(draft_state, f)
        logger.info(f"Saved draft state for {draft_id}")
    except Exception as e:
        logger.error(f"Failed to save draft state for {draft_id}: {e}")

def load_draft_state(draft_id: str) -> tuple[DraftState, DynamicDraftEngine]:
    """Load draft state from disk and rebuild engine fresh (stateless)."""
    try:
        state_file = DRAFT_STATE_DIR / f"{draft_id}_state.pkl"
        if not state_file.exists():
            return None, None
        with open(state_file, 'rb') as f:
            draft_state = pickle.load(f)
        # Rebuild engine using a fresh DB session
        engine = DynamicDraftEngine(next(get_db()))
        
        logger.info(f"Loaded draft state for {draft_id}")
        return draft_state, engine
    except Exception as e:
        logger.error(f"Failed to load draft state for {draft_id}: {e}")
        return None, None

def get_draft_state(draft_id: str) -> tuple[DraftState, DynamicDraftEngine]:
    """Get draft state from memory or disk"""
    # Try memory first
    if draft_id in active_drafts and draft_id in draft_engines:
        return active_drafts[draft_id], draft_engines[draft_id]
    
    # Try loading from disk
    draft_state, engine = load_draft_state(draft_id)
    if draft_state and engine:
        # Cache in memory
        active_drafts[draft_id] = draft_state
        draft_engines[draft_id] = engine
        return draft_state, engine
    
    return None, None

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
        
        # Store in memory and persist to disk
        active_drafts[draft_state.draft_id] = draft_state
        draft_engines[draft_state.draft_id] = engine
        save_draft_state(draft_state.draft_id, draft_state, engine)
        
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
async def get_draft_state_endpoint(draft_id: str):
    """Get current draft state"""
    draft_state, engine = get_draft_state(draft_id)
    if not draft_state:
        raise HTTPException(status_code=404, detail="Draft not found")
    
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
        "draft_complete": draft_state.is_draft_complete(),
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
    limit: int = Query(500, description="Limit results")
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
    
    # Ensure VORP is calculated for all positions before sorting (CRITICAL: must be done before limiting!)
    try:
        for pos in PositionEnum:
            engine.ensure_vorp_calculated(draft_state, pos)
        logger.info("VORP calculation completed for all positions")
    except Exception as e:
        logger.error(f"Failed to calculate VORP: {e}")
        # Continue without VORP if calculation fails
    
    # Sort by VORP descending, with fallback to ECR ascending for players with same VORP
    available_players.sort(
        key=lambda p: (
            -draft_state.vorp_cache.get(p.id, 0),  # VORP descending (negative for reverse)
            p.expert_consensus_rank or 999         # ECR ascending as tiebreaker
        )
    )
    
    # Apply limit only for frontend display (but keep full pool for AI calculations)
    display_players = available_players[:limit] if limit < len(available_players) else available_players
    
    # Format response - VORP should now be properly calculated
    players_data = []
    for player in display_players:
        
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

@router.post("/drafts/{draft_id}/complete")
async def complete_draft(draft_id: str):
    """Mark a draft as complete and record it for learning"""
    draft_state, engine = get_draft_state(draft_id)
    if not draft_state:
        raise HTTPException(status_code=404, detail="Draft not found")
    
    try:
        # Record the completed draft for learning
        engine.record_completed_draft(draft_state)
        
        # Add completed draft to team analysis with Monte Carlo simulation
        await _add_draft_to_team_analysis(draft_state, engine)
        
        # Clean up draft state from memory (but keep persistent storage)
        if draft_id in active_drafts:
            del active_drafts[draft_id]
        if draft_id in draft_engines:
            del draft_engines[draft_id]
        
        logger.info(f"Draft {draft_id} completed, recorded for learning, and added to team analysis")
        
        return {
            "message": "Draft completed, recorded for learning, and added to team analysis",
            "draft_id": draft_id,
            "total_picks": len(draft_state.picks),
            "team_analysis_updated": True
        }
    except Exception as e:
        logger.error(f"Failed to complete draft {draft_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to complete draft")

async def _add_draft_to_team_analysis(draft_state: DraftState, engine: DynamicDraftEngine):
    """Add completed draft to team analysis with Monte Carlo simulation"""
    try:
        from app.services.evaluation import TeamEvaluator
        
        # Get user's team (draft_spot - 1 for 0-indexed)
        user_team_id = draft_state.draft_spot - 1
        user_picks = [pick for pick in draft_state.picks if pick.team_id == user_team_id]
        
        if not user_picks:
            logger.warning("No user picks found in completed draft")
            return
        
        # Get user's roster
        user_roster = []
        for pick in user_picks:
            if pick.player_id in engine.players_cache:
                user_roster.append(engine.players_cache[pick.player_id])
        
        if len(user_roster) < 10:  # Minimum viable roster
            logger.warning(f"User roster too small ({len(user_roster)} players) for team analysis")
            return
        
        # Evaluate the team
        evaluator = TeamEvaluator(next(get_db()))
        evaluation = evaluator.evaluate_team(user_roster, draft_state.scoring_mode)
        
        # Store in team analysis (in production, this would go to a database)
        team_analysis_data = {
            "draft_id": f"draft_{len(draft_state.picks)}_{user_team_id}",
            "team_name": f"User Draft Team",
            "draft_date": time.time(),
            "evaluation": evaluation,
            "roster": [{"id": p.id, "name": p.name, "position": p.position.value} for p in user_roster],
            "scoring_mode": draft_state.scoring_mode.value
        }
        
        # TODO: Store in persistent team analysis database
        logger.info(f"Team analysis completed for user draft: Grade {evaluation.get('overall_grade', 'N/A')}")
        
    except Exception as e:
        logger.error(f"Failed to add draft to team analysis: {e}")

@router.post("/drafts/{draft_id}/abandon")
async def abandon_draft(draft_id: str):
    """Mark a draft as abandoned and clean up data"""
    try:
        # Clean up draft state from memory and persistent storage
        if draft_id in active_drafts:
            del active_drafts[draft_id]
        if draft_id in draft_engines:
            del draft_engines[draft_id]
        
        # Remove persistent files
        import os
        from pathlib import Path
        
        draft_dir = Path("draft_states")
        state_file = draft_dir / f"{draft_id}_state.pkl"
        if state_file.exists():
            os.remove(state_file)
        
        logger.info(f"Draft {draft_id} abandoned and data cleaned up")
        
        return {
            "message": "Draft abandoned and data cleaned up",
            "draft_id": draft_id
        }
    except Exception as e:
        logger.error(f"Failed to abandon draft {draft_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to abandon draft")

@router.post("/drafts/{draft_id}/pick")
async def make_pick(draft_id: str, request: MakePickRequest):
    """Make a pick in the draft"""
    draft_state, engine = get_draft_state(draft_id)
    if not draft_state:
        raise HTTPException(status_code=404, detail="Draft not found")
    
    try:
        # Debug logging before pick
        logger.info(f"Before pick - Current pick index: {draft_state.current_pick_index}, Current team: {draft_state.get_current_team_id()}")
        
        # Validate player is available
        if request.player_id not in draft_state.remaining_players:
            logger.error(f"Player {request.player_id} not available - remaining players: {len(draft_state.remaining_players)}")
            raise HTTPException(status_code=400, detail=f"Player {request.player_id} is not available")
        
        # Validate player exists in cache
        if request.player_id not in engine.players_cache:
            logger.error(f"Player {request.player_id} not found in cache")
            raise HTTPException(status_code=400, detail=f"Player {request.player_id} not found")
        
        # Make the pick
        result = engine.make_pick(draft_state, request.player_id)
        
        # Debug logging after pick
        logger.info(f"After pick - Current pick index: {draft_state.current_pick_index}, Current team: {draft_state.get_current_team_id()}")
        
        # Get player info (support both ORM object and dict representation)
        player = engine.players_cache[request.player_id]
        if hasattr(player, 'id'):
            player_id_val = player.id
            player_name_val = player.name
            player_team_val = getattr(player, 'team', None)
            player_position_val = getattr(player, 'position', None)
            player_position_str = player_position_val.value if hasattr(player_position_val, 'value') else str(player_position_val)
        else:
            player_id_val = player.get('id')
            player_name_val = player.get('name')
            player_team_val = player.get('team')
            pos_val = player.get('position')
            player_position_str = pos_val.value if hasattr(pos_val, 'value') else str(pos_val)
        
        # Save updated draft state to disk
        save_draft_state(draft_id, draft_state, engine)
        
        return {
            "success": True,
            "pick": {
                "pick_index": result["pick"].pick_index,
                "team_id": result["pick"].team_id,
                "player": {
                    "id": player_id_val,
                    "name": player_name_val,
                    "position": player_position_str,
                    "team": player_team_val,
                    "projected_points": engine._get_projected_points(player, draft_state.scoring_mode),
                    "vorp": draft_state.vorp_cache.get(player_id_val, 0)
                },
                "round_number": result["pick"].round_number,
                "pick_in_round": result["pick"].pick_in_round
            },
            "updated_metrics": {
                "vorp_updates_count": len(result["updated_vorp"]),
                    # Engine returns a dict {"scarcity_metrics": ScarcityMetrics}
                    "scarcity_updated": (
                        result["updated_scarcity"].get("scarcity_metrics").position.value
                        if isinstance(result.get("updated_scarcity"), dict)
                        and result["updated_scarcity"].get("scarcity_metrics") is not None
                        else None
                    ),
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

@router.post("/drafts/{draft_id}/simulate-bot-picks")
async def simulate_bot_picks(draft_id: str):
    """Simulate bot picks until user's turn or draft completion"""
    draft_state, engine = get_draft_state(draft_id)
    if not draft_state:
        raise HTTPException(status_code=404, detail="Draft not found")
    
    try:
        bot_picks = []
        max_bot_picks = 50  # Safety limit
        
        while (not draft_state.is_draft_complete() and len(bot_picks) < max_bot_picks):
            
            current_team_id = draft_state.get_current_team_id()
            if current_team_id == -1:
                logger.info("Draft complete - no more picks needed")
                break
                
            if current_team_id == draft_state.draft_spot:
                logger.info(f"User's turn (team {current_team_id}) - stopping bot simulation")
                break
                
            logger.info(f"Bot pick for team {current_team_id}, pick {draft_state.current_pick_index}")
            
            # Get bot advice
            advice = engine.get_advice(draft_state, current_team_id, "bot_realistic")
            if not advice:
                logger.error(f"No advice available for team {current_team_id}")
                break
            
            # Pick from top 3 recommendations with some randomness
            import random
            top_picks = advice[:min(3, len(advice))]
            selected_pick = random.choice(top_picks)
            player_id = selected_pick["player_id"]
            
            # Double-check player is still available
            if player_id not in draft_state.remaining_players:
                logger.error(f"Player {player_id} no longer available for team {current_team_id}")
                # Try next available player from advice
                available_advice = [p for p in advice if p["player_id"] in draft_state.remaining_players]
                if not available_advice:
                    logger.error(f"No available players in advice for team {current_team_id}")
                    break
                selected_pick = available_advice[0]
                player_id = selected_pick["player_id"]
            
            # Make the pick
            try:
                result = engine.make_pick(draft_state, player_id)
                player = engine.players_cache[player_id]
            except Exception as e:
                logger.error(f"Failed to make bot pick for team {current_team_id}: {e}")
                break
            
            bot_picks.append({
                "pick_index": result["pick"].pick_index,
                "team_id": current_team_id,
                "player": {
                    "id": player.id,
                    "name": player.name,
                    "position": player.position.value,
                    "team": player.team
                },
                "reason": selected_pick.get("reason", "Bot selection")
            })
            
            logger.info(f"Bot pick made: Team {current_team_id} selected {player.name}")
        
        # Save updated draft state to disk after bot picks
        save_draft_state(draft_id, draft_state, engine)
        
        return {
            "success": True,
            "bot_picks": bot_picks,
            "draft_complete": draft_state.current_pick_index >= len(draft_state.draft_order),
            "next_pick": {
                "pick_index": draft_state.current_pick_index,
                "team_id": draft_state.get_current_team_id() if draft_state.current_pick_index < len(draft_state.draft_order) else None,
                "is_user_turn": draft_state.get_current_team_id() == draft_state.draft_spot if draft_state.current_pick_index < len(draft_state.draft_order) else False
            }
        }
        
    except Exception as e:
        logger.error(f"Error simulating bot picks: {e}")
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
