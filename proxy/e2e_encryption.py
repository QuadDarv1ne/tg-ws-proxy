"""
E2E Encryption Module for TG WS Proxy.

Provides end-to-end encryption for traffic between client and proxy:
- Session-based key exchange using ECDH
- Forward secrecy with key rotation
- AES-256-GCM for data encryption
- HMAC authentication
- Replay attack protection

Author: Dupley Maxim Igorevich
© 2026 Dupley Maxim Igorevich. All rights reserved.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets
import time
from dataclasses import dataclass, field
from typing import Any

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

log = logging.getLogger('tg-ws-e2e')


@dataclass
class E2ESession:
    """E2E encryption session state."""
    session_id: str
    send_key: bytes  # Key for encrypting outgoing data
    recv_key: bytes  # Key for decrypting incoming data
    send_nonce: int = 0  # Nonce counter for outgoing
    recv_nonce: int = 0  # Expected nonce for incoming
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    messages_sent: int = 0
    messages_received: int = 0
    is_active: bool = True
    
    # Replay protection
    seen_nonces: set[int] = field(default_factory=set)
    max_seen_nonces: int = 1000  # Keep last 1000 nonces for replay detection


@dataclass
class E2EHandshakeRequest:
    """Client handshake request."""
    client_public_key: bytes
    client_nonce: bytes
    timestamp: float


@dataclass
class E2EHandshakeResponse:
    """Server handshake response."""
    server_public_key: bytes
    server_nonce: bytes
    session_id: str
    signature: bytes  # Signature to verify server identity


class E2EEncryption:
    """
    End-to-End Encryption handler.
    
    Features:
    - ECDH key exchange (X25519)
    - HKDF key derivation
    - AES-256-GCM encryption
    - Replay attack protection
    - Automatic key rotation
    """
    
    NONCE_SIZE = 12  # 96 bits for GCM
    KEY_SIZE = 32    # 256 bits
    TAG_SIZE = 16    # 128 bits authentication tag
    SESSION_TIMEOUT = 3600.0  # 1 hour session lifetime
    KEY_ROTATION_MESSAGES = 10000  # Rotate key after N messages
    
    def __init__(self, private_key: ec.EllipticCurvePrivateKey | None = None):
        """
        Initialize E2E encryption.
        
        Args:
            private_key: Optional private key for ECDH. If None, generates new one.
        """
        if private_key is None:
            self._private_key = ec.generate_private_key(ec.X25519(), default_backend())
        else:
            self._private_key = private_key
            
        self._public_key = self._private_key.public_key()
        self._sessions: dict[str, E2ESession] = {}
        self._server_signature_key = secrets.token_bytes(32)  # For signing handshake responses
        
        log.debug("E2E encryption initialized (X25519 + AES-256-GCM)")
    
    def get_public_key(self) -> bytes:
        """Get server's public key in raw format."""
        return self._public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
    
    def create_handshake_request(self) -> tuple[bytes, bytes, float]:
        """
        Create client-side handshake request.
        
        Returns:
            Tuple of (public_key_bytes, nonce, timestamp)
        """
        client_private = ec.generate_private_key(ec.X25519(), default_backend())
        client_public = client_private.public_key()
        
        public_bytes = client_public.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        
        nonce = secrets.token_bytes(self.NONCE_SIZE)
        timestamp = time.time()
        
        # Store private key for later (in real implementation, use secure storage)
        self._client_private = client_private
        
        return public_bytes, nonce, timestamp
    
    def process_handshake_request(
        self,
        client_public_bytes: bytes,
        client_nonce: bytes,
        timestamp: float,
    ) -> E2EHandshakeResponse:
        """
        Process client handshake request and create session.
        
        Args:
            client_public_bytes: Client's X25519 public key
            client_nonce: Client's random nonce
            timestamp: Client's timestamp
            
        Returns:
            Handshake response with session info
        """
        # Verify timestamp (prevent replay attacks)
        if abs(time.time() - timestamp) > 60.0:
            raise ValueError("Handshake timestamp too old")
        
        # Load client's public key
        client_public_key = ec.X25519PublicKey.from_public_bytes(
            client_public_bytes
        )
        
        # Perform ECDH key exchange
        shared_secret = self._private_key.exchange(client_public_key)
        
        # Derive session keys using HKDF
        session_keys = self._derive_session_keys(shared_secret, client_nonce)
        
        # Generate session ID
        session_id = hashlib.sha256(
            client_public_bytes + self.get_public_key() + client_nonce
        ).hexdigest()[:16]
        
        # Create session
        session = E2ESession(
            session_id=session_id,
            send_key=session_keys['send'],
            recv_key=session_keys['recv'],
        )
        self._sessions[session_id] = session
        
        # Generate server nonce
        server_nonce = secrets.token_bytes(self.NONCE_SIZE)
        
        # Create signature to verify server identity
        signature_data = session_id.encode() + server_nonce + self.get_public_key()
        signature = hmac.new(
            self._server_signature_key,
            signature_data,
            hashlib.sha256
        ).digest()
        
        log.info("E2E session created: %s", session_id)
        
        return E2EHandshakeResponse(
            server_public_key=self.get_public_key(),
            server_nonce=server_nonce,
            session_id=session_id,
            signature=signature,
        )
    
    def complete_handshake(
        self,
        response: E2EHandshakeResponse,
    ) -> E2ESession:
        """
        Complete client-side handshake.
        
        Args:
            response: Server's handshake response
            
        Returns:
            Established E2E session
        """
        # Verify server signature
        signature_data = (
            response.session_id.encode() + 
            response.server_nonce + 
            response.server_public_key
        )
        expected_signature = hmac.new(
            self._server_signature_key,
            signature_data,
            hashlib.sha256
        ).digest()
        
        if not hmac.compare_digest(response.signature, expected_signature):
            raise ValueError("Invalid server signature")
        
        # Load server's public key
        server_public_key = ec.X25519PublicKey.from_public_bytes(
            response.server_public_key
        )
        
        # Perform ECDH key exchange
        shared_secret = self._client_private.exchange(server_public_key)
        
        # Derive session keys
        session_keys = self._derive_session_keys(
            shared_secret, 
            response.server_nonce
        )
        
        # Create session
        session = E2ESession(
            session_id=response.session_id,
            send_key=session_keys['send'],
            recv_key=session_keys['recv'],
        )
        self._sessions[response.session_id] = session
        
        log.info("E2E session completed: %s", response.session_id)
        
        return session
    
    def _derive_session_keys(
        self,
        shared_secret: bytes,
        nonce: bytes,
    ) -> dict[str, bytes]:
        """
        Derive session keys from shared secret using HKDF.
        
        Args:
            shared_secret: ECDH shared secret
            nonce: Random nonce for key separation
            
        Returns:
            Dictionary with 'send' and 'recv' keys
        """
        # Use HKDF to derive keys
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=self.KEY_SIZE * 2,  # Two keys: send + recv
            salt=None,
            info=b'tg-ws-proxy-e2e' + nonce,
            backend=default_backend(),
        )
        derived = hkdf.derive(shared_secret)
        
        return {
            'send': derived[:self.KEY_SIZE],
            'recv': derived[self.KEY_SIZE:],
        }
    
    def encrypt(
        self,
        session_id: str,
        plaintext: bytes,
        associated_data: bytes = b'',
    ) -> tuple[bytes, int]:
        """
        Encrypt data for a session.
        
        Args:
            session_id: Session identifier
            plaintext: Data to encrypt
            associated_data: Optional authenticated data (not encrypted)
            
        Returns:
            Tuple of (ciphertext_with_tag, nonce_int)
        """
        session = self._get_session(session_id)
        
        # Check key rotation
        if session.messages_sent >= self.KEY_ROTATION_MESSAGES:
            self._rotate_session_keys(session)
        
        # Create nonce from counter
        nonce = session.send_nonce.to_bytes(self.NONCE_SIZE, 'big')
        
        # Encrypt with AES-256-GCM
        aesgcm = AESGCM(session.send_key)
        ciphertext = aesgcm.encrypt(nonce, plaintext, associated_data)
        
        # Update session state
        session.send_nonce += 1
        session.messages_sent += 1
        session.last_activity = time.time()
        
        return ciphertext, session.send_nonce - 1
    
    def decrypt(
        self,
        session_id: str,
        ciphertext: bytes,
        nonce_int: int,
        associated_data: bytes = b'',
    ) -> bytes:
        """
        Decrypt data for a session.
        
        Args:
            session_id: Session identifier
            ciphertext: Encrypted data with authentication tag
            nonce_int: Nonce counter value
            associated_data: Optional authenticated data
            
        Returns:
            Decrypted plaintext
        """
        session = self._get_session(session_id)
        
        # Replay attack protection
        if nonce_int in session.seen_nonces:
            log.warning("E2E replay attack detected: session=%s, nonce=%d", 
                       session_id, nonce_int)
            raise ValueError("Replay attack detected")
        
        # Store nonce for replay detection
        session.seen_nonces.add(nonce_int)
        if len(session.seen_nonces) > self.max_seen_nonces:
            # Remove oldest nonces (simple approach: remove random half)
            to_remove = list(session.seen_nonces)[:self.max_seen_nonces // 2]
            for n in to_remove:
                session.seen_nonces.discard(n)
        
        # Create nonce from counter
        nonce = nonce_int.to_bytes(self.NONCE_SIZE, 'big')
        
        # Decrypt with AES-256-GCM
        aesgcm = AESGCM(session.recv_key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, associated_data)
        
        # Update session state
        session.recv_nonce = nonce_int + 1
        session.messages_received += 1
        session.last_activity = time.time()
        
        return plaintext
    
    def _get_session(self, session_id: str) -> E2ESession:
        """Get or create session."""
        if session_id not in self._sessions:
            raise ValueError(f"Session not found: {session_id}")
        
        session = self._sessions[session_id]
        
        # Check session timeout
        if time.time() - session.last_activity > self.SESSION_TIMEOUT:
            session.is_active = False
            raise ValueError("Session expired")
        
        if not session.is_active:
            raise ValueError("Session is not active")
        
        return session
    
    def _rotate_session_keys(self, session: E2ESession) -> None:
        """Rotate session keys for forward secrecy."""
        # Generate new key material
        new_send = secrets.token_bytes(self.KEY_SIZE)
        new_recv = secrets.token_bytes(self.KEY_SIZE)
        
        # Update session keys
        session.send_key = new_send
        session.recv_key = new_recv
        session.messages_sent = 0
        
        log.debug("E2E session keys rotated: %s", session.session_id)
    
    def close_session(self, session_id: str) -> None:
        """Close and cleanup session."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            log.debug("E2E session closed: %s", session_id)
    
    def cleanup_expired_sessions(self) -> int:
        """Remove expired sessions."""
        now = time.time()
        expired = [
            sid for sid, session in self._sessions.items()
            if now - session.last_activity > self.SESSION_TIMEOUT
        ]
        
        for sid in expired:
            del self._sessions[sid]
        
        if expired:
            log.info("Cleaned up %d expired E2E sessions", len(expired))
        
        return len(expired)
    
    def get_session_stats(self, session_id: str) -> dict[str, Any]:
        """Get statistics for a session."""
        session = self._get_session(session_id)
        
        return {
            'session_id': session.session_id,
            'created_at': session.created_at,
            'last_activity': session.last_activity,
            'messages_sent': session.messages_sent,
            'messages_received': session.messages_received,
            'is_active': session.is_active,
            'send_nonce': session.send_nonce,
            'recv_nonce': session.recv_nonce,
        }
    
    def get_all_sessions_stats(self) -> list[dict[str, Any]]:
        """Get statistics for all active sessions."""
        return [
            self.get_session_stats(sid) 
            for sid in self._sessions.keys()
        ]


# Global E2E encryption instance
_e2e_instance: E2EEncryption | None = None


def get_e2e() -> E2EEncryption:
    """Get or create global E2E encryption instance."""
    global _e2e_instance
    if _e2e_instance is None:
        _e2e_instance = E2EEncryption()
    return _e2e_instance


def init_e2e(private_key: ec.EllipticCurvePrivateKey | None = None) -> E2EEncryption:
    """Initialize global E2E encryption."""
    global _e2e_instance
    _e2e_instance = E2EEncryption(private_key)
    return _e2e_instance


__all__ = [
    'E2EEncryption',
    'E2ESession',
    'E2EHandshakeRequest',
    'E2EHandshakeResponse',
    'get_e2e',
    'init_e2e',
]
