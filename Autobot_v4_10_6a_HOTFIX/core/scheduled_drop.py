"""
Scheduled Drop Engine - Phase 2A
Implements smart drop scheduling with timezone support and phase-based monitoring.

Phases:
1. IDLE - Sleep until 5 minutes before drop
2. PRE_DROP - Check every 15s, warming up
3. AGGRESSIVE - Check every 1s for 30 minutes
4. POST_DROP - Resume normal monitoring

Author: Bob (Bloomfield, IN)
Created: November 12, 2025
"""

import asyncio
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional
from zoneinfo import ZoneInfo


class DropPhase(Enum):
    """Drop monitoring phases"""
    IDLE = "idle"
    PRE_DROP = "pre_drop"
    AGGRESSIVE = "aggressive"
    POST_DROP = "post_drop"


class ScheduledDrop:
    """
    Manages scheduled drop monitoring with intelligent phase transitions.
    
    Features:
    - Timezone support (America/Indiana/Indianapolis default)
    - Four-phase monitoring strategy
    - Automatic phase transitions
    - Resource-efficient idle mode
    - Aggressive 1-second checking during drops
    """
    
    def __init__(
        self,
        drop_time: datetime,
        timezone: str = "America/Indiana/Indianapolis",
        pre_drop_minutes: int = 5,
        aggressive_duration_minutes: int = 30
    ):
        """
        Initialize scheduled drop.
        
        Args:
            drop_time: Scheduled drop time (naive datetime, will apply timezone)
            timezone: IANA timezone string (default: America/Indiana/Indianapolis)
            pre_drop_minutes: Minutes before drop to start PRE_DROP phase (default: 5)
            aggressive_duration_minutes: Duration of AGGRESSIVE phase (default: 30)
        """
        self.timezone = ZoneInfo(timezone)
        
        # Convert drop_time to aware datetime if naive
        if drop_time.tzinfo is None:
            self.drop_time = drop_time.replace(tzinfo=self.timezone)
        else:
            self.drop_time = drop_time.astimezone(self.timezone)
        
        self.pre_drop_minutes = pre_drop_minutes
        self.aggressive_duration_minutes = aggressive_duration_minutes
        
        # State tracking
        self.current_phase = DropPhase.IDLE
        self.phase_start_time = None
        self.check_count = 0
        self.is_running = False
        self.stop_requested = False
        
        # Phase transition times
        self.pre_drop_time = self.drop_time - timedelta(minutes=pre_drop_minutes)
        self.aggressive_end_time = self.drop_time + timedelta(minutes=aggressive_duration_minutes)
        
    def get_current_time(self) -> datetime:
        """Get current time in the configured timezone."""
        return datetime.now(self.timezone)
    
    def time_until_phase(self, phase: DropPhase) -> Optional[float]:
        """
        Calculate seconds until a specific phase starts.
        
        Args:
            phase: Target phase
            
        Returns:
            Seconds until phase starts, or None if phase is in the past
        """
        now = self.get_current_time()
        
        if phase == DropPhase.PRE_DROP:
            target = self.pre_drop_time
        elif phase == DropPhase.AGGRESSIVE:
            target = self.drop_time
        elif phase == DropPhase.POST_DROP:
            target = self.aggressive_end_time
        else:
            return None
        
        delta = (target - now).total_seconds()
        return delta if delta > 0 else None
    
    def should_transition(self) -> Optional[DropPhase]:
        """
        Check if we should transition to a new phase.
        
        Returns:
            Next phase to transition to, or None if no transition needed
        """
        now = self.get_current_time()
        
        if self.current_phase == DropPhase.IDLE:
            if now >= self.pre_drop_time:
                return DropPhase.PRE_DROP
        
        elif self.current_phase == DropPhase.PRE_DROP:
            if now >= self.drop_time:
                return DropPhase.AGGRESSIVE
        
        elif self.current_phase == DropPhase.AGGRESSIVE:
            if now >= self.aggressive_end_time:
                return DropPhase.POST_DROP
        
        return None
    
    def transition_to(self, phase: DropPhase) -> None:
        """
        Transition to a new phase.
        
        Args:
            phase: Phase to transition to
        """
        self.current_phase = phase
        self.phase_start_time = self.get_current_time()
        self.check_count = 0
    
    def get_check_interval(self) -> float:
        """
        Get the appropriate check interval for the current phase.
        
        Returns:
            Interval in seconds
        """
        intervals = {
            DropPhase.IDLE: 60.0,  # Check every minute (just to ensure we don't miss transition)
            DropPhase.PRE_DROP: 15.0,  # Every 15 seconds
            DropPhase.AGGRESSIVE: 1.0,  # Every 1 second
            DropPhase.POST_DROP: 5.0   # Every 5 seconds
        }
        return intervals[self.current_phase]
    
    def get_phase_description(self) -> str:
        """Get human-readable description of current phase."""
        descriptions = {
            DropPhase.IDLE: "Idle (sleeping until drop)",
            DropPhase.PRE_DROP: f"Pre-Drop (warming up, {self.pre_drop_minutes}min before)",
            DropPhase.AGGRESSIVE: f"AGGRESSIVE (1s checks for {self.aggressive_duration_minutes}min)",
            DropPhase.POST_DROP: "Post-Drop (normal monitoring)"
        }
        return descriptions[self.current_phase]
    
    def get_schedule_summary(self) -> dict:
        """
        Get a summary of the drop schedule.
        
        Returns:
            Dictionary with schedule information
        """
        now = self.get_current_time()
        
        return {
            "drop_time": self.drop_time.isoformat(),
            "timezone": str(self.timezone),
            "current_time": now.isoformat(),
            "current_phase": self.current_phase.value,
            "phase_description": self.get_phase_description(),
            "check_interval": self.get_check_interval(),
            "phases": {
                "idle": {
                    "start": "Now",
                    "end": self.pre_drop_time.isoformat(),
                    "duration": self.time_until_phase(DropPhase.PRE_DROP)
                },
                "pre_drop": {
                    "start": self.pre_drop_time.isoformat(),
                    "end": self.drop_time.isoformat(),
                    "duration_minutes": self.pre_drop_minutes
                },
                "aggressive": {
                    "start": self.drop_time.isoformat(),
                    "end": self.aggressive_end_time.isoformat(),
                    "duration_minutes": self.aggressive_duration_minutes
                },
                "post_drop": {
                    "start": self.aggressive_end_time.isoformat(),
                    "end": "Until found",
                    "check_interval": 5
                }
            }
        }
    
    async def wait_for_phase_transition(self) -> None:
        """Wait until it's time to transition to the next phase."""
        while not self.stop_requested:
            next_phase = self.should_transition()
            
            if next_phase:
                print(f"[Scheduled Drop] Transitioning: {self.current_phase.value} → {next_phase.value}")
                self.transition_to(next_phase)
                break
            
            # Check again in a bit
            await asyncio.sleep(1)
    
    async def idle_phase(self) -> None:
        """
        IDLE phase: Sleep until it's time for PRE_DROP.
        Uses minimal resources during this phase.
        """
        print(f"[Scheduled Drop] Entering IDLE phase")
        print(f"[Scheduled Drop] Will wake at: {self.pre_drop_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        
        seconds_until_wake = self.time_until_phase(DropPhase.PRE_DROP)
        
        if seconds_until_wake and seconds_until_wake > 0:
            minutes = seconds_until_wake / 60
            print(f"[Scheduled Drop] Sleeping for {minutes:.1f} minutes...")
            
            # Sleep with periodic wake checks (every minute)
            while not self.stop_requested:
                remaining = self.time_until_phase(DropPhase.PRE_DROP)
                
                if not remaining or remaining <= 0:
                    break
                
                # Sleep for 1 minute or remaining time, whichever is shorter
                sleep_time = min(60, remaining)
                await asyncio.sleep(sleep_time)
        
        # Transition to PRE_DROP
        await self.wait_for_phase_transition()
    
    async def pre_drop_phase(self) -> None:
        """
        PRE_DROP phase: Check every 15 seconds to warm up connections.
        Prepares for aggressive phase.
        """
        print(f"[Scheduled Drop] Entering PRE-DROP phase (5min before drop)")
        print(f"[Scheduled Drop] Checking every 15 seconds...")
        print(f"[Scheduled Drop] Warming up connections...")
        
        while not self.stop_requested and self.current_phase == DropPhase.PRE_DROP:
            # Check if it's time to transition
            if self.should_transition():
                break
            
            self.check_count += 1
            yield True  # Yield control back to monitor for actual check
            
            # Wait for next check
            await asyncio.sleep(self.get_check_interval())
        
        # Transition to AGGRESSIVE
        await self.wait_for_phase_transition()
    
    async def aggressive_phase(self) -> None:
        """
        AGGRESSIVE phase: Check every 1 second for maximum responsiveness.
        This is the critical period during the actual drop.
        """
        print(f"[Scheduled Drop] 🚨 DROP TIME! Entering AGGRESSIVE phase")
        print(f"[Scheduled Drop] Checking every 1 second for {self.aggressive_duration_minutes} minutes")
        
        max_checks = self.aggressive_duration_minutes * 60  # 1 check per second
        
        while not self.stop_requested and self.current_phase == DropPhase.AGGRESSIVE:
            # Check if it's time to transition
            if self.should_transition():
                break
            
            self.check_count += 1
            
            if self.check_count % 60 == 0:  # Progress update every minute
                elapsed_min = self.check_count / 60
                print(f"[Scheduled Drop] AGGRESSIVE: {elapsed_min:.0f}/{self.aggressive_duration_minutes} minutes")
            
            yield True  # Yield control back to monitor for actual check
            
            # Wait for next check (1 second)
            await asyncio.sleep(self.get_check_interval())
        
        # Transition to POST_DROP
        await self.wait_for_phase_transition()
    
    async def post_drop_phase(self) -> None:
        """
        POST_DROP phase: Resume normal monitoring after aggressive phase.
        Continues until product is found.
        """
        print(f"[Scheduled Drop] Entering POST-DROP phase")
        print(f"[Scheduled Drop] Resuming normal monitoring (5s intervals)")
        print(f"[Scheduled Drop] Will continue until product is found...")
        
        while not self.stop_requested and self.current_phase == DropPhase.POST_DROP:
            self.check_count += 1
            yield True  # Yield control back to monitor for actual check
            
            # Wait for next check
            await asyncio.sleep(self.get_check_interval())
    
    async def run(self):
        """
        Main execution loop for scheduled drop.
        Manages phase transitions and yields control for actual monitoring checks.
        """
        self.is_running = True
        self.stop_requested = False
        
        print(f"\n{'='*60}")
        print(f"[Scheduled Drop] Starting Scheduled Drop Monitor")
        print(f"[Scheduled Drop] Drop Time: {self.drop_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        print(f"[Scheduled Drop] Timezone: {self.timezone}")
        print(f"{'='*60}\n")
        
        # Print schedule summary
        summary = self.get_schedule_summary()
        print(f"[Scheduled Drop] Phase Schedule:")
        print(f"  • IDLE: Now → {self.pre_drop_time.strftime('%H:%M:%S')}")
        print(f"  • PRE-DROP: {self.pre_drop_time.strftime('%H:%M:%S')} → {self.drop_time.strftime('%H:%M:%S')}")
        print(f"  • AGGRESSIVE: {self.drop_time.strftime('%H:%M:%S')} → {self.aggressive_end_time.strftime('%H:%M:%S')}")
        print(f"  • POST-DROP: {self.aggressive_end_time.strftime('%H:%M:%S')} → Until found")
        print()
        
        try:
            # Start with IDLE phase
            self.transition_to(DropPhase.IDLE)
            
            # Execute phases in sequence
            await self.idle_phase()
            
            if not self.stop_requested:
                self.transition_to(DropPhase.PRE_DROP)
                async for _ in self.pre_drop_phase():
                    pass
            
            if not self.stop_requested:
                self.transition_to(DropPhase.AGGRESSIVE)
                async for _ in self.aggressive_phase():
                    pass
            
            if not self.stop_requested:
                self.transition_to(DropPhase.POST_DROP)
                async for _ in self.post_drop_phase():
                    pass
        
        except Exception as e:
            print(f"[Scheduled Drop] Error in drop execution: {e}")
            raise
        
        finally:
            self.is_running = False
            print(f"[Scheduled Drop] Scheduled drop monitoring ended")
    
    def stop(self) -> None:
        """Request the scheduled drop to stop."""
        print(f"[Scheduled Drop] Stop requested")
        self.stop_requested = True
    
    def get_status(self) -> dict:
        """
        Get current status of the scheduled drop.
        
        Returns:
            Dictionary with status information
        """
        return {
            "is_running": self.is_running,
            "current_phase": self.current_phase.value,
            "phase_description": self.get_phase_description(),
            "check_interval": self.get_check_interval(),
            "check_count": self.check_count,
            "phase_start_time": self.phase_start_time.isoformat() if self.phase_start_time else None,
            "drop_time": self.drop_time.isoformat(),
            "time_until_drop": self.time_until_phase(DropPhase.AGGRESSIVE),
            "time_until_aggressive_end": self.time_until_phase(DropPhase.POST_DROP)
        }


def validate_drop_time(drop_time: datetime, timezone: str = "America/Indiana/Indianapolis") -> tuple[bool, str]:
    """
    Validate a drop time.
    
    Args:
        drop_time: Proposed drop time
        timezone: Timezone string
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        tz = ZoneInfo(timezone)
        now = datetime.now(tz)
        
        # Convert to aware datetime in the same timezone as 'now'
        if drop_time.tzinfo is None:
            # Naive datetime - interpret in target timezone
            drop_time_aware = drop_time.replace(tzinfo=tz)
        else:
            # Already aware - convert to target timezone
            drop_time_aware = drop_time.astimezone(tz)
        
        # Both times are now in the same timezone for comparison
        time_diff = (drop_time_aware - now).total_seconds()
        
        # Check if drop time is in the past (with small tolerance for test execution time)
        if time_diff < -1:  # 1 second in the past
            return False, "Drop time cannot be in the past"
        
        # Check if drop time is too far in the future (more than 7 days)
        if time_diff > 7 * 24 * 3600:  # 7 days in seconds
            return False, "Drop time cannot be more than 7 days in the future"
        
        return True, ""
    
    except Exception as e:
        return False, f"Invalid drop time or timezone: {e}"


# Example usage (for testing)
if __name__ == "__main__":
    async def test_scheduled_drop():
        """Test the scheduled drop system"""
        # Create a drop 2 minutes from now
        now = datetime.now()
        drop_time = now + timedelta(minutes=2)
        
        print("Creating scheduled drop for testing...")
        scheduled_drop = ScheduledDrop(
            drop_time=drop_time,
            timezone="America/Indiana/Indianapolis",
            pre_drop_minutes=1,  # 1 minute for testing
            aggressive_duration_minutes=1  # 1 minute for testing
        )
        
        # Print schedule
        summary = scheduled_drop.get_schedule_summary()
        print("\nSchedule Summary:")
        print(f"Drop Time: {summary['drop_time']}")
        print(f"Current Time: {summary['current_time']}")
        print(f"Current Phase: {summary['current_phase']}")
        print()
        
        # Simulate running (in real use, this would be integrated with monitor)
        await scheduled_drop.run()
    
    # Run test
    asyncio.run(test_scheduled_drop())
