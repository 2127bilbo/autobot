"""
Autobot Task Manager
Handles task lifecycle, execution, and state management
"""

import asyncio
import threading
import time
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Callable, Dict, List
from datetime import datetime
import uuid


class TaskStatus(Enum):
    """Task execution states"""
    IDLE = "idle"
    RUNNING = "running"
    STOPPED = "stopped"
    SUCCESS = "success"
    FAILED = "failed"
    WAITING_CAPTCHA = "waiting_captcha"


class TaskMode(Enum):
    """Task execution modes"""
    SAFE = "safe"  # Slower, more human-like
    FAST = "fast"  # Faster, less delays
    HEADLESS = "headless"  # No browser UI


@dataclass
class Task:
    """Individual task configuration and state"""
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    site: str = "Target"
    product_url: str = ""
    size: str = "Random"
    profile_name: str = ""
    proxy: Optional[str] = None
    mode: TaskMode = TaskMode.SAFE
    status: TaskStatus = TaskStatus.IDLE
    learn_api: bool = False  # Toggle for API pattern learning
    monitor_id: Optional[str] = None  # Link to monitor for auto-restart
    
    # Runtime data
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    error_message: str = ""
    retry_count: int = 0
    max_retries: int = 3
    
    # Product info (populated during execution)
    product_name: str = ""
    product_price: float = 0.0
    product_image: str = ""
    
    def to_dict(self) -> Dict:
        """Convert task to dictionary for UI updates"""
        # Handle mode - could be enum or string
        if isinstance(self.mode, TaskMode):
            mode_str = self.mode.value
        else:
            mode_str = str(self.mode) if self.mode else "safe"
        
        return {
            'id': self.task_id,
            'task_id': self.task_id,
            'site': self.site,
            'url': self.product_url,
            'product_url': self.product_url,
            'size': self.size,
            'profile': {'name': self.profile_name} if self.profile_name else {},
            'proxy': self.proxy or "None",
            'mode': mode_str,
            'status': self.status.value.upper(),
            'product_name': self.product_name,
            'product_price': self.product_price,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'error': self.error_message,
            'monitor_id': self.monitor_id
        }


class TaskManager:
    """
    Central task management system
    Handles task creation, execution, monitoring, and lifecycle
    """
    
    def __init__(self, db=None):
        self.db = db
        self.tasks: Dict[str, Task] = {}
        self.active_threads: Dict[str, threading.Thread] = {}
        self.stop_flags: Dict[str, threading.Event] = {}
        self.task_callbacks: List[Callable] = []
        
        # Callback properties for UI
        self.on_status_change = None
        self.on_log = None
        
        # Global settings
        self.headless_mode = False
        self.webhook_enabled = False
        self.webhook_url = ""
        
        # Statistics
        self.total_started = 0
        self.total_success = 0
        self.total_failed = 0
    
    def create_task(self, **kwargs) -> str:
        """
        Create a new task with configuration
        Handles parameter transformation from UI
        """
        # Transform UI parameters to Task parameters
        if 'url' in kwargs:
            kwargs['product_url'] = kwargs.pop('url')
        
        if 'profile' in kwargs:
            profile = kwargs.pop('profile')
            if isinstance(profile, dict):
                kwargs['profile_name'] = profile.get('name', '')
            else:
                kwargs['profile_name'] = str(profile)
        
        # Remove quantity (not part of Task)
        kwargs.pop('quantity', None)
        
        # Create task
        task = Task(**kwargs)
        self.tasks[task.task_id] = task
        self._notify_callbacks(task, "created")
        return task.task_id
    
    def create_multiple_tasks(self, count: int, **kwargs) -> List[Task]:
        """Create multiple identical tasks"""
        tasks = []
        for _ in range(count):
            task = self.create_task(**kwargs)
            tasks.append(task)
        return tasks
    
    def start_task(self, task_id: str):
        """Start a specific task"""
        if task_id not in self.tasks:
            raise ValueError(f"Task {task_id} not found")
        
        task = self.tasks[task_id]
        
        if task.status == TaskStatus.RUNNING:
            return  # Already running
        
        # Create stop flag for this task
        stop_flag = threading.Event()
        self.stop_flags[task_id] = stop_flag
        
        # Create and start thread
        thread = threading.Thread(
            target=self._run_task,
            args=(task, stop_flag),
            daemon=True
        )
        self.active_threads[task_id] = thread
        
        task.status = TaskStatus.RUNNING
        task.start_time = datetime.now()
        self.total_started += 1
        
        thread.start()
        self._notify_callbacks(task, "started")
    
    def start_all_tasks(self):
        """Start all idle tasks"""
        for task_id, task in self.tasks.items():
            if task.status == TaskStatus.IDLE:
                self.start_task(task_id)
    
    def stop_task(self, task_id: str):
        """Stop a running task"""
        if task_id in self.stop_flags:
            self.stop_flags[task_id].set()
            
            task = self.tasks.get(task_id)
            if task:
                task.status = TaskStatus.STOPPED
                task.end_time = datetime.now()
                self._notify_callbacks(task, "stopped")
    
    def stop_all_tasks(self):
        """Stop all running tasks"""
        for task_id in list(self.stop_flags.keys()):
            self.stop_task(task_id)
    
    def delete_task(self, task_id: str):
        """Delete a task"""
        if task_id in self.tasks:
            # Stop if running
            if task_id in self.stop_flags:
                self.stop_task(task_id)
            
            task = self.tasks.pop(task_id)
            self._notify_callbacks(task, "deleted")
            
            # Cleanup
            self.active_threads.pop(task_id, None)
            self.stop_flags.pop(task_id, None)
    
    def delete_all_tasks(self):
        """Delete all tasks"""
        task_ids = list(self.tasks.keys())
        for task_id in task_ids:
            self.delete_task(task_id)
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """Get a task by ID"""
        return self.tasks.get(task_id)
    
    def update_task_profile(self, task_id: str, profile: Optional[Dict]):
        """Update the profile for a task"""
        task = self.tasks.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        
        # Update profile
        if profile:
            task.profile_name = profile.get('name', '')
        else:
            task.profile_name = ''
        
        self._notify_callbacks(task, "updated")
    
    def edit_task(self, task_id: str, **kwargs) -> bool:
        """
        Edit an existing task's configuration
        Can only edit tasks that are IDLE or STOPPED
        """
        task = self.tasks.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        
        # Can't edit running tasks
        if task.status == TaskStatus.RUNNING:
            return False
        
        # Update allowed fields
        if 'url' in kwargs or 'product_url' in kwargs:
            task.product_url = kwargs.get('url') or kwargs.get('product_url')
        
        if 'site' in kwargs:
            task.site = kwargs['site']
        
        if 'size' in kwargs:
            task.size = kwargs['size']
        
        if 'profile' in kwargs:
            profile = kwargs['profile']
            if isinstance(profile, dict):
                task.profile_name = profile.get('name', '')
            else:
                task.profile_name = str(profile) if profile else ''
        
        if 'proxy' in kwargs:
            task.proxy = kwargs['proxy']
        
        if 'mode' in kwargs:
            mode = kwargs['mode']
            if isinstance(mode, str):
                task.mode = TaskMode(mode.lower())
            else:
                task.mode = mode
        
        # Reset status if stopped/failed
        if task.status in [TaskStatus.STOPPED, TaskStatus.FAILED, TaskStatus.SUCCESS]:
            task.status = TaskStatus.IDLE
            task.error_message = ""
            task.retry_count = 0
        
        self._notify_callbacks(task, "updated")
        return True
    
    def get_all_tasks(self) -> List[Dict]:
        """Get all tasks as dictionaries for UI"""
        return [task.to_dict() for task in self.tasks.values()]
    
    def get_tasks_by_status(self, status: TaskStatus) -> List[Task]:
        """Get tasks filtered by status"""
        return [task for task in self.tasks.values() if task.status == status]
    
    def register_callback(self, callback: Callable):
        """Register a callback for task updates"""
        self.task_callbacks.append(callback)
    
    def _notify_callbacks(self, task: Task, event_type: str):
        """Notify all registered callbacks"""
        # Call registered callbacks
        for callback in self.task_callbacks:
            try:
                callback(task, event_type)
            except Exception as e:
                print(f"Callback error: {e}")
        
        # Call UI callbacks if set
        if event_type in ['created', 'started', 'completed', 'failed', 'stopped']:
            if self.on_status_change:
                try:
                    self.on_status_change(task.task_id, task.status.value.upper())
                except Exception as e:
                    print(f"Status callback error: {e}")
            
            if self.on_log:
                try:
                    self.on_log(f"Task {task.task_id} - {event_type}")
                except Exception as e:
                    print(f"Log callback error: {e}")
    
    def _run_task(self, task: Task, stop_flag: threading.Event):
        """
        Execute a task (runs in separate thread)
        Uses site-specific checkout flow with Smart API integration
        """
        try:
            # Log start with clear indicator
            if self.on_log:
                self.on_log(f"Task {task.task_id}: 🚀 Starting execution...")
                self.on_log(f"Task {task.task_id}:    Site: {task.site}")
                self.on_log(f"Task {task.task_id}:    URL: {task.product_url}")
                self.on_log(f"Task {task.task_id}:    Profile: {task.profile_name or 'NOT ASSIGNED'}")
            
            # Import the site module
            site_name = task.site.lower().replace(' ', '_')
            
            if self.on_log:
                self.on_log(f"Task {task.task_id}: Loading {task.site} site module...")
            
            # Use profile_name for persistent browser profile
            # If no profile assigned, use site-specific default
            profile_name_for_browser = task.profile_name if task.profile_name else f"{site_name}_default"
            
            if site_name == 'target':
                from sites.target import TargetSite
                site = TargetSite(headless=self.headless_mode, profile_name=profile_name_for_browser)
            elif site_name == 'walmart':
                from sites.walmart import WalmartSite
                site = WalmartSite(headless=self.headless_mode, profile_name=profile_name_for_browser)
            elif site_name in ['pokemon_center', 'pokemoncenter']:
                from sites.pokemon_center import PokemonCenterSite
                site = PokemonCenterSite(headless=self.headless_mode, profile_name=profile_name_for_browser)
            else:
                raise ValueError(f"Unknown site: {task.site}")
            
            if self.on_log:
                self.on_log(f"Task {task.task_id}: Site module loaded successfully")
            
            # Get profile from database if profile_name is set
            profile = None
            if task.profile_name and self.db:
                if self.on_log:
                    self.on_log(f"Task {task.task_id}: Loading profile '{task.profile_name}'...")
                profiles = self.db.get_all_profiles()
                profile = next((p for p in profiles if p['name'] == task.profile_name), None)
                
                if not profile:
                    if self.on_log:
                        self.on_log(f"Task {task.task_id}: ⚠️  Profile '{task.profile_name}' not found, using persistent browser session")
            
            # If no profile, use persistent browser - assumes user logged in via Settings
            if not profile:
                if self.on_log:
                    self.on_log(f"Task {task.task_id}: ℹ️  Using persistent browser session (no profile)")
                # Create minimal profile for persistent session
                profile = {
                    'name': profile_name_for_browser,
                    'email': '',  # Will use existing login
                    'password': ''  # Will use existing login
                }
            
            # === SMART API CHECK (NO ASYNC - Pattern must be learned beforehand via Settings) ===
            api_result = None
            if self.db:
                try:
                    # Check if we have a learned pattern (from separate async warmup)
                    patterns = self.db.get_api_patterns(site_name)
                    
                    if patterns:
                        if self.on_log:
                            self.on_log(f"Task {task.task_id}: Using Smart API for pre-checkout stock check...")
                        
                        # Use SYNC API check (no async needed - just HTTP request)
                        import requests
                        import re
                        
                        pattern = patterns[0]  # Use most recent pattern
                        
                        # Extract TCIN/product ID from URL
                        if site_name == 'target':
                            tcin_match = re.search(r'/-?/A-(\d+)', task.product_url)
                            if tcin_match:
                                tcin = tcin_match.group(1)
                                
                                # Make API request (SYNC - no async/await!)
                                api_url = f"{pattern['endpoint_pattern']}?key=ff457966e64d5e877fdbad070f276d18ecec4a01&tcin={tcin}&pricing_store_id=1771&has_pricing_store_id=true"
                                
                                try:
                                    response = requests.get(api_url, timeout=5)
                                    if response.status_code == 200:
                                        data = response.json()
                                        
                                        # Extract data using saved paths
                                        def get_nested(d, path):
                                            keys = path.split('.')
                                            for key in keys:
                                                d = d.get(key, {})
                                            return d
                                        
                                        name = get_nested(data, pattern['name_path']) if pattern.get('name_path') else 'Unknown'
                                        price = get_nested(data, pattern['price_path']) if pattern.get('price_path') else 0.0
                                        stock_oos = get_nested(data, pattern['stock_path']) if pattern.get('stock_path') else None
                                        image = get_nested(data, pattern['image_path']) if pattern.get('image_path') else ''
                                        
                                        stock_status = not stock_oos if stock_oos is not None else True
                                        
                                        api_result = {
                                            'success': True,
                                            'name': name,
                                            'price': price,
                                            'stock': stock_status,
                                            'image': image
                                        }
                                        
                                        if self.on_log:
                                            self.on_log(f"Task {task.task_id}: ✓ API Check Complete!")
                                            self.on_log(f"Task {task.task_id}:   Product: {name}")
                                            self.on_log(f"Task {task.task_id}:   Price: ${price}")
                                            self.on_log(f"Task {task.task_id}:   Stock: {'IN STOCK' if stock_status else 'OUT OF STOCK'}")
                                        
                                        # Check if out of stock
                                        if not stock_status:
                                            task.status = TaskStatus.FAILED
                                            task.error_message = "Out of stock (verified by API)"
                                            self.total_failed += 1
                                            if self.on_log:
                                                self.on_log(f"Task {task.task_id}: ✗ Product out of stock, skipping checkout")
                                            self._notify_callbacks(task, "failed")
                                            return
                                        
                                        # Update product info from API
                                        task.product_name = name
                                        task.product_price = float(price) if price else 0.0
                                        
                                        if self.on_log:
                                            self.on_log(f"Task {task.task_id}: ✓ Stock available, proceeding with checkout...")
                                
                                except Exception as e:
                                    if self.on_log:
                                        self.on_log(f"Task {task.task_id}: ⚠️  API request failed: {e}")
                    else:
                        if self.on_log:
                            self.on_log(f"Task {task.task_id}: No API pattern learned yet - using browser only")
                            self.on_log(f"Task {task.task_id}: 💡 Tip: Learn API via Settings → API Learning for 10-100x speed!")
                        
                except Exception as e:
                    if self.on_log:
                        self.on_log(f"Task {task.task_id}: ⚠️ Smart API error (non-fatal): {e}")
                    # Continue with normal checkout even if API fails
            
            # === CONTINUE WITH BROWSER CHECKOUT ===
            if self.on_log:
                self.on_log(f"Task {task.task_id}: 🌐 Starting browser and checkout flow...")
            
            try:
                # Run the checkout flow with correct parameters
                # Pass api_result so checkout can use it
                result = site.checkout(
                    url=task.product_url,
                    profile=profile,
                    captcha_queue=None,
                    api_data=api_result  # Pass API data to checkout
                )
            except Exception as checkout_error:
                # Catch and report checkout errors clearly
                error_msg = f"Browser/checkout error: {checkout_error}"
                if self.on_log:
                    self.on_log(f"Task {task.task_id}: ❌ {error_msg}")
                result = {
                    'success': False,
                    'message': error_msg,
                    'error': str(checkout_error)
                }
            
            if self.on_log:
                self.on_log(f"Task {task.task_id}: ⚙️  Processing result...")
            
            if result.get('success', False):
                task.status = TaskStatus.SUCCESS
                task.end_time = datetime.now()
                # Extract product info from result (prefer API data if available)
                product_info = result.get('product_info', {})
                task.product_name = task.product_name or product_info.get('name', '')
                task.product_price = task.product_price or product_info.get('price', 0.0)
                task.product_image = product_info.get('image', '')
                self.total_success += 1
                if self.on_log:
                    self.on_log(f"Task {task.task_id}: ✅ SUCCESS - Order completed!")
                # Notify success
                self._notify_callbacks(task, "completed")
            else:
                # Failed - extract all error info
                error_msg = result.get('message', 'Unknown error')
                error_detail = result.get('error', '')
                
                # Combine error messages for clarity
                if error_detail and error_detail not in error_msg:
                    full_error = f"{error_msg} ({error_detail})"
                else:
                    full_error = error_msg
                
                task.status = TaskStatus.FAILED
                task.error_message = full_error
                task.end_time = datetime.now()
                self.total_failed += 1
                if self.on_log:
                    self.on_log(f"Task {task.task_id}: ❌ FAILED - {full_error}")
                
                # Auto-delete failed tasks created by monitors
                # Monitor will create fresh task on next stock detection
                if task.monitor_id:
                    if self.on_log:
                        self.on_log(f"Task {task.task_id}: 🔄 Auto-deleting (monitor will retry on restock)")
                    # Notify failure first, then schedule deletion
                    self._notify_callbacks(task, "failed")
                    # Delete in finally block
                else:
                    # Notify failure for manual tasks
                    self._notify_callbacks(task, "failed")

            
        except Exception as e:
            error_msg = str(e)
            task.status = TaskStatus.FAILED
            task.error_message = error_msg
            task.end_time = datetime.now()
            self.total_failed += 1
            if self.on_log:
                self.on_log(f"Task {task.task_id}: ❌ EXCEPTION - {error_msg}")
            # Print to console for debugging
            import traceback
            print(f"\n{'='*60}")
            print(f"❌ Task {task.task_id} error:")
            print(f"{'='*60}")
            traceback.print_exc()
            print(f"{'='*60}\n")
            # Notify UI about failure
            self._notify_callbacks(task, "failed")
        
        finally:
            task.end_time = datetime.now()
            
            # Auto-delete failed monitor tasks
            if task.monitor_id and task.status == TaskStatus.FAILED:
                if self.on_log:
                    self.on_log(f"Task {task.task_id}: Cleaning up failed monitor task")
                # Delete from tasks dict
                self.tasks.pop(task.task_id, None)
            else:
                # Keep manual tasks for review
                self._notify_callbacks(task, "completed")
            
            # Cleanup
            self.active_threads.pop(task.task_id, None)
            self.stop_flags.pop(task.task_id, None)
    
    def get_statistics(self) -> Dict:
        """Get current statistics"""
        running = len(self.get_tasks_by_status(TaskStatus.RUNNING))
        idle = len(self.get_tasks_by_status(TaskStatus.IDLE))
        
        return {
            'total_tasks': len(self.tasks),
            'running': running,
            'idle': idle,
            'total_started': self.total_started,
            'total_success': self.total_success,
            'total_failed': self.total_failed,
            'success_rate': (self.total_success / self.total_started * 100) 
                           if self.total_started > 0 else 0
        }
    
    def get_stats(self) -> Dict:
        """Get statistics for UI (alias for get_statistics)"""
        return {
            'total': len(self.tasks),
            'running': len(self.get_tasks_by_status(TaskStatus.RUNNING)),
            'success': self.total_success,
            'failed': self.total_failed
        }


# Global task manager instance
task_manager = TaskManager()

