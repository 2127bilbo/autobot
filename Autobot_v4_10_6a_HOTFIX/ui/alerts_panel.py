"""
Alert Settings Panel for Autobot v4.4
UI for configuring SMS, Email, and Push notifications

Features:
- Twilio SMS configuration
- SMTP email configuration
- Alert type toggles
- Priority settings
- Test buttons
- Alert history viewer
"""

import customtkinter as ctk
from tkinter import messagebox
import json
from pathlib import Path
from typing import Optional
import logging

from core.smart_alerts import AlertManager, AlertConfig, AlertTemplates


class AlertsPanel(ctk.CTkFrame):
    """Panel for managing alert settings"""
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        
        self.logger = logging.getLogger(__name__)
        self.config_file = Path("config/alerts.json")
        
        # Alert manager (will be initialized after loading config)
        self.alert_manager: Optional[AlertManager] = None
        
        # Build UI
        self._build_ui()
        
        # Load saved configuration
        self._load_config()
    
    def _build_ui(self):
        """Build the alerts settings UI"""
        # Main title
        title = ctk.CTkLabel(
            self,
            text="🔔 Smart Alert System",
            font=("Arial", 20, "bold")
        )
        title.pack(pady=10)
        
        # Create tabview for different sections
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Add tabs
        self.tabview.add("SMS (Twilio)")
        self.tabview.add("Email (SMTP)")
        self.tabview.add("Rules")
        self.tabview.add("History")
        
        # Build each tab
        self._build_sms_tab()
        self._build_email_tab()
        self._build_rules_tab()
        self._build_history_tab()
        
        # Bottom buttons
        button_frame = ctk.CTkFrame(self)
        button_frame.pack(fill="x", padx=10, pady=10)
        
        save_btn = ctk.CTkButton(
            button_frame,
            text="💾 Save Configuration",
            command=self._save_config,
            fg_color="green",
            hover_color="darkgreen"
        )
        save_btn.pack(side="left", padx=5)
        
        reset_btn = ctk.CTkButton(
            button_frame,
            text="🔄 Reset to Defaults",
            command=self._reset_config,
            fg_color="gray",
            hover_color="darkgray"
        )
        reset_btn.pack(side="left", padx=5)
    
    def _build_sms_tab(self):
        """Build SMS configuration tab"""
        tab = self.tabview.tab("SMS (Twilio)")
        
        # Scrollable frame
        scroll = ctk.CTkScrollableFrame(tab)
        scroll.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Info label
        info = ctk.CTkLabel(
            scroll,
            text="Configure Twilio for SMS alerts\nSign up at: https://www.twilio.com",
            font=("Arial", 11),
            text_color="gray"
        )
        info.pack(pady=5)
        
        # Account SID
        ctk.CTkLabel(scroll, text="Account SID:", anchor="w").pack(fill="x", pady=2)
        self.twilio_sid_entry = ctk.CTkEntry(scroll, placeholder_text="ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
        self.twilio_sid_entry.pack(fill="x", pady=2)
        
        # Auth Token
        ctk.CTkLabel(scroll, text="Auth Token:", anchor="w").pack(fill="x", pady=2)
        self.twilio_token_entry = ctk.CTkEntry(scroll, placeholder_text="Your auth token", show="*")
        self.twilio_token_entry.pack(fill="x", pady=2)
        
        # From Number
        ctk.CTkLabel(scroll, text="From Number:", anchor="w").pack(fill="x", pady=2)
        self.twilio_from_entry = ctk.CTkEntry(scroll, placeholder_text="+1234567890")
        self.twilio_from_entry.pack(fill="x", pady=2)
        
        # To Numbers
        ctk.CTkLabel(scroll, text="To Numbers (one per line):", anchor="w").pack(fill="x", pady=2)
        self.sms_to_text = ctk.CTkTextbox(scroll, height=100)
        self.sms_to_text.pack(fill="x", pady=2)
        self.sms_to_text.insert("1.0", "+1234567890\n+1098765432")
        
        # Test button
        test_btn = ctk.CTkButton(
            scroll,
            text="📱 Test SMS",
            command=self._test_sms,
            fg_color="blue",
            hover_color="darkblue"
        )
        test_btn.pack(pady=10)
    
    def _build_email_tab(self):
        """Build Email configuration tab"""
        tab = self.tabview.tab("Email (SMTP)")
        
        # Scrollable frame
        scroll = ctk.CTkScrollableFrame(tab)
        scroll.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Info label
        info = ctk.CTkLabel(
            scroll,
            text="Configure SMTP for email alerts\nCommon: Gmail (smtp.gmail.com:587)",
            font=("Arial", 11),
            text_color="gray"
        )
        info.pack(pady=5)
        
        # SMTP Host
        ctk.CTkLabel(scroll, text="SMTP Host:", anchor="w").pack(fill="x", pady=2)
        self.smtp_host_entry = ctk.CTkEntry(scroll, placeholder_text="smtp.gmail.com")
        self.smtp_host_entry.pack(fill="x", pady=2)
        
        # SMTP Port
        ctk.CTkLabel(scroll, text="SMTP Port:", anchor="w").pack(fill="x", pady=2)
        self.smtp_port_entry = ctk.CTkEntry(scroll, placeholder_text="587")
        self.smtp_port_entry.pack(fill="x", pady=2)
        
        # Username
        ctk.CTkLabel(scroll, text="Username:", anchor="w").pack(fill="x", pady=2)
        self.smtp_user_entry = ctk.CTkEntry(scroll, placeholder_text="your.email@gmail.com")
        self.smtp_user_entry.pack(fill="x", pady=2)
        
        # Password
        ctk.CTkLabel(scroll, text="Password / App Password:", anchor="w").pack(fill="x", pady=2)
        self.smtp_pass_entry = ctk.CTkEntry(scroll, placeholder_text="Your password", show="*")
        self.smtp_pass_entry.pack(fill="x", pady=2)
        
        # From Email
        ctk.CTkLabel(scroll, text="From Email:", anchor="w").pack(fill="x", pady=2)
        self.email_from_entry = ctk.CTkEntry(scroll, placeholder_text="autobot@yourdomain.com")
        self.email_from_entry.pack(fill="x", pady=2)
        
        # To Emails
        ctk.CTkLabel(scroll, text="To Emails (one per line):", anchor="w").pack(fill="x", pady=2)
        self.email_to_text = ctk.CTkTextbox(scroll, height=100)
        self.email_to_text.pack(fill="x", pady=2)
        self.email_to_text.insert("1.0", "your.email@gmail.com\nbackup@gmail.com")
        
        # TLS checkbox
        self.smtp_tls_var = ctk.BooleanVar(value=True)
        self.smtp_tls_check = ctk.CTkCheckBox(
            scroll,
            text="Use TLS/SSL",
            variable=self.smtp_tls_var
        )
        self.smtp_tls_check.pack(pady=5)
        
        # Test button
        test_btn = ctk.CTkButton(
            scroll,
            text="📧 Test Email",
            command=self._test_email,
            fg_color="blue",
            hover_color="darkblue"
        )
        test_btn.pack(pady=10)
    
    def _build_rules_tab(self):
        """Build alert rules configuration tab"""
        tab = self.tabview.tab("Rules")
        
        # Scrollable frame
        scroll = ctk.CTkScrollableFrame(tab)
        scroll.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Info
        info = ctk.CTkLabel(
            scroll,
            text="Configure when to send alerts",
            font=("Arial", 12, "bold")
        )
        info.pack(pady=5)
        
        # Enabled alert types
        ctk.CTkLabel(
            scroll,
            text="📋 Enabled Alert Types:",
            font=("Arial", 11, "bold"),
            anchor="w"
        ).pack(fill="x", pady=5)
        
        self.alert_type_vars = {}
        alert_types = [
            ("drop_detected", "🔥 Drop Detected"),
            ("checkout_success", "✅ Checkout Success"),
            ("checkout_failed", "❌ Checkout Failed"),
            ("ban_detected", "⚠️ Ban Detected"),
            ("ban_recovered", "✅ Ban Recovered"),
            ("system_health", "🏥 System Health"),
            ("low_stock", "📉 Low Stock"),
            ("restock", "📦 Restock"),
            ("monitor_error", "❌ Monitor Error")
        ]
        
        for alert_type, label in alert_types:
            var = ctk.BooleanVar(value=True)
            self.alert_type_vars[alert_type] = var
            check = ctk.CTkCheckBox(scroll, text=label, variable=var)
            check.pack(anchor="w", padx=20, pady=2)
        
        # Priority level
        ctk.CTkLabel(
            scroll,
            text="🎯 Minimum Priority:",
            font=("Arial", 11, "bold"),
            anchor="w"
        ).pack(fill="x", pady=5)
        
        self.priority_var = ctk.StringVar(value="medium")
        priority_frame = ctk.CTkFrame(scroll)
        priority_frame.pack(fill="x", pady=5)
        
        for priority in ["low", "medium", "high", "critical"]:
            radio = ctk.CTkRadioButton(
                priority_frame,
                text=priority.capitalize(),
                variable=self.priority_var,
                value=priority
            )
            radio.pack(side="left", padx=10)
        
        # Max alerts per hour
        ctk.CTkLabel(
            scroll,
            text="⏱️ Max Alerts Per Hour:",
            font=("Arial", 11, "bold"),
            anchor="w"
        ).pack(fill="x", pady=5)
        
        self.max_alerts_entry = ctk.CTkEntry(scroll, placeholder_text="20")
        self.max_alerts_entry.pack(fill="x", pady=2)
        
        # Cooldown settings
        ctk.CTkLabel(
            scroll,
            text="⏲️ Cooldown Periods (seconds):",
            font=("Arial", 11, "bold"),
            anchor="w"
        ).pack(fill="x", pady=5)
        
        cooldown_info = ctk.CTkLabel(
            scroll,
            text="Prevents spam by limiting repeat alerts",
            font=("Arial", 10),
            text_color="gray"
        )
        cooldown_info.pack(anchor="w", pady=2)
        
        # Show current cooldowns (read-only info)
        cooldowns_text = """
Drop Detected: 5 minutes
Checkout Success: 1 minute  
Ban Detected: 10 minutes
Restock: 5 minutes
System Health: 1 hour
        """.strip()
        
        cooldowns_label = ctk.CTkLabel(
            scroll,
            text=cooldowns_text,
            font=("Arial", 10),
            justify="left"
        )
        cooldowns_label.pack(anchor="w", padx=20, pady=5)
    
    def _build_history_tab(self):
        """Build alert history viewer tab"""
        tab = self.tabview.tab("History")
        
        # Info
        info_frame = ctk.CTkFrame(tab)
        info_frame.pack(fill="x", padx=5, pady=5)
        
        ctk.CTkLabel(
            info_frame,
            text="📊 Recent Alerts",
            font=("Arial", 14, "bold")
        ).pack(side="left", padx=10)
        
        refresh_btn = ctk.CTkButton(
            info_frame,
            text="🔄 Refresh",
            command=self._refresh_history,
            width=100
        )
        refresh_btn.pack(side="right", padx=10)
        
        # Stats frame
        self.stats_frame = ctk.CTkFrame(tab)
        self.stats_frame.pack(fill="x", padx=5, pady=5)
        
        # History textbox
        self.history_text = ctk.CTkTextbox(tab, height=300)
        self.history_text.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Initial load
        self._refresh_history()
    
    def _test_sms(self):
        """Test SMS alert delivery"""
        try:
            # Initialize alert manager with current config
            self._initialize_alert_manager()
            
            if not self.alert_manager:
                messagebox.showerror("Error", "Alert manager not initialized")
                return
            
            # Send test
            result = self.alert_manager.test_sms()
            
            if result.get("sent"):
                channels = result.get("channels", {})
                sms_result = channels.get("sms", {})
                
                if sms_result.get("success"):
                    sent_to = sms_result.get("sent_to", 0)
                    messagebox.showinfo(
                        "Success!",
                        f"✅ Test SMS sent successfully to {sent_to} number(s)!\nCheck your phone."
                    )
                else:
                    error = sms_result.get("error", "Unknown error")
                    messagebox.showerror("Failed", f"❌ SMS failed: {error}")
            else:
                reason = result.get("reason", "Unknown reason")
                messagebox.showwarning("Blocked", f"⏸️ Test blocked: {reason}")
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to send test SMS:\n{str(e)}")
    
    def _test_email(self):
        """Test email alert delivery"""
        try:
            # Initialize alert manager with current config
            self._initialize_alert_manager()
            
            if not self.alert_manager:
                messagebox.showerror("Error", "Alert manager not initialized")
                return
            
            # Send test
            result = self.alert_manager.test_email()
            
            if result.get("sent"):
                channels = result.get("channels", {})
                email_result = channels.get("email", {})
                
                if email_result.get("success"):
                    sent_to = email_result.get("sent_to", 0)
                    messagebox.showinfo(
                        "Success!",
                        f"✅ Test email sent successfully to {sent_to} recipient(s)!\nCheck your inbox."
                    )
                else:
                    error = email_result.get("error", "Unknown error")
                    messagebox.showerror("Failed", f"❌ Email failed: {error}")
            else:
                reason = result.get("reason", "Unknown reason")
                messagebox.showwarning("Blocked", f"⏸️ Test blocked: {reason}")
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to send test email:\n{str(e)}")
    
    def _initialize_alert_manager(self):
        """Initialize alert manager with current UI values"""
        try:
            # Get SMS config
            twilio_sid = self.twilio_sid_entry.get().strip()
            twilio_token = self.twilio_token_entry.get().strip()
            twilio_from = self.twilio_from_entry.get().strip()
            sms_to_text = self.sms_to_text.get("1.0", "end").strip()
            sms_to_numbers = [n.strip() for n in sms_to_text.split("\n") if n.strip()]
            
            # Get email config
            smtp_host = self.smtp_host_entry.get().strip()
            smtp_port = int(self.smtp_port_entry.get().strip() or "587")
            smtp_user = self.smtp_user_entry.get().strip()
            smtp_pass = self.smtp_pass_entry.get().strip()
            email_from = self.email_from_entry.get().strip()
            email_to_text = self.email_to_text.get("1.0", "end").strip()
            email_to = [e.strip() for e in email_to_text.split("\n") if e.strip()]
            smtp_tls = self.smtp_tls_var.get()
            
            # Get rules
            enabled_types = [t for t, var in self.alert_type_vars.items() if var.get()]
            min_priority = self.priority_var.get()
            max_alerts = int(self.max_alerts_entry.get() or "20")
            
            # Create config
            config = AlertConfig(
                twilio_account_sid=twilio_sid or None,
                twilio_auth_token=twilio_token or None,
                twilio_from_number=twilio_from or None,
                sms_to_numbers=sms_to_numbers,
                smtp_host=smtp_host or None,
                smtp_port=smtp_port,
                smtp_username=smtp_user or None,
                smtp_password=smtp_pass or None,
                smtp_use_tls=smtp_tls,
                email_from=email_from or None,
                email_to=email_to,
                enabled_alert_types=enabled_types,
                min_priority=min_priority,
                max_alerts_per_hour=max_alerts
            )
            
            self.alert_manager = AlertManager(config)
            self.logger.info("Alert manager initialized")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize alert manager: {e}")
            raise
    
    def _save_config(self):
        """Save configuration to file"""
        try:
            # Initialize to get current config
            self._initialize_alert_manager()
            
            # Save to file
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            
            config_dict = {
                "twilio_account_sid": self.twilio_sid_entry.get().strip(),
                "twilio_auth_token": self.twilio_token_entry.get().strip(),
                "twilio_from_number": self.twilio_from_entry.get().strip(),
                "sms_to_numbers": [n.strip() for n in self.sms_to_text.get("1.0", "end").strip().split("\n") if n.strip()],
                "smtp_host": self.smtp_host_entry.get().strip(),
                "smtp_port": int(self.smtp_port_entry.get().strip() or "587"),
                "smtp_username": self.smtp_user_entry.get().strip(),
                "smtp_password": self.smtp_pass_entry.get().strip(),
                "smtp_use_tls": self.smtp_tls_var.get(),
                "email_from": self.email_from_entry.get().strip(),
                "email_to": [e.strip() for e in self.email_to_text.get("1.0", "end").strip().split("\n") if e.strip()],
                "enabled_alert_types": [t for t, var in self.alert_type_vars.items() if var.get()],
                "min_priority": self.priority_var.get(),
                "max_alerts_per_hour": int(self.max_alerts_entry.get() or "20")
            }
            
            with open(self.config_file, 'w') as f:
                json.dump(config_dict, f, indent=2)
            
            messagebox.showinfo("Success", "✅ Alert configuration saved!")
            self.logger.info(f"Saved alert config to {self.config_file}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save configuration:\n{str(e)}")
            self.logger.error(f"Failed to save config: {e}")
    
    def _load_config(self):
        """Load configuration from file"""
        try:
            if not self.config_file.exists():
                self.logger.info("No saved alert config found, using defaults")
                return
            
            with open(self.config_file, 'r') as f:
                config = json.load(f)
            
            # Load SMS config
            self.twilio_sid_entry.insert(0, config.get("twilio_account_sid", ""))
            self.twilio_token_entry.insert(0, config.get("twilio_auth_token", ""))
            self.twilio_from_entry.insert(0, config.get("twilio_from_number", ""))
            sms_numbers = "\n".join(config.get("sms_to_numbers", []))
            if sms_numbers:
                self.sms_to_text.delete("1.0", "end")
                self.sms_to_text.insert("1.0", sms_numbers)
            
            # Load email config
            self.smtp_host_entry.insert(0, config.get("smtp_host", ""))
            self.smtp_port_entry.insert(0, str(config.get("smtp_port", 587)))
            self.smtp_user_entry.insert(0, config.get("smtp_username", ""))
            self.smtp_pass_entry.insert(0, config.get("smtp_password", ""))
            self.email_from_entry.insert(0, config.get("email_from", ""))
            email_addresses = "\n".join(config.get("email_to", []))
            if email_addresses:
                self.email_to_text.delete("1.0", "end")
                self.email_to_text.insert("1.0", email_addresses)
            self.smtp_tls_var.set(config.get("smtp_use_tls", True))
            
            # Load rules
            enabled_types = config.get("enabled_alert_types", [])
            for alert_type, var in self.alert_type_vars.items():
                var.set(alert_type in enabled_types)
            
            self.priority_var.set(config.get("min_priority", "medium"))
            self.max_alerts_entry.insert(0, str(config.get("max_alerts_per_hour", 20)))
            
            # Initialize alert manager
            self._initialize_alert_manager()
            
            self.logger.info("Loaded alert configuration")
            
        except Exception as e:
            self.logger.error(f"Failed to load config: {e}")
    
    def _reset_config(self):
        """Reset configuration to defaults"""
        if messagebox.askyesno("Confirm Reset", "Reset all alert settings to defaults?"):
            # Clear all entries
            self.twilio_sid_entry.delete(0, "end")
            self.twilio_token_entry.delete(0, "end")
            self.twilio_from_entry.delete(0, "end")
            self.sms_to_text.delete("1.0", "end")
            self.sms_to_text.insert("1.0", "+1234567890")
            
            self.smtp_host_entry.delete(0, "end")
            self.smtp_port_entry.delete(0, "end")
            self.smtp_port_entry.insert(0, "587")
            self.smtp_user_entry.delete(0, "end")
            self.smtp_pass_entry.delete(0, "end")
            self.email_from_entry.delete(0, "end")
            self.email_to_text.delete("1.0", "end")
            self.email_to_text.insert("1.0", "your.email@gmail.com")
            
            # Reset checkboxes
            for var in self.alert_type_vars.values():
                var.set(True)
            
            self.priority_var.set("medium")
            self.max_alerts_entry.delete(0, "end")
            self.max_alerts_entry.insert(0, "20")
            
            messagebox.showinfo("Reset", "Settings reset to defaults")
    
    def _refresh_history(self):
        """Refresh alert history display"""
        try:
            if not self.alert_manager:
                self._initialize_alert_manager()
            
            if not self.alert_manager:
                return
            
            # Get stats
            stats = self.alert_manager.get_stats()
            
            # Update stats frame
            for widget in self.stats_frame.winfo_children():
                widget.destroy()
            
            stat_items = [
                ("Total Alerts", stats["total_alerts"]),
                ("Last Hour", stats["last_hour"]),
                ("Last Day", stats["last_day"]),
                ("Cooldowns Active", stats["cooldowns_active"])
            ]
            
            for label, value in stat_items:
                frame = ctk.CTkFrame(self.stats_frame)
                frame.pack(side="left", padx=10, pady=5, expand=True, fill="both")
                
                ctk.CTkLabel(frame, text=str(value), font=("Arial", 20, "bold")).pack()
                ctk.CTkLabel(frame, text=label, font=("Arial", 10)).pack()
            
            # Get history
            history = self.alert_manager.get_alert_history(limit=50)
            
            # Display history
            self.history_text.delete("1.0", "end")
            
            if not history:
                self.history_text.insert("1.0", "No alerts sent yet.\n\nUse the test buttons to verify your configuration.")
            else:
                for alert in reversed(history):  # Most recent first
                    timestamp = alert.get("timestamp", 0)
                    from datetime import datetime
                    time_str = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
                    
                    alert_type = alert.get("type", "unknown")
                    title = alert.get("title", "No title")
                    channels = ", ".join(alert.get("channels", []))
                    
                    line = f"[{time_str}] {title} ({alert_type}) → {channels}\n"
                    self.history_text.insert("end", line)
            
        except Exception as e:
            self.logger.error(f"Failed to refresh history: {e}")
            self.history_text.delete("1.0", "end")
            self.history_text.insert("1.0", f"Error loading history:\n{str(e)}")
    
    def get_alert_manager(self) -> Optional[AlertManager]:
        """Get the configured alert manager"""
        return self.alert_manager


if __name__ == "__main__":
    # Test the panel
    import sys
    
    logging.basicConfig(level=logging.INFO)
    
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    
    app = ctk.CTk()
    app.title("Alert Settings Test")
    app.geometry("800x600")
    
    panel = AlertsPanel(app)
    panel.pack(fill="both", expand=True)
    
    app.mainloop()
