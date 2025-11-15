#!/usr/bin/env python3
"""
Autobot System Diagnostic Script
Checks all critical components and reports status
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def check_imports():
    """Check if all critical modules can be imported"""
    print("\n" + "="*60)
    print("🔍 CHECKING IMPORTS")
    print("="*60)
    
    modules = [
        ('core.aggressive_checkout', 'AggressiveCheckout'),
        ('core.smart_api_analyzer', 'SmartAPIAnalyzer'),
        ('sites.target', 'TargetSite'),
        ('ui.dashboard', 'AutobotApp'),
        ('core.settings_manager', 'SettingsManager'),
    ]
    
    results = []
    for module_name, class_name in modules:
        try:
            module = __import__(module_name, fromlist=[class_name])
            cls = getattr(module, class_name)
            print(f"✅ {module_name}.{class_name}")
            results.append(True)
        except Exception as e:
            print(f"❌ {module_name}.{class_name}")
            print(f"   Error: {e}")
            results.append(False)
    
    return all(results)

def check_files():
    """Check if all critical files exist"""
    print("\n" + "="*60)
    print("📁 CHECKING FILES")
    print("="*60)
    
    critical_files = [
        'main.py',
        'core/aggressive_checkout.py',
        'core/smart_api_analyzer.py',
        'sites/target.py',
        'ui/dashboard.py',
        'ui/phase0_integration.py',
        'requirements.txt',
    ]
    
    results = []
    for file_path in critical_files:
        full_path = project_root / file_path
        exists = full_path.exists()
        size = full_path.stat().st_size if exists else 0
        
        if exists and size > 0:
            print(f"✅ {file_path} ({size:,} bytes)")
            results.append(True)
        else:
            print(f"❌ {file_path} {'(missing)' if not exists else '(empty)'}")
            results.append(False)
    
    return all(results)

def check_features():
    """Check if key features are implemented"""
    print("\n" + "="*60)
    print("🔧 CHECKING FEATURES")
    print("="*60)
    
    checks = []
    
    # Check aggressive checkout has high retry counts
    try:
        from core.aggressive_checkout import AggressiveCheckout
        checkout = AggressiveCheckout()
        
        if checkout.max_cart_attempts >= 100:
            print(f"✅ High retry count: {checkout.max_cart_attempts} cart attempts")
            checks.append(True)
        else:
            print(f"⚠️ Low retry count: {checkout.max_cart_attempts} cart attempts (expected >= 100)")
            checks.append(False)
        
        # Check for duplicate prevention
        if hasattr(checkout, 'verify_not_duplicate_purchase'):
            print("✅ Duplicate prevention: Available")
            checks.append(True)
        else:
            print("❌ Duplicate prevention: Missing")
            checks.append(False)
        
        # Check for error handling
        if hasattr(checkout, 'handle_high_demand_errors'):
            print("✅ Error handling: Available")
            checks.append(True)
        else:
            print("❌ Error handling: Missing")
            checks.append(False)
            
    except Exception as e:
        print(f"❌ Could not check aggressive checkout: {e}")
        checks.append(False)
    
    # Check API analyzer
    try:
        from core.smart_api_analyzer import SmartAPIAnalyzer
        analyzer = SmartAPIAnalyzer()
        pattern_count = len(analyzer.learned_patterns) if hasattr(analyzer, 'learned_patterns') else 0
        print(f"✅ API Analyzer: Available (learned_patterns: {pattern_count})")
        checks.append(True)
    except Exception as e:
        print(f"❌ API Analyzer: {e}")
        checks.append(False)
    
    # Check Target site
    try:
        from sites.target import TargetSite
        # Check for aggressive methods
        has_aggressive = hasattr(TargetSite, 'add_to_cart')
        has_error_handler = 'handle_target_errors' in open('sites/target.py').read()
        
        if has_aggressive and has_error_handler:
            print("✅ Target aggressive checkout: Available")
            checks.append(True)
        else:
            print(f"⚠️ Target methods: add_to_cart={has_aggressive}, error_handler={has_error_handler}")
            checks.append(False)
    except Exception as e:
        print(f"❌ Target site check: {e}")
        checks.append(False)
    
    return all(checks)

def check_configuration():
    """Check configuration files"""
    print("\n" + "="*60)
    print("⚙️ CHECKING CONFIGURATION")
    print("="*60)
    
    # Check config.json
    config_path = project_root / 'config' / 'config.json'
    if config_path.exists():
        print(f"✅ config.json exists ({config_path.stat().st_size} bytes)")
        
        try:
            import json
            with open(config_path) as f:
                config = json.load(f)
            print(f"   Settings: {len(config)} keys")
            return True
        except Exception as e:
            print(f"⚠️ Could not parse config.json: {e}")
            return False
    else:
        print("⚠️ config.json not found (will be created on first run)")
        return True  # This is OK, will be created

def check_version():
    """Check version information"""
    print("\n" + "="*60)
    print("📦 VERSION INFO")
    print("="*60)
    
    # Try to find version in files
    version_files = [
        'COMPLETION_SUMMARY.md',
        'MASTER_TRACKING_CHECKLIST.md',
        'AUTOBOT_v4.6_FIX_SUMMARY.md',
    ]
    
    for vf in version_files:
        path = project_root / vf
        if path.exists():
            with open(path) as f:
                content = f.read()
                # Look for version strings
                if 'v4.9' in content:
                    print(f"✅ Found v4.9 reference in {vf}")
                elif 'v4.6' in content:
                    print(f"ℹ️ Found v4.6 reference in {vf}")
                elif 'v4.' in content:
                    import re
                    versions = re.findall(r'v4\.\d+', content)
                    if versions:
                        print(f"ℹ️ Found versions in {vf}: {', '.join(set(versions))}")

def main():
    """Run all diagnostic checks"""
    print("\n")
    print("=" * 60)
    print("🤖 AUTOBOT SYSTEM DIAGNOSTIC")
    print("=" * 60)
    print(f"Python: {sys.version}")
    print(f"Working Directory: {os.getcwd()}")
    print(f"Project Root: {project_root}")
    
    # Run checks
    import_check = check_imports()
    file_check = check_files()
    feature_check = check_features()
    config_check = check_configuration()
    
    # Version info (informational only)
    check_version()
    
    # Summary
    print("\n" + "="*60)
    print("📊 DIAGNOSTIC SUMMARY")
    print("="*60)
    
    all_passed = import_check and file_check and feature_check and config_check
    
    print(f"{'✅' if import_check else '❌'} Imports: {'PASS' if import_check else 'FAIL'}")
    print(f"{'✅' if file_check else '❌'} Files: {'PASS' if file_check else 'FAIL'}")
    print(f"{'✅' if feature_check else '❌'} Features: {'PASS' if feature_check else 'FAIL'}")
    print(f"{'✅' if config_check else '❌'} Configuration: {'PASS' if config_check else 'FAIL'}")
    
    print("\n" + "="*60)
    if all_passed:
        print("🎉 ALL CHECKS PASSED - SYSTEM READY!")
        print("="*60)
        print("\nTo start Autobot:")
        print("  python3 main.py")
        return 0
    else:
        print("⚠️ SOME CHECKS FAILED - SEE DETAILS ABOVE")
        print("="*60)
        print("\nReview the errors above and fix any issues.")
        print("Then run this diagnostic again.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
