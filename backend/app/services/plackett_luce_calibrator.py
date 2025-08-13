"""
Plackett-Luce / Softmax-based bot calibration for realistic ADP matching.

This module implements iterative Monte-Carlo calibration to ensure bot picks
match real ADP distributions using statistically sound probability models.
"""

import numpy as np
import logging
from typing import Dict, List, Tuple, Optional, Callable
from collections import defaultdict
import asyncio
from concurrent.futures import ThreadPoolExecutor
import random

from app.data.models import PositionEnum, ScoringTypeEnum, Player

logger = logging.getLogger(__name__)


class PlackettLuceCalibrator:
    """
    Calibrates bot pick utilities using Plackett-Luce model to match target ADP.
    
    Uses iterative simulation-based fitting to find utilities that produce
    simulated ADP matching real-world ADP distributions.
    """
    
    def __init__(self, players: List[Player], num_simulations: int = 500):
        self.players = players
        self.calibrated_utilities = {}  # player_id -> utility
        self.target_adp = {}  # player_id -> target_adp
        self.num_simulations = num_simulations
        self.convergence_history = []
        
    def set_target_adp(self, players: List[Player]):
        """Set target ADP from player data"""
        self.target_adp = {}
        for player in players:
            # Use best available ADP as target
            adp = self.draft_engine._get_adp(player)
            if adp and adp < 300:  # Only calibrate for draftable players
                self.target_adp[player.id] = adp
        
        logger.info(f"Set target ADP for {len(self.target_adp)} players")
    
    def initialize_utilities(self, players: List[Player]) -> np.ndarray:
        """Initialize utilities from player projections and ADP"""
        utilities = []
        player_ids = []
        
        for player in players:
            if player.id in self.target_adp:
                # Initialize utility inversely related to ADP (lower ADP = higher utility)
                target_adp = self.target_adp[player.id]
                base_utility = np.log(max(1.0, 300.0 - target_adp))
                
                # Add small random noise to break ties
                base_utility += np.random.normal(0, 0.1)
                
                utilities.append(base_utility)
                player_ids.append(player.id)
        
        return np.array(utilities), player_ids
    
    def simulate_draft_batch(self, utilities: np.ndarray, player_ids: List[int], 
                           num_sims: int, num_teams: int = 12, 
                           scoring_mode: ScoringTypeEnum = ScoringTypeEnum.PPR) -> Dict[int, float]:
        """
        Simulate a batch of drafts using current utilities.
        Returns simulated ADP for each player.
        """
        pick_records = defaultdict(list)  # player_id -> [pick_positions]
        
        for sim in range(num_sims):
            sim_picks = self._simulate_single_draft(utilities, player_ids, num_teams, scoring_mode)
            for player_id, pick_pos in sim_picks.items():
                pick_records[player_id].append(pick_pos)
        
        # Calculate simulated ADP (mean pick position)
        simulated_adp = {}
        for player_id in player_ids:
            if player_id in pick_records and pick_records[player_id]:
                simulated_adp[player_id] = np.mean(pick_records[player_id])
            else:
                # Player not drafted in any simulation
                simulated_adp[player_id] = 999.0
        
        return simulated_adp
    
    def _simulate_single_draft(self, utilities: np.ndarray, player_ids: List[int], 
                             num_teams: int, scoring_mode: ScoringTypeEnum) -> Dict[int, int]:
        """
        Simulate a single draft using Plackett-Luce sampling.
        Returns player_id -> pick_position mapping.
        """
        # Create utility lookup
        utility_map = dict(zip(player_ids, utilities))
        
        # Initialize draft state
        available_players = set(player_ids)
        team_rosters = {i: {"picks": [], "positional_counts": defaultdict(int)} for i in range(1, num_teams + 1)}
        pick_results = {}
        
        # Generate snake draft order
        draft_order = []
        for round_num in range(16):  # 16 rounds
            if round_num % 2 == 0:
                draft_order.extend(range(1, num_teams + 1))
            else:
                draft_order.extend(range(num_teams, 0, -1))
        
        # Simulate each pick
        for pick_idx, team_id in enumerate(draft_order):
            if not available_players:
                break
                
            # Get team's positional needs
            roster = team_rosters[team_id]
            need_multipliers = self._calculate_positional_needs(roster, pick_idx, num_teams)
            
            # Calculate pick probabilities using Plackett-Luce
            pick_probs = self._calculate_pick_probabilities(
                available_players, utility_map, need_multipliers, pick_idx
            )
            
            # Sample player using softmax probabilities
            selected_player = self._softmax_sample(pick_probs)
            
            if selected_player:
                # Record pick
                pick_results[selected_player] = pick_idx + 1
                available_players.remove(selected_player)
                
                # Update team roster
                player = self.draft_engine.players_cache.get(selected_player)
                if player:
                    roster["picks"].append(selected_player)
                    roster["positional_counts"][player.position] += 1
        
        return pick_results
    
    def _calculate_positional_needs(self, roster: Dict, pick_idx: int, num_teams: int) -> Dict[int, float]:
        """Calculate positional need multipliers for team"""
        current_round = (pick_idx // num_teams) + 1
        need_multipliers = {}
        
        # Standard roster requirements
        requirements = {
            PositionEnum.QB: 1,
            PositionEnum.RB: 2,
            PositionEnum.WR: 2,
            PositionEnum.TE: 1,
            PositionEnum.K: 1,
            PositionEnum.DEF: 1
        }
        
        for player_id in self.draft_engine.players_cache:
            player = self.draft_engine.players_cache[player_id]
            position = player.position
            
            current_count = roster["positional_counts"].get(position, 0)
            required = requirements.get(position, 0)
            need = max(0, required - current_count)
            
            # Need multiplier based on round and necessity
            if current_round <= 8:  # Early rounds - moderate need influence
                need_multiplier = 1.0 + (need * 0.2)
            else:  # Later rounds - stronger need influence
                need_multiplier = 1.0 + (need * 0.5)
            
            need_multipliers[player_id] = need_multiplier
        
        return need_multipliers
    
    def _calculate_pick_probabilities(self, available_players: set, utility_map: Dict[int, float],
                                    need_multipliers: Dict[int, float], pick_idx: int) -> Dict[int, float]:
        """Calculate Plackett-Luce pick probabilities"""
        probabilities = {}
        
        for player_id in available_players:
            base_utility = utility_map.get(player_id, 0.0)
            need_multiplier = need_multipliers.get(player_id, 1.0)
            
            # Combine base utility with positional need
            final_utility = base_utility + np.log(need_multiplier)
            probabilities[player_id] = final_utility
        
        return probabilities
    
    def _softmax_sample(self, utilities: Dict[int, float]) -> Optional[int]:
        """Sample player using softmax probabilities"""
        if not utilities:
            return None
        
        player_ids = list(utilities.keys())
        utility_values = np.array([utilities[pid] for pid in player_ids])
        
        # Apply softmax with temperature
        temperature = 1.0  # Can be tuned
        exp_utilities = np.exp(utility_values / temperature)
        probabilities = exp_utilities / np.sum(exp_utilities)
        
        # Sample
        selected_idx = np.random.choice(len(player_ids), p=probabilities)
        return player_ids[selected_idx]
    
    def calibrate(self, players: List[Player], sims_per_iter: int = 1000, 
                 eta: float = 0.3, max_iters: int = 100, tolerance: float = 2.0) -> Dict[int, float]:
        """
        Main calibration loop using iterative Monte-Carlo fitting.
        
        Args:
            players: List of players to calibrate
            sims_per_iter: Number of simulations per iteration
            eta: Learning rate for utility updates
            max_iters: Maximum iterations
            tolerance: RMSE tolerance for convergence
            
        Returns:
            Dictionary of calibrated utilities (player_id -> utility)
        """
        logger.info(f"Starting Plackett-Luce calibration with {len(players)} players")
        
        # Set target ADP
        self.set_target_adp(players)
        
        if len(self.target_adp) < 50:
            logger.warning(f"Only {len(self.target_adp)} players have target ADP. Calibration may be limited.")
        
        # Initialize utilities
        utilities, player_ids = self.initialize_utilities(players)
        
        self.convergence_history = []
        
        for iteration in range(max_iters):
            logger.info(f"Calibration iteration {iteration + 1}/{max_iters}")
            
            # Simulate draft batch
            simulated_adp = self.simulate_draft_batch(utilities, player_ids, sims_per_iter)
            
            # Calculate errors
            errors = []
            target_vec = []
            sim_vec = []
            
            for i, player_id in enumerate(player_ids):
                target = self.target_adp[player_id]
                simulated = simulated_adp.get(player_id, 999.0)
                
                error = target - simulated  # Positive = need to draft earlier
                errors.append(error)
                target_vec.append(target)
                sim_vec.append(simulated)
            
            errors = np.array(errors)
            rmse = np.sqrt(np.mean(errors**2))
            
            # Calculate correlation
            correlation = np.corrcoef(target_vec, sim_vec)[0, 1] if len(target_vec) > 1 else 0.0
            
            logger.info(f"Iteration {iteration + 1}: RMSE={rmse:.3f}, Correlation={correlation:.3f}")
            self.convergence_history.append({"iteration": iteration + 1, "rmse": rmse, "correlation": correlation})
            
            # Check convergence
            if rmse < tolerance:
                logger.info(f"Converged at iteration {iteration + 1} with RMSE {rmse:.3f}")
                break
            
            # Update utilities
            if np.std(errors) > 0:
                scale = np.std(errors)
                utilities += eta * (errors / scale)
                
                # Re-center utilities for numerical stability
                utilities -= np.mean(utilities)
            
            # Reduce learning rate over time
            eta *= 0.99
        
        # Store calibrated utilities
        self.calibrated_utilities = dict(zip(player_ids, utilities))
        
        logger.info(f"Calibration complete. Final RMSE: {rmse:.3f}")
        return self.calibrated_utilities
    
    def get_calibrated_utility(self, player_id: int) -> float:
        """Get calibrated utility for a player"""
        return self.calibrated_utilities.get(player_id, 0.0)
    
    def validate_calibration(self, players: List[Player], num_validation_sims: int = 10000) -> Dict[str, float]:
        """
        Validate calibration with a large simulation run.
        Returns validation metrics.
        """
        if not self.calibrated_utilities:
            logger.warning("No calibrated utilities available for validation")
            return {}
        
        logger.info(f"Validating calibration with {num_validation_sims} simulations")
        
        utilities, player_ids = self.initialize_utilities(players)
        # Use calibrated utilities
        for i, player_id in enumerate(player_ids):
            utilities[i] = self.calibrated_utilities.get(player_id, utilities[i])
        
        # Run validation simulations
        simulated_adp = self.simulate_draft_batch(utilities, player_ids, num_validation_sims)
        
        # Calculate validation metrics
        target_vec = []
        sim_vec = []
        
        for player_id in player_ids:
            if player_id in self.target_adp:
                target_vec.append(self.target_adp[player_id])
                sim_vec.append(simulated_adp.get(player_id, 999.0))
        
        if len(target_vec) > 1:
            rmse = np.sqrt(np.mean((np.array(target_vec) - np.array(sim_vec))**2))
            correlation = np.corrcoef(target_vec, sim_vec)[0, 1]
            
            # Calculate rank correlation (Spearman)
            from scipy.stats import spearmanr
            spearman_corr, _ = spearmanr(target_vec, sim_vec)
            
            validation_metrics = {
                "rmse": rmse,
                "pearson_correlation": correlation,
                "spearman_correlation": spearman_corr,
                "num_players": len(target_vec),
                "num_sims": num_validation_sims
            }
            
            logger.info(f"Validation results: RMSE={rmse:.3f}, Pearson={correlation:.3f}, Spearman={spearman_corr:.3f}")
            return validation_metrics
        
        return {}
