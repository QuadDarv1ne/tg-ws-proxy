"""
Anti-censorship configuration for TG WS Proxy.

Configuration options for pluggable transports, domain fronting,
and other circumvention features.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ObfuscationConfig:
    """Configuration for traffic obfuscation."""
    
    # Enable obfuscation
    enabled: bool = False
    
    # Obfs4-like obfuscation
    enable_obfs4: bool = True
    
    # Shadowsocks-style encryption
    enable_shadowsocks: bool = False
    shadowsocks_password: str = ""
    shadowsocks_cipher: str = "aes-256-gcm"
    
    # WebSocket fragmentation
    enable_fragmentation: bool = True
    fragment_min_size: int = 64
    fragment_max_size: int = 256
    
    # Traffic shaping
    enable_traffic_shaping: bool = True
    traffic_jitter_ms: tuple[int, int] = (10, 100)
    traffic_padding_ratio: float = 0.1
    
    # TLS fingerprint spoofing
    enable_tls_spoof: bool = True
    browser_profile: str = "chrome_120"  # chrome_120, firefox_121, safari_17
    
    # Domain fronting
    enable_domain_fronting: bool = False
    fronting_provider: str = "cloudflare"  # cloudflare, google, azure, amazon
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "enabled": self.enabled,
            "enable_obfs4": self.enable_obfs4,
            "enable_shadowsocks": self.enable_shadowsocks,
            "shadowsocks_password": self.shadowsocks_password,
            "shadowsocks_cipher": self.shadowsocks_cipher,
            "enable_fragmentation": self.enable_fragmentation,
            "fragment_min_size": self.fragment_min_size,
            "fragment_max_size": self.fragment_max_size,
            "enable_traffic_shaping": self.enable_traffic_shaping,
            "traffic_jitter_ms": list(self.traffic_jitter_ms),
            "traffic_padding_ratio": self.traffic_padding_ratio,
            "enable_tls_spoof": self.enable_tls_spoof,
            "browser_profile": self.browser_profile,
            "enable_domain_fronting": self.enable_domain_fronting,
            "fronting_provider": self.fronting_provider,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ObfuscationConfig:
        """Create from dictionary."""
        return cls(
            enabled=data.get("enabled", False),
            enable_obfs4=data.get("enable_obfs4", True),
            enable_shadowsocks=data.get("enable_shadowsocks", False),
            shadowsocks_password=data.get("shadowsocks_password", ""),
            shadowsocks_cipher=data.get("shadowsocks_cipher", "aes-256-gcm"),
            enable_fragmentation=data.get("enable_fragmentation", True),
            fragment_min_size=data.get("fragment_min_size", 64),
            fragment_max_size=data.get("fragment_max_size", 256),
            enable_traffic_shaping=data.get("enable_traffic_shaping", True),
            traffic_jitter_ms=tuple(data.get("traffic_jitter_ms", [10, 100])),
            traffic_padding_ratio=data.get("traffic_padding_ratio", 0.1),
            enable_tls_spoof=data.get("enable_tls_spoof", True),
            browser_profile=data.get("browser_profile", "chrome_120"),
            enable_domain_fronting=data.get("enable_domain_fronting", False),
            fronting_provider=data.get("fronting_provider", "cloudflare"),
        )


@dataclass
class RelayConfig:
    """Configuration for bridge/relay routing."""
    
    # Enable relay routing
    enabled: bool = False
    
    # Auto-select best relay
    auto_select: bool = True
    
    # Preferred relay ID (if not auto-select)
    preferred_relay: str = ""
    
    # Preferred region
    preferred_region: str = ""
    
    # Require domain fronting
    require_fronting: bool = False
    
    # Custom relays
    custom_relays: list[dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "enabled": self.enabled,
            "auto_select": self.auto_select,
            "preferred_relay": self.preferred_relay,
            "preferred_region": self.preferred_region,
            "require_fronting": self.require_fronting,
            "custom_relays": self.custom_relays,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RelayConfig:
        """Create from dictionary."""
        return cls(
            enabled=data.get("enabled", False),
            auto_select=data.get("auto_select", True),
            preferred_relay=data.get("preferred_relay", ""),
            preferred_region=data.get("preferred_region", ""),
            require_fronting=data.get("require_fronting", False),
            custom_relays=data.get("custom_relays", []),
        )


@dataclass
class HTTP2Config:
    """Configuration for HTTP/2 transport."""
    
    # Enable HTTP/2 as fallback
    enable_fallback: bool = True
    
    # Try HTTP/2 first (instead of WebSocket)
    prefer_http2: bool = False
    
    # Use HTTP/2 only (no WebSocket)
    http2_only: bool = False
    
    # HTTP/2 path
    path: str = "/apiws"
    
    # Connection timeout
    timeout: float = 10.0
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "enable_fallback": self.enable_fallback,
            "prefer_http2": self.prefer_http2,
            "http2_only": self.http2_only,
            "path": self.path,
            "timeout": self.timeout,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HTTP2Config:
        """Create from dictionary."""
        return cls(
            enable_fallback=data.get("enable_fallback", True),
            prefer_http2=data.get("prefer_http2", False),
            http2_only=data.get("http2_only", False),
            path=data.get("path", "/apiws"),
            timeout=data.get("timeout", 10.0),
        )


@dataclass
class CensorshipDetectionConfig:
    """Configuration for censorship detection."""
    
    # Enable auto-detection
    enabled: bool = True
    
    # Auto-switch to alternative transport
    auto_switch: bool = True
    
    # Failure threshold before switching
    failure_threshold: int = 5
    
    # Time window for failures (seconds)
    failure_window: int = 60
    
    # Check interval for blocked detection (seconds)
    check_interval: int = 30
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "enabled": self.enabled,
            "auto_switch": self.auto_switch,
            "failure_threshold": self.failure_threshold,
            "failure_window": self.failure_window,
            "check_interval": self.check_interval,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CensorshipDetectionConfig:
        """Create from dictionary."""
        return cls(
            enabled=data.get("enabled", True),
            auto_switch=data.get("auto_switch", True),
            failure_threshold=data.get("failure_threshold", 5),
            failure_window=data.get("failure_window", 60),
            check_interval=data.get("check_interval", 30),
        )


@dataclass
class AntiCensorshipConfig:
    """Main anti-censorship configuration."""
    
    # Master switch for all anti-censorship features
    enabled: bool = False
    
    # Sub-configurations
    obfuscation: ObfuscationConfig = field(default_factory=ObfuscationConfig)
    relay: RelayConfig = field(default_factory=RelayConfig)
    http2: HTTP2Config = field(default_factory=HTTP2Config)
    censorship_detection: CensorshipDetectionConfig = field(
        default_factory=CensorshipDetectionConfig
    )
    
    # Preset modes
    # "default", "aggressive", "stealth", "custom"
    preset: str = "default"
    
    def apply_preset(self, preset: str) -> None:
        """Apply predefined preset configuration."""
        self.preset = preset
        
        if preset == "default":
            # Basic obfuscation only
            self.enabled = True
            self.obfuscation.enabled = True
            self.obfuscation.enable_obfs4 = True
            self.obfuscation.enable_fragmentation = True
            self.obfuscation.enable_tls_spoof = True
            self.relay.enabled = False
            self.obfuscation.enable_domain_fronting = False
            
        elif preset == "aggressive":
            # All features enabled
            self.enabled = True
            self.obfuscation.enabled = True
            self.obfuscation.enable_obfs4 = True
            self.obfuscation.enable_fragmentation = True
            self.obfuscation.enable_tls_spoof = True
            self.obfuscation.enable_traffic_shaping = True
            self.obfuscation.enable_domain_fronting = True
            self.relay.enabled = True
            self.relay.auto_select = True
            self.http2.enable_fallback = True
            
        elif preset == "stealth":
            # Maximum stealth
            self.enabled = True
            self.obfuscation.enabled = True
            self.obfuscation.enable_obfs4 = True
            self.obfuscation.enable_shadowsocks = True
            self.obfuscation.enable_fragmentation = True
            self.obfuscation.enable_tls_spoof = True
            self.obfuscation.enable_traffic_shaping = True
            self.obfuscation.traffic_jitter_ms = (50, 200)
            self.obfuscation.traffic_padding_ratio = 0.2
            self.obfuscation.enable_domain_fronting = True
            self.obfuscation.browser_profile = "firefox_121"
            self.relay.enabled = True
            self.relay.require_fronting = True
            self.http2.enable_fallback = True
            self.http2.prefer_http2 = True
            
        elif preset == "custom":
            # Keep current settings
            pass
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "enabled": self.enabled,
            "preset": self.preset,
            "obfuscation": self.obfuscation.to_dict(),
            "relay": self.relay.to_dict(),
            "http2": self.http2.to_dict(),
            "censorship_detection": self.censorship_detection.to_dict(),
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AntiCensorshipConfig:
        """Create from dictionary."""
        config = cls(
            enabled=data.get("enabled", False),
            preset=data.get("preset", "default"),
            obfuscation=ObfuscationConfig.from_dict(
                data.get("obfuscation", {})
            ),
            relay=RelayConfig.from_dict(data.get("relay", {})),
            http2=HTTP2Config.from_dict(data.get("http2", {})),
            censorship_detection=CensorshipDetectionConfig.from_dict(
                data.get("censorship_detection", {})
            ),
        )
        
        # Apply preset if specified
        if config.preset != "custom":
            config.apply_preset(config.preset)
            
        return config


# Default configuration instance
DEFAULT_CONFIG = AntiCensorshipConfig()
