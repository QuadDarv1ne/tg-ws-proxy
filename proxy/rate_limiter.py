"""
Rate Limiting Module for TG WS Proxy.

Provides connection rate limiting to prevent abuse and overload:
- Per-IP rate limiting
- Global connection limits
- Exponential backoff for violations
- Sliding window rate limiting
- Allow-list support for trusted IPs

Author: Dupley Maxim Igorevich
© 2026 Dupley Maxim Igorevich. All rights reserved.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum, auto

log = logging.getLogger('tg-ws-ratelimit')


class RateLimitAction(Enum):
    ALLOW = auto()
    DELAY = auto()
    REJECT = auto()
    BAN = auto()


@dataclass
class RateLimitConfig:
    requests_per_second: float = 10.0
    requests_per_minute: int = 100
    requests_per_hour: int = 1000
    max_concurrent_connections: int = 500
    max_connections_per_ip: int = 10
    ban_threshold: int = 5
    ban_duration_seconds: float = 300.0
    initial_delay_ms: int = 100
    max_delay_ms: int = 5000
    backoff_multiplier: float = 2.0
    # Trusted IPs that are not subject to rate limits
    allow_list: set[str] = field(default_factory=lambda: {"127.0.0.1", "::1"})


@dataclass
class IPStats:
    # Use deque for efficient O(1) removal from the left
    requests: deque[float] = field(default_factory=deque)
    violations: int = 0
    last_violation: float = 0.0
    ban_until: float = 0.0
    total_requests: int = 0
    blocked_requests: int = 0


class RateLimiter:
    """Rate limiter with sliding window and exponential backoff."""

    def __init__(self, config: RateLimitConfig | None = None):
        self.config = config or RateLimitConfig()
        self._ip_stats: dict[str, IPStats] = defaultdict(IPStats)
        self._global_requests: deque[float] = deque()
        self._active_connections: dict[str, int] = defaultdict(int)
        self._total_active = 0
        self._cleanup_task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        log.info("Rate limiter started (Allow-list size: %d)", len(self.config.allow_list))

    async def stop(self) -> None:
        self._running = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        log.info("Rate limiter stopped")

    async def _cleanup_loop(self) -> None:
        while self._running:
            try:
                # Cleanup every 5 minutes to reduce CPU usage
                await asyncio.sleep(300)
                self._cleanup_old_data()
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error("Rate limiter cleanup error: %s", e)

    def _cleanup_old_data(self) -> None:
        now = time.time()
        hour_ago = now - 3600

        ips_to_remove = []
        for ip, stats in self._ip_stats.items():
            # Efficiently remove old requests
            while stats.requests and stats.requests[0] < hour_ago:
                stats.requests.popleft()

            if stats.ban_until > 0 and now > stats.ban_until:
                stats.ban_until = 0.0
                stats.violations = 0
                log.info("IP %s unbanned after timeout", ip)

            if not stats.requests and stats.ban_until == 0 and self._active_connections[ip] == 0:
                ips_to_remove.append(ip)

        for ip in ips_to_remove:
            del self._ip_stats[ip]

        while self._global_requests and self._global_requests[0] < hour_ago:
            self._global_requests.popleft()

    def check_rate_limit(self, ip: str) -> tuple[RateLimitAction, float]:
        if ip in self.config.allow_list:
            return RateLimitAction.ALLOW, 0.0

        now = time.time()
        stats = self._ip_stats[ip]
        stats.total_requests += 1

        if stats.ban_until > now:
            stats.blocked_requests += 1
            return RateLimitAction.BAN, stats.ban_until - now

        global_action = self._check_global_limit()
        if global_action != RateLimitAction.ALLOW:
            stats.blocked_requests += 1
            return global_action, 0

        self._clean_old_requests(stats)

        # 1. Per Second Limit
        recent_second = sum(1 for t in stats.requests if t > now - 1)
        if recent_second >= self.config.requests_per_second:
            return self._handle_violation(ip, stats, "requests/second")

        # 2. Per Minute Limit
        recent_minute = sum(1 for t in stats.requests if t > now - 60)
        if recent_minute >= self.config.requests_per_minute:
            return self._handle_violation(ip, stats, "requests/minute")

        # 3. Per Hour Limit
        if len(stats.requests) >= self.config.requests_per_hour:
            return self._handle_violation(ip, stats, "requests/hour")

        # 4. Max Concurrent Connections per IP
        if self._active_connections[ip] >= self.config.max_connections_per_ip:
            stats.blocked_requests += 1
            return RateLimitAction.REJECT, 0

        stats.requests.append(now)
        return RateLimitAction.ALLOW, 0

    def _check_global_limit(self) -> RateLimitAction:
        now = time.time()
        # Clean global requests older than 1 minute
        while self._global_requests and self._global_requests[0] < now - 60:
            self._global_requests.popleft()

        if len(self._global_requests) >= self.config.requests_per_minute * 10:
            log.warning("Global rate limit exceeded: %d requests/minute", len(self._global_requests))
            return RateLimitAction.DELAY

        if self._total_active >= self.config.max_concurrent_connections:
            log.warning("Max concurrent connections reached: %d", self._total_active)
            return RateLimitAction.REJECT

        return RateLimitAction.ALLOW

    def _clean_old_requests(self, stats: IPStats) -> None:
        hour_ago = time.time() - 3600
        while stats.requests and stats.requests[0] < hour_ago:
            stats.requests.popleft()

    def _handle_violation(self, ip: str, stats: IPStats, limit_type: str) -> tuple[RateLimitAction, float]:
        stats.violations += 1
        stats.last_violation = time.time()
        stats.blocked_requests += 1

        delay_ms = min(
            self.config.initial_delay_ms * (self.config.backoff_multiplier ** (stats.violations - 1)),
            self.config.max_delay_ms
        )
        delay_sec = delay_ms / 1000.0

        if stats.violations >= self.config.ban_threshold:
            stats.ban_until = time.time() + self.config.ban_duration_seconds
            log.warning("IP %s banned for %.0f seconds (violations: %d, limit: %s)",
                        ip, self.config.ban_duration_seconds, stats.violations, limit_type)
            return RateLimitAction.BAN, self.config.ban_duration_seconds

        log.debug("IP %s rate limited: %s (violation %d, delay: %.1fs)",
                  ip, limit_type, stats.violations, delay_sec)
        return RateLimitAction.DELAY, delay_sec

    def add_connection(self, ip: str) -> None:
        self._active_connections[ip] += 1
        self._total_active += 1
        self._global_requests.append(time.time())

    def remove_connection(self, ip: str) -> None:
        if self._active_connections[ip] > 0:
            self._active_connections[ip] -= 1
            self._total_active -= 1

    def get_ip_stats(self, ip: str) -> dict:
        stats = self._ip_stats.get(ip, IPStats())
        now = time.time()
        return {
            "total_requests": stats.total_requests,
            "blocked_requests": stats.blocked_requests,
            "violations": stats.violations,
            "active_connections": self._active_connections[ip],
            "is_banned": stats.ban_until > now,
            "ban_remaining": max(0, stats.ban_until - now),
            "requests_last_minute": sum(1 for t in stats.requests if t > now - 60)
        }

    def get_global_stats(self) -> dict:
        now = time.time()
        return {
            "total_active_connections": self._total_active,
            "unique_ips": len(self._ip_stats),
            "requests_last_minute": len([t for t in self._global_requests if t > now - 60]),
            "banned_ips": sum(1 for s in self._ip_stats.values() if s.ban_until > now),
            "total_violations": sum(s.violations for s in self._ip_stats.values())
        }

    def reset_ip(self, ip: str) -> None:
        if ip in self._ip_stats:
            stats = self._ip_stats[ip]
            stats.violations = 0
            stats.ban_until = 0.0
            stats.requests.clear()

    def ban_ip(self, ip: str, duration: float | None = None) -> None:
        duration = duration or self.config.ban_duration_seconds
        self._ip_stats[ip].ban_until = time.time() + duration

    def unban_ip(self, ip: str) -> None:
        if ip in self._ip_stats:
            self._ip_stats[ip].ban_until = 0.0
            self._ip_stats[ip].violations = 0


_rate_limiter: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


def check_rate_limit(ip: str) -> tuple[RateLimitAction, float]:
    return get_rate_limiter().check_rate_limit(ip)


def add_connection(ip: str) -> None:
    get_rate_limiter().add_connection(ip)


def remove_connection(ip: str) -> None:
    get_rate_limiter().remove_connection(ip)


__all__ = ['RateLimitConfig', 'RateLimiter', 'RateLimitAction', 'get_rate_limiter', 'check_rate_limit', 'add_connection', 'remove_connection']
