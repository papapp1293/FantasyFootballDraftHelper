from sqlalchemy.orm import Session
from typing import Dict, List, Optional, Any
import numpy as np
import logging

from ..data.models import Player, PositionEnum, ScoringTypeEnum
from ..data.crud import PlayerCRUD
from ..core.config import settings

logger = logging.getLogger(__name__)

class VORPCalculator:
    """Calculate Value Over Replacement Player (VORP) for fantasy football players"""
    
    def __init__(self, db: Session):
        self.db = db
        self.replacement_percentile = settings.REPLACEMENT_LEVEL_PERCENTILE
    
    def calculate_position_vorp(self, position: PositionEnum, scoring_type: ScoringTypeEnum) -> Dict[int, float]:
        """
        Calculate VORP for all players at a specific position
        
        Args:
            position: Player position to analyze
            scoring_type: Scoring system (PPR, Half-PPR, Standard)
            
        Returns:
            Dictionary mapping player_id to VORP value
        """
        # Get all players at this position
        players = PlayerCRUD.get_players_by_position(self.db, position)
        
        if not players:
            logger.warning(f"No players found for position {position}")
            return {}
        
        # Extract projected points
        player_points = []
        for player in players:
            points = self._get_projected_points(player, scoring_type)
            if points is not None:
                player_points.append((player.id, points))
        
        if not player_points:
            logger.warning(f"No projected points found for position {position}")
            return {}
        
        # Sort by projected points (descending)
        player_points.sort(key=lambda x: x[1], reverse=True)
        
        # Calculate replacement level
        replacement_level = self._calculate_replacement_level(
            [points for _, points in player_points], position
        )
        
        # Calculate VORP for each player
        vorp_values = {}
        for player_id, points in player_points:
            vorp = points - replacement_level
            vorp_values[player_id] = round(vorp, 2)
        
        logger.info(f"Calculated VORP for {len(vorp_values)} {position} players (replacement: {replacement_level:.2f})")
        return vorp_values
    
    def _get_projected_points(self, player: Player, scoring_type: ScoringTypeEnum) -> Optional[float]:
        """Get projected points for a player based on scoring type"""
        if scoring_type == ScoringTypeEnum.PPR:
            return player.projected_points_ppr
        elif scoring_type == ScoringTypeEnum.HALF_PPR:
            return player.projected_points_half_ppr
        elif scoring_type == ScoringTypeEnum.STANDARD:
            return player.projected_points_standard
        return None
    
    def _calculate_replacement_level(self, points: List[float], position: PositionEnum) -> float:
        """
        Calculate replacement level for a position
        
        Replacement level is based on:
        1. League size and roster requirements
        2. Position scarcity
        3. Typical draft patterns
        """
        if not points:
            return 0.0
        
        # Position-specific replacement level calculations
        league_size = settings.DEFAULT_LEAGUE_SIZE
        starting_lineup = settings.DEFAULT_STARTING_LINEUP
        
        if position == PositionEnum.QB:
            # Most leagues start 1 QB, replacement is around QB12-15
            replacement_rank = league_size + 3
        elif position == PositionEnum.RB:
            # Most leagues start 2-3 RBs, replacement is around RB30-36
            rb_starters = starting_lineup.get("RB", 2) + starting_lineup.get("FLEX", 1) * 0.4  # 40% of flex are RBs
            replacement_rank = int(league_size * rb_starters) + 6
        elif position == PositionEnum.WR:
            # Most leagues start 2-3 WRs, replacement is around WR36-42
            wr_starters = starting_lineup.get("WR", 2) + starting_lineup.get("FLEX", 1) * 0.5  # 50% of flex are WRs
            replacement_rank = int(league_size * wr_starters) + 6
        elif position == PositionEnum.TE:
            # Most leagues start 1 TE, replacement is around TE12-15
            te_starters = starting_lineup.get("TE", 1) + starting_lineup.get("FLEX", 1) * 0.1  # 10% of flex are TEs
            replacement_rank = int(league_size * te_starters) + 3
        elif position == PositionEnum.K:
            # Kickers have low variance, replacement is around K12-15
            replacement_rank = league_size + 3
        elif position == PositionEnum.DEF:
            # Defenses have low variance, replacement is around DEF12-15
            replacement_rank = league_size + 3
        else:
            # Default fallback
            replacement_rank = league_size
        
        # Ensure replacement rank doesn't exceed available players
        replacement_rank = min(replacement_rank, len(points))
        
        # Get replacement level points (0-indexed, so subtract 1)
        if replacement_rank > 0:
            replacement_level = points[replacement_rank - 1]
        else:
            replacement_level = points[-1] if points else 0.0
        
        # Apply position-specific multiplier for scarcity
        from ..core.scoring import ScoringSystem
        scoring_system = ScoringSystem()
        multiplier = scoring_system.get_replacement_level_multiplier(position.value)
        
        return replacement_level * multiplier
    
    def calculate_all_vorp(self, scoring_type: ScoringTypeEnum = ScoringTypeEnum.PPR) -> Dict[int, float]:
        """Calculate VORP for all players across all positions"""
        all_vorp = {}
        
        for position in PositionEnum:
            try:
                position_vorp = self.calculate_position_vorp(position, scoring_type)
                all_vorp.update(position_vorp)
            except Exception as e:
                logger.error(f"Error calculating VORP for {position}: {e}")
                continue
        
        logger.info(f"Calculated VORP for {len(all_vorp)} total players")
        return all_vorp
    
    def get_top_vorp_players(self, scoring_type: ScoringTypeEnum = ScoringTypeEnum.PPR, 
                           limit: int = 100) -> List[Player]:
        """Get players with highest VORP values"""
        if scoring_type == ScoringTypeEnum.PPR:
            players = self.db.query(Player).filter(Player.vorp_ppr.isnot(None)).order_by(Player.vorp_ppr.desc()).limit(limit).all()
        elif scoring_type == ScoringTypeEnum.HALF_PPR:
            players = self.db.query(Player).filter(Player.vorp_half_ppr.isnot(None)).order_by(Player.vorp_half_ppr.desc()).limit(limit).all()
        else:
            players = self.db.query(Player).filter(Player.vorp_standard.isnot(None)).order_by(Player.vorp_standard.desc()).limit(limit).all()
        
        return players
    
    def get_position_vorp_rankings(self, position: PositionEnum, 
                                 scoring_type: ScoringTypeEnum = ScoringTypeEnum.PPR) -> List[Player]:
        """Get VORP rankings for a specific position"""
        players = PlayerCRUD.get_players_by_position(self.db, position)
        
        # Filter and sort by VORP
        vorp_players = []
        for player in players:
            vorp_value = self._get_player_vorp(player, scoring_type)
            if vorp_value is not None:
                vorp_players.append((player, vorp_value))
        
        # Sort by VORP descending
        vorp_players.sort(key=lambda x: x[1], reverse=True)
        
        return [player for player, _ in vorp_players]
    
    def _get_player_vorp(self, player: Player, scoring_type: ScoringTypeEnum) -> Optional[float]:
        """Get VORP value for a player based on scoring type"""
        if scoring_type == ScoringTypeEnum.PPR:
            return player.vorp_ppr
        elif scoring_type == ScoringTypeEnum.HALF_PPR:
            return player.vorp_half_ppr
        elif scoring_type == ScoringTypeEnum.STANDARD:
            return player.vorp_standard
        return None
    
    def compare_players(self, player_ids: List[int], scoring_type: ScoringTypeEnum = ScoringTypeEnum.PPR) -> Dict[str, Any]:
        """Compare VORP values between multiple players"""
        comparison = {
            "players": [],
            "scoring_type": scoring_type.value
        }
        
        for player_id in player_ids:
            player = PlayerCRUD.get_player(self.db, player_id)
            if player:
                vorp = self._get_player_vorp(player, scoring_type)
                projected_points = self._get_projected_points(player, scoring_type)
                
                comparison["players"].append({
                    "id": player.id,
                    "name": player.name,
                    "position": player.position.value,
                    "team": player.team,
                    "projected_points": projected_points,
                    "vorp": vorp,
                    "adp": self._get_player_adp(player, scoring_type)
                })
        
        # Sort by VORP descending
        comparison["players"].sort(key=lambda x: x["vorp"] or 0, reverse=True)
        
        return comparison
    
    def _get_player_adp(self, player: Player, scoring_type: ScoringTypeEnum) -> Optional[float]:
        """Get ADP for a player based on scoring type"""
        if scoring_type == ScoringTypeEnum.PPR:
            return player.adp_ppr
        elif scoring_type == ScoringTypeEnum.HALF_PPR:
            return player.adp_half_ppr
        elif scoring_type == ScoringTypeEnum.STANDARD:
            return player.adp_standard
        return None
