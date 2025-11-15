#!/usr/bin/env python3
"""
Autobot v4.0 Database Migration
Upgrades database from v3.1.3 to v4.0
"""

import sqlite3
import sys
from pathlib import Path
from datetime import datetime

def upgrade_to_v4(db_path='autobot.db'):
    """Upgrade database to v4.0 schema"""
    
    print("=" * 60)
    print("AUTOBOT V4.0 DATABASE MIGRATION")
    print("=" * 60)
    print(f"\nDatabase: {db_path}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Backup database first
    backup_path = f"{db_path}.v3_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    print(f"Creating backup: {backup_path}")
    
    try:
        import shutil
        shutil.copy2(db_path, backup_path)
        print("✅ Backup created successfully\n")
    except Exception as e:
        print(f"⚠️  Warning: Could not create backup: {e}")
        response = input("Continue without backup? (yes/no): ")
        if response.lower() != 'yes':
            print("Migration cancelled.")
            return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if monitors table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='monitors'
        """)
        
        if not cursor.fetchone():
            print("📋 Creating monitors table...")
            cursor.execute("""
                CREATE TABLE monitors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_url TEXT NOT NULL,
                    site TEXT NOT NULL,
                    check_interval INTEGER DEFAULT 30,
                    status TEXT DEFAULT 'stopped',
                    product_name TEXT,
                    product_price REAL,
                    product_regular_price REAL,
                    last_check TIMESTAMP,
                    check_count INTEGER DEFAULT 0,
                    in_stock BOOLEAN DEFAULT 0,
                    is_preorder BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            print("✅ Monitors table created")
        else:
            print("✅ Monitors table already exists")
        
        # Add v4.0 specific columns to monitors table
        print("\n📋 Adding v4.0 columns to monitors table...")
        
        v4_columns = [
            ('target_price', 'REAL DEFAULT NULL', 'Target price for scalper detection'),
            ('show_stores', 'INTEGER DEFAULT 1', 'Show local store inventory'),
            ('show_rating', 'INTEGER DEFAULT 1', 'Show product rating'),
            ('show_promotions', 'INTEGER DEFAULT 1', 'Show active promotions'),
            ('zip_code', 'TEXT DEFAULT NULL', 'Zip code for local stores'),
            ('image_url', 'TEXT DEFAULT NULL', 'Cached product image URL'),
            ('cached_image_path', 'TEXT DEFAULT NULL', 'Local cached image path'),
            ('rating', 'REAL DEFAULT NULL', 'Product rating'),
            ('review_count', 'INTEGER DEFAULT 0', 'Number of reviews'),
        ]
        
        for col_name, col_type, description in v4_columns:
            try:
                cursor.execute(f'ALTER TABLE monitors ADD COLUMN {col_name} {col_type}')
                print(f"  ✅ Added: {col_name} - {description}")
            except sqlite3.OperationalError as e:
                if 'duplicate column name' in str(e).lower():
                    print(f"  ⚠️  Exists: {col_name}")
                else:
                    raise
        
        # Add v4.0 settings
        print("\n📋 Adding v4.0 settings...")
        
        v4_settings = [
            ('default_zip_code', '47401', 'Default zip code for all monitors'),
            ('show_images', '1', 'Show product images in UI'),
            ('show_scalper_detection', '1', 'Enable scalper price detection'),
            ('show_local_stores', '1', 'Show local store inventory'),
            ('show_ratings', '1', 'Show product ratings'),
            ('show_promotions', '1', 'Show active promotions'),
            ('enable_quick_links', '1', 'Enable quick links to products'),
            ('image_cache_enabled', '1', 'Enable local image caching'),
            ('v4_enabled', '1', 'v4.0 features enabled'),
            ('v4_migration_date', datetime.now().isoformat(), 'Date of v4.0 migration'),
        ]
        
        for key, value, description in v4_settings:
            cursor.execute("""
                INSERT OR IGNORE INTO settings (key, value) 
                VALUES (?, ?)
            """, (key, value))
            print(f"  ✅ {key}: {description}")
        
        # Commit all changes
        conn.commit()
        
        print("\n" + "=" * 60)
        print("✅ DATABASE MIGRATION COMPLETE!")
        print("=" * 60)
        print("\nChanges applied:")
        print("  • Monitors table ready for v4.0")
        print("  • 9 new columns added for enhanced features")
        print("  • 10 new settings configured")
        print(f"  • Backup saved: {backup_path}")
        print("\n🚀 Autobot v4.0 is ready to use!")
        print("=" * 60 + "\n")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR during migration: {e}")
        print(f"Database backup available at: {backup_path}")
        import traceback
        traceback.print_exc()
        return False

def verify_migration(db_path='autobot.db'):
    """Verify that migration was successful"""
    print("\n🔍 Verifying migration...")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check monitors table structure
    cursor.execute("PRAGMA table_info(monitors)")
    columns = {row[1] for row in cursor.fetchall()}
    
    required_columns = {
        'id', 'product_url', 'site', 'target_price', 'show_stores',
        'show_rating', 'show_promotions', 'zip_code', 'image_url'
    }
    
    missing = required_columns - columns
    if missing:
        print(f"⚠️  Missing columns: {missing}")
        return False
    
    # Check v4.0 settings
    cursor.execute("SELECT key FROM settings WHERE key LIKE 'v4_%' OR key = 'default_zip_code'")
    settings = {row[0] for row in cursor.fetchall()}
    
    if 'v4_enabled' not in settings:
        print("⚠️  v4.0 settings not found")
        return False
    
    print("✅ Migration verified successfully!")
    conn.close()
    return True

if __name__ == '__main__':
    # Get database path from command line or use default
    db_path = sys.argv[1] if len(sys.argv) > 1 else 'autobot.db'
    
    # Check if database exists
    if not Path(db_path).exists():
        print(f"❌ Database not found: {db_path}")
        print("Creating new database...")
    
    # Run migration
    success = upgrade_to_v4(db_path)
    
    if success:
        # Verify migration
        verify_migration(db_path)
        print("\n✅ You can now run Autobot v4.0!")
    else:
        print("\n❌ Migration failed. Check errors above.")
        sys.exit(1)
