from sqlalchemy.orm import Session
from typing import List, Dict, Any, Tuple
import numpy as np
from scipy import stats
import logging

from ..data.models import Player, PositionEnum, ScoringTypeEnum, ScarcityAnalysis
from ..data.crud import PlayerCRUD, ScarcityCRUD

logger = logging.getLogger(__name__)

class ScarcityAnalyzer:
    """Analyze positional scarcity and tier breaks in fantasy football"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def analyze_position_scarcity(self, position: PositionEnum, scoring_type: ScoringTypeEnum) -> Dict[str, Any]:
        """
        Analyze scarcity for a specific position
        
        Returns:
            Dictionary containing tier breaks, drop-off points, and scarcity score
        """
        # Get players for this position
        players = PlayerCRUD.get_players_by_position(self.db, position)
        
        if not players:
            logger.warning(f"No players found for position {position}")
            return {}
        
        # Extract projected points based on scoring type
        points = self._extract_projected_points(players, scoring_type)
        
        if len(points) < 3:
            logger.warning(f"Not enough players for scarcity analysis: {position}")
            return {}
        
        # Find tier breaks using multiple methods
        tier_breaks = self._find_tier_breaks(points)
        
        # Calculate drop-off points at each tier break
        drop_off_points = [points[i] if i < len(points) else 0 for i in tier_breaks]
        
        # Calculate overall scarcity score
        scarcity_score = self._calculate_scarcity_score(points, tier_breaks)
        
        # Update player scarcity scores
        self._update_player_scarcity_scores(players, points, tier_breaks, scarcity_score)
        
        analysis_data = {
            "position": position,
            "scoring_type": scoring_type,
            "tier_breaks": tier_breaks,
            "drop_off_points": drop_off_points,
            "scarcity_score": scarcity_score,
            "player_count": len(players)
        }
        
        # Store analysis in database
        ScarcityCRUD.create_scarcity_analysis(self.db, analysis_data)
        
        logger.info(f"Scarcity analysis complete for {position}: {scarcity_score:.2f}")
        return analysis_data
    
    def _extract_projected_points(self, players: List[Player], scoring_type: ScoringTypeEnum) -> List[float]:
        """Extract projected points based on scoring type"""
        points = []
        
        for player in players:
            if scoring_type == ScoringTypeEnum.PPR and player.projected_points_ppr:
                points.append(player.projected_points_ppr)
            elif scoring_type == ScoringTypeEnum.HALF_PPR and player.projected_points_half_ppr:
                points.append(player.projected_points_half_ppr)
            elif scoring_type == ScoringTypeEnum.STANDARD and player.projected_points_standard:
                points.append(player.projected_points_standard)
        
        # Sort in descending order
        return sorted(points, reverse=True)
    
    def _find_tier_breaks(self, points: List[float]) -> List[int]:
        """
        Find tier breaks using multiple statistical methods
        
        Methods used:
        1. Standard deviation gaps
        2. Percentage drop-offs
        3. K-means clustering
        """
        if len(points) < 3:
            return []
        
        tier_breaks = set()
        
        # Method 1: Standard deviation gaps
        tier_breaks.update(self._find_stddev_breaks(points))
        
        # Method 2: Percentage drop-offs
        tier_breaks.update(self._find_percentage_breaks(points))
        
        # Method 3: Clustering-based breaks
        tier_breaks.update(self._find_clustering_breaks(points))
        
        # Convert to sorted list and limit to reasonable number of tiers
        tier_breaks = sorted(list(tier_breaks))
        
        # Limit to top 5 tier breaks to avoid over-segmentation
        return tier_breaks[:5]
    
    def _find_stddev_breaks(self, points: List[float]) -> List[int]:
        """Find tier breaks based on standard deviation of gaps"""
        gaps = [points[i] - points[i+1] for i in range(len(points)-1)]
        
        if not gaps:
            return []
        
        gap_mean = np.mean(gaps)
        gap_std = np.std(gaps)
        
        # Find gaps that are significantly larger than average
        threshold = gap_mean + 1.5 * gap_std
        
        breaks = []
        for i, gap in enumerate(gaps):
            if gap > threshold:
                breaks.append(i + 1)  # Position after the gap
        
        return breaks
    
    def _find_percentage_breaks(self, points: List[float]) -> List[int]:
        """Find tier breaks based on percentage drop-offs"""
        breaks = []
        
        for i in range(len(points) - 1):
            if points[i] > 0:  # Avoid division by zero
                pct_drop = (points[i] - points[i+1]) / points[i]
                
                # Significant drop-off thresholds by position
                if pct_drop > 0.15:  # 15% drop is significant
                    breaks.append(i + 1)
        
        return breaks
    
    def _find_clustering_breaks(self, points: List[float]) -> List[int]:
        """Find tier breaks using clustering analysis"""
        if len(points) < 6:  # Need minimum points for clustering
            return []
        
        from sklearn.cluster import KMeans
        
        # Reshape for sklearn
        points_array = np.array(points).reshape(-1, 1)
        
        # Try different numbers of clusters (2-6)
        best_breaks = []
        best_score = -1
        
        for n_clusters in range(2, min(7, len(points)//2)):
            try:
                kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
                labels = kmeans.fit_predict(points_array)
                
                # Find cluster boundaries
                breaks = []
                for i in range(1, len(labels)):
                    if labels[i] != labels[i-1]:
                        breaks.append(i)
                
                # Score based on silhouette score
                if len(set(labels)) > 1:
                    from sklearn.metrics import silhouette_score
                    score = silhouette_score(points_array, labels)
                    
                    if score > best_score:
                        best_score = score
                        best_breaks = breaks
                        
            except Exception as e:
                logger.debug(f"Clustering failed for {n_clusters} clusters: {e}")
                continue
        
        return best_breaks
    
    def _calculate_scarcity_score(self, points: List[float], tier_breaks: List[int]) -> float:
        """
        Calculate overall scarcity score for the position
        
        Higher scores indicate more scarcity (bigger drop-offs)
        """
        if not tier_breaks or len(points) < 2:
            return 0.0
        
        # Calculate weighted drop-off score
        total_drop = 0.0
        total_weight = 0.0
        
        for i, break_point in enumerate(tier_breaks):
            if break_point < len(points) - 1:
                # Drop from previous tier to this tier
                if break_point == 0:
                    prev_point = points[0]
                else:
                    prev_point = points[break_point - 1]
                
                curr_point = points[break_point]
                drop = prev_point - curr_point
                
                # Weight early tiers more heavily
                weight = 1.0 / (i + 1)
                
                total_drop += drop * weight
                total_weight += weight
        
        if total_weight == 0:
            return 0.0
        
        # Normalize by average points to make comparable across positions
        avg_points = np.mean(points[:min(24, len(points))])  # Top 24 players
        scarcity_score = (total_drop / total_weight) / avg_points * 100
        
        return round(scarcity_score, 2)
    
    def _update_player_scarcity_scores(self, players: List[Player], points: List[float], 
                                     tier_breaks: List[int], overall_scarcity: float) -> None:
        """Update individual player scarcity scores"""
        
        # Create tier mapping
        tier_map = {}
        current_tier = 1
        
        for i, point in enumerate(points):
            if i in tier_breaks:
                current_tier += 1
            tier_map[point] = current_tier
        
        # Update player scarcity scores
        for player in players:
            player_points = self._get_player_points(player)
            if player_points in tier_map:
                # Individual scarcity based on tier and overall position scarcity
                tier = tier_map[player_points]
                individual_scarcity = overall_scarcity / tier  # Higher tier = lower individual scarcity
                player.scarcity_score = round(individual_scarcity, 2)
        
        self.db.commit()
    
    def _get_player_points(self, player: Player) -> float:
        """Get player's projected points (defaulting to PPR)"""
        return player.projected_points_ppr or player.projected_points_half_ppr or player.projected_points_standard or 0.0
    
    def analyze_all_positions(self, scoring_type: ScoringTypeEnum = ScoringTypeEnum.PPR) -> Dict[str, Any]:
        """Run scarcity analysis for all positions"""
        results = {}
        
        for position in PositionEnum:
            try:
                analysis = self.analyze_position_scarcity(position, scoring_type)
                results[position.value] = analysis
            except Exception as e:
                logger.error(f"Error analyzing {position}: {e}")
                results[position.value] = {"error": str(e)}
        
        return results
    
    def get_position_rankings_by_scarcity(self, scoring_type: ScoringTypeEnum = ScoringTypeEnum.PPR) -> List[Tuple[str, float]]:
        """Get positions ranked by scarcity (most scarce first)"""
        analyses = ScarcityCRUD.get_all_scarcity_analyses(self.db, scoring_type)
        
        rankings = [(analysis.position.value, analysis.scarcity_score) for analysis in analyses]
        rankings.sort(key=lambda x: x[1], reverse=True)  # Sort by scarcity score descending
        
        return rankings
