"""
Autobot Account Pool - Phase 3B
Multi-account management with rotation and session isolation

This module manages multiple accounts for the bot:
- Account rotation for load distribution
- Session isolation per account
- Success/failure tracking per account
- Auto-switch on ban detection
- Account health monitoring

Author: Bob (Bloomfield, IN)
Created: November 13, 2025
"""

import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import threading
import random


class Account:
    """
    Represents a single account with tracking.
    """
    
    def __init__(
        self,
        account_id: int,
        name: str,
        email: str,
        profile_id: Optional[int] = None,
        proxy_id: Optional[int] = None,
        site: Optional[str] = None
    ):
        self.id = account_id
        self.name = name
        self.email = email
        self.profile_id = profile_id
        self.proxy_id = proxy_id
        self.site = site
        
        # Statistics
        self.success_count = 0
        self.failure_count = 0
        self.ban_count = 0
        self.last_used = None
        self.last_ban = None
        self.is_banned = False
        self.cooldown_until = None
        
        # Session data
        self.session_data = {}
        self.cookies = {}
        
    def __repr__(self):
        return f"Account({self.name}, successes={self.success_count}, bans={self.ban_count})"
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate (0-1)."""
        total = self.success_count + self.failure_count
        if total == 0:
            return 0.0
        return self.success_count / total
    
    @property
    def health_score(self) -> float:
        """
        Calculate overall account health (0-1).
        
        Factors:
        - Success rate (50%)
        - Ban frequency (30%)
        - Recent activity (20%)
        """
        # Success rate component
        success_component = self.success_rate * 0.5
        
        # Ban frequency component (inverse - fewer bans = better)
        total_uses = self.success_count + self.failure_count
        if total_uses > 0:
            ban_rate = self.ban_count / total_uses
            ban_component = (1 - min(ban_rate, 1.0)) * 0.3
        else:
            ban_component = 0.3
        
        # Recent activity component
        if self.last_used:
            hours_since_use = (datetime.now() - self.last_used).total_seconds() / 3600
            if hours_since_use < 24:
                activity_component = 0.2
            elif hours_since_use < 168:  # 1 week
                activity_component = 0.15
            else:
                activity_component = 0.1
        else:
            activity_component = 0.1
        
        return success_component + ban_component + activity_component
    
    def is_available(self) -> bool:
        """Check if account is available for use."""
        if self.is_banned and self.cooldown_until:
            if datetime.now() < self.cooldown_until:
                return False
            else:
                # Cooldown expired
                self.is_banned = False
                self.cooldown_until = None
        
        return not self.is_banned


class AccountPool:
    """
    Manages a pool of accounts with rotation and health tracking.
    
    Features:
    - Multiple account support
    - Automatic rotation strategies
    - Ban detection and cooldown
    - Session isolation
    - Performance tracking
    """
    
    def __init__(self, db_path: str = "autobot.db"):
        self.db_path = db_path
        self.lock = threading.Lock()
        self.accounts: Dict[int, Account] = {}
        self._ensure_tables()
        self._load_accounts()
    
    def _ensure_tables(self):
        """Create account pool tables if they don't exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Accounts table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS account_pool (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    email TEXT NOT NULL,
                    profile_id INTEGER,
                    proxy_id INTEGER,
                    site TEXT,
                    success_count INTEGER DEFAULT 0,
                    failure_count INTEGER DEFAULT 0,
                    ban_count INTEGER DEFAULT 0,
                    last_used TEXT,
                    last_ban TEXT,
                    is_banned INTEGER DEFAULT 0,
                    cooldown_until TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (profile_id) REFERENCES profiles(id),
                    FOREIGN KEY (proxy_id) REFERENCES proxies(id)
                )
            """)
            
            # Account usage history
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS account_usage_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id INTEGER NOT NULL,
                    monitor_id INTEGER,
                    action TEXT NOT NULL,
                    result TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    details TEXT,
                    FOREIGN KEY (account_id) REFERENCES account_pool(id)
                )
            """)
            
            # Indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_account_pool_site 
                ON account_pool(site)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_account_usage_account 
                ON account_usage_history(account_id)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_account_usage_timestamp 
                ON account_usage_history(timestamp)
            """)
            
            conn.commit()
            
        except Exception as e:
            conn.rollback()
            print(f"[AccountPool] Error creating tables: {e}")
        
        finally:
            conn.close()
    
    def _load_accounts(self):
        """Load accounts from database."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT * FROM account_pool")
            rows = cursor.fetchall()
            
            for row in rows:
                account = Account(
                    account_id=row['id'],
                    name=row['name'],
                    email=row['email'],
                    profile_id=row['profile_id'],
                    proxy_id=row['proxy_id'],
                    site=row['site']
                )
                
                account.success_count = row['success_count']
                account.failure_count = row['failure_count']
                account.ban_count = row['ban_count']
                account.is_banned = bool(row['is_banned'])
                
                if row['last_used']:
                    account.last_used = datetime.fromisoformat(row['last_used'])
                if row['last_ban']:
                    account.last_ban = datetime.fromisoformat(row['last_ban'])
                if row['cooldown_until']:
                    account.cooldown_until = datetime.fromisoformat(row['cooldown_until'])
                
                self.accounts[account.id] = account
            
            print(f"[AccountPool] Loaded {len(self.accounts)} accounts")
            
        finally:
            conn.close()
    
    def add_account(
        self,
        name: str,
        email: str,
        profile_id: Optional[int] = None,
        proxy_id: Optional[int] = None,
        site: Optional[str] = None
    ) -> int:
        """
        Add a new account to the pool.
        
        Args:
            name: Account name/identifier
            email: Account email
            profile_id: Associated profile ID
            proxy_id: Associated proxy ID
            site: Site this account is for (optional)
            
        Returns:
            Account ID
        """
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            try:
                now = datetime.now().isoformat()
                
                cursor.execute("""
                    INSERT INTO account_pool 
                    (name, email, profile_id, proxy_id, site, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (name, email, profile_id, proxy_id, site, now, now))
                
                account_id = cursor.lastrowid
                conn.commit()
                
                # Create Account object
                account = Account(
                    account_id=account_id,
                    name=name,
                    email=email,
                    profile_id=profile_id,
                    proxy_id=proxy_id,
                    site=site
                )
                
                self.accounts[account_id] = account
                
                print(f"[AccountPool] Added account: {name} (ID: {account_id})")
                return account_id
                
            except Exception as e:
                conn.rollback()
                print(f"[AccountPool] Error adding account: {e}")
                raise
            
            finally:
                conn.close()
    
    def get_next_account(
        self,
        site: Optional[str] = None,
        strategy: str = "round_robin"
    ) -> Optional[Account]:
        """
        Get the next available account based on rotation strategy.
        
        Args:
            site: Filter by site (optional)
            strategy: Rotation strategy:
                - "round_robin": Least recently used
                - "health": Best health score
                - "random": Random selection
                - "success_rate": Highest success rate
                
        Returns:
            Account object or None if no accounts available
        """
        with self.lock:
            # Filter available accounts
            available = [
                acc for acc in self.accounts.values()
                if acc.is_available() and (site is None or acc.site == site or acc.site is None)
            ]
            
            if not available:
                print(f"[AccountPool] No available accounts for site: {site}")
                return None
            
            # Select based on strategy
            if strategy == "round_robin":
                # Least recently used
                account = min(available, key=lambda a: a.last_used or datetime.min)
            
            elif strategy == "health":
                # Best health score
                account = max(available, key=lambda a: a.health_score)
            
            elif strategy == "success_rate":
                # Highest success rate
                account = max(available, key=lambda a: a.success_rate)
            
            elif strategy == "random":
                # Random selection
                account = random.choice(available)
            
            else:
                # Default to round robin
                account = min(available, key=lambda a: a.last_used or datetime.min)
            
            # Mark as used
            account.last_used = datetime.now()
            self._update_account(account)
            
            print(f"[AccountPool] Selected account: {account.name} (strategy: {strategy})")
            return account
    
    def record_success(self, account_id: int, action: str = "checkout", details: str = None):
        """Record a successful action for an account."""
        with self.lock:
            if account_id not in self.accounts:
                print(f"[AccountPool] Account {account_id} not found")
                return
            
            account = self.accounts[account_id]
            account.success_count += 1
            
            self._update_account(account)
            self._log_usage(account_id, action, "success", details)
            
            print(f"[AccountPool] Success recorded for {account.name}")
    
    def record_failure(self, account_id: int, action: str = "checkout", details: str = None):
        """Record a failed action for an account."""
        with self.lock:
            if account_id not in self.accounts:
                print(f"[AccountPool] Account {account_id} not found")
                return
            
            account = self.accounts[account_id]
            account.failure_count += 1
            
            self._update_account(account)
            self._log_usage(account_id, action, "failure", details)
            
            print(f"[AccountPool] Failure recorded for {account.name}")
    
    def record_ban(
        self,
        account_id: int,
        cooldown_minutes: int = 60,
        details: str = None
    ):
        """
        Record a ban for an account and set cooldown.
        
        Args:
            account_id: Account ID
            cooldown_minutes: How long to wait before using again
            details: Ban details
        """
        with self.lock:
            if account_id not in self.accounts:
                print(f"[AccountPool] Account {account_id} not found")
                return
            
            account = self.accounts[account_id]
            account.ban_count += 1
            account.is_banned = True
            account.last_ban = datetime.now()
            account.cooldown_until = datetime.now() + timedelta(minutes=cooldown_minutes)
            
            self._update_account(account)
            self._log_usage(account_id, "ban", "banned", details)
            
            print(f"[AccountPool] Ban recorded for {account.name} (cooldown: {cooldown_minutes}min)")
    
    def _update_account(self, account: Account):
        """Update account in database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            now = datetime.now().isoformat()
            
            cursor.execute("""
                UPDATE account_pool
                SET success_count = ?,
                    failure_count = ?,
                    ban_count = ?,
                    last_used = ?,
                    last_ban = ?,
                    is_banned = ?,
                    cooldown_until = ?,
                    updated_at = ?
                WHERE id = ?
            """, (
                account.success_count,
                account.failure_count,
                account.ban_count,
                account.last_used.isoformat() if account.last_used else None,
                account.last_ban.isoformat() if account.last_ban else None,
                1 if account.is_banned else 0,
                account.cooldown_until.isoformat() if account.cooldown_until else None,
                now,
                account.id
            ))
            
            conn.commit()
            
        except Exception as e:
            conn.rollback()
            print(f"[AccountPool] Error updating account: {e}")
        
        finally:
            conn.close()
    
    def _log_usage(self, account_id: int, action: str, result: str, details: str = None):
        """Log account usage to history."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            now = datetime.now().isoformat()
            
            cursor.execute("""
                INSERT INTO account_usage_history
                (account_id, action, result, timestamp, details)
                VALUES (?, ?, ?, ?, ?)
            """, (account_id, action, result, now, details))
            
            conn.commit()
            
        except Exception as e:
            conn.rollback()
            print(f"[AccountPool] Error logging usage: {e}")
        
        finally:
            conn.close()
    
    def get_account_stats(self, account_id: int) -> Dict:
        """Get detailed statistics for an account."""
        if account_id not in self.accounts:
            return {}
        
        account = self.accounts[account_id]
        
        return {
            'id': account.id,
            'name': account.name,
            'email': account.email,
            'success_count': account.success_count,
            'failure_count': account.failure_count,
            'ban_count': account.ban_count,
            'success_rate': account.success_rate,
            'health_score': account.health_score,
            'is_banned': account.is_banned,
            'last_used': account.last_used.isoformat() if account.last_used else None,
            'last_ban': account.last_ban.isoformat() if account.last_ban else None,
            'cooldown_until': account.cooldown_until.isoformat() if account.cooldown_until else None
        }
    
    def get_all_accounts(self, site: Optional[str] = None) -> List[Dict]:
        """Get statistics for all accounts."""
        accounts = self.accounts.values()
        
        if site:
            accounts = [a for a in accounts if a.site == site or a.site is None]
        
        return [self.get_account_stats(a.id) for a in accounts]
    
    def get_pool_stats(self) -> Dict:
        """Get overall pool statistics."""
        total_accounts = len(self.accounts)
        available_accounts = len([a for a in self.accounts.values() if a.is_available()])
        banned_accounts = len([a for a in self.accounts.values() if a.is_banned])
        
        if total_accounts == 0:
            return {
                'total_accounts': 0,
                'available_accounts': 0,
                'banned_accounts': 0,
                'avg_success_rate': 0.0,
                'avg_health_score': 0.0
            }
        
        avg_success_rate = sum(a.success_rate for a in self.accounts.values()) / total_accounts
        avg_health_score = sum(a.health_score for a in self.accounts.values()) / total_accounts
        
        return {
            'total_accounts': total_accounts,
            'available_accounts': available_accounts,
            'banned_accounts': banned_accounts,
            'avg_success_rate': avg_success_rate,
            'avg_health_score': avg_health_score
        }
    
    def remove_account(self, account_id: int) -> bool:
        """Remove an account from the pool."""
        with self.lock:
            if account_id not in self.accounts:
                return False
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            try:
                cursor.execute("DELETE FROM account_pool WHERE id = ?", (account_id,))
                conn.commit()
                
                del self.accounts[account_id]
                print(f"[AccountPool] Removed account ID: {account_id}")
                return True
                
            except Exception as e:
                conn.rollback()
                print(f"[AccountPool] Error removing account: {e}")
                return False
            
            finally:
                conn.close()


# Convenience functions
def create_account_pool(db_path: str = "autobot.db") -> AccountPool:
    """Create an account pool instance."""
    return AccountPool(db_path)


if __name__ == "__main__":
    # Test the account pool
    print("🎭 Account Pool Test")
    print("=" * 60)
    
    pool = AccountPool(db_path="test_accounts.db")
    
    # Add test accounts
    print("\n📝 Adding test accounts...")
    
    acc1_id = pool.add_account("Account1", "user1@example.com", site="nike.com")
    acc2_id = pool.add_account("Account2", "user2@example.com", site="nike.com")
    acc3_id = pool.add_account("Account3", "user3@example.com", site="nike.com")
    
    # Simulate usage
    print("\n🔄 Simulating account rotation...")
    
    for i in range(10):
        account = pool.get_next_account(site="nike.com", strategy="round_robin")
        if account:
            print(f"  Round {i+1}: Using {account.name}")
            
            # Simulate success/failure
            if i % 3 == 0:
                pool.record_success(account.id, action="checkout")
            else:
                pool.record_failure(account.id, action="checkout")
    
    # Simulate ban
    print("\n🚫 Simulating ban on Account1...")
    pool.record_ban(acc1_id, cooldown_minutes=5)
    
    # Check next account (should skip banned one)
    print("\n🔍 Getting next account (should skip banned)...")
    account = pool.get_next_account(site="nike.com")
    print(f"  Selected: {account.name}")
    
    # Show statistics
    print("\n📊 Account Statistics:")
    for acc_stats in pool.get_all_accounts():
        print(f"\n  {acc_stats['name']}:")
        print(f"    Success rate: {acc_stats['success_rate']:.2%}")
        print(f"    Health score: {acc_stats['health_score']:.2f}")
        print(f"    Successes: {acc_stats['success_count']}")
        print(f"    Failures: {acc_stats['failure_count']}")
        print(f"    Bans: {acc_stats['ban_count']}")
        print(f"    Is banned: {acc_stats['is_banned']}")
    
    # Pool stats
    print("\n📈 Pool Statistics:")
    pool_stats = pool.get_pool_stats()
    print(f"  Total accounts: {pool_stats['total_accounts']}")
    print(f"  Available: {pool_stats['available_accounts']}")
    print(f"  Banned: {pool_stats['banned_accounts']}")
    print(f"  Avg success rate: {pool_stats['avg_success_rate']:.2%}")
    print(f"  Avg health score: {pool_stats['avg_health_score']:.2f}")
    
    print("\n✅ Test complete!")
    
    # Cleanup
    import os
    if os.path.exists("test_accounts.db"):
        os.remove("test_accounts.db")
        print("[Cleanup] Removed test database")
