from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import random
from dataclasses import dataclass
import logging

from ..data.models import Player, Team, League, PositionEnum, ScoringTypeEnum
from ..data.crud import TeamCRUD, PlayerCRUD
from ..core.config import settings

logger = logging.getLogger(__name__)

@dataclass
class WeeklyMatchup:
    """Represents a weekly fantasy matchup"""
    team1_id: int
    team2_id: int
    team1_score: float
    team2_score: float
    winner_id: int
    week: int

@dataclass
class SeasonResult:
    """Results of a season simulation"""
    team_id: int
    wins: int
    losses: int
    points_for: float
    points_against: float
    playoff_seed: Optional[int]
    championship_probability: float

class SeasonSimulator:
    """Monte Carlo season simulation for playoff probabilities"""
    
    def __init__(self, db: Session):
        self.db = db
        self.iterations = settings.MONTE_CARLO_ITERATIONS
        self.regular_season_weeks = 14  # Standard fantasy regular season
        self.playoff_teams = 6  # Standard playoff format
    
    def simulate_season(self, league_id: int, scoring_type: ScoringTypeEnum = ScoringTypeEnum.PPR) -> Dict[str, Any]:
        """
        Simulate a complete fantasy season with playoffs
        
        Args:
            league_id: League to simulate
            scoring_type: Scoring system
            
        Returns:
            Season simulation results with playoff probabilities
        """
        league = self.db.query(League).filter(League.id == league_id).first()
        if not league:
            raise ValueError("Invalid league ID")
        
        teams = TeamCRUD.get_teams_by_league(self.db, league_id)
        if len(teams) < 4:
            raise ValueError("Need at least 4 teams for season simulation")
        
        # Run multiple season simulations
        all_results = []
        
        for iteration in range(self.iterations):
            season_results = self._simulate_single_season(teams, scoring_type)
            all_results.append(season_results)
        
        # Aggregate results
        aggregated_results = self._aggregate_season_results(all_results, teams)
        
        return {
            "league_id": league_id,
            "scoring_type": scoring_type.value,
            "iterations": self.iterations,
            "team_results": aggregated_results,
            "league_analysis": self._analyze_league_competitiveness(aggregated_results)
        }
    
    def _simulate_single_season(self, teams: List[Team], scoring_type: ScoringTypeEnum) -> List[SeasonResult]:
        """Simulate a single season"""
        
        # Generate weekly scores for each team
        team_weekly_scores = {}
        for team in teams:
            team_weekly_scores[team.id] = self._generate_team_weekly_scores(team, scoring_type)
        
        # Simulate regular season matchups
        season_records = {team.id: {"wins": 0, "losses": 0, "pf": 0, "pa": 0} for team in teams}
        
        for week in range(1, self.regular_season_weeks + 1):
            matchups = self._generate_weekly_matchups(teams, week)
            
            for matchup in matchups:
                team1_score = team_weekly_scores[matchup.team1_id][week - 1]
                team2_score = team_weekly_scores[matchup.team2_id][week - 1]
                
                # Update records
                season_records[matchup.team1_id]["pf"] += team1_score
                season_records[matchup.team1_id]["pa"] += team2_score
                season_records[matchup.team2_id]["pf"] += team2_score
                season_records[matchup.team2_id]["pa"] += team1_score
                
                if team1_score > team2_score:
                    season_records[matchup.team1_id]["wins"] += 1
                    season_records[matchup.team2_id]["losses"] += 1
                else:
                    season_records[matchup.team2_id]["wins"] += 1
                    season_records[matchup.team1_id]["losses"] += 1
        
        # Determine playoff seeding
        playoff_teams = self._determine_playoff_seeding(season_records)
        
        # Simulate playoffs
        championship_winner = self._simulate_playoffs(playoff_teams, team_weekly_scores)
        
        # Create season results
        results = []
        for team_id, record in season_records.items():
            playoff_seed = None
            if team_id in [t[0] for t in playoff_teams]:
                playoff_seed = next(i + 1 for i, (tid, _) in enumerate(playoff_teams) if tid == team_id)
            
            championship_prob = 1.0 if team_id == championship_winner else 0.0
            
            results.append(SeasonResult(
                team_id=team_id,
                wins=record["wins"],
                losses=record["losses"],
                points_for=record["pf"],
                points_against=record["pa"],
                playoff_seed=playoff_seed,
                championship_probability=championship_prob
            ))
        
        return results
    
    def _generate_team_weekly_scores(self, team: Team, scoring_type: ScoringTypeEnum) -> List[float]:
        """Generate weekly fantasy scores for a team"""
        # Get team roster (from draft picks)
        from ..data.crud import DraftCRUD
        
        # Find most recent draft for this team's league
        league = team.league
        if not league.drafts:
            # Use projected points as baseline if no draft data
            base_score = team.projected_points or 100.0
            weekly_variance = 0.2  # 20% variance
        else:
            current_draft = league.drafts[-1]
            picks = DraftCRUD.get_team_picks(self.db, current_draft.id, team.id)
            
            # Calculate optimal lineup score
            base_score = self._calculate_optimal_lineup_score(picks, scoring_type)
            weekly_variance = 0.25  # 25% variance for real rosters
        
        # Generate weekly scores with variance
        weekly_scores = []
        for week in range(self.regular_season_weeks + 4):  # Include playoff weeks
            # Add weekly variance (normal distribution)
            variance_factor = np.random.normal(1.0, weekly_variance)
            variance_factor = max(0.5, min(1.5, variance_factor))  # Clamp variance
            
            weekly_score = base_score * variance_factor
            weekly_scores.append(round(weekly_score, 2))
        
        return weekly_scores
    
    def _calculate_optimal_lineup_score(self, picks: List, scoring_type: ScoringTypeEnum) -> float:
        """Calculate optimal starting lineup score from draft picks"""
        if not picks:
            return 100.0  # Default score
        
        # Group players by position
        roster = {"QB": [], "RB": [], "WR": [], "TE": [], "K": [], "DEF": []}
        
        for pick in picks:
            if pick.player and pick.player.position:
                pos = pick.player.position.value
                if pos in roster:
                    projected = self._get_projected_points(pick.player, scoring_type) or 0
                    roster[pos].append(projected)
        
        # Sort each position by projected points (descending)
        for pos in roster:
            roster[pos].sort(reverse=True)
        
        # Calculate optimal lineup (1 QB, 2 RB, 2 WR, 1 TE, 1 FLEX, 1 K, 1 DEF)
        lineup_score = 0.0
        
        # Required starters
        lineup_score += roster["QB"][0] if roster["QB"] else 0
        lineup_score += sum(roster["RB"][:2]) if len(roster["RB"]) >= 2 else sum(roster["RB"])
        lineup_score += sum(roster["WR"][:2]) if len(roster["WR"]) >= 2 else sum(roster["WR"])
        lineup_score += roster["TE"][0] if roster["TE"] else 0
        lineup_score += roster["K"][0] if roster["K"] else 0
        lineup_score += roster["DEF"][0] if roster["DEF"] else 0
        
        # FLEX (best remaining RB/WR/TE)
        flex_options = []
        if len(roster["RB"]) > 2:
            flex_options.extend(roster["RB"][2:])
        if len(roster["WR"]) > 2:
            flex_options.extend(roster["WR"][2:])
        if len(roster["TE"]) > 1:
            flex_options.extend(roster["TE"][1:])
        
        if flex_options:
            lineup_score += max(flex_options)
        
        return max(lineup_score, 50.0)  # Minimum reasonable score
    
    def _generate_weekly_matchups(self, teams: List[Team], week: int) -> List[WeeklyMatchup]:
        """Generate matchups for a given week"""
        # Simple round-robin scheduling
        team_ids = [team.id for team in teams]
        random.shuffle(team_ids)  # Randomize matchups
        
        matchups = []
        for i in range(0, len(team_ids), 2):
            if i + 1 < len(team_ids):
                matchups.append(WeeklyMatchup(
                    team1_id=team_ids[i],
                    team2_id=team_ids[i + 1],
                    team1_score=0,  # Will be filled later
                    team2_score=0,
                    winner_id=0,
                    week=week
                ))
        
        return matchups
    
    def _determine_playoff_seeding(self, season_records: Dict[int, Dict]) -> List[Tuple[int, Dict]]:
        """Determine playoff seeding based on regular season records"""
        # Sort teams by wins, then by points for
        teams_sorted = sorted(
            season_records.items(),
            key=lambda x: (x[1]["wins"], x[1]["pf"]),
            reverse=True
        )
        
        # Return top teams for playoffs
        return teams_sorted[:self.playoff_teams]
    
    def _simulate_playoffs(self, playoff_teams: List[Tuple[int, Dict]], 
                         team_weekly_scores: Dict[int, List[float]]) -> int:
        """Simulate playoff bracket and return championship winner"""
        if len(playoff_teams) < 4:
            return playoff_teams[0][0] if playoff_teams else 0
        
        # Standard 6-team playoff: top 2 get bye, seeds 3-6 play wild card
        if len(playoff_teams) >= 6:
            # Wild card round (week 15)
            wild_card_winners = []
            
            # 3 vs 6
            team3_score = team_weekly_scores[playoff_teams[2][0]][14]  # Week 15
            team6_score = team_weekly_scores[playoff_teams[5][0]][14]
            wild_card_winners.append(playoff_teams[2][0] if team3_score > team6_score else playoff_teams[5][0])
            
            # 4 vs 5
            team4_score = team_weekly_scores[playoff_teams[3][0]][14]
            team5_score = team_weekly_scores[playoff_teams[4][0]][14]
            wild_card_winners.append(playoff_teams[3][0] if team4_score > team5_score else playoff_teams[4][0])
            
            # Semifinals (week 16): 1 vs lower seed, 2 vs higher seed
            semifinal_winners = []
            
            # 1 seed vs lower wild card winner
            seed1_score = team_weekly_scores[playoff_teams[0][0]][15]  # Week 16
            lower_wc_score = team_weekly_scores[wild_card_winners[1]][15]
            semifinal_winners.append(playoff_teams[0][0] if seed1_score > lower_wc_score else wild_card_winners[1])
            
            # 2 seed vs higher wild card winner
            seed2_score = team_weekly_scores[playoff_teams[1][0]][15]
            higher_wc_score = team_weekly_scores[wild_card_winners[0]][15]
            semifinal_winners.append(playoff_teams[1][0] if seed2_score > higher_wc_score else wild_card_winners[0])
            
            # Championship (week 17)
            champ1_score = team_weekly_scores[semifinal_winners[0]][16]  # Week 17
            champ2_score = team_weekly_scores[semifinal_winners[1]][16]
            
            return semifinal_winners[0] if champ1_score > champ2_score else semifinal_winners[1]
        
        else:
            # Simple 4-team playoff
            # Semifinals
            semi1_winner = playoff_teams[0][0] if team_weekly_scores[playoff_teams[0][0]][15] > team_weekly_scores[playoff_teams[3][0]][15] else playoff_teams[3][0]
            semi2_winner = playoff_teams[1][0] if team_weekly_scores[playoff_teams[1][0]][15] > team_weekly_scores[playoff_teams[2][0]][15] else playoff_teams[2][0]
            
            # Championship
            return semi1_winner if team_weekly_scores[semi1_winner][16] > team_weekly_scores[semi2_winner][16] else semi2_winner
    
    def _aggregate_season_results(self, all_results: List[List[SeasonResult]], teams: List[Team]) -> List[Dict[str, Any]]:
        """Aggregate results across all simulation iterations"""
        aggregated = {}
        
        # Initialize aggregation structure
        for team in teams:
            aggregated[team.id] = {
                "team_id": team.id,
                "team_name": team.name,
                "avg_wins": 0.0,
                "avg_losses": 0.0,
                "avg_points_for": 0.0,
                "avg_points_against": 0.0,
                "playoff_probability": 0.0,
                "championship_probability": 0.0,
                "seed_distribution": {i: 0 for i in range(1, self.playoff_teams + 1)}
            }
        
        # Aggregate across iterations
        total_iterations = len(all_results)
        
        for season_results in all_results:
            for result in season_results:
                team_data = aggregated[result.team_id]
                
                team_data["avg_wins"] += result.wins
                team_data["avg_losses"] += result.losses
                team_data["avg_points_for"] += result.points_for
                team_data["avg_points_against"] += result.points_against
                
                if result.playoff_seed:
                    team_data["playoff_probability"] += 1
                    team_data["seed_distribution"][result.playoff_seed] += 1
                
                team_data["championship_probability"] += result.championship_probability
        
        # Calculate averages and probabilities
        for team_id, data in aggregated.items():
            data["avg_wins"] = round(data["avg_wins"] / total_iterations, 2)
            data["avg_losses"] = round(data["avg_losses"] / total_iterations, 2)
            data["avg_points_for"] = round(data["avg_points_for"] / total_iterations, 2)
            data["avg_points_against"] = round(data["avg_points_against"] / total_iterations, 2)
            data["playoff_probability"] = round(data["playoff_probability"] / total_iterations * 100, 1)
            data["championship_probability"] = round(data["championship_probability"] / total_iterations * 100, 1)
            
            # Convert seed distribution to percentages
            for seed in data["seed_distribution"]:
                data["seed_distribution"][seed] = round(data["seed_distribution"][seed] / total_iterations * 100, 1)
        
        # Sort by championship probability
        return sorted(aggregated.values(), key=lambda x: x["championship_probability"], reverse=True)
    
    def _analyze_league_competitiveness(self, team_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze overall league competitiveness"""
        championship_probs = [team["championship_probability"] for team in team_results]
        playoff_probs = [team["playoff_probability"] for team in team_results]
        
        return {
            "parity_score": round(100 - np.std(championship_probs), 1),  # Higher = more parity
            "competitive_balance": round(np.mean(playoff_probs), 1),
            "championship_favorite": team_results[0]["team_name"] if team_results else None,
            "championship_favorite_probability": team_results[0]["championship_probability"] if team_results else 0,
            "playoff_lock_teams": len([t for t in team_results if t["playoff_probability"] > 90]),
            "bubble_teams": len([t for t in team_results if 30 <= t["playoff_probability"] <= 70])
        }
    
    def _get_projected_points(self, player: Player, scoring_type: ScoringTypeEnum) -> Optional[float]:
        """Get projected points for scoring type"""
        if scoring_type == ScoringTypeEnum.PPR:
            return player.projected_points_ppr
        elif scoring_type == ScoringTypeEnum.HALF_PPR:
            return player.projected_points_half_ppr
        else:
            return player.projected_points_standard
