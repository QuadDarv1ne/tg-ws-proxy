#!/usr/bin/env python3
"""
Build script for TG WS Proxy - Mobile applications (Android/iOS).

Uses Capacitor to build mobile apps from the web dashboard.

Author: Dupley Maxim Igorevich
© 2026 Dupley Maxim Igorevich. All rights reserved.

Requirements:
    - Node.js 18+
    - npm or yarn
    - For Android: Android Studio with SDK
    - For iOS: Xcode (macOS only)

Usage:
    python build_mobile.py [platform]
    
Platforms:
    - android: Build Android APK
    - ios: Build iOS app (macOS only)
    - all: Build for both platforms
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

# Project root
PROJECT_ROOT = Path(__file__).parent
MOBILE_DIR = PROJECT_ROOT / "mobile-app"
WWW_DIR = MOBILE_DIR / "www"
PROXY_STATIC = PROJECT_ROOT / "proxy" / "static"

# Node executable
NODE = shutil.which("node") or "node"
NPM = shutil.which("npm") or "npm"


def check_prerequisites():
    """Check if required tools are installed."""
    print("🔍 Checking prerequisites...")
    
    # Check Node.js
    try:
        result = subprocess.run([NODE, "--version"], capture_output=True, text=True, check=True)
        print(f"✅ Node.js: {result.stdout.strip()}")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ Node.js not found. Please install Node.js 18+ from https://nodejs.org/")
        return False
    
    # Check npm
    try:
        result = subprocess.run([NPM, "--version"], capture_output=True, text=True, check=True)
        print(f"✅ npm: {result.stdout.strip()}")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ npm not found. Please install npm")
        return False
    
    return True


def copy_static_files():
    """Copy static files (icons) to mobile www directory."""
    print("📋 Copying static files...")
    
    WWW_DIR.mkdir(parents=True, exist_ok=True)
    
    if PROXY_STATIC.exists():
        for file in PROXY_STATIC.glob("*"):
            dest = WWW_DIR / file.name
            shutil.copy2(file, dest)
            print(f"  ✓ Copied {file.name}")
    else:
        print("⚠️  Static directory not found, icons may be missing")


def install_deps():
    """Install npm dependencies."""
    print("📦 Installing npm dependencies...")
    subprocess.check_call([NPM, "install"], cwd=MOBILE_DIR)


def sync_capacitor():
    """Sync web assets with Capacitor."""
    print("🔄 Syncing with Capacitor...")
    subprocess.check_call([NPM, "run", "sync"], cwd=MOBILE_DIR)


def build_android():
    """Build Android APK."""
    print("🤖 Building Android APK...")
    
    android_dir = MOBILE_DIR / "android"
    if not android_dir.exists():
        print("❌ Android directory not found. Run 'npx cap add android' first")
        return False
    
    try:
        # Build debug APK (for release, use assembleRelease with signing)
        gradle = "gradlew.bat" if os.name == "nt" else "./gradlew"
        subprocess.check_call([str(android_dir / gradle), "assembleDebug"], cwd=android_dir)
        
        apk_path = android_dir / "app" / "build" / "outputs" / "apk" / "debug" / "app-debug.apk"
        if apk_path.exists():
            # Copy to dist directory
            dist_dir = PROJECT_ROOT / "dist"
            dist_dir.mkdir(exist_ok=True)
            output_path = dist_dir / "TgWsProxy-Android.apk"
            shutil.copy2(apk_path, output_path)
            print(f"✅ Android APK built: {output_path}")
            return True
        else:
            print("❌ APK not found after build")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"❌ Android build failed: {e}")
        return False


def build_ios():
    """Build iOS app."""
    print("🍎 Building iOS app...")
    
    if sys.platform != "darwin":
        print("❌ iOS build is only supported on macOS")
        return False
    
    ios_dir = MOBILE_DIR / "ios"
    if not ios_dir.exists():
        print("❌ iOS directory not found. Run 'npx cap add ios' first")
        return False
    
    try:
        # Open Xcode project for manual build (automated build requires signing setup)
        print("📱 Opening Xcode project for manual build...")
        workspace = ios_dir / "App.xcworkspace"
        if workspace.exists():
            subprocess.run(["open", str(workspace)], check=True)
            print("✅ Xcode opened. Build the app using Product → Archive for distribution")
            return True
        else:
            print("❌ Xcode workspace not found")
            return False
            
    except Exception as e:
        print(f"❌ iOS build failed: {e}")
        return False


def add_capacitor_platform(platform: str):
    """Add a Capacitor platform."""
    print(f"➕ Adding {platform} platform...")
    try:
        subprocess.check_call([NPM, "run", "sync"], cwd=MOBILE_DIR)
        return True
    except subprocess.CalledProcessError:
        # Try adding the platform
        try:
            subprocess.check_call([NPM, "exec", "--", "cap", "add", platform], cwd=MOBILE_DIR)
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to add {platform} platform: {e}")
            return False


def main():
    """Main build function."""
    platform = sys.argv[1] if len(sys.argv) > 1 else "all"
    
    print("=" * 60)
    print("TG WS Proxy - Mobile Build Script")
    print("=" * 60)
    print(f"Target: {platform.upper()}")
    print("=" * 60)
    
    # Check prerequisites
    if not check_prerequisites():
        return 1
    
    # Copy static files
    copy_static_files()
    
    # Install dependencies
    install_deps()
    
    # Determine platforms to build
    if platform == "all":
        platforms = ["android", "ios"]
    else:
        platforms = [platform]
    
    success = False
    
    for plat in platforms:
        print(f"\n{'='*60}")
        print(f"Building for {plat.upper()}")
        print("="*60)
        
        if plat == "android":
            if build_android():
                success = True
                
        elif plat == "ios":
            if build_ios():
                success = True
    
    if success:
        print("\n" + "=" * 60)
        print("✅ Build completed!")
        print("📁 Distribution: dist/")
        print("=" * 60)
        return 0
    else:
        print("\n" + "=" * 60)
        print("❌ Build failed or no platforms built")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
