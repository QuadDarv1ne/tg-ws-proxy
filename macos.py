#!/usr/bin/env python3
"""
macOS native menu bar application for TG WS Proxy.

Uses rumps for native macOS menu bar integration.
Supports Universal binary (Apple Silicon + Intel).

Requirements:
    pip install -r requirements.txt
    pip install rumps

Usage:
    python macos.py
"""

from __future__ import annotations

import asyncio as _asyncio
import json
import logging
import os
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Optional

import psutil

try:
    import rumps
except ImportError:
    rumps = None
    print("rumps not installed. Install with: pip install rumps")
    sys.exit(1)

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    Image = ImageDraw = ImageFont = None

try:
    import pyperclip
except ImportError:
    pyperclip = None

import proxy.tg_ws_proxy as tg_ws_proxy

APP_NAME = "TgWsProxy"
APP_DIR = Path.home() / "Library" / "Application Support" / APP_NAME
CONFIG_FILE = APP_DIR / "config.json"
LOG_FILE = APP_DIR / "proxy.log"
FIRST_RUN_MARKER = APP_DIR / ".first_run_done"
IPV6_WARN_MARKER = APP_DIR / ".ipv6_warned"
MENUBAR_ICON_PATH = APP_DIR / "menubar_icon.png"

DEFAULT_CONFIG = {
    "port": 1080,
    "host": "127.0.0.1",
    "dc_ip": ["2:149.154.167.220", "4:149.154.167.220"],
    "verbose": False,
}

_proxy_thread: Optional[threading.Thread] = None
_async_stop: Optional[object] = None
_app: Optional[object] = None
_config: dict = {}
_exiting: bool = False
_lock_file_path: Optional[Path] = None

log = logging.getLogger("tg-ws-tray")


# Single-instance lock

def _same_process(lock_meta: dict, proc: psutil.Process) -> bool:
    try:
        lock_ct = float(lock_meta.get("create_time", 0.0))
        proc_ct = float(proc.create_time())
        if lock_ct > 0 and abs(lock_ct - proc_ct) > 1.0:
            return False
    except Exception:
        return False

    frozen = bool(getattr(sys, "frozen", False))
    if frozen:
        return APP_NAME.lower() in proc.name().lower()
    return False


def _release_lock():
    global _lock_file_path
    if not _lock_file_path:
        return
    try:
        _lock_file_path.unlink(missing_ok=True)
    except Exception:
        pass
    _lock_file_path = None


def _acquire_lock() -> bool:
    global _lock_file_path
    _ensure_dirs()
    lock_files = list(APP_DIR.glob("*.lock"))

    for f in lock_files:
        pid = None
        meta: dict = {}

        try:
            pid = int(f.stem)
        except Exception:
            f.unlink(missing_ok=True)
            continue

        try:
            raw = f.read_text(encoding="utf-8").strip()
            if raw:
                meta = json.loads(raw)
        except Exception:
            meta = {}

        try:
            proc = psutil.Process(pid)
            if _same_process(meta, proc):
                return False
        except Exception:
            pass

        f.unlink(missing_ok=True)

    lock_file = APP_DIR / f"{os.getpid()}.lock"
    try:
        proc = psutil.Process(os.getpid())
        payload = {"create_time": proc.create_time()}
        lock_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    except Exception:
        lock_file.touch()

    _lock_file_path = lock_file
    return True


def _ensure_dirs():
    APP_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> dict:
    _ensure_dirs()
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, encoding="utf-8") as f:
                data = json.load(f)
            for k, v in DEFAULT_CONFIG.items():
                data.setdefault(k, v)
            return data
        except Exception as exc:
            log.warning("Failed to load config: %s", exc)
    return dict(DEFAULT_CONFIG)


def save_config(cfg: dict):
    _ensure_dirs()
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def setup_logging(verbose: bool = False):
    _ensure_dirs()
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if verbose else logging.INFO)

    fh = logging.FileHandler(str(LOG_FILE), encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s  %(levelname)-5s  %(name)s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"))
    root.addHandler(fh)

    if not getattr(sys, "frozen", False):
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.DEBUG if verbose else logging.INFO)
        ch.setFormatter(logging.Formatter(
            "%(asctime)s  %(levelname)-5s  %(message)s",
            datefmt="%H:%M:%S"))
        root.addHandler(ch)


def _has_ipv6_enabled() -> bool:
    import socket as _sock
    try:
        addrs = _sock.getaddrinfo(_sock.gethostname(), None, _sock.AF_INET6)
        for addr in addrs:
            ip = addr[4][0]
            if ip and not ip.startswith('::1') and not ip.startswith('fe80::1'):
                return True
    except Exception:
        pass
    try:
        s = _sock.socket(_sock.AF_INET6, _sock.SOCK_STREAM)
        s.bind(('::1', 0))
        s.close()
        return True
    except Exception:
        return False


def _create_menubar_icon() -> Optional[str]:
    """Create a simple PNG icon for menu bar."""
    if Image is None:
        return None

    _ensure_dirs()
    size = 22
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Blue circle
    margin = 2
    draw.ellipse([margin, margin, size - margin, size - margin],
                 fill=(51, 144, 236, 255))

    # White "T"
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", size=14)
    except Exception:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), "T", font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = (size - tw) // 2 - bbox[0]
    ty = (size - th) // 2 - bbox[1]
    draw.text((tx, ty), "T", fill=(255, 255, 255, 255), font=font)

    img.save(str(MENUBAR_ICON_PATH), "PNG")
    return str(MENUBAR_ICON_PATH)


class TGWSProxyApp(rumps.App):
    """Native macOS menu bar application for TG WS Proxy."""

    def __init__(self):
        icon_path = _create_menubar_icon()
        super().__init__(APP_NAME, icon=icon_path)

        self._config = load_config()
        self._proxy_thread = None
        self._async_stop = None

        # Menu items
        self.status_item = rumps.MenuItem("Status: Stopped")
        self.open_tg_item = rumps.MenuItem("Open in Telegram", self._on_open_in_telegram)
        self.stats_item = rumps.MenuItem("Statistics", self._on_show_stats)
        self.restart_item = rumps.MenuItem("Restart Proxy", self._on_restart)
        self.settings_item = rumps.MenuItem("Settings...", self._on_edit_config)
        self.logs_item = rumps.MenuItem("Open Logs", self._on_open_logs)
        self.quit_item = rumps.MenuItem("Quit", self._on_quit)

        self.menu = [
            self.status_item,
            None,
            self.open_tg_item,
            self.stats_item,
            self.restart_item,
            None,
            self.settings_item,
            self.logs_item,
            None,
            self.quit_item,
        ]

        # Start proxy on launch
        self._start_proxy()

    def _start_proxy(self):
        """Start the proxy server in background thread."""
        if self._proxy_thread and self._proxy_thread.is_alive():
            return

        cfg = self._config
        port = cfg.get("port", DEFAULT_CONFIG["port"])
        host = cfg.get("host", DEFAULT_CONFIG["host"])
        dc_ip_list = cfg.get("dc_ip", DEFAULT_CONFIG["dc_ip"])
        verbose = cfg.get("verbose", False)

        try:
            dc_opt = tg_ws_proxy.parse_dc_ip_list(dc_ip_list)
        except ValueError as e:
            log.error("Bad config dc_ip: %s", e)
            rumps.notification("Error", "Configuration Error", str(e))
            return

        log.info("Starting proxy on %s:%d ...", host, port)

        def run_proxy():
            loop = _asyncio.new_event_loop()
            _asyncio.set_event_loop(loop)
            stop_ev = _asyncio.Event()
            self._async_stop = (loop, stop_ev)

            try:
                loop.run_until_complete(
                    tg_ws_proxy._run(port, dc_opt, stop_event=stop_ev, host=host))
            except Exception as exc:
                log.error("Proxy thread crashed: %s", exc)
                rumps.notification("Error", "Proxy Failed", str(exc))
            finally:
                loop.close()
                self._async_stop = None

        self._proxy_thread = threading.Thread(target=run_proxy, daemon=True, name="proxy")
        self._proxy_thread.start()
        self.status_item.title = "Status: Running"

    def _stop_proxy(self):
        """Stop the proxy server."""
        if self._async_stop:
            loop, stop_ev = self._async_stop
            loop.call_soon_threadsafe(stop_ev.set)
            if self._proxy_thread:
                self._proxy_thread.join(timeout=2)
        self._proxy_thread = None
        self.status_item.title = "Status: Stopped"
        log.info("Proxy stopped")

    def _on_open_in_telegram(self, sender):
        port = self._config.get("port", DEFAULT_CONFIG["port"])
        url = f"tg://socks?server=127.0.0.1&port={port}"
        webbrowser.open(url)

    def _on_show_stats(self, sender):
        stats = tg_ws_proxy.get_stats()
        summary = (
            f"Connections: {stats['connections_total']}\n"
            f"WebSocket: {stats['connections_ws']}\n"
            f"TCP Fallback: {stats['connections_tcp_fallback']}\n"
            f"Traffic Up: {self._human_bytes(stats['bytes_up'])}\n"
            f"Traffic Down: {self._human_bytes(stats['bytes_down'])}"
        )
        rumps.notification("Proxy Statistics", "", summary)

    def _on_restart(self, sender):
        self._stop_proxy()
        time.sleep(0.3)
        self._start_proxy()

    def _on_edit_config(self, sender):
        # Open config file in default editor
        if CONFIG_FILE.exists():
            subprocess.run(["open", "-a", "TextEdit", str(CONFIG_FILE)])
        else:
            save_config(self._config)
            subprocess.run(["open", "-a", "TextEdit", str(CONFIG_FILE)])

    def _on_open_logs(self, sender):
        if LOG_FILE.exists():
            subprocess.run(["open", str(LOG_FILE)])
        else:
            rumps.notification("Logs", "No log file found", "")

    def _on_quit(self, sender):
        self._stop_proxy()
        self.quit()

    @staticmethod
    def _human_bytes(n: int) -> str:
        for unit in ('B', 'KB', 'MB', 'GB'):
            if abs(n) < 1024:
                return f"{n:.1f} {unit}"
            n /= 1024
        return f"{n:.1f} TB"


def main():
    """Main entry point."""
    global _app

    if not _acquire_lock():
        print("Another instance is already running")
        sys.exit(1)

    _ensure_dirs()

    if LOG_FILE.exists():
        try:
            LOG_FILE.unlink()
        except Exception:
            pass

    setup_logging()
    log.info("TG WS Proxy macOS app starting")

    try:
        _app = TGWSProxyApp()
        _app.run()
    except Exception as e:
        log.error("Fatal error: %s", e)
        _release_lock()
        sys.exit(1)

    _release_lock()


if __name__ == "__main__":
    main()
