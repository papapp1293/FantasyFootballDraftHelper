from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import uuid
import random
import logging
from sqlalchemy.orm import Session

from ..data.models import Player, PositionEnum, ScoringTypeEnum
from ..data.crud import PlayerCRUD

logger = logging.getLogger(__name__)

class DraftPickType(Enum):
    USER = "user"
    BOT = "bot"

@dataclass
class DraftPick:
    """Represents a single draft pick"""
    pick_number: int
    team_id: int
    player: Player
    pick_type: DraftPickType
    reasoning: str = ""

@dataclass
class TeamRoster:
    """Current roster for a draft team"""
    team_id: int
    team_name: str
    picks: List[DraftPick]
    positional_needs: Dict[PositionEnum, int]
    
    def get_players_by_position(self, position: PositionEnum) -> List[Player]:
        return [pick.player for pick in self.picks if pick.player.position == position]
    
    def has_position_filled(self, position: PositionEnum, min_count: int = 1) -> bool:
        return len(self.get_players_by_position(position)) >= min_count

@dataclass
class LiveDraftState:
    """Current state of a live draft"""
    draft_id: str
    teams: List[TeamRoster]
    available_players: List[Player]
    current_pick: int
    current_team_id: int
    scoring_type: ScoringTypeEnum
    draft_order: List[int]  # Team IDs in draft order
    is_snake_draft: bool = True
    
    def get_current_team(self) -> TeamRoster:
        return next(team for team in self.teams if team.team_id == self.current_team_id)
    
    def get_next_team_id(self) -> int:
        """Get the next team to pick based on snake draft logic"""
        if not self.is_snake_draft:
            # Standard draft - same order every round
            round_pick = (self.current_pick - 1) % len(self.draft_order)
            return self.draft_order[round_pick]
        else:
            # Snake draft - alternate direction each round
            teams_count = len(self.draft_order)
            round_num = (self.current_pick - 1) // teams_count
            round_pick = (self.current_pick - 1) % teams_count
            
            if round_num % 2 == 0:
                # Even rounds: normal order
                return self.draft_order[round_pick]
            else:
                # Odd rounds: reverse order
                return self.draft_order[teams_count - 1 - round_pick]

class BotDraftStrategy(Enum):
    """Different bot drafting strategies"""
    BEST_AVAILABLE = "best_available"  # Always pick highest projected points
    POSITIONAL_NEED = "positional_need"  # Focus on filling roster holes
    VALUE_BASED = "value_based"  # ADP vs projection value
    SCARCITY_AWARE = "scarcity_aware"  # Consider positional scarcity

class LiveDraftSimulator:
    """Live draft simulation with bot players and dynamic scarcity"""
    
    def __init__(self, db: Session):
        self.db = db
        self.scarcity_analyzer = ScarcityAnalyzer(db)
    
    def create_draft(self, team_count: int = 12, user_team_id: int = 1, 
                    scoring_type: ScoringTypeEnum = ScoringTypeEnum.PPR) -> LiveDraftState:
        """Create a new live draft with bots"""
        
        try:
            # Get all available players - use existing method without limit parameter
            all_players = PlayerCRUD.get_all_players(self.db, scoring_type)
            
            # Filter to players with projections and limit to top 300 for performance
            available_players = [
                p for p in all_players 
                if self._get_projected_points(p, scoring_type) is not None
            ]
            
            # Sort by ADP for better draft order and limit to top 300
            available_players.sort(key=lambda p: self._get_adp(p, scoring_type) or 999)
            available_players = available_players[:300]  # Limit to top 300 players
            
            logger.info(f"Loaded {len(available_players)} players for draft creation")
        except Exception as e:
            logger.error(f"Error loading players for draft: {e}")
            # Fallback: create with empty player list and load later
            available_players = []
        
        # Create teams
        teams = []
        draft_order = list(range(1, team_count + 1))
        
        for team_id in draft_order:
            team_name = f"User Team" if team_id == user_team_id else f"Bot Team {team_id}"
            positional_needs = self._get_standard_positional_needs()
            
            teams.append(TeamRoster(
                team_id=team_id,
                team_name=team_name,
                picks=[],
                positional_needs=positional_needs
            ))
        
        draft_state = LiveDraftState(
            draft_id=f"draft_{random.randint(1000, 9999)}",
            teams=teams,
            available_players=available_players,
            current_pick=1,
            current_team_id=draft_order[0],
            scoring_type=scoring_type,
            draft_order=draft_order,
            is_snake_draft=True
        )
        
        logger.info(f"Created live draft {draft_state.draft_id} with {team_count} teams")
        return draft_state
    
    def make_user_pick(self, draft_state: LiveDraftState, player_id: int) -> LiveDraftState:
        """User makes a draft pick"""
        
        # Find the player
        player = next((p for p in draft_state.available_players if p.id == player_id), None)
        if not player:
            raise ValueError(f"Player {player_id} not available")
        
        # Make the pick
        current_team = draft_state.get_current_team()
        pick = DraftPick(
            pick_number=draft_state.current_pick,
            team_id=current_team.team_id,
            player=player,
            pick_type=DraftPickType.USER,
            reasoning="User selection"
        )
        
        # Update draft state
        current_team.picks.append(pick)
        draft_state.available_players.remove(player)
        self._update_positional_needs(current_team, player)
        
        # Advance to next pick
        draft_state.current_pick += 1
        draft_state.current_team_id = draft_state.get_next_team_id()
        
        logger.info(f"User picked {player.name} (Pick #{pick.pick_number})")
        return draft_state
    
    def make_bot_pick(self, draft_state: LiveDraftState, 
                     strategy: BotDraftStrategy = BotDraftStrategy.SCARCITY_AWARE) -> LiveDraftState:
        """Bot makes a draft pick using specified strategy"""
        
        current_team = draft_state.get_current_team()
        
        # Get dynamic scarcity analysis for remaining players
        scarcity_data = self._get_dynamic_scarcity(draft_state)
        
        # Choose player based on strategy
        if strategy == BotDraftStrategy.BEST_AVAILABLE:
            player = self._pick_best_available(draft_state)
        elif strategy == BotDraftStrategy.POSITIONAL_NEED:
            player = self._pick_by_positional_need(draft_state)
        elif strategy == BotDraftStrategy.VALUE_BASED:
            player = self._pick_by_value(draft_state)
        else:  # SCARCITY_AWARE
            player = self._pick_by_scarcity(draft_state, scarcity_data)
        
        # Make the pick
        pick = DraftPick(
            pick_number=draft_state.current_pick,
            team_id=current_team.team_id,
            player=player,
            pick_type=DraftPickType.BOT,
            reasoning=f"Bot strategy: {strategy.value}"
        )
        
        # Update draft state
        current_team.picks.append(pick)
        draft_state.available_players.remove(player)
        self._update_positional_needs(current_team, player)
        
        # Advance to next pick
        draft_state.current_pick += 1
        if draft_state.current_pick <= len(draft_state.draft_order) * 16:  # Assuming 16 rounds
            draft_state.current_team_id = draft_state.get_next_team_id()
        
        logger.info(f"Bot picked {player.name} (Pick #{pick.pick_number}, Strategy: {strategy.value})")
        return draft_state
    
    def get_user_recommendations(self, draft_state: LiveDraftState, top_n: int = 5) -> List[Dict[str, Any]]:
        """Get recommendations for user's next pick with dynamic scarcity"""
        
        if draft_state.current_team_id != 1:  # Assuming user is team 1
            return []
        
        current_team = draft_state.get_current_team()
        scarcity_data = self._get_dynamic_scarcity(draft_state)
        
        # Score available players
        recommendations = []
        
        for player in draft_state.available_players[:50]:  # Limit for performance
            score = self._calculate_player_score(player, current_team, draft_state, scarcity_data)
            
            recommendations.append({
                'player': {
                    'id': player.id,
                    'name': player.name,
                    'position': player.position.value,
                    'team': player.team,
                    'projected_points': self._get_projected_points(player, draft_state.scoring_type),
                    'adp': self._get_adp(player, draft_state.scoring_type)
                },
                'score': score,
                'reasoning': self._get_pick_reasoning(player, current_team, scarcity_data)
            })
        
        # Sort by score and return top N
        recommendations.sort(key=lambda x: x['score'], reverse=True)
        return recommendations[:top_n]
    
    def _get_dynamic_scarcity(self, draft_state: LiveDraftState) -> Dict[str, Any]:
        """Calculate scarcity analysis for remaining available players"""
        
        scarcity_results = {}
        
        for position in [PositionEnum.QB, PositionEnum.RB, PositionEnum.WR, PositionEnum.TE]:
            position_players = [
                p for p in draft_state.available_players 
                if p.position == position and self._get_projected_points(p, draft_state.scoring_type) is not None
            ]
            
            if len(position_players) >= 5:  # Need minimum players for analysis
                analysis = self.scarcity_analyzer.analyze_position_scarcity(position, draft_state.scoring_type)
                
                # Filter analysis to only available players
                available_analysis = self._filter_scarcity_to_available(analysis, position_players)
                scarcity_results[position.value] = available_analysis
        
        return scarcity_results
    
    def _pick_by_scarcity(self, draft_state: LiveDraftState, scarcity_data: Dict[str, Any]) -> Player:
        """Pick player based on scarcity analysis and positional needs"""
        
        current_team = draft_state.get_current_team()
        candidates = []
        
        # Score players based on scarcity and need
        for player in draft_state.available_players[:30]:  # Top 30 available
            position = player.position.value
            
            if position in scarcity_data:
                pos_scarcity = scarcity_data[position]
                tier_breaks = pos_scarcity.get('tier_breaks', [])
                
                # Calculate scarcity urgency
                scarcity_score = self._calculate_scarcity_urgency(player, tier_breaks, draft_state)
                
                # Factor in positional need
                need_multiplier = current_team.positional_needs.get(player.position, 0) / 3.0
                
                # Base player value
                base_value = self._get_projected_points(player, draft_state.scoring_type) or 0
                
                total_score = base_value + (scarcity_score * 50) + (need_multiplier * 30)
                
                candidates.append((player, total_score))
        
        if candidates:
            # Add some randomness to make bots less predictable
            candidates.sort(key=lambda x: x[1], reverse=True)
            top_candidates = candidates[:3]
            weights = [3, 2, 1]  # Prefer top candidate but allow variation
            
            chosen = random.choices(top_candidates, weights=weights)[0]
            return chosen[0]
        
        # Fallback to best available
        return self._pick_best_available(draft_state)
    
    def _pick_best_available(self, draft_state: LiveDraftState) -> Player:
        """Pick highest projected points player"""
        return max(
            draft_state.available_players[:20], 
            key=lambda p: self._get_projected_points(p, draft_state.scoring_type) or 0
        )
    
    def _pick_by_positional_need(self, draft_state: LiveDraftState) -> Player:
        """Pick based on roster holes"""
        current_team = draft_state.get_current_team()
        
        # Find positions with highest need
        max_need = max(current_team.positional_needs.values())
        needed_positions = [pos for pos, need in current_team.positional_needs.items() if need == max_need]
        
        # Get best player from needed positions
        candidates = [
            p for p in draft_state.available_players[:30]
            if p.position in needed_positions
        ]
        
        if candidates:
            return max(candidates, key=lambda p: self._get_projected_points(p, draft_state.scoring_type) or 0)
        
        return self._pick_best_available(draft_state)
    
    def _pick_by_value(self, draft_state: LiveDraftState) -> Player:
        """Pick based on ADP vs projection value"""
        best_value = None
        best_value_score = -999
        
        for player in draft_state.available_players[:30]:
            projected = self._get_projected_points(player, draft_state.scoring_type) or 0
            adp = self._get_adp(player, draft_state.scoring_type) or 999
            
            # Simple value calculation: how much better than ADP expectation
            expected_at_adp = max(0, 300 - adp * 2)  # Rough expectation curve
            value_score = projected - expected_at_adp
            
            if value_score > best_value_score:
                best_value_score = value_score
                best_value = player
        
        return best_value or self._pick_best_available(draft_state)
    
    def _calculate_player_score(self, player: Player, team: TeamRoster, 
                               draft_state: LiveDraftState, scarcity_data: Dict[str, Any]) -> float:
        """Calculate comprehensive player score for recommendations"""
        
        # Base value from projections
        base_value = self._get_projected_points(player, draft_state.scoring_type) or 0
        
        # Positional need bonus
        need_bonus = team.positional_needs.get(player.position, 0) * 20
        
        # Scarcity bonus
        scarcity_bonus = 0
        position = player.position.value
        if position in scarcity_data:
            pos_scarcity = scarcity_data[position]
            tier_breaks = pos_scarcity.get('tier_breaks', [])
            scarcity_bonus = self._calculate_scarcity_urgency(player, tier_breaks, draft_state) * 30
        
        return base_value + need_bonus + scarcity_bonus
    
    def _calculate_scarcity_urgency(self, player: Player, tier_breaks: List[int], 
                                   draft_state: LiveDraftState) -> float:
        """Calculate how urgent it is to draft this player based on tier breaks"""
        
        # Find player's current rank among available players of same position
        same_position = [
            p for p in draft_state.available_players 
            if p.position == player.position
        ]
        same_position.sort(key=lambda p: self._get_projected_points(p, draft_state.scoring_type) or 0, reverse=True)
        
        try:
            player_rank = same_position.index(player) + 1
        except ValueError:
            return 0.0
        
        # Check proximity to tier breaks
        urgency = 0.0
        for tier_break in tier_breaks:
            if player_rank <= tier_break <= player_rank + 3:
                # Player is near a tier break - high urgency
                urgency += 2.0
            elif player_rank <= tier_break <= player_rank + 6:
                # Moderate urgency
                urgency += 1.0
        
        return urgency
    
    def _get_pick_reasoning(self, player: Player, team: TeamRoster, scarcity_data: Dict[str, Any]) -> str:
        """Generate reasoning for why this player is recommended"""
        
        reasons = []
        
        # Positional need
        need = team.positional_needs.get(player.position, 0)
        if need >= 2:
            reasons.append(f"High positional need at {player.position.value}")
        elif need >= 1:
            reasons.append(f"Moderate need at {player.position.value}")
        
        # Scarcity
        position = player.position.value
        if position in scarcity_data:
            pos_scarcity = scarcity_data[position]
            tier_breaks = pos_scarcity.get('tier_breaks', [])
            if tier_breaks:
                reasons.append(f"Tier break approaching at {player.position.value}")
        
        # Value
        projected = self._get_projected_points(player, ScoringTypeEnum.PPR) or 0
        if projected > 200:
            reasons.append("High projected points")
        
        return "; ".join(reasons) if reasons else "Best available option"
    
    def _get_standard_positional_needs(self) -> Dict[PositionEnum, int]:
        """Standard starting lineup needs"""
        return {
            PositionEnum.QB: 1,
            PositionEnum.RB: 2,
            PositionEnum.WR: 2,
            PositionEnum.TE: 1,
            PositionEnum.K: 1,
            PositionEnum.DEF: 1
        }
    
    def _update_positional_needs(self, team: TeamRoster, player: Player):
        """Update team's positional needs after a pick"""
        if player.position in team.positional_needs:
            team.positional_needs[player.position] = max(0, team.positional_needs[player.position] - 1)
    
    def _filter_scarcity_to_available(self, analysis: Dict[str, Any], available_players: List[Player]) -> Dict[str, Any]:
        """Filter scarcity analysis to only include available players"""
        # This would need to be implemented based on the actual scarcity analysis structure
        return analysis
    
    def _get_projected_points(self, player: Player, scoring_type: ScoringTypeEnum) -> Optional[float]:
        """Get projected points for player based on scoring type"""
        if scoring_type == ScoringTypeEnum.PPR:
            return player.projected_points_ppr
        elif scoring_type == ScoringTypeEnum.HALF_PPR:
            return player.projected_points_half_ppr
        else:
            return player.projected_points_standard
    
    def _get_adp(self, player: Player, scoring_type: ScoringTypeEnum) -> Optional[float]:
        """Get ADP for player based on scoring type"""
        if scoring_type == ScoringTypeEnum.PPR:
            return player.adp_ppr
        elif scoring_type == ScoringTypeEnum.HALF_PPR:
            return player.adp_half_ppr
        else:
            return player.adp_standard
