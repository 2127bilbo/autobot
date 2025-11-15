"""
Autobot Analytics - Phase 3C
Comprehensive performance tracking and analytics

This module provides detailed analytics for the bot:
- Success/failure rate tracking
- Response time monitoring
- Site performance comparison
- Account performance metrics
- Drop success tracking
- Visual analytics data

Author: Bob (Bloomfield, IN)
Created: November 13, 2025
"""

import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import statistics


class Analytics:
    """
    Comprehensive analytics system for Autobot.
    
    Tracks:
    - Monitor performance
    - Checkout success rates
    - Response times
    - Site-specific metrics
    - Account performance
    - Overall system health
    """
    
    def __init__(self, db_path: str = "autobot.db"):
        self.db_path = db_path
        self._ensure_tables()
    
    def _ensure_tables(self):
        """Create analytics tables if they don't exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Performance metrics table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS performance_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    metric_type TEXT NOT NULL,
                    metric_name TEXT NOT NULL,
                    metric_value REAL NOT NULL,
                    site TEXT,
                    account_id INTEGER,
                    monitor_id INTEGER,
                    details TEXT
                )
            """)
            
            # Session analytics table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS session_analytics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_start TEXT NOT NULL,
                    session_end TEXT,
                    total_checks INTEGER DEFAULT 0,
                    successful_checks INTEGER DEFAULT 0,
                    failed_checks INTEGER DEFAULT 0,
                    bans_detected INTEGER DEFAULT 0,
                    drops_found INTEGER DEFAULT 0,
                    checkouts_attempted INTEGER DEFAULT 0,
                    checkouts_successful INTEGER DEFAULT 0,
                    avg_response_time REAL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_metrics_timestamp 
                ON performance_metrics(timestamp)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_metrics_type 
                ON performance_metrics(metric_type)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_metrics_site 
                ON performance_metrics(site)
            """)
            
            conn.commit()
            
        except Exception as e:
            conn.rollback()
            print(f"[Analytics] Error creating tables: {e}")
        
        finally:
            conn.close()
    
    def record_metric(
        self,
        metric_type: str,
        metric_name: str,
        metric_value: float,
        site: Optional[str] = None,
        account_id: Optional[int] = None,
        monitor_id: Optional[int] = None,
        details: Optional[str] = None
    ):
        """
        Record a performance metric.
        
        Args:
            metric_type: Type of metric (response_time, success_rate, etc.)
            metric_name: Specific metric name
            metric_value: Numeric value
            site: Associated site
            account_id: Associated account
            monitor_id: Associated monitor
            details: Additional details (JSON string)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            now = datetime.now().isoformat()
            
            cursor.execute("""
                INSERT INTO performance_metrics
                (timestamp, metric_type, metric_name, metric_value, 
                 site, account_id, monitor_id, details)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (now, metric_type, metric_name, metric_value,
                  site, account_id, monitor_id, details))
            
            conn.commit()
            
        except Exception as e:
            conn.rollback()
            print(f"[Analytics] Error recording metric: {e}")
        
        finally:
            conn.close()
    
    def get_success_rate(
        self,
        hours: int = 24,
        site: Optional[str] = None,
        account_id: Optional[int] = None
    ) -> float:
        """
        Calculate success rate for a time period.
        
        Args:
            hours: Time period in hours
            site: Filter by site
            account_id: Filter by account
            
        Returns:
            Success rate (0-1)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
            
            # Build query
            query = """
                SELECT metric_value
                FROM performance_metrics
                WHERE metric_type = 'checkout_result'
                AND timestamp >= ?
            """
            params = [cutoff]
            
            if site:
                query += " AND site = ?"
                params.append(site)
            
            if account_id:
                query += " AND account_id = ?"
                params.append(account_id)
            
            cursor.execute(query, params)
            results = cursor.fetchall()
            
            if not results:
                return 0.0
            
            successes = sum(1 for (val,) in results if val == 1)
            total = len(results)
            
            return successes / total if total > 0 else 0.0
            
        finally:
            conn.close()
    
    def get_avg_response_time(
        self,
        hours: int = 24,
        site: Optional[str] = None
    ) -> float:
        """
        Calculate average response time.
        
        Args:
            hours: Time period in hours
            site: Filter by site
            
        Returns:
            Average response time in seconds
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
            
            query = """
                SELECT metric_value
                FROM performance_metrics
                WHERE metric_type = 'response_time'
                AND timestamp >= ?
            """
            params = [cutoff]
            
            if site:
                query += " AND site = ?"
                params.append(site)
            
            cursor.execute(query, params)
            results = cursor.fetchall()
            
            if not results:
                return 0.0
            
            times = [val for (val,) in results]
            return statistics.mean(times)
            
        finally:
            conn.close()
    
    def get_site_performance(self, hours: int = 24) -> List[Dict]:
        """
        Get performance metrics grouped by site.
        
        Args:
            hours: Time period in hours
            
        Returns:
            List of site performance dicts
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
            
            # Get sites with metrics
            cursor.execute("""
                SELECT DISTINCT site
                FROM performance_metrics
                WHERE timestamp >= ?
                AND site IS NOT NULL
            """, (cutoff,))
            
            sites = [row[0] for row in cursor.fetchall()]
            
            site_stats = []
            
            for site in sites:
                # Success rate
                success_rate = self.get_success_rate(hours, site=site)
                
                # Response time
                avg_response = self.get_avg_response_time(hours, site=site)
                
                # Total checks
                cursor.execute("""
                    SELECT COUNT(*)
                    FROM performance_metrics
                    WHERE metric_type = 'check'
                    AND site = ?
                    AND timestamp >= ?
                """, (site, cutoff))
                
                total_checks = cursor.fetchone()[0]
                
                # Bans
                cursor.execute("""
                    SELECT COUNT(*)
                    FROM performance_metrics
                    WHERE metric_type = 'ban'
                    AND site = ?
                    AND timestamp >= ?
                """, (site, cutoff))
                
                bans = cursor.fetchone()[0]
                
                site_stats.append({
                    'site': site,
                    'success_rate': success_rate,
                    'avg_response_time': avg_response,
                    'total_checks': total_checks,
                    'bans': bans
                })
            
            # Sort by success rate
            site_stats.sort(key=lambda x: x['success_rate'], reverse=True)
            
            return site_stats
            
        finally:
            conn.close()
    
    def get_account_performance(self, hours: int = 24) -> List[Dict]:
        """
        Get performance metrics grouped by account.
        
        Args:
            hours: Time period in hours
            
        Returns:
            List of account performance dicts
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
            
            # Get accounts with metrics
            cursor.execute("""
                SELECT DISTINCT account_id
                FROM performance_metrics
                WHERE timestamp >= ?
                AND account_id IS NOT NULL
            """, (cutoff,))
            
            account_ids = [row[0] for row in cursor.fetchall()]
            
            account_stats = []
            
            for account_id in account_ids:
                # Success rate
                success_rate = self.get_success_rate(hours, account_id=account_id)
                
                # Total attempts
                cursor.execute("""
                    SELECT COUNT(*)
                    FROM performance_metrics
                    WHERE metric_type = 'checkout_result'
                    AND account_id = ?
                    AND timestamp >= ?
                """, (account_id, cutoff))
                
                total_attempts = cursor.fetchone()[0]
                
                account_stats.append({
                    'account_id': account_id,
                    'success_rate': success_rate,
                    'total_attempts': total_attempts
                })
            
            # Sort by success rate
            account_stats.sort(key=lambda x: x['success_rate'], reverse=True)
            
            return account_stats
            
        finally:
            conn.close()
    
    def get_timeline_data(
        self,
        metric_type: str,
        hours: int = 24,
        interval_minutes: int = 60
    ) -> List[Dict]:
        """
        Get timeline data for charting.
        
        Args:
            metric_type: Type of metric to track
            hours: Time period in hours
            interval_minutes: Data point interval
            
        Returns:
            List of {timestamp, value} dicts
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cutoff = datetime.now() - timedelta(hours=hours)
            
            # Generate time buckets
            timeline = []
            current = cutoff
            
            while current <= datetime.now():
                bucket_start = current
                bucket_end = current + timedelta(minutes=interval_minutes)
                
                # Get metrics in this bucket
                cursor.execute("""
                    SELECT AVG(metric_value)
                    FROM performance_metrics
                    WHERE metric_type = ?
                    AND timestamp >= ?
                    AND timestamp < ?
                """, (metric_type, bucket_start.isoformat(), bucket_end.isoformat()))
                
                result = cursor.fetchone()
                avg_value = result[0] if result[0] is not None else 0
                
                timeline.append({
                    'timestamp': bucket_start.isoformat(),
                    'value': avg_value
                })
                
                current = bucket_end
            
            return timeline
            
        finally:
            conn.close()
    
    def get_system_health(self) -> Dict:
        """
        Get overall system health metrics.
        
        Returns:
            Dict with health indicators
        """
        # Get 24-hour metrics
        success_rate = self.get_success_rate(hours=24)
        avg_response = self.get_avg_response_time(hours=24)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
            
            # Total checks
            cursor.execute("""
                SELECT COUNT(*)
                FROM performance_metrics
                WHERE metric_type = 'check'
                AND timestamp >= ?
            """, (cutoff,))
            
            total_checks = cursor.fetchone()[0]
            
            # Bans
            cursor.execute("""
                SELECT COUNT(*)
                FROM performance_metrics
                WHERE metric_type = 'ban'
                AND timestamp >= ?
            """, (cutoff,))
            
            total_bans = cursor.fetchone()[0]
            
            # Drops found
            cursor.execute("""
                SELECT COUNT(*)
                FROM performance_metrics
                WHERE metric_type = 'drop_found'
                AND timestamp >= ?
            """, (cutoff,))
            
            drops_found = cursor.fetchone()[0]
            
            # Calculate health score (0-1)
            health_components = {
                'success_rate': success_rate * 0.4,
                'response_time': max(0, 1 - (avg_response / 5.0)) * 0.3,  # 5s = bad
                'ban_rate': max(0, 1 - (total_bans / max(total_checks, 1))) * 0.3
            }
            
            health_score = sum(health_components.values())
            
            return {
                'health_score': health_score,
                'success_rate': success_rate,
                'avg_response_time': avg_response,
                'total_checks': total_checks,
                'total_bans': total_bans,
                'drops_found': drops_found,
                'ban_rate': total_bans / max(total_checks, 1)
            }
            
        finally:
            conn.close()
    
    def get_top_performers(self, limit: int = 5) -> Dict:
        """
        Get top performing sites and accounts.
        
        Args:
            limit: Number of results to return
            
        Returns:
            Dict with top_sites and top_accounts
        """
        site_perf = self.get_site_performance(hours=168)  # 1 week
        account_perf = self.get_account_performance(hours=168)
        
        return {
            'top_sites': site_perf[:limit],
            'top_accounts': account_perf[:limit]
        }
    
    def get_statistics_summary(self, hours: int = 24) -> Dict:
        """
        Get comprehensive statistics summary.
        
        Args:
            hours: Time period in hours
            
        Returns:
            Dict with all key statistics
        """
        health = self.get_system_health()
        site_perf = self.get_site_performance(hours)
        
        return {
            'period_hours': hours,
            'health': health,
            'site_performance': site_perf,
            'total_sites': len(site_perf),
            'avg_success_rate': statistics.mean([s['success_rate'] for s in site_perf]) if site_perf else 0,
            'avg_response_time': statistics.mean([s['avg_response_time'] for s in site_perf]) if site_perf else 0
        }
    
    def clear_old_metrics(self, days: int = 30):
        """
        Clear metrics older than specified days.
        
        Args:
            days: Keep metrics newer than this
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cutoff = (datetime.now() - timedelta(days=days)).isoformat()
            
            cursor.execute("""
                DELETE FROM performance_metrics
                WHERE timestamp < ?
            """, (cutoff,))
            
            deleted = cursor.rowcount
            conn.commit()
            
            print(f"[Analytics] Cleared {deleted} old metrics")
            
        except Exception as e:
            conn.rollback()
            print(f"[Analytics] Error clearing metrics: {e}")
        
        finally:
            conn.close()


# Convenience functions
def record_checkout_result(
    success: bool,
    site: str = None,
    account_id: int = None,
    response_time: float = None
):
    """Record a checkout attempt result."""
    analytics = Analytics()
    
    # Record result
    analytics.record_metric(
        metric_type='checkout_result',
        metric_name='checkout',
        metric_value=1.0 if success else 0.0,
        site=site,
        account_id=account_id
    )
    
    # Record response time if provided
    if response_time:
        analytics.record_metric(
            metric_type='response_time',
            metric_name='checkout_time',
            metric_value=response_time,
            site=site,
            account_id=account_id
        )


def record_monitor_check(site: str, response_time: float, success: bool = True):
    """Record a monitor check."""
    analytics = Analytics()
    
    analytics.record_metric(
        metric_type='check',
        metric_name='monitor_check',
        metric_value=1.0 if success else 0.0,
        site=site
    )
    
    analytics.record_metric(
        metric_type='response_time',
        metric_name='check_time',
        metric_value=response_time,
        site=site
    )


def record_ban(site: str, account_id: int = None):
    """Record a ban detection."""
    analytics = Analytics()
    
    analytics.record_metric(
        metric_type='ban',
        metric_name='ban_detected',
        metric_value=1.0,
        site=site,
        account_id=account_id
    )


def record_drop_found(site: str, product_url: str):
    """Record a drop found."""
    analytics = Analytics()
    
    analytics.record_metric(
        metric_type='drop_found',
        metric_name='product_drop',
        metric_value=1.0,
        site=site,
        details=product_url
    )


if __name__ == "__main__":
    # Test analytics
    print("📊 Analytics System Test")
    print("=" * 60)
    
    analytics = Analytics(db_path="test_analytics.db")
    
    # Record some test metrics
    print("\n📝 Recording test metrics...")
    
    sites = ["nike.com", "adidas.com", "supreme.com"]
    
    # Simulate 50 checks with varying success
    for i in range(50):
        site = sites[i % 3]
        success = i % 4 != 0  # 75% success rate
        response_time = 0.5 + (i % 10) * 0.1  # 0.5-1.4s
        
        record_monitor_check(site, response_time, success)
        
        # Some checkouts
        if i % 5 == 0:
            record_checkout_result(
                success=(i % 2 == 0),
                site=site,
                account_id=1,
                response_time=response_time * 2
            )
    
    # Record some bans
    record_ban("nike.com", account_id=1)
    record_ban("supreme.com", account_id=2)
    
    # Record drops
    record_drop_found("nike.com", "https://nike.com/air-jordan-1")
    record_drop_found("adidas.com", "https://adidas.com/yeezy")
    
    # Get statistics
    print("\n📈 System Health:")
    health = analytics.get_system_health()
    print(f"  Health Score: {health['health_score']:.2f}/1.00")
    print(f"  Success Rate: {health['success_rate']:.1%}")
    print(f"  Avg Response: {health['avg_response_time']:.2f}s")
    print(f"  Total Checks: {health['total_checks']}")
    print(f"  Bans: {health['total_bans']}")
    print(f"  Drops Found: {health['drops_found']}")
    
    print("\n🏆 Site Performance:")
    site_perf = analytics.get_site_performance(hours=24)
    for site in site_perf:
        print(f"\n  {site['site']}:")
        print(f"    Success: {site['success_rate']:.1%}")
        print(f"    Avg Response: {site['avg_response_time']:.2f}s")
        print(f"    Checks: {site['total_checks']}")
        print(f"    Bans: {site['bans']}")
    
    print("\n📊 Statistics Summary:")
    summary = analytics.get_statistics_summary(hours=24)
    print(f"  Total Sites: {summary['total_sites']}")
    print(f"  Avg Success: {summary['avg_success_rate']:.1%}")
    print(f"  Avg Response: {summary['avg_response_time']:.2f}s")
    
    print("\n✅ Test complete!")
    
    # Cleanup
    import os
    if os.path.exists("test_analytics.db"):
        os.remove("test_analytics.db")
        print("[Cleanup] Removed test database")
