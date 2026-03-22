"""Tests for system_proxy.py module."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from proxy.system_proxy import (
    LinuxSystemProxy,
    MacOSSystemProxy,
    ProxyConfig,
    WindowsSystemProxy,
    get_system_proxy,
)


class TestProxyConfig:
    """Tests for ProxyConfig dataclass."""

    def test_proxy_config_default(self):
        """Test default ProxyConfig."""
        config = ProxyConfig()
        
        assert config.host == "127.0.0.1"
        assert config.port == 1080
        assert config.proxy_type == "socks5"
        assert config.bypass_local is True

    def test_proxy_config_custom(self):
        """Test custom ProxyConfig."""
        config = ProxyConfig(
            host="192.168.1.1",
            port=8080,
            proxy_type="http",
            bypass_local=False,
        )
        
        assert config.host == "192.168.1.1"
        assert config.port == 8080
        assert config.proxy_type == "http"
        assert config.bypass_local is False

    def test_proxy_config_proxy_string(self):
        """Test proxy_string property."""
        config = ProxyConfig(host="127.0.0.1", port=1080)
        
        assert config.proxy_string == "127.0.0.1:1080"

    def test_proxy_config_bypass_list(self):
        """Test bypass_list property."""
        config = ProxyConfig(bypass_local=True)
        
        assert "localhost" in config.bypass_list
        assert "127.*" in config.bypass_list

    def test_proxy_config_bypass_list_disabled(self):
        """Test bypass_list when bypass_local is False."""
        config = ProxyConfig(bypass_local=False)
        
        assert config.bypass_list == ""


class TestWindowsSystemProxy:
    """Tests for WindowsSystemProxy class."""

    def test_windows_proxy_init(self):
        """Test WindowsSystemProxy initialization."""
        with patch.object(sys, 'platform', 'win32'):
            proxy = WindowsSystemProxy()
            
            assert proxy.registry_path is not None
            assert proxy._backup is None

    def test_windows_proxy_init_non_windows(self):
        """Test WindowsSystemProxy raises on non-Windows."""
        with patch.object(sys, 'platform', 'linux'):
            with pytest.raises(RuntimeError, match="only supported on Windows"):
                WindowsSystemProxy()

    @pytest.mark.skipif(sys.platform != 'win32', reason="Windows only")
    def test_windows_proxy_backup(self):
        """Test backup_settings on Windows."""
        proxy = WindowsSystemProxy()
        
        backup = proxy.backup_settings()
        
        assert isinstance(backup, dict)
        assert 'ProxyEnable' in backup
        assert 'ProxyServer' in backup
        assert 'ProxyOverride' in backup

    @pytest.mark.skipif(sys.platform != 'win32', reason="Windows only")
    def test_windows_proxy_restore(self):
        """Test restore_settings on Windows."""
        proxy = WindowsSystemProxy()
        
        # Backup first
        proxy.backup_settings()
        
        # Should not raise
        proxy.restore_settings()

    @pytest.mark.skipif(sys.platform != 'win32', reason="Windows only")
    def test_windows_proxy_restore_no_backup(self):
        """Test restore_settings with no backup."""
        proxy = WindowsSystemProxy()
        proxy._backup = None
        
        # Should not raise, just log warning
        proxy.restore_settings()


class TestWindowsSystemProxyMocked:
    """Tests for WindowsSystemProxy with mocked registry."""

    def test_enable_proxy_failure_handling(self):
        """Test enable_proxy handles failures gracefully."""
        with patch.object(sys, 'platform', 'win32'):
            proxy = WindowsSystemProxy()
            
            # Mock all registry methods
            with patch.object(proxy, 'backup_settings'):
                with patch.object(proxy, '_write_registry_value', side_effect=Exception("test")):
                    with patch.object(proxy, '_configure_winhttp'):
                        config = ProxyConfig()
                        
                        # Should return False on failure, not raise
                        result = proxy.enable_proxy(config)
                        
                        assert result is False

    def test_disable_proxy_failure_handling(self):
        """Test disable_proxy handles failures gracefully."""
        with patch.object(sys, 'platform', 'win32'):
            proxy = WindowsSystemProxy()
            
            with patch.object(proxy, '_write_registry_value', side_effect=Exception("test")):
                with patch.object(proxy, '_clear_winhttp'):
                    result = proxy.disable_proxy()
                    
                    assert result is False


class TestLinuxSystemProxy:
    """Tests for LinuxSystemProxy class."""

    def test_linux_proxy_init(self):
        """Test LinuxSystemProxy initialization."""
        with patch.object(sys, 'platform', 'linux'):
            proxy = LinuxSystemProxy()
            
            assert proxy is not None

    def test_linux_proxy_init_non_linux(self):
        """Test LinuxSystemProxy raises on non-Linux."""
        with patch.object(sys, 'platform', 'win32'):
            with pytest.raises(RuntimeError, match="only supported on Linux"):
                LinuxSystemProxy()

    def test_linux_proxy_enable(self):
        """Test LinuxSystemProxy enable_proxy."""
        with patch.object(sys, 'platform', 'linux'):
            with patch.dict('os.environ', {}, clear=True):
                proxy = LinuxSystemProxy()
                config = ProxyConfig()
                
                result = proxy.enable_proxy(config)
                
                assert result is True

    def test_linux_proxy_enable_sets_env(self):
        """Test LinuxSystemProxy sets environment variables."""
        with patch.object(sys, 'platform', 'linux'):
            with patch.dict('os.environ', {}, clear=True):
                proxy = LinuxSystemProxy()
                config = ProxyConfig(host="192.168.1.1", port=8080)
                
                proxy.enable_proxy(config)
                
                import os
                assert os.environ.get('http_proxy') is not None
                assert os.environ.get('https_proxy') is not None

    def test_linux_proxy_disable(self):
        """Test LinuxSystemProxy disable_proxy."""
        with patch.object(sys, 'platform', 'linux'):
            with patch.dict('os.environ', {
                'http_proxy': 'http://127.0.0.1:1080',
                'https_proxy': 'http://127.0.0.1:1080',
            }):
                proxy = LinuxSystemProxy()
                
                result = proxy.disable_proxy()
                
                assert result is True

    def test_linux_proxy_disable_clears_env(self):
        """Test LinuxSystemProxy clears environment variables."""
        with patch.object(sys, 'platform', 'linux'):
            with patch.dict('os.environ', {
                'http_proxy': 'http://127.0.0.1:1080',
                'https_proxy': 'http://127.0.0.1:1080',
                'ftp_proxy': 'http://127.0.0.1:1080',
                'no_proxy': 'localhost',
            }):
                proxy = LinuxSystemProxy()
                
                proxy.disable_proxy()
                
                import os
                assert 'http_proxy' not in os.environ
                assert 'https_proxy' not in os.environ


class TestMacOSSystemProxy:
    """Tests for MacOSSystemProxy class."""

    def test_macos_proxy_init(self):
        """Test MacOSSystemProxy initialization."""
        with patch.object(sys, 'platform', 'darwin'):
            proxy = MacOSSystemProxy()
            
            assert proxy is not None

    def test_macos_proxy_init_non_macos(self):
        """Test MacOSSystemProxy raises on non-macOS."""
        with patch.object(sys, 'platform', 'win32'):
            with pytest.raises(RuntimeError, match="only supported on macOS"):
                MacOSSystemProxy()

    def test_macos_proxy_enable(self):
        """Test MacOSSystemProxy enable_proxy."""
        with patch.object(sys, 'platform', 'darwin'):
            with patch('subprocess.run') as mock_run:
                mock_run.return_value = MagicMock(stdout="Wi-Fi\nEthernet")
                
                proxy = MacOSSystemProxy()
                config = ProxyConfig()
                
                result = proxy.enable_proxy(config)
                
                assert result is True

    def test_macos_proxy_enable_failure(self):
        """Test MacOSSystemProxy enable_proxy failure."""
        with patch.object(sys, 'platform', 'darwin'):
            with patch('subprocess.run', side_effect=Exception("test error")):
                proxy = MacOSSystemProxy()
                config = ProxyConfig()
                
                result = proxy.enable_proxy(config)
                
                assert result is False

    def test_macos_proxy_disable(self):
        """Test MacOSSystemProxy disable_proxy."""
        with patch.object(sys, 'platform', 'darwin'):
            with patch('subprocess.run') as mock_run:
                mock_run.return_value = MagicMock(stdout="Wi-Fi\nEthernet")
                
                proxy = MacOSSystemProxy()
                
                result = proxy.disable_proxy()
                
                assert result is True

    def test_macos_proxy_disable_failure(self):
        """Test MacOSSystemProxy disable_proxy failure."""
        with patch.object(sys, 'platform', 'darwin'):
            with patch('subprocess.run', side_effect=Exception("test error")):
                proxy = MacOSSystemProxy()
                
                result = proxy.disable_proxy()
                
                assert result is False


class TestGetSystemProxy:
    """Tests for get_system_proxy factory function."""

    def test_get_system_proxy_windows(self):
        """Test get_system_proxy on Windows."""
        with patch.object(sys, 'platform', 'win32'):
            proxy = get_system_proxy()
            
            assert isinstance(proxy, WindowsSystemProxy)

    def test_get_system_proxy_linux(self):
        """Test get_system_proxy on Linux."""
        with patch.object(sys, 'platform', 'linux'):
            proxy = get_system_proxy()
            
            assert isinstance(proxy, LinuxSystemProxy)

    def test_get_system_proxy_macos(self):
        """Test get_system_proxy on macOS."""
        with patch.object(sys, 'platform', 'darwin'):
            proxy = get_system_proxy()
            
            assert isinstance(proxy, MacOSSystemProxy)

    def test_get_system_proxy_unsupported(self):
        """Test get_system_proxy on unsupported platform."""
        with patch.object(sys, 'platform', 'freebsd'):
            with pytest.raises(RuntimeError, match="Unsupported platform"):
                get_system_proxy()


class TestProxyConfigEdgeCases:
    """Edge case tests for ProxyConfig."""

    def test_proxy_config_ipv6(self):
        """Test ProxyConfig with IPv6 address."""
        config = ProxyConfig(host="::1", port=1080)
        
        assert config.host == "::1"
        assert config.proxy_string == "::1:1080"

    def test_proxy_config_large_port(self):
        """Test ProxyConfig with large port number."""
        config = ProxyConfig(port=65535)
        
        assert config.port == 65535
        assert "65535" in config.proxy_string

    def test_proxy_config_custom_bypass(self):
        """Test ProxyConfig with custom bypass list."""
        config = ProxyConfig(bypass_local=True)
        
        bypass = config.bypass_list
        assert "localhost" in bypass
        assert "10.*" in bypass


class TestWindowsSystemProxyEdgeCases:
    """Edge case tests for WindowsSystemProxy."""

    def test_read_registry_value_missing(self):
        """Test reading missing registry value."""
        with patch.object(sys, 'platform', 'win32'):
            with patch('winreg.OpenKey') as mock_open_key:
                with patch('winreg.CloseKey'):
                    mock_open_key.side_effect = FileNotFoundError()
                    
                    proxy = WindowsSystemProxy()
                    result = proxy._read_registry_value('ProxyEnable', 'ProxyEnable')
                    
                    assert result is None

    def test_write_registry_value(self):
        """Test writing registry value."""
        with patch.object(sys, 'platform', 'win32'):
            with patch('winreg.OpenKey') as mock_open_key:
                with patch('winreg.SetValueEx') as mock_set_value:
                    with patch('winreg.CloseKey'):
                        mock_key = MagicMock()
                        mock_open_key.return_value = mock_key
                        
                        proxy = WindowsSystemProxy()
                        
                        # Should not raise
                        proxy._write_registry_value('TestValue', 1)

    def test_configure_winhttp_failure(self):
        """Test _configure_winhttp failure."""
        with patch.object(sys, 'platform', 'win32'):
            with patch('subprocess.run', side_effect=Exception("test error")):
                proxy = WindowsSystemProxy()
                config = ProxyConfig()
                
                # Should not raise, just log debug
                proxy._configure_winhttp(config)

    def test_clear_winhttp_failure(self):
        """Test _clear_winhttp failure."""
        with patch.object(sys, 'platform', 'win32'):
            with patch('subprocess.run', side_effect=Exception("test error")):
                proxy = WindowsSystemProxy()
                
                # Should not raise, just log debug
                proxy._clear_winhttp()
