"""
Site Management Panel for Autobot v4.4
Dynamic site addition and management without coding!

Features:
- View all supported sites
- Enable/disable sites
- Add new sites via wizard
- Test site patterns
- Auto-generate virtual modules
"""

import customtkinter as ctk
from tkinter import messagebox, simpledialog
import json
import threading
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging

from core.smart_api_analyzer import SmartAPIAnalyzer
from core.api_pattern_matcher import APIPatternMatcher


class SiteManagementPanel(ctk.CTkFrame):
    """Panel for managing supported sites dynamically"""
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        
        self.logger = logging.getLogger(__name__)
        self.sites_file = Path("config/sites.json")
        
        # API analyzer for new sites
        self.api_analyzer = SmartAPIAnalyzer()
        
        # Sites data
        self.sites: Dict = {}
        
        # Build UI
        self._build_ui()
        
        # Load sites
        self._load_sites()
    
    def _build_ui(self):
        """Build the site management UI"""
        # Main title
        title = ctk.CTkLabel(
            self,
            text="🌐 Site Management",
            font=("Arial", 20, "bold")
        )
        title.pack(pady=10)
        
        # Create tabview
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Add tabs
        self.tabview.add("Supported Sites")
        self.tabview.add("Add New Site")
        self.tabview.add("Site Details")
        
        # Build each tab
        self._build_supported_sites_tab()
        self._build_add_site_tab()
        self._build_details_tab()
        
        # Bottom buttons
        button_frame = ctk.CTkFrame(self)
        button_frame.pack(fill="x", padx=10, pady=10)
        
        refresh_btn = ctk.CTkButton(
            button_frame,
            text="🔄 Refresh Sites",
            command=self._refresh_sites,
            fg_color="blue",
            hover_color="darkblue"
        )
        refresh_btn.pack(side="left", padx=5)
        
        export_btn = ctk.CTkButton(
            button_frame,
            text="📥 Export Config",
            command=self._export_config,
            fg_color="gray",
            hover_color="darkgray"
        )
        export_btn.pack(side="left", padx=5)
    
    def _build_supported_sites_tab(self):
        """Build the supported sites list tab"""
        tab = self.tabview.tab("Supported Sites")
        
        # Info
        info = ctk.CTkLabel(
            tab,
            text="Manage supported sites. Enable/disable or remove sites.",
            font=("Arial", 11),
            text_color="gray"
        )
        info.pack(pady=5)
        
        # Scrollable frame for sites
        self.sites_scroll = ctk.CTkScrollableFrame(tab, height=400)
        self.sites_scroll.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Sites will be populated by _refresh_sites()
    
    def _build_add_site_tab(self):
        """Build the Add New Site wizard tab"""
        tab = self.tabview.tab("Add New Site")
        
        # Scrollable frame
        scroll = ctk.CTkScrollableFrame(tab)
        scroll.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Title
        title = ctk.CTkLabel(
            scroll,
            text="✨ Add New Site Wizard",
            font=("Arial", 16, "bold")
        )
        title.pack(pady=10)
        
        # Instructions
        instructions = ctk.CTkLabel(
            scroll,
            text=(
                "Add unlimited sites without coding!\n\n"
                "How it works:\n"
                "1. Enter a product URL from the site\n"
                "2. Bot analyzes API calls automatically\n"
                "3. Bot finds product data patterns\n"
                "4. Bot generates site module\n"
                "5. Site is added to dropdown!\n\n"
                "Example URLs:\n"
                "• https://www.nike.com/t/product-name/ABC123\n"
                "• https://shop.example.com/products/item-123\n"
                "• https://store.com/collections/all/products/shoe"
            ),
            font=("Arial", 11),
            justify="left"
        )
        instructions.pack(pady=10, padx=20)
        
        # Site name
        name_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        name_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(
            name_frame,
            text="Site Name:",
            font=("Arial", 12, "bold")
        ).pack(anchor="w")
        
        self.site_name_entry = ctk.CTkEntry(
            name_frame,
            placeholder_text="e.g., 'Nike', 'Shopify Store', 'Custom Shop'"
        )
        self.site_name_entry.pack(fill="x", pady=5)
        
        # Product URL
        url_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        url_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(
            url_frame,
            text="Product URL:",
            font=("Arial", 12, "bold")
        ).pack(anchor="w")
        
        self.product_url_entry = ctk.CTkEntry(
            url_frame,
            placeholder_text="https://example.com/products/item-123"
        )
        self.product_url_entry.pack(fill="x", pady=5)
        
        # Site type
        type_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        type_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(
            type_frame,
            text="Site Type (optional):",
            font=("Arial", 12, "bold")
        ).pack(anchor="w")
        
        self.site_type_var = ctk.StringVar(value="auto")
        type_options = ["auto", "shopify", "woocommerce", "custom"]
        
        type_menu = ctk.CTkOptionMenu(
            type_frame,
            variable=self.site_type_var,
            values=type_options
        )
        type_menu.pack(fill="x", pady=5)
        
        # Analyze button
        self.analyze_btn = ctk.CTkButton(
            scroll,
            text="🔍 Analyze Site",
            command=self._analyze_new_site,
            fg_color="green",
            hover_color="darkgreen",
            height=40,
            font=("Arial", 14, "bold")
        )
        self.analyze_btn.pack(pady=20)
        
        # Results frame (hidden initially)
        self.results_frame = ctk.CTkFrame(scroll)
        self.results_frame.pack(fill="x", padx=20, pady=10)
        self.results_frame.pack_forget()  # Hide initially
        
        # Results content
        self.results_label = ctk.CTkLabel(
            self.results_frame,
            text="",
            font=("Arial", 11),
            justify="left"
        )
        self.results_label.pack(pady=10)
        
        # Add site button (shown after successful analysis)
        self.add_site_btn = ctk.CTkButton(
            self.results_frame,
            text="✅ Add This Site",
            command=self._add_analyzed_site,
            fg_color="green",
            hover_color="darkgreen"
        )
        self.add_site_btn.pack(pady=10)
        
        # Progress label
        self.progress_label = ctk.CTkLabel(
            scroll,
            text="",
            font=("Arial", 10),
            text_color="gray"
        )
        self.progress_label.pack(pady=5)
    
    def _build_details_tab(self):
        """Build the site details viewer tab"""
        tab = self.tabview.tab("Site Details")
        
        # Info
        info = ctk.CTkLabel(
            tab,
            text="View detailed information about a site's patterns",
            font=("Arial", 11),
            text_color="gray"
        )
        info.pack(pady=5)
        
        # Site selector
        selector_frame = ctk.CTkFrame(tab)
        selector_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(
            selector_frame,
            text="Select Site:"
        ).pack(side="left", padx=5)
        
        self.detail_site_var = ctk.StringVar(value="Select a site...")
        self.detail_site_menu = ctk.CTkOptionMenu(
            selector_frame,
            variable=self.detail_site_var,
            values=["No sites available"],
            command=self._show_site_details
        )
        self.detail_site_menu.pack(side="left", fill="x", expand=True, padx=5)
        
        # Details display
        self.details_text = ctk.CTkTextbox(tab, height=400)
        self.details_text.pack(fill="both", expand=True, padx=10, pady=10)
    
    def _load_sites(self):
        """Load sites from config file"""
        try:
            if not self.sites_file.exists():
                # Create default sites
                self.sites = self._get_default_sites()
                self._save_sites()
            else:
                with open(self.sites_file, 'r') as f:
                    self.sites = json.load(f)
            
            self.logger.info(f"Loaded {len(self.sites)} sites")
            self._refresh_sites()
            
        except Exception as e:
            self.logger.error(f"Failed to load sites: {e}")
            self.sites = self._get_default_sites()
    
    def _get_default_sites(self) -> Dict:
        """Get default site configurations"""
        return {
            "Nike SNKRS": {
                "enabled": True,
                "type": "custom",
                "base_url": "https://www.nike.com",
                "api_patterns": {
                    "product_api": "/api/products/{id}",
                    "stock_api": "/api/stock/{id}",
                    "cart_api": "/api/cart"
                },
                "patterns": {},
                "added_date": "2025-11-13",
                "user_added": False
            },
            "Shopify (Generic)": {
                "enabled": True,
                "type": "shopify",
                "base_url": "https://shop.example.com",
                "api_patterns": {
                    "product_api": "/products/{handle}.json",
                    "cart_api": "/cart.json"
                },
                "patterns": {},
                "added_date": "2025-11-13",
                "user_added": False
            }
        }
    
    def _save_sites(self):
        """Save sites to config file"""
        try:
            self.sites_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.sites_file, 'w') as f:
                json.dump(self.sites, f, indent=2)
            self.logger.info(f"Saved {len(self.sites)} sites")
        except Exception as e:
            self.logger.error(f"Failed to save sites: {e}")
    
    def _refresh_sites(self):
        """Refresh the supported sites display"""
        # Clear existing widgets
        for widget in self.sites_scroll.winfo_children():
            widget.destroy()
        
        if not self.sites:
            no_sites = ctk.CTkLabel(
                self.sites_scroll,
                text="No sites configured. Add a site using the wizard!",
                font=("Arial", 12),
                text_color="gray"
            )
            no_sites.pack(pady=20)
            return
        
        # Display each site
        for site_name, site_data in self.sites.items():
            self._create_site_card(site_name, site_data)
        
        # Update details dropdown
        site_names = list(self.sites.keys())
        if site_names:
            self.detail_site_menu.configure(values=site_names)
            if self.detail_site_var.get() == "Select a site...":
                self.detail_site_var.set(site_names[0])
    
    def _create_site_card(self, site_name: str, site_data: Dict):
        """Create a card for a single site"""
        card = ctk.CTkFrame(self.sites_scroll)
        card.pack(fill="x", padx=5, pady=5)
        
        # Left side - site info
        info_frame = ctk.CTkFrame(card, fg_color="transparent")
        info_frame.pack(side="left", fill="x", expand=True, padx=10, pady=10)
        
        # Site name
        name_label = ctk.CTkLabel(
            info_frame,
            text=f"🌐 {site_name}",
            font=("Arial", 14, "bold")
        )
        name_label.pack(anchor="w")
        
        # Site details
        site_type = site_data.get("type", "unknown")
        user_added = site_data.get("user_added", False)
        added_tag = " (User Added)" if user_added else " (Built-in)"
        
        details = ctk.CTkLabel(
            info_frame,
            text=f"Type: {site_type}{added_tag}",
            font=("Arial", 10),
            text_color="gray"
        )
        details.pack(anchor="w")
        
        # Right side - controls
        controls_frame = ctk.CTkFrame(card, fg_color="transparent")
        controls_frame.pack(side="right", padx=10, pady=10)
        
        # Enable/Disable switch
        enabled_var = ctk.BooleanVar(value=site_data.get("enabled", True))
        
        def toggle_site():
            site_data["enabled"] = enabled_var.get()
            self._save_sites()
            status = "enabled" if enabled_var.get() else "disabled"
            self.logger.info(f"Site '{site_name}' {status}")
        
        toggle = ctk.CTkSwitch(
            controls_frame,
            text="Enabled",
            variable=enabled_var,
            command=toggle_site
        )
        toggle.pack(pady=2)
        
        # Test button
        test_btn = ctk.CTkButton(
            controls_frame,
            text="🧪 Test",
            command=lambda: self._test_site(site_name),
            width=80,
            height=28
        )
        test_btn.pack(pady=2)
        
        # Remove button (only for user-added sites)
        if user_added:
            remove_btn = ctk.CTkButton(
                controls_frame,
                text="🗑️ Remove",
                command=lambda: self._remove_site(site_name),
                width=80,
                height=28,
                fg_color="red",
                hover_color="darkred"
            )
            remove_btn.pack(pady=2)
    
    def _analyze_new_site(self):
        """Analyze a new site URL"""
        site_name = self.site_name_entry.get().strip()
        product_url = self.product_url_entry.get().strip()
        
        if not site_name:
            messagebox.showerror("Error", "Please enter a site name")
            return
        
        if not product_url:
            messagebox.showerror("Error", "Please enter a product URL")
            return
        
        if site_name in self.sites:
            if not messagebox.askyesno("Site Exists", f"Site '{site_name}' already exists. Overwrite?"):
                return
        
        # Disable button during analysis
        self.analyze_btn.configure(state="disabled", text="⏳ Analyzing...")
        self.progress_label.configure(text="Loading page and intercepting API calls...")
        self.results_frame.pack_forget()
        
        # Run analysis in thread
        def analyze():
            try:
                self.progress_label.configure(text="Analyzing API patterns...")
                
                # Use Phase 1C API analyzer
                patterns = self.api_analyzer.analyze_page(product_url)
                
                if not patterns:
                    self.after(0, lambda: self._show_analysis_error("No API patterns found"))
                    return
                
                # Store results for adding
                self.pending_site = {
                    "name": site_name,
                    "url": product_url,
                    "type": self.site_type_var.get(),
                    "patterns": patterns
                }
                
                # Show results
                self.after(0, lambda: self._show_analysis_results(patterns))
                
            except Exception as e:
                self.after(0, lambda: self._show_analysis_error(str(e)))
            finally:
                self.after(0, lambda: self.analyze_btn.configure(
                    state="normal",
                    text="🔍 Analyze Site"
                ))
                self.after(0, lambda: self.progress_label.configure(text=""))
        
        thread = threading.Thread(target=analyze, daemon=True)
        thread.start()
    
    def _show_analysis_results(self, patterns: Dict):
        """Show analysis results"""
        # Format results
        result_text = "✅ Analysis Complete!\n\n"
        result_text += f"Found {len(patterns)} API patterns:\n\n"
        
        for i, (url, data) in enumerate(patterns.items(), 1):
            result_text += f"{i}. {url}\n"
            if 'product_name' in data:
                result_text += f"   • Product: {data['product_name']}\n"
            if 'price' in data:
                result_text += f"   • Price: {data['price']}\n"
            if 'in_stock' in data:
                result_text += f"   • Stock: {data['in_stock']}\n"
            result_text += "\n"
        
        result_text += "Ready to add this site!"
        
        self.results_label.configure(text=result_text)
        self.results_frame.pack(fill="x", padx=20, pady=10)
        
        messagebox.showinfo(
            "Success",
            f"Successfully analyzed site!\n\nFound {len(patterns)} API patterns.\n\nClick 'Add This Site' to add it."
        )
    
    def _show_analysis_error(self, error: str):
        """Show analysis error"""
        self.progress_label.configure(text="")
        messagebox.showerror(
            "Analysis Failed",
            f"Failed to analyze site:\n\n{error}\n\nTips:\n"
            "• Make sure the URL is a direct product page\n"
            "• Check that the site uses APIs (not server-rendered)\n"
            "• Try a different product URL"
        )
    
    def _add_analyzed_site(self):
        """Add the analyzed site to configuration"""
        if not hasattr(self, 'pending_site'):
            messagebox.showerror("Error", "No analyzed site to add")
            return
        
        site = self.pending_site
        
        # Create site config
        self.sites[site['name']] = {
            "enabled": True,
            "type": site['type'],
            "base_url": site['url'].split('/products')[0] if '/products' in site['url'] else site['url'].split('/t/')[0],
            "patterns": site['patterns'],
            "added_date": "2025-11-13",
            "user_added": True
        }
        
        # Save
        self._save_sites()
        
        # Refresh display
        self._refresh_sites()
        
        # Clear form
        self.site_name_entry.delete(0, 'end')
        self.product_url_entry.delete(0, 'end')
        self.results_frame.pack_forget()
        
        # Success message
        messagebox.showinfo(
            "Site Added!",
            f"✅ '{site['name']}' has been added!\n\n"
            "The site is now available in the monitor dropdown.\n"
            "You can start monitoring products from this site immediately!"
        )
        
        self.logger.info(f"Added new site: {site['name']}")
        
        # Switch to supported sites tab
        self.tabview.set("Supported Sites")
    
    def _test_site(self, site_name: str):
        """Test a site's configuration"""
        messagebox.showinfo(
            "Test Site",
            f"Testing {site_name}...\n\n"
            "This feature will:\n"
            "• Verify API patterns work\n"
            "• Check data extraction\n"
            "• Validate stock checking\n\n"
            "(Not yet implemented - coming soon!)"
        )
    
    def _remove_site(self, site_name: str):
        """Remove a user-added site"""
        if messagebox.askyesno(
            "Confirm Removal",
            f"Remove site '{site_name}'?\n\nThis cannot be undone."
        ):
            del self.sites[site_name]
            self._save_sites()
            self._refresh_sites()
            messagebox.showinfo("Removed", f"Site '{site_name}' removed successfully")
            self.logger.info(f"Removed site: {site_name}")
    
    def _show_site_details(self, site_name: str):
        """Show detailed information about a site"""
        if site_name not in self.sites:
            return
        
        site = self.sites[site_name]
        
        # Format details
        details = f"Site: {site_name}\n"
        details += "=" * 50 + "\n\n"
        details += f"Type: {site.get('type', 'unknown')}\n"
        details += f"Base URL: {site.get('base_url', 'N/A')}\n"
        details += f"Enabled: {'Yes' if site.get('enabled') else 'No'}\n"
        details += f"User Added: {'Yes' if site.get('user_added') else 'No'}\n"
        details += f"Added Date: {site.get('added_date', 'Unknown')}\n\n"
        
        details += "API Patterns:\n"
        details += "-" * 50 + "\n"
        
        patterns = site.get('patterns', {})
        if patterns:
            for url, data in patterns.items():
                details += f"\nURL: {url}\n"
                for key, value in data.items():
                    details += f"  {key}: {value}\n"
        else:
            details += "No patterns configured\n"
        
        # Display
        self.details_text.delete("1.0", "end")
        self.details_text.insert("1.0", details)
    
    def _export_config(self):
        """Export site configuration"""
        try:
            export_path = Path("config/sites_export.json")
            with open(export_path, 'w') as f:
                json.dump(self.sites, f, indent=2)
            
            messagebox.showinfo(
                "Exported",
                f"Site configuration exported to:\n{export_path}"
            )
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export:\n{str(e)}")
    
    def get_enabled_sites(self) -> List[str]:
        """Get list of enabled site names"""
        return [name for name, data in self.sites.items() if data.get("enabled", True)]
    
    def get_site_config(self, site_name: str) -> Optional[Dict]:
        """Get configuration for a specific site"""
        return self.sites.get(site_name)


if __name__ == "__main__":
    # Test the panel
    import sys
    
    logging.basicConfig(level=logging.INFO)
    
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    
    app = ctk.CTk()
    app.title("Site Management Test")
    app.geometry("900x700")
    
    panel = SiteManagementPanel(app)
    panel.pack(fill="both", expand=True)
    
    app.mainloop()
