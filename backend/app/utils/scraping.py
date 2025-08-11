import requests
from bs4 import BeautifulSoup
import time
import logging
from typing import List, Dict, Any, Optional
from ..core.config import settings

logger = logging.getLogger(__name__)

class FantasyProsScraper:
    """Enhanced FantasyPros scraper with better error handling and rate limiting"""
    
    def __init__(self):
        self.base_url = "https://www.fantasypros.com"
        self.session = requests.Session()
        
        # Set headers to avoid being blocked
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
        self.delay = settings.SCRAPING_DELAY
        self.timeout = settings.REQUEST_TIMEOUT
    
    def scrape_all_data(self) -> List[Dict[str, Any]]:
        """
        Scrape all player data for both PPR and Half-PPR scoring
        
        Returns:
            List of player dictionaries with all relevant data
        """
        all_data = []
        
        # Use ADP URLs to get player lists, then scrape individual projections
        scoring_types = {
            'ppr': f"{self.base_url}/nfl/adp/ppr-overall.php",
            'half_ppr': f"{self.base_url}/nfl/adp/half-point-ppr-overall.php"
        }
        
        for scoring_type, url in scoring_types.items():
            logger.info(f"Scraping {scoring_type} data from {url}")
            
            try:
                data = self._scrape_adp_rankings(url, scoring_type)
                all_data.extend(data)
                
                # Be respectful to the server
                time.sleep(self.delay)
                
            except Exception as e:
                logger.error(f"Error scraping {scoring_type} data: {e}")
                continue
        
        logger.info(f"Successfully scraped {len(all_data)} total player records")
        return all_data
    
    def _scrape_adp_rankings(self, url: str, scoring_type: str) -> List[Dict[str, Any]]:
        """Scrape ADP rankings from FantasyPros"""
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find the main data table
            table = soup.find('table', {'id': 'data'}) or soup.find('table', class_='table')
            
            if not table:
                logger.warning(f"Could not find data table on {url}")
                return []
            
            players_data = []
            rows = table.find('tbody').find_all('tr') if table.find('tbody') else table.find_all('tr')[1:]
            
            for row in rows:
                try:
                    player_data = self._parse_table_row(row, scoring_type)
                    if player_data:
                        players_data.append(player_data)
                except Exception as e:
                    logger.debug(f"Error parsing row: {e}")
                    continue
            
            logger.info(f"Scraped {len(players_data)} players for {scoring_type}")
            return players_data
            
        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            return []
    
    def _parse_table_row(self, row, scoring_type: str) -> Optional[Dict[str, Any]]:
        """Parse a single table row into player data"""
        cells = row.find_all(['td', 'th'])
        
        if len(cells) < 3:
            return None
        
        try:
            # Extract basic data from cells
            rank = int(cells[0].get_text(strip=True))
            player_cell = cells[1]
            
            # Get player name and details
            player_text = player_cell.get_text(strip=True)
            player_name, team, bye_week = self._parse_player_info(player_text)
            
            if not player_name:
                return None
            
            # Get position info from remaining cells
            position_info = None
            adp_value = None
            
            for cell in cells[2:]:
                cell_text = cell.get_text(strip=True)
                
                # Try to parse as position (e.g., "WR1", "RB12")
                if self._is_position_text(cell_text):
                    position_info = cell_text
                
                # Try to parse as ADP (numeric value)
                try:
                    potential_adp = float(cell_text)
                    if 1 <= potential_adp <= 300:  # Reasonable ADP range
                        adp_value = potential_adp
                except ValueError:
                    continue
            
            # Parse position from position info
            position = self._parse_position(position_info) if position_info else None
            
            if not position:
                return None
            
            # Use rank as ADP if no specific ADP found
            if not adp_value:
                adp_value = float(rank)
            
            # Get player URL for projections
            player_url = self._extract_player_url(player_cell)
            
            # Scrape projections if URL available
            projections = {}
            if player_url:
                projections = self._scrape_player_projections(player_url, scoring_type)
                time.sleep(0.3)  # Small delay between projection requests
            
            return {
                'player_name': player_name,
                'position': position,
                'team': team,
                'bye_week': bye_week,
                'rank': rank,
                'adp': adp_value,
                'scoring_type': scoring_type,
                'player_url': player_url,
                'projections': projections
            }
            
        except Exception as e:
            logger.debug(f"Error parsing player row: {e}")
            return None
    
    def _parse_player_info(self, player_text: str) -> tuple:
        """Parse player name, team, and bye week from combined text"""
        import re
        
        # Clean up the text first
        player_text = player_text.strip()
        
        # Common team abbreviations to look for
        valid_teams = {'BAL', 'BUF', 'MIA', 'NE', 'NEP', 'NYJ', 'CIN', 'CLE', 'PIT', 'HOU', 'IND', 'JAC', 'TEN', 
                      'DEN', 'KC', 'KCC', 'LV', 'LVR', 'LAC', 'DAL', 'NYG', 'PHI', 'WAS', 'CHI', 'DET', 'GB', 'GBP', 'MIN',
                      'ATL', 'CAR', 'NO', 'NOR', 'TB', 'TAM', 'ARI', 'LAR', 'SF', 'SFO', 'SEA', 'DST'}
        
        # Pattern 1: "Player Name TEAM(BYE)" - most common format
        # Look for 2-4 uppercase letters followed by parentheses with digits
        match = re.search(r'^(.+?)\s+([A-Z]{2,4})\((\d+)\)$', player_text)
        if match:
            name = match.group(1).strip()
            team = match.group(2).strip()
            bye_week = int(match.group(3))
            return name, team, bye_week
        
        # Pattern 2: "Player Name TEAM (BYE)" - with space before parentheses
        match = re.search(r'^(.+?)\s+([A-Z]{2,4})\s+\((\d+)\)$', player_text)
        if match:
            name = match.group(1).strip()
            team = match.group(2).strip()
            bye_week = int(match.group(3))
            return name, team, bye_week
        
        # Pattern 3: Handle Roman numerals and suffixes like "Kenneth Walker Iiisea(8)"
        # Look for Roman numerals (II, III, IV, Jr, Sr) that might be combined with team
        roman_suffixes = ['II', 'III', 'IV', 'JR', 'SR']
        
        for suffix in roman_suffixes:
            # Pattern: "Player Name [Suffix][TEAM](BYE)" - case insensitive matching
            pattern = rf'^(.+?)\s+{re.escape(suffix.lower())}([A-Z]{{2,4}})\((\d+)\)$'
            match = re.search(pattern, player_text, re.IGNORECASE)
            if match:
                name_part = match.group(1).strip()
                team_part = match.group(2).strip().upper()
                bye_week = int(match.group(3))
                
                # Check if team_part is a valid team
                if team_part in valid_teams:
                    # Ensure proper capitalization of suffix
                    if suffix in ['II', 'III', 'IV']:
                        proper_suffix = suffix  # Keep Roman numerals uppercase
                    else:
                        proper_suffix = suffix.title()  # Jr, Sr -> Jr, Sr
                    
                    name = f"{name_part} {proper_suffix}"
                    return name, team_part, bye_week
        
        # Pattern 4: "Player NameTEAM(BYE)" - no space between name and team
        # This handles cases like "Lamar Jacksonbal(7)" -> "Lamar Jackson" + "BAL"
        match = re.search(r'^(.+?)([A-Z]{2,4})\((\d+)\)$', player_text)
        if match:
            name_part = match.group(1).strip()
            team = match.group(2).strip()
            bye_week = int(match.group(3))
            
            if team in valid_teams:
                # Remove team abbreviation from the end of name if it's there
                if name_part.upper().endswith(team):
                    name = name_part[:-len(team)].strip()
                else:
                    name = name_part
                return name, team, bye_week
        
        # Pattern 5: "Player Name TEAM" - no bye week
        match = re.search(r'^(.+?)\s+([A-Z]{2,4})$', player_text)
        if match:
            name = match.group(1).strip()
            team = match.group(2).strip()
            return name, team, None
        
        # Pattern 6: Just player name
        return player_text.strip(), None, None
    
    def _is_position_text(self, text: str) -> bool:
        """Check if text looks like position info (e.g., WR1, RB12)"""
        import re
        return bool(re.match(r'^[A-Z]{1,3}\d+$', text))
    
    def _parse_position(self, position_text: str) -> Optional[str]:
        """Parse position from text like 'WR1', 'RB12'"""
        import re
        
        if not position_text:
            return None
        
        match = re.match(r'^([A-Z]+)\d*$', position_text)
        if match:
            pos = match.group(1)
            
            position_mapping = {
                'QB': 'QB',
                'RB': 'RB', 
                'WR': 'WR',
                'TE': 'TE',
                'K': 'K',
                'DST': 'DEF',
                'DEF': 'DEF'
            }
            
            return position_mapping.get(pos)
        
        return None
    
    def _extract_player_url(self, player_cell) -> Optional[str]:
        """Extract player profile URL from cell"""
        link = player_cell.find('a')
        if link and link.get('href'):
            href = link.get('href')
            if href.startswith('/'):
                return f"{self.base_url}{href}"
            else:
                return href
        return None
    
    def _scrape_player_projections(self, player_url: str, scoring_type: str) -> Dict[str, Any]:
        """Scrape projections from individual player page"""
        try:
            response = self.session.get(player_url, timeout=self.timeout)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for projections table
            projections_table = self._find_projections_table(soup)
            
            if not projections_table:
                return {}
            
            # Parse projections
            projections = self._parse_projections_table(projections_table)
            
            # Calculate fantasy points
            if projections:
                projected_points = self._calculate_fantasy_points(projections, scoring_type)
                projections['calculated_points'] = projected_points
            
            return projections
            
        except Exception as e:
            logger.debug(f"Error scraping projections from {player_url}: {e}")
            return {}
    
    def _find_projections_table(self, soup) -> Optional[Any]:
        """Find the projections table on player page - look for POINTS and RECS"""
        # Look for any table with projection-related headers including POINTS and RECS
        tables = soup.find_all('table')
        for table in tables:
            # Get all headers from the table
            header_cells = table.find_all(['th', 'td'])
            if len(header_cells) > 5:  # Only check substantial tables
                headers = [th.get_text(strip=True).upper() for th in header_cells[:15]]
                
                # Look for tables with both POINTS and RECS (or REC)
                has_points = 'POINTS' in headers
                has_recs = any(keyword in headers for keyword in ['RECS', 'REC'])
                
                if has_points and has_recs:
                    return table
                
                # Fallback: look for tables with key fantasy stats
                if any(keyword in ' '.join(headers) for keyword in ['RECS', 'POINTS', 'REC YDS', 'REC TDS']):
                    return table
        
        return None
    
    def _parse_projections_table(self, table) -> Dict[str, Any]:
        """Parse projections from table - extract POINTS and RECS using proper row structure"""
        projections = {}
        
        try:
            # Get all rows
            rows = table.find_all('tr')
            if len(rows) < 2:
                return projections
            
            # First row should be headers, second row should be data
            header_row = rows[0]
            data_row = rows[1]
            
            # Get headers and data
            header_cells = header_row.find_all(['th', 'td'])
            data_cells = data_row.find_all(['td', 'th'])
            
            headers = [th.get_text(strip=True).upper() for th in header_cells]
            
            # Map headers to values
            for i, header in enumerate(headers):
                if i < len(data_cells):
                    value_text = data_cells[i].get_text(strip=True)
                    
                    # Focus on key stats: POINTS and RECS
                    if header in ['POINTS', 'RECS', 'REC', 'RECEPTIONS']:
                        try:
                            projections[header] = float(value_text)
                        except ValueError:
                            projections[header] = 0.0
                    else:
                        # Store other stats as well for debugging
                        try:
                            projections[header] = float(value_text)
                        except ValueError:
                            projections[header] = value_text
            
            return projections
            
        except Exception as e:
            logger.debug(f"Error parsing projections table: {e}")
            return {}
    
    def _calculate_fantasy_points(self, projections: Dict[str, Any], scoring_type: str) -> Optional[float]:
        """Calculate fantasy points using POINTS + RECS formula"""
        try:
            # Get POINTS and RECS directly from projections table
            base_points = projections.get('POINTS', None)
            receptions = projections.get('RECS', projections.get('REC', projections.get('RECEPTIONS', None)))
            
            # If no base points found, return None (don't assign 0)
            if base_points is None or base_points == '' or base_points == 0:
                return None
            
            # Convert to float
            base_points = float(base_points)
            receptions = float(receptions) if receptions else 0.0
            
            # Apply user's formula:
            # Half-PPR: POINTS + (RECS / 2)
            # PPR: POINTS + RECS
            if scoring_type == 'ppr':
                total_points = base_points + receptions
            elif scoring_type == 'half_ppr':
                total_points = base_points + (receptions / 2.0)
            else:  # standard
                total_points = base_points
            
            return round(total_points, 2)
            
        except Exception as e:
            logger.debug(f"Error calculating fantasy points: {e}")
            # Don't return 0 as fallback - return None to indicate missing data
            return None
