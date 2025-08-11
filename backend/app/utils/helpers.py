from typing import List, Dict, Any, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def format_player_name(name: str) -> str:
    """Format player name for display"""
    if not name:
        return ""
    return name.title()

def format_team_name(team: Optional[str]) -> str:
    """Format team abbreviation for display"""
    if not team:
        return "FA"  # Free Agent
    return team.upper()

def format_position(position: str) -> str:
    """Format position for display"""
    position_display = {
        "QB": "QB",
        "RB": "RB", 
        "WR": "WR",
        "TE": "TE",
        "K": "K",
        "DEF": "D/ST"
    }
    return position_display.get(position.upper(), position)

def calculate_draft_pick_info(pick_number: int, league_size: int = 12, snake_draft: bool = True) -> Dict[str, int]:
    """Calculate round and pick in round from overall pick number"""
    round_number = ((pick_number - 1) // league_size) + 1
    
    if snake_draft and round_number % 2 == 0:
        # Even rounds in snake draft go in reverse order
        pick_in_round = league_size - ((pick_number - 1) % league_size)
    else:
        # Odd rounds or standard draft
        pick_in_round = ((pick_number - 1) % league_size) + 1
    
    return {
        "round": round_number,
        "pick_in_round": pick_in_round
    }

def get_next_pick_info(current_pick: int, team_position: int, league_size: int = 12, snake_draft: bool = True) -> Dict[str, Any]:
    """Calculate when a team picks next"""
    current_round = ((current_pick - 1) // league_size) + 1
    
    if snake_draft:
        # Calculate next pick for this team in snake draft
        if current_round % 2 == 1:  # Odd round
            next_round_pick = (current_round * league_size) + (league_size - team_position + 1)
        else:  # Even round
            next_round_pick = ((current_round + 1) * league_size) - team_position + 1
    else:
        # Standard draft - same position each round
        next_round_pick = (current_round * league_size) + team_position
    
    picks_until_next = next_round_pick - current_pick
    
    return {
        "next_pick_number": next_round_pick,
        "picks_until_next": picks_until_next,
        "next_round": current_round + 1
    }

def grade_to_numeric(grade: str) -> float:
    """Convert letter grade to numeric value for sorting"""
    grade_values = {
        "A+": 4.3,
        "A": 4.0,
        "A-": 3.7,
        "B+": 3.3,
        "B": 3.0,
        "B-": 2.7,
        "C+": 2.3,
        "C": 2.0,
        "C-": 1.7,
        "D+": 1.3,
        "D": 1.0,
        "D-": 0.7,
        "F": 0.0
    }
    return grade_values.get(grade.upper(), 2.0)

def numeric_to_grade(value: float) -> str:
    """Convert numeric value to letter grade"""
    if value >= 4.2:
        return "A+"
    elif value >= 3.8:
        return "A"
    elif value >= 3.5:
        return "A-"
    elif value >= 3.2:
        return "B+"
    elif value >= 2.8:
        return "B"
    elif value >= 2.5:
        return "B-"
    elif value >= 2.2:
        return "C+"
    elif value >= 1.8:
        return "C"
    elif value >= 1.5:
        return "C-"
    elif value >= 1.2:
        return "D+"
    elif value >= 0.8:
        return "D"
    elif value >= 0.5:
        return "D-"
    else:
        return "F"

def calculate_positional_scarcity_tier(rank: int, position: str) -> str:
    """Determine scarcity tier based on positional rank"""
    tiers = {
        "QB": {
            "Elite": (1, 3),
            "Tier 1": (4, 8),
            "Tier 2": (9, 15),
            "Tier 3": (16, 24),
            "Streamer": (25, 999)
        },
        "RB": {
            "Elite": (1, 6),
            "Tier 1": (7, 15),
            "Tier 2": (16, 30),
            "Tier 3": (31, 45),
            "Handcuff": (46, 999)
        },
        "WR": {
            "Elite": (1, 8),
            "Tier 1": (9, 20),
            "Tier 2": (21, 40),
            "Tier 3": (41, 60),
            "Depth": (61, 999)
        },
        "TE": {
            "Elite": (1, 3),
            "Tier 1": (4, 8),
            "Tier 2": (9, 15),
            "Tier 3": (16, 24),
            "Streamer": (25, 999)
        },
        "K": {
            "Tier 1": (1, 5),
            "Tier 2": (6, 12),
            "Streamer": (13, 999)
        },
        "DEF": {
            "Tier 1": (1, 5),
            "Tier 2": (6, 12),
            "Streamer": (13, 999)
        }
    }
    
    position_tiers = tiers.get(position.upper(), tiers["RB"])
    
    for tier_name, (min_rank, max_rank) in position_tiers.items():
        if min_rank <= rank <= max_rank:
            return tier_name
    
    return "Unranked"

def format_currency(amount: float) -> str:
    """Format dollar amount for auction drafts"""
    return f"${amount:.0f}"

def format_percentage(value: float) -> str:
    """Format percentage for display"""
    return f"{value:.1f}%"

def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Safely divide two numbers, returning default if denominator is 0"""
    if denominator == 0:
        return default
    return numerator / denominator

def get_week_range(week: int) -> str:
    """Get date range for a given NFL week"""
    # This is a simplified version - in production you'd want actual NFL schedule dates
    start_date = datetime(2024, 9, 5)  # Approximate NFL season start
    week_start = start_date.replace(day=start_date.day + (week - 1) * 7)
    week_end = week_start.replace(day=week_start.day + 6)
    
    return f"{week_start.strftime('%m/%d')} - {week_end.strftime('%m/%d')}"

def validate_league_settings(settings: Dict[str, Any]) -> List[str]:
    """Validate league settings and return list of errors"""
    errors = []
    
    # Check required fields
    required_fields = ['name', 'league_size', 'scoring_type', 'roster_size']
    for field in required_fields:
        if field not in settings or settings[field] is None:
            errors.append(f"Missing required field: {field}")
    
    # Validate league size
    league_size = settings.get('league_size', 0)
    if not isinstance(league_size, int) or league_size < 4 or league_size > 20:
        errors.append("League size must be between 4 and 20")
    
    # Validate roster size
    roster_size = settings.get('roster_size', 0)
    if not isinstance(roster_size, int) or roster_size < 10 or roster_size > 25:
        errors.append("Roster size must be between 10 and 25")
    
    # Validate starting lineup
    starting_lineup = settings.get('starting_lineup', {})
    if not isinstance(starting_lineup, dict):
        errors.append("Starting lineup must be a dictionary")
    else:
        required_positions = ['QB', 'RB', 'WR', 'TE', 'K', 'DEF']
        for pos in required_positions:
            if pos not in starting_lineup or not isinstance(starting_lineup[pos], int):
                errors.append(f"Starting lineup missing or invalid for position: {pos}")
    
    return errors

def calculate_strength_of_schedule(team_schedule: List[str], opponent_rankings: Dict[str, int]) -> float:
    """Calculate strength of schedule based on opponent rankings"""
    if not team_schedule or not opponent_rankings:
        return 0.0
    
    total_opponent_strength = 0
    valid_opponents = 0
    
    for opponent in team_schedule:
        if opponent in opponent_rankings:
            # Lower ranking = stronger opponent
            opponent_strength = (33 - opponent_rankings[opponent]) / 32.0  # Normalize to 0-1
            total_opponent_strength += opponent_strength
            valid_opponents += 1
    
    if valid_opponents == 0:
        return 0.0
    
    return total_opponent_strength / valid_opponents

def get_bye_week_difficulty(bye_week: int, league_size: int = 12) -> str:
    """Determine bye week difficulty based on timing"""
    if bye_week is None:
        return "Unknown"
    
    if bye_week <= 6:
        return "Early"
    elif bye_week <= 10:
        return "Mid-Season"
    elif bye_week <= 12:
        return "Late"
    else:
        return "Playoff"
