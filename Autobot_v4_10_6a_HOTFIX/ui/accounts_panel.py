"""
Autobot Accounts Panel - Phase 3B
UI for managing the account pool

This panel allows users to:
- View all accounts
- Add new accounts
- Remove accounts
- View account statistics
- Monitor account health

Author: Bob (Bloomfield, IN)
Created: November 13, 2025
"""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from typing import Optional
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.account_pool import AccountPool


class AccountsPanel(ttk.Frame):
    """
    Panel for managing the account pool.
    """
    
    def __init__(self, parent, db_path: str = "autobot.db"):
        super().__init__(parent)
        self.db_path = db_path
        self.account_pool = AccountPool(db_path)
        
        self.init_ui()
        self.refresh_accounts()
    
    def init_ui(self):
        """Initialize the UI components."""
        # Title
        title_frame = ttk.Frame(self)
        title_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(
            title_frame,
            text="Account Pool Management",
            font=("Arial", 14, "bold")
        ).pack(side=tk.LEFT)
        
        ttk.Button(
            title_frame,
            text="Refresh",
            command=self.refresh_accounts
        ).pack(side=tk.RIGHT, padx=5)
        
        ttk.Button(
            title_frame,
            text="Add Account",
            command=self.show_add_account_dialog
        ).pack(side=tk.RIGHT)
        
        # Stats frame
        stats_frame = ttk.LabelFrame(self, text="Pool Statistics", padding=10)
        stats_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        self.stats_labels = {}
        stats_grid = ttk.Frame(stats_frame)
        stats_grid.pack(fill=tk.X)
        
        # Create stat labels
        stat_names = [
            ("Total Accounts:", "total"),
            ("Available:", "available"),
            ("Banned:", "banned"),
            ("Avg Success Rate:", "success_rate"),
            ("Avg Health:", "health")
        ]
        
        for i, (label, key) in enumerate(stat_names):
            row = i // 3
            col = (i % 3) * 2
            
            ttk.Label(stats_grid, text=label).grid(
                row=row, column=col, sticky=tk.W, padx=(0, 5), pady=2
            )
            
            value_label = ttk.Label(stats_grid, text="0", font=("Arial", 10, "bold"))
            value_label.grid(row=row, column=col+1, sticky=tk.W, padx=(0, 20), pady=2)
            
            self.stats_labels[key] = value_label
        
        # Accounts list
        list_frame = ttk.LabelFrame(self, text="Accounts", padding=10)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Treeview
        columns = ("Email", "Site", "Successes", "Failures", "Bans", "Success Rate", "Health", "Status")
        self.tree = ttk.Treeview(
            list_frame,
            columns=columns,
            show="tree headings",
            yscrollcommand=scrollbar.set,
            selectmode="browse"
        )
        scrollbar.config(command=self.tree.yview)
        
        # Configure columns
        self.tree.column("#0", width=150, minwidth=100)
        self.tree.heading("#0", text="Name")
        
        column_widths = [200, 100, 80, 80, 60, 100, 80, 100]
        for col, width in zip(columns, column_widths):
            self.tree.column(col, width=width, minwidth=50)
            self.tree.heading(col, text=col)
        
        self.tree.pack(fill=tk.BOTH, expand=True)
        
        # Context menu
        self.context_menu = tk.Menu(self.tree, tearoff=0)
        self.context_menu.add_command(label="View Details", command=self.show_account_details)
        self.context_menu.add_command(label="Remove Account", command=self.remove_account)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Clear Ban", command=self.clear_ban)
        
        self.tree.bind("<Button-3>", self.show_context_menu)
        
        # Button frame
        button_frame = ttk.Frame(self)
        button_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        ttk.Button(
            button_frame,
            text="View Details",
            command=self.show_account_details
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(
            button_frame,
            text="Remove Account",
            command=self.remove_account
        ).pack(side=tk.LEFT)
    
    def refresh_accounts(self):
        """Refresh the accounts list and statistics."""
        # Clear tree
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Get pool stats
        pool_stats = self.account_pool.get_pool_stats()
        
        # Update stats labels
        self.stats_labels['total'].config(text=str(pool_stats['total_accounts']))
        self.stats_labels['available'].config(text=str(pool_stats['available_accounts']))
        self.stats_labels['banned'].config(text=str(pool_stats['banned_accounts']))
        self.stats_labels['success_rate'].config(text=f"{pool_stats['avg_success_rate']:.1%}")
        self.stats_labels['health'].config(text=f"{pool_stats['avg_health_score']:.2f}")
        
        # Get all accounts
        accounts = self.account_pool.get_all_accounts()
        
        # Add to tree
        for acc in accounts:
            status = "🚫 BANNED" if acc['is_banned'] else "✅ Available"
            
            self.tree.insert(
                "",
                tk.END,
                text=acc['name'],
                values=(
                    acc['email'],
                    acc.get('site', 'Any'),
                    acc['success_count'],
                    acc['failure_count'],
                    acc['ban_count'],
                    f"{acc['success_rate']:.1%}",
                    f"{acc['health_score']:.2f}",
                    status
                ),
                tags=('banned',) if acc['is_banned'] else ()
            )
        
        # Configure tags
        self.tree.tag_configure('banned', foreground='red')
    
    def show_add_account_dialog(self):
        """Show dialog to add a new account."""
        dialog = tk.Toplevel(self)
        dialog.title("Add Account")
        dialog.geometry("400x300")
        dialog.transient(self)
        dialog.grab_set()
        
        # Form
        form_frame = ttk.Frame(dialog, padding=20)
        form_frame.pack(fill=tk.BOTH, expand=True)
        
        # Name
        ttk.Label(form_frame, text="Account Name:").grid(row=0, column=0, sticky=tk.W, pady=5)
        name_entry = ttk.Entry(form_frame, width=30)
        name_entry.grid(row=0, column=1, pady=5, padx=(10, 0))
        
        # Email
        ttk.Label(form_frame, text="Email:").grid(row=1, column=0, sticky=tk.W, pady=5)
        email_entry = ttk.Entry(form_frame, width=30)
        email_entry.grid(row=1, column=1, pady=5, padx=(10, 0))
        
        # Site (optional)
        ttk.Label(form_frame, text="Site (optional):").grid(row=2, column=0, sticky=tk.W, pady=5)
        site_entry = ttk.Entry(form_frame, width=30)
        site_entry.grid(row=2, column=1, pady=5, padx=(10, 0))
        
        ttk.Label(
            form_frame,
            text="Leave blank for any site",
            font=("Arial", 8),
            foreground="gray"
        ).grid(row=3, column=1, sticky=tk.W, padx=(10, 0))
        
        def add_account():
            name = name_entry.get().strip()
            email = email_entry.get().strip()
            site = site_entry.get().strip() or None
            
            if not name or not email:
                messagebox.showerror("Error", "Name and email are required")
                return
            
            try:
                self.account_pool.add_account(name, email, site=site)
                self.refresh_accounts()
                dialog.destroy()
                messagebox.showinfo("Success", f"Account '{name}' added successfully!")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to add account: {e}")
        
        # Buttons
        button_frame = ttk.Frame(form_frame)
        button_frame.grid(row=4, column=0, columnspan=2, pady=20)
        
        ttk.Button(button_frame, text="Add", command=add_account).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT)
        
        name_entry.focus()
    
    def show_account_details(self):
        """Show detailed statistics for selected account."""
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select an account")
            return
        
        item = selection[0]
        account_name = self.tree.item(item, "text")
        
        # Find account
        account = None
        for acc in self.account_pool.accounts.values():
            if acc.name == account_name:
                account = acc
                break
        
        if not account:
            messagebox.showerror("Error", "Account not found")
            return
        
        # Show details dialog
        dialog = tk.Toplevel(self)
        dialog.title(f"Account Details: {account.name}")
        dialog.geometry("500x400")
        dialog.transient(self)
        
        # Details frame
        details_frame = ttk.Frame(dialog, padding=20)
        details_frame.pack(fill=tk.BOTH, expand=True)
        
        # Basic info
        info_text = tk.Text(details_frame, height=20, width=60)
        info_text.pack(fill=tk.BOTH, expand=True)
        
        info_text.insert(tk.END, f"Account: {account.name}\n", "bold")
        info_text.insert(tk.END, f"Email: {account.email}\n\n")
        
        info_text.insert(tk.END, "Performance:\n", "bold")
        info_text.insert(tk.END, f"  Successes: {account.success_count}\n")
        info_text.insert(tk.END, f"  Failures: {account.failure_count}\n")
        info_text.insert(tk.END, f"  Bans: {account.ban_count}\n")
        info_text.insert(tk.END, f"  Success Rate: {account.success_rate:.1%}\n\n")
        
        info_text.insert(tk.END, "Health:\n", "bold")
        info_text.insert(tk.END, f"  Health Score: {account.health_score:.2f}/1.00\n\n")
        
        info_text.insert(tk.END, "Status:\n", "bold")
        if account.is_banned:
            info_text.insert(tk.END, f"  Status: BANNED\n", "banned")
            if account.cooldown_until:
                info_text.insert(tk.END, f"  Cooldown until: {account.cooldown_until.strftime('%Y-%m-%d %H:%M:%S')}\n")
        else:
            info_text.insert(tk.END, f"  Status: Available\n", "available")
        
        if account.last_used:
            info_text.insert(tk.END, f"  Last used: {account.last_used.strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        if account.last_ban:
            info_text.insert(tk.END, f"  Last ban: {account.last_ban.strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        # Configure tags
        info_text.tag_config("bold", font=("Arial", 10, "bold"))
        info_text.tag_config("banned", foreground="red")
        info_text.tag_config("available", foreground="green")
        
        info_text.config(state=tk.DISABLED)
        
        # Close button
        ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=10)
    
    def remove_account(self):
        """Remove selected account."""
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select an account")
            return
        
        item = selection[0]
        account_name = self.tree.item(item, "text")
        
        # Confirm
        if not messagebox.askyesno("Confirm", f"Remove account '{account_name}'?"):
            return
        
        # Find and remove account
        for acc_id, acc in self.account_pool.accounts.items():
            if acc.name == account_name:
                if self.account_pool.remove_account(acc_id):
                    self.refresh_accounts()
                    messagebox.showinfo("Success", f"Account '{account_name}' removed")
                else:
                    messagebox.showerror("Error", "Failed to remove account")
                break
    
    def clear_ban(self):
        """Clear ban on selected account."""
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select an account")
            return
        
        item = selection[0]
        account_name = self.tree.item(item, "text")
        
        # Find account
        for acc in self.account_pool.accounts.values():
            if acc.name == account_name:
                acc.is_banned = False
                acc.cooldown_until = None
                self.account_pool._update_account(acc)
                self.refresh_accounts()
                messagebox.showinfo("Success", f"Ban cleared for '{account_name}'")
                break
    
    def show_context_menu(self, event):
        """Show context menu on right-click."""
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.context_menu.post(event.x_root, event.y_root)


def main():
    """Test the accounts panel."""
    root = tk.Tk()
    root.title("Accounts Panel Test")
    root.geometry("1000x600")
    
    panel = AccountsPanel(root)
    panel.pack(fill=tk.BOTH, expand=True)
    
    root.mainloop()


if __name__ == "__main__":
    main()
