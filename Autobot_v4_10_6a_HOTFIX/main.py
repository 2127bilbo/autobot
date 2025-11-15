"""
Autobot - Retail Automation Bot
Main application entry point
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def main():
    """Main application entry point"""
    try:
        print("🤖 Starting Autobot...")
        print("=" * 50)
        
        # Check if UI module exists
        try:
            from ui.dashboard import AutobotApp
        except ImportError as e:
            print(f"❌ Error importing UI: {e}")
            print("\n📦 Please ensure all dependencies are installed:")
            print("   py -m pip install -r requirements.txt")
            print("   py -m playwright install chromium")
            return 1
        
        # Initialize and run application
        print("✅ Initializing application...")
        app = AutobotApp()
        
        # ✨ PHASE 0: Add right-click menus, live settings, image display
        try:
            from ui.phase0_integration import integrate_phase0
            integrate_phase0(app)
            print("✅ Phase 0 features enabled!")
            print("   - Right-click context menus")
            print("   - Live settings (no restart needed)")
            print("   - Product image display")
        except Exception as e:
            print(f"⚠️ Phase 0 features unavailable: {e}")
            print("   (App will work without them)")
        
        print("✅ Autobot started successfully!")
        print("=" * 50)
        
        app.mainloop()
        
    except KeyboardInterrupt:
        print("\n\n👋 Autobot shutting down...")
        return 0
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
