from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
import numpy as np
import logging

from ..data.models import Player, Team, League, PositionEnum, ScoringTypeEnum
from ..data.crud import TeamCRUD, DraftCRUD, PlayerCRUD
from .season_simulation import SeasonSimulator

logger = logging.getLogger(__name__)

class TeamEvaluator:
    """Evaluate team strength and competitive advantage post-draft"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def evaluate_team(self, team_id: int, scoring_type: ScoringTypeEnum = ScoringTypeEnum.PPR) -> Dict[str, Any]:
        """
        Comprehensive team evaluation including VORP, depth, and projections
        
        Args:
            team_id: Team to evaluate
            scoring_type: Scoring system
            
        Returns:
            Dictionary with team evaluation metrics
        """
        team = TeamCRUD.get_team(self.db, team_id)
        if not team:
            raise ValueError("Invalid team ID")
        
        # Get team roster from draft picks
        roster = self._get_team_roster(team_id)
        
        if not roster:
            logger.warning(f"No roster found for team {team_id}")
            return {"error": "No roster data available"}
        
        # Calculate core metrics
        vorp_analysis = self._calculate_team_vorp(roster, scoring_type)
        depth_analysis = self._analyze_team_depth(roster, scoring_type)
        projected_points = self._calculate_projected_points(roster, scoring_type)
        bye_week_analysis = self._analyze_bye_week_impact(roster)
        positional_strength = self._analyze_positional_strength(roster, scoring_type)
        
        # Overall team grade
        overall_grade = self._calculate_overall_grade(
            vorp_analysis, depth_analysis, projected_points, bye_week_analysis
        )
        
        evaluation = {
            "team_id": team_id,
            "team_name": team.name,
            "scoring_type": scoring_type.value,
            "overall_grade": overall_grade,
            "projected_points": projected_points,
            "vorp_analysis": vorp_analysis,
            "depth_analysis": depth_analysis,
            "bye_week_analysis": bye_week_analysis,
            "positional_strength": positional_strength,
            "roster_summary": self._create_roster_summary(roster, scoring_type)
        }
        
        # Update team metrics in database
        self._update_team_metrics(team, evaluation)
        
        return evaluation
    
    def _get_team_roster(self, team_id: int) -> List[Player]:
        """Get team's current roster from draft picks"""
        team = TeamCRUD.get_team(self.db, team_id)
        if not team or not team.league.drafts:
            return []
        
        # Get most recent draft
        current_draft = team.league.drafts[-1]
        picks = DraftCRUD.get_team_picks(self.db, current_draft.id, team_id)
        
        return [pick.player for pick in picks if pick.player]
    
    def _calculate_team_vorp(self, roster: List[Player], scoring_type: ScoringTypeEnum) -> Dict[str, Any]:
        """Calculate team's total VORP and positional breakdown"""
        total_vorp = 0.0
        positional_vorp = {}
        starting_lineup_vorp = 0.0
        
        # Group players by position
        by_position = {}
        for player in roster:
            pos = player.position.value
            if pos not in by_position:
                by_position[pos] = []
            by_position[pos].append(player)
        
        # Sort each position by VORP
        for pos, players in by_position.items():
            players.sort(key=lambda p: self._get_vorp(p, scoring_type) or 0, reverse=True)
            pos_vorp = sum(self._get_vorp(p, scoring_type) or 0 for p in players)
            positional_vorp[pos] = round(pos_vorp, 2)
            total_vorp += pos_vorp
        
        # Calculate starting lineup VORP (best players at each position)
        starting_lineup = self._get_optimal_starting_lineup(by_position, scoring_type)
        starting_lineup_vorp = sum(self._get_vorp(p, scoring_type) or 0 for p in starting_lineup)
        
        return {
            "total_vorp": round(total_vorp, 2),
            "starting_lineup_vorp": round(starting_lineup_vorp, 2),
            "positional_vorp": positional_vorp,
            "vorp_rank_estimate": self._estimate_vorp_rank(starting_lineup_vorp)
        }
    
    def _analyze_team_depth(self, roster: List[Player], scoring_type: ScoringTypeEnum) -> Dict[str, Any]:
        """Analyze team depth at each position"""
        depth_scores = {}
        
        # Group by position
        by_position = {}
        for player in roster:
            pos = player.position.value
            if pos not in by_position:
                by_position[pos] = []
            by_position[pos].append(player)
        
        # Calculate depth score for each position
        for pos, players in by_position.items():
            if not players:
                depth_scores[pos] = 0.0
                continue
            
            # Sort by projected points
            players.sort(key=lambda p: self._get_projected_points(p, scoring_type) or 0, reverse=True)
            
            # Depth score based on drop-off from starter to bench
            if len(players) == 1:
                depth_scores[pos] = 1.0  # No depth
            else:
                starter_points = self._get_projected_points(players[0], scoring_type) or 0
                backup_points = self._get_projected_points(players[1], scoring_type) or 0
                
                if starter_points > 0:
                    depth_ratio = backup_points / starter_points
                    depth_scores[pos] = round(min(10.0, depth_ratio * 10), 1)
                else:
                    depth_scores[pos] = 0.0
        
        # Overall depth score (weighted by position importance)
        position_weights = {"QB": 0.15, "RB": 0.25, "WR": 0.25, "TE": 0.15, "K": 0.05, "DEF": 0.05, "FLEX": 0.10}
        overall_depth = sum(depth_scores.get(pos, 0) * weight for pos, weight in position_weights.items())
        
        return {
            "overall_depth_score": round(overall_depth, 2),
            "positional_depth": depth_scores,
            "depth_grade": self._grade_depth(overall_depth)
        }
    
    def _calculate_projected_points(self, roster: List[Player], scoring_type: ScoringTypeEnum) -> Dict[str, Any]:
        """Calculate team's projected points for optimal lineup"""
        by_position = {}
        for player in roster:
            pos = player.position.value
            if pos not in by_position:
                by_position[pos] = []
            by_position[pos].append(player)
        
        # Get optimal starting lineup
        starting_lineup = self._get_optimal_starting_lineup(by_position, scoring_type)
        
        # Calculate total projected points
        total_projected = sum(self._get_projected_points(p, scoring_type) or 0 for p in starting_lineup)
        
        # Calculate positional breakdown
        positional_breakdown = {}
        for player in starting_lineup:
            pos = player.position.value
            if pos not in positional_breakdown:
                positional_breakdown[pos] = 0
            positional_breakdown[pos] += self._get_projected_points(player, scoring_type) or 0
        
        return {
            "total_projected_points": round(total_projected, 2),
            "positional_breakdown": {pos: round(pts, 2) for pos, pts in positional_breakdown.items()},
            "projected_rank_estimate": self._estimate_points_rank(total_projected)
        }
    
    def _analyze_bye_week_impact(self, roster: List[Player]) -> Dict[str, Any]:
        """Analyze bye week clustering and impact"""
        bye_weeks = {}
        total_impact = 0.0
        
        # Group players by bye week
        for player in roster:
            if player.bye_week:
                if player.bye_week not in bye_weeks:
                    bye_weeks[player.bye_week] = []
                bye_weeks[player.bye_week].append(player)
        
        # Calculate impact for each bye week
        week_impacts = {}
        for week, players in bye_weeks.items():
            # Impact based on number of starters on bye
            starters_on_bye = len([p for p in players if self._is_likely_starter(p)])
            impact_score = min(10.0, starters_on_bye * 2.5)  # Max impact of 10
            week_impacts[week] = {
                "players_count": len(players),
                "starters_count": starters_on_bye,
                "impact_score": round(impact_score, 1)
            }
            total_impact += impact_score
        
        return {
            "total_bye_impact": round(total_impact, 2),
            "worst_bye_week": max(week_impacts.items(), key=lambda x: x[1]["impact_score"])[0] if week_impacts else None,
            "bye_week_breakdown": week_impacts,
            "bye_grade": self._grade_bye_impact(total_impact)
        }
    
    def _analyze_positional_strength(self, roster: List[Player], scoring_type: ScoringTypeEnum) -> Dict[str, Any]:
        """Analyze relative strength at each position"""
        strengths = {}
        
        # Group by position
        by_position = {}
        for player in roster:
            pos = player.position.value
            if pos not in by_position:
                by_position[pos] = []
            by_position[pos].append(player)
        
        # Analyze each position
        for pos, players in by_position.items():
            if not players:
                continue
            
            # Get best player at position
            best_player = max(players, key=lambda p: self._get_projected_points(p, scoring_type) or 0)
            best_points = self._get_projected_points(best_player, scoring_type) or 0
            
            # Estimate positional rank (rough approximation)
            position_rank = self._estimate_positional_rank(best_player, pos, scoring_type)
            
            strengths[pos] = {
                "best_player": best_player.name,
                "projected_points": round(best_points, 2),
                "estimated_rank": position_rank,
                "player_count": len(players),
                "strength_grade": self._grade_positional_strength(position_rank)
            }
        
        return strengths
    
    def _get_optimal_starting_lineup(self, by_position: Dict[str, List[Player]], 
                                   scoring_type: ScoringTypeEnum) -> List[Player]:
        """Get optimal starting lineup from roster"""
        lineup = []
        
        # Sort each position by projected points
        for pos, players in by_position.items():
            players.sort(key=lambda p: self._get_projected_points(p, scoring_type) or 0, reverse=True)
        
        # Standard lineup: 1 QB, 2 RB, 2 WR, 1 TE, 1 FLEX, 1 K, 1 DEF
        if "QB" in by_position and by_position["QB"]:
            lineup.append(by_position["QB"][0])
        
        if "RB" in by_position:
            lineup.extend(by_position["RB"][:2])  # Top 2 RBs
        
        if "WR" in by_position:
            lineup.extend(by_position["WR"][:2])  # Top 2 WRs
        
        if "TE" in by_position and by_position["TE"]:
            lineup.append(by_position["TE"][0])
        
        if "K" in by_position and by_position["K"]:
            lineup.append(by_position["K"][0])
        
        if "DEF" in by_position and by_position["DEF"]:
            lineup.append(by_position["DEF"][0])
        
        # FLEX: Best remaining RB/WR/TE
        flex_candidates = []
        if "RB" in by_position and len(by_position["RB"]) > 2:
            flex_candidates.extend(by_position["RB"][2:])
        if "WR" in by_position and len(by_position["WR"]) > 2:
            flex_candidates.extend(by_position["WR"][2:])
        if "TE" in by_position and len(by_position["TE"]) > 1:
            flex_candidates.extend(by_position["TE"][1:])
        
        if flex_candidates:
            best_flex = max(flex_candidates, key=lambda p: self._get_projected_points(p, scoring_type) or 0)
            lineup.append(best_flex)
        
        return lineup
    
    def _calculate_overall_grade(self, vorp_analysis: Dict, depth_analysis: Dict, 
                               projected_points: Dict, bye_analysis: Dict) -> str:
        """Calculate overall team grade"""
        # Weight different factors
        vorp_score = min(100, max(0, vorp_analysis["starting_lineup_vorp"] + 50))  # Normalize VORP
        depth_score = depth_analysis["overall_depth_score"] * 10  # Convert to 0-100 scale
        points_score = min(100, max(0, (projected_points["total_projected_points"] - 1000) / 10))  # Rough normalization
        bye_penalty = bye_analysis["total_bye_impact"] * 2  # Penalty for bad bye weeks
        
        # Weighted average
        overall_score = (vorp_score * 0.4 + depth_score * 0.2 + points_score * 0.3 - bye_penalty * 0.1)
        
        # Convert to letter grade
        if overall_score >= 90:
            return "A+"
        elif overall_score >= 85:
            return "A"
        elif overall_score >= 80:
            return "A-"
        elif overall_score >= 75:
            return "B+"
        elif overall_score >= 70:
            return "B"
        elif overall_score >= 65:
            return "B-"
        elif overall_score >= 60:
            return "C+"
        elif overall_score >= 55:
            return "C"
        elif overall_score >= 50:
            return "C-"
        else:
            return "D"
    
    def _create_roster_summary(self, roster: List[Player], scoring_type: ScoringTypeEnum) -> Dict[str, Any]:
        """Create a summary of the roster"""
        by_position = {}
        for player in roster:
            pos = player.position.value
            if pos not in by_position:
                by_position[pos] = []
            by_position[pos].append(player)
        
        summary = {}
        for pos, players in by_position.items():
            players.sort(key=lambda p: self._get_projected_points(p, scoring_type) or 0, reverse=True)
            summary[pos] = [
                {
                    "name": p.name,
                    "team": p.team,
                    "projected_points": self._get_projected_points(p, scoring_type),
                    "vorp": self._get_vorp(p, scoring_type),
                    "bye_week": p.bye_week
                }
                for p in players
            ]
        
        return summary
    
    def _update_team_metrics(self, team: Team, evaluation: Dict[str, Any]) -> None:
        """Update team metrics in database"""
        metrics = {
            "total_vorp": evaluation["vorp_analysis"]["total_vorp"],
            "projected_points": evaluation["projected_points"]["total_projected_points"],
            "depth_score": evaluation["depth_analysis"]["overall_depth_score"],
            "bye_week_penalty": evaluation["bye_week_analysis"]["total_bye_impact"]
        }
        
        TeamCRUD.update_team_metrics(self.db, team.id, metrics)
    
    def compare_teams(self, league_id: int, scoring_type: ScoringTypeEnum = ScoringTypeEnum.PPR) -> Dict[str, Any]:
        """Compare all teams in a league"""
        teams = TeamCRUD.get_teams_by_league(self.db, league_id)
        team_evaluations = []
        
        for team in teams:
            try:
                evaluation = self.evaluate_team(team.id, scoring_type)
                team_evaluations.append(evaluation)
            except Exception as e:
                logger.error(f"Error evaluating team {team.id}: {e}")
                continue
        
        # Sort by projected points
        team_evaluations.sort(key=lambda x: x["projected_points"]["total_projected_points"], reverse=True)
        
        # Add rankings
        for i, evaluation in enumerate(team_evaluations):
            evaluation["power_ranking"] = i + 1
        
        return {
            "league_id": league_id,
            "scoring_type": scoring_type.value,
            "team_count": len(team_evaluations),
            "teams": team_evaluations,
            "league_averages": self._calculate_league_averages(team_evaluations)
        }
    
    def _calculate_league_averages(self, evaluations: List[Dict[str, Any]]) -> Dict[str, float]:
        """Calculate league-wide averages"""
        if not evaluations:
            return {}
        
        total_points = sum(e["projected_points"]["total_projected_points"] for e in evaluations)
        total_vorp = sum(e["vorp_analysis"]["total_vorp"] for e in evaluations)
        total_depth = sum(e["depth_analysis"]["overall_depth_score"] for e in evaluations)
        
        return {
            "avg_projected_points": round(total_points / len(evaluations), 2),
            "avg_total_vorp": round(total_vorp / len(evaluations), 2),
            "avg_depth_score": round(total_depth / len(evaluations), 2)
        }
    
    # Helper methods
    def _get_projected_points(self, player: Player, scoring_type: ScoringTypeEnum) -> Optional[float]:
        if scoring_type == ScoringTypeEnum.PPR:
            return player.projected_points_ppr
        elif scoring_type == ScoringTypeEnum.HALF_PPR:
            return player.projected_points_half_ppr
        else:
            return player.projected_points_standard
    
    def _get_vorp(self, player: Player, scoring_type: ScoringTypeEnum) -> Optional[float]:
        if scoring_type == ScoringTypeEnum.PPR:
            return player.vorp_ppr
        elif scoring_type == ScoringTypeEnum.HALF_PPR:
            return player.vorp_half_ppr
        else:
            return player.vorp_standard
    
    def _is_likely_starter(self, player: Player) -> bool:
        """Rough estimate if player is likely to be a starter"""
        return (player.adp_ppr or 999) < 150  # Top 150 ADP roughly corresponds to starters
    
    def _estimate_vorp_rank(self, vorp: float) -> int:
        """Rough estimate of team VORP ranking"""
        if vorp > 50:
            return 1
        elif vorp > 30:
            return 2
        elif vorp > 15:
            return 4
        elif vorp > 5:
            return 6
        elif vorp > -5:
            return 8
        else:
            return 10
    
    def _estimate_points_rank(self, points: float) -> int:
        """Rough estimate of team points ranking"""
        if points > 1400:
            return 1
        elif points > 1350:
            return 2
        elif points > 1300:
            return 4
        elif points > 1250:
            return 6
        elif points > 1200:
            return 8
        else:
            return 10
    
    def _estimate_positional_rank(self, player: Player, position: str, scoring_type: ScoringTypeEnum) -> int:
        """Rough estimate of positional ranking"""
        adp = getattr(player, f"adp_{scoring_type.value}", None) or 999
        
        # Rough positional rank based on ADP
        if position == "QB":
            return min(24, max(1, int(adp / 12) + 1))
        elif position in ["RB", "WR"]:
            return min(60, max(1, int(adp / 4) + 1))
        elif position == "TE":
            return min(24, max(1, int(adp / 8) + 1))
        else:
            return min(24, max(1, int(adp / 12) + 1))
    
    def _grade_depth(self, depth_score: float) -> str:
        if depth_score >= 7:
            return "A"
        elif depth_score >= 6:
            return "B"
        elif depth_score >= 5:
            return "C"
        else:
            return "D"
    
    def _grade_bye_impact(self, impact: float) -> str:
        if impact <= 5:
            return "A"
        elif impact <= 10:
            return "B"
        elif impact <= 15:
            return "C"
        else:
            return "D"
    
    def _grade_positional_strength(self, rank: int) -> str:
        if rank <= 3:
            return "A"
        elif rank <= 8:
            return "B"
        elif rank <= 15:
            return "C"
        else:
            return "D"
