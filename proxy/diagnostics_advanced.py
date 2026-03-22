"""
Advanced Diagnostics for TG WS Proxy.

Provides comprehensive connectivity testing:
- DNS resolution
- TCP connectivity
- WebSocket handshake
- DC latency measurement
- Performance recommendations

Author: Dupley Maxim Igorevich
© 2026 Dupley Maxim Igorevich. All rights reserved.
"""

from __future__ import annotations

import asyncio
import json
import logging
import socket
import ssl
import sys
import time
from dataclasses import dataclass, field

log = logging.getLogger('tg-diagnostics')


@dataclass
class TestResult:
    """Result of a single diagnostic test."""
    test_name: str
    target: str
    success: bool
    latency_ms: float | None = None
    error: str | None = None
    details: str | None = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            'test_name': self.test_name,
            'target': self.target,
            'success': self.success,
            'latency_ms': self.latency_ms,
            'error': self.error,
            'details': self.details,
            'timestamp': self.timestamp,
        }


@dataclass
class DiagnosticsReport:
    """Complete diagnostics report."""
    start_time: float = field(default_factory=time.time)
    end_time: float | None = None
    total_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0
    results: list[TestResult] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        if self.total_tests == 0:
            return 0.0
        return (self.passed_tests / self.total_tests) * 100

    @property
    def duration_ms(self) -> float:
        """Get test duration in milliseconds."""
        if self.end_time is None:
            return 0.0
        return (self.end_time - self.start_time) * 1000

    def add_result(self, result: TestResult) -> None:
        """Add test result and update counters."""
        self.results.append(result)
        self.total_tests += 1
        if result.success:
            self.passed_tests += 1
        else:
            self.failed_tests += 1

    def add_recommendation(self, recommendation: str) -> None:
        """Add recommendation to the report."""
        if recommendation not in self.recommendations:
            self.recommendations.append(recommendation)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            'start_time': self.start_time,
            'end_time': self.end_time,
            'duration_ms': self.duration_ms,
            'total_tests': self.total_tests,
            'passed_tests': self.passed_tests,
            'failed_tests': self.failed_tests,
            'success_rate': self.success_rate,
            'results': [r.to_dict() for r in self.results],
            'recommendations': self.recommendations,
        }


async def test_dns_resolution(hostname: str) -> TestResult:
    """Test DNS resolution for a hostname."""
    start = time.perf_counter()
    try:
        loop = asyncio.get_event_loop()
        addrs = await loop.getaddrinfo(
            host=hostname, port=None, family=socket.AF_INET, type=socket.SOCK_STREAM
        )
        latency = (time.perf_counter() - start) * 1000
        ips = list({addr[4][0] for addr in addrs})

        return TestResult(
            test_name="DNS Resolution",
            target=hostname,
            success=True,
            latency_ms=latency,
            details=f"Resolved to: {', '.join(ips)}",
        )
    except Exception as e:
        return TestResult(
            test_name="DNS Resolution",
            target=hostname,
            success=False,
            error=str(e),
        )


async def test_tcp_connect(host: str, port: int, timeout: float = 5.0) -> TestResult:
    """Test TCP connection to host:port."""
    start = time.perf_counter()
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=timeout
        )
        latency = (time.perf_counter() - start) * 1000
        writer.close()
        await writer.wait_closed()

        return TestResult(
            test_name="TCP Connect",
            target=f"{host}:{port}",
            success=True,
            latency_ms=latency,
        )
    except asyncio.TimeoutError:
        return TestResult(
            test_name="TCP Connect",
            target=f"{host}:{port}",
            success=False,
            error="Connection timeout",
        )
    except Exception as e:
        return TestResult(
            test_name="TCP Connect",
            target=f"{host}:{port}",
            success=False,
            error=str(e),
        )


async def test_websocket_connect(ip: str, domain: str, timeout: float = 10.0) -> TestResult:
    """Test WebSocket connection to Telegram DC."""
    start = time.perf_counter()
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, 443, ssl=ssl_ctx, server_hostname=domain),
            timeout=timeout
        )

        # Send WebSocket handshake
        import base64
        import os

        ws_key = base64.b64encode(os.urandom(16)).decode()
        req = (
            f'GET /apiws HTTP/1.1\r\n'
            f'Host: {domain}\r\n'
            f'Upgrade: websocket\r\n'
            f'Connection: Upgrade\r\n'
            f'Sec-WebSocket-Key: {ws_key}\r\n'
            f'Sec-WebSocket-Version: 13\r\n'
            f'\r\n'
        )
        writer.write(req.encode())
        await writer.drain()

        # Read response
        response = await asyncio.wait_for(reader.read(512), timeout=timeout)
        latency = (time.perf_counter() - start) * 1000

        writer.close()
        await writer.wait_closed()

        # Check if upgrade was successful
        if b'101' in response:
            return TestResult(
                test_name="WebSocket Connect",
                target=f"{domain} via {ip}",
                success=True,
                latency_ms=latency,
                details="WebSocket upgrade successful",
            )
        elif b'302' in response:
            return TestResult(
                test_name="WebSocket Connect",
                target=f"{domain} via {ip}",
                success=False,
                latency_ms=latency,
                error="HTTP 302 Redirect (WS not available)",
            )
        else:
            return TestResult(
                test_name="WebSocket Connect",
                target=f"{domain} via {ip}",
                success=False,
                latency_ms=latency,
                error=f"Unexpected response: {response[:100].decode('utf-8', errors='replace')}",
            )

    except asyncio.TimeoutError:
        return TestResult(
            test_name="WebSocket Connect",
            target=f"{domain} via {ip}",
            success=False,
            error="Connection timeout",
        )
    except Exception as e:
        return TestResult(
            test_name="WebSocket Connect",
            target=f"{domain} via {ip}",
            success=False,
            error=str(e),
        )


# Telegram DC WebSocket domains
DC_DOMAINS = {
    1: ['kws1.web.telegram.org', 'kws1-1.web.telegram.org'],
    2: ['kws2.web.telegram.org', 'kws2-1.web.telegram.org'],
    3: ['kws3.web.telegram.org', 'kws3-1.web.telegram.org'],
    4: ['kws4.web.telegram.org', 'kws4-1.web.telegram.org'],
    5: ['kws5.web.telegram.org', 'kws5-1.web.telegram.org'],
}

# Telegram DC IPs
DC_IPS = {
    1: ['149.154.175.50'],
    2: ['149.154.167.220', '95.161.76.100'],
    3: ['149.154.175.100'],
    4: ['149.154.167.91'],
    5: ['91.108.56.100'],
}


async def run_full_diagnostics() -> DiagnosticsReport:
    """Run full diagnostic suite."""
    report = DiagnosticsReport()

    log.info("Starting diagnostics...")

    # Test DNS
    log.info("Testing DNS resolution...")
    for dc in range(1, 6):
        for domain in DC_DOMAINS[dc]:
            result = await test_dns_resolution(domain)
            report.add_result(result)
            log.info("  %s: %s", result.target, "✓" if result.success else f"✗ {result.error}")

    # Test TCP connectivity to DC IPs
    log.info("Testing TCP connectivity...")
    for _dc, ips in DC_IPS.items():
        for ip in ips:
            result = await test_tcp_connect(ip, 443)
            report.add_result(result)
            log.info("  %s: %s", result.target, "✓" if result.success else f"✗ {result.error}")

    # Test WebSocket endpoints
    log.info("Testing WebSocket endpoints...")
    for dc, domains in DC_DOMAINS.items():
        ip = DC_IPS[dc][0]
        for domain in domains[:1]:  # Test first domain only
            result = await test_websocket_connect(ip, domain)
            report.add_result(result)
            log.info("  %s: %s", result.target, "✓" if result.success else f"✗ {result.error}")

    # Generate recommendations
    _generate_recommendations(report)

    # Summary
    log.info("Diagnostics complete: %d/%d tests passed (%.1f%%)",
             report.passed_tests, report.total_tests, report.success_rate)

    report.end_time = time.time()
    return report


def _generate_recommendations(report: DiagnosticsReport) -> None:
    """Generate recommendations based on test results."""
    # Check DNS issues
    dns_failures = [r for r in report.results if r.test_name == "DNS Resolution" and not r.success]
    if dns_failures:
        report.add_recommendation("⚠️ DNS resolution failures detected. Try changing your DNS server to Google DNS (8.8.8.8) or Cloudflare (1.1.1.1).")

    # Check TCP connectivity
    tcp_failures = [r for r in report.results if r.test_name == "TCP Connect" and not r.success]
    if len(tcp_failures) > len(DC_IPS):
        report.add_recommendation("⚠️ Multiple TCP connection failures. Check your firewall and internet connection.")

    # Check WebSocket issues
    ws_failures = [r for r in report.results if r.test_name == "WebSocket Connect" and not r.success]
    ws_redirects = [r for r in ws_failures if "302" in (r.error or "")]

    if ws_redirects:
        report.add_recommendation("⚠️ WebSocket endpoints returning 302 redirects. This DC may not support WebSocket connections - TCP fallback will be used.")

    if len(ws_failures) > len(DC_DOMAINS) and not ws_redirects:
        report.add_recommendation("⚠️ Multiple WebSocket failures. Consider using TCP fallback or checking your network configuration.")

    # Check latency
    successful_ws = [r for r in report.results if r.test_name == "WebSocket Connect" and r.success and r.latency_ms]
    if successful_ws:
        avg_latency = sum(r.latency_ms for r in successful_ws) / len(successful_ws)  # type: ignore[misc]
        if avg_latency > 200:
            report.add_recommendation(f"🐌 High average latency ({avg_latency:.1f}ms). Try selecting a different DC or checking your network connection.")
        elif avg_latency > 100:
            report.add_recommendation(f"⚡ Moderate latency ({avg_latency:.1f}ms). Performance should be acceptable.")
        else:
            report.add_recommendation(f"✅ Excellent latency ({avg_latency:.1f}ms). Network connection is optimal.")

    # Overall success rate
    if report.success_rate < 50:
        report.add_recommendation("🔴 Low success rate. Major connectivity issues detected. Check your internet connection and firewall settings.")
    elif report.success_rate < 80:
        report.add_recommendation("🟡 Moderate success rate. Some connectivity issues detected. Review failed tests above.")
    else:
        report.add_recommendation("🟢 Good connectivity. All critical systems operational.")


def print_diagnostics_report(report: DiagnosticsReport) -> None:
    """Print formatted diagnostics report."""
    print("\n" + "=" * 70)
    print("  TG WS Proxy - Diagnostics Report")
    print("=" * 70)
    print(f"  Duration: {report.duration_ms:.0f}ms | Tests: {report.total_tests} | "
          f"Passed: {report.passed_tests} | Failed: {report.failed_tests} | "
          f"Success: {report.success_rate:.1f}%")
    print("=" * 70)

    # Group by type
    dns_results = [r for r in report.results if r.test_name == "DNS Resolution"]
    tcp_results = [r for r in report.results if r.test_name == "TCP Connect"]
    ws_results = [r for r in report.results if r.test_name == "WebSocket Connect"]

    def print_section(title: str, results: list[TestResult]) -> None:
        print(f"\n{title}:")
        for r in results:
            status = "✓" if r.success else "✗"
            if r.success:
                print(f"  {status} {r.target}: {r.latency_ms:.1f}ms" if r.latency_ms else f"  {status} {r.target}")
            else:
                print(f"  {status} {r.target}: {r.error}")
            if r.details:
                print(f"      {r.details}")

    print_section("📡 DNS Resolution", dns_results)
    print_section("🔌 TCP Connectivity (port 443)", tcp_results)
    print_section("🌐 WebSocket Endpoints", ws_results)

    print("\n" + "=" * 70)
    print("  Recommendations:")
    print("=" * 70)
    for rec in report.recommendations:
        print(f"  {rec}")
    print("=" * 70 + "\n")


def run_diagnostics_cli() -> int:
    """Run diagnostics from CLI."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(message)s'
    )

    print("\n🔍 Running TG WS Proxy Diagnostics...\n")

    report = asyncio.run(run_full_diagnostics())
    print_diagnostics_report(report)

    # Optionally save to file
    if len(sys.argv) > 1 and sys.argv[1] == '--json':
        output_file = 'diagnostics_report.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report.to_dict(), f, indent=2)
        print(f"\n💾 Report saved to: {output_file}")

    # Return exit code based on results
    return 0 if report.success_rate >= 80 else 1


if __name__ == '__main__':
    sys.exit(run_diagnostics_cli())
