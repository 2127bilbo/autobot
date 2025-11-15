"""
Autobot Settings Manager
Handles live settings updates without requiring restart
"""

import threading
from typing import Callable, Dict, Any, List
from pathlib import Path


class SettingsManager:
    """
    Manages application settings with live update capability.
    Allows components to register callbacks that fire when settings change.
    """
    
    def __init__(self, settings_file: str = "database/settings.json"):
        """
        Initialize the settings manager
        
        Args:
            settings_file: Path to settings file (unused, using database)
        """
        self.settings_file = Path(settings_file)
        self.lock = threading.Lock()
        
        # Callbacks: {setting_key: [callback_functions]}
        self.callbacks: Dict[str, List[Callable]] = {}
        
        # Current settings cache
        self.current_settings: Dict[str, Any] = {}
    
    def register_callback(self, setting_key: str, callback: Callable[[Any], None]):
        """
        Register a callback for when a specific setting changes
        
        Args:
            setting_key: The setting to watch (e.g., 'monitor_interval')
            callback: Function to call when setting changes. Receives new value.
        
        Example:
            manager.register_callback('monitor_interval', lambda val: print(f"New interval: {val}"))
        """
        with self.lock:
            if setting_key not in self.callbacks:
                self.callbacks[setting_key] = []
            
            if callback not in self.callbacks[setting_key]:
                self.callbacks[setting_key].append(callback)
    
    def unregister_callback(self, setting_key: str, callback: Callable):
        """
        Remove a callback for a setting
        
        Args:
            setting_key: The setting key
            callback: The callback function to remove
        """
        with self.lock:
            if setting_key in self.callbacks:
                if callback in self.callbacks[setting_key]:
                    self.callbacks[setting_key].remove(callback)
    
    def notify_change(self, setting_key: str, new_value: Any):
        """
        Notify all registered callbacks that a setting has changed
        
        Args:
            setting_key: The setting that changed
            new_value: The new value of the setting
        """
        # Update cache
        with self.lock:
            self.current_settings[setting_key] = new_value
            callbacks = self.callbacks.get(setting_key, []).copy()
        
        # Call callbacks outside of lock to prevent deadlocks
        for callback in callbacks:
            try:
                callback(new_value)
            except Exception as e:
                print(f"Error in settings callback for {setting_key}: {e}")
    
    def update_setting(self, setting_key: str, new_value: Any):
        """
        Update a setting and notify all callbacks
        
        Args:
            setting_key: The setting to update
            new_value: The new value
        """
        self.notify_change(setting_key, new_value)
    
    def get_setting(self, setting_key: str, default: Any = None) -> Any:
        """
        Get current value of a setting
        
        Args:
            setting_key: The setting to get
            default: Default value if not found
        
        Returns:
            Current setting value or default
        """
        with self.lock:
            return self.current_settings.get(setting_key, default)
    
    def update_multiple(self, settings_dict: Dict[str, Any]):
        """
        Update multiple settings at once
        
        Args:
            settings_dict: Dictionary of setting_key -> new_value
        """
        for key, value in settings_dict.items():
            self.update_setting(key, value)
    
    def get_all_settings(self) -> Dict[str, Any]:
        """
        Get a copy of all current settings
        
        Returns:
            Dictionary of all settings
        """
        with self.lock:
            return self.current_settings.copy()


# Global settings manager instance
_settings_manager = None


def get_settings_manager() -> SettingsManager:
    """
    Get the global settings manager instance
    
    Returns:
        SettingsManager instance
    """
    global _settings_manager
    if _settings_manager is None:
        _settings_manager = SettingsManager()
    return _settings_manager


# Convenience functions
def register_callback(setting_key: str, callback: Callable):
    """Register a callback for setting changes"""
    get_settings_manager().register_callback(setting_key, callback)


def unregister_callback(setting_key: str, callback: Callable):
    """Unregister a callback"""
    get_settings_manager().unregister_callback(setting_key, callback)


def update_setting(setting_key: str, new_value: Any):
    """Update a setting and notify callbacks"""
    get_settings_manager().update_setting(setting_key, new_value)


def get_setting(setting_key: str, default: Any = None) -> Any:
    """Get current setting value"""
    return get_settings_manager().get_setting(setting_key, default)


def update_multiple_settings(settings_dict: Dict[str, Any]):
    """Update multiple settings at once"""
    get_settings_manager().update_multiple(settings_dict)
