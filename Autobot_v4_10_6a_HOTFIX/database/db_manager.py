"""
Autobot Database Module
SQLite-based storage for profiles, proxies, settings, and task history
"""

import sqlite3
import json
from typing import List, Dict, Optional
from pathlib import Path
from datetime import datetime
import threading


class DatabaseManager:
    """
    Central database manager using SQLite
    Handles profiles, proxies, settings, and task history
    """
    
    def __init__(self, db_path: str = "autobot.db"):
        self.db_path = db_path
        self.lock = threading.Lock()
        self._init_database()
    
    def _get_connection(self):
        """Get a database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_database(self):
        """Initialize database tables"""
        with self.lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Profiles table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    email TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    address_line1 TEXT,
                    address_line2 TEXT,
                    city TEXT,
                    state TEXT,
                    zip_code TEXT,
                    country TEXT,
                    phone TEXT,
                    card_number TEXT,
                    card_month TEXT,
                    card_year TEXT,
                    card_cvv TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Proxies table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS proxies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    proxy_string TEXT NOT NULL,
                    type TEXT DEFAULT 'http',
                    active BOOLEAN DEFAULT 1,
                    success_count INTEGER DEFAULT 0,
                    fail_count INTEGER DEFAULT 0,
                    last_used TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Settings table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Task history table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS task_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT UNIQUE,
                    site TEXT,
                    product_url TEXT,
                    product_name TEXT,
                    product_price REAL,
                    status TEXT,
                    profile_name TEXT,
                    proxy TEXT,
                    mode TEXT,
                    start_time TIMESTAMP,
                    end_time TIMESTAMP,
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Initialize default settings
            default_settings = {
                'webhook_url': '',
                'webhook_enabled': 'false',
                'headless_mode': 'false',
                'retry_limit': '3',
                'monitor_delay': '5000',
                'price_tolerance': '10',
                'theme': 'dark_purple'
            }
            
            for key, value in default_settings.items():
                cursor.execute("""
                    INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)
                """, (key, value))
            
            conn.commit()
            conn.close()
    
    # ============ PROFILE METHODS ============
    
    def add_profile(self, profile_data: Dict) -> int:
        """Add a new profile"""
        with self.lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO profiles (
                    name, email, first_name, last_name,
                    address_line1, address_line2, city, state, zip_code, country,
                    phone, card_number, card_month, card_year, card_cvv
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                profile_data.get('name'),
                profile_data.get('email'),
                profile_data.get('first_name'),
                profile_data.get('last_name'),
                profile_data.get('address_line1'),
                profile_data.get('address_line2'),
                profile_data.get('city'),
                profile_data.get('state'),
                profile_data.get('zip_code'),
                profile_data.get('country'),
                profile_data.get('phone'),
                profile_data.get('card_number'),
                profile_data.get('card_month'),
                profile_data.get('card_year'),
                profile_data.get('card_cvv')
            ))
            
            profile_id = cursor.lastrowid
            conn.commit()
            conn.close()
            return profile_id
    
    def get_profile(self, name: str) -> Optional[Dict]:
        """Get a profile by name"""
        with self.lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM profiles WHERE name = ?", (name,))
            row = cursor.fetchone()
            conn.close()
            
            return dict(row) if row else None
    
    def get_all_profiles(self) -> List[Dict]:
        """Get all profiles"""
        with self.lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM profiles ORDER BY name")
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows]
    
    def update_profile(self, name: str, profile_data: Dict):
        """Update an existing profile"""
        with self.lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE profiles SET
                    email = ?, first_name = ?, last_name = ?,
                    address_line1 = ?, address_line2 = ?,
                    city = ?, state = ?, zip_code = ?, country = ?,
                    phone = ?, card_number = ?, card_month = ?, card_year = ?, card_cvv = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE name = ?
            """, (
                profile_data.get('email'),
                profile_data.get('first_name'),
                profile_data.get('last_name'),
                profile_data.get('address_line1'),
                profile_data.get('address_line2'),
                profile_data.get('city'),
                profile_data.get('state'),
                profile_data.get('zip_code'),
                profile_data.get('country'),
                profile_data.get('phone'),
                profile_data.get('card_number'),
                profile_data.get('card_month'),
                profile_data.get('card_year'),
                profile_data.get('card_cvv'),
                name
            ))
            
            conn.commit()
            conn.close()
    
    def delete_profile(self, name: str):
        """Delete a profile"""
        with self.lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM profiles WHERE name = ?", (name,))
            conn.commit()
            conn.close()
    
    # ============ PROXY METHODS ============
    
    def add_proxy(self, proxy_string: str, proxy_type: str = 'http') -> int:
        """Add a new proxy"""
        with self.lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO proxies (proxy_string, type) VALUES (?, ?)
            """, (proxy_string, proxy_type))
            
            proxy_id = cursor.lastrowid
            conn.commit()
            conn.close()
            return proxy_id
    
    def add_proxies_bulk(self, proxy_list: List[str], proxy_type: str = 'http'):
        """Add multiple proxies at once"""
        with self.lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            for proxy in proxy_list:
                cursor.execute("""
                    INSERT OR IGNORE INTO proxies (proxy_string, type) VALUES (?, ?)
                """, (proxy.strip(), proxy_type))
            
            conn.commit()
            conn.close()
    
    def get_all_proxies(self, active_only: bool = False) -> List[Dict]:
        """Get all proxies"""
        with self.lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            query = "SELECT * FROM proxies"
            if active_only:
                query += " WHERE active = 1"
            query += " ORDER BY id"
            
            cursor.execute(query)
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows]
    
    def update_proxy_stats(self, proxy_string: str, success: bool):
        """Update proxy statistics after use"""
        with self.lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            if success:
                cursor.execute("""
                    UPDATE proxies SET
                        success_count = success_count + 1,
                        last_used = CURRENT_TIMESTAMP
                    WHERE proxy_string = ?
                """, (proxy_string,))
            else:
                cursor.execute("""
                    UPDATE proxies SET
                        fail_count = fail_count + 1,
                        last_used = CURRENT_TIMESTAMP
                    WHERE proxy_string = ?
                """, (proxy_string,))
            
            conn.commit()
            conn.close()
    
    def delete_proxy(self, proxy_id: int):
        """Delete a proxy"""
        with self.lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM proxies WHERE id = ?", (proxy_id,))
            conn.commit()
            conn.close()
    
    def clear_all_proxies(self):
        """Delete all proxies"""
        with self.lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM proxies")
            conn.commit()
            conn.close()
    
    # ============ SETTINGS METHODS ============
    
    def get_setting(self, key: str) -> Optional[str]:
        """Get a setting value"""
        with self.lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            conn.close()
            
            return row['value'] if row else None
    
    def set_setting(self, key: str, value: str):
        """Set a setting value"""
        with self.lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO settings (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            """, (key, value))
            
            conn.commit()
            conn.close()
    
    def get_all_settings(self) -> Dict:
        """Get all settings as a dictionary"""
        with self.lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT key, value FROM settings")
            rows = cursor.fetchall()
            conn.close()
            
            return {row['key']: row['value'] for row in rows}
    
    def get_settings(self) -> Dict:
        """Get all settings (alias for UI compatibility)"""
        settings = self.get_all_settings()
        # Convert string values to appropriate types
        result = {}
        for key, value in settings.items():
            if key in ['headless', 'webhook_enabled']:
                result[key] = value.lower() == 'true' if isinstance(value, str) else bool(value)
            elif key in ['price_tolerance', 'max_retries', 'monitor_delay']:
                try:
                    result[key] = float(value) if '.' in str(value) else int(value)
                except:
                    result[key] = value
            else:
                result[key] = value
        return result
    
    def save_settings(self, settings: Dict):
        """Save multiple settings at once"""
        for key, value in settings.items():
            # Convert boolean and numeric values to strings for storage
            if isinstance(value, bool):
                value = 'true' if value else 'false'
            elif isinstance(value, (int, float)):
                value = str(value)
            self.set_setting(key, value)
    
    # ============ TASK HISTORY METHODS ============
    
    def save_task_result(self, task_data: Dict):
        """Save task execution result to history"""
        with self.lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO task_history (
                    task_id, site, product_url, product_name, product_price,
                    status, profile_name, proxy, mode,
                    start_time, end_time, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                task_data.get('task_id'),
                task_data.get('site'),
                task_data.get('product_url'),
                task_data.get('product_name'),
                task_data.get('product_price'),
                task_data.get('status'),
                task_data.get('profile_name'),
                task_data.get('proxy'),
                task_data.get('mode'),
                task_data.get('start_time'),
                task_data.get('end_time'),
                task_data.get('error_message')
            ))
            
            conn.commit()
            conn.close()
    
    def get_task_history(self, limit: int = 100) -> List[Dict]:
        """Get recent task history"""
        with self.lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM task_history
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))
            
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows]
    
    def clear_task_history(self):
        """Clear all task history"""
        with self.lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM task_history")
            conn.commit()
            conn.close()
    
    # ============================================
    # Phase 1C: API Pattern Methods
    # ============================================
    
    def save_api_pattern(self, pattern: Dict):
        """
        Save or update learned API pattern
        
        Args:
            pattern: Dict with site, endpoint_pattern, and JSON paths
        """
        with self.lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Check if pattern exists for this site
            cursor.execute("""
                SELECT id FROM learned_api_patterns WHERE site = ?
            """, (pattern['site'],))
            
            existing = cursor.fetchone()
            
            if existing:
                # Update existing pattern
                cursor.execute("""
                    UPDATE learned_api_patterns
                    SET endpoint_pattern = ?,
                        price_path = ?,
                        stock_path = ?,
                        name_path = ?,
                        image_path = ?,
                        learned_at = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE site = ?
                """, (
                    pattern['endpoint_pattern'],
                    pattern.get('price_path'),
                    pattern.get('stock_path'),
                    pattern.get('name_path'),
                    pattern.get('image_path'),
                    pattern['learned_at'],
                    pattern['site']
                ))
            else:
                # Insert new pattern
                cursor.execute("""
                    INSERT INTO learned_api_patterns (
                        site, endpoint_pattern, price_path, stock_path,
                        name_path, image_path, learned_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    pattern['site'],
                    pattern['endpoint_pattern'],
                    pattern.get('price_path'),
                    pattern.get('stock_path'),
                    pattern.get('name_path'),
                    pattern.get('image_path'),
                    pattern['learned_at']
                ))
            
            conn.commit()
            conn.close()
    
    def get_api_pattern(self, site: str) -> Optional[Dict]:
        """
        Get learned API pattern for a site
        
        Args:
            site: Site name (target, walmart, etc.)
        
        Returns:
            Pattern dict or None if not found
        """
        with self.lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM learned_api_patterns WHERE site = ?
            """, (site,))
            
            row = cursor.fetchone()
            conn.close()
            
            return dict(row) if row else None
    
    def get_api_patterns(self) -> List[Dict]:
        """Get all learned API patterns"""
        with self.lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM learned_api_patterns")
            
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows]
    
    def update_api_pattern_stats(self, site: str, success: bool):
        """
        Update API pattern success/failure statistics
        
        Args:
            site: Site name
            success: True if API check succeeded, False otherwise
        """
        with self.lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            if success:
                cursor.execute("""
                    UPDATE learned_api_patterns
                    SET success_count = success_count + 1,
                        last_used = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE site = ?
                """, (site,))
            else:
                cursor.execute("""
                    UPDATE learned_api_patterns
                    SET failure_count = failure_count + 1,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE site = ?
                """, (site,))
            
            conn.commit()
            conn.close()
    
    def delete_api_pattern(self, site: str):
        """
        Delete learned API pattern for a site
        
        Args:
            site: Site name
        """
        with self.lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM learned_api_patterns WHERE site = ?", (site,))
            
            conn.commit()
            conn.close()


# Global database instance
db = DatabaseManager()
