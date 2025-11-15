"""
Autobot Adaptive Speed Learning System
Phase 1B - Core Intelligence
Learns optimal check intervals per site, speeds up on success, slows on bans
"""

import time
from datetime import datetime, timedelta
from typing import Dict, Optional
from dataclasses import dataclass, field


@dataclass
class SpeedProfile:
    """Track speed metrics for a site/monitor"""
    site: str
    monitor_id: str
    current_interval: float = 15.0  # Start at 15s baseline
    optimal_interval: float = 15.0  # Best known interval
    min_interval: float = 3.0  # Don't go below 3s
    max_interval: float = 60.0  # Don't exceed 60s
    
    # Performance tracking
    success_count: int = 0
    ban_count: int = 0
    consecutive_successes: int = 0
    total_checks: int = 0
    
    # Speed adjustment settings
    speedup_threshold: int = 10  # Speed up after 10 clean checks
    speedup_factor: float = 0.9  # Speed up by 10%
    slowdown_factor: float = 1.5  # Slow down by 50%
    
    # Timestamps
    last_adjustment: Optional[datetime] = None
    last_success: Optional[datetime] = None
    last_ban: Optional[datetime] = None
    
    # History for analysis
    interval_history: list = field(default_factory=list)
    success_rate_history: list = field(default_factory=list)


class AdaptiveSpeedLearner:
    """
    Learns and optimizes check speeds per monitor/site
    
    Algorithm:
    1. Start at 15s baseline (safe for all sites)
    2. After 10 consecutive successes -> speed up 10%
    3. On ban detection -> slow down 50%
    4. Track optimal speeds per site
    5. Never go below 3s or above 60s
    """
    
    def __init__(self, db_manager=None):
        """
        Initialize adaptive speed learner
        
        Args:
            db_manager: Database manager for persistence
        """
        self.db_manager = db_manager
        self.profiles: Dict[str, SpeedProfile] = {}
        self._load_profiles()
    
    def _load_profiles(self):
        """Load speed profiles from database"""
        if not self.db_manager:
            return
        
        try:
            with self.db_manager.lock:
                conn = self.db_manager._get_connection()
                cursor = conn.cursor()
                
                cursor.execute(
                    """
                    SELECT monitor_id, site, current_interval, optimal_interval,
                           success_count, ban_count, consecutive_successes,
                           last_adjustment, last_success, last_ban
                    FROM speed_history
                    ORDER BY last_adjustment DESC
                    """
                )
                
                rows = cursor.fetchall()
                conn.close()
            
            for row in rows:
                profile = SpeedProfile(
                    monitor_id=row[0],
                    site=row[1],
                    current_interval=row[2],
                    optimal_interval=row[3],
                    success_count=row[4],
                    ban_count=row[5],
                    consecutive_successes=row[6],
                )
                
                # Parse timestamps
                if row[7]:
                    profile.last_adjustment = datetime.fromisoformat(row[7])
                if row[8]:
                    profile.last_success = datetime.fromisoformat(row[8])
                if row[9]:
                    profile.last_ban = datetime.fromisoformat(row[9])
                
                self.profiles[row[0]] = profile
                print(f"[ADAPTIVE] Loaded profile for {row[0]}: {row[2]:.1f}s interval")
                
        except Exception as e:
            print(f"[ADAPTIVE] Failed to load profiles: {e}")
    
    def get_profile(self, monitor_id: str, site: str) -> SpeedProfile:
        """
        Get or create speed profile for a monitor
        
        Args:
            monitor_id: Monitor identifier
            site: Site name (target, walmart, etc.)
            
        Returns:
            SpeedProfile instance
        """
        if monitor_id not in self.profiles:
            # Check if we have a site-wide optimal learned
            site_optimal = self._get_site_optimal_interval(site)
            
            profile = SpeedProfile(
                monitor_id=monitor_id,
                site=site,
                current_interval=site_optimal if site_optimal else 15.0,
                optimal_interval=site_optimal if site_optimal else 15.0
            )
            self.profiles[monitor_id] = profile
            
            print(f"[ADAPTIVE] New profile: {monitor_id} ({site}) @ {profile.current_interval:.1f}s")
            self._save_profile(profile)
        
        return self.profiles[monitor_id]
    
    def _get_site_optimal_interval(self, site: str) -> Optional[float]:
        """
        Get the best known interval for a site across all monitors
        
        Args:
            site: Site name
            
        Returns:
            Optimal interval or None
        """
        site_profiles = [p for p in self.profiles.values() if p.site == site]
        
        if not site_profiles:
            return None
        
        # Find profile with best success rate and lowest interval
        best_profile = None
        best_score = 0
        
        for profile in site_profiles:
            if profile.total_checks < 20:  # Need enough data
                continue
            
            success_rate = profile.success_count / profile.total_checks if profile.total_checks > 0 else 0
            
            # Score = success_rate * speed_multiplier
            # Lower interval = higher speed = higher score
            speed_multiplier = 15.0 / profile.current_interval if profile.current_interval > 0 else 1
            score = success_rate * speed_multiplier
            
            if score > best_score:
                best_score = score
                best_profile = profile
        
        if best_profile:
            print(f"[ADAPTIVE] Site {site} optimal: {best_profile.current_interval:.1f}s")
            return best_profile.current_interval
        
        return None
    
    def record_success(self, monitor_id: str, site: str):
        """
        Record a successful check - may trigger speedup
        
        Args:
            monitor_id: Monitor identifier
            site: Site name
        """
        profile = self.get_profile(monitor_id, site)
        
        profile.success_count += 1
        profile.consecutive_successes += 1
        profile.total_checks += 1
        profile.last_success = datetime.now()
        
        # Check if we should speed up
        if profile.consecutive_successes >= profile.speedup_threshold:
            self._speed_up(profile)
        
        # Update success rate history every 10 checks
        if profile.total_checks % 10 == 0:
            success_rate = profile.success_count / profile.total_checks
            profile.success_rate_history.append({
                'timestamp': datetime.now(),
                'success_rate': success_rate,
                'interval': profile.current_interval
            })
            # Keep last 100 entries
            profile.success_rate_history = profile.success_rate_history[-100:]
        
        self._save_profile(profile)
    
    def record_ban(self, monitor_id: str, site: str):
        """
        Record a ban detection - triggers slowdown
        
        Args:
            monitor_id: Monitor identifier
            site: Site name
        """
        profile = self.get_profile(monitor_id, site)
        
        profile.ban_count += 1
        profile.total_checks += 1
        profile.consecutive_successes = 0  # Reset
        profile.last_ban = datetime.now()
        
        # Always slow down on ban
        self._slow_down(profile)
        
        self._save_profile(profile)
    
    def _speed_up(self, profile: SpeedProfile):
        """
        Speed up check interval by 10%
        
        Args:
            profile: Speed profile to adjust
        """
        old_interval = profile.current_interval
        new_interval = old_interval * profile.speedup_factor
        
        # Don't go below minimum
        new_interval = max(new_interval, profile.min_interval)
        
        # Only apply if actually changing
        if new_interval < old_interval:
            profile.current_interval = new_interval
            profile.last_adjustment = datetime.now()
            
            # Record in history
            profile.interval_history.append({
                'timestamp': datetime.now(),
                'old_interval': old_interval,
                'new_interval': new_interval,
                'reason': 'speedup',
                'consecutive_successes': profile.consecutive_successes
            })
            # Keep last 100 entries
            profile.interval_history = profile.interval_history[-100:]
            
            # Update optimal if this is better
            if new_interval < profile.optimal_interval:
                profile.optimal_interval = new_interval
            
            print(f"[ADAPTIVE] ⚡ {profile.monitor_id}: {old_interval:.1f}s → {new_interval:.1f}s "
                  f"(+10% speed, {profile.consecutive_successes} clean checks)")
            
            # Reset counter
            profile.consecutive_successes = 0
    
    def _slow_down(self, profile: SpeedProfile):
        """
        Slow down check interval by 50%
        
        Args:
            profile: Speed profile to adjust
        """
        old_interval = profile.current_interval
        new_interval = old_interval * profile.slowdown_factor
        
        # Don't exceed maximum
        new_interval = min(new_interval, profile.max_interval)
        
        profile.current_interval = new_interval
        profile.last_adjustment = datetime.now()
        
        # Record in history
        profile.interval_history.append({
            'timestamp': datetime.now(),
            'old_interval': old_interval,
            'new_interval': new_interval,
            'reason': 'ban_detected',
            'ban_count': profile.ban_count
        })
        # Keep last 100 entries
        profile.interval_history = profile.interval_history[-100:]
        
        print(f"[ADAPTIVE] 🐢 {profile.monitor_id}: {old_interval:.1f}s → {new_interval:.1f}s "
              f"(-50% speed, ban detected)")
    
    def get_current_interval(self, monitor_id: str, site: str) -> float:
        """
        Get current check interval for a monitor
        
        Args:
            monitor_id: Monitor identifier
            site: Site name
            
        Returns:
            Current interval in seconds
        """
        profile = self.get_profile(monitor_id, site)
        return profile.current_interval
    
    def get_optimal_interval(self, monitor_id: str, site: str) -> float:
        """
        Get optimal (best known) interval for a monitor
        
        Args:
            monitor_id: Monitor identifier
            site: Site name
            
        Returns:
            Optimal interval in seconds
        """
        profile = self.get_profile(monitor_id, site)
        return profile.optimal_interval
    
    def get_stats(self, monitor_id: str) -> Dict:
        """
        Get statistics for a monitor
        
        Args:
            monitor_id: Monitor identifier
            
        Returns:
            Dictionary with speed stats
        """
        if monitor_id not in self.profiles:
            return {}
        
        profile = self.profiles[monitor_id]
        success_rate = profile.success_count / profile.total_checks if profile.total_checks > 0 else 0
        
        return {
            'monitor_id': monitor_id,
            'site': profile.site,
            'current_interval': profile.current_interval,
            'optimal_interval': profile.optimal_interval,
            'success_count': profile.success_count,
            'ban_count': profile.ban_count,
            'total_checks': profile.total_checks,
            'success_rate': success_rate,
            'consecutive_successes': profile.consecutive_successes,
            'last_adjustment': profile.last_adjustment.isoformat() if profile.last_adjustment else None,
            'interval_history': profile.interval_history[-10:],  # Last 10 adjustments
        }
    
    def get_all_stats(self) -> Dict[str, Dict]:
        """
        Get statistics for all monitors
        
        Returns:
            Dictionary of monitor_id -> stats
        """
        return {
            monitor_id: self.get_stats(monitor_id)
            for monitor_id in self.profiles.keys()
        }
    
    def _save_profile(self, profile: SpeedProfile):
        """
        Save speed profile to database
        
        Args:
            profile: Speed profile to save
        """
        if not self.db_manager:
            return
        
        try:
            with self.db_manager.lock:
                conn = self.db_manager._get_connection()
                cursor = conn.cursor()
                
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO speed_history
                    (monitor_id, site, current_interval, optimal_interval, 
                     success_count, ban_count, consecutive_successes, total_checks,
                     last_adjustment, last_success, last_ban)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        profile.monitor_id,
                        profile.site,
                        profile.current_interval,
                        profile.optimal_interval,
                        profile.success_count,
                        profile.ban_count,
                        profile.consecutive_successes,
                        profile.total_checks,
                        profile.last_adjustment.isoformat() if profile.last_adjustment else None,
                        profile.last_success.isoformat() if profile.last_success else None,
                        profile.last_ban.isoformat() if profile.last_ban else None,
                    )
                )
                
                conn.commit()
                conn.close()
        except Exception as e:
            print(f"[ADAPTIVE] Failed to save profile: {e}")
    
    def remove_profile(self, monitor_id: str):
        """
        Remove speed profile for a monitor
        
        Args:
            monitor_id: Monitor identifier
        """
        if monitor_id in self.profiles:
            del self.profiles[monitor_id]
        
        if self.db_manager:
            try:
                with self.db_manager.lock:
                    conn = self.db_manager._get_connection()
                    cursor = conn.cursor()
                    
                    cursor.execute(
                        "DELETE FROM speed_history WHERE monitor_id = ?",
                        (monitor_id,)
                    )
                    
                    conn.commit()
                    conn.close()
            except Exception as e:
                print(f"[ADAPTIVE] Failed to delete profile: {e}")


# Global adaptive speed learner
_speed_learner = None


def get_speed_learner(db_manager=None) -> AdaptiveSpeedLearner:
    """
    Get global adaptive speed learner instance
    
    Args:
        db_manager: Database manager (optional)
        
    Returns:
        AdaptiveSpeedLearner instance
    """
    global _speed_learner
    if _speed_learner is None:
        _speed_learner = AdaptiveSpeedLearner(db_manager)
    return _speed_learner
