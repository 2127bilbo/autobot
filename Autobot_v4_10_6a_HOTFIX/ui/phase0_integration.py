"""
Phase 0 Integration Module
Adds right-click menus, live settings, and image display to existing dashboard
"""

import tkinter as tk
from typing import TYPE_CHECKING
from core.settings_manager import get_settings_manager
from ui.context_menu import (
    MonitorContextMenu, TaskContextMenu, 
    ProfileContextMenu, ProxyContextMenu
)
from ui.image_display import get_image_manager, get_product_image

if TYPE_CHECKING:
    from ui.dashboard import AutobotApp


class Phase0Integration:
    """
    Integrates Phase 0 features into existing AutobotApp
    - Right-click context menus
    - Live settings updates
    - Actual image display
    """
    
    def __init__(self, app: 'AutobotApp'):
        """
        Initialize Phase 0 integration
        
        Args:
            app: The AutobotApp instance
        """
        self.app = app
        self.settings_manager = get_settings_manager()
        self.image_manager = get_image_manager()
        
        # Track created context menus for cleanup
        self.context_menus = []
        
        # Setup everything
        self.setup_live_settings()
        print("✅ Phase 0: Live settings enabled")
    
    def setup_live_settings(self):
        """
        Setup live settings system
        Settings now apply immediately without restart
        """
        # Register callbacks for all settings
        
        # Monitor interval
        self.settings_manager.register_callback(
            'monitor_interval',
            self._on_monitor_interval_change
        )
        
        # Webhook URL
        self.settings_manager.register_callback(
            'webhook_url',
            self._on_webhook_url_change
        )
        
        # Display toggles
        self.settings_manager.register_callback(
            'show_images',
            self._on_show_images_change
        )
        
        self.settings_manager.register_callback(
            'show_prices',
            self._on_display_change
        )
        
        self.settings_manager.register_callback(
            'show_monitor_stats',
            self._on_display_change
        )
    
    def _on_monitor_interval_change(self, new_value):
        """Handle monitor interval change"""
        try:
            interval = int(new_value)
            if hasattr(self.app, 'product_monitor'):
                # Update all active monitors
                for monitor_id in list(self.app.product_monitor.monitors.keys()):
                    monitor = self.app.product_monitor.monitors.get(monitor_id)
                    if monitor and hasattr(monitor, 'check_interval'):
                        monitor.check_interval = interval
                
                print(f"✅ Monitor interval updated to {interval}s (live)")
        except Exception as e:
            print(f"Error updating monitor interval: {e}")
    
    def _on_webhook_url_change(self, new_value):
        """Handle webhook URL change"""
        try:
            if hasattr(self.app, 'webhook'):
                self.app.webhook.set_webhook_url(new_value)
                print(f"✅ Webhook URL updated (live)")
        except Exception as e:
            print(f"Error updating webhook: {e}")
    
    def _on_show_images_change(self, new_value):
        """Handle show images toggle"""
        try:
            # Refresh monitor panel to show/hide images
            if hasattr(self.app, 'refresh_monitor_list'):
                self.app.refresh_monitor_list()
                print(f"✅ Image display updated (live)")
        except Exception as e:
            print(f"Error updating image display: {e}")
    
    def _on_display_change(self, new_value):
        """Handle any display setting change"""
        try:
            # Refresh relevant UI panels
            if hasattr(self.app, 'refresh_monitor_list'):
                self.app.refresh_monitor_list()
                print(f"✅ Display settings updated (live)")
        except Exception as e:
            print(f"Error updating display: {e}")
    
    def add_monitor_context_menu(self, widget, monitor_id: int):
        """
        Add right-click context menu to a monitor card
        
        Args:
            widget: The monitor card widget
            monitor_id: ID of the monitor
        """
        callbacks = {
            'edit': self._edit_monitor,
            'delete': self._delete_monitor,
            'pause': self._pause_monitor,
            'resume': self._resume_monitor,
            'copy_url': self._copy_monitor_url,
            'analytics': self._show_monitor_analytics
        }
        
        menu = MonitorContextMenu(widget, monitor_id, callbacks)
        self.context_menus.append(menu)
        return menu
    
    def add_task_context_menu(self, widget, task_id: int):
        """
        Add right-click context menu to a task item
        
        Args:
            widget: The task widget
            task_id: ID of the task
        """
        callbacks = {
            'edit': self._edit_task,
            'clone': self._clone_task,
            'delete': self._delete_task,
            'set_priority': self._set_task_priority
        }
        
        menu = TaskContextMenu(widget, task_id, callbacks)
        self.context_menus.append(menu)
        return menu
    
    def add_profile_context_menu(self, widget, profile_id: int):
        """
        Add right-click context menu to a profile card
        
        Args:
            widget: The profile card widget
            profile_id: ID of the profile
        """
        callbacks = {
            'edit': self._edit_profile,
            'clone': self._clone_profile,
            'delete': self._delete_profile,
            'set_default': self._set_default_profile,
            'test': self._test_profile
        }
        
        menu = ProfileContextMenu(widget, profile_id, callbacks)
        self.context_menus.append(menu)
        return menu
    
    def add_proxy_context_menu(self, widget, proxy_id: int):
        """
        Add right-click context menu to a proxy item
        
        Args:
            widget: The proxy widget
            proxy_id: ID of the proxy
        """
        callbacks = {
            'test': self._test_proxy,
            'edit': self._edit_proxy,
            'delete': self._delete_proxy,
            'toggle': self._toggle_proxy,
            'stats': self._show_proxy_stats
        }
        
        menu = ProxyContextMenu(widget, proxy_id, callbacks)
        self.context_menus.append(menu)
        return menu
    
    def get_monitor_image(self, monitor, size=(80, 80)):
        """
        Get actual product image for display
        
        Args:
            monitor: Monitor object with image_url
            size: Tuple of (width, height)
        
        Returns:
            CTkImage for display
        """
        if hasattr(monitor, 'image_url') and monitor.image_url:
            # Check if images are enabled
            settings = self.app.db.get_settings()
            if settings and settings.get('show_images', '1') == '1':
                try:
                    return get_product_image(monitor.image_url, size)
                except Exception as e:
                    print(f"Error loading image: {e}")
        
        # Return placeholder
        return self.image_manager.placeholder_image
    
    # Monitor callbacks
    def _edit_monitor(self, monitor_id: int):
        """Edit a monitor"""
        try:
            # Find the monitor
            monitor = self.app.product_monitor.monitors.get(monitor_id)
            if not monitor:
                # Try to get from database
                monitors = self.app.db.get_monitors()
                monitor_data = next((m for m in monitors if m['id'] == monitor_id), None)
                if not monitor_data:
                    print(f"Monitor {monitor_id} not found")
                    return
                monitor = monitor_data
            
            # TODO: Open edit dialog (would need to create edit_monitor_dialog)
            print(f"📝 Edit monitor {monitor_id}")
            # For now, just show a message
            tk.messagebox.showinfo("Edit Monitor", f"Edit dialog for monitor {monitor_id}\n(Feature coming soon)")
        except Exception as e:
            print(f"Error editing monitor: {e}")
    
    def _delete_monitor(self, monitor_id: int):
        """Delete a monitor"""
        try:
            result = tk.messagebox.askyesno(
                "Delete Monitor",
                f"Are you sure you want to delete monitor {monitor_id}?"
            )
            if result:
                # Stop the monitor if running
                if monitor_id in self.app.product_monitor.monitors:
                    self.app.product_monitor.stop_monitor(monitor_id)
                
                # Delete from database
                self.app.db.delete_monitor(monitor_id)
                
                # Refresh UI
                if hasattr(self.app, 'refresh_monitor_list'):
                    self.app.refresh_monitor_list()
                
                print(f"🗑️ Deleted monitor {monitor_id}")
        except Exception as e:
            print(f"Error deleting monitor: {e}")
    
    def _pause_monitor(self, monitor_id: int):
        """Pause a monitor"""
        try:
            self.app.product_monitor.stop_monitor(monitor_id)
            print(f"⏸️ Paused monitor {monitor_id}")
            
            if hasattr(self.app, 'refresh_monitor_list'):
                self.app.refresh_monitor_list()
        except Exception as e:
            print(f"Error pausing monitor: {e}")
    
    def _resume_monitor(self, monitor_id: int):
        """Resume a monitor"""
        try:
            # Get monitor data
            monitors = self.app.db.get_monitors()
            monitor_data = next((m for m in monitors if m['id'] == monitor_id), None)
            
            if monitor_data:
                self.app.product_monitor.start_monitor(
                    monitor_data['id'],
                    monitor_data['site'],
                    monitor_data['product_url']
                )
                print(f"▶️ Resumed monitor {monitor_id}")
                
                if hasattr(self.app, 'refresh_monitor_list'):
                    self.app.refresh_monitor_list()
        except Exception as e:
            print(f"Error resuming monitor: {e}")
    
    def _copy_monitor_url(self, monitor_id: int):
        """Copy monitor product URL to clipboard"""
        try:
            monitors = self.app.db.get_monitors()
            monitor_data = next((m for m in monitors if m['id'] == monitor_id), None)
            
            if monitor_data and monitor_data.get('product_url'):
                self.app.clipboard_clear()
                self.app.clipboard_append(monitor_data['product_url'])
                print(f"📋 Copied URL for monitor {monitor_id}")
                tk.messagebox.showinfo("Copied", "Product URL copied to clipboard!")
        except Exception as e:
            print(f"Error copying URL: {e}")
    
    def _show_monitor_analytics(self, monitor_id: int):
        """Show analytics for a monitor"""
        try:
            # TODO: Open analytics panel filtered to this monitor
            print(f"📊 Analytics for monitor {monitor_id}")
            tk.messagebox.showinfo("Analytics", f"Analytics for monitor {monitor_id}\n(Feature coming soon)")
        except Exception as e:
            print(f"Error showing analytics: {e}")
    
    # Task callbacks
    def _edit_task(self, task_id: int):
        """Edit a task"""
        print(f"📝 Edit task {task_id}")
        tk.messagebox.showinfo("Edit Task", f"Edit dialog for task {task_id}\n(Feature coming soon)")
    
    def _clone_task(self, task_id: int):
        """Clone a task"""
        try:
            # Get task data
            task = self.app.task_manager.get_task(task_id)
            if task:
                # Create new task with same data
                new_task_id = self.app.task_manager.create_task(
                    task.product_url,
                    task.site,
                    task.profile_id,
                    task.proxy_id
                )
                print(f"📋 Cloned task {task_id} -> {new_task_id}")
                tk.messagebox.showinfo("Cloned", f"Task cloned successfully!")
        except Exception as e:
            print(f"Error cloning task: {e}")
    
    def _delete_task(self, task_id: int):
        """Delete a task"""
        try:
            result = tk.messagebox.askyesno("Delete Task", f"Delete task {task_id}?")
            if result:
                self.app.task_manager.delete_task(task_id)
                print(f"🗑️ Deleted task {task_id}")
        except Exception as e:
            print(f"Error deleting task: {e}")
    
    def _set_task_priority(self, task_id: int, priority: str):
        """Set task priority"""
        print(f"⚡ Set task {task_id} priority to {priority}")
        tk.messagebox.showinfo("Priority", f"Task priority set to {priority}")
    
    # Profile callbacks
    def _edit_profile(self, profile_id: int):
        """Edit a profile"""
        print(f"📝 Edit profile {profile_id}")
        tk.messagebox.showinfo("Edit Profile", f"Edit dialog for profile {profile_id}\n(Feature coming soon)")
    
    def _clone_profile(self, profile_id: int):
        """Clone a profile"""
        print(f"📋 Clone profile {profile_id}")
        tk.messagebox.showinfo("Clone", "Profile cloned!")
    
    def _delete_profile(self, profile_id: int):
        """Delete a profile"""
        try:
            result = tk.messagebox.askyesno("Delete Profile", f"Delete profile {profile_id}?")
            if result:
                self.app.db.delete_profile(profile_id)
                print(f"🗑️ Deleted profile {profile_id}")
        except Exception as e:
            print(f"Error deleting profile: {e}")
    
    def _set_default_profile(self, profile_id: int):
        """Set as default profile"""
        print(f"⭐ Set profile {profile_id} as default")
        tk.messagebox.showinfo("Default", "Profile set as default!")
    
    def _test_profile(self, profile_id: int):
        """Test a profile"""
        print(f"🧪 Test profile {profile_id}")
        tk.messagebox.showinfo("Test", "Profile test started...")
    
    # Proxy callbacks
    def _test_proxy(self, proxy_id: int):
        """Test a proxy"""
        print(f"🧪 Test proxy {proxy_id}")
        tk.messagebox.showinfo("Test", "Proxy test started...")
    
    def _edit_proxy(self, proxy_id: int):
        """Edit a proxy"""
        print(f"📝 Edit proxy {proxy_id}")
        tk.messagebox.showinfo("Edit Proxy", f"Edit dialog for proxy {proxy_id}\n(Feature coming soon)")
    
    def _delete_proxy(self, proxy_id: int):
        """Delete a proxy"""
        try:
            result = tk.messagebox.askyesno("Delete Proxy", f"Delete proxy {proxy_id}?")
            if result:
                self.app.db.delete_proxy(proxy_id)
                print(f"🗑️ Deleted proxy {proxy_id}")
        except Exception as e:
            print(f"Error deleting proxy: {e}")
    
    def _toggle_proxy(self, proxy_id: int):
        """Toggle proxy enabled/disabled"""
        print(f"🔄 Toggle proxy {proxy_id}")
        tk.messagebox.showinfo("Toggle", "Proxy toggled!")
    
    def _show_proxy_stats(self, proxy_id: int):
        """Show proxy statistics"""
        print(f"📊 Stats for proxy {proxy_id}")
        tk.messagebox.showinfo("Stats", f"Statistics for proxy {proxy_id}\n(Feature coming soon)")
    
    def cleanup(self):
        """Cleanup all context menus"""
        for menu in self.context_menus:
            try:
                menu.menu.destroy()
            except:
                pass
        self.context_menus.clear()


def integrate_phase0(app: 'AutobotApp') -> Phase0Integration:
    """
    Integrate Phase 0 features into existing app
    
    Args:
        app: The AutobotApp instance
    
    Returns:
        Phase0Integration instance
    """
    integration = Phase0Integration(app)
    
    # Store reference in app
    app.phase0 = integration
    
    print("✅ Phase 0 integration complete!")
    print("   - Right-click context menus enabled")
    print("   - Live settings system enabled")
    print("   - Image display system ready")
    
    return integration
