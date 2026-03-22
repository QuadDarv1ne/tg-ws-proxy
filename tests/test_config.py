"""Unit tests for config module."""

import json
import os
import tempfile

from proxy.config import (
    Config,
    ConfigManager,
    DNSConfig,
    LoggingConfig,
    MonitoringConfig,
    PerformanceConfig,
    SecurityConfig,
    ServerConfig,
    WebSocketConfig,
    get_config,
    load_config,
)


class TestDataclasses:
    """Test configuration dataclasses."""

    def test_server_config_defaults(self):
        """Test ServerConfig default values."""
        config = ServerConfig()

        assert config.host == "0.0.0.0"
        assert config.port == 8080
        assert config.socks_port == 1080
        assert config.max_connections == 500
        assert config.connection_timeout == 30.0

    def test_websocket_config_defaults(self):
        """Test WebSocketConfig default values."""
        config = WebSocketConfig()

        assert config.pool_size == 4
        assert config.pool_max_size == 8
        assert config.pool_max_age == 120.0
        assert config.enable_compression is False
        assert config.ping_interval == 30.0
        assert config.ping_timeout == 10.0

    def test_security_config_defaults(self):
        """Test SecurityConfig default values."""
        config = SecurityConfig()

        assert config.auth_required is False
        assert config.auth_username == ""
        assert config.auth_password == ""
        assert config.ip_whitelist == []
        assert config.ip_blacklist == []
        assert config.rate_limit_enabled is False

    def test_main_config_defaults(self):
        """Test main Config default values."""
        config = Config()

        assert isinstance(config.server, ServerConfig)
        assert isinstance(config.websocket, WebSocketConfig)
        assert isinstance(config.dns, DNSConfig)
        assert isinstance(config.security, SecurityConfig)
        assert isinstance(config.performance, PerformanceConfig)
        assert isinstance(config.logging, LoggingConfig)
        assert isinstance(config.monitoring, MonitoringConfig)


class TestConfigManager:
    """Test ConfigManager class."""

    def test_load_from_dict_empty(self):
        """Test loading empty dictionary."""
        manager = ConfigManager()
        config = manager.load_from_dict({})

        assert isinstance(config, Config)
        assert config.server.port == 8080

    def test_load_from_dict_server(self):
        """Test loading server configuration."""
        manager = ConfigManager()
        data = {
            'server': {
                'host': '127.0.0.1',
                'port': 9000,
                'max_connections': 1000,
            }
        }
        config = manager.load_from_dict(data)

        assert config.server.host == '127.0.0.1'
        assert config.server.port == 9000
        assert config.server.max_connections == 1000

    def test_load_from_dict_websocket(self):
        """Test loading websocket configuration."""
        manager = ConfigManager()
        data = {
            'websocket': {
                'pool_size': 8,
                'pool_max_size': 16,
                'enable_compression': True,
            }
        }
        config = manager.load_from_dict(data)

        assert config.websocket.pool_size == 8
        assert config.websocket.pool_max_size == 16
        assert config.websocket.enable_compression is True

    def test_load_from_dict_security(self):
        """Test loading security configuration."""
        manager = ConfigManager()
        data = {
            'security': {
                'auth_required': True,
                'auth_username': 'admin',
                'auth_password': 'secret',
                'ip_whitelist': ['192.168.1.1', '10.0.0.1'],
                'rate_limit_enabled': True,
                'rate_limit_requests': 50,
            }
        }
        config = manager.load_from_dict(data)

        assert config.security.auth_required is True
        assert config.security.auth_username == 'admin'
        assert config.security.auth_password == 'secret'
        assert config.security.ip_whitelist == ['192.168.1.1', '10.0.0.1']
        assert config.security.rate_limit_enabled is True
        assert config.security.rate_limit_requests == 50

    def test_load_from_dict_dc_override(self):
        """Test loading DC override configuration."""
        manager = ConfigManager()
        data = {
            'dc_override': {
                '1': '1.2.3.4',
                '2': '5.6.7.8',
            }
        }
        config = manager.load_from_dict(data)

        assert config.dc_override == {1: '1.2.3.4', 2: '5.6.7.8'}

    def test_load_from_file_json(self):
        """Test loading configuration from JSON file."""
        manager = ConfigManager()

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({'server': {'port': 9999}}, f)
            f.flush()

            config = manager.load_from_file(f.name)

            assert config.server.port == 9999

        os.unlink(f.name)

    def test_load_from_file_not_found(self):
        """Test loading from non-existent file."""
        manager = ConfigManager()
        config = manager.load_from_file('/nonexistent/path/config.json')

        # Should return default config
        assert config.server.port == 8080

    def test_to_dict(self):
        """Test converting config to dictionary."""
        manager = ConfigManager()
        manager.load_from_dict({
            'server': {'port': 7777},
            'security': {'auth_required': True},
        })

        data = manager._to_dict()

        assert isinstance(data, dict)
        assert data['server']['port'] == 7777
        assert data['security']['auth_required'] is True
        assert 'websocket' in data
        assert 'dns' in data
        assert 'monitoring' in data

    def test_save_and_load_json(self):
        """Test saving and loading configuration."""
        manager = ConfigManager()
        manager.load_from_dict({
            'server': {'port': 8888},
            'websocket': {'pool_size': 10},
        })

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            manager.save(f.name)

            # Verify file was written
            with open(f.name) as rf:
                data = json.load(rf)
                assert data['server']['port'] == 8888
                assert data['websocket']['pool_size'] == 10

        os.unlink(f.name)


class TestEnvironmentOverrides:
    """Test environment variable overrides."""

    def test_env_override_port(self, monkeypatch):
        """Test TGWS_PORT environment variable."""
        monkeypatch.setenv('TGWS_PORT', '7777')

        manager = ConfigManager()
        manager.load_from_dict({})
        manager._apply_environment_overrides()

        assert manager.config.server.port == 7777

    def test_env_override_auth(self, monkeypatch):
        """Test TGWS_AUTH_REQUIRED environment variable."""
        monkeypatch.setenv('TGWS_AUTH_REQUIRED', 'true')
        monkeypatch.setenv('TGWS_AUTH_USERNAME', 'testuser')

        manager = ConfigManager()
        manager.load_from_dict({})
        manager._apply_environment_overrides()

        assert manager.config.security.auth_required is True
        assert manager.config.security.auth_username == 'testuser'

    def test_env_override_log_level(self, monkeypatch):
        """Test TGWS_LOG_LEVEL environment variable."""
        monkeypatch.setenv('TGWS_LOG_LEVEL', 'DEBUG')

        manager = ConfigManager()
        manager.load_from_dict({})
        manager._apply_environment_overrides()

        assert manager.config.logging.level == 'DEBUG'

    def test_env_override_invalid(self, monkeypatch):
        """Test invalid environment variable value."""
        monkeypatch.setenv('TGWS_PORT', 'not_a_number')

        manager = ConfigManager()
        manager.load_from_dict({})
        manager._apply_environment_overrides()

        # Should keep default value
        assert manager.config.server.port == 8080


class TestGlobalFunctions:
    """Test global configuration functions."""

    def teardown_method(self):
        """Reset global config manager."""
        import proxy.config as cfg
        cfg._config_manager = None

    def test_get_config_default(self):
        """Test get_config with defaults."""
        config = get_config()

        assert isinstance(config, Config)
        assert config.server.port == 8080

    def test_load_config(self):
        """Test load_config function."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({'server': {'port': 6666}}, f)
            f.flush()

            config = load_config(f.name)

            assert config.server.port == 6666

        os.unlink(f.name)


class TestConfigValidation:
    """Test configuration validation."""

    def test_port_range(self):
        """Test port values are valid."""
        manager = ConfigManager()
        config = manager.load_from_dict({
            'server': {'port': 65535},
            'monitoring': {'metrics_port': 9090},
        })

        assert 1 <= config.server.port <= 65535
        assert 1 <= config.monitoring.metrics_port <= 65535

    def test_positive_timeouts(self):
        """Test timeout values are positive."""
        manager = ConfigManager()
        config = manager.load_from_dict({
            'server': {'connection_timeout': 0.1},
            'websocket': {'ping_timeout': 1.0, 'ping_interval': 10.0},
        })

        assert config.server.connection_timeout > 0
        assert config.websocket.ping_timeout > 0
        assert config.websocket.ping_interval > 0

    def test_pool_sizes(self):
        """Test pool size values are valid."""
        manager = ConfigManager()
        config = manager.load_from_dict({
            'websocket': {'pool_size': 2, 'pool_max_size': 4},
        })

        assert config.websocket.pool_size > 0
        assert config.websocket.pool_max_size > 0
        assert config.websocket.pool_max_size >= config.websocket.pool_size
