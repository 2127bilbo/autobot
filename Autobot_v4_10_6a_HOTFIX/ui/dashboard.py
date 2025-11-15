"""
Autobot Dashboard - Main UI with all panels
Complete CustomTkinter interface with dark purple theme
"""

import customtkinter as ctk
from tkinter import filedialog, messagebox
import threading
import time
from datetime import datetime
from typing import Dict, List, Optional
import json

# Import core modules
from core.task_manager import TaskManager
from core.captcha_queue import CaptchaQueue
from core.webhook import DiscordWebhook
from core.monitor import ProductMonitor
from database.db_manager import DatabaseManager

# Import alert system
from ui.alerts_panel import AlertsPanel
from ui.site_management_panel import SiteManagementPanel

# Set appearance
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class AutobotApp(ctk.CTk):
    """Main Autobot application window"""
    
    def __init__(self):
        super().__init__()
        
        # Window configuration
        self.title("Autobot - Retail Automation")
        self.geometry("1400x900")
        self.minsize(1200, 700)
        
        # Dark purple color scheme
        self.colors = {
            "bg_primary": "#1a1625",
            "bg_secondary": "#231d2e",
            "bg_tertiary": "#2d2538",
            "accent": "#8b5cf6",
            "accent_hover": "#a78bfa",
            "text_primary": "#ffffff",
            "text_secondary": "#a0a0a0",
            "success": "#10b981",
            "error": "#ef4444",
            "warning": "#f59e0b",
            "info": "#3b82f6"
        }
        
        self.configure(fg_color=self.colors["bg_primary"])
        
        # Initialize core systems
        self.db = DatabaseManager()
        self.task_manager = TaskManager(self.db)
        self.captcha_queue = CaptchaQueue()
        self.webhook = DiscordWebhook()
        self.product_monitor = ProductMonitor(self.task_manager, self.webhook, self.db)  # V4.10.6: Pass db for API learning
        
        # Load settings
        self.settings = self.db.get_settings()
        if self.settings and self.settings.get('webhook_url'):
            self.webhook.set_webhook_url(self.settings['webhook_url'])
        
        # Setup task manager callbacks (thread-safe wrappers)
        self.task_manager.on_status_change = self.on_task_status_change
        self.task_manager.on_log = self._thread_safe_log
        
        # Setup product monitor callbacks (thread-safe)
        self.product_monitor.add_callback(self._thread_safe_monitor_event)
        
        # UI state
        self.current_panel = "dashboard"
        self.activity_logs = []
        
        # Grid configuration
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # Create UI
        self.create_sidebar()
        self.create_main_area()
        
        # Create all panels
        self.create_dashboard_panel()
        self.create_tasks_panel()
        self.create_monitor_panel()
        self.create_captcha_panel()
        self.create_profiles_panel()
        self.create_proxies_panel()
        self.create_alerts_panel()
        self.create_sites_panel()
        self.create_settings_panel()
        
        # Show dashboard by default
        self.show_panel("dashboard")
        
        # Start update loop
        self.update_ui_loop()
    
    def create_sidebar(self):
        """Create navigation sidebar"""
        self.sidebar = ctk.CTkFrame(self, width=250, fg_color=self.colors["bg_secondary"])
        self.sidebar.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        self.sidebar.grid_propagate(False)
        
        # Logo/Title
        title = ctk.CTkLabel(
            self.sidebar,
            text="🤖 AUTOBOT",
            font=("Arial Bold", 24),
            text_color=self.colors["accent"]
        )
        title.pack(pady=30)
        
        # Navigation buttons
        self.nav_buttons = {}
        nav_items = [
            ("📊 Dashboard", "dashboard"),
            ("📋 Tasks", "tasks"),
            ("👁️ Monitor", "monitor"),
            ("🔐 Captcha", "captcha"),
            ("👤 Profiles", "profiles"),
            ("🌐 Proxies", "proxies"),
            ("🔔 Alerts", "alerts"),
            ("🌍 Sites", "sites"),
            ("⚙️ Settings", "settings"),
        ]
        
        for label, panel_name in nav_items:
            btn = ctk.CTkButton(
                self.sidebar,
                text=label,
                command=lambda p=panel_name: self.show_panel(p),
                fg_color="transparent",
                hover_color=self.colors["bg_tertiary"],
                anchor="w",
                height=45,
                font=("Arial", 14)
            )
            btn.pack(fill="x", padx=15, pady=5)
            self.nav_buttons[panel_name] = btn
        
        # Version info at bottom
        version_label = ctk.CTkLabel(
            self.sidebar,
            text="v4.5 | Phase 4 Complete",
            font=("Arial", 10),
            text_color=self.colors["text_secondary"]
        )
        version_label.pack(side="bottom", pady=20)
    
    def create_main_area(self):
        """Create main content area"""
        self.main_frame = ctk.CTkFrame(self, fg_color=self.colors["bg_primary"])
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(0, weight=1)
        
        # Container for panels
        self.panels = {}
    
    def show_panel(self, panel_name: str):
        """Switch to a specific panel"""
        # Hide all panels
        for name, panel in self.panels.items():
            if panel.winfo_exists():
                panel.grid_remove()
        
        # Show selected panel
        if panel_name in self.panels:
            self.panels[panel_name].grid(row=0, column=0, sticky="nsew")
        
        # Update nav button colors
        for name, btn in self.nav_buttons.items():
            if name == panel_name:
                btn.configure(fg_color=self.colors["accent"])
            else:
                btn.configure(fg_color="transparent")
        
        self.current_panel = panel_name
        
        # Refresh panel-specific content
        if panel_name == "tasks":
            self.refresh_tasks()
        elif panel_name == "monitor":
            self.update_monitor_display()
    
    # ========================================
    # DASHBOARD PANEL
    # ========================================
    
    def create_dashboard_panel(self):
        """Create dashboard with stats and activity log"""
        panel = ctk.CTkFrame(self.main_frame, fg_color=self.colors["bg_primary"])
        
        # Title
        title = ctk.CTkLabel(panel, text="📊 Dashboard", font=("Arial Bold", 28))
        title.pack(pady=20)
        
        # Stats frame
        stats_frame = ctk.CTkFrame(panel, fg_color="transparent")
        stats_frame.pack(fill="x", padx=20, pady=10)
        
        # Create 4 stat cards
        self.stat_cards = {}
        stat_items = [
            ("tasks_total", "Total Tasks", "0", self.colors["info"]),
            ("tasks_running", "Running", "0", self.colors["success"]),
            ("tasks_success", "Success", "0", self.colors["success"]),
            ("tasks_failed", "Failed", "0", self.colors["error"])
        ]
        
        for i, (key, label, value, color) in enumerate(stat_items):
            card = self.create_stat_card(stats_frame, label, value, color)
            card.grid(row=0, column=i, padx=10, pady=10, sticky="ew")
            stats_frame.grid_columnconfigure(i, weight=1)
            self.stat_cards[key] = card
        
        # Activity log
        log_label = ctk.CTkLabel(panel, text="Recent Activity", font=("Arial Bold", 18))
        log_label.pack(pady=(20, 10))
        
        self.activity_text = ctk.CTkTextbox(panel, height=400, fg_color=self.colors["bg_secondary"])
        self.activity_text.pack(fill="both", expand=True, padx=20, pady=10)
        
        self.panels["dashboard"] = panel
    
    def create_stat_card(self, parent, label: str, value: str, color: str):
        """Create a statistics card"""
        card = ctk.CTkFrame(parent, fg_color=self.colors["bg_secondary"], height=120)
        card.grid_propagate(False)
        
        value_label = ctk.CTkLabel(
            card,
            text=value,
            font=("Arial Bold", 36),
            text_color=color
        )
        value_label.pack(pady=(20, 5))
        
        label_widget = ctk.CTkLabel(
            card,
            text=label,
            font=("Arial", 14),
            text_color=self.colors["text_secondary"]
        )
        label_widget.pack()
        
        # Store reference for updates
        card.value_label = value_label
        
        return card
    
    # Continued in next part...
    
    # ========================================
    # TASKS PANEL
    # ========================================
    
    def create_tasks_panel(self):
        """Create tasks management panel"""
        panel = ctk.CTkFrame(self.main_frame, fg_color=self.colors["bg_primary"])
        
        # Title
        title = ctk.CTkLabel(panel, text="📋 Task Management", font=("Arial Bold", 28))
        title.pack(pady=20)
        
        # Controls frame
        controls = ctk.CTkFrame(panel, fg_color="transparent")
        controls.pack(fill="x", padx=20, pady=10)
        
        create_btn = ctk.CTkButton(
            controls,
            text="➕ Create Task",
            command=self.show_create_task_dialog,
            fg_color=self.colors["success"],
            hover_color="#059669",
            height=40,
            font=("Arial Bold", 14)
        )
        create_btn.pack(side="left", padx=5)
        
        edit_btn = ctk.CTkButton(
            controls,
            text="✏️ Edit Selected",
            command=self.edit_selected_task,
            fg_color=self.colors["info"],
            hover_color="#2563eb",
            height=40
        )
        edit_btn.pack(side="left", padx=5)
        
        start_btn = ctk.CTkButton(
            controls,
            text="▶️ Start Selected",
            command=self.start_selected_tasks,
            height=40
        )
        start_btn.pack(side="left", padx=5)
        
        stop_btn = ctk.CTkButton(
            controls,
            text="⏸️ Stop Selected",
            command=self.stop_selected_tasks,
            height=40
        )
        stop_btn.pack(side="left", padx=5)
        
        delete_btn = ctk.CTkButton(
            controls,
            text="🗑️ Delete Selected",
            command=self.delete_selected_tasks,
            fg_color=self.colors["error"],
            hover_color="#dc2626",
            height=40
        )
        delete_btn.pack(side="left", padx=5)
        
        # Task list frame
        list_frame = ctk.CTkFrame(panel, fg_color=self.colors["bg_secondary"])
        list_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        # Scrollable frame for tasks
        self.tasks_scroll = ctk.CTkScrollableFrame(
            list_frame,
            fg_color=self.colors["bg_secondary"]
        )
        self.tasks_scroll.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.task_widgets = {}
        
        self.panels["tasks"] = panel
    
    # ========================================
    # MONITOR PANEL
    # ========================================
    
    def create_monitor_panel(self):
        """Create product monitoring panel"""
        panel = ctk.CTkFrame(self.main_frame, fg_color=self.colors["bg_primary"])
        
        # Title
        title = ctk.CTkLabel(panel, text="👁️ Product Monitor", font=("Arial Bold", 28))
        title.pack(pady=20)
        
        # Top controls
        controls_frame = ctk.CTkFrame(panel, fg_color="transparent")
        controls_frame.pack(fill="x", padx=20, pady=10)
        
        # Add monitor button
        add_btn = ctk.CTkButton(
            controls_frame,
            text="➕ Add Monitor",
            command=self.show_add_monitor_dialog,
            fg_color=self.colors["accent"],
            hover_color=self.colors["accent_hover"],
            height=40,
            font=("Arial Bold", 14)
        )
        add_btn.pack(side="left", padx=5)
        
        # Start/Stop all buttons
        start_all_btn = ctk.CTkButton(
            controls_frame,
            text="▶️ Start All",
            command=self.start_all_monitors,
            fg_color=self.colors["success"],
            hover_color="#1a7f37",
            height=40,
            width=120,
            font=("Arial Bold", 14)
        )
        start_all_btn.pack(side="left", padx=5)
        
        stop_all_btn = ctk.CTkButton(
            controls_frame,
            text="⏸️ Stop All",
            command=self.stop_all_monitors,
            fg_color=self.colors["error"],
            hover_color="#bd2130",
            height=40,
            width=120,
            font=("Arial Bold", 14)
        )
        stop_all_btn.pack(side="left", padx=5)
        
        # Stats frame
        stats_frame = ctk.CTkFrame(panel, fg_color=self.colors["bg_secondary"])
        stats_frame.pack(fill="x", padx=20, pady=10)
        
        # Monitor stats
        stats_container = ctk.CTkFrame(stats_frame, fg_color="transparent")
        stats_container.pack(pady=15)
        
        # Total Monitors
        self.monitor_total_label = self._create_stat_card(
            stats_container, "Total Monitors", "0", self.colors["accent"]
        )
        self.monitor_total_label.pack(side="left", padx=10)
        
        # Running
        self.monitor_running_label = self._create_stat_card(
            stats_container, "Running", "0", self.colors["success"]
        )
        self.monitor_running_label.pack(side="left", padx=10)
        
        # In Stock
        self.monitor_stock_label = self._create_stat_card(
            stats_container, "In Stock", "0", "#FFD700"
        )
        self.monitor_stock_label.pack(side="left", padx=10)
        
        # Total Checks
        self.monitor_checks_label = self._create_stat_card(
            stats_container, "Total Checks", "0", "#00CED1"
        )
        self.monitor_checks_label.pack(side="left", padx=10)
        
        # Monitors table
        table_frame = ctk.CTkFrame(panel, fg_color=self.colors["bg_secondary"])
        table_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        # Table title
        table_title = ctk.CTkLabel(
            table_frame,
            text="Active Monitors",
            font=("Arial Bold", 16)
        )
        table_title.pack(pady=10)
        
        # Scrollable frame for monitors
        self.monitors_scroll = ctk.CTkScrollableFrame(
            table_frame,
            fg_color=self.colors["bg_tertiary"],
            height=400
        )
        self.monitors_scroll.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Store panel
        self.panels["monitor"] = panel
        
    def _create_stat_card(self, parent, label, value, color):
        """Helper to create stat card"""
        card = ctk.CTkFrame(parent, fg_color=self.colors["bg_tertiary"], width=180, height=80)
        card.pack_propagate(False)
        
        label_widget = ctk.CTkLabel(
            card,
            text=label,
            font=("Arial", 12),
            text_color=self.colors["text_secondary"]
        )
        label_widget.pack(pady=(10, 5))
        
        value_widget = ctk.CTkLabel(
            card,
            text=value,
            font=("Arial Bold", 24),
            text_color=color
        )
        value_widget.pack()
        
        return value_widget
        
    def show_add_monitor_dialog(self):
        """Show dialog to add a new monitor"""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Add Product Monitor")
        dialog.geometry("650x800")
        dialog.transient(self)
        dialog.grab_set()
        
        # Center dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (650 // 2)
        y = (dialog.winfo_screenheight() // 2) - (800 // 2)
        dialog.geometry(f"650x800+{x}+{y}")
        
        # Title
        title = ctk.CTkLabel(dialog, text="➕ Add Product Monitor", font=("Arial Bold", 20))
        title.pack(pady=20)
        
        # Scrollable form frame
        scroll_frame = ctk.CTkScrollableFrame(dialog, fg_color="transparent")
        scroll_frame.pack(fill="both", expand=True, padx=30, pady=10)
        
        # Product URL
        url_label = ctk.CTkLabel(scroll_frame, text="Product URL:", font=("Arial", 14))
        url_label.pack(anchor="w", pady=(0, 5))
        
        url_entry = ctk.CTkEntry(
            scroll_frame,
            placeholder_text="https://www.target.com/p/...",
            height=40,
            font=("Arial", 12)
        )
        url_entry.pack(fill="x", pady=(0, 20))
        
        # Check interval
        interval_label = ctk.CTkLabel(scroll_frame, text="Check Interval (seconds):", font=("Arial", 14))
        interval_label.pack(anchor="w", pady=(0, 5))
        
        interval_entry = ctk.CTkEntry(
            scroll_frame,
            placeholder_text="5",
            height=40,
            font=("Arial", 12)
        )
        interval_entry.insert(0, "5")
        interval_entry.pack(fill="x", pady=(0, 20))
        
        # V4.0 FEATURES - Pricing Section
        v4_pricing_label = ctk.CTkLabel(scroll_frame, text="💰 Pricing & Scalper Detection:", font=("Arial Bold", 14))
        v4_pricing_label.pack(anchor="w", pady=(10, 10))
        
        # Target price
        target_price_label = ctk.CTkLabel(scroll_frame, text="Target Price (expected retail):", font=("Arial", 12))
        target_price_label.pack(anchor="w", pady=(0, 5))
        
        target_price_entry = ctk.CTkEntry(
            scroll_frame,
            placeholder_text="e.g., 79.99",
            height=35,
            font=("Arial", 12)
        )
        target_price_entry.pack(fill="x", pady=(0, 10))
        
        # V4.0 FEATURES - Location Section
        v4_location_label = ctk.CTkLabel(scroll_frame, text="🏪 Local Store Inventory:", font=("Arial Bold", 14))
        v4_location_label.pack(anchor="w", pady=(10, 10))
        
        # Zip code
        zip_label = ctk.CTkLabel(scroll_frame, text="Zip Code (for store availability):", font=("Arial", 12))
        zip_label.pack(anchor="w", pady=(0, 5))
        
        zip_entry = ctk.CTkEntry(
            scroll_frame,
            placeholder_text="e.g., 47401",
            height=35,
            font=("Arial", 12)
        )
        zip_entry.pack(fill="x", pady=(0, 10))
        
        # V4.0 FEATURES - Display Options
        v4_display_label = ctk.CTkLabel(scroll_frame, text="🎨 Display Options:", font=("Arial Bold", 14))
        v4_display_label.pack(anchor="w", pady=(10, 10))
        
        # Show stores checkbox
        show_stores_var = ctk.CTkCheckBox(
            scroll_frame,
            text="Show local store inventory",
            font=("Arial", 12)
        )
        show_stores_var.select()  # Default: ON
        show_stores_var.pack(anchor="w", pady=5)
        
        # Show ratings checkbox
        show_rating_var = ctk.CTkCheckBox(
            scroll_frame,
            text="Show product ratings & reviews",
            font=("Arial", 12)
        )
        show_rating_var.select()  # Default: ON
        show_rating_var.pack(anchor="w", pady=5)
        
        # Show promotions checkbox
        show_promotions_var = ctk.CTkCheckBox(
            scroll_frame,
            text="Show active promotions & deals",
            font=("Arial", 12)
        )
        show_promotions_var.select()  # Default: ON
        show_promotions_var.pack(anchor="w", pady=5)
        
        # Optional Settings Section
        options_label = ctk.CTkLabel(scroll_frame, text="⚙️ Monitor Settings:", font=("Arial Bold", 14))
        options_label.pack(anchor="w", pady=(10, 10))
        
        # Auto-buy checkbox
        auto_buy_var = ctk.CTkCheckBox(
            scroll_frame,
            text="Auto-buy when in stock (create task automatically)",
            font=("Arial", 12)
        )
        auto_buy_var.select()  # Default: ON
        auto_buy_var.pack(anchor="w", pady=5)
        
        # Discord notify checkbox
        discord_notify_var = ctk.CTkCheckBox(
            scroll_frame,
            text="Send Discord notification on stock",
            font=("Arial", 12)
        )
        discord_notify_var.select()  # Default: ON
        discord_notify_var.pack(anchor="w", pady=5)
        
        # Detailed logging checkbox
        detailed_log_var = ctk.CTkCheckBox(
            scroll_frame,
            text="Show detailed price/stock info in activity log",
            font=("Arial", 12)
        )
        detailed_log_var.deselect()  # Default: OFF (keep it clean)
        detailed_log_var.pack(anchor="w", pady=5)
        
        # ========================================
        # PHASE 2A: DROP SCHEDULING
        # ========================================
        drop_label = ctk.CTkLabel(scroll_frame, text="⏰ Drop Scheduling (Phase 2A):", font=("Arial Bold", 14))
        drop_label.pack(anchor="w", pady=(20, 10))
        
        # Enable drop scheduling
        enable_drop_var = ctk.CTkCheckBox(
            scroll_frame,
            text="Enable scheduled drop monitoring",
            font=("Arial", 12)
        )
        enable_drop_var.pack(anchor="w", pady=5)
        
        # Drop scheduling frame (only visible when enabled)
        drop_frame = ctk.CTkFrame(scroll_frame, fg_color=self.colors["bg_primary"])
        drop_frame.pack(fill="x", pady=10)
        drop_frame.pack_forget()  # Hide initially
        
        def toggle_drop_scheduling():
            if enable_drop_var.get():
                drop_frame.pack(fill="x", pady=10)
            else:
                drop_frame.pack_forget()
        
        enable_drop_var.configure(command=toggle_drop_scheduling)
        
        # Drop time input
        time_label = ctk.CTkLabel(drop_frame, text="Drop Time (HH:MM:SS):", font=("Arial", 12))
        time_label.pack(anchor="w", padx=15, pady=(10, 5))
        
        time_input_frame = ctk.CTkFrame(drop_frame, fg_color="transparent")
        time_input_frame.pack(anchor="w", padx=15, pady=5)
        
        hour_entry = ctk.CTkEntry(time_input_frame, width=60, placeholder_text="18")
        hour_entry.pack(side="left", padx=(0, 5))
        ctk.CTkLabel(time_input_frame, text=":").pack(side="left")
        
        minute_entry = ctk.CTkEntry(time_input_frame, width=60, placeholder_text="00")
        minute_entry.pack(side="left", padx=5)
        ctk.CTkLabel(time_input_frame, text=":").pack(side="left")
        
        second_entry = ctk.CTkEntry(time_input_frame, width=60, placeholder_text="00")
        second_entry.pack(side="left", padx=(5, 0))
        
        # Pre-drop start time
        pre_drop_label = ctk.CTkLabel(drop_frame, text="Start monitoring before drop:", font=("Arial", 12))
        pre_drop_label.pack(anchor="w", padx=15, pady=(15, 5))
        
        pre_drop_input_frame = ctk.CTkFrame(drop_frame, fg_color="transparent")
        pre_drop_input_frame.pack(anchor="w", padx=15, pady=5)
        
        pre_drop_min_entry = ctk.CTkEntry(pre_drop_input_frame, width=60, placeholder_text="0")
        pre_drop_min_entry.insert(0, "0")
        pre_drop_min_entry.pack(side="left", padx=(0, 5))
        ctk.CTkLabel(pre_drop_input_frame, text="minutes").pack(side="left", padx=(0, 15))
        
        pre_drop_sec_entry = ctk.CTkEntry(pre_drop_input_frame, width=60, placeholder_text="15")
        pre_drop_sec_entry.insert(0, "15")
        pre_drop_sec_entry.pack(side="left", padx=(0, 5))
        ctk.CTkLabel(pre_drop_input_frame, text="seconds").pack(side="left")
        
        # Timezone selection
        timezone_label = ctk.CTkLabel(drop_frame, text="Timezone:", font=("Arial", 12))
        timezone_label.pack(anchor="w", padx=15, pady=(15, 5))
        
        timezones = [
            "America/New_York (EST/EDT)",
            "America/Chicago (CST/CDT)", 
            "America/Denver (MST/MDT)",
            "America/Phoenix (MST - No DST)",
            "America/Los_Angeles (PST/PDT)",
            "America/Anchorage (AKST/AKDT)",
            "Pacific/Honolulu (HST)",
            "America/Puerto_Rico (AST)"
        ]
        
        timezone_var = ctk.StringVar(value=timezones[0])
        timezone_menu = ctk.CTkOptionMenu(
            drop_frame,
            values=timezones,
            variable=timezone_var,
            width=300
        )
        timezone_menu.pack(anchor="w", padx=15, pady=5)
        
        # Aggressive duration
        aggressive_label = ctk.CTkLabel(drop_frame, text="Aggressive monitoring duration (minutes):", font=("Arial", 12))
        aggressive_label.pack(anchor="w", padx=15, pady=(15, 5))
        
        aggressive_entry = ctk.CTkEntry(drop_frame, width=100, placeholder_text="5")
        aggressive_entry.insert(0, "5")
        aggressive_entry.pack(anchor="w", padx=15, pady=5)
        
        ctk.CTkLabel(
            drop_frame,
            text="💡 Example: Drop at 6:00 PM, start 15 seconds before = monitoring begins at 5:59:45 PM",
            font=("Arial", 10),
            text_color=self.colors["text_secondary"],
            wraplength=550
        ).pack(anchor="w", padx=15, pady=(10, 15))
        
        # Site info
        info_label = ctk.CTkLabel(
            scroll_frame,
            text="✅ Supported: Target, Walmart, Pokemon Center\n⚡ Lower intervals = faster detection but more requests\n🎯 v4.0 features work best with Target.com",
            font=("Arial", 11),
            text_color=self.colors["text_secondary"],
            justify="left"
        )
        info_label.pack(anchor="w", pady=10)
        
        # Buttons
        button_frame = ctk.CTkFrame(scroll_frame, fg_color="transparent")
        button_frame.pack(fill="x", pady=20)
        
        def add_monitor():
            url = url_entry.get().strip()
            try:
                interval = int(interval_entry.get().strip())
            except:
                interval = 5
                
            if not url:
                return
            
            # Get optional settings
            settings = {
                'auto_buy': auto_buy_var.get() == 1,
                'discord_notify': discord_notify_var.get() == 1,
                'detailed_log': detailed_log_var.get() == 1,
                # V4.0 settings
                'target_price': float(target_price_entry.get().strip()) if target_price_entry.get().strip() else 0.0,
                'zip_code': zip_entry.get().strip(),
                'show_stores': show_stores_var.get() == 1,
                'show_rating': show_rating_var.get() == 1,
                'show_promotions': show_promotions_var.get() == 1
            }
            
            # Phase 2A: Drop Scheduling settings
            if enable_drop_var.get() == 1:
                try:
                    from datetime import datetime
                    
                    # Parse drop time
                    hour = int(hour_entry.get().strip() or "0")
                    minute = int(minute_entry.get().strip() or "0")
                    second = int(second_entry.get().strip() or "0")
                    
                    # Parse pre-drop time
                    pre_drop_minutes = int(pre_drop_min_entry.get().strip() or "0")
                    pre_drop_seconds = int(pre_drop_sec_entry.get().strip() or "0")
                    
                    # Parse aggressive duration
                    aggressive_duration = int(aggressive_entry.get().strip() or "5")
                    
                    # Extract timezone (before the parenthesis)
                    timezone_str = timezone_var.get().split(' ')[0]
                    
                    settings['enable_drop_scheduling'] = True
                    settings['drop_hour'] = hour
                    settings['drop_minute'] = minute
                    settings['drop_second'] = second
                    settings['pre_drop_minutes'] = pre_drop_minutes
                    settings['pre_drop_seconds'] = pre_drop_seconds
                    settings['drop_timezone'] = timezone_str
                    settings['aggressive_duration_minutes'] = aggressive_duration
                    
                except Exception as e:
                    self.add_activity_log(f"⚠️ Drop scheduling error: {e}", color=self.colors["warning"])
                    settings['enable_drop_scheduling'] = False
            else:
                settings['enable_drop_scheduling'] = False
                
            # Add monitor with settings
            monitor_id = self.product_monitor.add_monitor(url, interval, settings)
            self.add_activity_log(f"Monitor added: {monitor_id}")
            
            # Start it immediately
            self.product_monitor.start_monitor(monitor_id)
            self.add_activity_log(f"Monitor started: {monitor_id}")
            
            dialog.destroy()
            
        add_button = ctk.CTkButton(
            button_frame,
            text="Add Monitor",
            command=add_monitor,
            fg_color=self.colors["accent"],
            hover_color=self.colors["accent_hover"],
            height=45,
            width=200,
            font=("Arial Bold", 14)
        )
        add_button.pack(side="left", expand=True, padx=5)
        
        cancel_button = ctk.CTkButton(
            button_frame,
            text="Cancel",
            command=dialog.destroy,
            fg_color=self.colors["bg_tertiary"],
            hover_color=self.colors["bg_secondary"],
            height=45,
            width=200,
            font=("Arial Bold", 14)
        )
        cancel_button.pack(side="left", expand=True, padx=5)
        
    def start_all_monitors(self):
        """Start all monitors"""
        self.product_monitor.start_all()
        self.add_activity_log("All monitors started")
        
    def stop_all_monitors(self):
        """Stop all monitors"""
        self.product_monitor.stop_all()
        self.add_activity_log("All monitors stopped")
        
    def on_monitor_event(self, event_type: str, data: dict):
        """Handle monitor events"""
        if event_type == 'preorder_detected':
            self.add_activity_log(
                f"⏰ PRE-ORDER DETECTED: {data['product_name']} - Monitoring for release",
                color=self.colors["warning"]
            )
        elif event_type == 'stock_found':
            was_preorder = data.get('was_preorder', False)
            if was_preorder:
                self.add_activity_log(
                    f"🎯 PRE-ORDER NOW LIVE: {data['product_name']} - Auto-task created!",
                    color=self.colors["success"]
                )
            else:
                self.add_activity_log(
                    f"🎯 STOCK ALERT: {data['product_name']} - Auto-task created!",
                    color=self.colors["success"]
                )
        elif event_type == 'auto_task_created':
            self.add_activity_log(
                f"✅ Auto-task {data['task_id']} created for {data['product_name']}",
                color=self.colors["success"]
            )
        elif event_type == 'error':
            self.add_activity_log(
                f"❌ Monitor error: {data['error']}",
                color=self.colors["error"]
            )
            
    def update_monitor_display(self):
        """Update monitor panel display"""
        if self.current_panel != "monitor":
            return
            
        # Update stats - these labels are CTkLabel widgets returned by _create_stat_card
        stats = self.product_monitor.get_stats()
        self.monitor_total_label.configure(text=str(stats['total_monitors']))
        self.monitor_running_label.configure(text=str(stats['running_monitors']))
        self.monitor_stock_label.configure(text=str(stats['products_in_stock']))
        self.monitor_checks_label.configure(text=str(stats['total_checks']))
        
        # Clear monitors display
        for widget in self.monitors_scroll.winfo_children():
            widget.destroy()
            
        # Display all monitors
        monitors = self.product_monitor.get_all_monitors()
        
        if not monitors:
            no_monitors_label = ctk.CTkLabel(
                self.monitors_scroll,
                text="No monitors yet. Click 'Add Monitor' to start!",
                font=("Arial", 14),
                text_color=self.colors["text_secondary"]
            )
            no_monitors_label.pack(pady=50)
            return
            
        for monitor in monitors:
            self._create_monitor_row(monitor)
            
    def _create_monitor_row(self, monitor):
        """Create an enhanced v4.0 monitor card"""
        # Main container - dynamic height based on content
        row = ctk.CTkFrame(
            self.monitors_scroll,
            fg_color=self.colors["bg_secondary"],
        )
        row.pack(fill="x", padx=5, pady=8)
        
        # === TOP SECTION: Header with status ===
        header_frame = ctk.CTkFrame(row, fg_color=self.colors["bg_tertiary"])
        header_frame.pack(fill="x", padx=2, pady=2)
        
        # Left: Product info
        header_left = ctk.CTkFrame(header_frame, fg_color="transparent")
        header_left.pack(side="left", fill="x", expand=True, padx=15, pady=8)
        
        # Product name (bold, larger)
        name_label = ctk.CTkLabel(
            header_left,
            text=f"📦 {monitor.product_name}",
            font=("Arial Bold", 14),
            text_color=self.colors["text_primary"]
        )
        name_label.pack(anchor="w")
        
        # Site and ID
        meta_label = ctk.CTkLabel(
            header_left,
            text=f"Site: {monitor.site.upper()} | ID: {monitor.monitor_id}",
            font=("Arial", 10),
            text_color=self.colors["text_secondary"]
        )
        meta_label.pack(anchor="w")
        
        # Right: Status badges
        header_right = ctk.CTkFrame(header_frame, fg_color="transparent")
        header_right.pack(side="right", padx=15, pady=8)
        
        # Running status
        if monitor.is_running:
            status_color = self.colors["success"]
            status_text = "🟢 RUNNING"
        else:
            status_color = self.colors["text_secondary"]
            status_text = "⚫ STOPPED"
            
        status_label = ctk.CTkLabel(
            header_right,
            text=status_text,
            font=("Arial Bold", 11),
            text_color=status_color
        )
        status_label.pack(side="top", anchor="e")
        
        # Stock status
        if hasattr(monitor, 'is_preorder') and monitor.is_preorder and not monitor.in_stock:
            stock_text = "⏰ PRE-ORDER"
            stock_color = "#FFA500"
        elif monitor.in_stock:
            stock_text = "✅ IN STOCK"
            stock_color = "#FFD700"
        else:
            stock_text = "❌ OUT OF STOCK"
            stock_color = self.colors["error"]
            
        stock_label = ctk.CTkLabel(
            header_right,
            text=stock_text,
            font=("Arial Bold", 10),
            text_color=stock_color
        )
        stock_label.pack(side="top", anchor="e", pady=(2, 0))
        
        # === CONTENT SECTION ===
        content_frame = ctk.CTkFrame(row, fg_color="transparent")
        content_frame.pack(fill="both", expand=True, padx=10, pady=8)
        
        # === LEFT COLUMN: Image placeholder + Quick actions ===
        left_column = ctk.CTkFrame(content_frame, fg_color=self.colors["bg_tertiary"], width=120)
        left_column.pack(side="left", fill="y", padx=(0, 10))
        left_column.pack_propagate(False)
        
        # Image placeholder (v4.0 - image_url available)
        if hasattr(monitor, 'image_url') and monitor.image_url:
            image_text = "🖼️\nImage\nAvailable"
        else:
            image_text = "📷\nNo\nImage"
            
        image_label = ctk.CTkLabel(
            left_column,
            text=image_text,
            font=("Arial", 10),
            text_color=self.colors["text_secondary"],
            width=100,
            height=80,
            fg_color=self.colors["bg_secondary"]
        )
        image_label.pack(padx=10, pady=10)
        
        # Quick link button (v4.0 feature)
        open_btn = ctk.CTkButton(
            left_column,
            text="🔗 Open",
            command=lambda: self._open_product_url(monitor.product_url),
            fg_color=self.colors["accent"],
            hover_color=self.colors["accent_hover"],
            height=30,
            width=100,
            font=("Arial", 10)
        )
        open_btn.pack(padx=10, pady=(0, 10))
        
        # === MIDDLE COLUMN: Main product data ===
        middle_column = ctk.CTkFrame(content_frame, fg_color="transparent")
        middle_column.pack(side="left", fill="both", expand=True, padx=(0, 10))
        
        # Price section with scalper detection (v4.0)
        price_frame = ctk.CTkFrame(middle_column, fg_color=self.colors["bg_tertiary"])
        price_frame.pack(fill="x", pady=(0, 8))
        
        # Current price
        if monitor.product_price > 0:
            price_text = f"💰 Current: ${monitor.product_price:.2f}"
            price_label = ctk.CTkLabel(
                price_frame,
                text=price_text,
                font=("Arial Bold", 13),
                text_color=self.colors["text_primary"]
            )
            price_label.pack(anchor="w", padx=10, pady=(8, 2))
            
            # V4.0: Scalper detection
            if hasattr(monitor, 'target_price') and monitor.target_price > 0:
                markup_percent = ((monitor.product_price - monitor.target_price) / monitor.target_price) * 100
                
                if markup_percent <= 0:
                    # Great deal!
                    scalper_text = f"🟢 GREAT DEAL! ({markup_percent:.1f}% below target ${monitor.target_price:.2f})"
                    scalper_color = self.colors["success"]
                elif markup_percent <= 20:
                    # Slight markup
                    scalper_text = f"🟡 SLIGHT MARKUP (+{markup_percent:.1f}% vs target ${monitor.target_price:.2f})"
                    scalper_color = "#FFA500"  # Orange
                else:
                    # Scalped!
                    scalper_text = f"🔴 SCALPED! (+{markup_percent:.1f}% vs target ${monitor.target_price:.2f})"
                    scalper_color = self.colors["error"]
                    
                scalper_label = ctk.CTkLabel(
                    price_frame,
                    text=scalper_text,
                    font=("Arial Bold", 11),
                    text_color=scalper_color
                )
                scalper_label.pack(anchor="w", padx=10, pady=(0, 8))
        else:
            price_label = ctk.CTkLabel(
                price_frame,
                text="💰 Price: N/A",
                font=("Arial", 12),
                text_color=self.colors["text_secondary"]
            )
            price_label.pack(anchor="w", padx=10, pady=8)
        
        # V4.0: Rating & Reviews
        if hasattr(monitor, 'rating') and monitor.rating and hasattr(monitor, 'show_rating') and monitor.show_rating:
            rating_text = f"⭐ Rating: {monitor.rating:.1f}/5.0"
            if hasattr(monitor, 'review_count') and monitor.review_count:
                rating_text += f" ({monitor.review_count} reviews)"
                
            rating_label = ctk.CTkLabel(
                middle_column,
                text=rating_text,
                font=("Arial", 11),
                text_color="#FFD700"
            )
            rating_label.pack(anchor="w", pady=(0, 5))
        
        # V4.0: Promotions
        if hasattr(monitor, 'promotions') and monitor.promotions and hasattr(monitor, 'show_promotions') and monitor.show_promotions:
            promo_frame = ctk.CTkFrame(middle_column, fg_color=self.colors["bg_tertiary"])
            promo_frame.pack(fill="x", pady=(0, 8))
            
            promo_title = ctk.CTkLabel(
                promo_frame,
                text="🎁 PROMOTIONS:",
                font=("Arial Bold", 11),
                text_color=self.colors["accent"]
            )
            promo_title.pack(anchor="w", padx=10, pady=(5, 2))
            
            # Show up to 3 promotions in compact form
            promos_to_show = monitor.promotions.split('\n')[:3] if isinstance(monitor.promotions, str) else []
            for promo in promos_to_show:
                if promo.strip():
                    promo_label = ctk.CTkLabel(
                        promo_frame,
                        text=f"  • {promo.strip()}",
                        font=("Arial", 10),
                        text_color=self.colors["text_primary"]
                    )
                    promo_label.pack(anchor="w", padx=15, pady=1)
            
            promo_frame.pack_configure(pady=(0, 8))
        
        # V4.0: Local Stores
        if hasattr(monitor, 'local_stores') and monitor.local_stores and hasattr(monitor, 'show_stores') and monitor.show_stores:
            stores_frame = ctk.CTkFrame(middle_column, fg_color=self.colors["bg_tertiary"])
            stores_frame.pack(fill="x", pady=(0, 8))
            
            stores_title = ctk.CTkLabel(
                stores_frame,
                text="🏪 LOCAL STORES:",
                font=("Arial Bold", 11),
                text_color=self.colors["accent"]
            )
            stores_title.pack(anchor="w", padx=10, pady=(5, 2))
            
            # Show up to 2 stores in compact form
            stores_to_show = monitor.local_stores.split('\n\n')[:2] if isinstance(monitor.local_stores, str) else []
            for store in stores_to_show:
                if store.strip():
                    # Parse store info
                    lines = store.strip().split('\n')
                    if lines:
                        store_label = ctk.CTkLabel(
                            stores_frame,
                            text=f"  • {lines[0]}",
                            font=("Arial", 10),
                            text_color=self.colors["text_primary"]
                        )
                        store_label.pack(anchor="w", padx=15, pady=1)
        
        # Monitor stats
        stats_text = f"📊 Checks: {monitor.check_count} | Interval: {monitor.check_interval}s"
        if monitor.last_check:
            stats_text += f" | Last: {monitor.last_check.strftime('%H:%M:%S')}"
        stats_label = ctk.CTkLabel(
            middle_column,
            text=stats_text,
            font=("Arial", 9),
            text_color=self.colors["text_secondary"]
        )
        stats_label.pack(anchor="w", pady=(5, 0))
        
        # === RIGHT COLUMN: Control buttons ===
        right_column = ctk.CTkFrame(content_frame, fg_color="transparent", width=100)
        right_column.pack(side="right", fill="y")
        right_column.pack_propagate(False)
        
        # Start/Stop button
        if monitor.is_running:
            control_btn = ctk.CTkButton(
                right_column,
                text="⏸️ Stop",
                command=lambda m=monitor: self.stop_monitor(m.monitor_id),
                fg_color=self.colors["error"],
                hover_color="#bd2130",
                width=90,
                height=35,
                font=("Arial Bold", 11)
            )
        else:
            control_btn = ctk.CTkButton(
                right_column,
                text="▶️ Start",
                command=lambda m=monitor: self.start_monitor(m.monitor_id),
                fg_color=self.colors["success"],
                hover_color="#1a7f37",
                width=90,
                height=35,
                font=("Arial Bold", 11)
            )
        control_btn.pack(pady=(0, 8))
        
        # Delete button
        delete_btn = ctk.CTkButton(
            right_column,
            text="🗑️ Delete",
            command=lambda m=monitor: self.delete_monitor(m.monitor_id),
            fg_color=self.colors["bg_tertiary"],
            hover_color=self.colors["bg_secondary"],
            width=90,
            height=35,
            font=("Arial", 11)
        )
        delete_btn.pack()
        
    def _open_product_url(self, url):
        """Open product URL in default browser (v4.0 Quick Links feature)"""
        import webbrowser
        try:
            webbrowser.open(url)
            self.add_activity_log(f"Opened product URL in browser")
        except Exception as e:
            self.add_activity_log(f"Failed to open URL: {str(e)}")
        
    def start_monitor(self, monitor_id: str):
        """Start a specific monitor"""
        self.product_monitor.start_monitor(monitor_id)
        self.add_activity_log(f"Monitor started: {monitor_id}")
        
    def stop_monitor(self, monitor_id: str):
        """Stop a specific monitor"""
        self.product_monitor.stop_monitor(monitor_id)
        self.add_activity_log(f"Monitor stopped: {monitor_id}")
        
    def delete_monitor(self, monitor_id: str):
        """Delete a monitor"""
        self.product_monitor.delete_monitor(monitor_id)
        self.add_activity_log(f"Monitor deleted: {monitor_id}")
    
    # ========================================
    # CAPTCHA PANEL
    # ========================================
    
    def create_captcha_panel(self):
        """Create captcha harvesting panel"""
        panel = ctk.CTkFrame(self.main_frame, fg_color=self.colors["bg_primary"])
        
        # Title
        title = ctk.CTkLabel(panel, text="🔐 Captcha Harvester", font=("Arial Bold", 28))
        title.pack(pady=20)
        
        # Stats
        stats_frame = ctk.CTkFrame(panel, fg_color=self.colors["bg_secondary"])
        stats_frame.pack(fill="x", padx=20, pady=10)
        
        self.captcha_stats_label = ctk.CTkLabel(
            stats_frame,
            text="Queue: 0 | Pending: 0 | Solved: 0",
            font=("Arial Bold", 16)
        )
        self.captcha_stats_label.pack(pady=15)
        
        # Controls
        controls = ctk.CTkFrame(panel, fg_color="transparent")
        controls.pack(fill="x", padx=20, pady=10)
        
        self.harvester_btn1 = ctk.CTkButton(
            controls,
            text="🌐 Open Harvester 1",
            command=lambda: self.open_captcha_harvester(1),
            height=50,
            font=("Arial Bold", 14)
        )
        self.harvester_btn1.pack(side="left", padx=10, expand=True, fill="x")
        
        self.harvester_btn2 = ctk.CTkButton(
            controls,
            text="🌐 Open Harvester 2",
            command=lambda: self.open_captcha_harvester(2),
            height=50,
            font=("Arial Bold", 14)
        )
        self.harvester_btn2.pack(side="left", padx=10, expand=True, fill="x")
        
        # Info
        info_text = """
        📝 Captcha Harvesting Instructions:
        
        1. Click "Open Harvester" to launch a browser window
        2. Solve captchas manually in the browser
        3. Tokens are automatically harvested and queued
        4. Tasks waiting for captcha will use queued tokens
        5. You can open multiple harvesters simultaneously
        
        Note: Manual captcha solving only - no automated solving
        """
        
        info_label = ctk.CTkTextbox(panel, height=300, fg_color=self.colors["bg_secondary"])
        info_label.insert("1.0", info_text)
        info_label.configure(state="disabled")
        info_label.pack(fill="both", expand=True, padx=20, pady=10)
        
        self.panels["captcha"] = panel
    
    # ========================================
    # PROFILES PANEL
    # ========================================
    
    def create_profiles_panel(self):
        """Create profiles management panel"""
        panel = ctk.CTkFrame(self.main_frame, fg_color=self.colors["bg_primary"])
        
        # Title
        title = ctk.CTkLabel(panel, text="👤 Profiles", font=("Arial Bold", 28))
        title.pack(pady=20)
        
        # Controls
        controls = ctk.CTkFrame(panel, fg_color="transparent")
        controls.pack(fill="x", padx=20, pady=10)
        
        add_btn = ctk.CTkButton(
            controls,
            text="➕ Add Profile",
            command=self.show_add_profile_dialog,
            fg_color=self.colors["success"],
            hover_color="#059669",
            height=40,
            font=("Arial Bold", 14)
        )
        add_btn.pack(side="left", padx=5)
        
        # Profiles list
        self.profiles_scroll = ctk.CTkScrollableFrame(
            panel,
            fg_color=self.colors["bg_secondary"]
        )
        self.profiles_scroll.pack(fill="both", expand=True, padx=20, pady=10)
        
        self.refresh_profiles()
        
        self.panels["profiles"] = panel
    
    # ========================================
    # PROXIES PANEL
    # ========================================
    
    def create_proxies_panel(self):
        """Create proxies management panel"""
        panel = ctk.CTkFrame(self.main_frame, fg_color=self.colors["bg_primary"])
        
        # Title
        title = ctk.CTkLabel(panel, text="🌐 Proxies", font=("Arial Bold", 28))
        title.pack(pady=20)
        
        # Controls
        controls = ctk.CTkFrame(panel, fg_color="transparent")
        controls.pack(fill="x", padx=20, pady=10)
        
        add_btn = ctk.CTkButton(
            controls,
            text="➕ Add Proxy",
            command=self.show_add_proxy_dialog,
            fg_color=self.colors["success"],
            height=40
        )
        add_btn.pack(side="left", padx=5)
        
        import_btn = ctk.CTkButton(
            controls,
            text="📁 Import from File",
            command=self.import_proxies,
            height=40
        )
        import_btn.pack(side="left", padx=5)
        
        delete_all_btn = ctk.CTkButton(
            controls,
            text="🗑️ Delete All",
            command=self.delete_all_proxies,
            fg_color=self.colors["error"],
            height=40
        )
        delete_all_btn.pack(side="left", padx=5)
        
        # Proxies list
        self.proxies_scroll = ctk.CTkScrollableFrame(
            panel,
            fg_color=self.colors["bg_secondary"]
        )
        self.proxies_scroll.pack(fill="both", expand=True, padx=20, pady=10)
        
        self.refresh_proxies()
        
        self.panels["proxies"] = panel
    
    # Continued...
    
    # ========================================
    # SITE MANAGEMENT PANEL
    # ========================================
    
    def create_sites_panel(self):
        """Create dynamic site management panel"""
        panel = ctk.CTkFrame(self.main_frame, fg_color=self.colors["bg_primary"])
        
        # Use the SiteManagementPanel component
        self.sites_panel_component = SiteManagementPanel(panel)
        self.sites_panel_component.pack(fill="both", expand=True, padx=20, pady=20)
        
        self.panels["sites"] = panel
    
    # ========================================
    # ALERTS PANEL
    # ========================================
    
    def create_alerts_panel(self):
        """Create smart alerts panel for SMS, Email, Push notifications"""
        panel = ctk.CTkFrame(self.main_frame, fg_color=self.colors["bg_primary"])
        
        # Use the AlertsPanel component
        self.alerts_panel_component = AlertsPanel(panel)
        self.alerts_panel_component.pack(fill="both", expand=True, padx=20, pady=20)
        
        self.panels["alerts"] = panel
    
    # ========================================
    # SETTINGS PANEL
    # ========================================
    
    def create_settings_panel(self):
        """Create enhanced v4.0 settings panel"""
        panel = ctk.CTkFrame(self.main_frame, fg_color=self.colors["bg_primary"])
        
        # Title
        title = ctk.CTkLabel(panel, text="⚙️ Settings", font=("Arial Bold", 28))
        title.pack(pady=20)
        
        # Scrollable frame for all settings
        scroll_frame = ctk.CTkScrollableFrame(panel, fg_color=self.colors["bg_secondary"])
        scroll_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        # ========================================
        # SECTION 1: General Settings
        # ========================================
        general_label = ctk.CTkLabel(scroll_frame, text="🔧 General Settings", font=("Arial Bold", 18))
        general_label.pack(anchor="w", padx=20, pady=(10, 5))
        
        general_frame = ctk.CTkFrame(scroll_frame, fg_color=self.colors["bg_primary"])
        general_frame.pack(fill="x", padx=20, pady=5)
        
        # Headless mode
        headless_frame = ctk.CTkFrame(general_frame, fg_color="transparent")
        headless_frame.pack(fill="x", padx=15, pady=8)
        
        ctk.CTkLabel(headless_frame, text="Headless Mode:", font=("Arial Bold", 14)).pack(side="left")
        self.headless_switch = ctk.CTkSwitch(headless_frame, text="Run browser in background")
        self.headless_switch.pack(side="left", padx=20)
        
        # Discord webhook
        webhook_frame = ctk.CTkFrame(general_frame, fg_color="transparent")
        webhook_frame.pack(fill="x", padx=15, pady=8)
        
        ctk.CTkLabel(webhook_frame, text="Discord Webhook URL:", font=("Arial Bold", 14)).pack(anchor="w")
        self.webhook_entry = ctk.CTkEntry(webhook_frame, placeholder_text="https://discord.com/api/webhooks/...")
        self.webhook_entry.pack(fill="x", pady=5)
        
        # Price tolerance
        tolerance_frame = ctk.CTkFrame(general_frame, fg_color="transparent")
        tolerance_frame.pack(fill="x", padx=15, pady=8)
        
        ctk.CTkLabel(tolerance_frame, text="Price Tolerance (%):", font=("Arial Bold", 14)).pack(anchor="w")
        self.tolerance_entry = ctk.CTkEntry(tolerance_frame, width=200, placeholder_text="10")
        self.tolerance_entry.pack(anchor="w", pady=5)
        self.tolerance_entry.insert(0, "10")
        
        # Retry limit
        retry_frame = ctk.CTkFrame(general_frame, fg_color="transparent")
        retry_frame.pack(fill="x", padx=15, pady=8)
        
        ctk.CTkLabel(retry_frame, text="Max Retries:", font=("Arial Bold", 14)).pack(anchor="w")
        self.retry_entry = ctk.CTkEntry(retry_frame, width=200, placeholder_text="3")
        self.retry_entry.pack(anchor="w", pady=5)
        self.retry_entry.insert(0, "3")
        
        # Monitor delay
        delay_frame = ctk.CTkFrame(general_frame, fg_color="transparent")
        delay_frame.pack(fill="x", padx=15, pady=8)
        
        ctk.CTkLabel(delay_frame, text="Monitor Check Interval (seconds):", font=("Arial Bold", 14)).pack(anchor="w")
        self.delay_entry = ctk.CTkEntry(delay_frame, width=200, placeholder_text="5")
        self.delay_entry.pack(anchor="w", pady=5)
        self.delay_entry.insert(0, "5")
        
        # ========================================
        # SECTION 2: v4.0 Monitor Features
        # ========================================
        v4_label = ctk.CTkLabel(scroll_frame, text="✨ v4.0 Monitor Features", font=("Arial Bold", 18))
        v4_label.pack(anchor="w", padx=20, pady=(20, 5))
        
        v4_frame = ctk.CTkFrame(scroll_frame, fg_color=self.colors["bg_primary"])
        v4_frame.pack(fill="x", padx=20, pady=5)
        
        # Default zip code
        zip_frame = ctk.CTkFrame(v4_frame, fg_color="transparent")
        zip_frame.pack(fill="x", padx=15, pady=8)
        
        ctk.CTkLabel(zip_frame, text="Default Zip Code:", font=("Arial Bold", 14)).pack(anchor="w")
        self.zip_entry = ctk.CTkEntry(zip_frame, width=200, placeholder_text="47401")
        self.zip_entry.pack(anchor="w", pady=5)
        ctk.CTkLabel(zip_frame, text="💡 Used for local store inventory checks", 
                    font=("Arial", 10), text_color=self.colors["text_secondary"]).pack(anchor="w")
        
        # Feature toggles
        toggles_info = ctk.CTkLabel(v4_frame, text="Enable/Disable Features:", 
                                    font=("Arial Bold", 14))
        toggles_info.pack(anchor="w", padx=15, pady=(15, 5))
        
        toggles_frame = ctk.CTkFrame(v4_frame, fg_color="transparent")
        toggles_frame.pack(fill="x", padx=15, pady=5)
        
        # Show images
        self.show_images_switch = ctk.CTkSwitch(toggles_frame, text="📷 Show Product Images")
        self.show_images_switch.pack(anchor="w", pady=5)
        
        # Show scalper detection
        self.show_scalper_switch = ctk.CTkSwitch(toggles_frame, text="💰 Scalper Price Detection")
        self.show_scalper_switch.pack(anchor="w", pady=5)
        
        # Show local stores
        self.show_stores_switch = ctk.CTkSwitch(toggles_frame, text="🏪 Local Store Inventory")
        self.show_stores_switch.pack(anchor="w", pady=5)
        
        # Show ratings
        self.show_ratings_switch = ctk.CTkSwitch(toggles_frame, text="⭐ Product Ratings")
        self.show_ratings_switch.pack(anchor="w", pady=5)
        
        # Show promotions
        self.show_promotions_switch = ctk.CTkSwitch(toggles_frame, text="🎁 Active Promotions")
        self.show_promotions_switch.pack(anchor="w", pady=5)
        
        # Enable quick links
        self.quick_links_switch = ctk.CTkSwitch(toggles_frame, text="🔗 Quick Product Links")
        self.quick_links_switch.pack(anchor="w", pady=5)
        
        # Enable image caching
        self.image_cache_switch = ctk.CTkSwitch(toggles_frame, text="💾 Image Caching")
        self.image_cache_switch.pack(anchor="w", pady=5)
        
        # ========================================
        # SECTION 3: Browser & Login
        # ========================================
        browser_label = ctk.CTkLabel(scroll_frame, text="🌐 Browser & Login", font=("Arial Bold", 18))
        browser_label.pack(anchor="w", padx=20, pady=(20, 5))
        
        browser_frame = ctk.CTkFrame(scroll_frame, fg_color=self.colors["bg_primary"])
        browser_frame.pack(fill="x", padx=20, pady=5)
        
        # Login browser button
        login_frame = ctk.CTkFrame(browser_frame, fg_color="transparent")
        login_frame.pack(fill="x", padx=15, pady=15)
        
        ctk.CTkLabel(login_frame, text="🔑 Manual Login Setup:", font=("Arial Bold", 14)).pack(anchor="w")
        ctk.CTkLabel(login_frame, 
                    text="Open a browser window to manually login to Target and save your session.\n"
                         "This prevents checkout failures and lets you login once, then never again!",
                    font=("Arial", 11), 
                    text_color=self.colors["text_secondary"]).pack(anchor="w", pady=(5, 10))
        
        # Profile selection for login
        login_profile_frame = ctk.CTkFrame(login_frame, fg_color="transparent")
        login_profile_frame.pack(fill="x", pady=5)
        
        ctk.CTkLabel(login_profile_frame, text="Select Profile:", font=("Arial", 12)).pack(side="left", padx=(0, 10))
        self.login_profile_var = ctk.StringVar(value="default")
        self.login_profile_dropdown = ctk.CTkComboBox(
            login_profile_frame, 
            variable=self.login_profile_var,
            values=["default"],  # Will be populated
            width=200
        )
        self.login_profile_dropdown.pack(side="left", padx=5)
        
        # Refresh profiles button
        refresh_profiles_btn = ctk.CTkButton(
            login_profile_frame,
            text="🔄",
            width=40,
            command=self.refresh_login_profiles
        )
        refresh_profiles_btn.pack(side="left", padx=5)
        
        # Open login browser button
        open_login_btn = ctk.CTkButton(
            login_frame,
            text="🌐 Open Login Browser",
            font=("Arial Bold", 14),
            fg_color=self.colors["accent"],
            hover_color=self.colors["accent_hover"],
            height=40,
            command=self.open_login_browser
        )
        open_login_btn.pack(fill="x", pady=10)
        
        ctk.CTkLabel(login_frame, 
                    text="💡 Tip: Browser will open to Target homepage. Login normally, then close the window.\n"
                         "Your login will be saved forever in that profile!",
                    font=("Arial", 10), 
                    text_color=self.colors["info"]).pack(anchor="w")
        
        # ========================================
        # SECTION 4: API Learning (Warmup)
        # ========================================
        api_label = ctk.CTkLabel(scroll_frame, text="⚡ Smart API Learning (Pre-Drop Warmup)", font=("Arial Bold", 18))
        api_label.pack(anchor="w", padx=20, pady=(20, 5))
        
        api_frame = ctk.CTkFrame(scroll_frame, fg_color=self.colors["bg_primary"])
        api_frame.pack(fill="x", padx=20, pady=5)
        
        # API learning info
        api_info_frame = ctk.CTkFrame(api_frame, fg_color="transparent")
        api_info_frame.pack(fill="x", padx=15, pady=15)
        
        ctk.CTkLabel(api_info_frame, 
                    text="Learn Target's API pattern BEFORE drops for 10-100x faster stock checks!",
                    font=("Arial Bold", 14)).pack(anchor="w")
        ctk.CTkLabel(api_info_frame, 
                    text="Run this once before drop day as a warmup. It takes 10 seconds and makes drops instant.",
                    font=("Arial", 11), 
                    text_color=self.colors["text_secondary"]).pack(anchor="w", pady=(5, 10))
        
        # Product URL for learning
        api_url_frame = ctk.CTkFrame(api_info_frame, fg_color="transparent")
        api_url_frame.pack(fill="x", pady=5)
        
        ctk.CTkLabel(api_url_frame, text="Product URL:", font=("Arial", 12)).pack(anchor="w")
        self.api_learn_url = ctk.CTkEntry(
            api_url_frame, 
            placeholder_text="https://www.target.com/p/.../A-12345",
            height=35
        )
        self.api_learn_url.pack(fill="x", pady=5)
        
        # Learn API button
        learn_api_btn = ctk.CTkButton(
            api_info_frame,
            text="⚡ Learn API Pattern (Warmup)",
            font=("Arial Bold", 14),
            fg_color=self.colors["success"],
            hover_color="#059669",
            height=40,
            command=self.learn_api_pattern
        )
        learn_api_btn.pack(fill="x", pady=10)
        
        ctk.CTkLabel(api_info_frame, 
                    text="✅ After learning, all tasks will use instant API checks instead of slow browser checks!",
                    font=("Arial", 10), 
                    text_color=self.colors["success"]).pack(anchor="w")
        
        # ========================================
        # SECTION 5: Save Button (moved to bottom)
        # ========================================
        self.image_cache_switch = ctk.CTkSwitch(toggles_frame, text="💾 Enable Image Caching")
        self.image_cache_switch.pack(anchor="w", pady=5)
        
        # ========================================
        # SECTION 3: Captcha Settings (Phase 4B)
        # ========================================
        captcha_label = ctk.CTkLabel(scroll_frame, text="🔐 Captcha Solver Settings", font=("Arial Bold", 18))
        captcha_label.pack(anchor="w", padx=20, pady=(20, 5))
        
        captcha_frame = ctk.CTkFrame(scroll_frame, fg_color=self.colors["bg_primary"])
        captcha_frame.pack(fill="x", padx=20, pady=5)
        
        ctk.CTkLabel(
            captcha_frame, 
            text="Manual solving is primary method. API keys are backup only.",
            font=("Arial", 11),
            text_color=self.colors["text_secondary"]
        ).pack(anchor="w", padx=15, pady=(10, 5))
        
        # 2Captcha API key
        captcha_2captcha_frame = ctk.CTkFrame(captcha_frame, fg_color="transparent")
        captcha_2captcha_frame.pack(fill="x", padx=15, pady=8)
        
        ctk.CTkLabel(captcha_2captcha_frame, text="2Captcha API Key:", font=("Arial Bold", 14)).pack(anchor="w")
        self.twocaptcha_entry = ctk.CTkEntry(captcha_2captcha_frame, placeholder_text="Optional - for automatic solving backup")
        self.twocaptcha_entry.pack(fill="x", pady=5)
        
        # Anti-Captcha API key
        captcha_anticaptcha_frame = ctk.CTkFrame(captcha_frame, fg_color="transparent")
        captcha_anticaptcha_frame.pack(fill="x", padx=15, pady=8)
        
        ctk.CTkLabel(captcha_anticaptcha_frame, text="Anti-Captcha API Key:", font=("Arial Bold", 14)).pack(anchor="w")
        self.anticaptcha_entry = ctk.CTkEntry(captcha_anticaptcha_frame, placeholder_text="Optional - for automatic solving backup")
        self.anticaptcha_entry.pack(fill="x", pady=5)
        
        # ========================================
        # SECTION 4: Phase 1B/1C - Adaptive Learning
        # ========================================
        learning_label = ctk.CTkLabel(scroll_frame, text="🧠 Adaptive Learning (Phase 1B/1C)", font=("Arial Bold", 18))
        learning_label.pack(anchor="w", padx=20, pady=(20, 5))
        
        learning_frame = ctk.CTkFrame(scroll_frame, fg_color=self.colors["bg_primary"])
        learning_frame.pack(fill="x", padx=20, pady=5)
        
        # Phase 1B: Adaptive Speed Learning
        speed_learning_frame = ctk.CTkFrame(learning_frame, fg_color="transparent")
        speed_learning_frame.pack(fill="x", padx=15, pady=8)
        
        ctk.CTkLabel(speed_learning_frame, text="Adaptive Speed Learning:", font=("Arial Bold", 14)).pack(side="left")
        self.speed_learning_switch = ctk.CTkSwitch(speed_learning_frame, text="Learn from successful checkouts")
        self.speed_learning_switch.select()  # Default: ON
        self.speed_learning_switch.pack(side="left", padx=20)
        
        # Phase 1C: API Pattern Learning
        api_learning_frame = ctk.CTkFrame(learning_frame, fg_color="transparent")
        api_learning_frame.pack(fill="x", padx=15, pady=8)
        
        ctk.CTkLabel(api_learning_frame, text="API Pattern Learning:", font=("Arial Bold", 14)).pack(side="left")
        self.api_learning_switch = ctk.CTkSwitch(api_learning_frame, text="Learn API patterns from browser actions")
        self.api_learning_switch.select()  # Default: ON
        self.api_learning_switch.pack(side="left", padx=20)
        
        # ========================================
        # SECTION 5: Phase 3A - Drop Predictions
        # ========================================
        prediction_label = ctk.CTkLabel(scroll_frame, text="🔮 Drop Predictions (Phase 3A)", font=("Arial Bold", 18))
        prediction_label.pack(anchor="w", padx=20, pady=(20, 5))
        
        prediction_frame = ctk.CTkFrame(scroll_frame, fg_color=self.colors["bg_primary"])
        prediction_frame.pack(fill="x", padx=20, pady=5)
        
        # Prediction confidence threshold
        confidence_frame = ctk.CTkFrame(prediction_frame, fg_color="transparent")
        confidence_frame.pack(fill="x", padx=15, pady=8)
        
        ctk.CTkLabel(confidence_frame, text="Prediction Confidence Threshold (%):", font=("Arial Bold", 14)).pack(anchor="w")
        self.confidence_entry = ctk.CTkEntry(confidence_frame, width=200, placeholder_text="70")
        self.confidence_entry.pack(anchor="w", pady=5)
        self.confidence_entry.insert(0, "70")
        ctk.CTkLabel(
            confidence_frame, 
            text="💡 Only show predictions above this confidence level",
            font=("Arial", 10),
            text_color=self.colors["text_secondary"]
        ).pack(anchor="w")
        
        # ========================================
        # SECTION 6: Phase 3B - Account Rotation
        # ========================================
        account_label = ctk.CTkLabel(scroll_frame, text="👥 Account Rotation (Phase 3B)", font=("Arial Bold", 18))
        account_label.pack(anchor="w", padx=20, pady=(20, 5))
        
        account_frame = ctk.CTkFrame(scroll_frame, fg_color=self.colors["bg_primary"])
        account_frame.pack(fill="x", padx=20, pady=5)
        
        # Enable account rotation
        rotation_enable_frame = ctk.CTkFrame(account_frame, fg_color="transparent")
        rotation_enable_frame.pack(fill="x", padx=15, pady=8)
        
        ctk.CTkLabel(rotation_enable_frame, text="Enable Account Rotation:", font=("Arial Bold", 14)).pack(side="left")
        self.account_rotation_switch = ctk.CTkSwitch(rotation_enable_frame, text="Rotate between profiles automatically")
        self.account_rotation_switch.pack(side="left", padx=20)
        
        # Rotation strategy
        strategy_frame = ctk.CTkFrame(account_frame, fg_color="transparent")
        strategy_frame.pack(fill="x", padx=15, pady=8)
        
        ctk.CTkLabel(strategy_frame, text="Rotation Strategy:", font=("Arial Bold", 14)).pack(anchor="w")
        self.rotation_strategy_var = ctk.StringVar(value="Round Robin")
        rotation_menu = ctk.CTkOptionMenu(
            strategy_frame,
            values=["Round Robin", "Random", "Least Recently Used"],
            variable=self.rotation_strategy_var,
            width=250
        )
        rotation_menu.pack(anchor="w", pady=5)
        
        # ========================================
        # SECTION 7: Phase 4B - Proxy Health
        # ========================================
        proxy_label = ctk.CTkLabel(scroll_frame, text="🌐 Proxy Health Monitoring (Phase 4B)", font=("Arial Bold", 18))
        proxy_label.pack(anchor="w", padx=20, pady=(20, 5))
        
        proxy_frame = ctk.CTkFrame(scroll_frame, fg_color=self.colors["bg_primary"])
        proxy_frame.pack(fill="x", padx=20, pady=5)
        
        # Health check interval
        health_interval_frame = ctk.CTkFrame(proxy_frame, fg_color="transparent")
        health_interval_frame.pack(fill="x", padx=15, pady=8)
        
        ctk.CTkLabel(health_interval_frame, text="Health Check Interval (minutes):", font=("Arial Bold", 14)).pack(anchor="w")
        self.proxy_health_entry = ctk.CTkEntry(health_interval_frame, width=200, placeholder_text="5")
        self.proxy_health_entry.pack(anchor="w", pady=5)
        self.proxy_health_entry.insert(0, "5")
        ctk.CTkLabel(
            health_interval_frame,
            text="💡 How often to check proxy health and latency",
            font=("Arial", 10),
            text_color=self.colors["text_secondary"]
        ).pack(anchor="w")
        
        # ========================================
        # SECTION 8: Info & Status
        # ========================================
        info_label = ctk.CTkLabel(scroll_frame, text="ℹ️ System Info", font=("Arial Bold", 18))
        info_label.pack(anchor="w", padx=20, pady=(20, 5))
        
        info_frame = ctk.CTkFrame(scroll_frame, fg_color=self.colors["bg_primary"])
        info_frame.pack(fill="x", padx=20, pady=5)
        
        info_text = ctk.CTkTextbox(info_frame, height=120, fg_color=self.colors["bg_secondary"])
        info_text.pack(fill="x", padx=15, pady=10)
        info_text.insert("1.0", 
            "🎯 Autobot v4.0 - Phase 3 Complete with Discord Integration\n\n"
            "✅ All core features operational\n"
            "✅ Target.com automation ready\n"
            "✅ Product monitoring active\n"
            "✅ Discord notifications enabled\n"
            "✅ Enhanced v4.0 monitor features available\n\n"
            "💡 Tip: Customize your zip code above for accurate local store data!"
        )
        info_text.configure(state="disabled")
        
        # ========================================
        # Save Button
        # ========================================
        save_btn = ctk.CTkButton(
            scroll_frame,
            text="💾 Save All Settings",
            command=self.save_settings,
            fg_color=self.colors["success"],
            hover_color="#059669",
            height=50,
            font=("Arial Bold", 16)
        )
        save_btn.pack(pady=30, padx=20, fill="x")
        
        # Load current settings
        self.load_settings()
        
        self.panels["settings"] = panel
    
    # ========================================
    # HELPER METHODS
    # ========================================
    
    def show_create_task_dialog(self):
        """Show dialog to create new task"""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Create Task")
        dialog.geometry("600x750")  # Increased from 650 to 750
        dialog.configure(fg_color=self.colors["bg_secondary"])
        
        # Center dialog
        dialog.transient(self)
        dialog.grab_set()
        
        # Form
        form = ctk.CTkFrame(dialog, fg_color="transparent")
        form.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Site selection
        ctk.CTkLabel(form, text="Site:", font=("Arial Bold", 14)).pack(anchor="w", pady=(0, 5))
        site_var = ctk.StringVar(value="Target")
        site_menu = ctk.CTkOptionMenu(form, values=["Target", "Walmart", "Pokemon Center"], variable=site_var)
        site_menu.pack(fill="x", pady=(0, 15))
        
        # Product URL
        ctk.CTkLabel(form, text="Product URL:", font=("Arial Bold", 14)).pack(anchor="w", pady=(0, 5))
        url_entry = ctk.CTkEntry(form, placeholder_text="https://...")
        url_entry.pack(fill="x", pady=(0, 15))
        
        # Profile selection (OPTIONAL - can create without profile)
        profiles = self.db.get_all_profiles()
        profile_names = ["(No Profile - Use Persistent Login)"] + [p['name'] for p in profiles] if profiles else ["(No Profile - Use Persistent Login)"]
        
        ctk.CTkLabel(form, text="Profile (optional):", font=("Arial Bold", 14)).pack(anchor="w", pady=(0, 5))
        profile_var = ctk.StringVar(value=profile_names[0])
        profile_menu = ctk.CTkOptionMenu(form, values=profile_names, variable=profile_var)
        profile_menu.pack(fill="x", pady=(0, 5))
        
        # Info label about profiles
        info_label = ctk.CTkLabel(
            form, 
            text="💡 No profile needed if you logged in via Settings → Open Login Browser",
            font=("Arial", 10),
            text_color=self.colors["text_secondary"],
            wraplength=540
        )
        info_label.pack(anchor="w", pady=(0, 15))
        
        # Quantity
        ctk.CTkLabel(form, text="Quantity:", font=("Arial Bold", 14)).pack(anchor="w", pady=(0, 5))
        qty_entry = ctk.CTkEntry(form, placeholder_text="1")
        qty_entry.insert(0, "1")
        qty_entry.pack(fill="x", pady=(0, 15))
        
        # Mode selection
        ctk.CTkLabel(form, text="Mode:", font=("Arial Bold", 14)).pack(anchor="w", pady=(0, 5))
        mode_var = ctk.StringVar(value="Safe")
        mode_menu = ctk.CTkOptionMenu(form, values=["Safe", "Fast", "Headless"], variable=mode_var)
        mode_menu.pack(fill="x", pady=(0, 15))
        
        # Proxy selection
        proxies = self.db.get_all_proxies() if hasattr(self.db, 'get_all_proxies') else []
        proxy_options = ["None"] + [f"{p['host']}:{p['port']}" for p in proxies] if proxies else ["None"]
        
        ctk.CTkLabel(form, text="Proxy (optional):", font=("Arial Bold", 14)).pack(anchor="w", pady=(0, 5))
        proxy_var = ctk.StringVar(value=proxy_options[0])
        proxy_menu = ctk.CTkOptionMenu(form, values=proxy_options, variable=proxy_var)
        proxy_menu.pack(fill="x", pady=(0, 15))
        
        # Learn API checkbox
        learn_api_var = ctk.BooleanVar(value=False)
        learn_api_frame = ctk.CTkFrame(form, fg_color=self.colors["bg_secondary"], corner_radius=10)
        learn_api_frame.pack(fill="x", pady=(0, 5))
        
        learn_api_check = ctk.CTkCheckBox(
            learn_api_frame,
            text="🧠 Learn API Pattern (First Time Site)",
            variable=learn_api_var,
            font=("Arial Bold", 13),
            fg_color=self.colors["accent"],
            hover_color=self.colors["accent_hover"]
        )
        learn_api_check.pack(anchor="w", padx=10, pady=10)
        
        # Info about Learn API
        api_info_label = ctk.CTkLabel(
            learn_api_frame, 
            text="💡 Enable this for first-time products to learn Smart API patterns.\n"
                 "This enables 25-80x faster stock checks! If you're monitoring this\n"
                 "product first, the API will already be learned - keep this OFF.",
            font=("Arial", 10),
            text_color=self.colors["text_secondary"],
            wraplength=540,
            justify="left"
        )
        api_info_label.pack(anchor="w", padx=10, pady=(0, 10))
        
        # Buttons
        btn_frame = ctk.CTkFrame(form, fg_color="transparent")
        btn_frame.pack(fill="x", pady=20)
        
        def create():
            url = url_entry.get().strip()
            if not url:
                messagebox.showerror("Error", "Please enter a product URL")
                return
            
            profile_name = profile_var.get()
            profile = None
            
            # Profile is optional for creation
            if profile_name not in ["(No Profile - Use Persistent Login)", "(No Profile)"]:
                profile = next((p for p in profiles if p['name'] == profile_name), None)
                if not profile:
                    messagebox.showerror("Error", "Profile not found")
                    return
            
            try:
                qty = int(qty_entry.get())
                if qty < 1:
                    raise ValueError()
            except:
                messagebox.showerror("Error", "Please enter a valid quantity")
                return
            
            # Get mode and proxy
            mode = mode_var.get().lower()
            proxy = proxy_var.get() if proxy_var.get() != "None" else None
            learn_api = learn_api_var.get()
            
            # Create task (profile can be None)
            task_id = self.task_manager.create_task(
                site=site_var.get().lower().replace(" ", "_"),
                url=url,
                profile=profile,
                quantity=qty,
                mode=mode,
                proxy=proxy,
                learn_api=learn_api
            )
            
            learn_api_status = " (will learn API)" if learn_api else ""
            profile_status = "with profile" if profile else "without profile (add before starting)"
            self.add_activity_log(f"Created task {task_id} for {site_var.get()} {profile_status}{learn_api_status}")
            dialog.destroy()
            self.refresh_tasks()
        
        create_btn = ctk.CTkButton(
            btn_frame,
            text="✓ Create",
            command=create,
            fg_color=self.colors["success"],
            width=150
        )
        create_btn.pack(side="left", padx=5)
        
        cancel_btn = ctk.CTkButton(
            btn_frame,
            text="✗ Cancel",
            command=dialog.destroy,
            fg_color=self.colors["error"],
            width=150
        )
        cancel_btn.pack(side="left", padx=5)
    
    def show_edit_task_dialog(self, task_id: int):
        """Show dialog to edit task - comprehensive editing of all fields"""
        task = self.task_manager.get_task(task_id)
        if not task:
            messagebox.showerror("Error", "Task not found")
            return
        
        # Can't edit running tasks
        if task.status.value == 'running':
            messagebox.showwarning("Can't Edit", "Cannot edit a running task. Please stop it first.")
            return
        
        dialog = ctk.CTkToplevel(self)
        dialog.title(f"Edit Task {task_id}")
        dialog.geometry("600x750")
        dialog.configure(fg_color=self.colors["bg_secondary"])
        
        # Center dialog
        dialog.transient(self)
        dialog.grab_set()
        
        # Form
        form = ctk.CTkFrame(dialog, fg_color="transparent")
        form.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Task info header
        ctk.CTkLabel(form, text=f"✏️ Editing Task {task_id}", 
                     font=("Arial Bold", 16), 
                     text_color=self.colors["accent"]).pack(anchor="w", pady=(0, 15))
        
        # Site selection
        ctk.CTkLabel(form, text="Site:", font=("Arial Bold", 14)).pack(anchor="w", pady=(0, 5))
        site_var = ctk.StringVar(value=task.site.replace('_', ' ').title())
        site_menu = ctk.CTkOptionMenu(form, values=["Target", "Walmart", "Pokemon Center"], variable=site_var)
        site_menu.pack(fill="x", pady=(0, 15))
        
        # Product URL
        ctk.CTkLabel(form, text="Product URL:", font=("Arial Bold", 14)).pack(anchor="w", pady=(0, 5))
        url_entry = ctk.CTkEntry(form, placeholder_text="https://...")
        url_entry.insert(0, task.product_url)
        url_entry.pack(fill="x", pady=(0, 15))
        
        # Profile selection
        profiles = self.db.get_all_profiles()
        profile_names = ["(No Profile - Use Persistent Login)"] + [p['name'] for p in profiles] if profiles else ["(No Profile - Use Persistent Login)"]
        
        current_profile_name = task.profile_name if task.profile_name else "(No Profile - Use Persistent Login)"
        
        ctk.CTkLabel(form, text="Profile (optional):", font=("Arial Bold", 14)).pack(anchor="w", pady=(0, 5))
        profile_var = ctk.StringVar(value=current_profile_name if current_profile_name in profile_names else profile_names[0])
        profile_menu = ctk.CTkOptionMenu(form, values=profile_names, variable=profile_var)
        profile_menu.pack(fill="x", pady=(0, 5))
        
        # Info label
        info_label = ctk.CTkLabel(
            form, 
            text="💡 No profile needed if you logged in via Settings → Open Login Browser",
            font=("Arial", 10),
            text_color=self.colors["text_secondary"],
            wraplength=540
        )
        info_label.pack(anchor="w", pady=(0, 15))
        
        # Mode selection
        ctk.CTkLabel(form, text="Mode:", font=("Arial Bold", 14)).pack(anchor="w", pady=(0, 5))
        # Convert TaskMode enum to string for display
        current_mode = task.mode.value.title() if hasattr(task.mode, 'value') else str(task.mode).title()
        mode_var = ctk.StringVar(value=current_mode)
        mode_menu = ctk.CTkOptionMenu(form, values=["Safe", "Fast", "Headless"], variable=mode_var)
        mode_menu.pack(fill="x", pady=(0, 15))
        
        # Proxy selection
        proxies = self.db.get_all_proxies() if hasattr(self.db, 'get_all_proxies') else []
        proxy_options = ["None"] + [f"{p['host']}:{p['port']}" for p in proxies] if proxies else ["None"]
        
        current_proxy = task.proxy if task.proxy else "None"
        
        ctk.CTkLabel(form, text="Proxy (optional):", font=("Arial Bold", 14)).pack(anchor="w", pady=(0, 5))
        proxy_var = ctk.StringVar(value=current_proxy if current_proxy in proxy_options else "None")
        proxy_menu = ctk.CTkOptionMenu(form, values=proxy_options, variable=proxy_var)
        proxy_menu.pack(fill="x", pady=(0, 15))
        
        # Buttons
        btn_frame = ctk.CTkFrame(form, fg_color="transparent")
        btn_frame.pack(fill="x", pady=20)
        
        def save():
            url = url_entry.get().strip()
            if not url:
                messagebox.showerror("Error", "Please enter a product URL")
                return
            
            profile_name = profile_var.get()
            profile = None
            
            if profile_name not in ["(No Profile - Use Persistent Login)", "(No Profile)"]:
                profile = next((p for p in profiles if p['name'] == profile_name), None)
                if not profile:
                    messagebox.showerror("Error", "Profile not found")
                    return
            
            # Get mode and proxy
            mode = mode_var.get().lower()
            proxy = proxy_var.get() if proxy_var.get() != "None" else None
            
            # Update task using edit_task method
            success = self.task_manager.edit_task(
                task_id,
                site=site_var.get().lower().replace(" ", "_"),
                url=url,
                profile=profile,
                mode=mode,
                proxy=proxy
            )
            
            if success:
                self.add_activity_log(f"✏️ Task {task_id} updated successfully")
                dialog.destroy()
                self.refresh_tasks()
            else:
                messagebox.showerror("Error", "Failed to edit task. Task may be running.")
        
        save_btn = ctk.CTkButton(
            btn_frame,
            text="💾 Save Changes",
            command=save,
            fg_color=self.colors["success"],
            width=150
        )
        save_btn.pack(side="left", padx=5)
        
        cancel_btn = ctk.CTkButton(
            btn_frame,
            text="✗ Cancel",
            command=dialog.destroy,
            fg_color=self.colors["error"],
            width=150
        )
        cancel_btn.pack(side="left", padx=5)
    
    def show_add_profile_dialog(self):
        """Show dialog to add profile"""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Add Profile")
        dialog.geometry("600x700")
        dialog.configure(fg_color=self.colors["bg_secondary"])
        
        dialog.transient(self)
        dialog.grab_set()
        
        form = ctk.CTkScrollableFrame(dialog, fg_color="transparent")
        form.pack(fill="both", expand=True, padx=20, pady=20)
        
        entries = {}
        
        # Shipping info
        ctk.CTkLabel(form, text="SHIPPING INFO", font=("Arial Bold", 16)).pack(anchor="w", pady=(0, 10))
        
        fields = [
            ("name", "Profile Name"),
            ("first_name", "First Name"),
            ("last_name", "Last Name"),
            ("email", "Email"),
            ("phone", "Phone"),
            ("address", "Address"),
            ("address2", "Address Line 2 (optional)"),
            ("city", "City"),
            ("state", "State"),
            ("zip_code", "ZIP Code"),
        ]
        
        for key, label in fields:
            ctk.CTkLabel(form, text=f"{label}:", font=("Arial", 12)).pack(anchor="w", pady=(5, 2))
            entry = ctk.CTkEntry(form)
            entry.pack(fill="x", pady=(0, 10))
            entries[key] = entry
        
        # Payment info
        ctk.CTkLabel(form, text="PAYMENT INFO", font=("Arial Bold", 16)).pack(anchor="w", pady=(20, 10))
        
        payment_fields = [
            ("card_number", "Card Number"),
            ("card_exp", "Expiration (MM/YY)"),
            ("card_cvv", "CVV"),
        ]
        
        for key, label in payment_fields:
            ctk.CTkLabel(form, text=f"{label}:", font=("Arial", 12)).pack(anchor="w", pady=(5, 2))
            entry = ctk.CTkEntry(form, show="*" if "cvv" in key or "number" in key else "")
            entry.pack(fill="x", pady=(0, 10))
            entries[key] = entry
        
        def save():
            data = {k: v.get().strip() for k, v in entries.items()}
            
            if not data['name']:
                messagebox.showerror("Error", "Please enter a profile name")
                return
            
            if not all([data['first_name'], data['last_name'], data['email']]):
                messagebox.showerror("Error", "Please fill in all required fields")
                return
            
            self.db.add_profile(data)
            self.add_activity_log(f"Added profile: {data['name']}")
            dialog.destroy()
            self.refresh_profiles()
        
        btn_frame = ctk.CTkFrame(form, fg_color="transparent")
        btn_frame.pack(fill="x", pady=20)
        
        save_btn = ctk.CTkButton(btn_frame, text="💾 Save", command=save, fg_color=self.colors["success"], width=150)
        save_btn.pack(side="left", padx=5)
        
        cancel_btn = ctk.CTkButton(btn_frame, text="✗ Cancel", command=dialog.destroy, fg_color=self.colors["error"], width=150)
        cancel_btn.pack(side="left", padx=5)
    
    def show_add_proxy_dialog(self):
        """Show dialog to add proxy"""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Add Proxy")
        dialog.geometry("400x200")
        dialog.configure(fg_color=self.colors["bg_secondary"])
        
        dialog.transient(self)
        dialog.grab_set()
        
        form = ctk.CTkFrame(dialog, fg_color="transparent")
        form.pack(fill="both", expand=True, padx=20, pady=20)
        
        ctk.CTkLabel(form, text="Proxy (host:port:user:pass):", font=("Arial Bold", 14)).pack(anchor="w", pady=5)
        proxy_entry = ctk.CTkEntry(form, placeholder_text="192.168.1.1:8080:user:pass")
        proxy_entry.pack(fill="x", pady=10)
        
        def save():
            proxy = proxy_entry.get().strip()
            if not proxy:
                messagebox.showerror("Error", "Please enter a proxy")
                return
            
            self.db.add_proxy(proxy)
            self.add_activity_log(f"Added proxy: {proxy}")
            dialog.destroy()
            self.refresh_proxies()
        
        btn_frame = ctk.CTkFrame(form, fg_color="transparent")
        btn_frame.pack(fill="x", pady=20)
        
        save_btn = ctk.CTkButton(btn_frame, text="💾 Add", command=save, fg_color=self.colors["success"])
        save_btn.pack(side="left", padx=5)
        
        cancel_btn = ctk.CTkButton(btn_frame, text="✗ Cancel", command=dialog.destroy, fg_color=self.colors["error"])
        cancel_btn.pack(side="left", padx=5)
    
    def import_proxies(self):
        """Import proxies from file"""
        filename = filedialog.askopenfilename(
            title="Select proxy file",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                with open(filename, 'r') as f:
                    proxies = [line.strip() for line in f if line.strip()]
                
                for proxy in proxies:
                    self.db.add_proxy(proxy)
                
                self.add_activity_log(f"Imported {len(proxies)} proxies")
                self.refresh_proxies()
                messagebox.showinfo("Success", f"Imported {len(proxies)} proxies")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to import proxies: {e}")
    
    def delete_all_proxies(self):
        """Delete all proxies"""
        if messagebox.askyesno("Confirm", "Delete all proxies?"):
            # TODO: Implement delete all in db_manager
            self.add_activity_log("Deleted all proxies")
            self.refresh_proxies()
    
    def start_selected_tasks(self):
        """Start selected tasks (no profile required - uses persistent browser session)"""
        started = 0
        
        for task_id, widget_data in self.task_widgets.items():
            if widget_data['checkbox'].get():
                # Get task details
                task = self.task_manager.get_task(task_id)
                if not task:
                    continue
                
                # Start task (profile optional - will use persistent browser if no profile)
                self.task_manager.start_task(task_id)
                started += 1
        
        # Report results
        if started > 0:
            self.add_activity_log(f"Started {started} task(s)")
            self.after(100, self.refresh_tasks)
        else:
            self.add_activity_log("No tasks selected")
    
    def stop_selected_tasks(self):
        """Stop selected tasks"""
        stopped = 0
        for task_id, widget_data in self.task_widgets.items():
            if widget_data['checkbox'].get():
                self.task_manager.stop_task(task_id)
                stopped += 1
        if stopped > 0:
            self.add_activity_log(f"Stopped {stopped} task(s)")
            self.after(100, self.refresh_tasks)
        else:
            self.add_activity_log("No tasks selected")
    
    def delete_selected_tasks(self):
        """Delete selected tasks"""
        deleted = 0
        for task_id, widget_data in list(self.task_widgets.items()):
            if widget_data['checkbox'].get():
                self.task_manager.delete_task(task_id)
                deleted += 1
        if deleted > 0:
            self.add_activity_log(f"Deleted {deleted} task(s)")
            self.after(100, self.refresh_tasks)
        else:
            self.add_activity_log("No tasks selected")
    
    def edit_selected_task(self):
        """Edit selected task (only one at a time)"""
        selected_tasks = [
            task_id for task_id, widget_data in self.task_widgets.items()
            if widget_data['checkbox'].get()
        ]
        
        if len(selected_tasks) == 0:
            self.add_activity_log("No task selected to edit")
            messagebox.showinfo("No Selection", "Please select one task to edit")
            return
        
        if len(selected_tasks) > 1:
            self.add_activity_log("Multiple tasks selected - can only edit one at a time")
            messagebox.showinfo("Multiple Selection", "Please select only one task to edit")
            return
        
        # Show edit dialog for the selected task
        self.show_edit_task_dialog(selected_tasks[0])
    
    def start_single_task(self, task_id: int):
        """Start a single task (requires profile)"""
        # Get task details
        task = self.task_manager.get_task(task_id)
        if not task:
            messagebox.showerror("Error", "Task not found")
            return
        
        # Check if task has a profile - Task is an object, not a dict
        if not task.profile_name or task.profile_name == '':
            # No profile - prompt user
            result = messagebox.askyesno(
                "Profile Required",
                "This task needs a profile to start.\n\n"
                "Would you like to edit the task and add a profile?",
                icon='warning'
            )
            if result:
                self.show_edit_task_dialog(task_id)
            return
        
        # Profile exists, start task
        self.task_manager.start_task(task_id)
        self.add_activity_log(f"Started task {task_id}")
        self.after(100, self.refresh_tasks)
    
    def stop_single_task(self, task_id: int):
        """Stop a single task"""
        self.task_manager.stop_task(task_id)
        self.add_activity_log(f"Stopped task {task_id}")
        self.after(100, self.refresh_tasks)
    
    def delete_single_task(self, task_id: int):
        """Delete a single task"""
        self.task_manager.delete_task(task_id)
        self.add_activity_log(f"Deleted task {task_id}")
        self.after(100, self.refresh_tasks)
    
    def open_captcha_harvester(self, window_number: int):
        """Open captcha harvester window"""
        self.add_activity_log(f"Opening captcha harvester {window_number}...")
        # TODO: Implement captcha harvester launch
    
    def refresh_profiles(self):
        """Refresh profiles list"""
        # Clear existing widgets
        for widget in self.profiles_scroll.winfo_children():
            widget.destroy()
        
        profiles = self.db.get_all_profiles()
        
        if not profiles:
            ctk.CTkLabel(
                self.profiles_scroll,
                text="No profiles yet. Click 'Add Profile' to create one.",
                font=("Arial", 14),
                text_color=self.colors["text_secondary"]
            ).pack(pady=50)
            return
        
        for profile in profiles:
            card = ctk.CTkFrame(self.profiles_scroll, fg_color=self.colors["bg_tertiary"])
            card.pack(fill="x", pady=5, padx=5)
            
            # Profile info
            info_frame = ctk.CTkFrame(card, fg_color="transparent")
            info_frame.pack(side="left", fill="x", expand=True, padx=15, pady=15)
            
            name_label = ctk.CTkLabel(info_frame, text=profile['name'], font=("Arial Bold", 16))
            name_label.pack(anchor="w")
            
            details = f"{profile['first_name']} {profile['last_name']} | {profile['email']}"
            details_label = ctk.CTkLabel(info_frame, text=details, font=("Arial", 12), text_color=self.colors["text_secondary"])
            details_label.pack(anchor="w")
            
            # Delete button
            delete_btn = ctk.CTkButton(
                card,
                text="🗑️",
                command=lambda p=profile: self.delete_profile(p['id']),
                fg_color=self.colors["error"],
                width=50
            )
            delete_btn.pack(side="right", padx=10)
    
    def delete_profile(self, profile_id: int):
        """Delete a profile"""
        if messagebox.askyesno("Confirm", "Delete this profile?"):
            # TODO: Implement in db_manager
            self.add_activity_log(f"Deleted profile {profile_id}")
            self.refresh_profiles()
    
    def refresh_proxies(self):
        """Refresh proxies list"""
        for widget in self.proxies_scroll.winfo_children():
            widget.destroy()
        
        proxies = self.db.get_all_proxies()
        
        if not proxies:
            ctk.CTkLabel(
                self.proxies_scroll,
                text="No proxies yet. Click 'Add Proxy' to add one.",
                font=("Arial", 14),
                text_color=self.colors["text_secondary"]
            ).pack(pady=50)
            return
        
        for proxy in proxies:
            card = ctk.CTkFrame(self.proxies_scroll, fg_color=self.colors["bg_tertiary"])
            card.pack(fill="x", pady=5, padx=5)
            
            # Proxy info
            info_frame = ctk.CTkFrame(card, fg_color="transparent")
            info_frame.pack(side="left", fill="x", expand=True, padx=15, pady=10)
            
            proxy_label = ctk.CTkLabel(info_frame, text=proxy['proxy'], font=("Arial", 14))
            proxy_label.pack(anchor="w")
            
            stats = f"✓ {proxy.get('success', 0)} | ✗ {proxy.get('fail', 0)}"
            stats_label = ctk.CTkLabel(info_frame, text=stats, font=("Arial", 12), text_color=self.colors["text_secondary"])
            stats_label.pack(anchor="w")
            
            # Delete button
            delete_btn = ctk.CTkButton(
                card,
                text="🗑️",
                command=lambda p=proxy: self.delete_proxy(p['id']),
                fg_color=self.colors["error"],
                width=50
            )
            delete_btn.pack(side="right", padx=10)
    
    def delete_proxy(self, proxy_id: int):
        """Delete a proxy"""
        # TODO: Implement in db_manager
        self.add_activity_log(f"Deleted proxy {proxy_id}")
        self.refresh_proxies()
    
    def refresh_tasks(self):
        """Refresh tasks list"""
        for widget in self.tasks_scroll.winfo_children():
            widget.destroy()
        
        tasks = self.task_manager.get_all_tasks()
        
        if not tasks:
            ctk.CTkLabel(
                self.tasks_scroll,
                text="No tasks yet. Click 'Create Task' to add one.",
                font=("Arial", 14),
                text_color=self.colors["text_secondary"]
            ).pack(pady=50)
            return
        
        for task in tasks:
            self.create_task_widget(task)
    
    def create_task_widget(self, task: Dict):
        """Create a task widget"""
        card = ctk.CTkFrame(self.tasks_scroll, fg_color=self.colors["bg_tertiary"], height=80)
        card.pack(fill="x", pady=5, padx=5)
        card.pack_propagate(False)
        
        # Checkbox for selection
        checkbox = ctk.CTkCheckBox(
            card,
            text="",
            width=20,
            checkbox_width=20,
            checkbox_height=20
        )
        checkbox.pack(side="left", padx=(10, 5))
        
        # Task info
        info_frame = ctk.CTkFrame(card, fg_color="transparent")
        info_frame.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        
        # Status color
        status_colors = {
            "IDLE": self.colors["text_secondary"],
            "RUNNING": self.colors["info"],
            "SUCCESS": self.colors["success"],
            "FAILED": self.colors["error"],
            "WAITING_CAPTCHA": self.colors["warning"]
        }
        
        status_color = status_colors.get(task['status'], self.colors["text_secondary"])
        
        title = f"Task {task['id']} | {task['site'].upper()} | {task['status']}"
        title_label = ctk.CTkLabel(info_frame, text=title, font=("Arial Bold", 13), text_color=status_color)
        title_label.pack(anchor="w")
        
        # URL (truncated)
        url_display = task['url'][:70] + "..." if len(task['url']) > 70 else task['url']
        url_label = ctk.CTkLabel(info_frame, text=url_display, font=("Arial", 10), text_color=self.colors["text_secondary"])
        url_label.pack(anchor="w", pady=(2, 0))
        
        # Buttons frame
        buttons_frame = ctk.CTkFrame(card, fg_color="transparent")
        buttons_frame.pack(side="right", padx=10)
        
        # Action buttons based on status
        if task['status'] in ['IDLE', 'FAILED', 'SUCCESS']:
            # Start button
            start_btn = ctk.CTkButton(
                buttons_frame,
                text="▶️ Start",
                command=lambda tid=task['id']: self.start_single_task(tid),
                fg_color=self.colors["success"],
                hover_color="#059669",
                width=80,
                height=30,
                font=("Arial", 11)
            )
            start_btn.pack(side="left", padx=2)
        elif task['status'] == 'RUNNING':
            # Stop button
            stop_btn = ctk.CTkButton(
                buttons_frame,
                text="⏸️ Stop",
                command=lambda tid=task['id']: self.stop_single_task(tid),
                fg_color=self.colors["error"],
                hover_color="#dc2626",
                width=80,
                height=30,
                font=("Arial", 11)
            )
            stop_btn.pack(side="left", padx=2)
        
        # Delete button (always available)
        delete_btn = ctk.CTkButton(
            buttons_frame,
            text="🗑️",
            command=lambda tid=task['id']: self.delete_single_task(tid),
            fg_color=self.colors["bg_secondary"],
            hover_color=self.colors["bg_primary"],
            width=40,
            height=30,
            font=("Arial", 11)
        )
        delete_btn.pack(side="left", padx=2)
        
        # Store widget references
        self.task_widgets[task['id']] = {
            'card': card,
            'checkbox': checkbox,
            'title_label': title_label,
            'status': task['status']
        }
    
    def load_settings(self):
        """Load settings from database including v4.0 and Phase settings"""
        settings = self.db.get_settings()
        if settings:
            # Original settings
            if settings.get('headless'):
                self.headless_switch.select()
                # Apply to task manager
                self.task_manager.headless_mode = True
            else:
                # Default to False (browser visible)
                self.task_manager.headless_mode = False
            if settings.get('webhook_url'):
                self.webhook_entry.delete(0, 'end')
                self.webhook_entry.insert(0, settings['webhook_url'])
            if settings.get('price_tolerance'):
                self.tolerance_entry.delete(0, 'end')
                self.tolerance_entry.insert(0, str(settings['price_tolerance']))
            if settings.get('max_retries'):
                self.retry_entry.delete(0, 'end')
                self.retry_entry.insert(0, str(settings['max_retries']))
            if settings.get('monitor_delay'):
                self.delay_entry.delete(0, 'end')
                self.delay_entry.insert(0, str(settings['monitor_delay']))
            
            # v4.0 settings
            if settings.get('default_zip_code'):
                self.zip_entry.delete(0, 'end')
                self.zip_entry.insert(0, str(settings['default_zip_code']))
            
            # v4.0 feature toggles (default to enabled if not set)
            if settings.get('show_images', '1') == '1':
                self.show_images_switch.select()
            if settings.get('show_scalper_detection', '1') == '1':
                self.show_scalper_switch.select()
            if settings.get('show_local_stores', '1') == '1':
                self.show_stores_switch.select()
            if settings.get('show_ratings', '1') == '1':
                self.show_ratings_switch.select()
            if settings.get('show_promotions', '1') == '1':
                self.show_promotions_switch.select()
            if settings.get('enable_quick_links', '1') == '1':
                self.quick_links_switch.select()
            if settings.get('image_cache_enabled', '1') == '1':
                self.image_cache_switch.select()
            
            # Phase 4B: Captcha API settings
            if settings.get('twocaptcha_api_key'):
                self.twocaptcha_entry.delete(0, 'end')
                self.twocaptcha_entry.insert(0, settings['twocaptcha_api_key'])
            if settings.get('anticaptcha_api_key'):
                self.anticaptcha_entry.delete(0, 'end')
                self.anticaptcha_entry.insert(0, settings['anticaptcha_api_key'])
            
            # Phase 1B/1C: Adaptive Learning (default to enabled)
            if settings.get('enable_speed_learning', '1') == '1':
                self.speed_learning_switch.select()
            if settings.get('enable_api_learning', '1') == '1':
                self.api_learning_switch.select()
            
            # Phase 3A: Predictions
            if settings.get('prediction_confidence_threshold'):
                self.confidence_entry.delete(0, 'end')
                self.confidence_entry.insert(0, str(settings['prediction_confidence_threshold']))
            
            # Phase 3B: Account Rotation
            if settings.get('enable_account_rotation', '0') == '1':
                self.account_rotation_switch.select()
            if settings.get('rotation_strategy'):
                self.rotation_strategy_var.set(settings['rotation_strategy'])
            
            # Phase 4B: Proxy Health
            if settings.get('proxy_health_interval'):
                self.proxy_health_entry.delete(0, 'end')
                self.proxy_health_entry.insert(0, str(settings['proxy_health_interval']))
    
    def save_settings(self):
        """Save all settings to database"""
        settings = {
            'webhook_url': self.webhook_entry.get(),
            'price_tolerance': float(self.tolerance_entry.get() or 0),
            'max_retries': int(self.retry_entry.get() or 3),
            'monitor_delay': int(self.delay_entry.get() or 5),
            'default_zip': self.zip_entry.get() or '47401'
        }
        
        self.db.save_settings(settings)
        self.add_activity_log("Settings saved successfully")
        messagebox.showinfo("Success", "Settings saved!")
    
    def refresh_login_profiles(self):
        """Refresh the profile dropdown with current profiles"""
        profiles = self.db.get_all_profiles()
        if profiles:
            profile_names = [p['name'] for p in profiles]
            self.login_profile_dropdown.configure(values=profile_names)
            if profile_names:
                self.login_profile_var.set(profile_names[0])
        else:
            self.login_profile_dropdown.configure(values=["default"])
            self.login_profile_var.set("default")
    
    def open_login_browser(self):
        """Open a browser window for manual login"""
        profile_name = self.login_profile_var.get()
        
        if not profile_name:
            messagebox.showwarning("No Profile", "Please select a profile first")
            return
        
        def run_login_browser():
            try:
                self.add_activity_log(f"Opening login browser for profile: {profile_name}")
                
                # Import Target site
                from sites.target import TargetSite
                
                # Create site with profile
                site = TargetSite(headless=False, profile_name=profile_name)
                
                # Start browser in LOGIN ONLY mode
                site.start_browser(login_only=True)
                
                # Show message
                messagebox.showinfo(
                    "Login Browser",
                    f"Browser opened for profile: {profile_name}\n\n"
                    "1. Login to Target normally\n"
                    "2. Complete any 2FA if needed\n"
                    "3. Close this message and the browser when done\n\n"
                    "Your login will be saved permanently!"
                )
                
                # Wait for user to close browser
                print("[Login Browser] Waiting for user to close browser...")
                input("Press Enter when you're done logging in...")
                
                # Close browser
                site.stop_browser()
                
                self.add_activity_log(f"✅ Login session saved for {profile_name}")
                messagebox.showinfo("Success", f"Login saved for {profile_name}!\n\nYou never need to login again.")
                
            except Exception as e:
                self.add_activity_log(f"❌ Login browser error: {e}")
                messagebox.showerror("Error", f"Failed to open login browser:\n{e}")
        
        # Run in thread so UI doesn't freeze
        thread = threading.Thread(target=run_login_browser, daemon=True)
        thread.start()
    
    def learn_api_pattern(self):
        """Learn API pattern using async learner"""
        product_url = self.api_learn_url.get().strip()
        
        if not product_url:
            messagebox.showwarning("No URL", "Please enter a product URL")
            return
        
        if 'target.com' not in product_url:
            messagebox.showwarning("Unsupported Site", "Currently only Target is supported for API learning")
            return
        
        profile_name = self.login_profile_var.get() or "default"
        
        def run_api_learning():
            try:
                self.add_activity_log(f"⚡ Learning API pattern from: {product_url[:50]}...")
                
                # Import async learner
                import asyncio
                from core.async_api_learner import learn_api_for_site
                
                # Create new event loop for this thread
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                # Learn pattern (async)
                pattern = loop.run_until_complete(
                    learn_api_for_site('target', product_url, profile_name, self.db)
                )
                
                loop.close()
                
                if pattern:
                    self.add_activity_log(f"✅ API pattern learned successfully!")
                    self.add_activity_log(f"   Endpoint: {pattern.get('endpoint', 'N/A')[:50]}...")
                    messagebox.showinfo(
                        "Success", 
                        "API pattern learned!\n\n"
                        "All tasks will now use instant API checks.\n"
                        "This gives you 10-100x faster stock monitoring!"
                    )
                else:
                    self.add_activity_log(f"⚠️  Could not learn API pattern")
                    messagebox.showwarning(
                        "Learning Failed",
                        "Could not detect API pattern.\n\n"
                        "Bot will still work using browser-based checks."
                    )
                
            except Exception as e:
                self.add_activity_log(f"❌ API learning error: {e}")
                messagebox.showerror("Error", f"Failed to learn API:\n{e}")
        
        # Run in thread
        thread = threading.Thread(target=run_api_learning, daemon=True)
        thread.start()

        """Save all settings to database including v4.0 and Phase settings"""
        try:
            settings = {
                # Original settings
                'headless': self.headless_switch.get() == 1,
                'webhook_url': self.webhook_entry.get().strip(),
                'price_tolerance': float(self.tolerance_entry.get()),
                'max_retries': int(self.retry_entry.get()),
                'monitor_delay': int(self.delay_entry.get()),
                
                # v4.0 settings
                'default_zip_code': self.zip_entry.get().strip(),
                'show_images': '1' if self.show_images_switch.get() == 1 else '0',
                'show_scalper_detection': '1' if self.show_scalper_switch.get() == 1 else '0',
                'show_local_stores': '1' if self.show_stores_switch.get() == 1 else '0',
                'show_ratings': '1' if self.show_ratings_switch.get() == 1 else '0',
                'show_promotions': '1' if self.show_promotions_switch.get() == 1 else '0',
                'enable_quick_links': '1' if self.quick_links_switch.get() == 1 else '0',
                'image_cache_enabled': '1' if self.image_cache_switch.get() == 1 else '0',
                
                # Phase 4B: Captcha API settings
                'twocaptcha_api_key': self.twocaptcha_entry.get().strip(),
                'anticaptcha_api_key': self.anticaptcha_entry.get().strip(),
                
                # Phase 1B/1C: Adaptive Learning
                'enable_speed_learning': '1' if self.speed_learning_switch.get() == 1 else '0',
                'enable_api_learning': '1' if self.api_learning_switch.get() == 1 else '0',
                
                # Phase 3A: Predictions
                'prediction_confidence_threshold': int(self.confidence_entry.get()),
                
                # Phase 3B: Account Rotation
                'enable_account_rotation': '1' if self.account_rotation_switch.get() == 1 else '0',
                'rotation_strategy': self.rotation_strategy_var.get(),
                
                # Phase 4B: Proxy Health
                'proxy_health_interval': int(self.proxy_health_entry.get()),
            }
            
            self.db.save_settings(settings)
            
            # Apply settings to task manager
            self.task_manager.headless_mode = settings['headless']
            
            # Update webhook
            if settings['webhook_url']:
                self.webhook.set_webhook_url(settings['webhook_url'])
            
            self.add_activity_log("✅ All settings saved successfully (including Phase features)")
            messagebox.showinfo("Success", "All settings saved successfully!\n\nAll Phase features are now configured.")
        except ValueError as e:
            messagebox.showerror("Error", f"Invalid input: {e}\n\nPlease check your numeric values.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save settings: {e}")
    
    def add_activity_log(self, message: str, color: str = None):
        """Add entry to activity log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        self.activity_logs.insert(0, log_entry)
        
        # Keep only last 100 entries
        if len(self.activity_logs) > 100:
            self.activity_logs = self.activity_logs[:100]
        
        # Update text widget
        if hasattr(self, 'activity_text'):
            self.activity_text.configure(state="normal")
            self.activity_text.delete("1.0", "end")
            self.activity_text.insert("1.0", "".join(self.activity_logs))
            self.activity_text.configure(state="disabled")
    
    def on_task_status_change(self, task_id: int, new_status: str):
        """Callback when task status changes - called from background thread"""
        # Use after() to schedule UI updates on main thread (thread-safe)
        try:
            self.after(0, lambda: self._handle_task_status_change(task_id, new_status))
        except:
            # Window might be destroyed, ignore
            pass
    
    def _handle_task_status_change(self, task_id: int, new_status: str):
        """Handle task status change on main thread"""
        try:
            self.add_activity_log(f"Task {task_id} status: {new_status}")
            self.refresh_tasks()
        except:
            # Widget might be destroyed, ignore
            pass
    
    def _thread_safe_log(self, message: str):
        """Thread-safe wrapper for add_activity_log"""
        try:
            self.after(0, lambda: self.add_activity_log(message))
        except:
            # Window might be destroyed, ignore
            pass
    
    def _thread_safe_monitor_event(self, event_type: str, data: dict):
        """Thread-safe wrapper for monitor events"""
        try:
            self.after(0, lambda: self.on_monitor_event(event_type, data))
        except:
            # Window might be destroyed, ignore
            pass
    
    def update_ui_loop(self):
        """Update UI periodically"""
        try:
            # Update stats
            stats = self.task_manager.get_stats()
            
            if hasattr(self, 'stat_cards') and self.stat_cards:
                self.stat_cards['tasks_total'].value_label.configure(text=str(stats['total']))
                self.stat_cards['tasks_running'].value_label.configure(text=str(stats['running']))
                self.stat_cards['tasks_success'].value_label.configure(text=str(stats['success']))
                self.stat_cards['tasks_failed'].value_label.configure(text=str(stats['failed']))
            
            # Update captcha stats
            if hasattr(self, 'captcha_stats_label'):
                queue_size = self.captcha_queue.queue_size()
                pending = self.captcha_queue.pending_requests()
                solved = self.captcha_queue.tokens_available()
                self.captcha_stats_label.configure(text=f"Queue: {queue_size} | Pending: {pending} | Solved: {solved}")
            
            # Update tasks display if on tasks panel
            if self.current_panel == "tasks":
                self.refresh_tasks()
            
            # Update monitor display if on monitor panel
            if self.current_panel == "monitor":
                self.update_monitor_display()
                
        except Exception as e:
            print(f"UI update error: {e}")
        
        # Schedule next update
        self.after(1000, self.update_ui_loop)


if __name__ == "__main__":
    app = AutobotApp()
    app.mainloop()
