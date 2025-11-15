"""
Database Migration: Add Ban Tracking
Phase 1A - Task 1A.2.1
Creates ban_history table for tracking ban events and recovery
"""

def upgrade(db):
    """
    Add ban tracking table
    
    Args:
        db: Database connection object
    """
    cursor = db.cursor()
    
    # Create ban_history table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ban_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            monitor_id TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            ban_type TEXT NOT NULL,
            ban_count INTEGER DEFAULT 1,
            cooldown_applied INTEGER DEFAULT 0,
            recovery_time REAL,
            status TEXT DEFAULT 'detected',
            FOREIGN KEY (monitor_id) REFERENCES monitors(id) ON DELETE CASCADE
        )
    """)
    
    # Create index for faster lookups
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_ban_monitor 
        ON ban_history(monitor_id, timestamp DESC)
    """)
    
    # Create index for analytics
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_ban_timestamp
        ON ban_history(timestamp DESC)
    """)
    
    db.commit()
    print("[MIGRATION] Ban tracking tables created successfully")


def downgrade(db):
    """
    Remove ban tracking table
    
    Args:
        db: Database connection object
    """
    cursor = db.cursor()
    
    cursor.execute("DROP INDEX IF EXISTS idx_ban_timestamp")
    cursor.execute("DROP INDEX IF EXISTS idx_ban_monitor")
    cursor.execute("DROP TABLE IF EXISTS ban_history")
    
    db.commit()
    print("[MIGRATION] Ban tracking tables removed")


# Migration metadata
MIGRATION_NAME = "add_ban_tracking"
MIGRATION_VERSION = "1A.2"
MIGRATION_DESCRIPTION = "Add ban detection and recovery tracking"
