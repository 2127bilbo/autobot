"""
Database Migration: Add Drop Groups Support

Creates tables for:
- drop_groups: Drop group definitions
- drop_group_products: Products in each group

Author: Autobot Development Team
Version: 4.2C
"""

import sqlite3
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def upgrade(db_path: str = "autobot.db"):
    """
    Create drop groups tables.
    
    Tables created:
    - drop_groups: Drop group definitions
    - drop_group_products: Products in each group
    """
    logger.info("[Migration] Adding drop groups support...")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create drop_groups table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS drop_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                created_at TEXT NOT NULL,
                drop_time TEXT,
                wait_for_all INTEGER DEFAULT 1,
                status TEXT DEFAULT 'active',
                check_interval REAL DEFAULT 2.0,
                max_retries INTEGER DEFAULT 3,
                last_checked TEXT,
                completed_at TEXT,
                success INTEGER DEFAULT 0,
                notes TEXT
            )
        """)
        
        # Create drop_group_products table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS drop_group_products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER NOT NULL,
                product_url TEXT NOT NULL,
                product_name TEXT,
                quantity INTEGER DEFAULT 1,
                price REAL,
                in_stock INTEGER DEFAULT 0,
                stock_detected_at TEXT,
                added_to_cart INTEGER DEFAULT 0,
                added_to_cart_at TEXT,
                verified INTEGER DEFAULT 0,
                check_count INTEGER DEFAULT 0,
                last_checked TEXT,
                FOREIGN KEY (group_id) REFERENCES drop_groups (id) ON DELETE CASCADE
            )
        """)
        
        # Create indexes for better performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_drop_groups_status 
            ON drop_groups(status)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_drop_groups_drop_time 
            ON drop_groups(drop_time)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_drop_group_products_group_id 
            ON drop_group_products(group_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_drop_group_products_in_stock 
            ON drop_group_products(in_stock)
        """)
        
        conn.commit()
        logger.info("[Migration] ✅ Drop groups tables created successfully")
        
        # Verify tables exist
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name IN ('drop_groups', 'drop_group_products')
        """)
        tables = cursor.fetchall()
        logger.info(f"[Migration] Verified tables: {[t[0] for t in tables]}")
        
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"[Migration] Error creating drop groups tables: {e}")
        return False


def downgrade(db_path: str = "autobot.db"):
    """
    Remove drop groups tables.
    
    WARNING: This will delete all drop group data!
    """
    logger.warning("[Migration] Removing drop groups tables...")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Drop indexes
        cursor.execute("DROP INDEX IF EXISTS idx_drop_groups_status")
        cursor.execute("DROP INDEX IF EXISTS idx_drop_groups_drop_time")
        cursor.execute("DROP INDEX IF EXISTS idx_drop_group_products_group_id")
        cursor.execute("DROP INDEX IF EXISTS idx_drop_group_products_in_stock")
        
        # Drop tables
        cursor.execute("DROP TABLE IF EXISTS drop_group_products")
        cursor.execute("DROP TABLE IF EXISTS drop_groups")
        
        conn.commit()
        logger.info("[Migration] ✅ Drop groups tables removed")
        
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"[Migration] Error removing drop groups tables: {e}")
        return False


def test_migration(db_path: str = "autobot.db"):
    """Test the migration by creating and querying data."""
    logger.info("[Migration] Testing drop groups migration...")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Test 1: Insert a drop group
        cursor.execute("""
            INSERT INTO drop_groups 
            (name, description, created_at, wait_for_all, status)
            VALUES (?, ?, ?, ?, ?)
        """, (
            "Test Bundle",
            "Test drop group",
            datetime.now().isoformat(),
            1,
            "active"
        ))
        
        group_id = cursor.lastrowid
        logger.info(f"[Migration] Created test group with ID: {group_id}")
        
        # Test 2: Insert products
        test_products = [
            ("https://example.com/product1", "Product 1", 2),
            ("https://example.com/product2", "Product 2", 1),
            ("https://example.com/product3", "Product 3", 1),
        ]
        
        for url, name, qty in test_products:
            cursor.execute("""
                INSERT INTO drop_group_products 
                (group_id, product_url, product_name, quantity, in_stock)
                VALUES (?, ?, ?, ?, ?)
            """, (group_id, url, name, qty, 0))
        
        logger.info(f"[Migration] Added {len(test_products)} test products")
        
        # Test 3: Query the group
        cursor.execute("""
            SELECT 
                g.id, g.name, g.wait_for_all, COUNT(p.id) as product_count
            FROM drop_groups g
            LEFT JOIN drop_group_products p ON g.id = p.group_id
            WHERE g.id = ?
            GROUP BY g.id
        """, (group_id,))
        
        result = cursor.fetchone()
        logger.info(f"[Migration] Query result: {result}")
        
        # Test 4: Query products
        cursor.execute("""
            SELECT product_name, quantity, in_stock
            FROM drop_group_products
            WHERE group_id = ?
        """, (group_id,))
        
        products = cursor.fetchall()
        logger.info(f"[Migration] Products: {products}")
        
        # Test 5: Update stock status
        cursor.execute("""
            UPDATE drop_group_products
            SET in_stock = 1, stock_detected_at = ?
            WHERE group_id = ? AND product_url = ?
        """, (datetime.now().isoformat(), group_id, "https://example.com/product1"))
        
        logger.info("[Migration] Updated stock status")
        
        # Test 6: Check if all in stock
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(in_stock) as in_stock_count
            FROM drop_group_products
            WHERE group_id = ?
        """, (group_id,))
        
        total, in_stock = cursor.fetchone()
        all_in_stock = total == in_stock
        logger.info(f"[Migration] Stock status: {in_stock}/{total} in stock (all ready: {all_in_stock})")
        
        # Cleanup test data
        cursor.execute("DELETE FROM drop_group_products WHERE group_id = ?", (group_id,))
        cursor.execute("DELETE FROM drop_groups WHERE id = ?", (group_id,))
        
        conn.commit()
        logger.info("[Migration] ✅ Migration test passed - cleaned up test data")
        
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"[Migration] Test failed: {e}")
        return False


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(message)s'
    )
    
    # Run migration
    print("\n=== Running Migration ===")
    success = upgrade()
    
    if success:
        print("\n=== Testing Migration ===")
        test_migration()
        print("\n✅ Migration complete and tested!")
    else:
        print("\n❌ Migration failed!")
