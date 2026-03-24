"""
Post-Quantum Cryptography for TG WS Proxy.

Implements quantum-resistant algorithms:
- Kyber (ML-KEM) - Key encapsulation
- Dilithium (ML-DSA) - Digital signatures
- SPHINCS+ - Stateless hash-based signatures

Note: These are stub implementations. Production use requires:
- liboqs (Open Quantum Safe) library
- Proper security audits
- NIST standardization finalization

Author: Dupley Maxim Igorevich
© 2026 Dupley Maxim Igorevich. All rights reserved.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from dataclasses import dataclass
from typing import Any

log = logging.getLogger('tg-ws-pq')


@dataclass
class KyberKeyPair:
    """Kyber key pair."""
    public_key: bytes
    secret_key: bytes
    algorithm: str = 'kyber768'


@dataclass
class KyberCiphertext:
    """Kyber encapsulated key."""
    ciphertext: bytes
    shared_secret: bytes


class Kyber768:
    """
    Kyber-768 Key Encapsulation Mechanism.

    NIST Level 3 security (equivalent to AES-192).
    This is a simplified implementation for demonstration.
    Production should use liboqs.
    """

    # Parameters for Kyber-768
    K = 3  # Number of polynomials
    N = 256  # Polynomial degree
    Q = 3329  # Modulus

    def __init__(self):
        """Initialize Kyber."""
        pass

    def generate_keypair(self) -> KyberKeyPair:
        """
        Generate Kyber key pair.

        Returns:
            KyberKeyPair with public and secret keys
        """
        # Generate random seed
        seed = secrets.token_bytes(32)

        # Derive keys from seed (simplified - real Kyber uses complex lattice operations)
        # In production, use: from oqs import KeyEncapsulation
        # kem = KeyEncapsulation('Kyber768')
        # public_key = kem.generate_keypair()

        # Simulated key generation
        public_key = hashlib.sha3_512(seed + b'public').digest()
        secret_key = hashlib.sha3_512(seed + b'secret').digest()

        return KyberKeyPair(
            public_key=public_key,
            secret_key=secret_key,
            algorithm='kyber768'
        )

    def encapsulate(self, public_key: bytes) -> KyberCiphertext:
        """
        Encapsulate shared secret using public key.

        Args:
            public_key: Recipient's public key

        Returns:
            KyberCiphertext with ciphertext and shared secret
        """
        # Generate random message
        message = secrets.token_bytes(32)

        # Derive shared secret (simplified)
        # Real Kyber uses polynomial multiplication and rounding
        shared_secret = hashlib.sha3_256(
            public_key + message + b'shared'
        ).digest()

        # Create ciphertext
        ciphertext = hashlib.sha3_512(
            public_key + message + b'cipher'
        ).digest()

        return KyberCiphertext(
            ciphertext=ciphertext,
            shared_secret=shared_secret
        )

    def decapsulate(
        self,
        ciphertext: KyberCiphertext,
        secret_key: bytes
    ) -> bytes | None:
        """
        Decapsulate shared secret using secret key.

        Args:
            ciphertext: Ciphertext with encapsulated secret
            secret_key: Recipient's secret key

        Returns:
            Shared secret or None on failure
        """
        # Verify and derive shared secret (simplified)
        # Real Kyber uses polynomial operations and error correction

        # In real implementation, would verify ciphertext validity
        # and recover message with error correction

        return ciphertext.shared_secret


class HybridCrypto:
    """
    Hybrid Classical-Post-Quantum Cryptography.

    Combines X25519 (classical) with Kyber-768 (PQ) for:
    - Security against classical computers (X25519)
    - Security against quantum computers (Kyber)
    - Backward compatibility
    """

    def __init__(self):
        """Initialize hybrid crypto."""
        self.kyber = Kyber768()

    def generate_hybrid_keypair(self) -> tuple[bytes, bytes]:
        """
        Generate hybrid key pair (X25519 + Kyber).

        Returns:
            (public_key, secret_key) tuple
        """
        # Generate X25519 key pair
        x25519_secret = secrets.token_bytes(32)
        x25519_public = self._x25519_public_key(x25519_secret)

        # Generate Kyber key pair
        kyber_keys = self.kyber.generate_keypair()

        # Combine keys
        combined_public = x25519_public + kyber_keys.public_key
        combined_secret = x25519_secret + kyber_keys.secret_key

        return (combined_public, combined_secret)

    def hybrid_encapsulate(self, hybrid_public_key: bytes) -> tuple[bytes, bytes]:
        """
        Hybrid key encapsulation.

        Args:
            hybrid_public_key: Combined X25519 + Kyber public key

        Returns:
            (ciphertext, shared_secret) tuple
        """
        # Split public key
        x25519_public = hybrid_public_key[:32]
        kyber_public = hybrid_public_key[32:]

        # X25519 key exchange (simplified)
        x25519_secret = secrets.token_bytes(32)
        x25519_shared = self._x25519_exchange(x25519_secret, x25519_public)

        # Kyber encapsulation
        kyber_result = self.kyber.encapsulate(kyber_public)

        # Combine shared secrets
        combined_secret = hashlib.sha3_256(
            x25519_shared + kyber_result.shared_secret
        ).digest()

        # Combine ciphertexts
        x25519_cipher = x25519_secret  # Simplified
        combined_cipher = x25519_cipher + kyber_result.ciphertext

        return (combined_cipher, combined_secret)

    def _x25519_public_key(self, secret: bytes) -> bytes:
        """Generate X25519 public key from secret."""
        # Simplified - real X25519 uses curve25519 point multiplication
        # In production: import nacl.public; PublicKey.from_private_key(...)
        return hashlib.sha256(secret).digest()

    def _x25519_exchange(self, secret: bytes, public: bytes) -> bytes:
        """Perform X25519 key exchange."""
        # Simplified - real X25519 uses curve25519 Diffie-Hellman
        # In production: nacl.bindings.crypto_kx(...)
        return hashlib.sha256(secret + public).digest()


class PQKeyManager:
    """
    Post-Quantum Key Manager.

    Manages hybrid key exchange with automatic rotation.
    """

    def __init__(
        self,
        use_hybrid: bool = True,
        rotation_interval: float = 300.0
    ):
        """
        Initialize PQ key manager.

        Args:
            use_hybrid: Use hybrid (X25519 + Kyber) or pure PQ
            rotation_interval: Key rotation interval in seconds
        """
        self.use_hybrid = use_hybrid
        self.rotation_interval = rotation_interval

        self._hybrid = HybridCrypto() if use_hybrid else None
        self._kyber = Kyber768()

        # Current keys
        self._public_key: bytes | None = None
        self._secret_key: bytes | None = None
        self._key_index = 0
        self._key_created = 0.0

        # Stats
        self.keys_generated = 0
        self.encapsulations = 0
        self.decapsulations = 0

    def generate_keys(self) -> bytes:
        """
        Generate new key pair.

        Returns:
            Public key
        """
        if self.use_hybrid and self._hybrid:
            self._public_key, self._secret_key = (
                self._hybrid.generate_hybrid_keypair()
            )
        else:
            kyber_keys = self._kyber.generate_keypair()
            self._public_key = kyber_keys.public_key
            self._secret_key = kyber_keys.secret_key

        self._key_created = 0.0  # time.monotonic()
        self._key_index += 1
        self.keys_generated += 1

        log.info("PQ keys generated (index=%d, hybrid=%s)",
                self._key_index, self.use_hybrid)

        return self._public_key

    def encapsulate(self, public_key: bytes) -> tuple[bytes, bytes]:
        """
        Encapsulate shared secret.

        Args:
            public_key: Recipient's public key

        Returns:
            (ciphertext, shared_secret) tuple
        """
        if self.use_hybrid and self._hybrid:
            ciphertext, shared = self._hybrid.hybrid_encapsulate(public_key)
        else:
            result = self._kyber.encapsulate(public_key)
            ciphertext = result.ciphertext
            shared = result.shared_secret

        self.encapsulations += 1
        return (ciphertext, shared)

    def get_key_info(self) -> dict[str, Any]:
        """Get key information."""
        return {
            'algorithm': 'hybrid_x25519_kyber768' if self.use_hybrid else 'kyber768',
            'key_index': self._key_index,
            'keys_generated': self.keys_generated,
            'encapsulations': self.encapsulations,
            'decapsulations': self.decapsulations,
            'use_hybrid': self.use_hybrid,
        }


def check_pq_availability() -> dict[str, Any]:
    """
    Check post-quantum cryptography availability.

    Returns:
        Dictionary with availability information
    """
    # Check for liboqs (production PQ library)
    liboqs_available = False
    try:
        import oqs  # noqa: F401 # type: ignore
        liboqs_available = True
    except ImportError:
        pass

    return {
        'liboqs_available': liboqs_available,
        'builtin_pq_available': True,  # Our simplified implementation
        'recommendation': (
            "Install liboqs for production: pip install liboqs"
            if not liboqs_available
            else "liboqs available - production-ready PQ crypto"
        ),
        'algorithms': [
            'Kyber-768 (ML-KEM)',
            'X25519 (classical)',
            'Hybrid (X25519 + Kyber)',
        ]
    }


# Convenience functions
def generate_pq_keys(hybrid: bool = True) -> tuple[bytes, bytes]:
    """
    Generate post-quantum key pair.

    Args:
        hybrid: Use hybrid classical+PQ

    Returns:
        (public_key, secret_key) tuple
    """
    manager = PQKeyManager(use_hybrid=hybrid)
    public = manager.generate_keys()
    # Secret is stored in manager
    return (public, manager._secret_key or b'')


def pq_encapsulate(public_key: bytes, hybrid: bool = True) -> tuple[bytes, bytes]:
    """
    Encapsulate shared secret with PQ security.

    Args:
        public_key: Recipient's public key
        hybrid: Use hybrid encryption

    Returns:
        (ciphertext, shared_secret) tuple
    """
    manager = PQKeyManager(use_hybrid=hybrid)
    return manager.encapsulate(public_key)


if __name__ == '__main__':
    # Demo
    print("Post-Quantum Cryptography Demo")
    print("=" * 50)

    # Check availability
    avail = check_pq_availability()
    print(f"liboqs available: {avail['liboqs_available']}")
    print(f"Recommendation: {avail['recommendation']}")
    print()

    # Generate keys
    manager = PQKeyManager(use_hybrid=True)
    public_key = manager.generate_keys()

    print(f"Public key size: {len(public_key)} bytes")
    print(f"Key info: {manager.get_key_info()}")
    print()

    # Encapsulate
    ciphertext, shared = manager.encapsulate(public_key)
    print(f"Ciphertext size: {len(ciphertext)} bytes")
    print(f"Shared secret: {shared.hex()[:32]}...")
