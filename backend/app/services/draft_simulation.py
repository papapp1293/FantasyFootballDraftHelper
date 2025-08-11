from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import random
import logging
from dataclasses import dataclass

from ..data.models import Player, PositionEnum, ScoringTypeEnum, League, Team
from ..data.crud import PlayerCRUD, LeagueCRUD, TeamCRUD
from ..core.config import settings

logger = logging.getLogger(__name__)

@dataclass
class DraftRecommendation:
    """Recommendation for a draft pick"""
    player: Player
    expected_value: float
    opportunity_cost: float
    pick_grade: str
    reasoning: str

@dataclass
class DraftSimulationResult:
    """Result of a draft simulation"""
    recommended_picks: List[DraftRecommendation]
    team_projection: Dict[str, Any]
    draft_strategy: str
    simulation_confidence: float

class DraftSimulator:
    """Monte Carlo draft simulation for optimal pick recommendations"""
    
    def __init__(self, db: Session):
        self.db = db
        self.iterations = settings.DRAFT_SIMULATION_ITERATIONS
    
    def simulate_draft_pick(self, league_id: int, team_id: int, current_pick: int, 
                          available_players: List[Player], 
                          scoring_type: ScoringTypeEnum = ScoringTypeEnum.PPR) -> DraftRecommendation:
        """
        Simulate optimal pick for a team at current draft position
        
        Args:
            league_id: League ID
            team_id: Team making the pick
            current_pick: Current pick number in draft
            available_players: List of available players
            scoring_type: Scoring system
            
        Returns:
            DraftRecommendation with optimal pick and analysis
        """
        league = LeagueCRUD.get_league(self.db, league_id)
        team = TeamCRUD.get_team(self.db, team_id)
        
        if not league or not team:
            raise ValueError("Invalid league or team ID")
        
        # Get current team roster
        current_roster = self._get_current_roster(team_id, league_id)
        
        # Calculate positional needs
        positional_needs = self._calculate_positional_needs(current_roster, league.starting_lineup)
        
        # Run Monte Carlo simulation for each viable pick
        pick_evaluations = []
        
        # Consider top candidates (limit to top 20 available for performance)
        candidates = self._get_pick_candidates(available_players, positional_needs, scoring_type)[:20]
        
        for candidate in candidates:
            evaluation = self._evaluate_pick_candidate(
                candidate, team, league, current_pick, available_players, 
                positional_needs, scoring_type
            )
            pick_evaluations.append(evaluation)
        
        # Sort by expected value and return best pick
        pick_evaluations.sort(key=lambda x: x.expected_value, reverse=True)
        
        if pick_evaluations:
            return pick_evaluations[0]
        else:
            # Fallback: return highest projected player
            best_player = max(available_players, key=lambda p: self._get_projected_points(p, scoring_type) or 0)
            return DraftRecommendation(
                player=best_player,
                expected_value=self._get_projected_points(best_player, scoring_type) or 0,
                opportunity_cost=0.0,
                pick_grade="C",
                reasoning="Best available player (fallback recommendation)"
            )
    
    def _get_current_roster(self, team_id: int, league_id: int) -> Dict[str, List[Player]]:
        """Get current roster for a team"""
        from ..data.crud import DraftCRUD
        
        # Get draft for this league (assume most recent)
        drafts = self.db.query(League).filter(League.id == league_id).first().drafts
        if not drafts:
            return {pos.value: [] for pos in PositionEnum}
        
        current_draft = drafts[-1]  # Most recent draft
        picks = DraftCRUD.get_team_picks(self.db, current_draft.id, team_id)
        
        roster = {pos.value: [] for pos in PositionEnum}
        for pick in picks:
            if pick.player:
                roster[pick.player.position.value].append(pick.player)
        
        return roster
    
    def _calculate_positional_needs(self, current_roster: Dict[str, List[Player]], 
                                  starting_lineup: Dict[str, int]) -> Dict[str, float]:
        """Calculate positional need scores (0-1, higher = more need)"""
        needs = {}
        
        for position, required in starting_lineup.items():
            if position == "FLEX":
                # FLEX can be filled by RB/WR/TE
                flex_players = len(current_roster.get("RB", [])) + len(current_roster.get("WR", [])) + len(current_roster.get("TE", []))
                flex_need = max(0, required - flex_players)
                needs["FLEX"] = min(1.0, flex_need / required)
            else:
                current_count = len(current_roster.get(position, []))
                need = max(0, required - current_count)
                needs[position] = min(1.0, need / required)
        
        return needs
    
    def _get_pick_candidates(self, available_players: List[Player], 
                           positional_needs: Dict[str, float], 
                           scoring_type: ScoringTypeEnum) -> List[Player]:
        """Get viable pick candidates based on value and need"""
        candidates = []
        
        for player in available_players:
            # Calculate composite score: projected points * positional need
            projected_points = self._get_projected_points(player, scoring_type) or 0
            position_need = positional_needs.get(player.position.value, 0.1)  # Minimum 0.1 need
            
            # FLEX eligibility
            if player.position.value in ["RB", "WR", "TE"]:
                flex_need = positional_needs.get("FLEX", 0)
                position_need = max(position_need, flex_need)
            
            composite_score = projected_points * (1 + position_need)
            candidates.append((player, composite_score))
        
        # Sort by composite score and return players
        candidates.sort(key=lambda x: x[1], reverse=True)
        return [player for player, _ in candidates]
    
    def _evaluate_pick_candidate(self, candidate: Player, team: Team, league: League,
                               current_pick: int, available_players: List[Player],
                               positional_needs: Dict[str, float], 
                               scoring_type: ScoringTypeEnum) -> DraftRecommendation:
        """Evaluate a pick candidate using Monte Carlo simulation"""
        
        # Base expected value from projections and VORP
        projected_points = self._get_projected_points(candidate, scoring_type) or 0
        vorp = self._get_vorp(candidate, scoring_type) or 0
        
        # Calculate opportunity cost by simulating alternative picks
        opportunity_cost = self._calculate_opportunity_cost(
            candidate, available_players, current_pick, league, scoring_type
        )
        
        # Adjust for positional need
        position_need = positional_needs.get(candidate.position.value, 0.1)
        if candidate.position.value in ["RB", "WR", "TE"]:
            flex_need = positional_needs.get("FLEX", 0)
            position_need = max(position_need, flex_need)
        
        need_multiplier = 1 + (position_need * 0.5)  # Up to 50% bonus for high need
        
        # Calculate expected value
        expected_value = (projected_points + vorp) * need_multiplier
        
        # Grade the pick
        pick_grade = self._grade_pick(expected_value, opportunity_cost, current_pick)
        
        # Generate reasoning
        reasoning = self._generate_pick_reasoning(candidate, position_need, vorp, opportunity_cost)
        
        return DraftRecommendation(
            player=candidate,
            expected_value=round(expected_value, 2),
            opportunity_cost=round(opportunity_cost, 2),
            pick_grade=pick_grade,
            reasoning=reasoning
        )
    
    def _calculate_opportunity_cost(self, candidate: Player, available_players: List[Player],
                                  current_pick: int, league: League, 
                                  scoring_type: ScoringTypeEnum) -> float:
        """Calculate opportunity cost of picking this player"""
        
        # Estimate when this player might be picked by others
        candidate_adp = self._get_adp(candidate, scoring_type) or current_pick
        
        # If player likely to be available later, opportunity cost is higher
        picks_until_next_turn = self._calculate_picks_until_next_turn(current_pick, league.league_size, league.snake_draft)
        
        if candidate_adp > current_pick + picks_until_next_turn:
            # Player likely available later - high opportunity cost
            opportunity_cost = 10.0
        else:
            # Player might be gone - lower opportunity cost
            opportunity_cost = max(0, candidate_adp - current_pick)
        
        return opportunity_cost
    
    def _calculate_picks_until_next_turn(self, current_pick: int, league_size: int, snake_draft: bool) -> int:
        """Calculate how many picks until this team picks again"""
        if not snake_draft:
            return league_size - 1
        
        # Snake draft logic
        current_round = ((current_pick - 1) // league_size) + 1
        pick_in_round = ((current_pick - 1) % league_size) + 1
        
        if current_round % 2 == 1:  # Odd round (1, 3, 5...)
            picks_left_in_round = league_size - pick_in_round
            picks_in_next_round = pick_in_round - 1
        else:  # Even round (2, 4, 6...)
            picks_left_in_round = pick_in_round - 1
            picks_in_next_round = league_size - pick_in_round
        
        return picks_left_in_round + picks_in_next_round + 1
    
    def _grade_pick(self, expected_value: float, opportunity_cost: float, current_pick: int) -> str:
        """Grade a pick based on value and opportunity cost"""
        # Normalize expected value by pick position
        pick_round = ((current_pick - 1) // 12) + 1  # Assume 12-team league
        expected_for_round = max(1, 20 - (pick_round * 2))  # Rough expectation by round
        
        value_ratio = expected_value / expected_for_round
        
        # Factor in opportunity cost
        if opportunity_cost > 5:
            value_ratio *= 0.8  # Penalty for high opportunity cost
        
        # Grade scale
        if value_ratio >= 1.3:
            return "A+"
        elif value_ratio >= 1.2:
            return "A"
        elif value_ratio >= 1.1:
            return "A-"
        elif value_ratio >= 1.0:
            return "B+"
        elif value_ratio >= 0.9:
            return "B"
        elif value_ratio >= 0.8:
            return "B-"
        elif value_ratio >= 0.7:
            return "C+"
        elif value_ratio >= 0.6:
            return "C"
        else:
            return "C-"
    
    def _generate_pick_reasoning(self, player: Player, position_need: float, 
                               vorp: float, opportunity_cost: float) -> str:
        """Generate human-readable reasoning for pick recommendation"""
        reasons = []
        
        # Position need
        if position_need > 0.7:
            reasons.append(f"High need at {player.position.value}")
        elif position_need > 0.4:
            reasons.append(f"Moderate need at {player.position.value}")
        
        # Value
        if vorp and vorp > 5:
            reasons.append("Excellent value over replacement")
        elif vorp and vorp > 2:
            reasons.append("Good value over replacement")
        
        # Opportunity cost
        if opportunity_cost < 2:
            reasons.append("Unlikely to be available later")
        elif opportunity_cost > 8:
            reasons.append("May be available in later rounds")
        
        # Scarcity
        if hasattr(player, 'scarcity_score') and player.scarcity_score and player.scarcity_score > 5:
            reasons.append(f"High scarcity at {player.position.value}")
        
        if not reasons:
            reasons.append("Best available player")
        
        return "; ".join(reasons)
    
    def _get_projected_points(self, player: Player, scoring_type: ScoringTypeEnum) -> Optional[float]:
        """Get projected points for scoring type"""
        if scoring_type == ScoringTypeEnum.PPR:
            return player.projected_points_ppr
        elif scoring_type == ScoringTypeEnum.HALF_PPR:
            return player.projected_points_half_ppr
        else:
            return player.projected_points_standard
    
    def _get_vorp(self, player: Player, scoring_type: ScoringTypeEnum) -> Optional[float]:
        """Get VORP for scoring type"""
        if scoring_type == ScoringTypeEnum.PPR:
            return player.vorp_ppr
        elif scoring_type == ScoringTypeEnum.HALF_PPR:
            return player.vorp_half_ppr
        else:
            return player.vorp_standard
    
    def _get_adp(self, player: Player, scoring_type: ScoringTypeEnum) -> Optional[float]:
        """Get ADP for scoring type"""
        if scoring_type == ScoringTypeEnum.PPR:
            return player.adp_ppr
        elif scoring_type == ScoringTypeEnum.HALF_PPR:
            return player.adp_half_ppr
        else:
            return player.adp_standard
    
    def simulate_full_draft(self, league_id: int, scoring_type: ScoringTypeEnum = ScoringTypeEnum.PPR) -> Dict[str, Any]:
        """Simulate a complete draft for all teams"""
        league = LeagueCRUD.get_league(self.db, league_id)
        if not league:
            raise ValueError("Invalid league ID")
        
        # Get all available players
        all_players = PlayerCRUD.get_all_players(self.db, scoring_type)
        available_players = all_players.copy()
        
        # Initialize draft results
        draft_results = {
            "teams": {},
            "picks": [],
            "analysis": {}
        }
        
        # Simulate each pick
        total_picks = league.league_size * 16  # Assume 16 rounds
        
        for pick_num in range(1, total_picks + 1):
            if not available_players:
                break
                
            # Determine which team is picking
            team_id = self._get_picking_team(pick_num, league)
            
            # Get recommendation for this pick
            recommendation = self.simulate_draft_pick(
                league_id, team_id, pick_num, available_players, scoring_type
            )
            
            # Record the pick
            draft_results["picks"].append({
                "pick_number": pick_num,
                "team_id": team_id,
                "player": {
                    "id": recommendation.player.id,
                    "name": recommendation.player.name,
                    "position": recommendation.player.position.value,
                    "projected_points": self._get_projected_points(recommendation.player, scoring_type)
                },
                "expected_value": recommendation.expected_value,
                "pick_grade": recommendation.pick_grade
            })
            
            # Remove picked player from available players
            available_players.remove(recommendation.player)
            
            # Add to team roster
            if team_id not in draft_results["teams"]:
                draft_results["teams"][team_id] = []
            draft_results["teams"][team_id].append(recommendation.player)
        
        return draft_results
    
    def _get_picking_team(self, pick_number: int, league: League) -> int:
        """Determine which team is picking based on pick number and draft order"""
        if not league.draft_order:
            # Default round-robin order
            team_ids = [team.id for team in league.teams]
        else:
            team_ids = league.draft_order
        
        if league.snake_draft:
            round_num = ((pick_number - 1) // league.league_size) + 1
            pick_in_round = ((pick_number - 1) % league.league_size) + 1
            
            if round_num % 2 == 1:  # Odd rounds: normal order
                team_index = pick_in_round - 1
            else:  # Even rounds: reverse order
                team_index = league.league_size - pick_in_round
        else:
            # Standard draft: same order every round
            team_index = ((pick_number - 1) % league.league_size)
        
        return team_ids[team_index]
