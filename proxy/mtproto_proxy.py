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
from typing import Dict, List, Optional, Tuple
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


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
    """
    
    def __init__(
        self,
        secret: str,
        host: str = MTPROTO_DEFAULT_HOST,
        port: int = MTPROTO_DEFAULT_PORT,
        dc_ip: Optional[Dict[int, str]] = None,
    ):
        self.secret = secret
        self.host = host
        self.port = port
        self.dc_ip = dc_ip or {}
        
        self.transport = MTProtoTransport(secret)
        self._server: Optional[asyncio.Server] = None
        
        # Statistics
        self.connections_total = 0
        self.connections_active = 0
        self.bytes_received = 0
        self.bytes_sent = 0
    
    async def start(self):
        """Start the MTProto proxy server."""
        if not validate_secret(self.secret):
            raise ValueError(f"Invalid secret key: must be {MTPROTO_SECRET_LENGTH} hex characters")
        
        self._server = await asyncio.start_server(
            self._handle_client,
            self.host,
            self.port,
        )
        
        log.info("=" * 60)
        log.info("  MTProto Proxy Server")
        log.info("  Listening on: %s:%d", self.host, self.port)
        log.info("  Secret: %s", self.secret[:8] + "..." + self.secret[-4:])
        log.info("=" * 60)
        log.info("  Telegram Mobile Connection URL:")
        log.info("  tg://proxy?server=YOUR_SERVER&port=%d&secret=%s", 
                 self.port, self.secret)
        log.info("=" * 60)
        
        async with self._server:
            await self._server.serve_forever()
    
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
            
            # Try to decrypt and process the packet
            try:
                decrypted = self.transport.decrypt(init_data)
                log.debug("[%s] Handshake decrypted (%d bytes)", label, len(decrypted))
                
                # Check if it's a valid MTProto packet
                packet = MTProtoPacket.deserialize(decrypted)
                if packet:
                    log.info("[%s] MTProto handshake successful (seq=%d)", label, packet.seq)
                    
                    # Send response (echo with encryption for now)
                    response_packet = MTProtoPacket(
                        length=len(packet.data),
                        seq=packet.seq + 1,
                        data=packet.data,
                    )
                    response_data = self.transport.encrypt(response_packet.serialize())
                    writer.write(response_data)
                    await writer.drain()
                    self.bytes_sent += len(response_data)
                    
                    log.info("[%s] MTProto proxy handshake complete", label)
                else:
                    log.warning("[%s] Invalid MTProto packet format", label)
                    
            except Exception as exc:
                log.warning("[%s] Failed to process MTProto packet: %s", label, exc)
                # Connection failed - close
                return
            
            # Keep connection alive and forward data
            await self._forward_data(reader, writer, label)
            
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
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
            log.info("[%s] MTProto client disconnected", label)
    
    async def _forward_data(self, client_reader: asyncio.StreamReader, 
                           client_writer: asyncio.StreamWriter, label: str):
        """Forward data between client and Telegram server."""
        async def client_to_server():
            try:
                while True:
                    data = await client_reader.read(65536)
                    if not data:
                        break
                    self.bytes_received += len(data)
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
        }


def run_mtproto_proxy(
    secret: Optional[str] = None,
    host: str = MTPROTO_DEFAULT_HOST,
    port: int = MTPROTO_DEFAULT_PORT,
    verbose: bool = False,
):
    """
    Run MTProto proxy server (blocking).
    
    Args:
        secret: Secret key (32 hex chars). Generated if not provided.
        host: Host to bind to.
        port: Port to listen on.
        verbose: Enable debug logging.
    """
    if secret is None:
        secret = generate_secret()
        log.info("Generated new secret: %s", secret)
    
    if not validate_secret(secret):
        log.error("Invalid secret: must be %d hex characters", MTPROTO_SECRET_LENGTH)
        sys.exit(1)
    
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format='%(asctime)s  %(levelname)-5s  %(message)s',
        datefmt='%H:%M:%S',
    )
    
    proxy = MTProtoProxy(secret=secret, host=host, port=port)
    
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
        '--secret', '-s',
        type=str,
        default=None,
        help=f'Secret key ({MTPROTO_SECRET_LENGTH} hex chars). Generated if not provided.'
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
        '-v', '--verbose',
        action='store_true',
        help='Debug logging'
    )
    
    args = parser.parse_args()
    run_mtproto_proxy(
        secret=args.secret,
        host=args.host,
        port=args.port,
        verbose=args.verbose,
    )


if __name__ == '__main__':
    main()
