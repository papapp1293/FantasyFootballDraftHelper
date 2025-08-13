#!/usr/bin/env python3
"""
Quick script to populate database with sample player data for testing
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set environment variable to use SQLite
os.environ['DATABASE_URL'] = 'sqlite:///./fantasy_football.db'

from app.data.database import SessionLocal, create_tables
from app.data.models import Player, PositionEnum, ScoringTypeEnum

def create_sample_players():
    """Create sample players for testing"""
    
    # Create tables first
    create_tables()
    
    db = SessionLocal()
    try:
        # Check if players already exist
        existing_count = db.query(Player).count()
        if existing_count > 0:
            print(f"Database already has {existing_count} players. Skipping creation.")
            return
        
        sample_players = [
            # QBs
            {"name": "Josh Allen", "position": PositionEnum.QB, "team": "BUF", "bye_week": 12, "projected_points_ppr": 24.5, "adp_ppr": 15.2, "expert_consensus_rank": 1},
            {"name": "Lamar Jackson", "position": PositionEnum.QB, "team": "BAL", "bye_week": 14, "projected_points_ppr": 23.8, "adp_ppr": 18.7, "expert_consensus_rank": 2},
            {"name": "Patrick Mahomes", "position": PositionEnum.QB, "team": "KC", "bye_week": 10, "projected_points_ppr": 23.2, "adp_ppr": 22.1, "expert_consensus_rank": 3},
            {"name": "Jalen Hurts", "position": PositionEnum.QB, "team": "PHI", "bye_week": 7, "projected_points_ppr": 22.9, "adp_ppr": 25.3, "expert_consensus_rank": 4},
            {"name": "Joe Burrow", "position": PositionEnum.QB, "team": "CIN", "bye_week": 12, "projected_points_ppr": 21.8, "adp_ppr": 35.6, "expert_consensus_rank": 5},
            
            # RBs
            {"name": "Christian McCaffrey", "position": PositionEnum.RB, "team": "SF", "bye_week": 9, "projected_points_ppr": 22.1, "adp_ppr": 1.2, "expert_consensus_rank": 1},
            {"name": "Austin Ekeler", "position": PositionEnum.RB, "team": "LAC", "bye_week": 5, "projected_points_ppr": 19.8, "adp_ppr": 3.4, "expert_consensus_rank": 2},
            {"name": "Jonathan Taylor", "position": PositionEnum.RB, "team": "IND", "bye_week": 13, "projected_points_ppr": 18.9, "adp_ppr": 4.1, "expert_consensus_rank": 3},
            {"name": "Derrick Henry", "position": PositionEnum.RB, "team": "TEN", "bye_week": 7, "projected_points_ppr": 17.2, "adp_ppr": 8.9, "expert_consensus_rank": 4},
            {"name": "Nick Chubb", "position": PositionEnum.RB, "team": "CLE", "bye_week": 5, "projected_points_ppr": 16.8, "adp_ppr": 12.3, "expert_consensus_rank": 5},
            {"name": "Saquon Barkley", "position": PositionEnum.RB, "team": "NYG", "bye_week": 11, "projected_points_ppr": 16.1, "adp_ppr": 15.7, "expert_consensus_rank": 6},
            {"name": "Josh Jacobs", "position": PositionEnum.RB, "team": "LV", "bye_week": 6, "projected_points_ppr": 15.4, "adp_ppr": 19.2, "expert_consensus_rank": 7},
            {"name": "Aaron Jones", "position": PositionEnum.RB, "team": "GB", "bye_week": 13, "projected_points_ppr": 14.9, "adp_ppr": 23.8, "expert_consensus_rank": 8},
            
            # WRs
            {"name": "Cooper Kupp", "position": PositionEnum.WR, "team": "LAR", "bye_week": 10, "projected_points_ppr": 18.7, "adp_ppr": 5.2, "expert_consensus_rank": 1},
            {"name": "Stefon Diggs", "position": PositionEnum.WR, "team": "BUF", "bye_week": 12, "projected_points_ppr": 17.9, "adp_ppr": 6.8, "expert_consensus_rank": 2},
            {"name": "Tyreek Hill", "position": PositionEnum.WR, "team": "MIA", "bye_week": 11, "projected_points_ppr": 17.3, "adp_ppr": 7.1, "expert_consensus_rank": 3},
            {"name": "Davante Adams", "position": PositionEnum.WR, "team": "LV", "bye_week": 6, "projected_points_ppr": 16.8, "adp_ppr": 9.4, "expert_consensus_rank": 4},
            {"name": "Ja'Marr Chase", "position": PositionEnum.WR, "team": "CIN", "bye_week": 12, "projected_points_ppr": 16.2, "adp_ppr": 11.7, "expert_consensus_rank": 5},
            {"name": "CeeDee Lamb", "position": PositionEnum.WR, "team": "DAL", "bye_week": 9, "projected_points_ppr": 15.9, "adp_ppr": 13.2, "expert_consensus_rank": 6},
            {"name": "A.J. Brown", "position": PositionEnum.WR, "team": "PHI", "bye_week": 7, "projected_points_ppr": 15.4, "adp_ppr": 16.8, "expert_consensus_rank": 7},
            {"name": "DeAndre Hopkins", "position": PositionEnum.WR, "team": "ARI", "bye_week": 13, "projected_points_ppr": 14.8, "adp_ppr": 20.5, "expert_consensus_rank": 8},
            
            # TEs
            {"name": "Travis Kelce", "position": PositionEnum.TE, "team": "KC", "bye_week": 10, "projected_points_ppr": 14.2, "adp_ppr": 14.3, "expert_consensus_rank": 1},
            {"name": "Mark Andrews", "position": PositionEnum.TE, "team": "BAL", "bye_week": 14, "projected_points_ppr": 12.8, "adp_ppr": 28.9, "expert_consensus_rank": 2},
            {"name": "George Kittle", "position": PositionEnum.TE, "team": "SF", "bye_week": 9, "projected_points_ppr": 11.9, "adp_ppr": 42.1, "expert_consensus_rank": 3},
            {"name": "T.J. Hockenson", "position": PositionEnum.TE, "team": "MIN", "bye_week": 13, "projected_points_ppr": 10.8, "adp_ppr": 56.7, "expert_consensus_rank": 4},
            
            # Kickers
            {"name": "Justin Tucker", "position": PositionEnum.K, "team": "BAL", "bye_week": 14, "projected_points_ppr": 8.9, "adp_ppr": 145.2, "expert_consensus_rank": 1},
            {"name": "Daniel Carlson", "position": PositionEnum.K, "team": "LV", "bye_week": 6, "projected_points_ppr": 8.4, "adp_ppr": 152.8, "expert_consensus_rank": 2},
            
            # Defenses
            {"name": "San Francisco 49ers", "position": PositionEnum.DEF, "team": "SF", "bye_week": 9, "projected_points_ppr": 9.2, "adp_ppr": 138.7, "expert_consensus_rank": 1},
            {"name": "Buffalo Bills", "position": PositionEnum.DEF, "team": "BUF", "bye_week": 12, "projected_points_ppr": 8.8, "adp_ppr": 142.1, "expert_consensus_rank": 2},
        ]
        
        created_count = 0
        for player_data in sample_players:
            # Calculate VORP (simple calculation for sample data)
            projected_points = player_data["projected_points_ppr"]
            if player_data["position"] == PositionEnum.QB:
                replacement_level = 18.0
            elif player_data["position"] == PositionEnum.RB:
                replacement_level = 12.0
            elif player_data["position"] == PositionEnum.WR:
                replacement_level = 10.0
            elif player_data["position"] == PositionEnum.TE:
                replacement_level = 8.0
            else:
                replacement_level = 6.0
            
            vorp = max(0, projected_points - replacement_level)
            
            player = Player(
                name=player_data["name"],
                position=player_data["position"],
                team=player_data["team"],
                bye_week=player_data["bye_week"],
                projected_points_ppr=projected_points,
                projected_points_half_ppr=projected_points * 0.95,
                projected_points_standard=projected_points * 0.85,
                adp_ppr=player_data["adp_ppr"],
                adp_half_ppr=player_data["adp_ppr"] * 1.1,
                adp_standard=player_data["adp_ppr"] * 1.2,
                vorp_ppr=vorp,
                vorp_half_ppr=vorp * 0.95,
                vorp_standard=vorp * 0.85,
                expert_consensus_rank=player_data["expert_consensus_rank"],
                positional_rank=player_data["expert_consensus_rank"]
            )
            
            db.add(player)
            created_count += 1
        
        db.commit()
        print(f"✅ Created {created_count} sample players successfully!")
        
    except Exception as e:
        print(f"❌ Error creating sample players: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    create_sample_players()
