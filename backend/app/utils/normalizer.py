import re
from typing import Dict, Optional

class PlayerNameNormalizer:
    """Normalize player names for consistent database storage and matching"""
    
    def __init__(self):
        # Common name variations and corrections
        self.name_corrections = {
            # Common abbreviations
            "Jr.": "Jr",
            "Sr.": "Sr",
            "III": "III",
            "II": "II",
            "IV": "IV",
            
            # Common misspellings or variations
            "D'Andre": "DeAndre",
            "De'Andre": "DeAndre",
            "D.K.": "DK",
            "A.J.": "AJ",
            "T.J.": "TJ",
            "J.J.": "JJ",
            "C.J.": "CJ",
            "D.J.": "DJ",
        }
        
        # Team name standardization
        self.team_corrections = {
            "JAX": "JAC",
            "WSH": "WAS", 
            "LV": "LVR",
            "NO": "NOR",
            "NE": "NEP",
            "SF": "SFO",
            "TB": "TAM",
            "GB": "GBP",
            "KC": "KCC",
        }
    
    def normalize_name(self, name: str) -> str:
        """
        Normalize a player name for consistent storage
        
        Args:
            name: Raw player name
            
        Returns:
            Normalized player name
        """
        if not name:
            return ""
        
        # Remove extra whitespace
        normalized = name.strip()
        
        # Remove common suffixes that might be inconsistent
        normalized = re.sub(r'\s+(Jr\.?|Sr\.?|III|II|IV)$', r' \1', normalized)
        
        # Apply specific corrections
        for old, new in self.name_corrections.items():
            normalized = normalized.replace(old, new)
        
        # Standardize apostrophes
        normalized = normalized.replace("'", "'")
        
        # Remove periods from initials but keep spaces
        normalized = re.sub(r'([A-Z])\.', r'\1', normalized)
        
        # Normalize spacing
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        # Title case
        normalized = self._smart_title_case(normalized)
        
        return normalized
    
    def _smart_title_case(self, name: str) -> str:
        """Apply smart title casing that handles prefixes correctly"""
        # Split into parts
        parts = name.split()
        
        result_parts = []
        for part in parts:
            # Handle prefixes like "De", "Van", "Mac", etc.
            if part.lower() in ['de', 'van', 'von', 'la', 'le', 'du', 'da']:
                result_parts.append(part.lower())
            elif part.lower().startswith('mc') and len(part) > 2:
                # Handle "Mc" names
                result_parts.append('Mc' + part[2:].capitalize())
            elif part.lower().startswith('mac') and len(part) > 3:
                # Handle "Mac" names  
                result_parts.append('Mac' + part[3:].capitalize())
            elif "'" in part:
                # Handle apostrophes (O'Brien, D'Angelo, etc.)
                apostrophe_parts = part.split("'")
                formatted_parts = [p.capitalize() for p in apostrophe_parts]
                result_parts.append("'".join(formatted_parts))
            else:
                result_parts.append(part.capitalize())
        
        return ' '.join(result_parts)
    
    def normalize_team(self, team: Optional[str]) -> Optional[str]:
        """Normalize team abbreviation"""
        if not team:
            return None
        
        team = team.upper().strip()
        return self.team_corrections.get(team, team)
    
    def fuzzy_match_names(self, name1: str, name2: str, threshold: float = 0.8) -> bool:
        """
        Check if two names are likely the same player using fuzzy matching
        
        Args:
            name1: First name to compare
            name2: Second name to compare  
            threshold: Similarity threshold (0-1)
            
        Returns:
            True if names are likely the same player
        """
        # Normalize both names
        norm1 = self.normalize_name(name1).lower()
        norm2 = self.normalize_name(name2).lower()
        
        # Exact match
        if norm1 == norm2:
            return True
        
        # Check for common variations
        # Remove middle names/initials for comparison
        first_last1 = self._get_first_last(norm1)
        first_last2 = self._get_first_last(norm2)
        
        if first_last1 == first_last2:
            return True
        
        # Use Levenshtein distance for fuzzy matching
        similarity = self._calculate_similarity(norm1, norm2)
        return similarity >= threshold
    
    def _get_first_last(self, name: str) -> str:
        """Extract first and last name only"""
        parts = name.split()
        if len(parts) >= 2:
            return f"{parts[0]} {parts[-1]}"
        return name
    
    def _calculate_similarity(self, s1: str, s2: str) -> float:
        """Calculate similarity ratio between two strings"""
        # Simple implementation - in production you might use python-Levenshtein
        if not s1 or not s2:
            return 0.0
        
        # Calculate Levenshtein distance
        len1, len2 = len(s1), len(s2)
        
        # Create matrix
        matrix = [[0] * (len2 + 1) for _ in range(len1 + 1)]
        
        # Initialize first row and column
        for i in range(len1 + 1):
            matrix[i][0] = i
        for j in range(len2 + 1):
            matrix[0][j] = j
        
        # Fill matrix
        for i in range(1, len1 + 1):
            for j in range(1, len2 + 1):
                if s1[i-1] == s2[j-1]:
                    cost = 0
                else:
                    cost = 1
                
                matrix[i][j] = min(
                    matrix[i-1][j] + 1,      # deletion
                    matrix[i][j-1] + 1,      # insertion
                    matrix[i-1][j-1] + cost  # substitution
                )
        
        # Calculate similarity ratio
        distance = matrix[len1][len2]
        max_len = max(len1, len2)
        
        if max_len == 0:
            return 1.0
        
        return 1.0 - (distance / max_len)
