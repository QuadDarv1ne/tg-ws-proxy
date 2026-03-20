#!/usr/bin/env python3
"""
Build script for TG WS Proxy - Desktop applications.

Builds executables for Windows, Linux, and macOS using PyInstaller.

Author: Dupley Maxim Igorevich
© 2026 Dupley Maxim Igorevich. All rights reserved.

Usage:
    python build_desktop.py [platform]

Platforms:
    - windows: Build for Windows (.exe)
    - linux: Build for Linux (binary)
    - macos: Build for macOS (.app)
    - all: Build for all platforms (current OS only)
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

# Project root
PROJECT_ROOT = Path(__file__).parent
PACKAGING_DIR = PROJECT_ROOT / "packaging"
BUILD_DIR = PROJECT_ROOT / "build"
DIST_DIR = PROJECT_ROOT / "dist"

# Python executable
PYTHON = sys.executable


def clean_build_dirs():
    """Clean previous build artifacts."""
    print("🧹 Cleaning build directories...")
    for dir_path in [BUILD_DIR, DIST_DIR]:
        if dir_path.exists():
            shutil.rmtree(dir_path)

    # Clean PyInstaller cache
    for pattern in ["build", "dist", "*.spec"]:
        for path in PROJECT_ROOT.glob(pattern):
            if path.is_dir() and path.name != "packaging":
                shutil.rmtree(path, ignore_errors=True)


def install_build_deps():
    """Install build dependencies."""
    print("📦 Installing build dependencies...")
    subprocess.check_call([
        PYTHON, "-m", "pip", "install", "-r",
        str(PROJECT_ROOT / "requirements-build.txt")
    ])

    # Install runtime dependencies
    subprocess.check_call([
        PYTHON, "-m", "pip", "install", "-r",
        str(PROJECT_ROOT / "requirements.txt")
    ])

    # Install tray dependencies
    try:
        subprocess.check_call([
            PYTHON, "-m", "pip", "install", "-r",
            str(PROJECT_ROOT / "requirements-dev.txt")
        ])
    except subprocess.CalledProcessError:
        print("⚠️  Some tray dependencies may not be available")


def build_platform(platform: str):
    """Build for a specific platform."""
    spec_file = PACKAGING_DIR / f"{platform}.spec"

    if not spec_file.exists():
        print(f"❌ Spec file not found: {spec_file}")
        return False

    print(f"🔨 Building for {platform.upper()}...")

    try:
        # When using a .spec file, we can't use --specpath
        # The spec file path is passed directly to PyInstaller
        subprocess.check_call([
            PYTHON, "-m", "PyInstaller",
            "--clean",
            "--distpath", str(DIST_DIR),
            "--workpath", str(BUILD_DIR / platform),
            str(spec_file)
        ])

        print(f"✅ Build completed for {platform.upper()}")
        print(f"📁 Output: {DIST_DIR}")
        return True

    except subprocess.CalledProcessError as e:
        print(f"❌ Build failed for {platform.upper()}: {e}")
        return False


def create_release_archive(platform: str):
    """Create a release archive for the platform."""
    dist_path = DIST_DIR

    if platform == "windows":
        exe_path = dist_path / "TgWsProxy.exe"
        if exe_path.exists():
            # Create ZIP archive
            import zipfile
            archive_path = dist_path / "TgWsProxy-Windows.zip"
            with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                zf.write(exe_path, "TgWsProxy.exe")
                # Add README
                readme = PROJECT_ROOT / "README.md"
                if readme.exists():
                    zf.write(readme, "README.md")
                # Add LICENSE
                license_file = PROJECT_ROOT / "LICENSE"
                if license_file.exists():
                    zf.write(license_file, "LICENSE")
            print(f"📦 Created archive: {archive_path}")

    elif platform == "linux":
        exe_path = dist_path / "TgWsProxy"
        if exe_path.exists():
            import tarfile
            archive_path = dist_path / "TgWsProxy-Linux.tar.gz"
            with tarfile.open(archive_path, "w:gz") as tar:
                tar.add(exe_path, arcname="TgWsProxy")
                # Add README
                readme = PROJECT_ROOT / "README.md"
                if readme.exists():
                    tar.add(readme, arcname="README.md")
                # Add LICENSE
                license_file = PROJECT_ROOT / "LICENSE"
                if license_file.exists():
                    tar.add(license_file, arcname="LICENSE")
            print(f"📦 Created archive: {archive_path}")

    elif platform == "macos":
        app_path = dist_path / "TgWsProxy.app"
        if app_path.exists():
            import shutil
            import tarfile
            archive_path = dist_path / "TgWsProxy-macOS.tar.gz"

            # Create temp directory for archiving
            temp_dir = DIST_DIR / "_temp_app"
            shutil.copytree(app_path, temp_dir / "TgWsProxy.app")

            with tarfile.open(archive_path, "w:gz") as tar:
                tar.add(temp_dir, arcname="TgWsProxy.app")

            shutil.rmtree(temp_dir)
            print(f"📦 Created archive: {archive_path}")


def main():
    """Main build function."""
    platform = sys.argv[1] if len(sys.argv) > 1 else "all"

    # Detect current OS
    current_os = "windows" if os.name == "nt" else "darwin" if sys.platform == "darwin" else "linux"

    print("=" * 60)
    print("TG WS Proxy - Desktop Build Script")
    print("=" * 60)
    print(f"Current OS: {current_os.upper()}")
    print(f"Target: {platform.upper()}")
    print("=" * 60)

    # Clean
    clean_build_dirs()

    # Install dependencies
    install_build_deps()

    # Determine platforms to build
    if platform == "all":
        # Can only build for current OS
        platforms_to_build = [current_os]
    else:
        platforms_to_build = [platform]

    # Build
    success = False
    for target_platform in platforms_to_build:
        if build_platform(target_platform):
            create_release_archive(target_platform)
            success = True

    if success:
        print("\n" + "=" * 60)
        print("✅ Build completed successfully!")
        print(f"📁 Distribution: {DIST_DIR}")
        print("=" * 60)
        return 0
    else:
        print("\n" + "=" * 60)
        print("❌ Build failed!")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
