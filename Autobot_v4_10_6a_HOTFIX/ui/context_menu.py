"""
Autobot Context Menu System
Provides right-click menus for monitors, tasks, profiles, and proxies
"""

import tkinter as tk
from typing import Callable, List, Tuple, Optional, Any


class ContextMenu:
    """
    Generic context menu that can be attached to any widget
    """
    
    def __init__(self, widget, items: List[Tuple[str, Callable]]):
        """
        Create a context menu
        
        Args:
            widget: The tk widget to attach menu to
            items: List of (label, callback) tuples
        """
        self.widget = widget
        self.menu = tk.Menu(widget, tearoff=0)
        
        # Add menu items
        for label, callback in items:
            if label == "---":  # Separator
                self.menu.add_separator()
            else:
                self.menu.add_command(label=label, command=callback)
        
        # Bind right-click
        widget.bind("<Button-3>", self._show_menu)  # Right-click (Linux/Windows)
        widget.bind("<Button-2>", self._show_menu)  # Right-click (Mac)
    
    def _show_menu(self, event):
        """Show the context menu at cursor position"""
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()
    
    def destroy(self):
        """Clean up the menu"""
        self.menu.destroy()


class MonitorContextMenu:
    """
    Context menu specifically for monitor cards
    Provides Edit, Delete, Pause/Resume, Copy URL options
    """
    
    def __init__(self, widget, monitor_id: int, callbacks: dict):
        """
        Create monitor context menu
        
        Args:
            widget: Widget to attach menu to
            monitor_id: ID of the monitor
            callbacks: Dict with 'edit', 'delete', 'pause', 'resume', 'copy_url' keys
        """
        self.widget = widget
        self.monitor_id = monitor_id
        self.callbacks = callbacks
        self.menu = tk.Menu(widget, tearoff=0)
        
        # Build menu items
        self.menu.add_command(
            label="✏️ Edit Monitor",
            command=lambda: self.callbacks.get('edit', lambda: None)(monitor_id)
        )
        
        self.menu.add_command(
            label="⏸️ Pause Monitor",
            command=lambda: self.callbacks.get('pause', lambda: None)(monitor_id)
        )
        
        self.menu.add_command(
            label="▶️ Resume Monitor",
            command=lambda: self.callbacks.get('resume', lambda: None)(monitor_id)
        )
        
        self.menu.add_separator()
        
        self.menu.add_command(
            label="🔗 Copy Product URL",
            command=lambda: self.callbacks.get('copy_url', lambda: None)(monitor_id)
        )
        
        self.menu.add_command(
            label="📊 View Analytics",
            command=lambda: self.callbacks.get('analytics', lambda: None)(monitor_id)
        )
        
        self.menu.add_separator()
        
        self.menu.add_command(
            label="🗑️ Delete Monitor",
            command=lambda: self.callbacks.get('delete', lambda: None)(monitor_id)
        )
        
        # Bind right-click
        widget.bind("<Button-3>", self._show_menu)
        widget.bind("<Button-2>", self._show_menu)
    
    def _show_menu(self, event):
        """Show the context menu"""
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()


class TaskContextMenu:
    """
    Context menu for task items
    Provides Edit, Clone, Delete, Priority options
    """
    
    def __init__(self, widget, task_id: int, callbacks: dict):
        """
        Create task context menu
        
        Args:
            widget: Widget to attach menu to
            task_id: ID of the task
            callbacks: Dict with 'edit', 'clone', 'delete', 'set_priority' keys
        """
        self.widget = widget
        self.task_id = task_id
        self.callbacks = callbacks
        self.menu = tk.Menu(widget, tearoff=0)
        
        # Build menu
        self.menu.add_command(
            label="✏️ Edit Task",
            command=lambda: self.callbacks.get('edit', lambda: None)(task_id)
        )
        
        self.menu.add_command(
            label="📋 Clone Task",
            command=lambda: self.callbacks.get('clone', lambda: None)(task_id)
        )
        
        self.menu.add_separator()
        
        # Priority submenu
        priority_menu = tk.Menu(self.menu, tearoff=0)
        priority_menu.add_command(
            label="🔴 High Priority",
            command=lambda: self.callbacks.get('set_priority', lambda x, y: None)(task_id, 'high')
        )
        priority_menu.add_command(
            label="🟡 Medium Priority",
            command=lambda: self.callbacks.get('set_priority', lambda x, y: None)(task_id, 'medium')
        )
        priority_menu.add_command(
            label="🟢 Low Priority",
            command=lambda: self.callbacks.get('set_priority', lambda x, y: None)(task_id, 'low')
        )
        
        self.menu.add_cascade(label="⚡ Set Priority", menu=priority_menu)
        
        self.menu.add_separator()
        
        self.menu.add_command(
            label="🗑️ Delete Task",
            command=lambda: self.callbacks.get('delete', lambda: None)(task_id)
        )
        
        # Bind right-click
        widget.bind("<Button-3>", self._show_menu)
        widget.bind("<Button-2>", self._show_menu)
    
    def _show_menu(self, event):
        """Show the context menu"""
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()


class ProfileContextMenu:
    """
    Context menu for profile cards
    Provides Edit, Clone, Set as Default, Delete options
    """
    
    def __init__(self, widget, profile_id: int, callbacks: dict):
        """
        Create profile context menu
        
        Args:
            widget: Widget to attach menu to
            profile_id: ID of the profile
            callbacks: Dict with 'edit', 'clone', 'set_default', 'delete' keys
        """
        self.widget = widget
        self.profile_id = profile_id
        self.callbacks = callbacks
        self.menu = tk.Menu(widget, tearoff=0)
        
        # Build menu
        self.menu.add_command(
            label="✏️ Edit Profile",
            command=lambda: self.callbacks.get('edit', lambda: None)(profile_id)
        )
        
        self.menu.add_command(
            label="📋 Clone Profile",
            command=lambda: self.callbacks.get('clone', lambda: None)(profile_id)
        )
        
        self.menu.add_separator()
        
        self.menu.add_command(
            label="⭐ Set as Default",
            command=lambda: self.callbacks.get('set_default', lambda: None)(profile_id)
        )
        
        self.menu.add_command(
            label="🧪 Test Profile",
            command=lambda: self.callbacks.get('test', lambda: None)(profile_id)
        )
        
        self.menu.add_separator()
        
        self.menu.add_command(
            label="🗑️ Delete Profile",
            command=lambda: self.callbacks.get('delete', lambda: None)(profile_id)
        )
        
        # Bind right-click
        widget.bind("<Button-3>", self._show_menu)
        widget.bind("<Button-2>", self._show_menu)
    
    def _show_menu(self, event):
        """Show the context menu"""
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()


class ProxyContextMenu:
    """
    Context menu for proxy items
    Provides Test, Edit, Delete, Enable/Disable options
    """
    
    def __init__(self, widget, proxy_id: int, callbacks: dict):
        """
        Create proxy context menu
        
        Args:
            widget: Widget to attach menu to
            proxy_id: ID of the proxy
            callbacks: Dict with 'test', 'edit', 'delete', 'toggle' keys
        """
        self.widget = widget
        self.proxy_id = proxy_id
        self.callbacks = callbacks
        self.menu = tk.Menu(widget, tearoff=0)
        
        # Build menu
        self.menu.add_command(
            label="🧪 Test Proxy",
            command=lambda: self.callbacks.get('test', lambda: None)(proxy_id)
        )
        
        self.menu.add_command(
            label="✏️ Edit Proxy",
            command=lambda: self.callbacks.get('edit', lambda: None)(proxy_id)
        )
        
        self.menu.add_separator()
        
        self.menu.add_command(
            label="🔄 Toggle Enable/Disable",
            command=lambda: self.callbacks.get('toggle', lambda: None)(proxy_id)
        )
        
        self.menu.add_command(
            label="📊 View Stats",
            command=lambda: self.callbacks.get('stats', lambda: None)(proxy_id)
        )
        
        self.menu.add_separator()
        
        self.menu.add_command(
            label="🗑️ Delete Proxy",
            command=lambda: self.callbacks.get('delete', lambda: None)(proxy_id)
        )
        
        # Bind right-click
        widget.bind("<Button-3>", self._show_menu)
        widget.bind("<Button-2>", self._show_menu)
    
    def _show_menu(self, event):
        """Show the context menu"""
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()


def attach_context_menu(widget, menu_type: str, item_id: int, callbacks: dict) -> Optional[Any]:
    """
    Convenience function to attach the appropriate context menu to a widget
    
    Args:
        widget: The widget to attach menu to
        menu_type: Type of menu ('monitor', 'task', 'profile', 'proxy')
        item_id: ID of the item
        callbacks: Callbacks dictionary
    
    Returns:
        The created menu object, or None if invalid type
    """
    menu_classes = {
        'monitor': MonitorContextMenu,
        'task': TaskContextMenu,
        'profile': ProfileContextMenu,
        'proxy': ProxyContextMenu
    }
    
    menu_class = menu_classes.get(menu_type.lower())
    if menu_class:
        return menu_class(widget, item_id, callbacks)
    
    return None
