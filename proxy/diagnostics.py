"""
Connection diagnostics for MTProto Proxy.

Tests connectivity to Telegram datacenters and WebSocket endpoints.
"""

from __future__ import annotations

import asyncio
import logging
import socket
import ssl
import time
from dataclasses import dataclass

log = logging.getLogger('tg-mtproto-diagnostics')


@dataclass
class DiagnosticResult:
    """Result of a single diagnostic test."""
    name: str
    success: bool
    latency_ms: float | None = None
    error: str | None = None
    details: str | None = None


async def test_tcp_connect(host: str, port: int, timeout: float = 5.0) -> DiagnosticResult:
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
        return DiagnosticResult(
            name=f"TCP {host}:{port}",
            success=True,
            latency_ms=latency,
        )
    except asyncio.TimeoutError:
        return DiagnosticResult(
            name=f"TCP {host}:{port}",
            success=False,
            error="Connection timeout",
        )
    except Exception as e:
        return DiagnosticResult(
            name=f"TCP {host}:{port}",
            success=False,
            error=str(e),
        )


async def test_websocket_connect(ip: str, domain: str, timeout: float = 10.0) -> DiagnosticResult:
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
            return DiagnosticResult(
                name=f"WS {domain} via {ip}",
                success=True,
                latency_ms=latency,
                details="WebSocket upgrade successful",
            )
        elif b'302' in response:
            return DiagnosticResult(
                name=f"WS {domain} via {ip}",
                success=False,
                latency_ms=latency,
                error="HTTP 302 Redirect (WS not available)",
            )
        else:
            return DiagnosticResult(
                name=f"WS {domain} via {ip}",
                success=False,
                latency_ms=latency,
                error=f"Unexpected response: {response[:100]}",
            )

    except asyncio.TimeoutError:
        return DiagnosticResult(
            name=f"WS {domain} via {ip}",
            success=False,
            error="Connection timeout",
        )
    except Exception as e:
        return DiagnosticResult(
            name=f"WS {domain} via {ip}",
            success=False,
            error=str(e),
        )


async def test_dns_resolve(hostname: str) -> DiagnosticResult:
    """Test DNS resolution."""
    start = time.perf_counter()
    try:
        addrs = await asyncio.get_event_loop().getaddrinfo(
            hostname, None, socket.AF_INET, socket.SOCK_STREAM
        )
        latency = (time.perf_counter() - start) * 1000
        ips = list({addr[4][0] for addr in addrs})
        return DiagnosticResult(
            name=f"DNS {hostname}",
            success=True,
            latency_ms=latency,
            details=f"Resolved to: {', '.join(ips)}",
        )
    except Exception as e:
        return DiagnosticResult(
            name=f"DNS {hostname}",
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


async def run_full_diagnostics() -> list[DiagnosticResult]:
    """Run full diagnostic suite."""
    results = []

    log.info("Starting diagnostics...")

    # Test DNS
    for dc in range(1, 6):
        for domain in DC_DOMAINS[dc]:
            result = await test_dns_resolve(domain)
            results.append(result)
            log.info("  %s: %s", result.name, "✓" if result.success else f"✗ {result.error}")

    # Test TCP connectivity to DC IPs
    for _dc, ips in DC_IPS.items():
        for ip in ips:
            result = await test_tcp_connect(ip, 443)
            results.append(result)
            log.info("  %s: %s", result.name, "✓" if result.success else f"✗ {result.error}")

    # Test WebSocket endpoints
    for dc, domains in DC_DOMAINS.items():
        ip = DC_IPS[dc][0]
        for domain in domains[:1]:  # Test first domain only
            result = await test_websocket_connect(ip, domain)
            results.append(result)
            log.info("  %s: %s", result.name, "✓" if result.success else f"✗ {result.error}")

    # Summary
    total = len(results)
    success = sum(1 for r in results if r.success)
    log.info("Diagnostics complete: %d/%d tests passed", success, total)

    return results


def print_diagnostics_report(results: list[DiagnosticResult]):
    """Print formatted diagnostics report."""
    print("\n" + "=" * 60)
    print("  MTProto Proxy Diagnostics Report")
    print("=" * 60)

    # Group by type
    dns_results = [r for r in results if r.name.startswith('DNS')]
    tcp_results = [r for r in results if r.name.startswith('TCP')]
    ws_results = [r for r in results if r.name.startswith('WS')]

    print("\n📡 DNS Resolution:")
    for r in dns_results:
        status = "✓" if r.success else "✗"
        print(f"  {status} {r.name}: {r.latency_ms:.1f}ms" if r.success else f"  {status} {r.name}: {r.error}")
        if r.details:
            print(f"      {r.details}")

    print("\n🔌 TCP Connectivity (port 443):")
    for r in tcp_results:
        status = "✓" if r.success else "✗"
        print(f"  {status} {r.name}: {r.latency_ms:.1f}ms" if r.success else f"  {status} {r.name}: {r.error}")

    print("\n🌐 WebSocket Endpoints:")
    for r in ws_results:
        status = "✓" if r.success else "✗"
        if r.success:
            print(f"  {status} {r.name}: {r.latency_ms:.1f}ms - {r.details}")
        else:
            print(f"  {status} {r.name}: {r.error}")

    # Summary
    total = len(results)
    success = sum(1 for r in results if r.success)
    print("\n" + "=" * 60)
    print(f"  Summary: {success}/{total} tests passed ({100*success/total:.1f}%)")
    print("=" * 60 + "\n")


def run_diagnostics_cli():
    """Run diagnostics from CLI."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(message)s'
    )

    print("\n🔍 Running MTProto Proxy Diagnostics...\n")

    results = asyncio.run(run_full_diagnostics())
    print_diagnostics_report(results)

    # Return exit code based on results
    success = sum(1 for r in results if r.success)
    return 0 if success == len(results) else 1


if __name__ == '__main__':
    import sys
    sys.exit(run_diagnostics_cli())
