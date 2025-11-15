"""
Autobot Monitor & Webhook System
Sends real-time updates to Discord webhooks
"""

import requests
import json
from typing import Dict, Optional
from datetime import datetime
from enum import Enum


class WebhookEventType(Enum):
    """Types of webhook events"""
    TASK_START = "task_start"
    TASK_SUCCESS = "task_success"
    TASK_FAILED = "task_failed"
    CAPTCHA_NEEDED = "captcha_needed"
    CHECKOUT_COMPLETE = "checkout_complete"


class DiscordWebhook:
    """
    Discord webhook integration for monitoring
    Sends formatted embeds for different bot events
    """
    
    # Discord color codes
    COLORS = {
        'success': 0x00ff00,  # Green
        'error': 0xff0000,    # Red
        'info': 0x0099ff,     # Blue
        'warning': 0xffaa00,  # Orange
        'captcha': 0x9b59b6   # Purple
    }
    
    def __init__(self, webhook_url: str = ""):
        self.webhook_url = webhook_url
        self.enabled = bool(webhook_url)
    
    def set_webhook_url(self, url: str):
        """Update webhook URL"""
        self.webhook_url = url
        self.enabled = bool(url)
    
    def send_task_start(self, task_data: Dict):
        """Send notification when task starts"""
        if not self.enabled:
            return
        
        embed = {
            "title": "🚀 Task Started",
            "color": self.COLORS['info'],
            "fields": [
                {
                    "name": "Site",
                    "value": task_data.get('site', 'Unknown'),
                    "inline": True
                },
                {
                    "name": "Product",
                    "value": task_data.get('product_name', 'Loading...'),
                    "inline": True
                },
                {
                    "name": "Mode",
                    "value": task_data.get('mode', 'Safe'),
                    "inline": True
                },
                {
                    "name": "Profile",
                    "value": task_data.get('profile', 'None'),
                    "inline": True
                }
            ],
            "timestamp": datetime.now().isoformat(),
            "footer": {
                "text": f"Task ID: {task_data.get('task_id', 'Unknown')}"
            }
        }
        
        if task_data.get('product_image'):
            embed["thumbnail"] = {"url": task_data['product_image']}
        
        self._send_embed(embed)
    
    def send_task_success(self, task_data: Dict):
        """Send notification when task succeeds"""
        if not self.enabled:
            return
        
        embed = {
            "title": "✅ Checkout Success!",
            "color": self.COLORS['success'],
            "fields": [
                {
                    "name": "Product",
                    "value": task_data.get('product_name', 'Unknown'),
                    "inline": False
                },
                {
                    "name": "Site",
                    "value": task_data.get('site', 'Unknown'),
                    "inline": True
                },
                {
                    "name": "Price",
                    "value": f"${task_data.get('product_price', 0):.2f}",
                    "inline": True
                },
                {
                    "name": "Profile",
                    "value": task_data.get('profile', 'None'),
                    "inline": True
                },
                {
                    "name": "Time",
                    "value": self._format_duration(task_data),
                    "inline": True
                }
            ],
            "timestamp": datetime.now().isoformat(),
            "footer": {
                "text": f"Task ID: {task_data.get('task_id', 'Unknown')}"
            }
        }
        
        if task_data.get('product_image'):
            embed["thumbnail"] = {"url": task_data['product_image']}
        
        self._send_embed(embed)
    
    def send_task_failed(self, task_data: Dict):
        """Send notification when task fails"""
        if not self.enabled:
            return
        
        embed = {
            "title": "❌ Task Failed",
            "color": self.COLORS['error'],
            "description": task_data.get('error', 'Unknown error'),
            "fields": [
                {
                    "name": "Site",
                    "value": task_data.get('site', 'Unknown'),
                    "inline": True
                },
                {
                    "name": "Product",
                    "value": task_data.get('product_name', 'Unknown'),
                    "inline": True
                },
                {
                    "name": "Profile",
                    "value": task_data.get('profile', 'None'),
                    "inline": True
                }
            ],
            "timestamp": datetime.now().isoformat(),
            "footer": {
                "text": f"Task ID: {task_data.get('task_id', 'Unknown')}"
            }
        }
        
        self._send_embed(embed)
    
    def send_captcha_request(self, task_data: Dict):
        """Send notification when captcha is needed"""
        if not self.enabled:
            return
        
        embed = {
            "title": "🔐 Captcha Required",
            "color": self.COLORS['captcha'],
            "description": "Task is waiting for manual captcha harvest",
            "fields": [
                {
                    "name": "Site",
                    "value": task_data.get('site', 'Unknown'),
                    "inline": True
                },
                {
                    "name": "Task ID",
                    "value": task_data.get('task_id', 'Unknown')[:8],
                    "inline": True
                }
            ],
            "timestamp": datetime.now().isoformat(),
            "footer": {
                "text": "Please harvest captcha in the Captcha Harvester panel"
            }
        }
        
        self._send_embed(embed)
    
    def send_monitor_alert(self, alert_data: Dict):
        """Send monitor/restock alert (v3.1.3 basic version)"""
        if not self.enabled:
            return
        
        embed = {
            "title": "🔔 Monitor Alert",
            "color": self.COLORS['warning'],
            "fields": [
                {
                    "name": "Product",
                    "value": alert_data.get('product_name', 'Unknown'),
                    "inline": False
                },
                {
                    "name": "Status",
                    "value": alert_data.get('status', 'In Stock'),
                    "inline": True
                },
                {
                    "name": "Price",
                    "value": f"${alert_data.get('price', 0):.2f}",
                    "inline": True
                },
                {
                    "name": "Link",
                    "value": f"[View Product]({alert_data.get('url', '#')})",
                    "inline": False
                }
            ],
            "timestamp": datetime.now().isoformat()
        }
        
        if alert_data.get('image'):
            embed["thumbnail"] = {"url": alert_data['image']}
        
        self._send_embed(embed)
    
    def send_v4_monitor_alert(self, monitor_data: Dict):
        """
        Send v4.0 enhanced monitor alert with rich data
        Includes: scalper detection, ratings, promotions, local stores
        """
        if not self.enabled:
            return
        
        # Determine embed color based on scalper status
        embed_color = self._get_scalper_color(monitor_data)
        
        # Build title with emoji based on stock status
        if monitor_data.get('in_stock'):
            title = "✅ PRODUCT IN STOCK!"
        elif monitor_data.get('is_preorder'):
            title = "⏰ PRE-ORDER AVAILABLE!"
        else:
            title = "🔔 Monitor Alert"
        
        # Build description with scalper warning
        description = self._build_scalper_description(monitor_data)
        
        embed = {
            "title": title,
            "description": description,
            "color": embed_color,
            "fields": [],
            "timestamp": datetime.now().isoformat(),
            "footer": {
                "text": f"Monitor: {monitor_data.get('monitor_id', 'Unknown')} | Site: {monitor_data.get('site', 'Unknown').upper()}"
            }
        }
        
        # Add product image (v4.0 feature)
        if monitor_data.get('image_url'):
            embed["thumbnail"] = {"url": monitor_data['image_url']}
        
        # Product name field
        embed["fields"].append({
            "name": "📦 Product",
            "value": monitor_data.get('product_name', 'Unknown'),
            "inline": False
        })
        
        # Price information
        price_value = self._format_price_field(monitor_data)
        embed["fields"].append({
            "name": "💰 Price",
            "value": price_value,
            "inline": True
        })
        
        # Stock status
        if monitor_data.get('in_stock'):
            status_value = "✅ **IN STOCK**"
        elif monitor_data.get('is_preorder'):
            status_value = "⏰ **PRE-ORDER**"
        else:
            status_value = "❌ Out of Stock"
        
        embed["fields"].append({
            "name": "📊 Status",
            "value": status_value,
            "inline": True
        })
        
        # V4.0: Rating & Reviews
        if monitor_data.get('rating') and monitor_data.get('show_rating'):
            rating_value = f"⭐ **{monitor_data['rating']:.1f}/5.0**"
            if monitor_data.get('review_count'):
                rating_value += f" ({monitor_data['review_count']} reviews)"
            
            embed["fields"].append({
                "name": "⭐ Rating",
                "value": rating_value,
                "inline": True
            })
        
        # V4.0: Promotions
        if monitor_data.get('promotions') and monitor_data.get('show_promotions'):
            promos_text = self._format_promotions(monitor_data['promotions'])
            if promos_text:
                embed["fields"].append({
                    "name": "🎁 Active Promotions",
                    "value": promos_text,
                    "inline": False
                })
        
        # V4.0: Local Stores
        if monitor_data.get('local_stores') and monitor_data.get('show_stores'):
            stores_text = self._format_local_stores(monitor_data['local_stores'])
            if stores_text:
                embed["fields"].append({
                    "name": "🏪 Local Store Availability",
                    "value": stores_text,
                    "inline": False
                })
        
        # Quick link to product
        embed["fields"].append({
            "name": "🔗 Quick Link",
            "value": f"[Open on {monitor_data.get('site', 'Site').title()}.com]({monitor_data.get('product_url', '#')})",
            "inline": False
        })
        
        self._send_embed(embed)
    
    def _get_scalper_color(self, monitor_data: Dict) -> int:
        """Determine Discord embed color based on scalper status"""
        target_price = monitor_data.get('target_price', 0)
        current_price = monitor_data.get('product_price', 0)
        
        if not target_price or target_price <= 0 or current_price <= 0:
            # No scalper detection - use default warning color
            return self.COLORS['warning']
        
        markup_percent = ((current_price - target_price) / target_price) * 100
        
        if markup_percent <= 0:
            # Great deal - green
            return self.COLORS['success']
        elif markup_percent <= 20:
            # Slight markup - orange
            return self.COLORS['warning']
        else:
            # Scalped - red
            return self.COLORS['error']
    
    def _build_scalper_description(self, monitor_data: Dict) -> str:
        """Build description with scalper warning"""
        target_price = monitor_data.get('target_price', 0)
        current_price = monitor_data.get('product_price', 0)
        
        if not target_price or target_price <= 0 or current_price <= 0:
            return "**Monitor detected a stock change!**"
        
        markup_percent = ((current_price - target_price) / target_price) * 100
        
        if markup_percent <= 0:
            return f"🟢 **GREAT DEAL!** Price is **{abs(markup_percent):.1f}% below** target price of ${target_price:.2f}"
        elif markup_percent <= 20:
            return f"🟡 **SLIGHT MARKUP** - Price is **{markup_percent:.1f}% above** target price of ${target_price:.2f}"
        else:
            return f"🔴 **WARNING: SCALPED!** Price is **{markup_percent:.1f}% above** target price of ${target_price:.2f}"
    
    def _format_price_field(self, monitor_data: Dict) -> str:
        """Format price field with regular price comparison"""
        current_price = monitor_data.get('product_price', 0)
        regular_price = monitor_data.get('product_regular_price', 0)
        
        price_text = f"**${current_price:.2f}**"
        
        # Add regular price if on sale
        if regular_price > 0 and current_price < regular_price:
            discount = ((regular_price - current_price) / regular_price) * 100
            price_text += f"\n~~${regular_price:.2f}~~ 🔥 **{discount:.0f}% OFF**"
        
        return price_text
    
    def _format_promotions(self, promotions) -> str:
        """Format promotions for Discord embed"""
        if not promotions:
            return ""
        
        # Handle string format (newline-separated)
        if isinstance(promotions, str):
            promo_list = [p.strip() for p in promotions.split('\n') if p.strip()]
        else:
            promo_list = promotions
        
        # Limit to 5 promotions
        promo_list = promo_list[:5]
        
        if not promo_list:
            return ""
        
        # Format as bullet list
        formatted = "\n".join([f"• {promo}" for promo in promo_list])
        return formatted
    
    def _format_local_stores(self, stores) -> str:
        """Format local stores for Discord embed"""
        if not stores:
            return ""
        
        # Handle string format (stores separated by double newlines)
        if isinstance(stores, str):
            store_blocks = [s.strip() for s in stores.split('\n\n') if s.strip()]
        else:
            store_blocks = stores
        
        # Limit to 3 stores
        store_blocks = store_blocks[:3]
        
        if not store_blocks:
            return ""
        
        formatted_stores = []
        for store in store_blocks:
            # Parse store info (format: "Name\nQuantity\nAddress")
            lines = store.split('\n') if isinstance(store, str) else [store]
            if lines:
                # Take first line (store name/quantity)
                formatted_stores.append(f"• {lines[0]}")
        
        return "\n".join(formatted_stores)
    
    def send_custom_message(self, message: str, color: str = 'info'):
        """Send a custom message"""
        if not self.enabled:
            return
        
        embed = {
            "description": message,
            "color": self.COLORS.get(color, self.COLORS['info']),
            "timestamp": datetime.now().isoformat()
        }
        
        self._send_embed(embed)
    
    def _send_embed(self, embed: Dict):
        """Internal method to send embed to Discord"""
        try:
            payload = {
                "username": "Autobot",
                "embeds": [embed]
            }
            
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=10
            )
            
            if response.status_code not in [200, 204]:
                print(f"Webhook error: {response.status_code} - {response.text}")
        
        except Exception as e:
            print(f"Failed to send webhook: {e}")
    
    def _format_duration(self, task_data: Dict) -> str:
        """Format task duration"""
        start = task_data.get('start_time')
        end = task_data.get('end_time')
        
        if not start or not end:
            return "Unknown"
        
        try:
            if isinstance(start, str):
                start = datetime.fromisoformat(start)
            if isinstance(end, str):
                end = datetime.fromisoformat(end)
            
            duration = (end - start).total_seconds()
            
            if duration < 60:
                return f"{duration:.1f}s"
            else:
                minutes = int(duration // 60)
                seconds = int(duration % 60)
                return f"{minutes}m {seconds}s"
        
        except Exception:
            return "Unknown"
    
    def test_webhook(self) -> bool:
        """Test if webhook URL is valid"""
        if not self.webhook_url:
            return False
        
        try:
            test_embed = {
                "title": "🤖 Autobot Webhook Test",
                "description": "Your webhook is configured correctly!",
                "color": self.COLORS['success'],
                "timestamp": datetime.now().isoformat()
            }
            
            response = requests.post(
                self.webhook_url,
                json={"username": "Autobot", "embeds": [test_embed]},
                timeout=10
            )
            
            return response.status_code in [200, 204]
        
        except Exception:
            return False


# Global webhook instance
webhook = DiscordWebhook()


# Compatibility function for simple webhook calls
def send_webhook(webhook_url: str, title: str, description: str, color: str = "#8b5cf6"):
    """
    Simple wrapper function for backward compatibility
    
    Args:
        webhook_url: Discord webhook URL
        title: Message title
        description: Message description
        color: Hex color (default purple)
    """
    if not webhook_url:
        return False
    
    # Create temporary webhook instance
    temp_webhook = DiscordWebhook(webhook_url)
    
    # Determine color type from hex
    color_map = {
        "#10b981": "success",  # Green
        "#ef4444": "error",     # Red
        "#8b5cf6": "info",      # Purple
        "#f59e0b": "warning",   # Orange
    }
    
    color_type = color_map.get(color, "info")
    
    # Send as custom message
    temp_webhook.send_custom_message(f"**{title}**\n{description}", color_type)
    return True
