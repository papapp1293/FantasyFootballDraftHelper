#!/usr/bin/env python3
"""
Database initialization script for Fantasy Football Draft Helper
This script creates all the necessary database tables.
"""

import sys
import os

# Add the app directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from app.data.database import create_tables

def main():
    """Initialize the database by creating all tables"""
    print("Initializing database...")
    try:
        create_tables()
        print("✅ Database tables created successfully!")
    except Exception as e:
        print(f"❌ Error creating database tables: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
