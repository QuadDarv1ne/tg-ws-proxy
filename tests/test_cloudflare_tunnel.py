"""Tests for cloudflare_tunnel.py module."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from subprocess import TimeoutExpired
from unittest.mock import MagicMock, patch

import pytest

from proxy.cloudflare_tunnel import (
    CloudflareTunnel,
    CloudflareTunnelConfig,
    CloudflareWARP,
    TunnelStatus,
)


class TestCloudflareTunnelConfig:
    """Tests for CloudflareTunnelConfig dataclass."""

    def test_config_default(self):
        """Test default CloudflareTunnelConfig."""
        config = CloudflareTunnelConfig()
        
        assert config.tunnel_id == ""
        assert config.tunnel_name == "tg-ws-proxy"
        assert config.proxy_host == "127.0.0.1"
        assert config.proxy_port == 1080
        assert config.proxy_type == "socks5"
        assert config.log_level == "info"
        assert config.auto_reconnect is True

    def test_config_custom(self):
        """Test custom CloudflareTunnelConfig."""
        config = CloudflareTunnelConfig(
            tunnel_id="test-tunnel-id",
            tunnel_name="my-tunnel",
            proxy_host="192.168.1.1",
            proxy_port=8080,
            proxy_type="http",
            log_level="debug",
        )
        
        assert config.tunnel_id == "test-tunnel-id"
        assert config.tunnel_name == "my-tunnel"
        assert config.proxy_host == "192.168.1.1"
        assert config.proxy_port == 8080
        assert config.proxy_type == "http"

    def test_config_proxy_url(self):
        """Test proxy_url property."""
        config = CloudflareTunnelConfig(
            proxy_type="socks5",
            proxy_host="127.0.0.1",
            proxy_port=1080,
        )
        
        assert config.proxy_url == "socks5://127.0.0.1:1080"

    def test_config_proxy_url_http(self):
        """Test proxy_url property with HTTP."""
        config = CloudflareTunnelConfig(
            proxy_type="http",
            proxy_host="192.168.1.1",
            proxy_port=8080,
        )
        
        assert config.proxy_url == "http://192.168.1.1:8080"


class TestTunnelStatus:
    """Tests for TunnelStatus dataclass."""

    def test_status_default(self):
        """Test default TunnelStatus."""
        status = TunnelStatus()
        
        assert status.is_running is False
        assert status.tunnel_id == ""
        assert status.connections == 0
        assert status.bytes_sent == 0
        assert status.bytes_received == 0
        assert status.uptime_seconds == 0.0
        assert status.last_error == ""
        assert status.cloudflare_ip == ""

    def test_status_custom(self):
        """Test custom TunnelStatus."""
        status = TunnelStatus(
            is_running=True,
            tunnel_id="test-id",
            connections=5,
            bytes_sent=1024,
            bytes_received=2048,
            uptime_seconds=3600.0,
            last_error="",
            cloudflare_ip="1.2.3.4",
        )
        
        assert status.is_running is True
        assert status.tunnel_id == "test-id"
        assert status.connections == 5


class TestCloudflareTunnelInit:
    """Tests for CloudflareTunnel initialization."""

    def test_tunnel_init(self):
        """Test CloudflareTunnel initialization."""
        tunnel = CloudflareTunnel()
        
        assert tunnel.config is not None
        assert tunnel._process is None
        assert tunnel._running is False
        assert tunnel._cloudflared_path is not None

    def test_tunnel_init_with_config(self):
        """Test CloudflareTunnel with custom config."""
        config = CloudflareTunnelConfig(tunnel_id="test-id")
        tunnel = CloudflareTunnel(config)
        
        assert tunnel.config.tunnel_id == "test-id"

    def test_tunnel_data_dir_created(self):
        """Test data directory is created."""
        tunnel = CloudflareTunnel()
        
        assert tunnel._data_dir.exists()


class TestCloudflareTunnelPlatform:
    """Tests for platform detection."""

    def test_get_platform_key_windows(self):
        """Test platform key for Windows."""
        with patch('platform.system', return_value='Windows'):
            with patch('platform.machine', return_value='AMD64'):
                tunnel = CloudflareTunnel()
                key = tunnel._get_platform_key()
                
                assert 'windows' in key

    def test_get_platform_key_linux(self):
        """Test platform key for Linux."""
        with patch('platform.system', return_value='Linux'):
            with patch('platform.machine', return_value='x86_64'):
                tunnel = CloudflareTunnel()
                key = tunnel._get_platform_key()
                
                assert 'linux' in key

    def test_get_platform_key_macos(self):
        """Test platform key for macOS."""
        with patch('platform.system', return_value='Darwin'):
            with patch('platform.machine', return_value='arm64'):
                tunnel = CloudflareTunnel()
                key = tunnel._get_platform_key()
                
                assert 'darwin' in key


class TestCloudflareTunnelDownload:
    """Tests for cloudflared download."""

    def test_download_cloudflared_exists(self):
        """Test download when file already exists."""
        tunnel = CloudflareTunnel()
        
        # Mock exists() to return True
        with patch.object(Path, 'exists', return_value=True):
            result = tunnel.download_cloudflared()
            
            assert result is True

    def test_check_cloudflared_exists(self):
        """Test check when file exists."""
        tunnel = CloudflareTunnel()
        
        with patch.object(Path, 'exists', return_value=True):
            result = tunnel.check_cloudflared()
            
            assert result is True

    def test_check_cloudflared_in_path(self):
        """Test check when cloudflared is in PATH."""
        tunnel = CloudflareTunnel()
        
        with patch.object(Path, 'exists', return_value=False):
            with patch('shutil.which', return_value='/usr/bin/cloudflared'):
                result = tunnel.check_cloudflared()
                
                assert result is True

    def test_check_cloudflared_not_found(self):
        """Test check when cloudflared not found."""
        tunnel = CloudflareTunnel()
        
        with patch.object(Path, 'exists', return_value=False):
            with patch('shutil.which', return_value=None):
                result = tunnel.check_cloudflared()
                
                assert result is False


class TestCloudflareTunnelConfigGeneration:
    """Tests for configuration generation."""

    def test_generate_config(self):
        """Test config generation."""
        tunnel = CloudflareTunnel()
        
        with patch.object(tunnel, '_generate_config_yaml', return_value="test: config"):
            with patch('builtins.open'):
                result = tunnel.generate_config()
                
                assert result is True
                assert tunnel.config.config_file is not None

    def test_generate_config_yaml_basic(self):
        """Test YAML config generation."""
        tunnel = CloudflareTunnel()
        
        config_yaml = tunnel._generate_config_yaml()
        
        assert 'tunnel:' in config_yaml
        assert 'credentials-file:' in config_yaml
        assert 'ingress:' in config_yaml
        assert 'service:' in config_yaml

    def test_generate_config_yaml_with_hostname(self):
        """Test YAML config with hostname."""
        config = CloudflareTunnelConfig(hostname="example.com")
        tunnel = CloudflareTunnel(config)
        
        config_yaml = tunnel._generate_config_yaml()
        
        assert 'hostname: example.com' in config_yaml

    def test_generate_config_yaml_with_metrics(self):
        """Test YAML config with metrics."""
        config = CloudflareTunnelConfig(metrics_port=2000)
        tunnel = CloudflareTunnel(config)
        
        config_yaml = tunnel._generate_config_yaml()
        
        assert 'metrics:' in config_yaml
        assert '2000' in config_yaml

    def test_generate_config_yaml_catch_all(self):
        """Test YAML config has catch-all rule."""
        tunnel = CloudflareTunnel()
        
        config_yaml = tunnel._generate_config_yaml()
        
        assert 'http_status:404' in config_yaml


class TestCloudflareTunnelAuth:
    """Tests for authentication."""

    def test_authenticate_success(self):
        """Test authentication success."""
        tunnel = CloudflareTunnel()
        
        mock_result = MagicMock()
        mock_result.returncode = 0
        
        with patch('subprocess.run', return_value=mock_result):
            result = tunnel.authenticate("test-token")
            
            assert result is True

    def test_authenticate_failure(self):
        """Test authentication failure."""
        tunnel = CloudflareTunnel()
        
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "error"
        
        with patch('subprocess.run', return_value=mock_result):
            result = tunnel.authenticate("test-token")
            
            assert result is False

    def test_authenticate_timeout(self):
        """Test authentication timeout."""
        tunnel = CloudflareTunnel()
        
        with patch('subprocess.run', side_effect=TimeoutError()):
            result = tunnel.authenticate("test-token")
            
            assert result is False


class TestCloudflareTunnelCreate:
    """Tests for tunnel creation."""

    def test_create_tunnel_success(self):
        """Test tunnel creation success."""
        tunnel = CloudflareTunnel()
        
        mock_result = MagicMock()
        mock_result.stdout = "Created tunnel test with id abc123"
        
        with patch('subprocess.run', return_value=mock_result):
            tunnel_id = tunnel.create_tunnel("test-tunnel")
            
            assert tunnel_id is not None

    def test_create_tunnel_failure(self):
        """Test tunnel creation failure."""
        tunnel = CloudflareTunnel()
        
        with patch('subprocess.run', side_effect=Exception("test error")):
            tunnel_id = tunnel.create_tunnel("test-tunnel")
            
            assert tunnel_id is None


class TestCloudflareTunnelLifecycle:
    """Tests for tunnel lifecycle."""

    def test_start_already_running(self):
        """Test start when already running."""
        tunnel = CloudflareTunnel()
        tunnel._running = True
        
        result = tunnel.start()
        
        assert result is False

    def test_start_no_cloudflared(self):
        """Test start without cloudflared."""
        tunnel = CloudflareTunnel()
        
        with patch.object(tunnel, 'check_cloudflared', return_value=False):
            with patch.object(tunnel, 'download_cloudflared', return_value=False):
                result = tunnel.start()
                
                assert result is False

    def test_start_config_generation_failure(self):
        """Test start with config generation failure."""
        tunnel = CloudflareTunnel()
        
        with patch.object(tunnel, 'check_cloudflared', return_value=True):
            with patch.object(tunnel, 'generate_config', return_value=False):
                result = tunnel.start()
                
                assert result is False

    def test_stop_not_running(self):
        """Test stop when not running."""
        tunnel = CloudflareTunnel()
        tunnel._running = False
        
        # Should not raise
        tunnel.stop()

    def test_stop_with_process(self):
        """Test stop with process."""
        tunnel = CloudflareTunnel()
        tunnel._running = True
        
        mock_process = MagicMock()
        mock_process.poll.return_value = None
        tunnel._process = mock_process
        
        tunnel.stop()
        
        assert tunnel._running is False
        assert tunnel._process is None

    def test_stop_timeout(self):
        """Test stop with timeout."""
        tunnel = CloudflareTunnel()
        tunnel._running = True
        
        mock_process = MagicMock()
        mock_process.wait.side_effect=TimeoutExpired("test", 10)
        tunnel._process = mock_process
        
        tunnel.stop()
        
        mock_process.kill.assert_called()

    def test_get_status(self):
        """Test get_status."""
        tunnel = CloudflareTunnel()
        tunnel._running = True
        tunnel._start_time = 1000.0
        
        with patch('time.time', return_value=2000.0):
            status = tunnel.get_status()
            
            assert status.is_running is True
            assert status.uptime_seconds == 1000.0

    def test_get_status_not_running(self):
        """Test get_status when not running."""
        tunnel = CloudflareTunnel()
        tunnel._running = False
        
        status = tunnel.get_status()
        
        assert status.is_running is False

    def test_get_logs(self):
        """Test get_logs."""
        tunnel = CloudflareTunnel()
        
        logs = tunnel.get_logs()
        
        assert isinstance(logs, list)


class TestCloudflareTunnelMonitor:
    """Tests for monitoring."""

    def test_monitor_loop_process_alive(self):
        """Test monitor loop when process is alive."""
        config = CloudflareTunnelConfig(auto_reconnect=False)
        tunnel = CloudflareTunnel(config)
        tunnel._running = True
        
        mock_process = MagicMock()
        mock_process.poll.return_value = None  # Process alive
        tunnel._process = mock_process
        
        # Run monitor loop briefly - should exit when _running becomes False
        def sleep_side_effect(duration):
            tunnel._running = False  # Stop the loop
            raise StopIteration()
        
        with patch('time.sleep', side_effect=sleep_side_effect):
            try:
                tunnel._monitor_loop()
            except StopIteration:
                pass
        
        # Should not have tried to reconnect
        assert tunnel._process is not None

    def test_monitor_loop_process_dead_no_reconnect(self):
        """Test monitor loop when process is dead."""
        config = CloudflareTunnelConfig(auto_reconnect=False)
        tunnel = CloudflareTunnel(config)
        tunnel._running = True
        
        mock_process = MagicMock()
        mock_process.poll.return_value = 1  # Process dead
        mock_process.stderr.read.return_value = "error"
        tunnel._process = mock_process
        
        # Run monitor loop briefly
        def sleep_side_effect(duration):
            tunnel._running = False  # Stop the loop after first iteration
            raise StopIteration()
        
        with patch('time.sleep', side_effect=sleep_side_effect):
            try:
                tunnel._monitor_loop()
            except StopIteration:
                pass
        
        # Should have stopped
        assert tunnel._running is False


class TestCloudflareWARP:
    """Tests for CloudflareWARP."""

    def test_warp_init(self):
        """Test CloudflareWARP initialization."""
        with patch('shutil.which', return_value=None):
            warp = CloudflareWARP()
            
            assert warp._connected is False
            assert warp.warp_cli is None

    def test_warp_is_installed_true(self):
        """Test is_installed when installed."""
        with patch('shutil.which', return_value='/usr/bin/warp-cli'):
            warp = CloudflareWARP()
            result = warp.is_installed()
            
            assert result is True

    def test_warp_is_installed_false(self):
        """Test is_installed when not installed."""
        with patch('shutil.which', return_value=None):
            warp = CloudflareWARP()
            result = warp.is_installed()
            
            assert result is False

    def test_warp_connect_success(self):
        """Test connect success."""
        with patch('shutil.which', return_value='/usr/bin/warp-cli'):
            with patch('subprocess.run'):
                warp = CloudflareWARP()
                result = warp.connect()
                
                assert result is True
                assert warp._connected is True

    def test_warp_connect_not_installed(self):
        """Test connect when not installed."""
        with patch('shutil.which', return_value=None):
            warp = CloudflareWARP()
            result = warp.connect()
            
            assert result is False

    def test_warp_connect_failure(self):
        """Test connect failure."""
        with patch('shutil.which', return_value='/usr/bin/warp-cli'):
            with patch('subprocess.run', side_effect=subprocess.CalledProcessError(1, 'warp-cli', output=b'', stderr=b'error')):
                warp = CloudflareWARP()
                result = warp.connect()
                
                assert result is False

    def test_warp_disconnect_success(self):
        """Test disconnect success."""
        with patch('shutil.which', return_value='/usr/bin/warp-cli'):
            with patch('subprocess.run'):
                warp = CloudflareWARP()
                warp._connected = True
                result = warp.disconnect()
                
                assert result is True
                assert warp._connected is False

    def test_warp_disconnect_not_installed(self):
        """Test disconnect when not installed."""
        with patch('shutil.which', return_value=None):
            warp = CloudflareWARP()
            result = warp.disconnect()
            
            assert result is False

    def test_warp_set_proxy_mode_success(self):
        """Test set_proxy_mode success."""
        with patch('shutil.which', return_value='/usr/bin/warp-cli'):
            with patch('subprocess.run'):
                warp = CloudflareWARP()
                result = warp.set_proxy_mode(1080)
                
                assert result is True

    def test_warp_set_proxy_mode_not_installed(self):
        """Test set_proxy_mode when not installed."""
        with patch('shutil.which', return_value=None):
            warp = CloudflareWARP()
            result = warp.set_proxy_mode(1080)
            
            assert result is False

    def test_warp_get_status_installed(self):
        """Test get_status when installed."""
        mock_result = MagicMock()
        mock_result.stdout = "Connected to WARP"
        
        with patch('shutil.which', return_value='/usr/bin/warp-cli'):
            with patch('subprocess.run', return_value=mock_result):
                warp = CloudflareWARP()
                status = warp.get_status()
                
                assert status['installed'] is True
                assert status['connected'] is True

    def test_warp_get_status_not_installed(self):
        """Test get_status when not installed."""
        with patch('shutil.which', return_value=None):
            warp = CloudflareWARP()
            status = warp.get_status()

            assert status['installed'] is False
