#!/usr/bin/env python3
"""
Security Audit Script for TG WS Proxy.

Run security audits using pip-audit and safety.
Usage: python scripts/security_audit.py [--requirements FILE]

Author: Dupley Maxim Igorevich
© 2026 Dupley Maxim Igorevich. All rights reserved.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def run_command(cmd: list[str], capture: bool = False) -> int:
    """Run shell command and return exit code."""
    print(f"\n{'='*60}")
    print(f"Running: {' '.join(cmd)}")
    print(f"{'='*60}\n")

    result = subprocess.run(cmd, capture_output=capture, text=True)

    if capture:
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)

    return result.returncode


def check_pip_audit(requirements_file: str) -> dict:
    """Run pip-audit and return results."""
    print(f"\n🔍 Running pip-audit on {requirements_file}...")

    # Run pip-audit with JSON output
    cmd = [
        sys.executable, "-m", "pip_audit",
        "-r", requirements_file,
        "--desc",
        "-f", "json"
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        print("✅ No vulnerabilities found!")
        return {"vulnerabilities": [], "status": "clean"}
    else:
        try:
            # Parse JSON output
            vulnerabilities = json.loads(result.stdout)
            count = len(vulnerabilities) if isinstance(vulnerabilities, list) else 0
            print(f"⚠️  Found {count} vulnerabilities!")

            for vuln in (vulnerabilities if isinstance(vulnerabilities, list) else []):
                if isinstance(vuln, dict):
                    name = vuln.get('name', 'Unknown')
                    vuln_id = vuln.get('vulns', [{}])[0].get('id', 'Unknown')
                    desc = vuln.get('vulns', [{}])[0].get('description', 'No description')[:200]
                    print(f"\n  📦 {name}: {vuln_id}")
                    print(f"     {desc}...")

            return {"vulnerabilities": vulnerabilities, "status": "vulnerable"}
        except json.JSONDecodeError:
            print("⚠️  pip-audit found issues (JSON parse error)")
            return {"vulnerabilities": [], "status": "error", "error": result.stdout}


def check_safety(requirements_file: str) -> None:
    """Run safety check."""
    print(f"\n🔍 Running safety check on {requirements_file}...")

    cmd = [sys.executable, "-m", "safety", "check", "-r", requirements_file]
    run_command(cmd, capture=True)


def generate_report(results: list[dict], output_file: str) -> None:
    """Generate security audit report."""
    report = {
        "timestamp": datetime.now().isoformat(),
        "results": results,
        "summary": {
            "total_vulnerabilities": sum(
                len(r.get("vulnerabilities", [])) for r in results
            ),
            "files_checked": len(results),
            "status": "clean" if all(r.get("status") == "clean" for r in results) else "vulnerable"
        }
    }

    output_path = Path(output_file)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"\n📄 Report saved to: {output_path}")


def main() -> int:
    """Main entry point."""
    # Parse arguments
    requirements_files = []
    if len(sys.argv) > 1:
        requirements_files = sys.argv[1:]
    else:
        # Default requirements files
        script_dir = Path(__file__).parent
        root_dir = script_dir.parent

        if (root_dir / "requirements.txt").exists():
            requirements_files.append(str(root_dir / "requirements.txt"))
        if (root_dir / "requirements-dev.txt").exists():
            requirements_files.append(str(root_dir / "requirements-dev.txt"))
        if (root_dir / "requirements-build.txt").exists():
            requirements_files.append(str(root_dir / "requirements-build.txt"))

    if not requirements_files:
        print("❌ No requirements files found!")
        return 1

    print("🔐 TG WS Proxy Security Audit")
    print(f"{'='*60}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"Files to check: {', '.join(requirements_files)}")

    # Check if pip-audit and safety are installed
    try:
        import pip_audit  # noqa: F401
    except ImportError:
        print("\n⚠️  pip-audit not installed. Installing...")
        run_command([sys.executable, "-m", "pip", "install", "pip-audit"])

    try:
        import safety  # noqa: F401
    except ImportError:
        print("\n⚠️  safety not installed. Installing...")
        run_command([sys.executable, "-m", "pip", "install", "safety"])

    # Run audits
    results = []
    for req_file in requirements_files:
        if not Path(req_file).exists():
            print(f"\n⚠️  Skipping {req_file} (not found)")
            continue

        result = check_pip_audit(req_file)
        result["file"] = req_file
        results.append(result)

        # Also run safety check
        check_safety(req_file)

    # Generate report
    report_file = Path(__file__).parent.parent / "security-audit-report.json"
    generate_report(results, str(report_file))

    # Summary
    print(f"\n{'='*60}")
    print("📊 SUMMARY")
    print(f"{'='*60}")

    total_vulns = sum(len(r.get("vulnerabilities", [])) for r in results)

    if total_vulns == 0:
        print("✅ All checks passed! No vulnerabilities found.")
        return 0
    else:
        print(f"⚠️  Total vulnerabilities found: {total_vulns}")
        print("\n💡 Recommendations:")
        print("   1. Run: pip install --upgrade <package>")
        print("   2. Review requirements.txt for outdated packages")
        print("   3. Check https://pyup.io/safety/ for more info")
        return 1


if __name__ == "__main__":
    sys.exit(main())
