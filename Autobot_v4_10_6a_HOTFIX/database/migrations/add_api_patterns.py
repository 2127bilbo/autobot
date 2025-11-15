"""
Database Migration: Add API Patterns Table
Phase 1C - Smart API Learning

Adds table to store learned API patterns for fast product checks.
"""

import sqlite3
from datetime import datetime


def migrate(db_path: str = "autobot.db"):
    """
    Add learned_api_patterns table to database
    
    Table stores:
    - Site name
    - API endpoint pattern
    - JSON paths for price, stock, name, image
    - Success/failure statistics
    - Timestamps for learning and usage
    """
    print("[Migration] Adding API patterns table...")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create learned_api_patterns table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS learned_api_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                site TEXT UNIQUE NOT NULL,
                endpoint_pattern TEXT NOT NULL,
                price_path TEXT,
                stock_path TEXT,
                name_path TEXT,
                image_path TEXT,
                learned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                success_count INTEGER DEFAULT 0,
                failure_count INTEGER DEFAULT 0,
                last_used TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create index on site for fast lookups
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_api_patterns_site 
            ON learned_api_patterns(site)
        """)
        
        conn.commit()
        print("[Migration] ✅ API patterns table created successfully")
        
        # Test that table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='learned_api_patterns'
        """)
        
        if cursor.fetchone():
            print("[Migration] ✅ Table verification passed")
        else:
            print("[Migration] ⚠️  Table verification failed")
            return False
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"[Migration] ❌ Error: {e}")
        return False


def rollback(db_path: str = "autobot.db"):
    """
    Rollback migration - drop API patterns table
    """
    print("[Migration] Rolling back API patterns table...")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("DROP TABLE IF EXISTS learned_api_patterns")
        cursor.execute("DROP INDEX IF EXISTS idx_api_patterns_site")
        
        conn.commit()
        conn.close()
        
        print("[Migration] ✅ Rollback complete")
        return True
        
    except Exception as e:
        print(f"[Migration] ❌ Rollback error: {e}")
        return False


if __name__ == "__main__":
    # Run migration
    success = migrate()
    
    if success:
        print("\n[Migration] Phase 1C database migration complete!")
    else:
        print("\n[Migration] Migration failed!")
