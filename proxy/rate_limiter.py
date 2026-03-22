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

from .metrics_history import get_metrics_history

# Optional alerts integration
try:
    from .web_dashboard import get_alerts_manager
    _HAS_ALERTS = True
except ImportError:
    _HAS_ALERTS = False

log = logging.getLogger('tg-ws-ratelimit')


class RateLimitAction(Enum):
    ALLOW = auto()
    DELAY = auto()
    REJECT = auto()
    BAN = auto()


@dataclass
class RateLimitConfig:
    # Basic rate limits
    requests_per_second: float = 10.0
    requests_per_minute: int = 100
    requests_per_hour: int = 1000
    max_concurrent_connections: int = 500
    max_connections_per_ip: int = 10

    # Token bucket configuration (more efficient algorithm)
    token_bucket_enabled: bool = True
    token_bucket_capacity: int = 20  # Max tokens
    token_bucket_refill_rate: float = 10.0  # Tokens per second

    # Ban configuration
    ban_threshold: int = 5
    ban_duration_seconds: float = 300.0
    initial_delay_ms: int = 100
    max_delay_ms: int = 5000
    backoff_multiplier: float = 2.0

    # Trusted IPs that are not subject to rate limits
    allow_list: set[str] = field(default_factory=lambda: {"127.0.0.1", "::1"})

    # DDoS Protection
    ddos_detection_enabled: bool = True
    ddos_threshold_rps: int = 50  # Requests per second from single IP
    ddos_ban_duration: float = 3600.0  # 1 hour ban for DDoS
    ddos_cooldown_seconds: float = 60.0  # Cooldown before re-evaluation

    # Connection Flood Protection
    flood_detection_enabled: bool = True
    flood_threshold_connections: int = 50  # Max connections per second
    flood_ban_duration: float = 600.0  # 10 minutes ban

    # Geographic Rate Limiting (by IP range)
    enable_ip_range_limiting: bool = True
    max_connections_per_subnet: int = 20  # /24 subnet

    # Progressive penalties
    progressive_ban_enabled: bool = True
    max_ban_duration: float = 86400.0  # 24 hours maximum

    # API Rate Limiting (for web dashboard)
    api_rate_limit_enabled: bool = True
    api_requests_per_second: float = 5.0
    api_burst_size: int = 10

    # Connection Scoring (suspicious activity detection)
    connection_scoring_enabled: bool = True
    suspicious_score_threshold: int = 100  # Ban if score exceeds
    score_decay_per_second: float = 1.0  # Score decay rate


@dataclass
class IPStats:
    # Use deque for efficient O(1) removal from the left
    requests: deque[float] = field(default_factory=deque)
    violations: int = 0
    last_violation: float = 0.0
    ban_until: float = 0.0
    total_requests: int = 0
    blocked_requests: int = 0

    # DDoS detection
    requests_per_second: deque[float] = field(default_factory=lambda: deque(maxlen=50))
    last_ddos_check: float = 0.0
    ddos_violations: int = 0

    # Connection tracking
    connections_per_second: deque[float] = field(default_factory=lambda: deque(maxlen=50))
    connection_flood_violations: int = 0

    # Subnet tracking
    subnet: str = ""

    # Progressive penalty tracking
    total_bans: int = 0
    last_ban_duration: float = 0.0

    # Token bucket state
    tokens: float = 20.0  # Start with full bucket
    last_token_refill: float = 0.0

    # Connection scoring (suspicious activity)
    suspicious_score: float = 0.0
    last_score_update: float = 0.0

    # API rate limiting (separate bucket for API)
    api_tokens: float = 10.0
    last_api_token_refill: float = 0.0


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

        # Subnet tracking for geographic limiting
        self._subnet_connections: dict[str, set[str]] = defaultdict(set)

        # Connection rate tracking for flood detection
        self._connection_timestamps: deque[float] = deque(maxlen=1000)

        # Initialize IP stats with subnet info
        for ip in self._ip_stats:
            self._ip_stats[ip].subnet = self._get_subnet(ip)

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

    def _get_subnet(self, ip: str) -> str:
        """Extract /24 subnet from IP address."""
        if ':' in ip:  # IPv6
            return ':'.join(ip.split(':')[:4]) + '::/32'
        # IPv4: get first 3 octets
        parts = ip.split('.')
        if len(parts) == 4:
            return f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"
        return ip

    def _check_ddos(self, ip: str, stats: IPStats) -> tuple[bool, float]:
        """Check for DDoS attack patterns.

        Returns:
            Tuple of (is_ddos_detected, ban_duration)
        """
        if not self.config.ddos_detection_enabled:
            return False, 0.0

        now = time.time()

        # Track requests per second
        stats.requests_per_second.append(now)

        # Calculate RPS
        recent_rps = len([t for t in stats.requests_per_second if t > now - 1.0])
        
        # Record RPS metric
        try:
            metrics = get_metrics_history()
            metrics.record_metric('rate_limiter_rps', recent_rps, {'ip': ip})
        except Exception:
            pass

        if recent_rps >= self.config.ddos_threshold_rps:
            stats.ddos_violations += 1
            log.warning(
                "DDoS detected from %s: %d RPS (threshold: %d)",
                ip, recent_rps, self.config.ddos_threshold_rps
            )
            
            # Record DDoS detection metric
            try:
                metrics = get_metrics_history()
                metrics.record_metric('rate_limiter_ddos_detected', 1, {'ip': ip, 'rps': str(recent_rps)})
            except Exception:
                pass

            # Progressive ban duration
            ban_duration = min(
                self.config.ddos_ban_duration * (2 ** stats.ddos_violations),
                self.config.max_ban_duration
            )
            return True, ban_duration

        return False, 0.0

    def _check_connection_flood(self, ip: str, stats: IPStats) -> tuple[bool, float]:
        """Check for connection flood attacks.

        Returns:
            Tuple of (is_flood_detected, ban_duration)
        """
        if not self.config.flood_detection_enabled:
            return False, 0.0

        now = time.time()

        # Track connections per second
        stats.connections_per_second.append(now)

        # Calculate CPS
        recent_cps = len([t for t in stats.connections_per_second if t > now - 1.0])
        
        # Record CPS metric
        try:
            metrics = get_metrics_history()
            metrics.record_metric('rate_limiter_cps', recent_cps, {'ip': ip})
        except Exception:
            pass

        if recent_cps >= self.config.flood_threshold_connections:
            stats.connection_flood_violations += 1
            log.warning(
                "Connection flood detected from %s: %d CPS (threshold: %d)",
                ip, recent_cps, self.config.flood_threshold_connections
            )
            
            # Record flood detection metric
            try:
                metrics = get_metrics_history()
                metrics.record_metric('rate_limiter_flood_detected', 1, {'ip': ip, 'cps': str(recent_cps)})
            except Exception:
                pass

            ban_duration = min(
                self.config.flood_ban_duration * (2 ** stats.connection_flood_violations),
                self.config.max_ban_duration
            )
            return True, ban_duration

        return False, 0.0

    def _check_subnet_limit(self, ip: str) -> tuple[bool, str]:
        """Check if IP's subnet has exceeded connection limit.

        Returns:
            Tuple of (is_limit_exceeded, subnet)
        """
        if not self.config.enable_ip_range_limiting:
            return False, ""

        subnet = self._get_subnet(ip)
        subnet_count = len(self._subnet_connections.get(subnet, set()))

        if subnet_count >= self.config.max_connections_per_subnet:
            log.warning(
                "Subnet limit exceeded for %s: %d connections (limit: %d)",
                subnet, subnet_count, self.config.max_connections_per_subnet
            )
            return True, subnet

        return False, subnet

    def check_rate_limit(self, ip: str) -> tuple[RateLimitAction, float]:
        if ip in self.config.allow_list:
            return RateLimitAction.ALLOW, 0.0

        now = time.time()
        stats = self._ip_stats[ip]
        stats.total_requests += 1

        # Initialize subnet if not set
        if not stats.subnet:
            stats.subnet = self._get_subnet(ip)

        # Check if already banned
        if stats.ban_until > now:
            stats.blocked_requests += 1
            return RateLimitAction.BAN, stats.ban_until - now

        # Check global limit
        global_action = self._check_global_limit()
        if global_action != RateLimitAction.ALLOW:
            stats.blocked_requests += 1
            return global_action, 0

        # DDoS detection
        if self.config.ddos_detection_enabled:
            is_ddos, ban_duration = self._check_ddos(ip, stats)
            if is_ddos:
                stats.ban_until = now + ban_duration
                stats.total_bans += 1
                stats.last_ban_duration = ban_duration
                log.critical("IP %s banned for DDoS: %.0f seconds", ip, ban_duration)
                
                # Send alert
                if _HAS_ALERTS:
                    get_alerts_manager().add_alert(
                        category='security',
                        severity='critical',
                        message=f'DDoS attack detected from {ip}',
                        details={
                            'ip': ip,
                            'ban_duration': ban_duration,
                            'rps': stats.requests_per_second[-1] if stats.requests_per_second else 0,
                        }
                    )
                
                return RateLimitAction.BAN, ban_duration

        # Connection flood detection
        if self.config.flood_detection_enabled:
            is_flood, ban_duration = self._check_connection_flood(ip, stats)
            if is_flood:
                stats.ban_until = now + ban_duration
                stats.total_bans += 1
                stats.last_ban_duration = ban_duration
                log.critical("IP %s banned for connection flood: %.0f seconds", ip, ban_duration)
                
                # Send alert
                if _HAS_ALERTS:
                    get_alerts_manager().add_alert(
                        category='security',
                        severity='critical',
                        message=f'Connection flood detected from {ip}',
                        details={
                            'ip': ip,
                            'ban_duration': ban_duration,
                            'cps': stats.connections_per_second[-1] if stats.connections_per_second else 0,
                        }
                    )
                
                return RateLimitAction.BAN, ban_duration

        # Subnet limit check
        if self.config.enable_ip_range_limiting:
            subnet_exceeded, subnet = self._check_subnet_limit(ip)
            if subnet_exceeded:
                stats.blocked_requests += 1
                log.warning("IP %s blocked: subnet %s limit exceeded", ip, subnet)
                return RateLimitAction.REJECT, 0

        # Token bucket check (more efficient than sliding window)
        if self.config.token_bucket_enabled:
            self._refill_tokens(stats, now)
            if stats.tokens < 1.0:
                # Fall back to sliding window if bucket empty
                pass
            else:
                # Consume token
                stats.tokens -= 1.0
                stats.requests.append(now)
                return RateLimitAction.ALLOW, 0

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

    def _refill_tokens(self, stats: IPStats, now: float) -> None:
        """
        Refill token bucket based on elapsed time.

        Limits maximum accumulation time to prevent token hoarding after long idle periods.
        This ensures more accurate rate limiting for burst traffic patterns.
        """
        if not self.config.token_bucket_enabled:
            return

        elapsed = now - stats.last_token_refill
        # Cap maximum refill time to prevent token accumulation abuse
        # Max 10 seconds of refill to avoid hoarding after long idle periods
        elapsed = min(elapsed, 10.0)
        refill_amount = elapsed * self.config.token_bucket_refill_rate
        stats.tokens = min(stats.tokens + refill_amount, self.config.token_bucket_capacity)
        stats.last_token_refill = now

    def _refill_api_tokens(self, stats: IPStats, now: float) -> None:
        """Refill API token bucket."""
        if not self.config.api_rate_limit_enabled:
            return

        elapsed = now - stats.last_api_token_refill
        refill_amount = elapsed * self.config.api_requests_per_second
        stats.api_tokens = min(stats.api_tokens + refill_amount, self.config.api_burst_size)
        stats.last_api_token_refill = now

    def _update_suspicious_score(self, stats: IPStats, now: float, delta: float) -> None:
        """Update suspicious activity score."""
        if not self.config.connection_scoring_enabled:
            return

        elapsed = now - stats.last_score_update
        decay = elapsed * self.config.score_decay_per_second
        stats.suspicious_score = max(0, stats.suspicious_score + delta - decay)
        stats.last_score_update = now

    def check_api_rate_limit(self, ip: str) -> tuple[RateLimitAction, float]:
        """Check rate limit for API requests (web dashboard)."""
        if ip in self.config.allow_list:
            return RateLimitAction.ALLOW, 0.0

        now = time.time()
        stats = self._ip_stats[ip]

        # Refill API tokens
        self._refill_api_tokens(stats, now)

        # Check if banned
        if stats.ban_until > now:
            return RateLimitAction.BAN, stats.ban_until - now

        # Check API token bucket
        if stats.api_tokens < 1.0:
            wait_time = (1.0 - stats.api_tokens) / self.config.api_requests_per_second
            log.debug("API rate limit exceeded for %s, wait %.1fs", ip, wait_time)
            return RateLimitAction.DELAY, wait_time

        # Consume token
        stats.api_tokens -= 1.0
        return RateLimitAction.ALLOW, 0.0

    def _clean_old_requests(self, stats: IPStats) -> None:
        hour_ago = time.time() - 3600
        while stats.requests and stats.requests[0] < hour_ago:
            stats.requests.popleft()

    def _handle_violation(self, ip: str, stats: IPStats, limit_type: str) -> tuple[RateLimitAction, float]:
        stats.violations += 1
        stats.last_violation = time.time()
        stats.blocked_requests += 1
        
        # Record violation metric
        try:
            metrics = get_metrics_history()
            metrics.record_metric('rate_limiter_violations', 1, {'ip': ip, 'type': limit_type})
        except Exception:
            pass

        delay_ms = min(
            self.config.initial_delay_ms * (self.config.backoff_multiplier ** (stats.violations - 1)),
            self.config.max_delay_ms
        )
        delay_sec = delay_ms / 1000.0

        if stats.violations >= self.config.ban_threshold:
            stats.ban_until = time.time() + self.config.ban_duration_seconds
            log.warning("IP %s banned for %.0f seconds (violations: %d, limit: %s)",
                        ip, self.config.ban_duration_seconds, stats.violations, limit_type)
            
            # Record ban metric
            try:
                metrics = get_metrics_history()
                metrics.record_metric('rate_limiter_bans', 1, {'ip': ip, 'duration': str(self.config.ban_duration_seconds)})
            except Exception:
                pass
                
            return RateLimitAction.BAN, self.config.ban_duration_seconds

        log.debug("IP %s rate limited: %s (violation %d, delay: %.1fs)",
                  ip, limit_type, stats.violations, delay_sec)
        return RateLimitAction.DELAY, delay_sec

    def add_connection(self, ip: str) -> None:
        stats = self._ip_stats[ip]
        subnet = stats.subnet or self._get_subnet(ip)

        self._active_connections[ip] += 1
        self._total_active += 1
        self._global_requests.append(time.time())

        # Track for subnet limiting
        if self.config.enable_ip_range_limiting:
            self._subnet_connections[subnet].add(ip)

        # Track for flood detection
        if self.config.flood_detection_enabled:
            self._connection_timestamps.append(time.time())
            stats.connections_per_second.append(time.time())

    def remove_connection(self, ip: str) -> None:
        if self._active_connections[ip] > 0:
            self._active_connections[ip] -= 1
            self._total_active -= 1

        # Remove from subnet tracking
        if self.config.enable_ip_range_limiting:
            stats = self._ip_stats.get(ip)
            if stats:
                subnet = stats.subnet or self._get_subnet(ip)
                self._subnet_connections[subnet].discard(ip)

                # Clean up empty subnets
                if not self._subnet_connections[subnet]:
                    del self._subnet_connections[subnet]

    def get_ip_stats(self, ip: str) -> dict:
        stats = self._ip_stats.get(ip, IPStats())
        now = time.time()

        # Refill tokens for accurate reading
        self._refill_tokens(stats, now)
        self._refill_api_tokens(stats, now)

        # Decay suspicious score
        if self.config.connection_scoring_enabled:
            elapsed = now - stats.last_score_update
            decay = elapsed * self.config.score_decay_per_second
            current_score = max(0, stats.suspicious_score - decay)
        else:
            current_score = 0

        return {
            "total_requests": stats.total_requests,
            "blocked_requests": stats.blocked_requests,
            "violations": stats.violations,
            "active_connections": self._active_connections[ip],
            "is_banned": stats.ban_until > now,
            "ban_remaining": max(0, stats.ban_until - now),
            "requests_last_minute": sum(1 for t in stats.requests if t > now - 60),
            "ddos_violations": stats.ddos_violations,
            "flood_violations": stats.connection_flood_violations,
            "total_bans": stats.total_bans,
            "subnet": stats.subnet or self._get_subnet(ip),
            # Token bucket stats
            "tokens_remaining": stats.tokens,
            "api_tokens_remaining": stats.api_tokens,
            # Suspicious activity
            "suspicious_score": current_score,
            "is_suspicious": current_score > self.config.suspicious_score_threshold,
        }

    def get_global_stats(self) -> dict:
        now = time.time()
        banned_count = sum(1 for s in self._ip_stats.values() if s.ban_until > now)
        ddos_detected = sum(1 for s in self._ip_stats.values() if s.ddos_violations > 0)
        flood_detected = sum(1 for s in self._ip_stats.values() if s.connection_flood_violations > 0)
        suspicious_count = sum(1 for s in self._ip_stats.values() if s.suspicious_score > self.config.suspicious_score_threshold)

        return {
            "total_active_connections": self._total_active,
            "unique_ips": len(self._ip_stats),
            "requests_last_minute": len([t for t in self._global_requests if t > now - 60]),
            "banned_ips": banned_count,
            "total_violations": sum(s.violations for s in self._ip_stats.values()),
            "ddos_attacks_detected": ddos_detected,
            "flood_attacks_detected": flood_detected,
            "subnets_active": len(self._subnet_connections),
            "connection_flood_rate": len([t for t in self._connection_timestamps if t > now - 1.0]),
            "suspicious_ips": suspicious_count,
        }

    def get_prometheus_metrics(self) -> str:
        """
        Export rate limiter metrics in Prometheus format.
        
        Returns:
            String with Prometheus metrics exposition format
        """
        now = time.time()
        lines = []
        stats = self.get_global_stats()
        
        # Active connections
        lines.append('# HELP rate_limiter_active_connections Current number of active connections')
        lines.append('# TYPE rate_limiter_active_connections gauge')
        lines.append(f'rate_limiter_active_connections {stats["total_active_connections"]}')
        lines.append('')
        
        # Unique IPs
        lines.append('# HELP rate_limiter_unique_ips Number of unique IPs seen')
        lines.append('# TYPE rate_limiter_unique_ips gauge')
        lines.append(f'rate_limiter_unique_ips {stats["unique_ips"]}')
        lines.append('')
        
        # Banned IPs
        lines.append('# HELP rate_limiter_banned_ips Number of currently banned IPs')
        lines.append('# TYPE rate_limiter_banned_ips gauge')
        lines.append(f'rate_limiter_banned_ips {stats["banned_ips"]}')
        lines.append('')
        
        # Total violations
        lines.append('# HELP rate_limiter_total_violations Total number of rate limit violations')
        lines.append('# TYPE rate_limiter_total_violations counter')
        lines.append(f'rate_limiter_total_violations {stats["total_violations"]}')
        lines.append('')
        
        # DDoS attacks detected
        lines.append('# HELP rate_limiter_ddos_attacks_total Number of DDoS attacks detected')
        lines.append('# TYPE rate_limiter_ddos_attacks_total counter')
        lines.append(f'rate_limiter_ddos_attacks_total {stats["ddos_attacks_detected"]}')
        lines.append('')
        
        # Flood attacks detected
        lines.append('# HELP rate_limiter_flood_attacks_total Number of flood attacks detected')
        lines.append('# TYPE rate_limiter_flood_attacks_total counter')
        lines.append(f'rate_limiter_flood_attacks_total {stats["flood_attacks_detected"]}')
        lines.append('')
        
        # Suspicious IPs
        lines.append('# HELP rate_limiter_suspicious_ips Number of IPs with suspicious score')
        lines.append('# TYPE rate_limiter_suspicious_ips gauge')
        lines.append(f'rate_limiter_suspicious_ips {stats["suspicious_ips"]}')
        lines.append('')
        
        # Active subnets
        lines.append('# HELP rate_limiter_subnets_active Number of active subnets')
        lines.append('# TYPE rate_limiter_subnets_active gauge')
        lines.append(f'rate_limiter_subnets_active {stats["subnets_active"]}')
        lines.append('')
        
        # Requests per minute
        lines.append('# HELP rate_limiter_requests_per_minute Requests in the last minute')
        lines.append('# TYPE rate_limiter_requests_per_minute gauge')
        lines.append(f'rate_limiter_requests_per_minute {stats["requests_last_minute"]}')
        lines.append('')
        
        # Connection flood rate (CPS)
        lines.append('# HELP rate_limiter_flood_rate Current connection flood rate (per second)')
        lines.append('# TYPE rate_limiter_flood_rate gauge')
        lines.append(f'rate_limiter_flood_rate {stats["connection_flood_rate"]}')
        
        return '\n'.join(lines)

    def record_request(self, ip: str, success: bool = True) -> None:
        """Record request for metrics tracking."""
        stats = self._ip_stats[ip]
        if success:
            stats.total_requests += 1
        else:
            stats.blocked_requests += 1

        # Update suspicious score for blocked requests
        if not success:
            self._update_suspicious_score(stats, time.time(), 10.0)

    def record_suspicious_activity(self, ip: str, score_delta: float = 5.0) -> None:
        """Record suspicious activity for an IP."""
        stats = self._ip_stats[ip]
        self._update_suspicious_score(stats, time.time(), score_delta)

        # Auto-ban if threshold exceeded
        if stats.suspicious_score > self.config.suspicious_score_threshold:
            self.ban_ip(ip, self.config.max_ban_duration)
            log.warning("IP %s auto-banned: suspicious score %.0f > %d",
                       ip, stats.suspicious_score, self.config.suspicious_score_threshold)

    def get_metrics_for_prometheus(self) -> dict[str, float]:
        """Get metrics formatted for Prometheus export."""
        stats = self.get_global_stats()

        return {
            'rate_limiter_active_connections': float(stats['total_active_connections']),
            'rate_limiter_unique_ips': float(stats['unique_ips']),
            'rate_limiter_banned_ips': float(stats['banned_ips']),
            'rate_limiter_total_violations': float(stats['total_violations']),
            'rate_limiter_ddos_attacks': float(stats['ddos_attacks_detected']),
            'rate_limiter_flood_attacks': float(stats['flood_attacks_detected']),
            'rate_limiter_suspicious_ips': float(stats['suspicious_ips']),
            'rate_limiter_requests_per_minute': float(stats['requests_last_minute']),
            'rate_limiter_flood_rate': float(stats['connection_flood_rate']),
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


def check_api_rate_limit(ip: str) -> tuple[RateLimitAction, float]:
    """Check API rate limit for web dashboard."""
    return get_rate_limiter().check_api_rate_limit(ip)


def record_suspicious_activity(ip: str, score_delta: float = 5.0) -> None:
    """Record suspicious activity for an IP."""
    get_rate_limiter().record_suspicious_activity(ip, score_delta)


__all__ = [
    'RateLimitConfig',
    'RateLimiter',
    'RateLimitAction',
    'get_rate_limiter',
    'check_rate_limit',
    'add_connection',
    'remove_connection',
    'check_api_rate_limit',
    'record_suspicious_activity',
]
