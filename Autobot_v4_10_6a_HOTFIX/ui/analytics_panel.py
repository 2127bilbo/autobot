"""
Autobot Analytics Panel - Phase 3C
Visual analytics dashboard

This panel displays:
- System health metrics
- Success rate charts
- Site performance comparison
- Account performance
- Response time trends

Author: Bob (Bloomfield, IN)
Created: November 13, 2025
"""

import tkinter as tk
from tkinter import ttk
from datetime import datetime
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.analytics import Analytics


class AnalyticsPanel(ttk.Frame):
    """
    Panel for displaying analytics and performance metrics.
    """
    
    def __init__(self, parent, db_path: str = "autobot.db"):
        super().__init__(parent)
        self.db_path = db_path
        self.analytics = Analytics(db_path)
        
        self.init_ui()
        self.refresh_data()
    
    def init_ui(self):
        """Initialize the UI components."""
        # Title
        title_frame = ttk.Frame(self)
        title_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(
            title_frame,
            text="Analytics Dashboard",
            font=("Arial", 14, "bold")
        ).pack(side=tk.LEFT)
        
        ttk.Button(
            title_frame,
            text="Refresh",
            command=self.refresh_data
        ).pack(side=tk.RIGHT)
        
        # System Health Section
        health_frame = ttk.LabelFrame(self, text="System Health (24h)", padding=10)
        health_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        self.health_labels = {}
        
        health_metrics = [
            ("Health Score:", "health_score", "0.00", "green"),
            ("Success Rate:", "success_rate", "0.0%", "blue"),
            ("Avg Response:", "avg_response", "0.00s", "orange"),
            ("Total Checks:", "total_checks", "0", "black"),
            ("Bans Detected:", "total_bans", "0", "red"),
            ("Drops Found:", "drops_found", "0", "green"),
        ]
        
        for i, (label_text, key, default, color) in enumerate(health_metrics):
            row = i // 2
            col = (i % 2) * 2
            
            ttk.Label(health_frame, text=label_text).grid(
                row=row, column=col, sticky=tk.W, padx=(0, 5), pady=5
            )
            
            value_label = ttk.Label(
                health_frame,
                text=default,
                font=("Arial", 11, "bold"),
                foreground=color
            )
            value_label.grid(row=row, column=col+1, sticky=tk.W, padx=(0, 30), pady=5)
            
            self.health_labels[key] = value_label
        
        # Site Performance Section
        site_frame = ttk.LabelFrame(self, text="Site Performance (24h)", padding=10)
        site_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(site_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Treeview
        columns = ("Success Rate", "Avg Response", "Total Checks", "Bans")
        self.site_tree = ttk.Treeview(
            site_frame,
            columns=columns,
            show="tree headings",
            yscrollcommand=scrollbar.set,
            height=8
        )
        scrollbar.config(command=self.site_tree.yview)
        
        # Configure columns
        self.site_tree.column("#0", width=150, minwidth=100)
        self.site_tree.heading("#0", text="Site")
        
        column_widths = [120, 120, 120, 80]
        for col, width in zip(columns, column_widths):
            self.site_tree.column(col, width=width, minwidth=80)
            self.site_tree.heading(col, text=col)
        
        self.site_tree.pack(fill=tk.BOTH, expand=True)
        
        # Summary Stats Section
        summary_frame = ttk.LabelFrame(self, text="Summary", padding=10)
        summary_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        self.summary_text = tk.Text(summary_frame, height=6, width=80)
        self.summary_text.pack(fill=tk.BOTH, expand=True)
        self.summary_text.config(state=tk.DISABLED)
        
        # Status bar
        self.status_label = ttk.Label(self, text="Ready", relief=tk.SUNKEN)
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=5)
    
    def refresh_data(self):
        """Refresh all analytics data."""
        try:
            self.status_label.config(text="Refreshing...")
            self.update_idletasks()
            
            # Update system health
            health = self.analytics.get_system_health()
            
            self.health_labels['health_score'].config(
                text=f"{health['health_score']:.2f}/1.00"
            )
            self.health_labels['success_rate'].config(
                text=f"{health['success_rate']:.1%}"
            )
            self.health_labels['avg_response'].config(
                text=f"{health['avg_response_time']:.2f}s"
            )
            self.health_labels['total_checks'].config(
                text=str(health['total_checks'])
            )
            self.health_labels['total_bans'].config(
                text=str(health['total_bans'])
            )
            self.health_labels['drops_found'].config(
                text=str(health['drops_found'])
            )
            
            # Update site performance
            for item in self.site_tree.get_children():
                self.site_tree.delete(item)
            
            site_perf = self.analytics.get_site_performance(hours=24)
            
            for site in site_perf:
                self.site_tree.insert(
                    "",
                    tk.END,
                    text=site['site'],
                    values=(
                        f"{site['success_rate']:.1%}",
                        f"{site['avg_response_time']:.2f}s",
                        site['total_checks'],
                        site['bans']
                    )
                )
            
            # Update summary
            self.summary_text.config(state=tk.NORMAL)
            self.summary_text.delete(1.0, tk.END)
            
            summary = self.analytics.get_statistics_summary(hours=24)
            
            summary_lines = [
                f"📊 Analytics Summary (Last 24 hours)",
                f"",
                f"Total Sites Monitored: {summary['total_sites']}",
                f"Overall Success Rate: {summary['avg_success_rate']:.1%}",
                f"Average Response Time: {summary['avg_response_time']:.2f}s",
                f"",
                f"System Health: {health['health_score']:.2f}/1.00",
            ]
            
            # Health interpretation
            if health['health_score'] >= 0.8:
                summary_lines.append("Status: ✅ Excellent")
            elif health['health_score'] >= 0.6:
                summary_lines.append("Status: ⚠️ Good")
            elif health['health_score'] >= 0.4:
                summary_lines.append("Status: ⚠️ Fair")
            else:
                summary_lines.append("Status: ❌ Poor")
            
            self.summary_text.insert(tk.END, "\n".join(summary_lines))
            self.summary_text.config(state=tk.DISABLED)
            
            self.status_label.config(
                text=f"Last updated: {datetime.now().strftime('%H:%M:%S')}"
            )
            
        except Exception as e:
            self.status_label.config(text=f"Error: {e}")


def main():
    """Test the analytics panel."""
    root = tk.Tk()
    root.title("Analytics Panel Test")
    root.geometry("700x700")
    
    panel = AnalyticsPanel(root)
    panel.pack(fill=tk.BOTH, expand=True)
    
    # Auto-refresh every 10 seconds
    def auto_refresh():
        panel.refresh_data()
        root.after(10000, auto_refresh)
    
    root.after(5000, auto_refresh)
    
    root.mainloop()


if __name__ == "__main__":
    main()
