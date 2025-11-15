"""
Database Migration: Add Scheduled Drops Support
Phase 2A - Smart Drop Scheduling

This migration adds support for storing scheduled drops with all necessary metadata.

Author: Bob (Bloomfield, IN)
Created: November 12, 2025
"""

import sqlite3
from datetime import datetime


def upgrade(db_path: str = "autobot.db") -> None:
    """
    Add scheduled_drops table to store drop scheduling information.
    
    Args:
        db_path: Path to the SQLite database
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Create scheduled_drops table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scheduled_drops (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                monitor_id INTEGER NOT NULL,
                drop_time TEXT NOT NULL,
                timezone TEXT NOT NULL DEFAULT 'America/Indiana/Indianapolis',
                pre_drop_minutes INTEGER NOT NULL DEFAULT 5,
                aggressive_duration_minutes INTEGER NOT NULL DEFAULT 30,
                current_phase TEXT NOT NULL DEFAULT 'idle',
                phase_start_time TEXT,
                check_count INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                completed_at TEXT,
                FOREIGN KEY (monitor_id) REFERENCES monitors (id) ON DELETE CASCADE
            )
        """)
        
        # Create index on monitor_id for faster lookups
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_scheduled_drops_monitor 
            ON scheduled_drops(monitor_id)
        """)
        
        # Create index on drop_time for chronological queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_scheduled_drops_time 
            ON scheduled_drops(drop_time)
        """)
        
        # Create index on is_active for filtering active drops
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_scheduled_drops_active 
            ON scheduled_drops(is_active)
        """)
        
        # Add scheduled_drop_id column to monitors table (optional reference)
        try:
            cursor.execute("""
                ALTER TABLE monitors 
                ADD COLUMN scheduled_drop_id INTEGER 
                REFERENCES scheduled_drops(id) ON DELETE SET NULL
            """)
            print("[Migration] Added scheduled_drop_id to monitors table")
        except sqlite3.OperationalError:
            # Column already exists
            print("[Migration] scheduled_drop_id column already exists in monitors")
        
        conn.commit()
        print("[Migration] ✅ Successfully created scheduled_drops table")
        print("[Migration] ✅ Created indexes for performance")
        
    except Exception as e:
        conn.rollback()
        print(f"[Migration] ❌ Error during migration: {e}")
        raise
    
    finally:
        conn.close()


def downgrade(db_path: str = "autobot.db") -> None:
    """
    Remove scheduled_drops table (for rollback).
    
    Args:
        db_path: Path to the SQLite database
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Drop indexes first
        cursor.execute("DROP INDEX IF EXISTS idx_scheduled_drops_monitor")
        cursor.execute("DROP INDEX IF EXISTS idx_scheduled_drops_time")
        cursor.execute("DROP INDEX IF EXISTS idx_scheduled_drops_active")
        
        # Drop the table
        cursor.execute("DROP TABLE IF EXISTS scheduled_drops")
        
        conn.commit()
        print("[Migration] ✅ Successfully removed scheduled_drops table")
        
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
        # Check if scheduled_drops table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='scheduled_drops'
        """)
        
        if not cursor.fetchone():
            print("[Migration] ❌ scheduled_drops table not found")
            return False
        
        # Check table structure
        cursor.execute("PRAGMA table_info(scheduled_drops)")
        columns = {row[1] for row in cursor.fetchall()}
        
        required_columns = {
            'id', 'monitor_id', 'drop_time', 'timezone',
            'pre_drop_minutes', 'aggressive_duration_minutes',
            'current_phase', 'phase_start_time', 'check_count',
            'is_active', 'created_at', 'updated_at', 'completed_at'
        }
        
        if not required_columns.issubset(columns):
            missing = required_columns - columns
            print(f"[Migration] ❌ Missing columns: {missing}")
            return False
        
        # Check indexes
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='index' AND tbl_name='scheduled_drops'
        """)
        indexes = {row[0] for row in cursor.fetchall()}
        
        required_indexes = {
            'idx_scheduled_drops_monitor',
            'idx_scheduled_drops_time',
            'idx_scheduled_drops_active'
        }
        
        if not required_indexes.issubset(indexes):
            missing = required_indexes - indexes
            print(f"[Migration] ❌ Missing indexes: {missing}")
            return False
        
        print("[Migration] ✅ Migration verification passed")
        return True
        
    except Exception as e:
        print(f"[Migration] ❌ Error during verification: {e}")
        return False
    
    finally:
        conn.close()


# Database helper functions for scheduled drops
class ScheduledDropDB:
    """Helper class for scheduled drop database operations."""
    
    def __init__(self, db_path: str = "autobot.db"):
        self.db_path = db_path
    
    def create_scheduled_drop(
        self,
        monitor_id: int,
        drop_time: str,
        timezone: str = "America/Indiana/Indianapolis",
        pre_drop_minutes: int = 5,
        aggressive_duration_minutes: int = 30
    ) -> int:
        """
        Create a new scheduled drop.
        
        Args:
            monitor_id: ID of the monitor to schedule
            drop_time: Drop time (ISO format string)
            timezone: IANA timezone string
            pre_drop_minutes: Minutes before drop to start PRE_DROP phase
            aggressive_duration_minutes: Duration of AGGRESSIVE phase
            
        Returns:
            ID of the created scheduled drop
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            now = datetime.now().isoformat()
            
            cursor.execute("""
                INSERT INTO scheduled_drops 
                (monitor_id, drop_time, timezone, pre_drop_minutes, 
                 aggressive_duration_minutes, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (monitor_id, drop_time, timezone, pre_drop_minutes,
                  aggressive_duration_minutes, now, now))
            
            drop_id = cursor.lastrowid
            conn.commit()
            
            print(f"[ScheduledDropDB] Created scheduled drop #{drop_id} for monitor #{monitor_id}")
            return drop_id
            
        except Exception as e:
            conn.rollback()
            print(f"[ScheduledDropDB] Error creating scheduled drop: {e}")
            raise
        
        finally:
            conn.close()
    
    def update_phase(self, drop_id: int, phase: str, check_count: int = 0) -> None:
        """
        Update the current phase of a scheduled drop.
        
        Args:
            drop_id: ID of the scheduled drop
            phase: New phase name
            check_count: Current check count
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            now = datetime.now().isoformat()
            
            cursor.execute("""
                UPDATE scheduled_drops 
                SET current_phase = ?,
                    phase_start_time = ?,
                    check_count = ?,
                    updated_at = ?
                WHERE id = ?
            """, (phase, now, check_count, now, drop_id))
            
            conn.commit()
            
        except Exception as e:
            conn.rollback()
            print(f"[ScheduledDropDB] Error updating phase: {e}")
            raise
        
        finally:
            conn.close()
    
    def complete_drop(self, drop_id: int) -> None:
        """
        Mark a scheduled drop as completed.
        
        Args:
            drop_id: ID of the scheduled drop
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            now = datetime.now().isoformat()
            
            cursor.execute("""
                UPDATE scheduled_drops 
                SET is_active = 0,
                    completed_at = ?,
                    updated_at = ?
                WHERE id = ?
            """, (now, now, drop_id))
            
            conn.commit()
            print(f"[ScheduledDropDB] Completed scheduled drop #{drop_id}")
            
        except Exception as e:
            conn.rollback()
            print(f"[ScheduledDropDB] Error completing drop: {e}")
            raise
        
        finally:
            conn.close()
    
    def get_active_drops(self) -> list:
        """
        Get all active scheduled drops.
        
        Returns:
            List of active scheduled drop records
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT * FROM scheduled_drops 
                WHERE is_active = 1
                ORDER BY drop_time ASC
            """)
            
            return [dict(row) for row in cursor.fetchall()]
            
        finally:
            conn.close()
    
    def get_drop_by_monitor(self, monitor_id: int) -> dict:
        """
        Get the active scheduled drop for a monitor.
        
        Args:
            monitor_id: ID of the monitor
            
        Returns:
            Scheduled drop record or None
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT * FROM scheduled_drops 
                WHERE monitor_id = ? AND is_active = 1
                ORDER BY created_at DESC
                LIMIT 1
            """, (monitor_id,))
            
            row = cursor.fetchone()
            return dict(row) if row else None
            
        finally:
            conn.close()


# Run migration if executed directly
if __name__ == "__main__":
    print("Running scheduled_drops migration...")
    
    # Upgrade
    upgrade()
    
    # Verify
    if verify_migration():
        print("\n✅ Migration completed successfully!")
    else:
        print("\n❌ Migration verification failed!")
