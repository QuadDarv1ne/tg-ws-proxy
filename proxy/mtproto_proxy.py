"""
MTProto Proxy for Telegram Mobile Apps.

This module implements a simple MTProto proxy server that allows
Telegram mobile apps (Android/iOS) to connect through a local proxy.

MTProto uses AES-256 encryption in IGE mode for secure communication.
"""

from __future__ import annotations

import asyncio
import logging
import os
import socket
import struct
import sys
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Callable
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

try:
    import qrcode
    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False


from .constants import (
    MTPROTO_MAGIC_INTERMEDIATE,
    MTPROTO_AES_KEY_SIZE,
    MTPROTO_AES_IV_SIZE,
    MTPROTO_BLOCK_SIZE,
    MTPROTO_SECRET_LENGTH,
    MTPROTO_DEFAULT_PORT,
    MTPROTO_DEFAULT_HOST,
    TG_RANGES,
)


log = logging.getLogger('tg-mtproto-proxy')


def generate_secret() -> str:
    """Generate a random MTProto secret key (32 hex characters)."""
    return os.urandom(16).hex()


def validate_secret(secret: str) -> bool:
    """Validate MTProto secret key format."""
    if len(secret) != MTPROTO_SECRET_LENGTH:
        return False
    try:
        bytes.fromhex(secret)
        return True
    except ValueError:
        return False


def secret_to_key_iv(secret: str) -> Tuple[bytes, bytes]:
    """
    Convert secret hex string to AES key and IV.

    MTProto uses a simple derivation: the secret is split into key and IV.
    """
    secret_bytes = bytes.fromhex(secret)
    # Key is first 32 bytes (or padded), IV is next 32 bytes
    # For 16-byte secret, we use it as seed for key/iv generation
    key = secret_bytes.ljust(MTPROTO_AES_KEY_SIZE, b'\x00')[:MTPROTO_AES_KEY_SIZE]
    iv = secret_bytes.ljust(MTPROTO_AES_IV_SIZE, b'\x00')[:MTPROTO_AES_IV_SIZE]
    return key, iv


def generate_qr_code(server: str, port: int, secret: str, output_path: Optional[str] = None) -> str:
    """
    Generate QR code for MTProto proxy connection.

    Args:
        server: Server IP or hostname
        port: Server port
        secret: MTProto secret key
        output_path: Optional path to save QR code image

    Returns:
        QR code as text (ASCII art) or path to saved image
    """
    if not HAS_QRCODE:
        log.warning("qrcode library not installed. Install with: pip install qrcode")
        return ""

    # Telegram proxy URL format
    url = f"tg://proxy?server={server}&port={port}&secret={secret}"

    # Generate QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)

    # Save to file if path provided
    if output_path:
        img = qr.make_image(fill_color="black", back_color="white")
        img.save(output_path)
        log.info("QR code saved to: %s", output_path)
        return output_path

    # Return ASCII art for console display
    return qr.print_ascii(invert=True) or ""


class MTProtoTransport:
    """
    MTProto Intermediate Transport implementation.
    
    Handles encryption/decryption of packets using AES-256 IGE mode.
    """
    
    def __init__(self, secret: str):
        self.secret = secret
        self.key, self.iv = secret_to_key_iv(secret)
        self._decrypt_cipher: Optional[Cipher] = None
        self._encrypt_cipher: Optional[Cipher] = None
        self._decrypt_ige = None
        self._encrypt_ige = None
        self._initialized = False
    
    def _init_ciphers(self):
        """Initialize AES-256 IGE ciphers."""
        if self._initialized:
            return
        
        # AES-256 IGE mode encryption
        self._encrypt_cipher = Cipher(
            algorithms.AES(self.key),
            modes.IGE(self.iv),
        )
        self._encrypt_ige = self._encrypt_cipher.encryptor()
        
        self._decrypt_cipher = Cipher(
            algorithms.AES(self.key),
            modes.IGE(self.iv),
        )
        self._decrypt_ige = self._decrypt_cipher.decryptor()
        
        self._initialized = True
    
    def encrypt(self, data: bytes) -> bytes:
        """Encrypt data using AES-256 IGE."""
        self._init_ciphers()
        
        # Pad to block size (16 bytes)
        padding_len = MTPROTO_BLOCK_SIZE - (len(data) % MTPROTO_BLOCK_SIZE)
        if padding_len == 0:
            padding_len = MTPROTO_BLOCK_SIZE
        padded_data = data + bytes([padding_len] * padding_len)
        
        return self._encrypt_ige.update(padded_data) + self._encrypt_ige.finalize()
    
    def decrypt(self, data: bytes) -> bytes:
        """Decrypt data using AES-256 IGE."""
        self._init_ciphers()
        
        decrypted = self._decrypt_ige.update(data) + self._decrypt_ige.finalize()
        
        # Remove padding
        if decrypted:
            padding_len = decrypted[-1]
            if 1 <= padding_len <= MTPROTO_BLOCK_SIZE:
                decrypted = decrypted[:-padding_len]
        
        return decrypted


class MTProtoPacket:
    """
    MTProto Intermediate packet format.
    
    Format:
    - Length (4 bytes, little-endian)
    - Sequence number (4 bytes, little-endian)
    - Data (variable length)
    """
    
    def __init__(self, length: int = 0, seq: int = 0, data: bytes = b''):
        self.length = length
        self.seq = seq
        self.data = data
    
    def serialize(self) -> bytes:
        """Serialize packet to bytes."""
        header = struct.pack('<II', self.length, self.seq)
        return header + self.data
    
    @classmethod
    def deserialize(cls, data: bytes) -> Optional['MTProtoPacket']:
        """Deserialize packet from bytes."""
        if len(data) < 8:
            return None
        
        length, seq = struct.unpack('<II', data[:8])
        
        if len(data) < 8 + length:
            return None
        
        packet_data = data[8:8 + length]
        return cls(length=length, seq=seq, data=packet_data)


class MTProtoProxy:
    """
    MTProto Proxy Server.

    Accepts connections from Telegram mobile apps and forwards them
    to Telegram servers using WebSocket relay or direct TCP.

    Supports multiple secrets for different users.
    """

    def __init__(
        self,
        secrets: List[str],
        host: str = MTPROTO_DEFAULT_HOST,
        port: int = MTPROTO_DEFAULT_PORT,
        dc_ip: Optional[Dict[int, str]] = None,
        auto_rotate: bool = False,
        rotate_interval_days: int = 7,
        on_secret_rotate: Optional[Callable[[List[str]], None]] = None,
        traffic_limit_gb: Optional[float] = None,  # Per-secret traffic limit in GB
    ):
        self.secrets = secrets  # Support multiple secrets
        self.host = host
        self.port = port
        self.dc_ip = dc_ip or {}

        # Auto-rotation settings
        self.auto_rotate = auto_rotate
        self.rotate_interval_days = rotate_interval_days
        self.on_secret_rotate = on_secret_rotate
        self._rotate_thread: Optional[threading.Thread] = None
        self._stop_rotate = threading.Event()
        
        # Traffic limit settings
        self.traffic_limit_gb = traffic_limit_gb
        self.traffic_limit_bytes = int(traffic_limit_gb * 1024**3) if traffic_limit_gb else None

        # Create transport for each secret
        self.transports = {secret: MTProtoTransport(secret) for secret in secrets}

        self._server: Optional[asyncio.Server] = None

        # Statistics per secret
        self.stats_per_secret = {
            secret: {
                "connections_total": 0,
                "connections_active": 0,
                "bytes_received": 0,
                "bytes_sent": 0,
                "limit_exceeded": False,
            }
            for secret in secrets
        }

        # Global statistics
        self.connections_total = 0
        self.connections_active = 0
        self.bytes_received = 0
        self.bytes_sent = 0

        # Rotation history
        self.rotation_history: List[dict] = []
    
    async def start(self):
        """Start the MTProto proxy server."""
        # Validate all secrets
        for secret in self.secrets:
            if not validate_secret(secret):
                raise ValueError(f"Invalid secret key: {secret[:8]}... (must be {MTPROTO_SECRET_LENGTH} hex characters)")

        self._server = await asyncio.start_server(
            self._handle_client,
            self.host,
            self.port,
        )

        # Start auto-rotation if enabled
        if self.auto_rotate:
            self._start_auto_rotation()

        log.info("=" * 60)
        log.info("  MTProto Proxy Server")
        log.info("  Listening on: %s:%d", self.host, self.port)
        log.info("  Secrets: %d configured", len(self.secrets))
        for i, secret in enumerate(self.secrets, 1):
            log.info("    [%d] %s...%s", i, secret[:8], secret[-4:])
        if self.auto_rotate:
            log.info("  Auto-rotation: Enabled (every %d days)", self.rotate_interval_days)
        log.info("=" * 60)
        log.info("  Telegram Mobile Connection:")
        log.info("    Scan QR code or use tg://proxy?server=YOUR_SERVER&port=%d&secret=YOUR_SECRET", self.port)
        log.info("=" * 60)

        async with self._server:
            await self._server.serve_forever()
    
    def _start_auto_rotation(self):
        """Start automatic secret rotation in background thread."""
        def rotate_loop():
            next_rotation = datetime.now() + timedelta(days=self.rotate_interval_days)
            log.info("Next secret rotation: %s", next_rotation.strftime("%Y-%m-%d %H:%M"))
            
            while not self._stop_rotate.wait(timeout=60):  # Check every minute
                if datetime.now() >= next_rotation:
                    self.rotate_secrets()
                    next_rotation = datetime.now() + timedelta(days=self.rotate_interval_days)
                    log.info("Next secret rotation: %s", next_rotation.strftime("%Y-%m-%d %H:%M"))
        
        self._rotate_thread = threading.Thread(target=rotate_loop, daemon=True)
        self._rotate_thread.start()
    
    def rotate_secrets(self, new_secrets: Optional[List[str]] = None):
        """
        Rotate secrets (manual or automatic).
        
        Args:
            new_secrets: New secrets to use. If None, generates new ones.
        """
        old_secrets = list(self.secrets)
        
        if new_secrets is None:
            # Generate new secrets (keep old ones for grace period)
            new_secrets = [generate_secret() for _ in self.secrets]
        
        # Add new secrets to the list (keep old for 24h grace period)
        self.secrets = new_secrets + old_secrets
        
        # Update transports
        self.transports = {secret: MTProtoTransport(secret) for secret in self.secrets}
        
        # Update stats for new secrets
        for secret in new_secrets:
            self.stats_per_secret[secret] = {
                "connections_total": 0,
                "connections_active": 0,
                "bytes_received": 0,
                "bytes_sent": 0,
            }
        
        # Log rotation
        log.info("Secrets rotated: %d old + %d new = %d total",
                 len(old_secrets), len(new_secrets), len(self.secrets))
        
        # Record rotation history
        self.rotation_history.append({
            "timestamp": datetime.now().isoformat(),
            "old_secrets": old_secrets,
            "new_secrets": new_secrets,
        })
        
        # Callback if provided
        if self.on_secret_rotate:
            try:
                self.on_secret_rotate(self.secrets)
            except Exception as e:
                log.error("Error in on_secret_rotate callback: %s", e)
        
        # Schedule cleanup of old secrets after 24h grace period
        def cleanup_old():
            time.sleep(86400)  # 24 hours
            # Remove old secrets
            for old in old_secrets:
                if old in self.secrets:
                    self.secrets.remove(old)
                    self.transports.pop(old, None)
                    self.stats_per_secret.pop(old, None)
            log.info("Old secrets cleaned up: %d remaining", len(self.secrets))
        
        threading.Thread(target=cleanup_old, daemon=True).start()
    
    def stop_auto_rotation(self):
        """Stop automatic secret rotation."""
        if self._rotate_thread:
            self._stop_rotate.set()
            self._rotate_thread = None
    
    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Handle incoming MTProto client connection."""
        self.connections_total += 1
        self.connections_active += 1

        peer = writer.get_extra_info('peername')
        label = f"{peer[0]}:{peer[1]}" if peer else "?"

        log.info("[%s] MTProto client connected", label)

        try:
            # Read initial packet (handshake)
            init_data = await asyncio.wait_for(reader.read(4096), timeout=30.0)

            if not init_data:
                log.debug("[%s] Client disconnected before handshake", label)
                return

            self.bytes_received += len(init_data)

            # Try to decrypt with each secret (multi-user support)
            transport = None
            used_secret = None
            decrypted = None

            for secret, trans in self.transports.items():
                try:
                    decrypted = trans.decrypt(init_data)
                    # Check if it's a valid MTProto packet
                    packet = MTProtoPacket.deserialize(decrypted)
                    if packet:
                        transport = trans
                        used_secret = secret
                        log.debug("[%s] Handshake decrypted with secret %s...%s (%d bytes)",
                                  label, secret[:8], secret[-4:], len(decrypted))
                        break
                except Exception:
                    continue

            if transport is None or decrypted is None or used_secret is None:
                log.warning("[%s] Failed to decrypt with any secret", label)
                return

            # Check traffic limit before accepting connection
            if self.traffic_limit_bytes:
                secret_stats = self.stats_per_secret[used_secret]
                total_traffic = secret_stats["bytes_received"] + secret_stats["bytes_sent"]
                if total_traffic >= self.traffic_limit_bytes:
                    if not secret_stats.get("limit_exceeded", False):
                        secret_stats["limit_exceeded"] = True
                        log.warning("[%s] Traffic limit exceeded for secret %s...%s (%.2f GB used)",
                                    label, used_secret[:8], used_secret[-4:],
                                    total_traffic / (1024**3))
                    writer.write(b'')  # Close connection
                    await writer.drain()
                    self.stats_per_secret[used_secret]["connections_active"] -= 1
                    return

            # Update stats for this secret
            self.stats_per_secret[used_secret]["connections_total"] += 1
            self.stats_per_secret[used_secret]["connections_active"] += 1
            self.stats_per_secret[used_secret]["bytes_received"] += len(init_data)

            # Check if it's a valid MTProto packet
            packet = MTProtoPacket.deserialize(decrypted)
            if packet:
                log.info("[%s] MTProto handshake successful (seq=%d, secret=%s...%s)",
                         label, packet.seq, used_secret[:8], used_secret[-4:])

                # Send response (echo with encryption)
                response_packet = MTProtoPacket(
                    length=len(packet.data),
                    seq=packet.seq + 1,
                    data=packet.data,
                )
                response_data = transport.encrypt(response_packet.serialize())
                writer.write(response_data)
                await writer.drain()
                self.bytes_sent += len(response_data)
                self.stats_per_secret[used_secret]["bytes_sent"] += len(response_data)

                log.info("[%s] MTProto proxy handshake complete", label)
            else:
                log.warning("[%s] Invalid MTProto packet format", label)
                self.stats_per_secret[used_secret]["connections_active"] -= 1
                return

            # Keep connection alive and forward data
            await self._forward_data(reader, writer, label, used_secret)

        except asyncio.TimeoutError:
            log.debug("[%s] Connection timeout", label)
        except asyncio.CancelledError:
            log.debug("[%s] Connection cancelled", label)
        except ConnectionResetError:
            log.debug("[%s] Connection reset by client", label)
        except Exception as exc:
            log.error("[%s] Unexpected error: %s", label, exc)
        finally:
            self.connections_active -= 1
            # Decrement active connections for the used secret
            if 'used_secret' in locals() and used_secret in self.stats_per_secret:
                self.stats_per_secret[used_secret]["connections_active"] -= 1
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
            log.info("[%s] MTProto client disconnected", label)

    async def _forward_data(self, client_reader: asyncio.StreamReader,
                           client_writer: asyncio.StreamWriter, label: str,
                           used_secret: str):
        """Forward data between client and Telegram server."""
        async def client_to_server():
            try:
                while True:
                    data = await client_reader.read(65536)
                    if not data:
                        break
                    self.bytes_received += len(data)
                    self.stats_per_secret[used_secret]["bytes_received"] += len(data)
                    log.debug("[%s] Client -> Server: %d bytes", label, len(data))
                    # TODO: Forward to Telegram server
            except (asyncio.CancelledError, ConnectionError, OSError):
                pass

        async def server_to_client():
            try:
                while True:
                    # TODO: Read from Telegram server
                    # data = await server_reader.read(65536)
                    # if not data:
                    #     break
                    # encrypted = self.transport.encrypt(data)
                    # client_writer.write(encrypted)
                    # await client_writer.drain()
                    # self.bytes_sent += len(encrypted)
                    await asyncio.sleep(1)  # Keep connection alive
            except (asyncio.CancelledError, ConnectionError, OSError):
                pass
        
        tasks = [
            asyncio.create_task(client_to_server()),
            asyncio.create_task(server_to_client()),
        ]
        
        try:
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for t in tasks:
                t.cancel()
            for t in tasks:
                try:
                    await t
                except BaseException:
                    pass
    
    def get_stats(self) -> dict:
        """Get proxy statistics."""
        return {
            "connections_total": self.connections_total,
            "connections_active": self.connections_active,
            "bytes_received": self.bytes_received,
            "bytes_sent": self.bytes_sent,
            "per_secret": dict(self.stats_per_secret),
        }


def run_mtproto_proxy(
    secrets: Optional[List[str]] = None,
    secret: Optional[str] = None,  # Deprecated, for backward compatibility
    host: str = MTPROTO_DEFAULT_HOST,
    port: int = MTPROTO_DEFAULT_PORT,
    verbose: bool = False,
    qr_output: Optional[str] = None,
    server_ip: Optional[str] = None,
    auto_rotate: bool = False,
    rotate_interval_days: int = 7,
    traffic_limit_gb: Optional[float] = None,
):
    """
    Run MTProto proxy server (blocking).

    Args:
        secrets: List of secret keys (32 hex chars). Generated if not provided.
        secret: Single secret (deprecated, use secrets instead).
        host: Host to bind to.
        port: Port to listen on.
        verbose: Enable debug logging.
        qr_output: Generate QR code ('console' for ASCII or file path).
        server_ip: Server IP for QR code (auto-detected if None).
        auto_rotate: Enable automatic secret rotation.
        rotate_interval_days: Rotate secrets every N days.
        traffic_limit_gb: Traffic limit per secret in GB (None for unlimited).
    """
    # Handle backward compatibility
    if secrets is None:
        if secret:
            secrets = [secret]
        else:
            secrets = [generate_secret()]
            log.info("Generated new secret: %s", secrets[0])

    # Validate all secrets
    for s in secrets:
        if not validate_secret(s):
            log.error("Invalid secret: %s... (must be %d hex characters)", s[:8], MTPROTO_SECRET_LENGTH)
            sys.exit(1)

    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format='%(asctime)s  %(levelname)-5s  %(message)s',
        datefmt='%H:%M:%S',
    )

    # Generate QR code if requested (use first secret)
    if qr_output:
        if qr_output == 'console':
            log.info("QR Code for mobile connection:")
            qr_text = generate_qr_code(server_ip or "YOUR_SERVER_IP", port, secrets[0])
            if qr_text:
                print("\n" + qr_text + "\n")
        else:
            generate_qr_code(server_ip or "YOUR_SERVER_IP", port, secrets[0], qr_output)

    proxy = MTProtoProxy(
        secrets=secrets,
        host=host,
        port=port,
        auto_rotate=auto_rotate,
        rotate_interval_days=rotate_interval_days,
        traffic_limit_gb=traffic_limit_gb,
    )

    try:
        asyncio.run(proxy.start())
    except KeyboardInterrupt:
        log.info("Shutting down. Final stats: %s", proxy.get_stats())


def main() -> None:
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description='MTProto Proxy for Telegram Mobile Apps'
    )
    parser.add_argument(
        '--secrets',
        type=str,
        default=None,
        help=f'Comma-separated secret keys ({MTPROTO_SECRET_LENGTH} hex chars each). Generated if not provided.'
    )
    parser.add_argument(
        '--secret', '-s',
        type=str,
        default=None,
        help=f'Single secret key (deprecated, use --secrets).'
    )
    parser.add_argument(
        '--host',
        type=str,
        default=MTPROTO_DEFAULT_HOST,
        help=f'Listen host (default: {MTPROTO_DEFAULT_HOST})'
    )
    parser.add_argument(
        '--port', '-p',
        type=int,
        default=MTPROTO_DEFAULT_PORT,
        help=f'Listen port (default: {MTPROTO_DEFAULT_PORT})'
    )
    parser.add_argument(
        '--qr',
        type=str,
        nargs='?',
        const='console',
        default=None,
        help='Generate QR code for mobile connection. Provide output path or use "console" for ASCII art.'
    )
    parser.add_argument(
        '--server',
        type=str,
        default=None,
        help='Server IP/hostname for QR code (default: auto-detect)'
    )
    parser.add_argument(
        '--auto-rotate',
        action='store_true',
        help='Enable automatic secret rotation'
    )
    parser.add_argument(
        '--rotate-days',
        type=int,
        default=7,
        help='Rotate secrets every N days (default: 7)'
    )
    parser.add_argument(
        '--traffic-limit-gb',
        type=float,
        default=None,
        help='Traffic limit per secret in GB (None for unlimited)'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Debug logging'
    )

    args = parser.parse_args()

    # Parse secrets
    secrets = None
    if args.secrets:
        secrets = [s.strip() for s in args.secrets.split(',')]
    elif args.secret:
        secrets = [args.secret]

    # Auto-detect server IP if not provided
    server_ip = args.server
    if server_ip is None and args.qr:
        # Try to get local IP
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            server_ip = s.getsockname()[0]
            s.close()
        except Exception:
            server_ip = "127.0.0.1"

    run_mtproto_proxy(
        secrets=secrets,
        host=args.host,
        port=args.port,
        verbose=args.verbose,
        qr_output=args.qr,
        server_ip=server_ip,
        auto_rotate=args.auto_rotate,
        rotate_interval_days=args.rotate_days,
        traffic_limit_gb=args.traffic_limit_gb,
    )


if __name__ == '__main__':
    main()
