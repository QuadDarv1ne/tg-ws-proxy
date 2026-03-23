#!/usr/bin/env python3
"""
Quick Build Script for TG WS Proxy - All Platforms.

Builds portable versions for:
- Windows (.exe + .zip)
- Linux (binary + .tar.gz)
- macOS (.app + .tar.gz)
- Mobile (APK/IPA placeholders)

Author: Dupley Maxim Igorevich
© 2026 Dupley Maxim Igorevich. All rights reserved.

Usage:
    python quick_build.py [platform]

Platforms:
    - windows: Build for Windows
    - linux: Build for Linux
    - macos: Build for macOS
    - mobile: Build mobile apps
    - all: Build all platforms
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from datetime import datetime

# Project root
PROJECT_ROOT = Path(__file__).parent
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_LOG = DIST_DIR / "build_log.txt"

# Python executable
PYTHON = sys.executable


def log(message: str) -> None:
    """Log message to console and file."""
    print(message)
    with open(BUILD_LOG, "a", encoding="utf-8") as f:
        f.write(message + "\n")


def clean_build_dirs() -> None:
    """Clean previous build artifacts."""
    log("🧹 Cleaning build directories...")
    for dir_path in [PROJECT_ROOT / "build", DIST_DIR]:
        if dir_path.exists():
            # Keep dist folder, just clean old builds
            if dir_path == DIST_DIR:
                for item in dir_path.iterdir():
                    if item.is_file():
                        item.unlink()
            else:
                shutil.rmtree(dir_path)


def get_version() -> str:
    """Get current version from pyproject.toml."""
    version = "2.59.0"
    try:
        pyproject = PROJECT_ROOT / "pyproject.toml"
        if pyproject.exists():
            content = pyproject.read_text(encoding="utf-8")
            for line in content.splitlines():
                if line.startswith("version ="):
                    version = line.split("=")[1].strip().strip('"')
                    break
    except Exception:
        pass
    return version


def build_windows() -> bool:
    """Build for Windows."""
    log("\n" + "=" * 60)
    log("Building for WINDOWS")
    log("=" * 60)

    try:
        # Run PyInstaller
        subprocess.check_call([
            PYTHON, "-m", "PyInstaller",
            "--clean",
            "--distpath", str(DIST_DIR),
            "--workpath", str(PROJECT_ROOT / "build" / "windows"),
            str(PROJECT_ROOT / "packaging" / "windows.spec")
        ])

        # Create archive
        exe_path = DIST_DIR / "TgWsProxy.exe"
        if exe_path.exists():
            import zipfile
            archive_path = DIST_DIR / f"TgWsProxy-Windows.zip"
            with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                zf.write(exe_path, "TgWsProxy.exe")
                readme = PROJECT_ROOT / "README.md"
                if readme.exists():
                    zf.write(readme, "README.md")

            log(f"✅ Windows build complete: {exe_path}")
            log(f"📦 Archive created: {archive_path}")
            return True

    except Exception as e:
        log(f"❌ Windows build failed: {e}")
        return False

    return False


def build_linux() -> bool:
    """Build for Linux."""
    log("\n" + "=" * 60)
    log("Building for LINUX")
    log("=" * 60)

    if sys.platform != "linux":
        log("⚠️  Linux build can only be done on Linux")
        return False

    try:
        subprocess.check_call([
            PYTHON, "-m", "PyInstaller",
            "--clean",
            "--distpath", str(DIST_DIR),
            "--workpath", str(PROJECT_ROOT / "build" / "linux"),
            str(PROJECT_ROOT / "packaging" / "linux.spec")
        ])

        exe_path = DIST_DIR / "TgWsProxy"
        if exe_path.exists():
            import tarfile
            archive_path = DIST_DIR / f"TgWsProxy-Linux.tar.gz"
            with tarfile.open(archive_path, "w:gz") as tar:
                tar.add(exe_path, arcname="TgWsProxy")
                readme = PROJECT_ROOT / "README.md"
                if readme.exists():
                    tar.add(readme, arcname="README.md")

            log(f"✅ Linux build complete: {exe_path}")
            log(f"📦 Archive created: {archive_path}")
            return True

    except Exception as e:
        log(f"❌ Linux build failed: {e}")
        return False

    return False


def build_macos() -> bool:
    """Build for macOS."""
    log("\n" + "=" * 60)
    log("Building for MACOS")
    log("=" * 60)

    if sys.platform != "darwin":
        log("⚠️  macOS build can only be done on macOS")
        return False

    try:
        subprocess.check_call([
            PYTHON, "-m", "PyInstaller",
            "--clean",
            "--distpath", str(DIST_DIR),
            "--workpath", str(PROJECT_ROOT / "build" / "macos"),
            str(PROJECT_ROOT / "packaging" / "macos.spec")
        ])

        app_path = DIST_DIR / "TgWsProxy.app"
        if app_path.exists():
            import tarfile
            archive_path = DIST_DIR / f"TgWsProxy-macOS.tar.gz"
            with tarfile.open(archive_path, "w:gz") as tar:
                tar.add(app_path, arcname="TgWsProxy.app")

            log(f"✅ macOS build complete: {app_path}")
            log(f"📦 Archive created: {archive_path}")
            return True

    except Exception as e:
        log(f"❌ macOS build failed: {e}")
        return False

    return False


def build_mobile() -> bool:
    """Build mobile apps (placeholder)."""
    log("\n" + "=" * 60)
    log("Building for MOBILE")
    log("=" * 60)

    # Check if Node.js is available
    node = shutil.which("node")
    npm = shutil.which("npm")

    if not node or not npm:
        log("⚠️  Node.js not found. Mobile build requires Node.js 18+")
        return False

    mobile_dir = PROJECT_ROOT / "mobile-app"
    if not mobile_dir.exists():
        log("⚠️  Mobile app directory not found")
        return False

    try:
        # Install dependencies
        log("📦 Installing npm dependencies...")
        subprocess.check_call([npm, "install"], cwd=mobile_dir)

        # Sync with Capacitor
        log("🔄 Syncing with Capacitor...")
        subprocess.check_call([npm, "run", "sync"], cwd=mobile_dir)

        log("✅ Mobile app synced")
        log("📱 For Android: Open Android Studio and build")
        log("📱 For iOS: Open Xcode and build")

        return True

    except Exception as e:
        log(f"❌ Mobile build failed: {e}")
        return False


def create_build_report(version: str, platforms: list) -> None:
    """Create build report."""
    report_path = DIST_DIR / "BUILD_REPORT.txt"

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("=" * 60 + "\n")
        f.write("TG WS Proxy - Build Report\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"Version: {version}\n")
        f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Python: {sys.version}\n")
        f.write(f"Platform: {sys.platform}\n\n")
        f.write("Built Platforms:\n")
        for platform in platforms:
            f.write(f"  ✅ {platform}\n")
        f.write("\n")
        f.write("Files:\n")
        for item in DIST_DIR.iterdir():
            if item.is_file():
                size_mb = item.stat().st_size / (1024 * 1024)
                f.write(f"  {item.name} ({size_mb:.2f} MB)\n")
        f.write("\n")
        f.write("=" * 60 + "\n")

    log(f"\n📄 Build report created: {report_path}")


def main() -> int:
    """Main build function."""
    platform = sys.argv[1] if len(sys.argv) > 1 else "all"

    print("=" * 60)
    print("TG WS Proxy - Quick Build Script")
    print("=" * 60)
    print(f"Target: {platform.upper()}")
    print("=" * 60)

    # Clean
    clean_build_dirs()

    # Create dist directory
    DIST_DIR.mkdir(exist_ok=True)

    # Initialize log
    with open(BUILD_LOG, "w", encoding="utf-8") as f:
        f.write(f"Build started: {datetime.now()}\n")
        f.write(f"Target: {platform}\n\n")

    # Get version
    version = get_version()
    log(f"Version: {version}")

    # Determine platforms to build
    built_platforms = []

    if platform in ("windows", "all"):
        if build_windows():
            built_platforms.append("Windows")

    if platform in ("linux", "all"):
        if build_linux():
            built_platforms.append("Linux")

    if platform in ("macos", "all"):
        if build_macos():
            built_platforms.append("macOS")

    if platform in ("mobile", "all"):
        if build_mobile():
            built_platforms.append("Mobile")

    # Create report
    if built_platforms:
        create_build_report(version, built_platforms)

        log("\n" + "=" * 60)
        log("✅ BUILD COMPLETED SUCCESSFULLY!")
        log("=" * 60)
        log(f"📁 Distribution: {DIST_DIR}")
        log(f"📊 Built for: {', '.join(built_platforms)}")
        log("=" * 60)
        return 0
    else:
        log("\n" + "=" * 60)
        log("❌ BUILD FAILED!")
        log("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
