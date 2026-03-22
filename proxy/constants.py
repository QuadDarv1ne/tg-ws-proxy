"""Constants for TG WS Proxy."""

from __future__ import annotations

import socket as _socket
import struct

# =============================================================================
# Network defaults
# =============================================================================

DEFAULT_PORT = 1080
DEFAULT_HOST = "127.0.0.1"

# Socket options
TCP_NODELAY = True
RECV_BUF_SIZE = 65536
SEND_BUF_SIZE = 65536

# WebSocket pool settings
WS_POOL_SIZE = 4
WS_POOL_MAX_AGE = 120.0  # seconds
WS_POOL_MAX_SIZE = 8  # maximum connections per DC

# Timeout settings
WS_CONNECT_TIMEOUT = 10.0
WS_HANDSHAKE_TIMEOUT = 8.0
SOCKS5_HANDSHAKE_TIMEOUT = 10.0
INIT_READ_TIMEOUT = 15.0
TCP_FALLBACK_TIMEOUT = 10.0

# Rate limiting
DC_FAIL_COOLDOWN = 60.0  # seconds

# =============================================================================
# MTProto constants
# =============================================================================

# MTProto protocol magic bytes
MTPROTO_OBFUSCATION_MAGIC = b'\x00' * 8
MTPROTO_MAGIC_INTERMEDIATE = b'\xee\xee\xee\xee'

# Valid protocol identifiers
PROTO_OBFUSCATED = 0xEFEFEFEF
PROTO_ABRIDGED = 0xEEEEEEEE
PROTO_PADDED_ABRIDGED = 0xDDDDDDDD

# Init packet structure
INIT_PACKET_SIZE = 64
INIT_KEY_OFFSET = 8
INIT_KEY_SIZE = 32
INIT_IV_OFFSET = 40
INIT_IV_SIZE = 16
INIT_DC_OFFSET = 60
INIT_DC_SIZE = 2

# Abridged protocol prefix
ABRIDGED_SHORT_PREFIX = 0x7F

# Encryption settings
MTPROTO_AES_KEY_SIZE = 32  # 256 bits
MTPROTO_AES_IV_SIZE = 32   # 256 bits for IGE mode
MTPROTO_BLOCK_SIZE = 16    # AES block size

# Secret key length (32 hex chars = 16 bytes)
MTPROTO_SECRET_LENGTH = 32

# Default MTProto port (443 for HTTPS masquerading)
MTPROTO_DEFAULT_PORT = 443
MTPROTO_DEFAULT_HOST = "0.0.0.0"

# =============================================================================
# Telegram IP ranges
# =============================================================================

TG_RANGES = [
    # 185.76.151.0/24
    (struct.unpack('!I', _socket.inet_aton('185.76.151.0'))[0],
     struct.unpack('!I', _socket.inet_aton('185.76.151.255'))[0]),
    # 149.154.160.0/20
    (struct.unpack('!I', _socket.inet_aton('149.154.160.0'))[0],
     struct.unpack('!I', _socket.inet_aton('149.154.175.255'))[0]),
    # 91.105.192.0/23
    (struct.unpack('!I', _socket.inet_aton('91.105.192.0'))[0],
     struct.unpack('!I', _socket.inet_aton('91.105.193.255'))[0]),
    # 91.108.0.0/16
    (struct.unpack('!I', _socket.inet_aton('91.108.0.0'))[0],
     struct.unpack('!I', _socket.inet_aton('91.108.255.255'))[0]),
]

# =============================================================================
# Telegram DC mappings
# =============================================================================

# IP -> (dc_id, is_media)
_IP_TO_DC: dict[str, tuple[int, bool]] = {
    # DC1
    '149.154.175.50': (1, False), '149.154.175.51': (1, False),
    '149.154.175.53': (1, False), '149.154.175.54': (1, False),
    '149.154.175.52': (1, True),
    # DC2
    '149.154.167.41': (2, False), '149.154.167.50': (2, False),
    '149.154.167.51': (2, False), '149.154.167.220': (2, False),
    '95.161.76.100':  (2, False),
    '149.154.167.151': (2, True), '149.154.167.222': (2, True),
    '149.154.167.223': (2, True), '149.154.162.123': (2, True),
    # DC3
    '149.154.175.100': (3, False), '149.154.175.101': (3, False),
    '149.154.175.102': (3, True),
    # DC4
    '149.154.167.91': (4, False), '149.154.167.92': (4, False),
    '149.154.164.250': (4, True), '149.154.166.120': (4, True),
    '149.154.166.121': (4, True), '149.154.167.118': (4, True),
    '149.154.165.111': (4, True),
    # DC5
    '91.108.56.100': (5, False), '91.108.56.101': (5, False),
    '91.108.56.116': (5, False), '91.108.56.126': (5, False),
    '149.154.171.5':  (5, False),
    '91.108.56.102': (5, True), '91.108.56.128': (5, True),
    '91.108.56.151': (5, True),
}

# =============================================================================
# WebSocket domains
# =============================================================================

WS_DOMAIN_TEMPLATE = "kws{dc}.web.telegram.org"
WS_DOMAIN_MEDIA_TEMPLATE = "kws{dc}-1.web.telegram.org"

# =============================================================================
# Application constants
# =============================================================================

APP_NAME = "TgWsProxy"
APP_DIR_NAME = "TgWsProxy"

# Config file names
CONFIG_FILE_NAME = "config.json"
LOG_FILE_NAME = "proxy.log"
FIRST_RUN_MARKER_NAME = ".first_run_done"
IPV6_WARN_MARKER_NAME = ".ipv6_warned"
LOCK_FILE_EXT = ".lock"

# Default configuration
DEFAULT_CONFIG = {
    "port": DEFAULT_PORT,
    "host": DEFAULT_HOST,
    "dc_ip": ["2:149.154.167.220", "4:149.154.167.220"],
    "verbose": False,
    "ip_whitelist": [],  # Empty = allow all IPs
    "compact_menu": False,  # Compact tray menu mode

    # Modern encryption settings
    "encryption_type": "aes-256-gcm",  # aes-256-gcm, chacha20-poly1305, xchacha20-poly1305
    "encryption_enabled": True,  # Enable additional encryption layer
    "key_rotation_interval": 3600,  # Rotate keys every hour (seconds)

    # Rate limiting settings
    "rate_limit_rps": 10.0,  # Requests per second per IP
    "rate_limit_rpm": 100,  # Requests per minute per IP
    "rate_limit_max_conn": 500,  # Max concurrent connections
    "rate_limit_per_ip": 10,  # Max connections per IP
    "rate_limit_ban_threshold": 5,  # Violations before ban
    "rate_limit_ban_duration": 300.0,  # Ban duration in seconds

    # Anti-censorship settings
    "anticensorship": {
        "enabled": False,
        "preset": "default",
        "obfuscation": {
            "enabled": False,
            "enable_obfs4": True,
            "enable_shadowsocks": False,
            "shadowsocks_password": "",
            "shadowsocks_cipher": "aes-256-gcm",
            "enable_fragmentation": True,
            "fragment_min_size": 64,
            "fragment_max_size": 256,
            "enable_traffic_shaping": True,
            "traffic_jitter_ms": [10, 100],
            "traffic_padding_ratio": 0.1,
            "enable_tls_spoof": True,
            "browser_profile": "chrome_120",
            "enable_domain_fronting": False,
            "fronting_provider": "cloudflare",
        },
        "relay": {
            "enabled": False,
            "auto_select": True,
            "preferred_relay": "",
            "preferred_region": "",
            "require_fronting": False,
            "custom_relays": [],
        },
        "http2": {
            "enable_fallback": True,
            "prefer_http2": False,
            "http2_only": False,
            "path": "/apiws",
            "timeout": 10.0,
        },
        "censorship_detection": {
            "enabled": True,
            "auto_switch": True,
            "failure_threshold": 5,
            "failure_window": 60,
            "check_interval": 30,
        },
    },
}

# =============================================================================
# UI colors (Telegram brand)
# =============================================================================

TG_BLUE = "#3390ec"
TG_BLUE_HOVER = "#2b7cd4"

# Status indicator colors
STATUS_OK = "#4ade80"        # Green - proxy running normally
STATUS_ERROR = "#f87171"     # Red - proxy error/stopped
STATUS_WARNING = "#fbbf24"   # Yellow - degraded performance

# Light theme
UI_BG = "#ffffff"
UI_FIELD_BG = "#f0f2f5"
UI_FIELD_BORDER = "#d6d9dc"
UI_TEXT_PRIMARY = "#000000"
UI_TEXT_SECONDARY = "#707579"

# Dark theme
UI_BG_DARK = "#2d3748"
UI_FIELD_BG_DARK = "#1a202c"
UI_FIELD_BORDER_DARK = "#4a5568"
UI_TEXT_PRIMARY_DARK = "#f7fafc"
UI_TEXT_SECONDARY_DARK = "#cbd5e0"

UI_FONT_FAMILY = "Segoe UI"

# =============================================================================
# Telegram DC IP mappings (for MTProto proxy)
# =============================================================================

# DC ID -> IP address (for direct TCP connection)
DC_IP_MAP = {
    1: "149.154.175.53",
    2: "149.154.167.220",
    3: "149.154.175.100",
    4: "149.154.167.91",
    5: "91.108.56.100",
}

# Default DC for MTProto proxy (DC2 is recommended for most users)
DEFAULT_DC_ID = 2

# =============================================================================
# Error codes
# =============================================================================

WSAEADDRINUSE = 10048
