"""
Configuration management for MTProto Proxy.

Loads and saves configuration from/to JSON file.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path

log = logging.getLogger('tg-mtproto-config')


@dataclass
class MTProtoConfig:
    """MTProto Proxy configuration."""

    # Server settings
    host: str = "0.0.0.0"
    port: int = 443
    dc_id: int = 2  # Telegram DC ID (1-5)

    # Secrets
    secrets: list[str] = field(default_factory=list)

    # Auto-rotation
    auto_rotate: bool = False
    rotate_days: int = 7

    # Traffic limits
    traffic_limit_gb: float | None = None

    # Rate limiting
    rate_limit_enabled: bool = False
    rate_limit_connections: int = 10
    rate_limit_mbps: float = 10.0

    # IP filtering
    ip_whitelist: list[str] | None = None
    ip_blacklist: list[str] | None = None

    # QR code
    generate_qr: bool = False
    qr_output: str | None = None

    # Logging
    verbose: bool = False

    @classmethod
    def from_dict(cls, data: dict) -> MTProtoConfig:
        """Create config from dictionary."""
        return cls(
            host=data.get('host', cls.host),
            port=data.get('port', cls.port),
            dc_id=data.get('dc_id', cls.dc_id),
            secrets=data.get('secrets', []),
            auto_rotate=data.get('auto_rotate', False),
            rotate_days=data.get('rotate_days', 7),
            traffic_limit_gb=data.get('traffic_limit_gb'),
            rate_limit_enabled=data.get('rate_limit_enabled', False),
            rate_limit_connections=data.get('rate_limit_connections', 10),
            rate_limit_mbps=data.get('rate_limit_mbps', 10.0),
            ip_whitelist=data.get('ip_whitelist'),
            ip_blacklist=data.get('ip_blacklist'),
            generate_qr=data.get('generate_qr', False),
            qr_output=data.get('qr_output'),
            verbose=data.get('verbose', False),
        )

    def to_dict(self) -> dict:
        """Convert config to dictionary."""
        return asdict(self)

    def to_cli_args(self) -> list[str]:
        """Convert config to CLI arguments list."""
        args = []

        # Server
        args.extend(['--host', self.host])
        args.extend(['--port', str(self.port)])
        args.extend(['--dc-id', str(self.dc_id)])

        # Secrets
        if self.secrets:
            args.extend(['--secrets', ','.join(self.secrets)])

        # Auto-rotation
        if self.auto_rotate:
            args.append('--auto-rotate')
            args.extend(['--rotate-days', str(self.rotate_days)])

        # Traffic limit
        if self.traffic_limit_gb is not None:
            args.extend(['--traffic-limit-gb', str(self.traffic_limit_gb)])

        # Rate limiting
        if self.rate_limit_enabled:
            args.append('--rate-limit')
            args.extend(['--rate-limit-connections', str(self.rate_limit_connections)])
            args.extend(['--rate-limit-mbps', str(self.rate_limit_mbps)])

        # IP filtering
        if self.ip_whitelist:
            args.extend(['--ip-whitelist', ','.join(self.ip_whitelist)])
        if self.ip_blacklist:
            args.extend(['--ip-blacklist', ','.join(self.ip_blacklist)])

        # QR code
        if self.generate_qr:
            if self.qr_output:
                args.extend(['--qr', self.qr_output])
            else:
                args.append('--qr')

        # Logging
        if self.verbose:
            args.append('--verbose')

        return args


def load_config(config_path: str = "mtproto_config.json") -> MTProtoConfig:
    """
    Load configuration from JSON file.

    Args:
        config_path: Path to configuration file.

    Returns:
        MTProtoConfig object.
    """
    path = Path(config_path)

    if not path.exists():
        log.info("Config file not found: %s, using defaults", config_path)
        return MTProtoConfig()

    try:
        with open(path, encoding='utf-8') as f:
            data = json.load(f)

        log.info("Loaded config from: %s", config_path)
        return MTProtoConfig.from_dict(data)

    except json.JSONDecodeError as e:
        log.error("Invalid JSON in config file: %s", e)
        return MTProtoConfig()

    except Exception as e:
        log.error("Failed to load config: %s", e)
        return MTProtoConfig()


def save_config(config: MTProtoConfig, config_path: str = "mtproto_config.json") -> bool:
    """
    Save configuration to JSON file.

    Args:
        config: MTProtoConfig object.
        config_path: Path to configuration file.

    Returns:
        True if saved successfully.
    """
    try:
        path = Path(config_path)

        # Create directory if needed
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(config.to_dict(), f, indent=2, ensure_ascii=False)

        log.info("Saved config to: %s", config_path)
        return True

    except Exception as e:
        log.error("Failed to save config: %s", e)
        return False


def generate_sample_config(output_path: str = "mtproto_config.example.json"):
    """Generate a sample configuration file."""
    config = MTProtoConfig(
        host="0.0.0.0",
        port=443,
        secrets=["your_secret_here_0123456789abcdef"],
        auto_rotate=True,
        rotate_days=7,
        traffic_limit_gb=50.0,
        rate_limit_enabled=True,
        rate_limit_connections=10,
        rate_limit_mbps=10.0,
        ip_whitelist=None,
        ip_blacklist=["192.168.1.100", "192.168.1.101"],
        generate_qr=True,
        verbose=False,
    )

    save_config(config, output_path)
    log.info("Generated sample config: %s", output_path)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    generate_sample_config()

    # Demo: load and print
    config = load_config("mtproto_config.example.json")
    print("\nLoaded config:")
    print(json.dumps(config.to_dict(), indent=2))

    print("\nCLI arguments:")
    print('python -m proxy.mtproto_proxy ' + ' '.join(config.to_cli_args()))
