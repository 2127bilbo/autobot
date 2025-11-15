"""
Database Migration: Add Checkout Tracking Support
Phase 2B - Smart Checkout

This migration adds tables for:
- Learned checkout patterns
- Checkout attempt tracking
- Success/failure statistics

Author: Bob (Bloomfield, IN)
Created: November 12, 2025
"""

import sqlite3
from datetime import datetime


def upgrade(db_path: str = "autobot.db") -> None:
    """
    Add checkout tracking tables.
    
    Args:
        db_path: Path to the SQLite database
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Create learned_checkout_patterns table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS learned_checkout_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                site_url TEXT NOT NULL UNIQUE,
                pattern TEXT NOT NULL,
                learned_at TEXT NOT NULL,
                last_validated TEXT NOT NULL,
                success_count INTEGER NOT NULL DEFAULT 0,
                failure_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        
        # Create index on site_url
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_checkout_patterns_site 
            ON learned_checkout_patterns(site_url)
        """)
        
        # Create checkout_attempts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS checkout_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                monitor_id INTEGER NOT NULL,
                product_url TEXT NOT NULL,
                method TEXT NOT NULL,
                attempt_number INTEGER NOT NULL,
                result TEXT NOT NULL,
                error_message TEXT,
                duration_seconds REAL,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (monitor_id) REFERENCES monitors (id) ON DELETE CASCADE
            )
        """)
        
        # Create indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_checkout_attempts_monitor 
            ON checkout_attempts(monitor_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_checkout_attempts_timestamp 
            ON checkout_attempts(timestamp)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_checkout_attempts_result 
            ON checkout_attempts(result)
        """)
        
        # Create checkout_statistics table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS checkout_statistics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                site_url TEXT NOT NULL,
                total_attempts INTEGER NOT NULL DEFAULT 0,
                successful_attempts INTEGER NOT NULL DEFAULT 0,
                failed_attempts INTEGER NOT NULL DEFAULT 0,
                api_wins INTEGER NOT NULL DEFAULT 0,
                browser_wins INTEGER NOT NULL DEFAULT 0,
                average_api_time REAL,
                average_browser_time REAL,
                last_success TEXT,
                last_failure TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(site_url)
            )
        """)
        
        # Create index on site_url
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_checkout_stats_site 
            ON checkout_statistics(site_url)
        """)
        
        conn.commit()
        print("[Migration] ✅ Successfully created checkout tracking tables")
        print("[Migration] ✅ Created learned_checkout_patterns table")
        print("[Migration] ✅ Created checkout_attempts table")
        print("[Migration] ✅ Created checkout_statistics table")
        print("[Migration] ✅ Created indexes for performance")
        
    except Exception as e:
        conn.rollback()
        print(f"[Migration] ❌ Error during migration: {e}")
        raise
    
    finally:
        conn.close()


def downgrade(db_path: str = "autobot.db") -> None:
    """
    Remove checkout tracking tables (for rollback).
    
    Args:
        db_path: Path to the SQLite database
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Drop indexes
        cursor.execute("DROP INDEX IF EXISTS idx_checkout_patterns_site")
        cursor.execute("DROP INDEX IF EXISTS idx_checkout_attempts_monitor")
        cursor.execute("DROP INDEX IF EXISTS idx_checkout_attempts_timestamp")
        cursor.execute("DROP INDEX IF EXISTS idx_checkout_attempts_result")
        cursor.execute("DROP INDEX IF EXISTS idx_checkout_stats_site")
        
        # Drop tables
        cursor.execute("DROP TABLE IF EXISTS checkout_attempts")
        cursor.execute("DROP TABLE IF EXISTS learned_checkout_patterns")
        cursor.execute("DROP TABLE IF EXISTS checkout_statistics")
        
        conn.commit()
        print("[Migration] ✅ Successfully removed checkout tracking tables")
        
    except Exception as e:
        conn.rollback()
        print(f"[Migration] ❌ Error during downgrade: {e}")
        raise
    
    finally:
        conn.close()


def verify_migration(db_path: str = "autobot.db") -> bool:
    """
    Verify that the migration was successful.
    
    Args:
        db_path: Path to the SQLite database
        
    Returns:
        True if migration is complete and valid
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check tables exist
        required_tables = [
            'learned_checkout_patterns',
            'checkout_attempts',
            'checkout_statistics'
        ]
        
        for table in required_tables:
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name=?
            """, (table,))
            
            if not cursor.fetchone():
                print(f"[Migration] ❌ Table '{table}' not found")
                return False
        
        print("[Migration] ✅ All tables exist")
        
        # Check learned_checkout_patterns columns
        cursor.execute("PRAGMA table_info(learned_checkout_patterns)")
        pattern_columns = {row[1] for row in cursor.fetchall()}
        required_pattern_cols = {
            'id', 'site_url', 'pattern', 'learned_at', 'last_validated',
            'success_count', 'failure_count', 'created_at', 'updated_at'
        }
        
        if not required_pattern_cols.issubset(pattern_columns):
            print(f"[Migration] ❌ Missing columns in learned_checkout_patterns")
            return False
        
        # Check checkout_attempts columns
        cursor.execute("PRAGMA table_info(checkout_attempts)")
        attempts_columns = {row[1] for row in cursor.fetchall()}
        required_attempts_cols = {
            'id', 'monitor_id', 'product_url', 'method', 'attempt_number',
            'result', 'error_message', 'duration_seconds', 'timestamp'
        }
        
        if not required_attempts_cols.issubset(attempts_columns):
            print(f"[Migration] ❌ Missing columns in checkout_attempts")
            return False
        
        # Check checkout_statistics columns
        cursor.execute("PRAGMA table_info(checkout_statistics)")
        stats_columns = {row[1] for row in cursor.fetchall()}
        required_stats_cols = {
            'id', 'site_url', 'total_attempts', 'successful_attempts',
            'failed_attempts', 'api_wins', 'browser_wins',
            'average_api_time', 'average_browser_time',
            'last_success', 'last_failure', 'created_at', 'updated_at'
        }
        
        if not required_stats_cols.issubset(stats_columns):
            print(f"[Migration] ❌ Missing columns in checkout_statistics")
            return False
        
        print("[Migration] ✅ All columns present")
        print("[Migration] ✅ Migration verification passed")
        return True
        
    except Exception as e:
        print(f"[Migration] ❌ Error during verification: {e}")
        return False
    
    finally:
        conn.close()


# Helper class for checkout database operations
class CheckoutDB:
    """Helper class for checkout database operations"""
    
    def __init__(self, db_path: str = "autobot.db"):
        self.db_path = db_path
    
    def log_attempt(
        self,
        monitor_id: int,
        product_url: str,
        method: str,
        attempt_number: int,
        result: str,
        error_message: str = None,
        duration_seconds: float = None
    ) -> int:
        """Log a checkout attempt"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            now = datetime.now().isoformat()
            
            cursor.execute("""
                INSERT INTO checkout_attempts 
                (monitor_id, product_url, method, attempt_number, result, 
                 error_message, duration_seconds, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (monitor_id, product_url, method, attempt_number, result,
                  error_message, duration_seconds, now))
            
            attempt_id = cursor.lastrowid
            conn.commit()
            
            return attempt_id
            
        except Exception as e:
            conn.rollback()
            print(f"[CheckoutDB] Error logging attempt: {e}")
            raise
        
        finally:
            conn.close()
    
    def update_statistics(
        self,
        site_url: str,
        method: str,
        success: bool,
        duration: float = None
    ) -> None:
        """Update checkout statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            now = datetime.now().isoformat()
            
            # Check if stats exist
            cursor.execute("""
                SELECT id, total_attempts, successful_attempts, failed_attempts,
                       api_wins, browser_wins, average_api_time, average_browser_time
                FROM checkout_statistics 
                WHERE site_url = ?
            """, (site_url,))
            
            row = cursor.fetchone()
            
            if row:
                # Update existing
                stats_id, total, successful, failed, api_wins, browser_wins, avg_api, avg_browser = row
                
                total += 1
                if success:
                    successful += 1
                    if method == 'api':
                        api_wins += 1
                        if duration and avg_api:
                            avg_api = (avg_api * (api_wins - 1) + duration) / api_wins
                        elif duration:
                            avg_api = duration
                    elif method == 'browser':
                        browser_wins += 1
                        if duration and avg_browser:
                            avg_browser = (avg_browser * (browser_wins - 1) + duration) / browser_wins
                        elif duration:
                            avg_browser = duration
                else:
                    failed += 1
                
                cursor.execute("""
                    UPDATE checkout_statistics 
                    SET total_attempts = ?,
                        successful_attempts = ?,
                        failed_attempts = ?,
                        api_wins = ?,
                        browser_wins = ?,
                        average_api_time = ?,
                        average_browser_time = ?,
                        last_success = CASE WHEN ? THEN ? ELSE last_success END,
                        last_failure = CASE WHEN NOT ? THEN ? ELSE last_failure END,
                        updated_at = ?
                    WHERE site_url = ?
                """, (total, successful, failed, api_wins, browser_wins,
                      avg_api, avg_browser, success, now, success, now, now, site_url))
            else:
                # Insert new
                cursor.execute("""
                    INSERT INTO checkout_statistics 
                    (site_url, total_attempts, successful_attempts, failed_attempts,
                     api_wins, browser_wins, average_api_time, average_browser_time,
                     last_success, last_failure, created_at, updated_at)
                    VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (site_url, 1 if success else 0, 0 if success else 1,
                      1 if (success and method == 'api') else 0,
                      1 if (success and method == 'browser') else 0,
                      duration if method == 'api' else None,
                      duration if method == 'browser' else None,
                      now if success else None,
                      now if not success else None,
                      now, now))
            
            conn.commit()
            
        except Exception as e:
            conn.rollback()
            print(f"[CheckoutDB] Error updating statistics: {e}")
            raise
        
        finally:
            conn.close()


# Run migration if executed directly
if __name__ == "__main__":
    print("Running checkout tracking migration...")
    
    # Upgrade
    upgrade()
    
    # Verify
    if verify_migration():
        print("\n✅ Migration completed successfully!")
    else:
        print("\n❌ Migration verification failed!")
