"""
Cloudflare WARP Integration.

Provides integration with Cloudflare WARP and Cloudflare Tunnel:
- WARP SOCKS proxy interface
- Cloudflare Tunnel (cloudflared)
- Domain fronting through Cloudflare CDN
- WARP routing configuration

Author: Dupley Maxim Igorevich
© 2026 Dupley Maxim Igorevich. All rights reserved.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import socket
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger('tg-ws-cloudflare')


@dataclass
class WARPConfig:
    """Cloudflare WARP configuration."""
    enabled: bool = True
    socks_port: int = 40000  # Default WARP SOCKS port
    warp_license_key: str = ""  # Optional license key
    team_name: str = ""  # Cloudflare Zero Trust team name
    team_id: str = ""
    access_client_id: str = ""
    access_client_secret: str = ""
    # Tunnel configuration
    tunnel_enabled: bool = False
    tunnel_id: str = ""
    tunnel_token: str = ""
    tunnel_config_path: str = ""
    # Domain fronting
    domain_fronting_enabled: bool = False
    front_domain: str = "www.cloudflare.com"
    # Routing
    routing_enabled: bool = False
    routing_rules: list[dict] = field(default_factory=list)


@dataclass
class WARPStatus:
    """WARP connection status."""
    is_connected: bool = False
    account_type: str = ""  # Free, Plus, Teams
    device_id: str = ""
    warp_enabled: bool = False
    mode: str = ""  # proxy, gateway
    latency_ms: float = 0.0
    upload_speed_mbps: float = 0.0
    download_speed_mbps: float = 0.0
    data_used_mb: float = 0.0


class CloudflareWARPManager:
    """
    Cloudflare WARP manager.
    
    Features:
    - WARP SOCKS proxy interface
    - Cloudflare Tunnel (cloudflared)
    - Domain fronting
    - WARP routing rules
    - Status monitoring
    """
    
    # Default paths
    WARP_CLI_PATH = "C:\\Program Files\\Cloudflare\\Cloudflare WARP\\warp-cli.exe"
    CLOUDFLARED_PATH = "cloudflared.exe"
    
    def __init__(self, config: WARPConfig | None = None):
        self.config = config or WARPConfig()
        self._warp_process: subprocess.Popen | None = None
        self._tunnel_process: subprocess.Popen | None = None
        self._is_initialized = False
        
    async def initialize(self) -> bool:
        """
        Initialize WARP connection.
        
        Returns:
            True if successful
        """
        try:
            log.info("Initializing Cloudflare WARP...")
            
            # Check if WARP CLI is available
            if not self._check_warp_cli():
                log.warning("WARP CLI not found, attempting to use SOCKS interface")
            
            # Configure WARP if license key provided
            if self.config.warp_license_key:
                await self._configure_warp_license()
            
            # Configure Cloudflare Zero Trust if team credentials provided
            if self.config.team_name and self.config.team_id:
                await self._configure_teams()
            
            # Start tunnel if enabled
            if self.config.tunnel_enabled:
                await self._start_tunnel()
            
            self._is_initialized = True
            log.info("Cloudflare WARP initialized")
            return True
            
        except Exception as e:
            log.error("Failed to initialize WARP: %s", e)
            return False
    
    def _check_warp_cli(self) -> bool:
        """Check if WARP CLI is available."""
        if os.path.exists(self.WARP_CLI_PATH):
            return True
        
        # Check in PATH
        warp_path = shutil.which("warp-cli")
        return warp_path is not None
    
    async def _configure_warp_license(self) -> None:
        """Configure WARP with license key."""
        try:
            # Use warp-cli to set license key
            result = await asyncio.create_subprocess_exec(
                self.WARP_CLI_PATH,
                "set-license", self.config.warp_license_key,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await result.communicate()
            
            if result.returncode == 0:
                log.info("WARP license key configured")
            else:
                log.warning("Failed to set WARP license: %s", stderr.decode())
                
        except Exception as e:
            log.error("Failed to configure WARP license: %s", e)
    
    async def _configure_teams(self) -> None:
        """Configure Cloudflare Zero Trust (Teams)."""
        try:
            # Create teams configuration
            teams_config = {
                "team_domain": f"{self.config.team_name}.teams.cloudflare.com",
                "client_id": self.config.access_client_id,
                "client_secret": self.config.access_client_secret,
            }
            
            config_dir = Path(os.getenv("APPDATA", "")) / "Cloudflare-WARP"
            config_dir.mkdir(parents=True, exist_ok=True)
            
            config_file = config_dir / "teams_config.json"
            with open(config_file, 'w') as f:
                json.dump(teams_config, f, indent=2)
            
            log.info("Cloudflare Teams configured: %s", self.config.team_name)
            
        except Exception as e:
            log.error("Failed to configure Teams: %s", e)
    
    async def _start_tunnel(self) -> None:
        """Start Cloudflare Tunnel (cloudflared)."""
        try:
            if not self.config.tunnel_id or not self.config.tunnel_token:
                log.error("Tunnel ID or token not provided")
                return
            
            # Create tunnel configuration
            tunnel_config = {
                "tunnel": self.config.tunnel_id,
                "credentials-file": self.config.tunnel_config_path,
                "ingress": [
                    {
                        "service": f"socks5://127.0.0.1:{self.config.socks_port}",
                        "originRequest": {
                            "noTLSVerify": True
                        }
                    },
                    {"service": "http_status:404"}  # Catch-all
                ]
            }
            
            # Write tunnel config
            config_path = Path(tempfile.gettempdir()) / f"cloudflared_{self.config.tunnel_id}.yml"
            import yaml
            with open(config_path, 'w') as f:
                yaml.dump(tunnel_config, f)
            
            # Start cloudflared
            self._tunnel_process = await asyncio.create_subprocess_exec(
                self.CLOUDFLARED_PATH,
                "tunnel",
                "--config", str(config_path),
                "run",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            log.info("Cloudflare Tunnel started: %s", self.config.tunnel_id)
            
        except Exception as e:
            log.error("Failed to start tunnel: %s", e)
    
    async def get_status(self) -> WARPStatus:
        """
        Get WARP connection status.
        
        Returns:
            WARPStatus object
        """
        status = WARPStatus()
        
        try:
            # Check if WARP SOCKS port is listening
            if await self._check_port_listening(self.config.socks_port):
                status.is_connected = True
                status.warp_enabled = True
            
            # Try to get status from warp-cli
            if self._check_warp_cli():
                cli_status = await self._get_warp_cli_status()
                if cli_status:
                    status.update(cli_status)
            
            # Measure latency through WARP
            if status.is_connected:
                status.latency_ms = await self._measure_warp_latency()
            
        except Exception as e:
            log.error("Failed to get WARP status: %s", e)
        
        return status
    
    async def _check_port_listening(self, port: int) -> bool:
        """Check if port is listening."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('127.0.0.1', port))
            sock.close()
            return result == 0
        except Exception:
            return False
    
    async def _get_warp_cli_status(self) -> dict | None:
        """Get status from warp-cli."""
        try:
            result = await asyncio.create_subprocess_exec(
                self.WARP_CLI_PATH,
                "status",
                "--output", "json",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, _ = await result.communicate()
            
            if result.returncode == 0:
                return json.loads(stdout.decode())
                
        except Exception:
            pass
        
        return None
    
    async def _measure_warp_latency(self) -> float:
        """Measure latency through WARP."""
        try:
            # Connect to Cloudflare through WARP SOCKS
            start = time.monotonic()
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            
            # Configure SOCKS proxy
            import socks
            socks.set_default_proxy(socks.SOCKS5, '127.0.0.1', self.config.socks_port)
            
            sock.connect(('1.1.1.1', 53))  # Cloudflare DNS
            sock.close()
            
            latency = (time.monotonic() - start) * 1000
            return latency
            
        except Exception:
            return 0.0
    
    async def set_routing_rules(self, rules: list[dict]) -> bool:
        """
        Set WARP routing rules.
        
        Args:
            rules: List of routing rules
                Example: [
                    {"destination": "192.168.0.0/16", "action": "exclude"},
                    {"destination": "10.0.0.0/8", "action": "exclude"},
                ]
        
        Returns:
            True if successful
        """
        try:
            self.config.routing_rules = rules
            self.config.routing_enabled = True
            
            # Apply routing rules through warp-cli
            for rule in rules:
                destination = rule.get('destination', '')
                action = rule.get('action', 'include')
                
                if action == 'exclude':
                    await self._add_route_exclude(destination)
                else:
                    await self._add_route_include(destination)
            
            log.info("WARP routing rules configured: %d rules", len(rules))
            return True
            
        except Exception as e:
            log.error("Failed to set routing rules: %s", e)
            return False
    
    async def _add_route_exclude(self, destination: str) -> None:
        """Add route exclusion."""
        try:
            result = await asyncio.create_subprocess_exec(
                self.WARP_CLI_PATH,
                "add-route", destination,
                "--action", "exclude",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await result.communicate()
        except Exception:
            pass
    
    async def _add_route_include(self, destination: str) -> None:
        """Add route inclusion."""
        try:
            result = await asyncio.create_subprocess_exec(
                self.WARP_CLI_PATH,
                "add-route", destination,
                "--action", "include",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await result.communicate()
        except Exception:
            pass
    
    def get_domain_fronting_config(self) -> dict:
        """
        Get domain fronting configuration.
        
        Returns:
            Configuration for domain fronting through Cloudflare
        """
        return {
            'enabled': self.config.domain_fronting_enabled,
            'front_domain': self.config.front_domain,
            'cdn': 'cloudflare',
            'headers': {
                'Host': self.config.front_domain,
            }
        }
    
    async def cleanup(self) -> None:
        """Cleanup WARP connections."""
        try:
            # Stop tunnel process
            if self._tunnel_process:
                self._tunnel_process.terminate()
                try:
                    await asyncio.wait_for(
                        asyncio.create_subprocess_exec(
                            self.CLOUDFLARED_PATH, "tunnel", "cleanup"
                        ).communicate(),
                        timeout=10
                    )
                except asyncio.TimeoutError:
                    self._tunnel_process.kill()
                self._tunnel_process = None
            
            log.info("Cloudflare WARP cleanup completed")
            
        except Exception as e:
            log.error("WARP cleanup error: %s", e)
    
    def __del__(self):
        """Destructor."""
        if self._tunnel_process or self._warp_process:
            asyncio.create_task(self.cleanup())


# Global WARP manager instance
_warp_manager: CloudflareWARPManager | None = None


def get_warp_manager() -> CloudflareWARPManager:
    """Get or create global WARP manager."""
    global _warp_manager
    if _warp_manager is None:
        _warp_manager = CloudflareWARPManager()
    return _warp_manager


async def init_warp(config: WARPConfig | None = None) -> CloudflareWARPManager:
    """Initialize global WARP manager."""
    global _warp_manager
    _warp_manager = CloudflareWARPManager(config)
    await _warp_manager.initialize()
    return _warp_manager


__all__ = [
    'WARPConfig',
    'WARPStatus',
    'CloudflareWARPManager',
    'get_warp_manager',
    'init_warp',
]
