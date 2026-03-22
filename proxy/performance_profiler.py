"""
Performance Profiling Module for TG WS Proxy.

Provides CPU and memory profiling with actionable recommendations:
- Hotspot detection (top 10 CPU consumers)
- Memory allocation tracking
- Function call statistics
- Optimization suggestions

Author: Dupley Maxim Igorevich
© 2026 Dupley Maxim Igorevich. All rights reserved.
"""

from __future__ import annotations

import asyncio
import cProfile
import gc
import logging
import pstats
import time
from dataclasses import dataclass
from io import StringIO
from typing import Any, Callable, TypeVar

log = logging.getLogger('tg-ws-profiler')

T = TypeVar('T')


@dataclass
class ProfileResult:
    """Profiling result with statistics."""
    total_time: float
    total_calls: int
    primitive_calls: int
    recursive_calls: int
    top_functions: list[tuple[str, int, float, float, float]]  # (name, calls, tottime, cumtime, percall)
    memory_before: int = 0
    memory_after: int = 0
    memory_delta: int = 0

    def get_report(self, limit: int = 20) -> str:
        """Generate human-readable report."""
        lines = [
            "=" * 80,
            "PERFORMANCE PROFILE REPORT",
            "=" * 80,
            f"Total Time: {self.total_time:.3f}s",
            f"Total Calls: {self.total_calls:,}",
            f"Primitive Calls: {self.primitive_calls:,}",
            f"Recursive Calls: {self.recursive_calls:,}",
            f"Memory Before: {self.memory_before / 1024 / 1024:.2f} MB",
            f"Memory After: {self.memory_after / 1024 / 1024:.2f} MB",
            f"Memory Delta: {self.memory_delta / 1024 / 1024:.2f} MB",
            "",
            "TOP FUNCTIONS BY CUMULATIVE TIME:",
            "-" * 80,
            f"{'Function':<60} {'Calls':>8} {'TotTime':>10} {'CumTime':>10} {'PerCall':>10}",
            "-" * 80,
        ]

        for name, calls, tottime, cumtime, percall in self.top_functions[:limit]:
            lines.append(f"{name:<60} {calls:>8} {tottime:>10.4f} {cumtime:>10.4f} {percall:>10.4f}")

        lines.append("=" * 80)
        return "\n".join(lines)


@dataclass
class OptimizationSuggestion:
    """Optimization suggestion with priority."""
    priority: int  # 1-5 (5 = highest)
    category: str
    description: str
    expected_improvement: str
    implementation_effort: str  # low/medium/high


class PerformanceProfiler:
    """
    Performance profiler with optimization recommendations.

    Usage:
        profiler = PerformanceProfiler()

        # Profile a function
        result = await profiler.profile(my_async_func, arg1, arg2)
        print(result.get_report())

        # Get optimization suggestions
        suggestions = profiler.get_suggestions(result)
    """

    def __init__(self, enable_memory_tracking: bool = True):
        """
        Initialize profiler.

        Args:
            enable_memory_tracking: Track memory usage during profiling
        """
        self.enable_memory_tracking = enable_memory_tracking
        self._results: list[ProfileResult] = []

    def _get_memory_usage(self) -> int:
        """Get current memory usage in bytes."""
        try:
            import tracemalloc
            if not tracemalloc.is_tracing():
                tracemalloc.start()
            current, peak = tracemalloc.get_traced_memory()
            return current
        except Exception:
            return 0

    async def profile(
        self,
        func: Callable[..., T],
        *args: Any,
        **kwargs: Any,
    ) -> ProfileResult:
        """
        Profile async function execution.

        Args:
            func: Async function to profile
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            ProfileResult with statistics
        """
        # Force garbage collection before profiling
        gc.collect()

        # Get memory before
        memory_before = self._get_memory_usage() if self.enable_memory_tracking else 0

        # Create profiler
        pr = cProfile.Profile()
        pr.enable()

        start_time = time.perf_counter()

        try:
            # Execute function
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
        finally:
            pr.disable()
            end_time = time.perf_counter()

        # Get memory after
        memory_after = self._get_memory_usage() if self.enable_memory_tracking else 0

        # Parse stats
        stream = StringIO()
        ps = pstats.Stats(pr, stream=stream)
        ps.sort_stats('cumulative')
        ps.print_stats(20)

        # Extract top functions
        top_functions = []
        for func_name, (cc, nc, tt, ct, _callers) in ps.stats.items():  # type: ignore[attr-defined]
            filename, line, func = func_name
            full_name = f"{filename}:{line}({func})"
            percall = ct / cc if cc > 0 else 0
            top_functions.append((full_name, nc, tt, ct, percall))

        # Sort by cumulative time
        top_functions.sort(key=lambda x: x[3], reverse=True)

        # Create result
        profile_result = ProfileResult(
            total_time=end_time - start_time,
            total_calls=ps.total_calls,  # type: ignore[attr-defined]
            primitive_calls=nc,
            recursive_calls=ps.stats.get((':', 0, '<listcomp>'), (0, 0, 0, 0, 0))[0] if ps.stats else 0,  # type: ignore[attr-defined]
            top_functions=top_functions[:20],
            memory_before=memory_before,
            memory_after=memory_after,
            memory_delta=memory_after - memory_before,
        )

        self._results.append(profile_result)

        # Log summary
        func_name = getattr(func, '__name__', str(func))
        log.info(
            "Profiled %s: %.3fs, %d calls, %d primitive, memory: %.2f MB",
            func_name,
            profile_result.total_time,
            profile_result.total_calls,
            profile_result.primitive_calls,
            profile_result.memory_delta / 1024 / 1024,
        )

        return profile_result

    def get_suggestions(self, result: ProfileResult) -> list[OptimizationSuggestion]:
        """
        Generate optimization suggestions based on profile result.

        Args:
            result: Profile result to analyze

        Returns:
            List of optimization suggestions sorted by priority
        """
        suggestions: list[OptimizationSuggestion] = []

        # Analyze memory usage
        if result.memory_delta > 50 * 1024 * 1024:  # > 50 MB
            suggestions.append(OptimizationSuggestion(
                priority=5,
                category="Memory",
                description="High memory allocation detected (>50MB)",
                expected_improvement="Reduce memory footprint by 30-50%",
                implementation_effort="medium",
            ))

        # Analyze function hotspots
        for name, calls, _tottime, _cumtime, percall in result.top_functions[:5]:
            # Check for high call count
            if calls > 10000:
                suggestions.append(OptimizationSuggestion(
                    priority=4,
                    category="CPU",
                    description=f"Function called excessively: {name} ({calls:,} calls)",
                    expected_improvement="Reduce call count with caching or batching",
                    implementation_effort="low",
                ))

            # Check for slow functions
            if percall > 0.1:  # > 100ms per call
                suggestions.append(OptimizationSuggestion(
                    priority=5,
                    category="CPU",
                    description=f"Slow function detected: {name} ({percall:.3f}s/call)",
                    expected_improvement="Optimize algorithm or use async I/O",
                    implementation_effort="medium",
                ))

        # Check for DNS-related functions
        dns_functions = [f for f in result.top_functions if 'dns' in f[0].lower() or 'resolve' in f[0].lower()]
        if dns_functions:
            total_dns_time = sum(f[3] for f in dns_functions)
            if total_dns_time > result.total_time * 0.3:  # > 30% of total time
                suggestions.append(OptimizationSuggestion(
                    priority=4,
                    category="I/O",
                    description=f"DNS resolution taking {total_dns_time:.2f}s ({total_dns_time/result.total_time*100:.1f}% of total)",
                    expected_improvement="Enable DNS caching (target: >90% hit rate)",
                    implementation_effort="low",
                ))

        # Check for WebSocket-related functions
        ws_functions = [f for f in result.top_functions if 'websocket' in f[0].lower() or 'ws_' in f[0].lower()]
        if ws_functions:
            total_ws_time = sum(f[3] for f in ws_functions)
            if total_ws_time > result.total_time * 0.4:  # > 40% of total time
                suggestions.append(OptimizationSuggestion(
                    priority=3,
                    category="I/O",
                    description=f"WebSocket operations taking {total_ws_time:.2f}s ({total_ws_time/result.total_time*100:.1f}% of total)",
                    expected_improvement="Optimize reconnection logic and pooling",
                    implementation_effort="medium",
                ))

        # Sort by priority
        suggestions.sort(key=lambda x: x.priority, reverse=True)

        return suggestions

    def get_all_results(self) -> list[ProfileResult]:
        """Get all profile results."""
        return self._results

    def clear_results(self) -> None:
        """Clear all profile results."""
        self._results.clear()


# Global profiler instance
_profiler: PerformanceProfiler | None = None


def get_profiler(enable_memory_tracking: bool = True) -> PerformanceProfiler:
    """Get global profiler instance."""
    global _profiler
    if _profiler is None:
        _profiler = PerformanceProfiler(enable_memory_tracking)
    return _profiler


async def profile_async(
    func: Callable[..., T],
    *args: Any,
    **kwargs: Any,
) -> T:
    """
    Profile async function using global profiler.

    Usage:
        result = await profile_async(my_func, arg1, arg2)
    """
    profiler = get_profiler()
    return await profiler.profile(func, *args, **kwargs)  # type: ignore[return-value]


def print_profile_report(result: ProfileResult, limit: int = 20) -> None:
    """Print profile report to stdout."""
    print(result.get_report(limit))


def print_optimization_suggestions(result: ProfileResult) -> None:
    """Print optimization suggestions to stdout."""
    profiler = get_profiler()
    suggestions = profiler.get_suggestions(result)

    if not suggestions:
        print("No optimization suggestions.")
        return

    print("\n" + "=" * 80)
    print("OPTIMIZATION SUGGESTIONS")
    print("=" * 80)

    for i, suggestion in enumerate(suggestions, 1):
        print(f"\n{i}. [{suggestion.priority}/5] {suggestion.category}")
        print(f"   {suggestion.description}")
        print(f"   Expected: {suggestion.expected_improvement}")
        print(f"   Effort: {suggestion.implementation_effort}")

    print("=" * 80)
