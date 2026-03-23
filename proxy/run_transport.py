"""
TG WS Proxy - Enhanced Transport Runner.

Usage:
    python -m proxy.run_transport --transport quic --port 1080
    python -m proxy.run_transport --transport http2 --meek-cdn google
    python -m proxy.run_transport --transport auto --auto-select
"""

import argparse
import asyncio
import logging
import sys

from .transport_manager import TransportManager, TransportConfig, TransportType

log = logging.getLogger('tg-ws-proxy-run')


def parse_transport_type(name: str) -> TransportType:
    """Parse transport type from string."""
    mapping = {
        'websocket': TransportType.WEBSOCKET,
        'http2': TransportType.HTTP2,
        'quic': TransportType.QUIC,
        'meek': TransportType.MEEK,
        'shadowsocks': TransportType.SHADOWSOCKS,
        'tuic': TransportType.TUIC,
        'reality': TransportType.REALITY,
        'auto': TransportType.WEBSOCKET,  # Will auto-select
    }
    return mapping.get(name, TransportType.WEBSOCKET)


async def run_proxy_with_transport(args: argparse.Namespace) -> None:
    """Run proxy with enhanced transport support."""
    
    # Create transport configuration
    config = TransportConfig(
        transport_type=parse_transport_type(args.transport),
        host=args.transport_host or 'kws2.web.telegram.org',
        port=args.transport_port,
        path=args.transport_path,
        meek_cdn=args.meek_cdn,
        ss_method=args.ss_method,
        ss_password=args.ss_password,
        reality_public_key=args.reality_pubkey,
        reality_short_id=args.reality_shortid,
        reality_server_name=args.reality_sni,
        auto_select=args.auto_select,
        health_check_interval=args.health_interval,
    )
    
    # Create transport manager
    manager = TransportManager(config)
    
    log.info("=" * 60)
    log.info("  TG WS Proxy - Enhanced Transport")
    log.info("=" * 60)
    log.info(f"  Transport: {args.transport.upper()}")
    log.info(f"  Target: {config.host}:{config.port}")
    log.info(f"  Listen: 127.0.0.1:{args.port}")
    if args.transport == 'auto':
        log.info("  Auto-select: ENABLED")
    log.info("=" * 60)
    
    # Connect transport
    log.info("Connecting...")
    if not await manager.start():
        log.error("Failed to connect with any transport")
        return
    
    log.info("Connected! Proxy ready.")
    log.info("Configure Telegram: SOCKS5 127.0.0.1:%d", args.port)
    
    # Main loop - forward data between SOCKS5 clients and transport
    try:
        await run_forward_loop(manager, args.port)
    except KeyboardInterrupt:
        log.info("Shutting down...")
    finally:
        await manager.stop()
    
    # Print stats
    stats = manager.get_stats()
    log.info("Final stats:")
    log.info("  Bytes sent: %d", stats['bytes_sent'])
    log.info("  Bytes received: %d", stats['bytes_received'])
    log.info("  Connections: %d", stats['connections_created'])
    log.info("  Transport switches: %d", stats['transports_switched'])


async def run_forward_loop(manager: TransportManager, listen_port: int) -> None:
    """
    Run SOCKS5 to transport forwarding loop.
    
    This is a simplified version - full implementation would
    integrate with the existing SOCKS5 handler from tg_ws_proxy.py
    """
    # For now, just keep running and monitoring transport
    while True:
        await asyncio.sleep(1)
        
        # Print periodic stats
        stats = manager.get_stats()
        if stats['bytes_sent'] > 0 or stats['bytes_received'] > 0:
            log.debug("Stats: sent=%d, recv=%d, status=%s",
                     stats['bytes_sent'],
                     stats['bytes_received'],
                     stats['status'])


def main() -> None:
    """Main entry point."""
    ap = argparse.ArgumentParser(
        description='TG WS Proxy - Enhanced Transport Runner'
    )
    
    ap.add_argument('--port', type=int, default=1080,
                    help='Local SOCKS5 listen port (default: 1080)')
    
    # Transport selection
    ap.add_argument('--transport', type=str, default='auto',
                    choices=['auto', 'websocket', 'http2', 'quic', 'meek', 
                             'shadowsocks', 'tuic', 'reality'],
                    help='Transport protocol (default: auto)')
    ap.add_argument('--transport-host', type=str, default=None,
                    help='Transport server host')
    ap.add_argument('--transport-port', type=int, default=443,
                    help='Transport server port (default: 443)')
    ap.add_argument('--transport-path', type=str, default='/api',
                    help='Transport path for HTTP/2 (default: /api)')
    
    # Meek settings
    ap.add_argument('--meek-cdn', type=str, default='cloudflare',
                    choices=['cloudflare', 'google', 'amazon', 'microsoft'],
                    help='CDN for Meek transport')
    
    # Shadowsocks settings
    ap.add_argument('--ss-method', type=str, default='chacha20-ietf-poly1305',
                    help='Shadowsocks encryption method')
    ap.add_argument('--ss-password', type=str, default='',
                    help='Shadowsocks password')
    
    # Reality settings
    ap.add_argument('--reality-pubkey', type=str, default='',
                    help='Reality server public key')
    ap.add_argument('--reality-shortid', type=str, default='',
                    help='Reality server short ID')
    ap.add_argument('--reality-sni', type=str, default='www.microsoft.com',
                    help='Reality SNI server name')
    
    # Advanced
    ap.add_argument('--auto-select', action='store_true', default=True,
                    help='Auto-select best transport')
    ap.add_argument('--health-interval', type=float, default=30.0,
                    help='Health check interval (default: 30s)')
    
    ap.add_argument('-v', '--verbose', action='store_true',
                    help='Verbose logging')
    
    args = ap.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(asctime)s  %(levelname)-5s  %(message)s',
        datefmt='%H:%M:%S',
    )
    
    # Run
    try:
        asyncio.run(run_proxy_with_transport(args))
    except KeyboardInterrupt:
        log.info("Interrupted")


if __name__ == '__main__':
    main()
