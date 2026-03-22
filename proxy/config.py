"""
Configuration Management for TG WS Proxy.

Provides configuration loading, validation, and hot-reload support:
- JSON/YAML configuration files
- Environment variable overrides
- Default values with validation
- Hot-reload on file changes
- Schema validation

Author: Dupley Maxim Igorevich
© 2026 Dupley Maxim Igorevich. All rights reserved.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger('tg-ws-config')


@dataclass
class ServerConfig:
    """Server configuration."""
    host: str = "0.0.0.0"
    port: int = 8080
    socks_port: int = 1080
    max_connections: int = 500
    connection_timeout: float = 30.0


@dataclass
class WebSocketConfig:
    """WebSocket connection configuration."""
    pool_size: int = 4
    pool_max_size: int = 8
    pool_max_age: float = 120.0
    enable_compression: bool = False
    ping_interval: float = 30.0
    ping_timeout: float = 10.0
    reconnect_delay: float = 5.0
    max_reconnect_attempts: int = 10


@dataclass
class DNSConfig:
    """DNS resolver configuration."""
    enable_cache: bool = True
    cache_ttl: float = 300.0
    aggressive_ttl: bool = True
    use_async_dns: bool = True
    timeout: float = 5.0


@dataclass
class SecurityConfig:
    """Security configuration."""
    auth_required: bool = False
    auth_username: str = ""
    auth_password: str = ""
    ip_whitelist: list[str] = field(default_factory=list)
    ip_blacklist: list[str] = field(default_factory=list)
    rate_limit_enabled: bool = False
    rate_limit_requests: int = 100
    rate_limit_window: float = 60.0  # seconds
    enable_encryption: bool = False
    encryption_key: str = ""


@dataclass
class PerformanceConfig:
    """Performance optimization configuration."""
    enable_connection_pooling: bool = True
    enable_auto_dc_selection: bool = True
    enable_dns_cache: bool = True
    tcp_nodelay: bool = True
    recv_buffer_size: int = 65536
    send_buffer_size: int = 65536
    enable_profiling: bool = False
    profiling_interval: float = 60.0


@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file: str = ""
    max_size_mb: int = 10
    backup_count: int = 3
    enable_audit: bool = False
    audit_file: str = "audit.log"


@dataclass
class MonitoringConfig:
    """Monitoring and metrics configuration."""
    enable_metrics: bool = True
    metrics_port: int = 9090
    enable_prometheus: bool = True
    prometheus_path: str = "/metrics"
    enable_alerts: bool = True
    alert_dc_latency_warning: float = 150.0  # ms
    alert_dc_latency_critical: float = 200.0  # ms
    alert_cooldown: float = 120.0  # seconds


@dataclass
class Config:
    """Main configuration container."""
    server: ServerConfig = field(default_factory=ServerConfig)
    websocket: WebSocketConfig = field(default_factory=WebSocketConfig)
    dns: DNSConfig = field(default_factory=DNSConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    performance: PerformanceConfig = field(default_factory=PerformanceConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)

    # Data Center configuration
    dc_override: dict[int, str] = field(default_factory=dict)

    # File path for hot-reload
    _config_path: Path | None = field(default=None, repr=False)
    _on_reload: Callable[[Config], None] | None = field(default=None, repr=False)


class ConfigManager:
    """
    Configuration manager with hot-reload support.

    Features:
    - Load from JSON/YAML files
    - Environment variable overrides (TGWS_ prefix)
    - Default values
    - Hot-reload on file changes
    - Validation
    """

    DEFAULT_CONFIG_PATHS = [
        Path("config.json"),
        Path("config.yaml"),
        Path("config.yml"),
        Path.home() / ".tg-ws-proxy" / "config.json",
        Path.home() / ".tg-ws-proxy" / "config.yaml",
    ]

    def __init__(self):
        self.config = Config()
        self._file_watcher: asyncio.Task | None = None
        self._last_mtime: float = 0.0
        self._config_file: Path | None = None

    def load_from_dict(self, data: dict[str, Any]) -> Config:
        """Load configuration from dictionary."""
        config = Config()

        # Server
        if 'server' in data:
            srv = data['server']
            config.server = ServerConfig(
                host=srv.get('host', '0.0.0.0'),
                port=srv.get('port', 8080),
                socks_port=srv.get('socks_port', 1080),
                max_connections=srv.get('max_connections', 500),
                connection_timeout=srv.get('connection_timeout', 30.0),
            )

        # WebSocket
        if 'websocket' in data:
            ws = data['websocket']
            config.websocket = WebSocketConfig(
                pool_size=ws.get('pool_size', 4),
                pool_max_size=ws.get('pool_max_size', 8),
                pool_max_age=ws.get('pool_max_age', 120.0),
                enable_compression=ws.get('enable_compression', False),
                ping_interval=ws.get('ping_interval', 30.0),
                ping_timeout=ws.get('ping_timeout', 10.0),
                reconnect_delay=ws.get('reconnect_delay', 5.0),
                max_reconnect_attempts=ws.get('max_reconnect_attempts', 10),
            )

        # DNS
        if 'dns' in data:
            dns = data['dns']
            config.dns = DNSConfig(
                enable_cache=dns.get('enable_cache', True),
                cache_ttl=dns.get('cache_ttl', 300.0),
                aggressive_ttl=dns.get('aggressive_ttl', True),
                use_async_dns=dns.get('use_async_dns', True),
                timeout=dns.get('timeout', 5.0),
            )

        # Security
        if 'security' in data:
            sec = data['security']
            config.security = SecurityConfig(
                auth_required=sec.get('auth_required', False),
                auth_username=sec.get('auth_username', ''),
                auth_password=sec.get('auth_password', ''),
                ip_whitelist=sec.get('ip_whitelist', []),
                ip_blacklist=sec.get('ip_blacklist', []),
                rate_limit_enabled=sec.get('rate_limit_enabled', False),
                rate_limit_requests=sec.get('rate_limit_requests', 100),
                rate_limit_window=sec.get('rate_limit_window', 60.0),
                enable_encryption=sec.get('enable_encryption', False),
                encryption_key=sec.get('encryption_key', ''),
            )

        # Performance
        if 'performance' in data:
            perf = data['performance']
            config.performance = PerformanceConfig(
                enable_connection_pooling=perf.get('enable_connection_pooling', True),
                enable_auto_dc_selection=perf.get('enable_auto_dc_selection', True),
                enable_dns_cache=perf.get('enable_dns_cache', True),
                tcp_nodelay=perf.get('tcp_nodelay', True),
                recv_buffer_size=perf.get('recv_buffer_size', 65536),
                send_buffer_size=perf.get('send_buffer_size', 65536),
                enable_profiling=perf.get('enable_profiling', False),
                profiling_interval=perf.get('profiling_interval', 60.0),
            )

        # Logging
        if 'logging' in data:
            log_cfg = data['logging']
            config.logging = LoggingConfig(
                level=log_cfg.get('level', 'INFO'),
                format=log_cfg.get('format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s'),
                file=log_cfg.get('file', ''),
                max_size_mb=log_cfg.get('max_size_mb', 10),
                backup_count=log_cfg.get('backup_count', 3),
                enable_audit=log_cfg.get('enable_audit', False),
                audit_file=log_cfg.get('audit_file', 'audit.log'),
            )

        # Monitoring
        if 'monitoring' in data:
            mon = data['monitoring']
            config.monitoring = MonitoringConfig(
                enable_metrics=mon.get('enable_metrics', True),
                metrics_port=mon.get('metrics_port', 9090),
                enable_prometheus=mon.get('enable_prometheus', True),
                prometheus_path=mon.get('prometheus_path', '/metrics'),
                enable_alerts=mon.get('enable_alerts', True),
                alert_dc_latency_warning=mon.get('alert_dc_latency_warning', 150.0),
                alert_dc_latency_critical=mon.get('alert_dc_latency_critical', 200.0),
                alert_cooldown=mon.get('alert_cooldown', 120.0),
            )

        # DC Override
        if 'dc_override' in data:
            config.dc_override = {int(k): v for k, v in data['dc_override'].items()}

        self.config = config
        return self.config

    def load_from_file(self, path: Path | str) -> Config:
        """Load configuration from JSON or YAML file."""
        path = Path(path)

        if not path.exists():
            log.warning(f"Config file not found: {path}")
            return self.config

        self._config_file = path

        try:
            if path.suffix in ('.yaml', '.yml'):
                import yaml  # type: ignore[import-not-found]
                with open(path, encoding='utf-8') as f:
                    data = yaml.safe_load(f) or {}
            else:
                with open(path, encoding='utf-8') as f:
                    data = json.load(f) or {}

            self.config = self.load_from_dict(data)
            self.config._config_path = path
            self._last_mtime = path.stat().st_mtime

            log.info(f"Configuration loaded from {path}")
            self._apply_environment_overrides()

            return self.config

        except Exception as e:
            log.error(f"Failed to load config from {path}: {e}")
            return self.config

    def load(self, path: Path | str | None = None) -> Config:
        """
        Load configuration from file or find default.

        Args:
            path: Optional path to config file. If None, searches default paths.
        """
        if path:
            return self.load_from_file(path)

        # Search default paths
        for default_path in self.DEFAULT_CONFIG_PATHS:
            if default_path.exists():
                return self.load_from_file(default_path)

        log.info("Using default configuration")
        self._apply_environment_overrides()
        return self.config

    def _apply_environment_overrides(self) -> None:
        """Apply environment variable overrides (TGWS_ prefix)."""
        env_map = {
            'TGWS_HOST': ('server', 'host', str),
            'TGWS_PORT': ('server', 'port', int),
            'TGWS_SOCKS_PORT': ('server', 'socks_port', int),
            'TGWS_WS_POOL_SIZE': ('websocket', 'pool_size', int),
            'TGWS_WS_POOL_MAX': ('websocket', 'pool_max_size', int),
            'TGWS_DNS_CACHE_TTL': ('dns', 'cache_ttl', float),
            'TGWS_AUTH_REQUIRED': ('security', 'auth_required', lambda x: x.lower() == 'true'),
            'TGWS_AUTH_USERNAME': ('security', 'auth_username', str),
            'TGWS_AUTH_PASSWORD': ('security', 'auth_password', str),
            'TGWS_RATE_LIMIT': ('security', 'rate_limit_enabled', lambda x: x.lower() == 'true'),
            'TGWS_LOG_LEVEL': ('logging', 'level', str),
            'TGWS_METRICS_ENABLED': ('monitoring', 'enable_metrics', lambda x: x.lower() == 'true'),
            'TGWS_METRICS_PORT': ('monitoring', 'metrics_port', int),
        }

        for env_var, (section, attr, converter) in env_map.items():
            value = os.environ.get(env_var)
            if value:
                try:
                    converted = converter(value)
                    section_obj = getattr(self.config, section)
                    setattr(section_obj, attr, converted)
                    log.debug(f"Config override: {env_var}={value}")
                except Exception as e:
                    log.warning(f"Failed to apply env override {env_var}={value}: {e}")

    def save(self, path: Path | str | None = None) -> None:
        """Save current configuration to file."""
        path = Path(path) if path else self.config._config_path
        if not path:
            raise ValueError("No config path specified")

        data = self._to_dict()

        path.parent.mkdir(parents=True, exist_ok=True)

        if path.suffix in ('.yaml', '.yml'):
            import yaml  # type: ignore[import-not-found]
            with open(path, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
        else:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

        log.info(f"Configuration saved to {path}")

    def _to_dict(self) -> dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            'server': {
                'host': self.config.server.host,
                'port': self.config.server.port,
                'socks_port': self.config.server.socks_port,
                'max_connections': self.config.server.max_connections,
                'connection_timeout': self.config.server.connection_timeout,
            },
            'websocket': {
                'pool_size': self.config.websocket.pool_size,
                'pool_max_size': self.config.websocket.pool_max_size,
                'pool_max_age': self.config.websocket.pool_max_age,
                'enable_compression': self.config.websocket.enable_compression,
                'ping_interval': self.config.websocket.ping_interval,
                'ping_timeout': self.config.websocket.ping_timeout,
                'reconnect_delay': self.config.websocket.reconnect_delay,
                'max_reconnect_attempts': self.config.websocket.max_reconnect_attempts,
            },
            'dns': {
                'enable_cache': self.config.dns.enable_cache,
                'cache_ttl': self.config.dns.cache_ttl,
                'aggressive_ttl': self.config.dns.aggressive_ttl,
                'use_async_dns': self.config.dns.use_async_dns,
                'timeout': self.config.dns.timeout,
            },
            'security': {
                'auth_required': self.config.security.auth_required,
                'auth_username': self.config.security.auth_username,
                'auth_password': self.config.security.auth_password,
                'ip_whitelist': self.config.security.ip_whitelist,
                'ip_blacklist': self.config.security.ip_blacklist,
                'rate_limit_enabled': self.config.security.rate_limit_enabled,
                'rate_limit_requests': self.config.security.rate_limit_requests,
                'rate_limit_window': self.config.security.rate_limit_window,
                'enable_encryption': self.config.security.enable_encryption,
                'encryption_key': self.config.security.encryption_key,
            },
            'performance': {
                'enable_connection_pooling': self.config.performance.enable_connection_pooling,
                'enable_auto_dc_selection': self.config.performance.enable_auto_dc_selection,
                'enable_dns_cache': self.config.performance.enable_dns_cache,
                'tcp_nodelay': self.config.performance.tcp_nodelay,
                'recv_buffer_size': self.config.performance.recv_buffer_size,
                'send_buffer_size': self.config.performance.send_buffer_size,
                'enable_profiling': self.config.performance.enable_profiling,
                'profiling_interval': self.config.performance.profiling_interval,
            },
            'logging': {
                'level': self.config.logging.level,
                'format': self.config.logging.format,
                'file': self.config.logging.file,
                'max_size_mb': self.config.logging.max_size_mb,
                'backup_count': self.config.logging.backup_count,
                'enable_audit': self.config.logging.enable_audit,
                'audit_file': self.config.logging.audit_file,
            },
            'monitoring': {
                'enable_metrics': self.config.monitoring.enable_metrics,
                'metrics_port': self.config.monitoring.metrics_port,
                'enable_prometheus': self.config.monitoring.enable_prometheus,
                'prometheus_path': self.config.monitoring.prometheus_path,
                'enable_alerts': self.config.monitoring.enable_alerts,
                'alert_dc_latency_warning': self.config.monitoring.alert_dc_latency_warning,
                'alert_dc_latency_critical': self.config.monitoring.alert_dc_latency_critical,
                'alert_cooldown': self.config.monitoring.alert_cooldown,
            },
            'dc_override': {str(k): v for k, v in self.config.dc_override.items()},
        }

    async def start_hot_reload(self, interval: float = 5.0) -> None:
        """Start hot-reload watcher for configuration file."""
        if not self.config._config_path:
            return

        import asyncio

        while True:
            await asyncio.sleep(interval)

            try:
                path = self.config._config_path
                if not path.exists():
                    continue

                current_mtime = path.stat().st_mtime
                if current_mtime > self._last_mtime:
                    log.info(f"Config file changed, reloading: {path}")
                    self.load_from_file(path)

                    if self.config._on_reload:
                        self.config._on_reload(self.config)

                    self._last_mtime = current_mtime

            except Exception as e:
                log.error(f"Hot-reload check failed: {e}")

    def stop_hot_reload(self) -> None:
        """Stop hot-reload watcher."""
        if self._file_watcher:
            self._file_watcher.cancel()
            self._file_watcher = None


# Global configuration manager
_config_manager: ConfigManager | None = None


def get_config() -> Config:
    """Get current configuration."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
        _config_manager.load()
    return _config_manager.config


def load_config(path: Path | str | None = None) -> Config:
    """Load configuration from file."""
    global _config_manager
    _config_manager = ConfigManager()
    return _config_manager.load(path)


def save_config(path: Path | str | None = None) -> None:
    """Save current configuration to file."""
    if _config_manager is None:
        raise RuntimeError("Config manager not initialized")
    _config_manager.save(path)


def reload_config() -> Config:
    """Reload configuration from file."""
    if _config_manager is None or not _config_manager.config._config_path:
        return get_config()
    return _config_manager.load_from_file(_config_manager.config._config_path)
