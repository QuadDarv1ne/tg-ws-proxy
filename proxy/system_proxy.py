"""
System Proxy Configuration for Windows.

Provides system-wide proxy configuration:
- Windows Registry proxy settings
- WinHTTP proxy configuration
- Proxy enable/disable with rollback

Author: Dupley Maxim Igorevich
© 2026 Dupley Maxim Igorevich. All rights reserved.
"""

from __future__ import annotations

import logging
import subprocess
import sys
from dataclasses import dataclass
from typing import Literal

log = logging.getLogger('tg-ws-system-proxy')

# Only import Windows modules on Windows
if sys.platform == 'win32':
    import winreg


@dataclass
class ProxyConfig:
    """Proxy configuration."""
    host: str = "127.0.0.1"
    port: int = 1080
    proxy_type: Literal["socks5", "http"] = "socks5"
    bypass_local: bool = True

    @property
    def proxy_string(self) -> str:
        """Get proxy string for Windows registry."""
        return f"{self.host}:{self.port}"

    @property
    def bypass_list(self) -> str:
        """Get bypass list for local addresses."""
        if self.bypass_local:
            return "localhost;127.*;10.*;<local>"
        return ""


class WindowsSystemProxy:
    """
    System-wide proxy configuration for Windows.
    
    Features:
    - Registry-based proxy settings
    - WinHTTP proxy configuration
    - Automatic rollback on failure
    - Backup/restore of original settings
    """

    def __init__(self):
        if sys.platform != 'win32':
            raise RuntimeError("WindowsSystemProxy is only supported on Windows")

        self.registry_path = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
        self._backup: dict | None = None

    def _read_registry_value(self, key: str, value_name: str):
        """Read registry value."""
        try:
            reg_key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                self.registry_path,
                0,
                winreg.KEY_READ
            )
            value, _ = winreg.QueryValueEx(reg_key, value_name)
            winreg.CloseKey(reg_key)
            return value
        except FileNotFoundError:
            return None

    def _write_registry_value(self, value_name: str, value, value_type: int = winreg.REG_DWORD) -> None:
        """Write registry value."""
        reg_key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            self.registry_path,
            0,
            winreg.KEY_SET_VALUE
        )
        winreg.SetValueEx(reg_key, value_name, 0, value_type, value)
        winreg.CloseKey(reg_key)

    def backup_settings(self) -> dict:
        """Backup current proxy settings."""
        self._backup = {
            'ProxyEnable': self._read_registry_value('ProxyEnable', 'ProxyEnable'),
            'ProxyServer': self._read_registry_value('ProxyServer', 'ProxyServer'),
            'ProxyOverride': self._read_registry_value('ProxyOverride', 'ProxyOverride'),
        }
        log.debug("Proxy settings backed up: %s", self._backup)
        return self._backup

    def restore_settings(self) -> None:
        """Restore backed up proxy settings."""
        if self._backup is None:
            log.warning("No backup to restore")
            return

        self._write_registry_value('ProxyEnable', self._backup['ProxyEnable'] or 0)
        if self._backup['ProxyServer']:
            self._write_registry_value('ProxyServer', self._backup['ProxyServer'], winreg.REG_SZ)
        if self._backup['ProxyOverride']:
            self._write_registry_value('ProxyOverride', self._backup['ProxyOverride'], winreg.REG_SZ)

        log.info("Proxy settings restored from backup")

    def enable_proxy(self, config: ProxyConfig) -> bool:
        """
        Enable system-wide proxy.
        
        Args:
            config: Proxy configuration
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Backup current settings
            self.backup_settings()

            # Enable proxy
            self._write_registry_value('ProxyEnable', 1)

            # Set proxy server
            self._write_registry_value('ProxyServer', config.proxy_string, winreg.REG_SZ)

            # Set bypass list
            if config.bypass_list:
                self._write_registry_value('ProxyOverride', config.bypass_list, winreg.REG_SZ)

            # Configure WinHTTP (for system services)
            self._configure_winhttp(config)

            log.info("System proxy enabled: %s", config.proxy_string)
            return True

        except Exception as e:
            log.error("Failed to enable system proxy: %s", e)
            if self._backup:
                self.restore_settings()
            return False

    def disable_proxy(self) -> bool:
        """
        Disable system-wide proxy.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Disable proxy
            self._write_registry_value('ProxyEnable', 0)

            # Clear WinHTTP proxy
            self._clear_winhttp()

            log.info("System proxy disabled")
            return True

        except Exception as e:
            log.error("Failed to disable system proxy: %s", e)
            return False

    def _configure_winhttp(self, config: ProxyConfig) -> None:
        """Configure WinHTTP proxy for system services."""
        try:
            # Use netsh for WinHTTP configuration
            cmd = [
                "netsh", "winhttp", "set", "proxy",
                f"{config.proxy_string}",
                f"{config.bypass_list}"
            ]
            subprocess.run(cmd, check=False, capture_output=True)
            log.debug("WinHTTP proxy configured")
        except Exception as e:
            log.debug("Failed to configure WinHTTP: %s", e)

    def _clear_winhttp(self) -> None:
        """Clear WinHTTP proxy configuration."""
        try:
            cmd = ["netsh", "winhttp", "reset", "proxy"]
            subprocess.run(cmd, check=False, capture_output=True)
            log.debug("WinHTTP proxy cleared")
        except Exception as e:
            log.debug("Failed to clear WinHTTP: %s", e)

    def is_enabled(self) -> bool:
        """Check if system proxy is enabled."""
        enabled = self._read_registry_value('ProxyEnable', 'ProxyEnable')
        return bool(enabled)

    def get_current_proxy(self) -> ProxyConfig | None:
        """Get current proxy configuration."""
        if not self.is_enabled():
            return None

        proxy_server = self._read_registry_value('ProxyServer', 'ProxyServer')
        if not proxy_server:
            return None

        # Parse proxy string
        if ':' in proxy_server:
            host, port = proxy_server.rsplit(':', 1)
            return ProxyConfig(host=host, port=int(port))

        return None


class LinuxSystemProxy:
    """System-wide proxy configuration for Linux (placeholder)."""

    def __init__(self):
        if sys.platform != 'linux':
            raise RuntimeError("LinuxSystemProxy is only supported on Linux")

    def enable_proxy(self, config: ProxyConfig) -> bool:
        """Enable proxy via environment variables."""
        # Set environment variables (temporary, for current session)
        import os
        os.environ['http_proxy'] = f"http://{config.proxy_string}"
        os.environ['https_proxy'] = f"http://{config.proxy_string}"
        os.environ['ftp_proxy'] = f"http://{config.proxy_string}"
        os.environ['no_proxy'] = config.bypass_list if config.bypass_list else "localhost,127.0.0.1"

        log.info("Linux proxy enabled (session only): %s", config.proxy_string)
        return True

    def disable_proxy(self) -> bool:
        """Disable proxy."""
        import os
        for var in ['http_proxy', 'https_proxy', 'ftp_proxy', 'no_proxy']:
            os.environ.pop(var, None)

        log.info("Linux proxy disabled")
        return True


class MacOSSystemProxy:
    """System-wide proxy configuration for macOS (placeholder)."""

    def __init__(self):
        if sys.platform != 'darwin':
            raise RuntimeError("MacOSSystemProxy is only supported on macOS")

    def enable_proxy(self, config: ProxyConfig) -> bool:
        """Enable proxy using networksetup."""
        try:
            # Get all network services
            result = subprocess.run(
                ["networksetup", "-listallnetworkservices"],
                capture_output=True,
                text=True,
                check=True
            )

            services = result.stdout.strip().split('\n')

            for service in services:
                if service.startswith('*'):
                    continue  # Skip disabled services

                # Set SOCKS proxy
                subprocess.run(
                    ["networksetup", "-setsocksfirewallproxy", service, config.host, str(config.port)],
                    capture_output=True,
                    check=False
                )

                # Enable proxy
                subprocess.run(
                    ["networksetup", "-setsocksfirewallproxystate", service, "on"],
                    capture_output=True,
                    check=False
                )

            log.info("macOS proxy enabled: %s", config.proxy_string)
            return True

        except Exception as e:
            log.error("Failed to enable macOS proxy: %s", e)
            return False

    def disable_proxy(self) -> bool:
        """Disable proxy."""
        try:
            result = subprocess.run(
                ["networksetup", "-listallnetworkservices"],
                capture_output=True,
                text=True,
                check=True
            )

            services = result.stdout.strip().split('\n')

            for service in services:
                if service.startswith('*'):
                    continue

                subprocess.run(
                    ["networksetup", "-setsocksfirewallproxystate", service, "off"],
                    capture_output=True,
                    check=False
                )

            log.info("macOS proxy disabled")
            return True

        except Exception as e:
            log.error("Failed to disable macOS proxy: %s", e)
            return False


def get_system_proxy() -> WindowsSystemProxy | LinuxSystemProxy | MacOSSystemProxy:
    """Get system proxy manager for current platform."""
    if sys.platform == 'win32':
        return WindowsSystemProxy()
    elif sys.platform == 'linux':
        return LinuxSystemProxy()
    elif sys.platform == 'darwin':
        return MacOSSystemProxy()
    else:
        raise RuntimeError(f"Unsupported platform: {sys.platform}")


__all__ = [
    'ProxyConfig',
    'WindowsSystemProxy',
    'LinuxSystemProxy',
    'MacOSSystemProxy',
    'get_system_proxy',
]
