"""
Advanced Diagnostics Report Module for TG WS Proxy.

Provides comprehensive network diagnostics with export capabilities:
- Full connectivity testing (DNS, TCP, WebSocket)
- Performance metrics (latency, packet loss)
- DC health assessment
- Export to JSON/CSV formats
- Historical data tracking
- Recommendations engine

Author: Dupley Maxim Igorevich
© 2026 Dupley Maxim Igorevich. All rights reserved.
"""

from __future__ import annotations

import asyncio
import csv
import io
import json
import logging
import os
import platform
import socket
import ssl
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Any

from . import tg_ws_proxy
from .connection_pool import get_tcp_pool, _WsPool
from .stats import Stats

log = logging.getLogger('tg-ws-diagnostics-adv')


class HealthStatus(Enum):
    """Health status levels."""
    EXCELLENT = auto()  # All tests passed, low latency
    GOOD = auto()       # Most tests passed, acceptable latency
    DEGRADED = auto()   # Some failures, high latency
    CRITICAL = auto()   # Major failures, very high latency
    DOWN = auto()       # Complete failure


@dataclass
class NetworkInterface:
    """Network interface information."""
    name: str
    ip_address: str
    mac_address: str | None
    is_up: bool
    is_default: bool = False


@dataclass
class DCTestResult:
    """Diagnostic result for a single DC."""
    dc_id: int
    ip: str
    domain: str
    dns_success: bool
    dns_latency_ms: float | None
    tcp_success: bool
    tcp_latency_ms: float | None
    ws_success: bool
    ws_latency_ms: float | None
    ws_available: bool  # False if 302 redirect
    error: str | None = None


@dataclass
class DiagnosticReport:
    """Complete diagnostic report."""
    timestamp: str
    hostname: str
    platform: str
    python_version: str
    proxy_version: str
    
    # Network info
    network_interfaces: list[NetworkInterface] = field(default_factory=list)
    
    # DC test results
    dc_results: list[DCTestResult] = field(default_factory=list)
    
    # Summary metrics
    total_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0
    avg_latency_ms: float = 0.0
    min_latency_ms: float | None = None
    max_latency_ms: float | None = None
    
    # Health assessment
    overall_health: HealthStatus = HealthStatus.DEGRADED
    best_dc: int | None = None
    best_dc_latency_ms: float | None = None
    
    # Recommendations
    recommendations: list[str] = field(default_factory=list)
    
    # Raw data for export
    raw_data: dict[str, Any] = field(default_factory=dict)


class DiagnosticsAdvanced:
    """
    Advanced diagnostics with comprehensive reporting.
    
    Features:
    - Multi-threaded testing for speed
    - Historical data tracking
    - Export to multiple formats
    - Health assessment
    - Automated recommendations
    """
    
    # Telegram DC configuration
    DC_DOMAINS = {
        1: ['kws1.web.telegram.org', 'kws1-1.web.telegram.org'],
        2: ['kws2.web.telegram.org', 'kws2-1.web.telegram.org'],
        3: ['kws3.web.telegram.org', 'kws3-1.web.telegram.org'],
        4: ['kws4.web.telegram.org', 'kws4-1.web.telegram.org'],
        5: ['kws5.web.telegram.org', 'kws5-1.web.telegram.org'],
    }
    
    DC_IPS = {
        1: ['149.154.175.50'],
        2: ['149.154.167.220', '95.161.76.100'],
        3: ['149.154.175.100'],
        4: ['149.154.167.91'],
        5: ['91.108.56.100'],
    }
    
    def __init__(self):
        self._history: list[DiagnosticReport] = []
        self._max_history = 100  # Keep last 100 reports
        self._ssl_ctx = ssl.create_default_context()
        self._ssl_ctx.check_hostname = False
        self._ssl_ctx.verify_mode = ssl.CERT_NONE
        
    async def run_full_diagnostics(
        self,
        dc_opt: dict[int, str | None] | None = None,
    ) -> DiagnosticReport:
        """
        Run comprehensive diagnostics suite.
        
        Args:
            dc_opt: Optional DC override configuration
            
        Returns:
            Complete diagnostic report
        """
        start_time = time.time()
        
        # Initialize report
        report = DiagnosticReport(
            timestamp=datetime.now().isoformat(),
            hostname=socket.gethostname(),
            platform=f"{platform.system()} {platform.release()} ({platform.machine()})",
            python_version=platform.python_version(),
            proxy_version=self._get_proxy_version(),
        )
        
        # Gather network interfaces
        report.network_interfaces = await self._gather_network_info()
        
        # Use provided DC config or default
        if dc_opt is None:
            dc_opt = self.DC_IPS.copy()
        
        # Run DC tests
        dc_results = await self._test_all_dcs(dc_opt)
        report.dc_results = dc_results
        
        # Calculate summary metrics
        self._calculate_summary(report)
        
        # Assess health
        report.overall_health = self._assess_health(report)
        
        # Generate recommendations
        report.recommendations = self._generate_recommendations(report)
        
        # Store in history
        self._history.append(report)
        if len(self._history) > self._max_history:
            self._history.pop(0)
        
        duration = time.time() - start_time
        log.info("Diagnostics completed in %.2fs (health: %s)", 
                duration, report.overall_health.name)
        
        return report
    
    async def _gather_network_info(self) -> list[NetworkInterface]:
        """Gather network interface information."""
        interfaces = []
        
        try:
            # Get default interface
            default_ip = self._get_default_ip()
            
            # Get all interfaces (simplified for cross-platform)
            hostname = socket.gethostname()
            try:
                addr_info = socket.getaddrinfo(hostname, None, socket.AF_INET)
                for info in addr_info:
                    ip = info[4][0]
                    if not ip.startswith('127.'):
                        interfaces.append(NetworkInterface(
                            name='default',
                            ip_address=ip,
                            mac_address=None,  # Requires admin privileges
                            is_up=True,
                            is_default=(ip == default_ip),
                        ))
            except Exception as e:
                log.debug("Failed to get interface info: %s", e)
                
        except Exception as e:
            log.debug("Network info gathering failed: %s", e)
        
        return interfaces
    
    def _get_default_ip(self) -> str:
        """Get default gateway IP."""
        try:
            # Create UDP socket to determine default route
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "unknown"
    
    async def _test_all_dcs(
        self,
        dc_opt: dict[int, str | None],
    ) -> list[DCTestResult]:
        """Test all DCs concurrently."""
        tasks = []
        
        for dc_id, target_ip in dc_opt.items():
            if target_ip is None:
                continue
                
            domains = self.DC_DOMAINS.get(dc_id, [])
            if not domains:
                continue
            
            # Test each domain for this DC
            for domain in domains[:1]:  # Test first domain only
                task = asyncio.create_task(
                    self._test_single_dc(dc_id, target_ip, domain)
                )
                tasks.append(task)
        
        # Run all tests concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions
        valid_results = []
        for r in results:
            if isinstance(r, DCTestResult):
                valid_results.append(r)
            elif isinstance(r, Exception):
                log.debug("DC test exception: %s", r)
        
        return valid_results
    
    async def _test_single_dc(
        self,
        dc_id: int,
        ip: str,
        domain: str,
    ) -> DCTestResult:
        """Test a single DC endpoint."""
        result = DCTestResult(
            dc_id=dc_id,
            ip=ip,
            domain=domain,
            dns_success=False,
            dns_latency_ms=None,
            tcp_success=False,
            tcp_latency_ms=None,
            ws_success=False,
            ws_latency_ms=None,
            ws_available=True,
        )
        
        # Test DNS resolution
        dns_start = time.perf_counter()
        try:
            loop = asyncio.get_event_loop()
            resolved = await loop.getaddrinfo(domain, 443, family=socket.AF_INET)
            dns_latency = (time.perf_counter() - dns_start) * 1000
            result.dns_success = True
            result.dns_latency_ms = dns_latency
            log.debug("DC%d DNS %s: %.1fms", dc_id, domain, dns_latency)
        except Exception as e:
            result.error = f"DNS: {e}"
            log.debug("DC%d DNS %s failed: %s", dc_id, domain, e)
        
        # Test TCP connectivity
        if result.dns_success:
            tcp_start = time.perf_counter()
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(ip, 443, ssl=self._ssl_ctx, server_hostname=domain),
                    timeout=10.0
                )
                tcp_latency = (time.perf_counter() - tcp_start) * 1000
                result.tcp_success = True
                result.tcp_latency_ms = tcp_latency
                
                # Test WebSocket upgrade
                ws_result = await self._test_websocket_upgrade(reader, writer, domain)
                result.ws_success = ws_result['success']
                result.ws_latency_ms = ws_result.get('latency_ms')
                result.ws_available = ws_result.get('available', True)
                if not result.ws_available:
                    result.error = "WebSocket not available (302 redirect)"
                    
                log.debug("DC%d TCP+WS %s: %.1fms", dc_id, domain, tcp_latency)
                
            except Exception as e:
                result.error = f"TCP: {e}"
                log.debug("DC%d TCP %s failed: %s", dc_id, domain, e)
        
        return result
    
    async def _test_websocket_upgrade(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        domain: str,
    ) -> dict[str, Any]:
        """Test WebSocket upgrade."""
        import base64
        
        try:
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
            
            start = time.perf_counter()
            writer.write(req.encode())
            await writer.drain()
            
            response = await asyncio.wait_for(reader.read(512), timeout=5.0)
            latency = (time.perf_counter() - start) * 1000
            
            writer.close()
            await writer.wait_closed()
            
            if b'101' in response:
                return {'success': True, 'latency_ms': latency, 'available': True}
            elif b'302' in response:
                return {'success': False, 'latency_ms': latency, 'available': False}
            else:
                return {'success': False, 'latency_ms': latency, 'available': True}
                
        except Exception as e:
            try:
                writer.close()
            except Exception:
                pass
            return {'success': False, 'error': str(e), 'available': True}
    
    def _calculate_summary(self, report: DiagnosticReport) -> None:
        """Calculate summary metrics."""
        report.total_tests = len(report.dc_results) * 3  # DNS + TCP + WS per DC
        report.passed_tests = sum(
            (1 if r.dns_success else 0) +
            (1 if r.tcp_success else 0) +
            (1 if r.ws_success else 0)
            for r in report.dc_results
        )
        report.failed_tests = report.total_tests - report.passed_tests
        
        # Calculate latency statistics
        latencies = [
            r.ws_latency_ms for r in report.dc_results
            if r.ws_success and r.ws_latency_ms is not None
        ]
        
        if latencies:
            report.avg_latency_ms = sum(latencies) / len(latencies)
            report.min_latency_ms = min(latencies)
            report.max_latency_ms = max(latencies)
            
            # Find best DC
            best = min(
                [(r.dc_id, r.ws_latency_ms) for r in report.dc_results if r.ws_success and r.ws_latency_ms],
                key=lambda x: x[1]
            )
            report.best_dc = best[0]
            report.best_dc_latency_ms = best[1]
    
    def _assess_health(self, report: DiagnosticReport) -> HealthStatus:
        """Assess overall health status."""
        if report.passed_tests == 0:
            return HealthStatus.DOWN
        
        pass_rate = report.passed_tests / report.total_tests if report.total_tests > 0 else 0
        
        if pass_rate == 1.0 and report.avg_latency_ms < 100:
            return HealthStatus.EXCELLENT
        elif pass_rate >= 0.8 and report.avg_latency_ms < 200:
            return HealthStatus.GOOD
        elif pass_rate >= 0.5 and report.avg_latency_ms < 500:
            return HealthStatus.DEGRADED
        elif pass_rate >= 0.3:
            return HealthStatus.CRITICAL
        else:
            return HealthStatus.DOWN
    
    def _generate_recommendations(self, report: DiagnosticReport) -> list[str]:
        """Generate recommendations based on diagnostics."""
        recommendations = []
        
        # Health-based recommendations
        if report.overall_health == HealthStatus.DOWN:
            recommendations.append("🔴 Критическая проблема: проверьте подключение к интернету")
        elif report.overall_health == HealthStatus.CRITICAL:
            recommendations.append("⚠️ Серьезные проблемы с подключением к Telegram DC")
        
        # Latency recommendations
        if report.avg_latency_ms > 300:
            recommendations.append(
                f"🐌 Высокая задержка ({report.avg_latency_ms:.0f}ms). "
                f"Попробуйте использовать DC{report.best_dc} ({report.best_dc_latency_ms:.0f}ms)"
            )
        
        # DC-specific recommendations
        failed_dcs = [r.dc_id for r in report.dc_results if not r.ws_success]
        if len(failed_dcs) > 0 and len(failed_dcs) < len(report.dc_results):
            recommendations.append(
                f"💡 DC {', '.join(map(str, failed_dcs))} недоступен. "
                f"Используйте DC{report.best_dc} как основной"
            )
        
        # DNS recommendations
        dns_failures = sum(1 for r in report.dc_results if not r.dns_success)
        if dns_failures > 0:
            recommendations.append("⚠️ Проблемы с DNS. Попробуйте использовать DoH или DNS over TLS")
        
        # General recommendations
        if not recommendations:
            recommendations.append("✅ Все системы работают нормально")
        
        return recommendations
    
    def _get_proxy_version(self) -> str:
        """Get proxy version."""
        try:
            from . import __version__
            return __version__
        except Exception:
            return "unknown"
    
    def export_json(self, report: DiagnosticReport, filepath: str | Path) -> None:
        """Export report to JSON format."""
        data = {
            'timestamp': report.timestamp,
            'hostname': report.hostname,
            'platform': report.platform,
            'python_version': report.python_version,
            'proxy_version': report.proxy_version,
            'network_interfaces': [asdict(i) for i in report.network_interfaces],
            'dc_results': [asdict(r) for r in report.dc_results],
            'summary': {
                'total_tests': report.total_tests,
                'passed_tests': report.passed_tests,
                'failed_tests': report.failed_tests,
                'avg_latency_ms': report.avg_latency_ms,
                'min_latency_ms': report.min_latency_ms,
                'max_latency_ms': report.max_latency_ms,
            },
            'health': report.overall_health.name,
            'best_dc': report.best_dc,
            'best_dc_latency_ms': report.best_dc_latency_ms,
            'recommendations': report.recommendations,
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        log.info("Diagnostic report exported to %s", filepath)
    
    def export_csv(self, report: DiagnosticReport, filepath: str | Path) -> None:
        """Export DC results to CSV format."""
        output = io.StringIO()
        
        fieldnames = [
            'dc_id', 'ip', 'domain', 'dns_success', 'dns_latency_ms',
            'tcp_success', 'tcp_latency_ms', 'ws_success', 'ws_latency_ms',
            'ws_available', 'error'
        ]
        
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        
        for r in report.dc_results:
            row = asdict(r)
            writer.writerow(row)
        
        with open(filepath, 'w', encoding='utf-8', newline='') as f:
            f.write(output.getvalue())
        
        log.info("Diagnostic CSV exported to %s", filepath)
    
    def get_history(self, limit: int = 10) -> list[DiagnosticReport]:
        """Get recent diagnostic history."""
        return self._history[-limit:]
    
    def print_report(self, report: DiagnosticReport) -> None:
        """Print formatted diagnostic report."""
        print("\n" + "=" * 70)
        print("  TG WS Proxy Diagnostic Report")
        print("=" * 70)
        print(f"  Time: {report.timestamp}")
        print(f"  Host: {report.hostname}")
        print(f"  Platform: {report.platform}")
        print(f"  Proxy: {report.proxy_version}")
        print("=" * 70)
        
        # Network interfaces
        if report.network_interfaces:
            print("\n📡 Network Interfaces:")
            for iface in report.network_interfaces:
                default = " (default)" if iface.is_default else ""
                print(f"  • {iface.name}{default}: {iface.ip_address}")
        
        # DC results
        print("\n🌐 Datacenter Results:")
        for r in report.dc_results:
            status = "✓" if r.ws_success else "✗"
            latency = f"{r.ws_latency_ms:.0f}ms" if r.ws_latency_ms else "N/A"
            print(f"  {status} DC{r.dc_id} ({r.domain} via {r.ip})")
            print(f"      DNS: {r.dns_latency_ms:.0f}ms | TCP: {r.tcp_latency_ms:.0f}ms | WS: {latency}")
            if r.error:
                print(f"      Error: {r.error}")
        
        # Summary
        print("\n📊 Summary:")
        print(f"  Tests: {report.passed_tests}/{report.total_tests} passed")
        if report.avg_latency_ms > 0:
            print(f"  Avg Latency: {report.avg_latency_ms:.0f}ms")
        if report.best_dc:
            print(f"  Best DC: DC{report.best_dc} ({report.best_dc_latency_ms:.0f}ms)")
        
        # Health status
        health_icons = {
            HealthStatus.EXCELLENT: "✅",
            HealthStatus.GOOD: "🟢",
            HealthStatus.DEGRADED: "🟡",
            HealthStatus.CRITICAL: "🔴",
            HealthStatus.DOWN: "⛔",
        }
        print(f"\n  Health: {health_icons[report.overall_health]} {report.overall_health.name}")
        
        # Recommendations
        print("\n💡 Recommendations:")
        for rec in report.recommendations:
            print(f"  • {rec}")
        
        print("\n" + "=" * 70 + "\n")


# Global diagnostics instance
_diagnostics: DiagnosticsAdvanced | None = None


def get_diagnostics() -> DiagnosticsAdvanced:
    """Get or create global diagnostics instance."""
    global _diagnostics
    if _diagnostics is None:
        _diagnostics = DiagnosticsAdvanced()
    return _diagnostics


__all__ = [
    'DiagnosticsAdvanced',
    'DiagnosticReport',
    'DCTestResult',
    'NetworkInterface',
    'HealthStatus',
    'get_diagnostics',
]
