#!/usr/bin/env python3
"""
Generate PWA icons from icon.ico for the web dashboard.

Author: Dupley Maxim Igorevich
© 2026 Dupley Maxim Igorevich. All rights reserved.
"""

import os
import shutil
from pathlib import Path

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


def generate_icons():
    """Generate PWA icons from icon.ico."""
    if not HAS_PIL:
        print("PIL (Pillow) not installed. Install with: pip install Pillow")
        return False

    # Source icon
    project_root = Path(__file__).parent
    icon_ico = project_root / "icon.ico"
    
    if not icon_ico.exists():
        print(f"icon.ico not found at {icon_ico}")
        return False

    # Output directory
    static_dir = project_root / "proxy" / "static"
    static_dir.mkdir(exist_ok=True)

    # Open the .ico file
    try:
        icon = Image.open(icon_ico)
    except Exception as e:
        print(f"Error opening icon.ico: {e}")
        return False

    # Sizes needed for PWA
    sizes = [
        (192, 192),
        (512, 512),
    ]

    generated = []
    for width, height in sizes:
        output_path = static_dir / f"icon-{width}.png"
        # Resize the icon
        resized = icon.resize((width, height), Image.Resampling.LANCZOS)
        # Convert to RGBA if necessary (for PNG transparency)
        if resized.mode != 'RGBA':
            resized = resized.convert('RGBA')
        resized.save(output_path, 'PNG')
        generated.append(output_path)
        print(f"Generated: {output_path}")

    # Also copy icon.ico to static folder for favicon
    shutil.copy2(icon_ico, static_dir / "favicon.ico")
    print(f"Copied: {static_dir / 'favicon.ico'}")

    print(f"\n✓ Generated {len(generated)} icons in {static_dir}")
    return True


if __name__ == "__main__":
    success = generate_icons()
    exit(0 if success else 1)
