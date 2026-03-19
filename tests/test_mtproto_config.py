"""Unit tests for MTProto config module."""

import json
import tempfile
from pathlib import Path

from proxy.mtproto_config import (
    MTProtoConfig,
    load_config,
    save_config,
)


class TestMTProtoConfigInit:
    """Tests for MTProtoConfig initialization."""

    def test_default_init(self):
        """Test default initialization."""
        config = MTProtoConfig()
        assert config.host == "0.0.0.0"
        assert config.port == 443
        assert config.dc_id == 2
        assert config.secrets == []
        assert config.auto_rotate is False
        assert config.rotate_days == 7
        assert config.traffic_limit_gb is None
        assert config.rate_limit_enabled is False
        assert config.rate_limit_connections == 10
        assert config.rate_limit_mbps == 10.0
        assert config.ip_whitelist is None
        assert config.ip_blacklist is None
        assert config.generate_qr is False
        assert config.verbose is False

    def test_custom_init(self):
        """Test initialization with custom values."""
        config = MTProtoConfig(
            host="127.0.0.1",
            port=8443,
            dc_id=4,
            secrets=["secret123"],
            auto_rotate=True,
            rotate_days=14,
            traffic_limit_gb=100.0,
            rate_limit_enabled=True,
            rate_limit_connections=20,
            rate_limit_mbps=50.0,
            ip_whitelist=["192.168.1.1"],
            ip_blacklist=["10.0.0.1"],
            generate_qr=True,
            verbose=True,
        )
        assert config.host == "127.0.0.1"
        assert config.port == 8443
        assert config.dc_id == 4
        assert config.secrets == ["secret123"]
        assert config.auto_rotate is True
        assert config.rotate_days == 14
        assert config.traffic_limit_gb == 100.0
        assert config.rate_limit_enabled is True
        assert config.rate_limit_connections == 20
        assert config.rate_limit_mbps == 50.0
        assert config.ip_whitelist == ["192.168.1.1"]
        assert config.ip_blacklist == ["10.0.0.1"]
        assert config.generate_qr is True
        assert config.verbose is True


class TestMTProtoConfigFromDict:
    """Tests for from_dict method."""

    def test_from_dict_empty(self):
        """Test from_dict with empty dict."""
        config = MTProtoConfig.from_dict({})
        assert config.host == "0.0.0.0"
        assert config.port == 443
        assert config.dc_id == 2

    def test_from_dict_partial(self):
        """Test from_dict with partial data."""
        config = MTProtoConfig.from_dict({
            'host': '127.0.0.1',
            'port': 8080,
        })
        assert config.host == "127.0.0.1"
        assert config.port == 8080
        assert config.dc_id == 2  # default

    def test_from_dict_full(self):
        """Test from_dict with full data."""
        data = {
            'host': '127.0.0.1',
            'port': 8443,
            'dc_id': 4,
            'secrets': ['secret123'],
            'auto_rotate': True,
            'rotate_days': 14,
            'traffic_limit_gb': 100.0,
            'rate_limit_enabled': True,
            'rate_limit_connections': 20,
            'rate_limit_mbps': 50.0,
            'ip_whitelist': ['192.168.1.1'],
            'ip_blacklist': ['10.0.0.1'],
            'generate_qr': True,
            'verbose': True,
        }
        config = MTProtoConfig.from_dict(data)
        assert config.host == "127.0.0.1"
        assert config.secrets == ['secret123']
        assert config.auto_rotate is True


class TestMTProtoConfigToDict:
    """Tests for to_dict method."""

    def test_to_dict_default(self):
        """Test to_dict with default config."""
        config = MTProtoConfig()
        result = config.to_dict()
        assert result['host'] == "0.0.0.0"
        assert result['port'] == 443
        assert result['dc_id'] == 2
        assert result['secrets'] == []

    def test_to_dict_custom(self):
        """Test to_dict with custom config."""
        config = MTProtoConfig(host="127.0.0.1", port=8443)
        result = config.to_dict()
        assert result['host'] == "127.0.0.1"
        assert result['port'] == 8443


class TestMTProtoConfigToCliArgs:
    """Tests for to_cli_args method."""

    def test_to_cli_args_basic(self):
        """Test basic CLI arguments."""
        config = MTProtoConfig()
        args = config.to_cli_args()
        assert '--host' in args
        assert '0.0.0.0' in args
        assert '--port' in args
        assert '443' in args
        assert '--dc-id' in args
        assert '2' in args

    def test_to_cli_args_secrets(self):
        """Test CLI arguments with secrets."""
        config = MTProtoConfig(secrets=['secret1', 'secret2'])
        args = config.to_cli_args()
        assert '--secrets' in args
        assert 'secret1,secret2' in args

    def test_to_cli_args_auto_rotate(self):
        """Test CLI arguments with auto-rotate."""
        config = MTProtoConfig(auto_rotate=True, rotate_days=14)
        args = config.to_cli_args()
        assert '--auto-rotate' in args
        assert '--rotate-days' in args
        assert '14' in args

    def test_to_cli_args_traffic_limit(self):
        """Test CLI arguments with traffic limit."""
        config = MTProtoConfig(traffic_limit_gb=50.0)
        args = config.to_cli_args()
        assert '--traffic-limit-gb' in args
        assert '50.0' in args

    def test_to_cli_args_rate_limit(self):
        """Test CLI arguments with rate limiting."""
        config = MTProtoConfig(
            rate_limit_enabled=True,
            rate_limit_connections=20,
            rate_limit_mbps=50.0,
        )
        args = config.to_cli_args()
        assert '--rate-limit' in args
        assert '--rate-limit-connections' in args
        assert '20' in args
        assert '--rate-limit-mbps' in args
        assert '50.0' in args

    def test_to_cli_args_ip_whitelist(self):
        """Test CLI arguments with IP whitelist."""
        config = MTProtoConfig(ip_whitelist=['192.168.1.1', '192.168.1.2'])
        args = config.to_cli_args()
        assert '--ip-whitelist' in args
        assert '192.168.1.1,192.168.1.2' in args

    def test_to_cli_args_ip_blacklist(self):
        """Test CLI arguments with IP blacklist."""
        config = MTProtoConfig(ip_blacklist=['10.0.0.1'])
        args = config.to_cli_args()
        assert '--ip-blacklist' in args
        assert '10.0.0.1' in args

    def test_to_cli_args_qr(self):
        """Test CLI arguments with QR code."""
        config = MTProtoConfig(generate_qr=True)
        args = config.to_cli_args()
        assert '--qr' in args

    def test_to_cli_args_qr_output(self):
        """Test CLI arguments with QR output path."""
        config = MTProtoConfig(generate_qr=True, qr_output='qr.png')
        args = config.to_cli_args()
        assert '--qr' in args
        assert 'qr.png' in args

    def test_to_cli_args_verbose(self):
        """Test CLI arguments with verbose."""
        config = MTProtoConfig(verbose=True)
        args = config.to_cli_args()
        assert '--verbose' in args


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_config_not_found(self):
        """Test load_config with non-existent file."""
        config = load_config('nonexistent_config.json')
        assert isinstance(config, MTProtoConfig)
        assert config.host == "0.0.0.0"  # default

    def test_load_config_valid(self):
        """Test load_config with valid file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({'host': '127.0.0.1', 'port': 8443}, f)
            temp_path = f.name

        try:
            config = load_config(temp_path)
            assert config.host == "127.0.0.1"
            assert config.port == 8443
        finally:
            Path(temp_path).unlink()

    def test_load_config_invalid_json(self):
        """Test load_config with invalid JSON."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('{invalid json}')
            temp_path = f.name

        try:
            config = load_config(temp_path)
            assert isinstance(config, MTProtoConfig)
            assert config.host == "0.0.0.0"  # default
        finally:
            Path(temp_path).unlink()


class TestSaveConfig:
    """Tests for save_config function."""

    def test_save_config_success(self):
        """Test save_config successful save."""
        config = MTProtoConfig(host="127.0.0.1", port=8443)

        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = Path(tmpdir) / 'config.json'
            result = save_config(config, str(temp_path))

            assert result is True
            assert temp_path.exists()

            with open(temp_path) as f:
                data = json.load(f)
            assert data['host'] == "127.0.0.1"
            assert data['port'] == 8443

    def test_save_config_creates_directory(self):
        """Test save_config creates directory if needed."""
        config = MTProtoConfig()

        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = Path(tmpdir) / 'subdir' / 'config.json'
            result = save_config(config, str(temp_path))

            assert result is True
            assert temp_path.exists()


class TestGenerateSampleConfig:
    """Tests for generate_sample_config function."""

    def test_generate_sample_config(self):
        """Test generate_sample_config creates valid config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / 'sample_config.json'

            # Import here to avoid circular imports
            from proxy.mtproto_config import generate_sample_config
            generate_sample_config(str(output_path))

            assert output_path.exists()

            # Verify it's valid JSON
            with open(output_path) as f:
                data = json.load(f)

            assert 'host' in data
            assert 'port' in data
            assert 'secrets' in data
            assert len(data['secrets']) > 0
