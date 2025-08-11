"""
Dynamic VORP and Scarcity Engine for Live Fantasy Football Drafts

This module implements incremental VORP calculation, positional scarcity analysis,
and draft state management with real-time updates as picks are made.
"""

from typing import Dict, List, Set, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import uuid
import math
import logging
from sqlalchemy.orm import Session

from ..data.models import Player, PositionEnum, ScoringTypeEnum
from ..data.crud import PlayerCRUD

logger = logging.getLogger(__name__)

@dataclass
class Pick:
    """Represents a single draft pick"""
    pick_index: int  # 0-based global pick index
    team_id: int
    player_id: int
    round_number: int
    pick_in_round: int
    timestamp: float

@dataclass
class ScarcityMetrics:
    """Positional scarcity metrics"""
    position: PositionEnum
    avg_vorp_remaining: float
    dropoff_at_next_tier: float
    scarcity_score: float
    urgency_flag: bool
    replacement_level: float
    players_remaining: int

@dataclass
class TeamRoster:
    """Team roster and needs tracking"""
    team_id: int
    picks: List[int] = field(default_factory=list)  # player_ids
    positional_counts: Dict[PositionEnum, int] = field(default_factory=dict)
    need_scores: Dict[PositionEnum, float] = field(default_factory=dict)
    
    def __post_init__(self):
        # Initialize positional counts
        for pos in PositionEnum:
            self.positional_counts[pos] = 0
            self.need_scores[pos] = 0.0

@dataclass
class DraftState:
    """Authoritative in-memory draft state with dynamic VORP/scarcity"""
    draft_id: str
    num_teams: int
    draft_spot: int  # User's position (1-based)
    snake: bool
    scoring_mode: ScoringTypeEnum
    
    # Draft progression
    draft_order: List[int] = field(default_factory=list)  # team_ids in order
    current_pick_index: int = 0  # 0-based global pick index
    picks: List[Pick] = field(default_factory=list)
    
    # Player tracking
    remaining_players: Set[int] = field(default_factory=set)  # player_ids
    rosters: Dict[int, TeamRoster] = field(default_factory=dict)  # team_id -> roster
    
    # Dynamic caches
    vorp_cache: Dict[int, float] = field(default_factory=dict)  # player_id -> vorp
    scarcity_cache: Dict[PositionEnum, ScarcityMetrics] = field(default_factory=dict)
    replacement_levels: Dict[PositionEnum, float] = field(default_factory=dict)
    drafted_count_by_pos: Dict[PositionEnum, int] = field(default_factory=dict)
    
    # Next pick mapping
    next_pick_map: Dict[int, int] = field(default_factory=dict)  # team_id -> next_pick_index
    
    def __post_init__(self):
        # Initialize team rosters
        for team_id in range(1, self.num_teams + 1):
            self.rosters[team_id] = TeamRoster(team_id=team_id)
        
        # Initialize drafted counts
        for pos in PositionEnum:
            self.drafted_count_by_pos[pos] = 0
    
    def get_current_team_id(self) -> int:
        """Get the team ID for the current pick"""
        if self.current_pick_index >= len(self.draft_order):
            return self.draft_order[-1]  # Draft complete
        return self.draft_order[self.current_pick_index]
    
    def get_round_and_pick(self, pick_index: int) -> Tuple[int, int]:
        """Convert global pick index to round and pick-in-round"""
        round_number = (pick_index // self.num_teams) + 1
        pick_in_round = (pick_index % self.num_teams) + 1
        return round_number, pick_in_round
    
    def get_user_next_pick_index(self) -> Optional[int]:
        """Find the user's next pick index"""
        user_team_id = self.draft_spot
        for i in range(self.current_pick_index + 1, len(self.draft_order)):
            if self.draft_order[i] == user_team_id:
                return i
        return None

class DynamicDraftEngine:
    """Engine for dynamic VORP calculation and scarcity analysis"""
    
    # Standard roster requirements
    ROSTER_REQUIREMENTS = {
        PositionEnum.QB: 1,
        PositionEnum.RB: 2,
        PositionEnum.WR: 2,
        PositionEnum.TE: 1,
        PositionEnum.K: 1,
        PositionEnum.DEF: 1
    }
    
    BENCH_BUFFER = 3  # Additional players per position for replacement level
    
    def __init__(self, db: Session):
        self.db = db
        self.players_cache: Dict[int, Player] = {}
        self.position_players: Dict[PositionEnum, List[Player]] = {}
    
    def create_draft(self, num_teams: int, draft_spot: int, scoring_mode: ScoringTypeEnum) -> DraftState:
        """Create a new draft with initial state"""
        draft_id = f"draft_{uuid.uuid4().hex[:8]}"
        
        # Generate draft order
        draft_order = self._generate_draft_order(num_teams, snake=True)
        
        # Load and cache players
        self._load_players(scoring_mode)
        
        # Create draft state
        draft_state = DraftState(
            draft_id=draft_id,
            num_teams=num_teams,
            draft_spot=draft_spot,
            snake=True,
            scoring_mode=scoring_mode,
            draft_order=draft_order
        )
        
        # Initialize remaining players
        draft_state.remaining_players = set(self.players_cache.keys())
        
        # Calculate initial VORP and scarcity
        self._initialize_vorp_and_scarcity(draft_state)
        
        logger.info(f"Created draft {draft_id} with {num_teams} teams, user at spot {draft_spot}")
        return draft_state
    
    def make_pick(self, draft_state: DraftState, player_id: int) -> Dict[str, Any]:
        """Make a pick and update all dynamic metrics"""
        if player_id not in draft_state.remaining_players:
            raise ValueError(f"Player {player_id} not available")
        
        current_team_id = draft_state.get_current_team_id()
        round_num, pick_in_round = draft_state.get_round_and_pick(draft_state.current_pick_index)
        
        # Create pick record
        pick = Pick(
            pick_index=draft_state.current_pick_index,
            team_id=current_team_id,
            player_id=player_id,
            round_number=round_num,
            pick_in_round=pick_in_round,
            timestamp=time.time()
        )
        
        # Update draft state
        draft_state.picks.append(pick)
        draft_state.remaining_players.remove(player_id)
        draft_state.rosters[current_team_id].picks.append(player_id)
        
        # Update positional counts
        player = self.players_cache[player_id]
        draft_state.drafted_count_by_pos[player.position] += 1
        draft_state.rosters[current_team_id].positional_counts[player.position] += 1
        
        # Advance pick
        draft_state.current_pick_index += 1
        
        # Incremental VORP and scarcity update
        updated_metrics = self._update_vorp_and_scarcity(draft_state, player.position)
        
        # Update team needs
        self._update_team_needs(draft_state, current_team_id)
        
        logger.info(f"Pick made: Team {current_team_id} selected {player.name} ({player.position})")
        
        return {
            "pick": pick,
            "updated_vorp": updated_metrics["vorp_updates"],
            "updated_scarcity": updated_metrics["scarcity_updates"],
            "team_needs": draft_state.rosters[current_team_id].need_scores
        }
    
    def get_advice(self, draft_state: DraftState, team_id: int, mode: str = "robust") -> List[Dict[str, Any]]:
        """Generate draft advice for a team"""
        available_players = [
            self.players_cache[pid] for pid in draft_state.remaining_players
        ]
        
        if mode == "best_vorp":
            return self._advice_best_vorp(available_players, draft_state)
        elif mode == "fill_need":
            return self._advice_fill_need(available_players, draft_state, team_id)
        elif mode == "upside":
            return self._advice_upside(available_players, draft_state)
        else:  # robust
            return self._advice_robust(available_players, draft_state, team_id)
    
    def simulate_availability(self, draft_state: DraftState, team_id: int, num_sims: int = 500) -> Dict[str, Any]:
        """Simulate player availability at user's next pick"""
        user_next_pick = draft_state.get_user_next_pick_index()
        if user_next_pick is None:
            return {"availability": {}, "confidence": {}}
        
        picks_until_user = user_next_pick - draft_state.current_pick_index
        available_players = list(draft_state.remaining_players)
        
        # Simple simulation: assume top players by ADP get picked
        likely_gone = self._simulate_picks_until_user(
            available_players, picks_until_user, num_sims
        )
        
        return {
            "picks_until_user": picks_until_user,
            "likely_available": [pid for pid in available_players if pid not in likely_gone],
            "likely_gone": likely_gone,
            "confidence": 0.7  # Placeholder confidence score
        }
    
    def _generate_draft_order(self, num_teams: int, snake: bool) -> List[int]:
        """Generate complete draft order for all rounds"""
        num_rounds = 16  # Standard fantasy football draft
        draft_order = []
        
        for round_num in range(num_rounds):
            if snake and round_num % 2 == 1:  # Odd rounds (0-indexed) reverse
                round_order = list(range(num_teams, 0, -1))
            else:
                round_order = list(range(1, num_teams + 1))
            draft_order.extend(round_order)
        
        return draft_order
    
    def _load_players(self, scoring_mode: ScoringTypeEnum):
        """Load and cache top players by position for performance"""
        # Load only top 300 players to avoid timeout
        players = PlayerCRUD.get_top_players(self.db, scoring_mode, limit=300)
        
        # Cache players
        self.players_cache = {p.id: p for p in players}
        
        # Group by position
        self.position_players = {}
        for pos in PositionEnum:
            self.position_players[pos] = [
                p for p in players if p.position == pos
            ]
            # Sort by projected points descending
            self.position_players[pos].sort(
                key=lambda p: self._get_projected_points(p, scoring_mode) or 0,
                reverse=True
            )
    
    def _initialize_vorp_and_scarcity(self, draft_state: DraftState):
        """Calculate initial VORP and scarcity for all players - lazy initialization"""
        # Initialize replacement levels only for performance
        for pos in PositionEnum:
            self._calculate_replacement_level(draft_state, pos)
        
        # Calculate VORP and scarcity for key positions only initially
        # Other positions will be calculated on-demand
        key_positions = [PositionEnum.QB, PositionEnum.RB, PositionEnum.WR, PositionEnum.TE]
        for pos in key_positions:
            if pos in self.position_players and self.position_players[pos]:
                self._calculate_position_vorp(draft_state, pos)
                self._calculate_position_scarcity(draft_state, pos)
    
    def _update_vorp_and_scarcity(self, draft_state: DraftState, affected_position: PositionEnum) -> Dict[str, Any]:
        """Incrementally update VORP and scarcity after a pick"""
        # Recalculate replacement level for affected position
        self._calculate_replacement_level(draft_state, affected_position)
        
        # Update VORP for remaining players of this position
        vorp_updates = self._calculate_position_vorp(draft_state, affected_position)
        
        # Update scarcity metrics
        scarcity_updates = self._calculate_position_scarcity(draft_state, affected_position)
        
        return {
            "vorp_updates": vorp_updates,
            "scarcity_updates": scarcity_updates
        }
    
    def _calculate_replacement_level(self, draft_state: DraftState, position: PositionEnum):
        """Calculate replacement level for a position"""
        slots_needed = self.ROSTER_REQUIREMENTS[position] * draft_state.num_teams
        replacement_rank = slots_needed + self.BENCH_BUFFER
        drafted_count = draft_state.drafted_count_by_pos[position]
        
        # Get remaining players at position, sorted by projection
        remaining_players = [
            p for p in self.position_players[position]
            if p.id in draft_state.remaining_players
        ]
        
        # Calculate replacement index
        replacement_index = replacement_rank - drafted_count
        
        if replacement_index < len(remaining_players):
            replacement_player = remaining_players[replacement_index]
            replacement_points = self._get_projected_points(replacement_player, draft_state.scoring_mode) or 0
        else:
            replacement_points = 0.0  # Fallback for deep positions
        
        draft_state.replacement_levels[position] = replacement_points
    
    def _calculate_position_vorp(self, draft_state: DraftState, position: PositionEnum) -> Dict[int, float]:
        """Calculate VORP for all remaining players at position"""
        replacement_level = draft_state.replacement_levels.get(position, 0.0)
        vorp_updates = {}
        
        # Ensure position has players
        if position not in self.position_players:
            return vorp_updates
        
        for player in self.position_players[position]:
            if player.id in draft_state.remaining_players:
                projection = self._get_projected_points(player, draft_state.scoring_mode) or 0
                vorp = projection - replacement_level
                draft_state.vorp_cache[player.id] = vorp
                vorp_updates[player.id] = vorp
        
        return vorp_updates
    
    def _calculate_position_scarcity(self, draft_state: DraftState, position: PositionEnum) -> ScarcityMetrics:
        """Calculate scarcity metrics for a position"""
        remaining_players = [
            p for p in self.position_players[position]
            if p.id in draft_state.remaining_players
        ]
        
        if not remaining_players:
            metrics = ScarcityMetrics(
                position=position,
                avg_vorp_remaining=0.0,
                dropoff_at_next_tier=0.0,
                scarcity_score=0.0,
                urgency_flag=False,
                replacement_level=draft_state.replacement_levels[position],
                players_remaining=0
            )
        else:
            # Calculate average VORP of top remaining players
            top_players = remaining_players[:10]  # Top 10 remaining
            avg_vorp = sum(draft_state.vorp_cache.get(p.id, 0) for p in top_players) / len(top_players)
            
            # Calculate tier dropoff
            dropoff = self._calculate_tier_dropoff(remaining_players, draft_state)
            
            # Scarcity score heuristic
            scarcity_score = avg_vorp * math.sqrt(draft_state.num_teams) / max(len(remaining_players), 1)
            urgency_flag = scarcity_score > 2.0 or dropoff > 0.15
            
            metrics = ScarcityMetrics(
                position=position,
                avg_vorp_remaining=avg_vorp,
                dropoff_at_next_tier=dropoff,
                scarcity_score=scarcity_score,
                urgency_flag=urgency_flag,
                replacement_level=draft_state.replacement_levels[position],
                players_remaining=len(remaining_players)
            )
        
        draft_state.scarcity_cache[position] = metrics
        return metrics
    
    def _calculate_tier_dropoff(self, players: List[Player], draft_state: DraftState) -> float:
        """Calculate the largest tier dropoff in remaining players"""
        if len(players) < 2:
            return 0.0
        
        max_dropoff = 0.0
        for i in range(len(players) - 1):
            current_vorp = draft_state.vorp_cache.get(players[i].id, 0)
            next_vorp = draft_state.vorp_cache.get(players[i + 1].id, 0)
            
            if current_vorp > 0:
                dropoff = (current_vorp - next_vorp) / current_vorp
                max_dropoff = max(max_dropoff, dropoff)
        
        return max_dropoff
    
    def _update_team_needs(self, draft_state: DraftState, team_id: int):
        """Update team need scores"""
        roster = draft_state.rosters[team_id]
        
        for pos in PositionEnum:
            target = self.ROSTER_REQUIREMENTS[pos]
            current = roster.positional_counts[pos]
            need = max(0, target - current)
            
            # Weight by scarcity
            scarcity_multiplier = 1.0
            if pos in draft_state.scarcity_cache:
                scarcity_multiplier = 1.0 + draft_state.scarcity_cache[pos].scarcity_score / 10.0
            
            roster.need_scores[pos] = need * scarcity_multiplier
    
    def _advice_best_vorp(self, players: List[Player], draft_state: DraftState) -> List[Dict[str, Any]]:
        """Advice based on highest VORP"""
        players_with_vorp = [
            (p, draft_state.vorp_cache.get(p.id, 0)) for p in players
        ]
        players_with_vorp.sort(key=lambda x: x[1], reverse=True)
        
        return [
            {
                "player_id": p.id,
                "name": p.name,
                "position": p.position.value,
                "vorp": vorp,
                "reason": f"Highest VORP available ({vorp:.1f})",
                "scarcity_flag": draft_state.scarcity_cache.get(p.position, ScarcityMetrics(p.position, 0, 0, 0, False, 0, 0)).urgency_flag
            }
            for p, vorp in players_with_vorp[:5]
        ]
    
    def _advice_fill_need(self, players: List[Player], draft_state: DraftState, team_id: int) -> List[Dict[str, Any]]:
        """Advice based on team needs"""
        roster = draft_state.rosters[team_id]
        
        # Sort players by need score * VORP
        players_with_score = []
        for p in players:
            need_score = roster.need_scores.get(p.position, 0)
            vorp = draft_state.vorp_cache.get(p.id, 0)
            combined_score = need_score * vorp
            players_with_score.append((p, combined_score, need_score, vorp))
        
        players_with_score.sort(key=lambda x: x[1], reverse=True)
        
        return [
            {
                "player_id": p.id,
                "name": p.name,
                "position": p.position.value,
                "vorp": vorp,
                "need_score": need_score,
                "reason": f"Fills {p.position.value} need (score: {need_score:.1f})",
                "scarcity_flag": draft_state.scarcity_cache.get(p.position, ScarcityMetrics(p.position, 0, 0, 0, False, 0, 0)).urgency_flag
            }
            for p, _, need_score, vorp in players_with_score[:5]
        ]
    
    def _advice_upside(self, players: List[Player], draft_state: DraftState) -> List[Dict[str, Any]]:
        """Advice based on upside/ceiling"""
        # For now, use VORP as proxy for upside
        return self._advice_best_vorp(players, draft_state)
    
    def _advice_robust(self, players: List[Player], draft_state: DraftState, team_id: int) -> List[Dict[str, Any]]:
        """Balanced advice considering VORP, scarcity, and needs"""
        roster = draft_state.rosters[team_id]
        
        players_with_score = []
        for p in players:
            vorp = draft_state.vorp_cache.get(p.id, 0)
            need_score = roster.need_scores.get(p.position, 0)
            scarcity = draft_state.scarcity_cache.get(p.position, ScarcityMetrics(p.position, 0, 0, 0, False, 0, 0))
            
            # Robust scoring: VORP + need bonus + scarcity bonus
            robust_score = vorp + (need_score * 2) + (scarcity.scarcity_score * 1.5)
            players_with_score.append((p, robust_score, vorp, need_score, scarcity))
        
        players_with_score.sort(key=lambda x: x[1], reverse=True)
        
        return [
            {
                "player_id": p.id,
                "name": p.name,
                "position": p.position.value,
                "vorp": vorp,
                "robust_score": score,
                "reason": f"Best value considering VORP, need, and scarcity",
                "scarcity_flag": scarcity.urgency_flag
            }
            for p, score, vorp, need_score, scarcity in players_with_score[:5]
        ]
    
    def _simulate_picks_until_user(self, available_players: List[int], picks_until: int, num_sims: int) -> Set[int]:
        """Simulate which players will likely be gone by user's next pick"""
        # Simple simulation: assume players get picked by ADP order
        players_by_adp = []
        for pid in available_players:
            player = self.players_cache[pid]
            adp = self._get_adp(player) or 999
            players_by_adp.append((pid, adp))
        
        players_by_adp.sort(key=lambda x: x[1])  # Sort by ADP
        
        # Take top picks_until players as likely gone
        likely_gone = set()
        for i in range(min(picks_until, len(players_by_adp))):
            likely_gone.add(players_by_adp[i][0])
        
        return likely_gone
    
    def _get_projected_points(self, player: Player, scoring_mode: ScoringTypeEnum) -> Optional[float]:
        """Get projected points for player based on scoring mode"""
        if scoring_mode == ScoringTypeEnum.PPR:
            return player.projected_points_ppr
        elif scoring_mode == ScoringTypeEnum.HALF_PPR:
            return player.projected_points_half_ppr
        else:
            return player.projected_points_standard
    
    def _get_adp(self, player: Player) -> Optional[float]:
        """Get ADP for player"""
        return player.adp_ppr or player.adp_half_ppr or player.adp_standard
    
    def ensure_vorp_calculated(self, draft_state: DraftState, position: PositionEnum):
        """Ensure VORP is calculated for a position (lazy loading)"""
        if position not in draft_state.scarcity_cache:
            # Calculate missing VORP and scarcity for this position
            if position not in draft_state.replacement_levels:
                self._calculate_replacement_level(draft_state, position)
            self._calculate_position_vorp(draft_state, position)
            self._calculate_position_scarcity(draft_state, position)

# Import time module
import time
