"""
Database Migration: Add Speed Tracking
Phase 1B - Adaptive Speed Learning
Creates speed_history table to track learned intervals
"""

import sqlite3
from datetime import datetime


def upgrade(db_path: str = "autobot.db"):
    """
    Add speed_history table to track adaptive intervals
    
    Args:
        db_path: Path to database file
    """
    print("[MIGRATION] Adding speed_history table...")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Create speed_history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS speed_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                monitor_id TEXT NOT NULL UNIQUE,
                site TEXT NOT NULL,
                current_interval REAL DEFAULT 15.0,
                optimal_interval REAL DEFAULT 15.0,
                success_count INTEGER DEFAULT 0,
                ban_count INTEGER DEFAULT 0,
                consecutive_successes INTEGER DEFAULT 0,
                total_checks INTEGER DEFAULT 0,
                last_adjustment TEXT,
                last_success TEXT,
                last_ban TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create index for faster lookups
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_speed_site 
            ON speed_history(site)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_speed_monitor 
            ON speed_history(monitor_id)
        """)
        
        conn.commit()
        print("[MIGRATION] ✅ speed_history table created successfully")
        
        # Show table info
        cursor.execute("PRAGMA table_info(speed_history)")
        columns = cursor.fetchall()
        print(f"[MIGRATION] Table has {len(columns)} columns:")
        for col in columns:
            print(f"  - {col[1]} ({col[2]})")
        
    except Exception as e:
        print(f"[MIGRATION] ❌ Failed to create speed_history table: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


def downgrade(db_path: str = "autobot.db"):
    """
    Remove speed_history table
    
    Args:
        db_path: Path to database file
    """
    print("[MIGRATION] Removing speed_history table...")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        cursor.execute("DROP TABLE IF EXISTS speed_history")
        cursor.execute("DROP INDEX IF EXISTS idx_speed_site")
        cursor.execute("DROP INDEX IF EXISTS idx_speed_monitor")
        
        conn.commit()
        print("[MIGRATION] ✅ speed_history table removed")
        
    except Exception as e:
        print(f"[MIGRATION] ❌ Failed to remove speed_history table: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


def test_migration(db_path: str = "autobot.db"):
    """
    Test the migration by inserting and querying data
    
    Args:
        db_path: Path to database file
    """
    print("[MIGRATION] Testing speed_history table...")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Insert test data
        test_data = {
            'monitor_id': 'test_monitor_001',
            'site': 'target',
            'current_interval': 15.0,
            'optimal_interval': 15.0,
            'success_count': 0,
            'ban_count': 0
        }
        
        cursor.execute("""
            INSERT INTO speed_history 
            (monitor_id, site, current_interval, optimal_interval, success_count, ban_count)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            test_data['monitor_id'],
            test_data['site'],
            test_data['current_interval'],
            test_data['optimal_interval'],
            test_data['success_count'],
            test_data['ban_count']
        ))
        
        conn.commit()
        
        # Query it back
        cursor.execute("SELECT * FROM speed_history WHERE monitor_id = ?", 
                      (test_data['monitor_id'],))
        result = cursor.fetchone()
        
        if result:
            print("[MIGRATION] ✅ Test insert/query successful")
            print(f"[MIGRATION] Retrieved: monitor_id={result[1]}, site={result[2]}, interval={result[3]}")
            
            # Clean up test data
            cursor.execute("DELETE FROM speed_history WHERE monitor_id = ?", 
                          (test_data['monitor_id'],))
            conn.commit()
            print("[MIGRATION] ✅ Test data cleaned up")
        else:
            print("[MIGRATION] ⚠️  Test query returned no results")
        
    except Exception as e:
        print(f"[MIGRATION] ❌ Test failed: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    """Run migration when executed directly"""
    import sys
    
    db_path = "autobot.db"
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    
    print(f"[MIGRATION] Running speed tracking migration on {db_path}")
    print("=" * 60)
    
    try:
        upgrade(db_path)
        test_migration(db_path)
        print("=" * 60)
        print("[MIGRATION] ✅ Speed tracking migration completed successfully!")
    except Exception as e:
        print("=" * 60)
        print(f"[MIGRATION] ❌ Migration failed: {e}")
        sys.exit(1)
