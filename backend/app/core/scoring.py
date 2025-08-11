from typing import Dict, Any
from .config import ScoringType

class ScoringSystem:
    """Fantasy football scoring system implementation"""
    
    # Standard scoring rules
    SCORING_RULES = {
        ScoringType.STANDARD: {
            # Passing
            "pass_yards_per_point": 25,
            "pass_td": 4,
            "pass_int": -2,
            "pass_2pt": 2,
            
            # Rushing
            "rush_yards_per_point": 10,
            "rush_td": 6,
            "rush_2pt": 2,
            
            # Receiving
            "rec_yards_per_point": 10,
            "rec_td": 6,
            "rec_2pt": 2,
            "reception": 0,  # No PPR bonus
            
            # Kicking
            "fg_0_39": 3,
            "fg_40_49": 4,
            "fg_50_plus": 5,
            "pat": 1,
            "fg_miss": 0,
            
            # Defense
            "def_td": 6,
            "def_int": 2,
            "def_fumble_rec": 2,
            "def_safety": 2,
            "def_sack": 1,
            "def_block": 2,
            
            # Points allowed (defense)
            "def_pts_0": 10,
            "def_pts_1_6": 7,
            "def_pts_7_13": 4,
            "def_pts_14_20": 1,
            "def_pts_21_27": 0,
            "def_pts_28_34": -1,
            "def_pts_35_plus": -4,
            
            # Yards allowed (defense)
            "def_yds_under_100": 5,
            "def_yds_100_199": 3,
            "def_yds_200_299": 2,
            "def_yds_300_399": 0,
            "def_yds_400_499": -1,
            "def_yds_500_plus": -3,
        }
    }
    
    def __init__(self, scoring_type: ScoringType = ScoringType.PPR):
        self.scoring_type = scoring_type
        self.rules = self.SCORING_RULES[ScoringType.STANDARD].copy()
        
        # Modify for PPR/Half-PPR
        if scoring_type == ScoringType.PPR:
            self.rules["reception"] = 1.0
        elif scoring_type == ScoringType.HALF_PPR:
            self.rules["reception"] = 0.5
    
    def calculate_points(self, stats: Dict[str, Any]) -> float:
        """Calculate fantasy points from player stats"""
        points = 0.0
        
        # Passing stats
        points += stats.get("pass_yards", 0) / self.rules["pass_yards_per_point"]
        points += stats.get("pass_td", 0) * self.rules["pass_td"]
        points += stats.get("pass_int", 0) * self.rules["pass_int"]
        points += stats.get("pass_2pt", 0) * self.rules["pass_2pt"]
        
        # Rushing stats
        points += stats.get("rush_yards", 0) / self.rules["rush_yards_per_point"]
        points += stats.get("rush_td", 0) * self.rules["rush_td"]
        points += stats.get("rush_2pt", 0) * self.rules["rush_2pt"]
        
        # Receiving stats
        points += stats.get("rec_yards", 0) / self.rules["rec_yards_per_point"]
        points += stats.get("rec_td", 0) * self.rules["rec_td"]
        points += stats.get("rec_2pt", 0) * self.rules["rec_2pt"]
        points += stats.get("receptions", 0) * self.rules["reception"]
        
        # Kicking stats
        points += stats.get("fg_0_39", 0) * self.rules["fg_0_39"]
        points += stats.get("fg_40_49", 0) * self.rules["fg_40_49"]
        points += stats.get("fg_50_plus", 0) * self.rules["fg_50_plus"]
        points += stats.get("pat", 0) * self.rules["pat"]
        
        # Defense stats
        points += stats.get("def_td", 0) * self.rules["def_td"]
        points += stats.get("def_int", 0) * self.rules["def_int"]
        points += stats.get("def_fumble_rec", 0) * self.rules["def_fumble_rec"]
        points += stats.get("def_safety", 0) * self.rules["def_safety"]
        points += stats.get("def_sack", 0) * self.rules["def_sack"]
        points += stats.get("def_block", 0) * self.rules["def_block"]
        
        return round(points, 2)
    
    def get_replacement_level_multiplier(self, position: str) -> float:
        """Get position-specific replacement level multiplier"""
        multipliers = {
            "QB": 1.0,
            "RB": 1.2,  # RBs are more scarce
            "WR": 1.1,
            "TE": 1.3,  # TEs are most scarce
            "K": 0.8,   # Kickers are less important
            "DEF": 0.8  # Defense is less important
        }
        return multipliers.get(position, 1.0)
