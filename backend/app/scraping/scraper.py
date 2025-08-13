#!/usr/bin/env python3
"""
Fantasy Football Data Scraper Runner
Runs the scraper and ingests data into the database
"""

import sys
import os
import logging
from pathlib import Path

# Add the parent directory to the path so we can import app modules
sys.path.append(str(Path(__file__).parent.parent.parent))

from app.data.database import SessionLocal, create_tables
from app.data.ingestion import DataIngestionService
from app.utils.scraping import FantasyProsScraper

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def run_scraper():
    """Run the scraper and ingest data into the database"""
    logger.info("🚀 Starting Fantasy Football Data Scraper")
    
    try:
        # Ensure database tables exist
        logger.info("📋 Creating database tables if they don't exist...")
        create_tables()
        
        # Initialize scraper
        logger.info("🔍 Initializing FantasyPros scraper...")
        scraper = FantasyProsScraper()
        
        # Scrape all data
        logger.info("📊 Scraping player data from FantasyPros...")
        scraped_data = scraper.scrape_all_data()
        
        if not scraped_data:
            logger.warning("⚠️  No data scraped - this might be due to rate limiting or site changes")
            return False
        
        logger.info(f"✅ Successfully scraped {len(scraped_data)} player records")
        
        # Initialize database session and ingestion service
        db = SessionLocal()
        try:
            logger.info("💾 Starting data ingestion...")
            ingestion_service = DataIngestionService(db)
            
            # Ingest the scraped data
            stats = ingestion_service.ingest_player_data(scraped_data)
            
            logger.info(f"📈 Ingestion complete:")
            logger.info(f"   - Created: {stats['created']} players")
            logger.info(f"   - Updated: {stats['updated']} players")
            logger.info(f"   - Errors: {stats['errors']} players")
            
            if stats['errors'] > 0:
                logger.warning(f"⚠️  {stats['errors']} errors occurred during ingestion")
            
            logger.info("🎉 Data scraping and ingestion completed successfully!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error during data ingestion: {e}")
            return False
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"❌ Error during scraping: {e}")
        return False

if __name__ == "__main__":
    success = run_scraper()
    if success:
        logger.info("✅ Scraper completed successfully")
        sys.exit(0)
    else:
        logger.error("❌ Scraper failed")
        sys.exit(1)
