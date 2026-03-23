"""
Cloudflare Tunnel Integration for TG WS Proxy.

Provides Cloudflare Tunnel integration for bypassing ISP blocks:
- cloudflared binary management
- Tunnel configuration and lifecycle
- Automatic reconnection and health monitoring

Author: Dupley Maxim Igorevich
© 2026 Dupley Maxim Igorevich. All rights reserved.
"""

from __future__ import annotations

import logging
import os
import platform
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

log = logging.getLogger('tg-ws-cloudflare')


@dataclass
class CloudflareTunnelConfig:
    """Cloudflare Tunnel configuration."""
    tunnel_id: str = ""
    tunnel_name: str = "tg-ws-proxy"
    credentials_file: str = ""
    config_file: str = ""

    # Tunnel endpoint
    proxy_host: str = "127.0.0.1"
    proxy_port: int = 1080
    proxy_type: Literal["socks5", "http"] = "socks5"

    # Cloudflare settings
    hostname: str = ""  # Optional: custom hostname
    ingress_port: int = 1080

    # Advanced settings
    log_level: str = "info"
    metrics_port: int = 0  # 0 = disabled
    auto_reconnect: bool = True
    reconnect_delay: float = 5.0

    @property
    def proxy_url(self) -> str:
        """Get proxy URL for tunnel configuration."""
        return f"{self.proxy_type}://{self.proxy_host}:{self.proxy_port}"


@dataclass
class TunnelStatus:
    """Tunnel status information."""
    is_running: bool = False
    tunnel_id: str = ""
    connections: int = 0
    bytes_sent: int = 0
    bytes_received: int = 0
    uptime_seconds: float = 0.0
    last_error: str = ""
    cloudflare_ip: str = ""


class CloudflareTunnel:
    """
    Cloudflare Tunnel manager.

    Features:
    - Automatic cloudflared download
    - Tunnel lifecycle management
    - Configuration file generation
    - Health monitoring
    - Automatic reconnection
    """

    CLOUDFLARED_VERSION = "2024.3.0"
    DOWNLOAD_URLS = {
        'windows-amd64': 'https://github.com/cloudflare/cloudflared/releases/download/2024.3.0/cloudflared-windows-amd64.exe',
        'windows-386': 'https://github.com/cloudflare/cloudflared/releases/download/2024.3.0/cloudflared-windows-386.exe',
        'linux-amd64': 'https://github.com/cloudflare/cloudflared/releases/download/2024.3.0/cloudflared-linux-amd64',
        'linux-386': 'https://github.com/cloudflare/cloudflared/releases/download/2024.3.0/cloudflared-linux-386',
        'linux-arm': 'https://github.com/cloudflare/cloudflared/releases/download/2024.3.0/cloudflared-linux-arm',
        'linux-arm64': 'https://github.com/cloudflare/cloudflared/releases/download/2024.3.0/cloudflared-linux-arm64',
        'darwin-amd64': 'https://github.com/cloudflare/cloudflared/releases/download/2024.3.0/cloudflared-darwin-amd64',
        'darwin-arm64': 'https://github.com/cloudflare/cloudflared/releases/download/2024.3.0/cloudflared-darwin-arm64',
    }

    def __init__(self, config: CloudflareTunnelConfig | None = None):
        self.config = config or CloudflareTunnelConfig()
        self._process: subprocess.Popen | None = None
        self._cloudflared_path: Path | None = None
        self._running = False
        self._reconnect_attempts = 0
        self._start_time: float | None = None

        # Determine cloudflared path
        self._data_dir = Path(__file__).parent.parent / 'cloudflared'
        self._data_dir.mkdir(exist_ok=True)

        # Get cloudflared binary name for current platform
        if sys.platform == 'win32':
            self._cloudflared_name = 'cloudflared.exe'
        else:
            self._cloudflared_name = 'cloudflared'

        self._cloudflared_path = self._data_dir / self._cloudflared_name

    def _get_platform_key(self) -> str:
        """Get platform key for download URL."""
        system = platform.system().lower()
        machine = platform.machine().lower()

        if system == 'windows':
            return f'windows-{machine}'
        elif system == 'linux':
            if machine in ('arm', 'armv7l'):
                return 'linux-arm'
            elif machine == 'aarch64':
                return 'linux-arm64'
            else:
                return 'linux-amd64'
        elif system == 'darwin':
            if machine == 'arm64':
                return 'darwin-arm64'
            else:
                return 'darwin-amd64'

        raise RuntimeError(f"Unsupported platform: {system} {machine}")

    def download_cloudflared(self) -> bool:
        """
        Download cloudflared binary if not present.

        Returns:
            True if successful, False otherwise
        """
        if self._cloudflared_path.exists():
            log.debug("cloudflared already exists: %s", self._cloudflared_path)
            return True

        try:
            import ssl
            import urllib.request

            platform_key = self._get_platform_key()
            if platform_key not in self.DOWNLOAD_URLS:
                log.error("No cloudflared binary for platform: %s", platform_key)
                return False

            url = self.DOWNLOAD_URLS[platform_key]
            log.info("Downloading cloudflared from %s", url)

            # Download with SSL verification disabled (cloudflared is signed)
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

            with urllib.request.urlopen(url, context=context) as response:
                with open(self._cloudflared_path, 'wb') as f:
                    shutil.copyfileobj(response, f)

            # Make executable on Unix
            if sys.platform != 'win32':
                os.chmod(self._cloudflared_path, 0o755)

            log.info("cloudflared downloaded to %s", self._cloudflared_path)
            return True

        except Exception as e:
            log.error("Failed to download cloudflared: %s", e)
            return False

    def check_cloudflared(self) -> bool:
        """Check if cloudflared is available."""
        # Check local installation
        if self._cloudflared_path.exists():
            return True

        # Check system installation
        cloudflared_in_path = shutil.which('cloudflared')
        if cloudflared_in_path:
            self._cloudflared_path = Path(cloudflared_in_path)
            return True

        return False

    def get_cloudflared_version(self) -> str | None:
        """Get cloudflared version."""
        try:
            result = subprocess.run(
                [str(self._cloudflared_path), '--version'],
                capture_output=True,
                text=True,
                check=True
            )
            # Output: "cloudflared version 2024.3.0 (build 12345)"
            version = result.stdout.strip().split('version ')[1].split(' ')[0]
            return version
        except Exception as e:
            log.debug("Failed to get cloudflared version: %s", e)
            return None

    def generate_config(self) -> bool:
        """
        Generate tunnel configuration file.

        Returns:
            True if successful, False otherwise
        """
        config_content = self._generate_config_yaml()

        config_path = self._data_dir / 'config.yml'
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write(config_content)

        self.config.config_file = str(config_path)
        log.info("Tunnel config generated: %s", config_path)
        return True

    def _generate_config_yaml(self) -> str:
        """Generate YAML configuration content."""
        # Basic configuration
        config_lines = [
            f"tunnel: {self.config.tunnel_id}",
            f"credentials-file: {self.config.credentials_file}",
            "",
            "# Logging",
            f"loglevel: {self.config.log_level}",
            "",
            "# Ingress rules",
            "ingress:",
        ]

        # Add hostname rule if specified
        if self.config.hostname:
            config_lines.append(f"  - hostname: {self.config.hostname}")
            config_lines.append(f"    service: {self.config.proxy_url}")

        # Default rule - forward to proxy
        config_lines.append(f"  - service: {self.config.proxy_url}")

        # Catch-all rule
        config_lines.append("  - service: http_status:404")

        # Metrics (optional)
        if self.config.metrics_port > 0:
            config_lines.append("")
            config_lines.append("# Metrics")
            config_lines.append(f"metrics: 0.0.0.0:{self.config.metrics_port}")

        return '\n'.join(config_lines)

    def authenticate(self, token: str) -> bool:
        """
        Authenticate tunnel with Cloudflare.

        Args:
            token: Cloudflare tunnel token

        Returns:
            True if successful, False otherwise
        """
        try:
            credentials_path = self._data_dir / 'credentials.json'

            # Run authentication
            cmd = [
                str(self._cloudflared_path),
                'tunnel',
                'login',
                '--credentials-file', str(credentials_path),
            ]

            # Note: This requires manual browser authentication
            # For automated setup, use API token instead
            log.info("Starting authentication. Open browser to complete.")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

            if result.returncode == 0:
                self.config.credentials_file = str(credentials_path)
                log.info("Authentication successful")
                return True
            else:
                log.error("Authentication failed: %s", result.stderr)
                return False

        except subprocess.TimeoutExpired:
            log.error("Authentication timeout")
            return False
        except Exception as e:
            log.error("Authentication error: %s", e)
            return False

    def create_tunnel(self, tunnel_name: str | None = None) -> str | None:
        """
        Create new tunnel.

        Args:
            tunnel_name: Optional tunnel name

        Returns:
            Tunnel ID if successful, None otherwise
        """
        try:
            name = tunnel_name or self.config.tunnel_name

            cmd = [
                str(self._cloudflared_path),
                'tunnel',
                'create',
                '--name', name,
                '--credentials-file', str(self._data_dir / 'credentials.json'),
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )

            # Parse tunnel ID from output
            # Output format: "Created tunnel {name} with id {id}"
            for line in result.stdout.split('\n'):
                if 'id' in line:
                    tunnel_id = line.split('id')[-1].strip()
                    self.config.tunnel_id = tunnel_id
                    log.info("Tunnel created: %s (%s)", name, tunnel_id)
                    return tunnel_id

            return None

        except Exception as e:
            log.error("Failed to create tunnel: %s", e)
            return None

    def start(self) -> bool:
        """
        Start tunnel.

        Returns:
            True if successful, False otherwise
        """
        if self._running:
            log.warning("Tunnel already running")
            return False

        # Check cloudflared
        if not self.check_cloudflared():
            if not self.download_cloudflared():
                return False

        # Generate config if needed
        if not self.config.config_file:
            if not self.generate_config():
                return False

        try:
            # Start tunnel process
            cmd = [
                str(self._cloudflared_path),
                'tunnel',
                '--config', self.config.config_file,
                'run',
                self.config.tunnel_id,
            ]

            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            self._running = True
            self._start_time = time.time()
            self._reconnect_attempts = 0

            log.info("Tunnel started: %s", self.config.tunnel_id)

            # Start monitoring
            import threading
            monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            monitor_thread.start()

            return True

        except Exception as e:
            log.error("Failed to start tunnel: %s", e)
            return False

    def stop(self) -> None:
        """Stop tunnel."""
        if not self._running:
            return

        self._running = False

        if self._process:
            try:
                self._process.terminate()
                self._process.wait(timeout=10)
                log.info("Tunnel stopped")
            except subprocess.TimeoutExpired:
                self._process.kill()
                log.warning("Tunnel process killed")
            except Exception as e:
                log.error("Error stopping tunnel: %s", e)

            self._process = None
            self._start_time = None

    def _monitor_loop(self) -> None:
        """Monitor tunnel health and reconnect if needed."""
        while self._running:
            time.sleep(10)

            if self._process and self._process.poll() is not None:
                # Process died
                log.error("Tunnel process died: %s", self._process.stderr.read())

                if self.config.auto_reconnect and self._reconnect_attempts < 5:
                    self._reconnect_attempts += 1
                    log.info("Reconnecting (attempt %d)...", self._reconnect_attempts)
                    time.sleep(self.config.reconnect_delay)
                    self.start()
                else:
                    self._running = False

    def get_status(self) -> TunnelStatus:
        """Get tunnel status."""
        status = TunnelStatus(
            is_running=self._running,
            tunnel_id=self.config.tunnel_id,
        )

        if self._start_time:
            status.uptime_seconds = time.time() - self._start_time

        if self._process:
            # Check if process is running
            status.is_running = self._process.poll() is None

            if not status.is_running:
                status.last_error = "Process exited"

        return status

    def get_logs(self, lines: int = 50) -> list[str]:
        """Get recent tunnel logs."""
        if not self._process or not self._process.stderr:
            return []

        # Note: This is a placeholder - real implementation would need
        # to capture logs in a buffer or file
        return []


class CloudflareWARP:
    """
    Cloudflare WARP integration (placeholder).

    WARP provides WireGuard-based proxy with Cloudflare optimization.
    """

    def __init__(self):
        self.warp_cli = shutil.which('warp-cli')
        self._connected = False

    def is_installed(self) -> bool:
        """Check if WARP client is installed."""
        return self.warp_cli is not None

    def connect(self) -> bool:
        """Connect to WARP."""
        if not self.is_installed():
            log.error("WARP client not installed")
            return False

        try:
            subprocess.run([self.warp_cli, 'connect'], check=True, capture_output=True)
            self._connected = True
            log.info("WARP connected")
            return True
        except subprocess.CalledProcessError as e:
            log.error("WARP connect failed: %s", e.stderr.decode())
            return False

    def disconnect(self) -> bool:
        """Disconnect from WARP."""
        if not self.is_installed():
            return False

        try:
            subprocess.run([self.warp_cli, 'disconnect'], check=True, capture_output=True)
            self._connected = False
            log.info("WARP disconnected")
            return True
        except subprocess.CalledProcessError as e:
            log.error("WARP disconnect failed: %s", e.stderr.decode())
            return False

    def set_proxy_mode(self, port: int = 1080) -> bool:
        """Set WARP to proxy mode."""
        if not self.is_installed():
            return False

        try:
            subprocess.run([self.warp_cli, 'set-mode', 'proxy'], check=True, capture_output=True)
            subprocess.run([self.warp_cli, 'set-proxy-port', str(port)], check=True, capture_output=True)
            log.info("WARP proxy mode enabled on port %d", port)
            return True
        except subprocess.CalledProcessError as e:
            log.error("WARP set-proxy-mode failed: %s", e.stderr.decode())
            return False

    def get_status(self) -> dict:
        """Get WARP status."""
        if not self.is_installed():
            return {'installed': False}

        try:
            result = subprocess.run(
                [self.warp_cli, 'status'],
                capture_output=True,
                text=True,
                check=True
            )

            return {
                'installed': True,
                'connected': 'Connected' in result.stdout,
                'status': result.stdout.strip(),
            }
        except subprocess.CalledProcessError:
            return {'installed': True, 'connected': False, 'status': 'Error'}


__all__ = [
    'CloudflareTunnelConfig',
    'CloudflareTunnel',
    'CloudflareWARP',
    'TunnelStatus',
]
