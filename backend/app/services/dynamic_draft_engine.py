"""
Dynamic VORP and Scarcity Engine for Live Fantasy Football Drafts

This module implements incremental VORP calculation, positional scarcity analysis,
and draft state management with real-time updates as picks are made.
"""

import logging
import math
import uuid
from typing import Dict, List, Set, Optional, Any, Tuple
from dataclasses import dataclass, field
import numpy as np
import random
from datetime import datetime

from sqlalchemy.orm import Session
from app.data.models import Player, PositionEnum, ScoringTypeEnum
from app.services.plackett_luce_calibrator import PlackettLuceCalibrator
from app.data.crud import PlayerCRUD

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
            return -1  # Draft complete indicator
        return self.draft_order[self.current_pick_index]
    
    def is_draft_complete(self) -> bool:
        """Check if the draft is complete"""
        return self.current_pick_index >= len(self.draft_order)
    
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
        self.active_drafts: Dict[str, DraftState] = {}
        self.players_cache: Dict[int, Player] = {}
        self.position_players: Dict[PositionEnum, List[Player]] = {}
        self.plackett_luce_calibrator = None  # Will be initialized when needed
        self.draft_learning_data = {}  # Store learning data from completed drafts
        self._load_players_cache()
        self._load_draft_learning_data()
    
    def _load_players_cache(self):
        """Load and cache all players for performance"""
        try:
            # Load all players using static method
            from app.data.models import ScoringTypeEnum
            players = PlayerCRUD.get_all_players(self.db, ScoringTypeEnum.HALF_PPR)
            
            # Check if database is empty
            if not players:
                logger.warning("No players found in database - creating empty cache")
                self.players_cache = {}
                self.position_players = {pos: [] for pos in PositionEnum}
                return
            
            # Cache players by ID
            self.players_cache = {p.id: p for p in players}
            
            # Group players by position
            self.position_players = {}
            for pos in PositionEnum:
                self.position_players[pos] = [
                    p for p in players if p.position == pos
                ]
            
            logger.info(f"Loaded {len(players)} players into cache")
        except Exception as e:
            logger.error(f"Failed to load players cache: {e}")
            # Initialize empty cache as fallback
            self.players_cache = {}
            self.position_players = {pos: [] for pos in PositionEnum}
    
    def _load_draft_learning_data(self):
        """Load draft learning data from completed drafts"""
        try:
            import json
            from pathlib import Path
            
            learning_file = Path("draft_learning_data.json")
            if learning_file.exists():
                with open(learning_file, 'r') as f:
                    self.draft_learning_data = json.load(f)
                logger.info(f"Loaded draft learning data: {len(self.draft_learning_data)} completed drafts")
            else:
                self.draft_learning_data = {}
        except Exception as e:
            logger.error(f"Failed to load draft learning data: {e}")
            self.draft_learning_data = {}
    
    def _save_draft_learning_data(self):
        """Save draft learning data to disk"""
        try:
            import json
            from pathlib import Path
            
            learning_file = Path("draft_learning_data.json")
            with open(learning_file, 'w') as f:
                json.dump(self.draft_learning_data, f, indent=2)
            logger.info("Saved draft learning data")
        except Exception as e:
            logger.error(f"Failed to save draft learning data: {e}")
    
    def record_completed_draft(self, draft_state: DraftState):
        """Record a completed draft for learning purposes"""
        try:
            draft_id = f"draft_{len(self.draft_learning_data)}"
            
            # Extract pick data for learning
            pick_data = []
            for pick in draft_state.picks:
                player = self.players_cache.get(pick.player_id)
                if player:
                    pick_data.append({
                        "pick_number": pick.pick_index,
                        "player_id": pick.player_id,
                        "player_name": player.name,
                        "position": player.position.value,
                        "adp": self._get_adp(player),
                        "ecr": player.expert_consensus_rank,
                        "team_id": pick.team_id
                    })
            
            # Store learning data
            self.draft_learning_data[draft_id] = {
                "num_teams": draft_state.num_teams,
                "scoring_mode": draft_state.scoring_mode.value,
                "picks": pick_data,
                "completed_at": str(datetime.now())
            }
            
            # Update ADP adjustments based on actual picks
            self._update_adp_adjustments(pick_data)
            
            # Save to disk
            self._save_draft_learning_data()
            
            logger.info(f"Recorded completed draft with {len(pick_data)} picks")
        except Exception as e:
            logger.error(f"Failed to record completed draft: {e}")
    
    def _update_adp_adjustments(self, pick_data):
        """Update ADP adjustments based on actual draft results"""
        try:
            # Track how players are actually being drafted vs their ADP
            for pick in pick_data:
                player_id = pick["player_id"]
                actual_pick = pick["pick_number"]
                adp = pick["adp"]
                
                if adp and adp > 0:
                    # Calculate adjustment factor
                    pick_diff = actual_pick - adp
                    
                    # Store adjustment (positive = drafted later, negative = drafted earlier)
                    if "adp_adjustments" not in self.draft_learning_data:
                        self.draft_learning_data["adp_adjustments"] = {}
                    
                    if str(player_id) not in self.draft_learning_data["adp_adjustments"]:
                        self.draft_learning_data["adp_adjustments"][str(player_id)] = []
                    
                    self.draft_learning_data["adp_adjustments"][str(player_id)].append(pick_diff)
                    
                    # Keep only last 10 drafts per player for rolling average
                    if len(self.draft_learning_data["adp_adjustments"][str(player_id)]) > 10:
                        self.draft_learning_data["adp_adjustments"][str(player_id)] = \
                            self.draft_learning_data["adp_adjustments"][str(player_id)][-10:]
        except Exception as e:
            logger.error(f"Failed to update ADP adjustments: {e}")
    
    def _get_learned_adp_adjustment(self, player: Player) -> float:
        """Get learned ADP adjustment for a player based on historical drafts"""
        try:
            if "adp_adjustments" not in self.draft_learning_data:
                return 0.0
            
            adjustments = self.draft_learning_data["adp_adjustments"].get(str(player.id), [])
            if adjustments:
                # Return average adjustment
                return sum(adjustments) / len(adjustments)
            return 0.0
        except Exception as e:
            logger.error(f"Failed to get learned ADP adjustment: {e}")
            return 0.0

    def create_draft(self, num_teams: int, draft_spot: int, scoring_mode: ScoringTypeEnum) -> DraftState:
        """Create a new draft with initial state"""
        draft_id = f"draft_{uuid.uuid4().hex[:8]}"
        
        # Generate draft order
        draft_order = self._generate_draft_order(num_teams, snake=True)
        
        # Load and cache players (already done in __init__, but ensure fresh data)
        self._load_players_cache()
        
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
        
        logger.info(f"Draft created - Initial state: pick_index={draft_state.current_pick_index}, current_team={draft_state.get_current_team_id()}, user_spot={draft_spot}")
        
        logger.info(f"Created draft {draft_id} with {num_teams} teams, user at spot {draft_spot}")
        return draft_state
    
    def make_pick(self, draft_state: DraftState, player_id: int) -> Dict[str, Any]:
        """Make a pick and update all dynamic metrics"""
        # Validate draft state
        if draft_state.is_draft_complete():
            raise ValueError("Draft is already complete")
        
        # Validate player availability with detailed logging
        if player_id not in draft_state.remaining_players:
            logger.error(f"Player {player_id} not in remaining_players set (size: {len(draft_state.remaining_players)})")
            logger.error(f"Already drafted players: {[p.player_id for p in draft_state.picks[-10:]]}")  # Last 10 picks
            raise ValueError(f"Player {player_id} not available")
        
        # Validate player exists in cache
        if player_id not in self.players_cache:
            raise ValueError(f"Player {player_id} not found in players cache")
        
        current_team_id = draft_state.get_current_team_id()
        if current_team_id == -1:
            raise ValueError("No current team - draft may be complete")
        
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
        
        # Update draft state atomically to prevent inconsistency
        try:
            draft_state.picks.append(pick)
            draft_state.remaining_players.discard(player_id)  # Use discard instead of remove
            draft_state.rosters[current_team_id].picks.append(player_id)
            
            # Double-check consistency
            if player_id in draft_state.remaining_players:
                logger.error(f"CONSISTENCY ERROR: Player {player_id} still in remaining_players after pick")
                draft_state.remaining_players.discard(player_id)  # Force removal
                
        except Exception as e:
            logger.error(f"Error updating draft state for player {player_id}: {e}")
            # Rollback if possible
            if pick in draft_state.picks:
                draft_state.picks.remove(pick)
            raise
        
        # Update positional counts
        player = self.players_cache[player_id]
        
        # Handle both Player objects and dict representations
        if hasattr(player, 'position'):
            # Player object
            player_position = player.position
            player_name = player.name
        else:
            # Dictionary representation
            player_position = PositionEnum(player['position']) if isinstance(player['position'], str) else player['position']
            player_name = player['name']
        
        draft_state.drafted_count_by_pos[player_position] += 1
        draft_state.rosters[current_team_id].positional_counts[player_position] += 1
        
        # Advance pick
        draft_state.current_pick_index += 1
        
        # Incremental VORP and scarcity update
        updated_metrics = self._update_vorp_and_scarcity(draft_state, player_position)
        
        # Update team needs
        self._update_team_needs(draft_state, current_team_id)
        
        logger.info(f"Pick made: Team {current_team_id} selected {player_name} ({player_position})")
        
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
        elif mode == "bot_realistic":
            return self._advice_bot_realistic(available_players, draft_state, team_id)
        elif mode == "draft_advantage":
            return self._advice_draft_advantage(available_players, draft_state, team_id)
        elif mode == "plackett_luce":
            return self._advice_plackett_luce(available_players, draft_state, team_id)
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
                # Use projected_points directly from player model if available
                projection = player.projected_points or self._get_projected_points(player, draft_state.scoring_mode) or 0
                vorp = max(0, projection - replacement_level)  # Ensure VORP is not negative
                draft_state.vorp_cache[player.id] = vorp
                vorp_updates[player.id] = vorp
        
        return vorp_updates
    
    def _calculate_position_scarcity(self, draft_state: DraftState, position: PositionEnum) -> Dict[str, Any]:
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
        return {"scarcity_metrics": metrics}
    
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
    
    def _advice_bot_realistic(self, players: List[Player], draft_state: DraftState, team_id: int) -> List[Dict[str, Any]]:
        """Realistic bot advice using ADP/ECR and positional need with nonlinear probability"""
        roster = draft_state.rosters[team_id]
        current_pick = draft_state.current_pick_index + 1
        current_round = (draft_state.current_pick_index // draft_state.num_teams) + 1
        
        # Calculate realistic bot scores for each player
        players_with_score = []
        for p in players:
            # Get ADP/ECR (lower is better, so invert for scoring)
            base_adp = self._get_adp(p)
            learned_adjustment = self._get_learned_adp_adjustment(p)
            adp = base_adp + learned_adjustment if base_adp else None  # Apply learned adjustment
            ecr = p.expert_consensus_rank or 999
            
            # Use the better of ADP or ECR as primary ranking, but heavily weight ADP
            # ADP is more important as it reflects actual draft behavior
            if adp and adp < 999:
                primary_rank = adp
                # If ECR exists and is significantly better, blend them (80% ADP, 20% ECR)
                if ecr and ecr < 999 and ecr < adp * 0.7:
                    primary_rank = adp * 0.8 + ecr * 0.2
            else:
                primary_rank = ecr or 999
        
            # STRICT ADP ADHERENCE: Heavily penalize picks that deviate too much from ADP
            pick_vs_rank_diff = current_pick - primary_rank
            
            # If player is being drafted WAY too early (more than 2 rounds), severely penalize
            if pick_vs_rank_diff < -24:  # More than 2 rounds early (12 picks per round * 2)
                value_multiplier = 0.01  # 99% penalty for reaching too early
            elif pick_vs_rank_diff < -12:  # More than 1 round early
                value_multiplier = 0.1   # 90% penalty for reaching 1+ rounds early
            elif pick_vs_rank_diff <= 0:
                # Player is going at or slightly before their rank - normal probability
                value_multiplier = 1.0
            else:
                # Player is falling - exponential increase in value (but more conservative)
                # Formula: 1 + (diff^1.5 / 15) gives moderate growth
                value_multiplier = 1.0 + (pick_vs_rank_diff ** 1.5) / 15.0
                value_multiplier = min(value_multiplier, 20.0)  # Cap at 20x value (reduced from 50x)
        
            # Base score from rank (higher for better ranks)
            base_score = max(0, 400 - primary_rank) * value_multiplier
            
            # Round-based weighting (early rounds follow consensus more)
            if current_round <= 3:
                consensus_weight = 0.95  # 95% consensus in early rounds
                need_weight = 0.05
            elif current_round <= 6:
                consensus_weight = 0.85  # 85% consensus in mid rounds
                need_weight = 0.15
            else:
                consensus_weight = 0.70  # 70% consensus in late rounds
                need_weight = 0.30
            
            # Get position - handle both Player objects and dicts
            if hasattr(p, 'position'):
                player_position = p.position
            else:
                player_position = PositionEnum(p['position']) if isinstance(p.get('position'), str) else p.get('position')
            
            # Positional need score
            need_score = roster.need_scores.get(player_position, 0)
            need_bonus = need_score * 30  # Need bonus
            
            # Position scarcity (only in later rounds)
            scarcity_bonus = 0
            if current_round > 6 and player_position in draft_state.scarcity_cache:
                scarcity_metrics = draft_state.scarcity_cache[player_position]
                if scarcity_metrics.urgency_flag:
                    scarcity_bonus = 15
            
            # Final weighted score
            final_score = (base_score * consensus_weight) + (need_bonus * need_weight) + scarcity_bonus
            
            # Minimal randomness for falling players, more for others
            import random
            if pick_vs_rank_diff > 5:  # Player falling significantly
                randomness = random.uniform(0.98, 1.02)  # Almost no randomness
            elif current_round <= 3:
                randomness = random.uniform(0.95, 1.05)  # ±5% in early rounds
            else:
                randomness = random.uniform(0.85, 1.15)  # ±15% in later rounds
            
            final_score *= randomness
            
            players_with_score.append((p, final_score, adp, ecr, need_score, primary_rank, value_multiplier, pick_vs_rank_diff))
        
        # Sort by final score (highest first)
        players_with_score.sort(key=lambda x: x[1], reverse=True)
        
        # Return top 5 recommendations
        recommendations = []
        for p, score, adp, ecr, need, rank, multiplier, diff in players_with_score[:5]:
            reason_parts = []
            
            if diff > 10:
                reason_parts.append(f"STEAL! Falling {diff} picks")
            elif diff > 5:
                reason_parts.append(f"Great value, falling {diff} picks")
            elif current_round <= 3:
                reason_parts.append(f"follows consensus (rank {rank})")
            elif need > 0:
                reason_parts.append(f"fills {player_position.value if hasattr(player_position, 'value') else player_position} need")
            
            if rank <= 12:  # Top round
                reason_parts.append("elite tier")
            elif rank <= 36:  # Top 3 rounds
                reason_parts.append("solid starter")
            
            reason = f"Bot pick: {', '.join(reason_parts) if reason_parts else 'best available'}"
            
            # Get player name and id - handle both Player objects and dicts
            player_id = p.id if hasattr(p, 'id') else p.get('id')
            player_name = p.name if hasattr(p, 'name') else p.get('name')
            position_value = player_position.value if hasattr(player_position, 'value') else player_position
            
            recommendations.append({
                "player_id": player_id,
                "player_name": player_name,
                "name": player_name,  # For compatibility
                "position": position_value,
                "score": round(score, 1),
                "adp": adp,
                "ecr": ecr,
                "consensus_rank": rank,
                "value_multiplier": round(multiplier, 1),
                "pick_vs_rank_diff": diff,
                "need_score": need,
                "round": current_round,
                "reason": reason,
                "scarcity_flag": p.position in draft_state.scarcity_cache and draft_state.scarcity_cache[p.position].urgency_flag
            })
        
        return recommendations
    
    def _calculate_draft_advantage_score(self, player: Player, draft_state: DraftState, user_team_id: int) -> Dict[str, Any]:
        """
        Calculate Draft Advantage Score (DAS) - the strategic advantage of picking a player now
        versus waiting until the user's next opportunity to draft that position.
        
        Formula: Player Value Now - Expected Replacement Value at Next Opportunity
        """
        # Get user's next pick opportunities
        user_next_picks = self._get_user_next_picks(draft_state, user_team_id)
        if not user_next_picks:
            return {"das": 0, "reason": "No future picks available", "replacement_player": None}
        
        # Get current player's projected points (with fallback)
        current_player_points = self._get_projected_points(player, draft_state.scoring_mode)
        if current_player_points is None:
            # Fallback to VORP or a reasonable default
            current_player_points = draft_state.vorp_cache.get(player.id, 0) + 10.0  # Base replacement + VORP
        
        # Find next opportunity to draft this position
        next_pick_for_position = None
        for pick_index in user_next_picks:
            picks_until_next = pick_index - draft_state.current_pick_index
            if picks_until_next > 0:
                next_pick_for_position = pick_index
                break
        
        if not next_pick_for_position:
            # This is user's last chance - high advantage
            return {
                "das": current_player_points * 0.5,  # 50% of points as advantage
                "reason": "Last chance to draft this position",
                "replacement_player": None,
                "picks_until_next": 999
            }
        
        picks_until_next = next_pick_for_position - draft_state.current_pick_index
        
        # Simulate what players will be taken before user's next pick
        available_at_position = [
            p for pid in draft_state.remaining_players 
            if (p := self.players_cache.get(pid)) and p.position == player.position
        ]
        
        # Sort by ADP (most likely to be drafted first)
        available_at_position.sort(key=lambda p: self._get_adp(p) or 999)
        
        # Estimate how many players at this position will be taken
        # Assume roughly 1 player per position per 12 picks (realistic draft distribution)
        position_picks_expected = max(1, picks_until_next // 12)
        
        # Find expected replacement player
        replacement_player = None
        replacement_points = 0
        
        if len(available_at_position) > position_picks_expected:
            replacement_player = available_at_position[position_picks_expected]
            replacement_points = self._get_projected_points(replacement_player, draft_state.scoring_mode)
            if replacement_points is None:
                # Fallback for replacement player
                replacement_points = draft_state.vorp_cache.get(replacement_player.id, 0) + 8.0  # Lower baseline
        else:
            # All good players at position will be gone - use baseline replacement
            replacement_points = current_player_points * 0.6  # 60% of current player
        
        # Calculate Draft Advantage Score
        das = current_player_points - replacement_points
        
        # Debug logging
        logger.debug(f"DAS calculation for {player.name}: current={current_player_points}, replacement={replacement_points}, das={das}")
        
        # Add context-based adjustments
        if picks_until_next <= 12:  # Next pick is soon
            das *= 0.8  # Lower advantage since next pick is close
        elif picks_until_next >= 24:  # Long wait until next pick
            das *= 1.3  # Higher advantage since long wait
        
        return {
            "das": round(das, 1),
            "reason": f"vs. expected replacement in {picks_until_next} picks",
            "replacement_player": replacement_player.name if replacement_player else "Baseline replacement",
            "replacement_points": round(replacement_points, 1),
            "picks_until_next": picks_until_next,
            "current_points": round(current_player_points, 1)
        }
    
    def _get_user_next_picks(self, draft_state: DraftState, user_team_id: int) -> List[int]:
        """Get list of user's future pick indices"""
        user_picks = []
        for i, team_id in enumerate(draft_state.draft_order):
            if team_id == user_team_id and i > draft_state.current_pick_index:
                user_picks.append(i)
        return user_picks[:3]  # Next 3 picks for efficiency
    
    def _advice_draft_advantage(self, players: List[Player], draft_state: DraftState, team_id: int) -> List[Dict[str, Any]]:
        """Strategic advice using Draft Advantage Score (DAS) - pick-aware value calculation"""
        roster = draft_state.rosters[team_id]
        
        # Calculate DAS for each available player
        players_with_das = []
        for p in players:
            das_info = self._calculate_draft_advantage_score(p, draft_state, team_id)
            
            # Add positional need consideration
            need_score = roster.need_scores.get(p.position, 0)
            need_bonus = need_score * 5.0  # 5 points per need level
            
            # Add scarcity urgency
            scarcity_bonus = 0
            if p.position in draft_state.scarcity_cache:
                scarcity_metrics = draft_state.scarcity_cache[p.position]
                if scarcity_metrics.urgency_flag:
                    scarcity_bonus = 10.0  # 10 point bonus for urgent positions
            
            # Base strategic score
            strategic_score = das_info["das"] + need_bonus + scarcity_bonus

            # Starting lineup awareness: penalize recommending positions already filled at starter level
            current_round = (draft_state.current_pick_index // draft_state.num_teams) + 1
            starting_requirements = {
                PositionEnum.QB: self.ROSTER_REQUIREMENTS.get(PositionEnum.QB, 1),
                PositionEnum.RB: self.ROSTER_REQUIREMENTS.get(PositionEnum.RB, 2),
                PositionEnum.WR: self.ROSTER_REQUIREMENTS.get(PositionEnum.WR, 2),
                PositionEnum.TE: self.ROSTER_REQUIREMENTS.get(PositionEnum.TE, 1),
            }
            rb_wr_te_required_total = (
                starting_requirements.get(PositionEnum.RB, 0)
                + starting_requirements.get(PositionEnum.WR, 0)
                + starting_requirements.get(PositionEnum.TE, 0)
                + 1  # FLEX slot
            )
            rb_wr_te_have = (
                roster.positional_counts.get(PositionEnum.RB, 0)
                + roster.positional_counts.get(PositionEnum.WR, 0)
                + roster.positional_counts.get(PositionEnum.TE, 0)
            )
            pool_starters_remaining = max(0, rb_wr_te_required_total - rb_wr_te_have)

            # Determine if position starter already filled
            pos_starter_filled = (
                roster.positional_counts.get(p.position, 0) >= starting_requirements.get(p.position, 0)
            )

            # Apply early-round penalty when there are still starting slots to fill
            if pool_starters_remaining > 0 and pos_starter_filled and current_round <= 8:
                # Strong penalty for TE once a TE is already drafted (user feedback)
                if p.position == PositionEnum.TE:
                    strategic_score *= 0.15
                else:
                    strategic_score *= 0.5
            
            players_with_das.append((p, strategic_score, das_info, need_score))
        
        # Sort by strategic score (highest first)
        players_with_das.sort(key=lambda x: x[1], reverse=True)
        
        # Return top 5 strategic recommendations
        recommendations = []
        for p, score, das_info, need in players_with_das[:5]:
            # Build strategic reasoning
            reason_parts = []
            if das_info["das"] > 10:
                reason_parts.append(f"High draft advantage ({das_info['das']})")
            if need > 0:
                reason_parts.append(f"Fills {p.position.value} need")
            if das_info["picks_until_next"] > 20:
                reason_parts.append("Long wait until next pick")
            if p.position in draft_state.scarcity_cache and draft_state.scarcity_cache[p.position].urgency_flag:
                reason_parts.append("Position becoming scarce")
            
            if not reason_parts:
                reason_parts.append("Best strategic value")
            
            reason = f"Strategic pick: {', '.join(reason_parts)}"
            
            recommendations.append({
                "player_id": p.id,
                "player_name": p.name,
                "name": p.name,  # For compatibility
                "position": p.position.value,
                "das": das_info["das"],
                "strategic_score": round(score, 1),
                "current_points": das_info.get("current_points", 0),
                "replacement_points": das_info.get("replacement_points", 0),
                "replacement_player": das_info.get("replacement_player", "Unknown"),
                "picks_until_next": das_info.get("picks_until_next", 0),
                "need_score": need,
                "reason": reason,
                "das_reason": das_info["reason"],
                "scarcity_flag": p.position in draft_state.scarcity_cache and draft_state.scarcity_cache[p.position].urgency_flag
            })
        
        return recommendations
    
    def _advice_plackett_luce(self, players: List[Player], draft_state: DraftState, team_id: int) -> List[Dict[str, Any]]:
        """
        Plackett-Luce calibrated bot advice using statistically calibrated utilities.
        This produces the most realistic bot picks that match real ADP distributions.
        """
        # For now, fallback to the improved bot_realistic advice until calibration is moved to startup
        # TODO: Move Plackett-Luce calibration to server startup or background process
        logger.debug("Using bot_realistic fallback instead of Plackett-Luce to avoid blocking")
        return self._advice_bot_realistic(players, draft_state, team_id)
        
        roster = draft_state.rosters[team_id]
        current_pick = draft_state.current_pick_index + 1
        current_round = (draft_state.current_pick_index // draft_state.num_teams) + 1
        
        # Calculate Plackett-Luce probabilities for each player
        players_with_score = []
        for p in players:
            # Get calibrated utility
            base_utility = self.plackett_luce_calibrator.get_calibrated_utility(p.id)
            
            # Add positional need adjustment
            need_score = roster.need_scores.get(p.position, 0)
            need_adjustment = np.log(1.0 + need_score * 0.3)  # Logarithmic need adjustment
            
            # Add scarcity adjustment for later rounds
            scarcity_adjustment = 0.0
            if current_round > 6 and p.position in draft_state.scarcity_cache:
                scarcity_metrics = draft_state.scarcity_cache[p.position]
                if scarcity_metrics.urgency_flag:
                    scarcity_adjustment = 0.5
            
            # Final utility
            final_utility = base_utility + need_adjustment + scarcity_adjustment
            
            # Convert utility to probability (softmax will be applied later)
            players_with_score.append((p, final_utility, base_utility, need_score))
        
        # Apply softmax to get probabilities
        utilities = np.array([score for _, score, _, _ in players_with_score])
        if len(utilities) > 0:
            # Apply temperature scaling (lower temperature = more deterministic)
            temperature = 1.0 if current_round <= 3 else 1.2
            exp_utilities = np.exp(utilities / temperature)
            probabilities = exp_utilities / np.sum(exp_utilities)
        else:
            probabilities = np.array([])
        
        # Sort by probability (highest first)
        if len(probabilities) > 0:
            sorted_indices = np.argsort(probabilities)[::-1]
            sorted_players = [(players_with_score[i], probabilities[i]) for i in sorted_indices]
        else:
            sorted_players = [(item, 0.0) for item in players_with_score]
        
        # Return top 5 recommendations with Plackett-Luce reasoning
        recommendations = []
        for i, ((p, utility, base_utility, need), probability) in enumerate(sorted_players[:5]):
            # Get ADP for context
            adp = self._get_adp(p) or 999
            pick_vs_adp = current_pick - adp
            
            # Build reasoning
            reason_parts = []
            if probability > 0.3:
                reason_parts.append("high probability pick")
            elif probability > 0.1:
                reason_parts.append("likely pick")
            else:
                reason_parts.append("possible pick")
            
            if pick_vs_adp > 5:
                reason_parts.append(f"great value (ADP {adp})")
            elif need > 0:
                reason_parts.append(f"fills {p.position.value} need")
            
            reason = f"Calibrated pick: {', '.join(reason_parts)}"
            
            recommendations.append({
                "player_id": p.id,
                "player_name": p.name,
                "name": p.name,  # For compatibility
                "position": p.position.value,
                "utility": round(utility, 3),
                "probability": round(probability, 3),
                "base_utility": round(base_utility, 3),
                "adp": adp,
                "pick_vs_adp": pick_vs_adp,
                "need_score": need,
                "round": current_round,
                "reason": reason,
                "scarcity_flag": p.position in draft_state.scarcity_cache and draft_state.scarcity_cache[p.position].urgency_flag
            })
        
        return recommendations
    
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

            # Starting lineup awareness penalty (avoid recommending extra TE early if TE starter filled)
            starting_requirements = {
                PositionEnum.QB: self.ROSTER_REQUIREMENTS.get(PositionEnum.QB, 1),
                PositionEnum.RB: self.ROSTER_REQUIREMENTS.get(PositionEnum.RB, 2),
                PositionEnum.WR: self.ROSTER_REQUIREMENTS.get(PositionEnum.WR, 2),
                PositionEnum.TE: self.ROSTER_REQUIREMENTS.get(PositionEnum.TE, 1),
            }
            current_round = (draft_state.current_pick_index // draft_state.num_teams) + 1
            pos_starter_filled = (
                roster.positional_counts.get(p.position, 0) >= starting_requirements.get(p.position, 0)
            )
            rb_wr_te_required_total = (
                starting_requirements.get(PositionEnum.RB, 0)
                + starting_requirements.get(PositionEnum.WR, 0)
                + starting_requirements.get(PositionEnum.TE, 0)
                + 1
            )
            rb_wr_te_have = (
                roster.positional_counts.get(PositionEnum.RB, 0)
                + roster.positional_counts.get(PositionEnum.WR, 0)
                + roster.positional_counts.get(PositionEnum.TE, 0)
            )
            pool_starters_remaining = max(0, rb_wr_te_required_total - rb_wr_te_have)
            if pool_starters_remaining > 0 and pos_starter_filled and current_round <= 8:
                if p.position == PositionEnum.TE:
                    robust_score *= 0.15
                else:
                    robust_score *= 0.5
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
        points = None
        if scoring_mode == ScoringTypeEnum.PPR:
            points = player.projected_points_ppr
        elif scoring_mode == ScoringTypeEnum.HALF_PPR:
            points = player.projected_points_half_ppr
        else:
            points = player.projected_points_standard
        
        # If no projected points, try other scoring modes as fallback
        if points is None:
            points = (player.projected_points_ppr or 
                     player.projected_points_half_ppr or 
                     player.projected_points_standard)
        
        return points
    
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
