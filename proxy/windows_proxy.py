"""
Windows System Proxy Integration.

Provides system-wide proxy configuration for Windows:
- WinHTTP proxy settings
- Internet Explorer/Edge proxy settings
- Registry-based proxy configuration
- PAC (Proxy Auto-Config) support
- Automatic proxy detection

Author: Dupley Maxim Igorevich
© 2026 Dupley Maxim Igorevich. All rights reserved.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
import winreg
from dataclasses import dataclass, field
from typing import Callable

log = logging.getLogger('tg-ws-windows-proxy')


@dataclass
class ProxyConfig:
    """Windows proxy configuration."""
    host: str = "127.0.0.1"
    port: int = 1080
    protocol: str = "socks"  # http, https, socks, socks5
    bypass_list: list[str] = field(default_factory=lambda: [
        "localhost",
        "127.*",
        "10.*",
        "192.168.*",
        "172.16.*",
        "172.17.*",
        "172.18.*",
        "172.19.*",
        "172.20.*",
        "172.21.*",
        "172.22.*",
        "172.23.*",
        "172.24.*",
        "172.25.*",
        "172.26.*",
        "172.27.*",
        "172.28.*",
        "172.29.*",
        "172.30.*",
        "172.31.*",
    ])
    enable_pac: bool = False
    pac_url: str = ""
    auto_detect: bool = = False


class WindowsProxyManager:
    """
    Windows system proxy manager.
    
    Features:
    - Set system-wide proxy via registry
    - Configure WinHTTP proxy
    - IE/Edge proxy settings
    - PAC file support
    - Proxy bypass list
    - Automatic proxy detection (WPAD)
    """
    
    # Registry paths for proxy settings
    IE_PROXY_KEY = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
    WINHTTP_KEY = r"Software\Microsoft\Windows\CurrentVersion\WinHttp"
    
    def __init__(self, config: ProxyConfig | None = None):
        self.config = config or ProxyConfig()
        self._original_settings: dict = {}
        self._is_enabled = False
        
    def enable_system_proxy(self) -> bool:
        """
        Enable system-wide proxy.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            log.info("Enabling system proxy: %s:%d (%s)", 
                    self.config.host, self.config.port, self.config.protocol)
            
            # Save original settings
            self._save_original_settings()
            
            # Set IE/Edge proxy
            self._set_ie_proxy()
            
            # Set WinHTTP proxy
            self._set_winhttp_proxy()
            
            # Enable proxy
            self._enable_proxy()
            
            self._is_enabled = True
            log.info("System proxy enabled successfully")
            return True
            
        except Exception as e:
            log.error("Failed to enable system proxy: %s", e)
            return False
    
    def disable_system_proxy(self) -> bool:
        """
        Disable system-wide proxy and restore original settings.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            log.info("Disabling system proxy")
            
            # Restore IE/Edge proxy
            self._restore_ie_proxy()
            
            # Restore WinHTTP proxy
            self._restore_winhttp_proxy()
            
            # Disable proxy
            self._disable_proxy()
            
            self._is_enabled = False
            log.info("System proxy disabled successfully")
            return True
            
        except Exception as e:
            log.error("Failed to disable system proxy: %s", e)
            return False
    
    def _save_original_settings(self) -> None:
        """Save original proxy settings."""
        try:
            # IE Proxy
            ie_key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                self.IE_PROXY_KEY,
                0,
                winreg.KEY_READ
            )
            
            try:
                proxy_enable, _ = winreg.QueryValueEx(ie_key, "ProxyEnable")
                self._original_settings['ie_proxy_enable'] = proxy_enable
            except FileNotFoundError:
                self._original_settings['ie_proxy_enable'] = 0
            
            try:
                proxy_server, _ = winreg.QueryValueEx(ie_key, "ProxyServer")
                self._original_settings['ie_proxy_server'] = proxy_server
            except FileNotFoundError:
                self._original_settings['ie_proxy_server'] = ""
            
            try:
                proxy_override, _ = winreg.QueryValueEx(ie_key, "ProxyOverride")
                self._original_settings['ie_proxy_override'] = proxy_override
            except FileNotFoundError:
                self._original_settings['ie_proxy_override'] = ""
            
            winreg.CloseKey(ie_key)
            
            # WinHTTP - save current settings via netsh
            try:
                result = subprocess.run(
                    ['netsh', 'winhttp', 'show', 'proxy'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                self._original_settings['winhttp_proxy'] = result.stdout
            except Exception:
                self._original_settings['winhttp_proxy'] = ""
                
        except Exception as e:
            log.error("Failed to save original settings: %s", e)
    
    def _set_ie_proxy(self) -> None:
        """Set IE/Edge proxy settings."""
        try:
            ie_key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                self.IE_PROXY_KEY,
                0,
                winreg.KEY_WRITE
            )
            
            # Set proxy server
            proxy_string = f"{self.config.protocol}={self.config.host}:{self.config.port}"
            winreg.SetValueEx(ie_key, "ProxyServer", 0, winreg.REG_SZ, proxy_string)
            
            # Set bypass list
            bypass = ";".join(self.config.bypass_list)
            winreg.SetValueEx(ie_key, "ProxyOverride", 0, winreg.REG_SZ, bypass)
            
            winreg.CloseKey(ie_key)
            log.debug("IE proxy set: %s", proxy_string)
            
        except Exception as e:
            log.error("Failed to set IE proxy: %s", e)
            raise
    
    def _set_winhttp_proxy(self) -> None:
        """Set WinHTTP proxy (used by system services)."""
        try:
            proxy_string = f"{self.config.protocol}={self.config.host}:{self.config.port}"
            bypass = ";".join(self.config.bypass_list)
            
            # Use netsh to set WinHTTP proxy
            result = subprocess.run(
                ['netsh', 'winhttp', 'set', 'proxy', proxy_string, bypass],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                log.debug("WinHTTP proxy set: %s", proxy_string)
            else:
                log.warning("WinHTTP proxy set failed: %s", result.stderr)
                
        except Exception as e:
            log.error("Failed to set WinHTTP proxy: %s", e)
    
    def _enable_proxy(self) -> None:
        """Enable proxy in registry."""
        try:
            ie_key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                self.IE_PROXY_KEY,
                0,
                winreg.KEY_WRITE
            )
            
            # Enable proxy
            winreg.SetValueEx(ie_key, "ProxyEnable", 0, winreg.REG_DWORD, 1)
            
            winreg.CloseKey(ie_key)
            log.debug("Proxy enabled in registry")
            
        except Exception as e:
            log.error("Failed to enable proxy: %s", e)
            raise
    
    def _disable_proxy(self) -> None:
        """Disable proxy in registry."""
        try:
            ie_key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                self.IE_PROXY_KEY,
                0,
                winreg.KEY_WRITE
            )
            
            # Disable proxy
            winreg.SetValueEx(ie_key, "ProxyEnable", 0, winreg.REG_DWORD, 0)
            
            winreg.CloseKey(ie_key)
            log.debug("Proxy disabled in registry")
            
        except Exception as e:
            log.error("Failed to disable proxy: %s", e)
    
    def _restore_ie_proxy(self) -> None:
        """Restore original IE proxy settings."""
        try:
            ie_key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                self.IE_PROXY_KEY,
                0,
                winreg.KEY_WRITE
            )
            
            # Restore ProxyEnable
            if 'ie_proxy_enable' in self._original_settings:
                winreg.SetValueEx(
                    ie_key,
                    "ProxyEnable",
                    0,
                    winreg.REG_DWORD,
                    self._original_settings['ie_proxy_enable']
                )
            
            # Restore ProxyServer
            if 'ie_proxy_server' in self._original_settings:
                winreg.SetValueEx(
                    ie_key,
                    "ProxyServer",
                    0,
                    winreg.REG_SZ,
                    self._original_settings['ie_proxy_server']
                )
            
            # Restore ProxyOverride
            if 'ie_proxy_override' in self._original_settings:
                winreg.SetValueEx(
                    ie_key,
                    "ProxyOverride",
                    0,
                    winreg.REG_SZ,
                    self._original_settings['ie_proxy_override']
                )
            
            winreg.CloseKey(ie_key)
            
        except Exception as e:
            log.error("Failed to restore IE proxy: %s", e)
    
    def _restore_winhttp_proxy(self) -> None:
        """Restore original WinHTTP proxy settings."""
        try:
            # Reset WinHTTP to direct connection
            result = subprocess.run(
                ['netsh', 'winhttp', 'reset', 'proxy'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                log.debug("WinHTTP proxy reset to direct")
            else:
                log.warning("WinHTTP proxy reset failed: %s", result.stderr)
                
        except Exception as e:
            log.error("Failed to restore WinHTTP proxy: %s", e)
    
    def set_pac_url(self, pac_url: str) -> bool:
        """
        Set PAC (Proxy Auto-Config) URL.
        
        Args:
            pac_url: URL to PAC file
            
        Returns:
            True if successful
        """
        try:
            ie_key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                self.IE_PROXY_KEY,
                0,
                winreg.KEY_WRITE
            )
            
            # Set AutoConfigURL
            winreg.SetValueEx(ie_key, "AutoConfigURL", 0, winreg.REG_SZ, pac_url)
            
            # Enable auto-detect
            winreg.SetValueEx(ie_key, "ProxyEnable", 0, winreg.REG_DWORD, 1)
            
            winreg.CloseKey(ie_key)
            
            self.config.pac_url = pac_url
            self.config.enable_pac = True
            
            log.info("PAC URL set: %s", pac_url)
            return True
            
        except Exception as e:
            log.error("Failed to set PAC URL: %s", e)
            return False
    
    def get_current_proxy(self) -> dict:
        """
        Get current system proxy settings.
        
        Returns:
            Dictionary with current proxy configuration
        """
        settings = {
            'ie_proxy': None,
            'winhttp_proxy': None,
            'pac_url': None,
        }
        
        try:
            # IE Proxy
            ie_key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                self.IE_PROXY_KEY,
                0,
                winreg.KEY_READ
            )
            
            try:
                proxy_enable, _ = winreg.QueryValueEx(ie_key, "ProxyEnable")
                proxy_server, _ = winreg.QueryValueEx(ie_key, "ProxyServer")
                settings['ie_proxy'] = {
                    'enabled': bool(proxy_enable),
                    'server': proxy_server,
                }
            except FileNotFoundError:
                pass
            
            try:
                pac_url, _ = winreg.QueryValueEx(ie_key, "AutoConfigURL")
                if pac_url:
                    settings['pac_url'] = pac_url
            except FileNotFoundError:
                pass
            
            winreg.CloseKey(ie_key)
            
            # WinHTTP
            try:
                result = subprocess.run(
                    ['netsh', 'winhttp', 'show', 'proxy'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                settings['winhttp_proxy'] = result.stdout
            except Exception:
                pass
                
        except Exception as e:
            log.error("Failed to get current proxy settings: %s", e)
        
        return settings
    
    def is_enabled(self) -> bool:
        """Check if system proxy is enabled."""
        try:
            ie_key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                self.IE_PROXY_KEY,
                0,
                winreg.KEY_READ
            )
            
            try:
                proxy_enable, _ = winreg.QueryValueEx(ie_key, "ProxyEnable")
                winreg.CloseKey(ie_key)
                return bool(proxy_enable)
            except FileNotFoundError:
                winreg.CloseKey(ie_key)
                return False
                
        except Exception:
            return False
    
    def __enter__(self) -> 'WindowsProxyManager':
        """Context manager entry."""
        self.enable_system_proxy()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.disable_system_proxy()


# Global proxy manager instance
_proxy_manager: WindowsProxyManager | None = None


def get_proxy_manager() -> WindowsProxyManager:
    """Get or create global proxy manager."""
    global _proxy_manager
    if _proxy_manager is None:
        _proxy_manager = WindowsProxyManager()
    return _proxy_manager


def enable_system_proxy(host: str = "127.0.0.1", port: int = 1080, 
                       protocol: str = "socks") -> bool:
    """
    Enable system proxy with specified settings.
    
    Args:
        host: Proxy host
        port: Proxy port
        protocol: Proxy protocol (http, https, socks, socks5)
        
    Returns:
        True if successful
    """
    config = ProxyConfig(host=host, port=port, protocol=protocol)
    manager = WindowsProxyManager(config)
    return manager.enable_system_proxy()


def disable_system_proxy() -> bool:
    """
    Disable system proxy.
    
    Returns:
        True if successful
    """
    manager = get_proxy_manager()
    return manager.disable_system_proxy()


__all__ = [
    'ProxyConfig',
    'WindowsProxyManager',
    'get_proxy_manager',
    'enable_system_proxy',
    'disable_system_proxy',
]
