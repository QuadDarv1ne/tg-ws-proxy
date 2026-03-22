"""
Console Dashboard for TG WS Proxy.

Provides a real-time text-based user interface for monitoring
and managing the proxy server.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Callable

try:
    from rich import box
    from rich.console import Console
    from rich.layout import Layout
    from rich.live import Live
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich.typing import RenderableType  # type: ignore[import-not-found]
    HAS_RICH = True
except ImportError:
    HAS_RICH = False
    RenderableType = None

from .stats import _human_bytes

log = logging.getLogger("tg-ws-proxy-dashboard")


class ConsoleDashboard:
    """
    Real-time console dashboard for proxy monitoring.

    Displays:
    - Connection statistics
    - Traffic rates
    - WebSocket pool status
    - Recent events log
    """

    def __init__(
        self,
        get_stats_fn: Callable[[], dict],
        refresh_interval: float = 1.0,
        enable_colors: bool = True,
    ):
        self.get_stats_fn = get_stats_fn
        self.refresh_interval = refresh_interval
        self.enable_colors = enable_colors
        self.running = False
        self.console: Console | None = None
        self.events_log: list[str] = []
        self.max_events = 10

    def add_event(self, event: str) -> None:
        """Add an event to the log."""
        timestamp = time.strftime("%H:%M:%S")
        self.events_log.append(f"[{timestamp}] {event}")
        # Keep only recent events
        if len(self.events_log) > self.max_events:
            self.events_log.pop(0)

    def _clear_screen(self) -> None:
        """Clear terminal screen."""
        os.system('cls' if os.name == 'nt' else 'clear')

    def _render_simple(self, stats: dict) -> str:
        """Render dashboard as plain text (no rich)."""
        lines = []
        lines.append("=" * 60)
        lines.append("  TG WS Proxy - Console Dashboard")
        lines.append("=" * 60)
        lines.append("")

        # Statistics
        lines.append("📊 STATISTICS:")
        lines.append(f"  Total Connections:     {stats.get('connections_total', 0)}")
        lines.append(f"  WebSocket:             {stats.get('connections_ws', 0)}")
        lines.append(f"  TCP Fallback:          {stats.get('connections_tcp_fallback', 0)}")
        lines.append(f"  HTTP Rejected:         {stats.get('connections_http_rejected', 0)}")
        lines.append(f"  Passthrough:           {stats.get('connections_passthrough', 0)}")
        lines.append(f"  WS Errors:             {stats.get('ws_errors', 0)}")
        lines.append("")

        # Traffic
        lines.append("📈 TRAFFIC:")
        lines.append(f"  Upload:                {_human_bytes(stats.get('bytes_up', 0))}")
        lines.append(f"  Download:              {_human_bytes(stats.get('bytes_down', 0))}")
        lines.append("")

        # Pool
        pool_hits = stats.get('pool_hits', 0)
        pool_misses = stats.get('pool_misses', 0)
        pool_total = pool_hits + pool_misses
        pool_rate = (pool_hits / pool_total * 100) if pool_total > 0 else 0
        lines.append("🔗 WebSocket POOL:")
        lines.append(f"  Hits:                  {pool_hits}")
        lines.append(f"  Misses:                {pool_misses}")
        lines.append(f"  Hit Rate:              {pool_rate:.1f}%")
        lines.append("")

        # Events
        if self.events_log:
            lines.append("📝 RECENT EVENTS:")
            for event in self.events_log[-5:]:
                lines.append(f"  {event}")

        lines.append("")
        lines.append("Press Ctrl+C to exit")
        lines.append("=" * 60)

        return "\n".join(lines)

    def _render_rich(self, stats: dict) -> Panel:
        """Render dashboard using Rich library."""
        # Statistics table
        stats_table = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
        stats_table.add_column("Label", style="cyan")
        stats_table.add_column("Value", style="bold white")

        stats_table.add_row("Total Connections", str(stats.get('connections_total', 0)))
        stats_table.add_row("WebSocket", str(stats.get('connections_ws', 0)))
        stats_table.add_row("TCP Fallback", str(stats.get('connections_tcp_fallback', 0)))
        stats_table.add_row("HTTP Rejected", str(stats.get('connections_http_rejected', 0)))
        stats_table.add_row("WS Errors", str(stats.get('ws_errors', 0)))

        # Traffic table
        traffic_table = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
        traffic_table.add_column("Label", style="green")
        traffic_table.add_column("Value", style="bold white")

        traffic_table.add_row("Upload", _human_bytes(stats.get('bytes_up', 0)))
        traffic_table.add_row("Download", _human_bytes(stats.get('bytes_down', 0)))

        # Pool table
        pool_hits = stats.get('pool_hits', 0)
        pool_misses = stats.get('pool_misses', 0)
        pool_total = pool_hits + pool_misses
        pool_rate = (pool_hits / pool_total * 100) if pool_total > 0 else 0

        pool_table = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
        pool_table.add_column("Label", style="yellow")
        pool_table.add_column("Value", style="bold white")

        pool_table.add_row("Hits", str(pool_hits))
        pool_table.add_row("Misses", str(pool_misses))
        pool_table.add_row("Hit Rate", f"{pool_rate:.1f}%")

        # Events
        events_text = Text()
        for event in self.events_log[-5:]:
            events_text.append(event + "\n", style="dim")

        # Layout
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=5),
        )

        # Header
        header_text = Text()
        header_text.append("TG WS Proxy", style="bold blue")
        header_text.append(" - Console Dashboard", style="dim")
        layout["header"].update(Panel(header_text, box=box.ROUNDED))

        # Body
        body_layout = Layout()
        body_layout.split_row(
            Layout(name="stats"),
            Layout(name="traffic"),
            Layout(name="pool"),
        )

        body_layout["stats"].update(Panel(stats_table, title="📊 Statistics", box=box.ROUNDED))
        body_layout["traffic"].update(Panel(traffic_table, title="📈 Traffic", box=box.ROUNDED))
        body_layout["pool"].update(Panel(pool_table, title="🔗 WebSocket Pool", box=box.ROUNDED))

        layout["body"].update(body_layout)

        # Footer with events
        events_panel = Panel(events_text, title="📝 Recent Events", box=box.ROUNDED)
        layout["footer"].update(events_panel)

        return layout  # type: ignore[return-value]

    async def run(self) -> None:
        """Run the dashboard."""
        if not HAS_RICH:
            await self._run_simple()
        else:
            await self._run_rich()

    async def _run_simple(self) -> None:
        """Run simple text dashboard."""
        self.running = True
        self._clear_screen()

        try:
            while self.running:
                stats = self.get_stats_fn()
                output = self._render_simple(stats)
                print(output, end="\r", flush=True)
                await asyncio.sleep(self.refresh_interval)
                self._clear_screen()
        except asyncio.CancelledError:
            pass
        except KeyboardInterrupt:
            pass
        finally:
            self._clear_screen()
            print("Dashboard stopped.")

    async def _run_rich(self) -> None:
        """Run Rich-based dashboard."""
        self.running = True
        self.console = Console()

        def generate_table() -> RenderableType:
            stats = self.get_stats_fn()
            return self._render_rich(stats)

        try:
            with Live(generate_table(), refresh_per_second=1.0/self.refresh_interval,
                      screen=True, redirect_stderr=False) as live:
                while self.running:
                    await asyncio.sleep(self.refresh_interval)
                    live.update(generate_table())
        except asyncio.CancelledError:
            pass
        except KeyboardInterrupt:
            pass

    def stop(self) -> None:
        """Stop the dashboard."""
        self.running = False


async def run_dashboard(get_stats_fn: Callable[[], dict], refresh_interval: float = 1.0) -> None:
    """
    Run console dashboard for proxy monitoring.

    Args:
        get_stats_fn: Function that returns proxy statistics dict
        refresh_interval: Update interval in seconds
    """
    if not HAS_RICH:
        log.warning("Rich library not installed. Install with: pip install rich")
        log.info("Using simple text dashboard")

    dashboard = ConsoleDashboard(get_stats_fn, refresh_interval)

    try:
        await dashboard.run()
    except KeyboardInterrupt:
        dashboard.stop()


def main() -> None:
    """Main entry point for standalone dashboard."""
    import argparse

    parser = argparse.ArgumentParser(description="TG WS Proxy Console Dashboard")
    parser.add_argument("--refresh", type=float, default=1.0,
                        help="Refresh interval in seconds (default: 1.0)")
    parser.add_argument("--no-colors", action="store_true",
                        help="Disable colors")
    args = parser.parse_args()

    # Dummy stats function for testing
    def dummy_stats() -> dict:
        return {
            "connections_total": 0,
            "connections_ws": 0,
            "connections_tcp_fallback": 0,
            "connections_http_rejected": 0,
            "connections_passthrough": 0,
            "ws_errors": 0,
            "bytes_up": 0,
            "bytes_down": 0,
            "pool_hits": 0,
            "pool_misses": 0,
        }

    dashboard = ConsoleDashboard(dummy_stats, args.refresh, not args.no_colors)

    try:
        asyncio.run(dashboard.run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
