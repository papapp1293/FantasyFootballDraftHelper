#!/usr/bin/env python3
"""
Script to clear and refresh all player data with improved parsing
"""

import sys
import os

# Add the app directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from app.utils.scraping import FantasyProsScraper
from app.data.database import SessionLocal
from app.data.ingestion import DataIngestionService
from app.data.models import Player

def refresh_all_data():
    """Clear existing data and re-scrape with improved parsing"""
    print("🔄 Refreshing Fantasy Football Data with Improved Parsing...")
    
    db = SessionLocal()
    try:
        # Clear existing player data
        print("🗑️ Clearing existing player data...")
        db.query(Player).delete()
        db.commit()
        print("✅ Existing data cleared")
        
        # Re-scrape with improved parsing
        print("📊 Re-scraping player data with improved parsing...")
        scraper = FantasyProsScraper()
        scraped_data = scraper.scrape_all_data()
        
        if not scraped_data:
            print("❌ No data scraped. Check scraper configuration.")
            return
        
        print(f"✅ Successfully scraped {len(scraped_data)} player records")
        
        # Show sample of improved parsing
        if scraped_data:
            print("\n📋 Sample of improved parsing:")
            for i, sample in enumerate(scraped_data[:5]):
                print(f"{i+1}. Name: '{sample.get('player_name')}' | Team: '{sample.get('team')}' | Bye: {sample.get('bye_week')}")
        
        # Ingest the data
        print("\n💾 Ingesting data with improved parsing...")
        ingestion_service = DataIngestionService(db)
        results = ingestion_service.full_data_refresh(scraped_data)
        
        print("✅ Data refresh completed!")
        print(f"📈 Results:")
        print(f"  - Created: {results['ingestion']['created']} players")
        print(f"  - Updated: {results['ingestion']['updated']} players")
        print(f"  - Errors: {results['ingestion']['errors']} players")
        print(f"  - VORP Calculated: {results['vorp_calculated']}")
        print(f"  - Scarcity Analyzed: {results['scarcity_analyzed']}")
        
    except Exception as e:
        print(f"❌ Error during data refresh: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    refresh_all_data()
