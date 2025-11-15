"""
Smart Alert System for Autobot v4.4
Sends SMS, Email, and Push notifications for important events

Features:
- SMS alerts via Twilio
- Email alerts via SMTP
- Push notifications (optional)
- Alert rules engine
- Priority levels
- Rate limiting / cooldowns
- Template system
"""

import os
import json
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Optional, Literal
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
import logging

# Try to import Twilio (optional dependency)
try:
    from twilio.rest import Client as TwilioClient
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False
    logging.warning("Twilio not installed. SMS alerts disabled. Install with: pip install twilio --break-system-packages")


AlertType = Literal["drop_detected", "checkout_success", "checkout_failed", 
                     "ban_detected", "ban_recovered", "system_health", 
                     "low_stock", "restock", "monitor_error", "test"]

AlertPriority = Literal["low", "medium", "high", "critical"]

AlertChannel = Literal["sms", "email", "push", "all"]


@dataclass
class AlertConfig:
    """Configuration for alert delivery"""
    # SMS (Twilio)
    twilio_account_sid: Optional[str] = None
    twilio_auth_token: Optional[str] = None
    twilio_from_number: Optional[str] = None
    sms_to_numbers: List[str] = None
    
    # Email (SMTP)
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_use_tls: bool = True
    email_from: Optional[str] = None
    email_to: List[str] = None
    
    # Push (future)
    push_enabled: bool = False
    push_tokens: List[str] = None
    
    # Alert rules
    enabled_alert_types: List[AlertType] = None
    min_priority: AlertPriority = "medium"
    cooldown_seconds: Dict[AlertType, int] = None
    max_alerts_per_hour: int = 20
    
    def __post_init__(self):
        if self.sms_to_numbers is None:
            self.sms_to_numbers = []
        if self.email_to is None:
            self.email_to = []
        if self.push_tokens is None:
            self.push_tokens = []
        if self.enabled_alert_types is None:
            self.enabled_alert_types = [
                "drop_detected", "checkout_success", "ban_detected", 
                "system_health", "restock"
            ]
        if self.cooldown_seconds is None:
            self.cooldown_seconds = {
                "drop_detected": 300,      # 5 min
                "checkout_success": 60,    # 1 min
                "checkout_failed": 300,    # 5 min
                "ban_detected": 600,       # 10 min
                "ban_recovered": 300,      # 5 min
                "system_health": 3600,     # 1 hour
                "low_stock": 600,          # 10 min
                "restock": 300,            # 5 min
                "monitor_error": 600,      # 10 min
                "test": 0                  # No cooldown for tests
            }


@dataclass
class Alert:
    """Represents an alert to be sent"""
    type: AlertType
    title: str
    message: str
    priority: AlertPriority = "medium"
    channels: List[AlertChannel] = None
    metadata: Dict = None
    timestamp: float = None
    
    def __post_init__(self):
        if self.channels is None:
            self.channels = ["all"]
        if self.metadata is None:
            self.metadata = {}
        if self.timestamp is None:
            self.timestamp = time.time()


class AlertTemplates:
    """Pre-defined alert message templates"""
    
    @staticmethod
    def drop_detected(product_name: str, site: str, price: Optional[str] = None) -> Alert:
        """Stock drop detected"""
        price_str = f" at ${price}" if price else ""
        return Alert(
            type="drop_detected",
            title=f"🔥 Drop Detected!",
            message=f"{product_name} is now in stock on {site}{price_str}!",
            priority="high",
            channels=["sms", "email"],
            metadata={"product": product_name, "site": site, "price": price}
        )
    
    @staticmethod
    def checkout_success(product_name: str, site: str, order_id: Optional[str] = None) -> Alert:
        """Successful checkout"""
        order_str = f" (Order #{order_id})" if order_id else ""
        return Alert(
            type="checkout_success",
            title=f"✅ Checkout Success!",
            message=f"Successfully checked out {product_name} on {site}{order_str}!",
            priority="critical",
            channels=["sms", "email"],
            metadata={"product": product_name, "site": site, "order_id": order_id}
        )
    
    @staticmethod
    def checkout_failed(product_name: str, site: str, reason: str) -> Alert:
        """Failed checkout attempt"""
        return Alert(
            type="checkout_failed",
            title=f"❌ Checkout Failed",
            message=f"Failed to checkout {product_name} on {site}. Reason: {reason}",
            priority="medium",
            channels=["email"],
            metadata={"product": product_name, "site": site, "reason": reason}
        )
    
    @staticmethod
    def ban_detected(site: str, ban_type: str) -> Alert:
        """Ban detected"""
        return Alert(
            type="ban_detected",
            title=f"⚠️ Ban Detected!",
            message=f"Detected {ban_type} ban on {site}. Auto-recovery initiated.",
            priority="high",
            channels=["email"],
            metadata={"site": site, "ban_type": ban_type}
        )
    
    @staticmethod
    def ban_recovered(site: str, recovery_time: float) -> Alert:
        """Ban recovered"""
        return Alert(
            type="ban_recovered",
            title=f"✅ Ban Recovered",
            message=f"Successfully recovered from ban on {site} in {recovery_time:.1f}s.",
            priority="medium",
            channels=["email"],
            metadata={"site": site, "recovery_time": recovery_time}
        )
    
    @staticmethod
    def system_health(status: str, details: str) -> Alert:
        """System health alert"""
        priority = "critical" if status == "error" else "medium"
        emoji = "🚨" if status == "error" else "ℹ️"
        return Alert(
            type="system_health",
            title=f"{emoji} System {status.title()}",
            message=f"System health status: {details}",
            priority=priority,
            channels=["email"],
            metadata={"status": status, "details": details}
        )
    
    @staticmethod
    def restock(product_name: str, site: str, stock_level: Optional[int] = None) -> Alert:
        """Product restocked"""
        stock_str = f" ({stock_level} units)" if stock_level else ""
        return Alert(
            type="restock",
            title=f"📦 Restock Alert!",
            message=f"{product_name} restocked on {site}{stock_str}!",
            priority="high",
            channels=["sms", "email"],
            metadata={"product": product_name, "site": site, "stock_level": stock_level}
        )
    
    @staticmethod
    def test_alert(channel: str) -> Alert:
        """Test alert"""
        return Alert(
            type="test",
            title=f"🧪 Test Alert ({channel.upper()})",
            message=f"This is a test alert via {channel}. Your alerts are working!",
            priority="low",
            channels=[channel],
            metadata={"test": True}
        )


class AlertManager:
    """
    Manages alert delivery across multiple channels
    
    Features:
    - Multi-channel support (SMS, Email, Push)
    - Rate limiting and cooldowns
    - Priority-based delivery
    - Alert history tracking
    - Template system
    """
    
    def __init__(self, config: AlertConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Initialize Twilio client if configured
        self.twilio_client = None
        if TWILIO_AVAILABLE and self.config.twilio_account_sid and self.config.twilio_auth_token:
            try:
                self.twilio_client = TwilioClient(
                    self.config.twilio_account_sid,
                    self.config.twilio_auth_token
                )
                self.logger.info("✅ Twilio SMS initialized")
            except Exception as e:
                self.logger.error(f"Failed to initialize Twilio: {e}")
        
        # Alert history for rate limiting
        self.alert_history: List[Dict] = []
        self.last_alert_time: Dict[AlertType, float] = {}
        
        # Load history from disk
        self.history_file = Path("database/alert_history.json")
        self._load_history()
    
    def _load_history(self):
        """Load alert history from disk"""
        try:
            if self.history_file.exists():
                with open(self.history_file, 'r') as f:
                    data = json.load(f)
                    self.alert_history = data.get('history', [])
                    self.last_alert_time = {k: float(v) for k, v in data.get('last_times', {}).items()}
                    self.logger.info(f"Loaded {len(self.alert_history)} alert history records")
        except Exception as e:
            self.logger.error(f"Failed to load alert history: {e}")
    
    def _save_history(self):
        """Save alert history to disk"""
        try:
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.history_file, 'w') as f:
                json.dump({
                    'history': self.alert_history[-1000:],  # Keep last 1000
                    'last_times': self.last_alert_time
                }, f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save alert history: {e}")
    
    def should_send_alert(self, alert: Alert) -> tuple[bool, Optional[str]]:
        """
        Check if alert should be sent based on rules
        Returns: (should_send, reason_if_not)
        """
        # Check if alert type is enabled
        if alert.type not in self.config.enabled_alert_types:
            return False, f"Alert type '{alert.type}' is disabled"
        
        # Check priority threshold
        priority_levels = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        if priority_levels[alert.priority] < priority_levels[self.config.min_priority]:
            return False, f"Priority too low (need {self.config.min_priority}+)"
        
        # Check cooldown
        if alert.type in self.last_alert_time:
            cooldown = self.config.cooldown_seconds.get(alert.type, 0)
            time_since_last = time.time() - self.last_alert_time[alert.type]
            if time_since_last < cooldown:
                remaining = cooldown - time_since_last
                return False, f"Cooldown active ({remaining:.0f}s remaining)"
        
        # Check hourly rate limit
        one_hour_ago = time.time() - 3600
        recent_alerts = [a for a in self.alert_history if a.get('timestamp', 0) > one_hour_ago]
        if len(recent_alerts) >= self.config.max_alerts_per_hour:
            return False, f"Max alerts per hour reached ({self.config.max_alerts_per_hour})"
        
        return True, None
    
    def send_alert(self, alert: Alert) -> Dict:
        """
        Send alert via configured channels
        Returns: Dictionary with delivery results
        """
        # Check if we should send
        should_send, reason = self.should_send_alert(alert)
        if not should_send:
            self.logger.info(f"⏸️ Alert blocked: {reason}")
            return {
                "sent": False,
                "reason": reason,
                "alert": asdict(alert)
            }
        
        results = {
            "sent": True,
            "timestamp": datetime.now().isoformat(),
            "alert": asdict(alert),
            "channels": {}
        }
        
        # Expand "all" channel
        channels = alert.channels
        if "all" in channels:
            channels = ["sms", "email", "push"]
        
        # Send to each channel
        for channel in channels:
            try:
                if channel == "sms":
                    result = self._send_sms(alert)
                    results["channels"]["sms"] = result
                elif channel == "email":
                    result = self._send_email(alert)
                    results["channels"]["email"] = result
                elif channel == "push":
                    result = self._send_push(alert)
                    results["channels"]["push"] = result
            except Exception as e:
                self.logger.error(f"Failed to send {channel} alert: {e}")
                results["channels"][channel] = {
                    "success": False,
                    "error": str(e)
                }
        
        # Update history
        self.last_alert_time[alert.type] = time.time()
        self.alert_history.append({
            "timestamp": time.time(),
            "type": alert.type,
            "title": alert.title,
            "channels": list(results["channels"].keys())
        })
        self._save_history()
        
        self.logger.info(f"📣 Sent {alert.type} alert via {list(results['channels'].keys())}")
        return results
    
    def _send_sms(self, alert: Alert) -> Dict:
        """Send SMS via Twilio"""
        if not self.twilio_client:
            return {"success": False, "error": "Twilio not configured"}
        
        if not self.config.sms_to_numbers:
            return {"success": False, "error": "No SMS recipients configured"}
        
        results = []
        for to_number in self.config.sms_to_numbers:
            try:
                message = self.twilio_client.messages.create(
                    to=to_number,
                    from_=self.config.twilio_from_number,
                    body=f"{alert.title}\n\n{alert.message}"
                )
                results.append({
                    "to": to_number,
                    "sid": message.sid,
                    "success": True
                })
            except Exception as e:
                results.append({
                    "to": to_number,
                    "success": False,
                    "error": str(e)
                })
        
        return {
            "success": all(r["success"] for r in results),
            "sent_to": len([r for r in results if r["success"]]),
            "total": len(results),
            "details": results
        }
    
    def _send_email(self, alert: Alert) -> Dict:
        """Send email via SMTP"""
        if not self.config.smtp_host or not self.config.email_to:
            return {"success": False, "error": "Email not configured"}
        
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.config.email_from or self.config.smtp_username
            msg['To'] = ", ".join(self.config.email_to)
            msg['Subject'] = alert.title
            
            # Build HTML body
            body = f"""
            <html>
            <body style="font-family: Arial, sans-serif;">
                <h2 style="color: #333;">{alert.title}</h2>
                <p style="font-size: 16px;">{alert.message}</p>
                <hr>
                <p style="font-size: 12px; color: #666;">
                    Alert Type: {alert.type}<br>
                    Priority: {alert.priority}<br>
                    Time: {datetime.fromtimestamp(alert.timestamp).strftime('%Y-%m-%d %H:%M:%S')}
                </p>
            </body>
            </html>
            """
            msg.attach(MIMEText(body, 'html'))
            
            # Send via SMTP
            with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port) as server:
                if self.config.smtp_use_tls:
                    server.starttls()
                if self.config.smtp_username and self.config.smtp_password:
                    server.login(self.config.smtp_username, self.config.smtp_password)
                server.send_message(msg)
            
            return {
                "success": True,
                "sent_to": len(self.config.email_to),
                "recipients": self.config.email_to
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def _send_push(self, alert: Alert) -> Dict:
        """Send push notification (placeholder for future implementation)"""
        if not self.config.push_enabled:
            return {"success": False, "error": "Push notifications not enabled"}
        
        # TODO: Implement push notifications (Firebase Cloud Messaging, OneSignal, etc.)
        return {
            "success": False,
            "error": "Push notifications not implemented yet"
        }
    
    def test_sms(self) -> Dict:
        """Test SMS delivery"""
        alert = AlertTemplates.test_alert("sms")
        return self.send_alert(alert)
    
    def test_email(self) -> Dict:
        """Test email delivery"""
        alert = AlertTemplates.test_alert("email")
        return self.send_alert(alert)
    
    def get_alert_history(self, limit: int = 50) -> List[Dict]:
        """Get recent alert history"""
        return self.alert_history[-limit:]
    
    def clear_cooldowns(self):
        """Clear all cooldowns (useful for testing)"""
        self.last_alert_time.clear()
        self.logger.info("Cleared all alert cooldowns")
    
    def get_stats(self) -> Dict:
        """Get alert statistics"""
        now = time.time()
        one_hour_ago = now - 3600
        one_day_ago = now - 86400
        
        recent_hour = [a for a in self.alert_history if a.get('timestamp', 0) > one_hour_ago]
        recent_day = [a for a in self.alert_history if a.get('timestamp', 0) > one_day_ago]
        
        return {
            "total_alerts": len(self.alert_history),
            "last_hour": len(recent_hour),
            "last_day": len(recent_day),
            "by_type": self._count_by_type(recent_day),
            "cooldowns_active": len(self.last_alert_time),
            "next_available": {
                alert_type: max(0, self.last_alert_time.get(alert_type, 0) + 
                               self.config.cooldown_seconds.get(alert_type, 0) - now)
                for alert_type in self.config.enabled_alert_types
            }
        }
    
    def _count_by_type(self, alerts: List[Dict]) -> Dict[str, int]:
        """Count alerts by type"""
        counts = {}
        for alert in alerts:
            alert_type = alert.get('type', 'unknown')
            counts[alert_type] = counts.get(alert_type, 0) + 1
        return counts


# Convenience function for quick setup
def create_alert_manager(
    twilio_sid: Optional[str] = None,
    twilio_token: Optional[str] = None,
    twilio_from: Optional[str] = None,
    sms_to: Optional[List[str]] = None,
    smtp_host: Optional[str] = None,
    smtp_user: Optional[str] = None,
    smtp_pass: Optional[str] = None,
    email_to: Optional[List[str]] = None
) -> AlertManager:
    """Quick setup for alert manager"""
    config = AlertConfig(
        twilio_account_sid=twilio_sid,
        twilio_auth_token=twilio_token,
        twilio_from_number=twilio_from,
        sms_to_numbers=sms_to or [],
        smtp_host=smtp_host,
        smtp_username=smtp_user,
        smtp_password=smtp_pass,
        email_to=email_to or []
    )
    return AlertManager(config)


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)
    
    # Create alert manager (with dummy config for testing)
    config = AlertConfig(
        enabled_alert_types=["drop_detected", "test"],
        min_priority="low"
    )
    manager = AlertManager(config)
    
    # Create test alert
    alert = AlertTemplates.drop_detected(
        product_name="Air Jordan 1 High OG",
        site="Nike SNKRS",
        price="170"
    )
    
    print(f"Alert: {alert.title}")
    print(f"Message: {alert.message}")
    print(f"Should send: {manager.should_send_alert(alert)}")
    
    # Get stats
    stats = manager.get_stats()
    print(f"\nStats: {json.dumps(stats, indent=2)}")
