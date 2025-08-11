from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional

from ..data.database import get_db
from ..data.models import ScoringTypeEnum, PositionEnum
from ..data.crud import ScarcityCRUD
from ..services.evaluation import TeamEvaluator
from ..services.season_simulation import SeasonSimulator
from ..services.scarcity import ScarcityAnalyzer

router = APIRouter()

@router.get("/team-evaluation/{team_id}")
async def evaluate_team(
    team_id: int,
    scoring_type: ScoringTypeEnum = ScoringTypeEnum.PPR,
    db: Session = Depends(get_db)
):
    """
    Get comprehensive team evaluation including VORP, depth, and projections
    """
    try:
        evaluator = TeamEvaluator(db)
        evaluation = evaluator.evaluate_team(team_id, scoring_type)
        
        return evaluation
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/league-comparison/{league_id}")
async def compare_league_teams(
    league_id: int,
    scoring_type: ScoringTypeEnum = ScoringTypeEnum.PPR,
    db: Session = Depends(get_db)
):
    """
    Compare all teams in a league with power rankings
    """
    try:
        evaluator = TeamEvaluator(db)
        comparison = evaluator.compare_teams(league_id, scoring_type)
        
        return comparison
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/scarcity-analysis")
async def get_scarcity_analysis(
    scoring_type: ScoringTypeEnum = ScoringTypeEnum.PPR,
    position: Optional[PositionEnum] = None,
    db: Session = Depends(get_db)
):
    """
    Get positional scarcity analysis
    """
    try:
        if position:
            # Get specific position analysis
            analysis = ScarcityCRUD.get_scarcity_analysis(db, position, scoring_type)
            if not analysis:
                raise HTTPException(status_code=404, detail=f"No scarcity analysis found for {position}")
            
            return {
                "position": analysis.position.value,
                "scoring_type": analysis.scoring_type.value,
                "tier_breaks": analysis.tier_breaks,
                "drop_off_points": analysis.drop_off_points,
                "scarcity_score": analysis.scarcity_score,
                "player_count": analysis.player_count,
                "analysis_date": analysis.analysis_date.isoformat()
            }
        else:
            # Get all positions
            analyses = ScarcityCRUD.get_all_scarcity_analyses(db, scoring_type)
            
            return {
                "scoring_type": scoring_type.value,
                "positions": [
                    {
                        "position": analysis.position.value,
                        "tier_breaks": analysis.tier_breaks,
                        "drop_off_points": analysis.drop_off_points,
                        "scarcity_score": analysis.scarcity_score,
                        "player_count": analysis.player_count
                    }
                    for analysis in analyses
                ],
                "position_rankings": sorted(
                    [(a.position.value, a.scarcity_score) for a in analyses],
                    key=lambda x: x[1],
                    reverse=True
                )
            }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/season-simulation/{league_id}")
async def simulate_season(
    league_id: int,
    scoring_type: ScoringTypeEnum = ScoringTypeEnum.PPR,
    db: Session = Depends(get_db)
):
    """
    Run Monte Carlo season simulation for playoff probabilities
    """
    try:
        simulator = SeasonSimulator(db)
        results = simulator.simulate_season(league_id, scoring_type)
        
        return results
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/competitive-advantage/{team_id}")
async def get_competitive_advantage(
    team_id: int,
    scoring_type: ScoringTypeEnum = ScoringTypeEnum.PPR,
    db: Session = Depends(get_db)
):
    """
    Get detailed competitive advantage analysis for a team
    """
    try:
        evaluator = TeamEvaluator(db)
        evaluation = evaluator.evaluate_team(team_id, scoring_type)
        
        # Enhanced analysis with competitive insights
        competitive_analysis = {
            "team_evaluation": evaluation,
            "strengths": [],
            "weaknesses": [],
            "recommendations": []
        }
        
        # Analyze strengths
        vorp_analysis = evaluation["vorp_analysis"]
        if vorp_analysis["starting_lineup_vorp"] > 20:
            competitive_analysis["strengths"].append("Elite starting lineup value")
        
        depth_analysis = evaluation["depth_analysis"]
        if depth_analysis["overall_depth_score"] > 6:
            competitive_analysis["strengths"].append("Strong roster depth")
        
        # Analyze weaknesses
        if vorp_analysis["starting_lineup_vorp"] < 0:
            competitive_analysis["weaknesses"].append("Below-average starting lineup")
        
        if depth_analysis["overall_depth_score"] < 4:
            competitive_analysis["weaknesses"].append("Lack of roster depth")
        
        bye_analysis = evaluation["bye_week_analysis"]
        if bye_analysis["total_bye_impact"] > 15:
            competitive_analysis["weaknesses"].append("Challenging bye week schedule")
        
        # Generate recommendations
        positional_strength = evaluation["positional_strength"]
        weak_positions = [pos for pos, data in positional_strength.items() 
                         if data.get("strength_grade", "C") in ["C", "D"]]
        
        if weak_positions:
            competitive_analysis["recommendations"].append(
                f"Consider upgrading at: {', '.join(weak_positions)}"
            )
        
        if depth_analysis["overall_depth_score"] < 5:
            competitive_analysis["recommendations"].append(
                "Focus on adding depth players from waiver wire"
            )
        
        return competitive_analysis
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/refresh-analysis")
async def refresh_analysis(
    scoring_type: ScoringTypeEnum = ScoringTypeEnum.PPR,
    db: Session = Depends(get_db)
):
    """
    Refresh scarcity analysis for all positions
    """
    try:
        analyzer = ScarcityAnalyzer(db)
        results = analyzer.analyze_all_positions(scoring_type)
        
        return {
            "message": "Analysis refreshed successfully",
            "scoring_type": scoring_type.value,
            "positions_analyzed": len(results),
            "results": results
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
