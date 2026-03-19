"""
Performance profiler for TG WS Proxy.

Provides tools for profiling and analyzing proxy performance.
"""

from __future__ import annotations

import cProfile
import io
import logging
import pstats
import time
from typing import Any, Callable, Dict, List, Optional

log = logging.getLogger("tg-ws-proxy-profiler")


class PerformanceProfiler:
    """
    Performance profiler for measuring function execution time.
    
    Usage:
        profiler = PerformanceProfiler()
        
        # Profile a function
        result = profiler.profile(my_function, *args, **kwargs)
        
        # Get statistics
        stats = profiler.get_stats()
        profiler.print_stats()
    """

    def __init__(self) -> None:
        self._profiler: Optional[cProfile.Profile] = None
        self._stats: Optional[pstats.Stats] = None
        self._profile_data: Optional[bytes] = None
        self._is_profiling = False

    def start(self) -> None:
        """Start profiling."""
        if self._is_profiling:
            log.warning("Profiling already in progress")
            return

        self._profiler = cProfile.Profile()
        self._profiler.enable()
        self._is_profiling = True
        log.info("Profiling started")

    def stop(self) -> None:
        """Stop profiling and collect statistics."""
        if not self._is_profiling or not self._profiler:
            return

        self._profiler.disable()
        self._is_profiling = False

        # Save profile data
        stream = io.StringIO()
        self._stats = pstats.Stats(self._profiler, stream=stream)
        self._stats.sort_stats(pstats.SortKey.TIME)

        log.info("Profiling completed")

    def profile(self, func: Callable, *args, **kwargs) -> Any:
        """
        Profile a function execution.
        
        Args:
            func: Function to profile
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function
            
        Returns:
            Function result
        """
        self.start()
        try:
            result = func(*args, **kwargs)
            return result
        finally:
            self.stop()

    async def profile_async(self, func: Callable, *args, **kwargs) -> Any:
        """
        Profile an async function execution.
        
        Args:
            func: Async function to profile
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function
            
        Returns:
            Function result
        """
        self.start()
        try:
            result = await func(*args, **kwargs)
            return result
        finally:
            self.stop()

    def get_stats(self) -> Dict:
        """
        Get profiling statistics.
        
        Returns:
            Dictionary with profiling statistics
        """
        if not self._stats:
            return {}

        # Extract key statistics
        total_calls = self._stats.total_calls
        total_time = self._stats.total_tt
        file_stats = []

        # Get top 20 functions by time
        for func_key, func_stats in list(self._stats.stats.items())[:20]:
            filename, line_no, func_name = func_key
            cc, nc, tt, ct, callers = func_stats

            file_stats.append({
                "function": func_name,
                "filename": filename,
                "line_no": line_no,
                "call_count": nc,
                "total_time": tt,
                "cumulative_time": ct,
                "time_per_call": tt / nc if nc > 0 else 0,
            })

        return {
            "total_calls": total_calls,
            "total_time": total_time,
            "functions": file_stats,
        }

    def print_stats(self, top_n: int = 20) -> None:
        """
        Print profiling statistics to log.
        
        Args:
            top_n: Number of top functions to display
        """
        if not self._stats:
            return

        stream = io.StringIO()
        print_stats = pstats.Stats(self._profiler, stream=stream)
        print_stats.sort_stats(pstats.SortKey.TIME)
        print_stats.print_stats(top_n)

        log.info("Profiling results:\n%s", stream.getvalue())

    def get_profile_string(self, top_n: int = 20) -> str:
        """
        Get profiling statistics as a formatted string.
        
        Args:
            top_n: Number of top functions to display
            
        Returns:
            Formatted profiling statistics string
        """
        if not self._stats:
            return "No profiling data available"

        stream = io.StringIO()
        print_stats = pstats.Stats(self._profiler, stream=stream)
        print_stats.sort_stats(pstats.SortKey.TIME)
        print_stats.print_stats(top_n)

        return stream.getvalue()


class AsyncPerformanceProfiler:
    """
    Async-aware performance profiler for measuring async function execution time.
    
    Usage:
        profiler = AsyncPerformanceProfiler()
        
        # Profile an async function
        result = await profiler.profile_async(my_async_function, *args, **kwargs)
        
        # Get statistics
        stats = profiler.get_stats()
    """

    def __init__(self) -> None:
        self._timings: Dict[str, List[float]] = {}
        self._call_counts: Dict[str, int] = {}

    async def profile_async(
        self,
        func: Callable,
        name: Optional[str] = None,
        *args,
        **kwargs
    ) -> Any:
        """
        Profile an async function execution.
        
        Args:
            func: Async function to profile
            name: Optional name for the function (defaults to func.__name__)
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function
            
        Returns:
            Function result
        """
        func_name = name or func.__name__

        start_time = time.perf_counter()
        try:
            result = await func(*args, **kwargs)
            return result
        finally:
            elapsed = time.perf_counter() - start_time
            self._record_timing(func_name, elapsed)

    def _record_timing(self, name: str, elapsed: float) -> None:
        """Record a timing measurement."""
        if name not in self._timings:
            self._timings[name] = []
            self._call_counts[name] = 0

        self._timings[name].append(elapsed)
        self._call_counts[name] += 1

        # Keep only last 1000 measurements
        if len(self._timings[name]) > 1000:
            self._timings[name].pop(0)

    def get_stats(self) -> Dict[str, Dict]:
        """
        Get timing statistics for all profiled functions.
        
        Returns:
            Dictionary mapping function names to statistics
        """
        result = {}

        for name, timings in self._timings.items():
            if not timings:
                continue

            result[name] = {
                "calls": self._call_counts.get(name, 0),
                "total_time": sum(timings),
                "avg_time": sum(timings) / len(timings),
                "min_time": min(timings),
                "max_time": max(timings),
                "last_time": timings[-1] if timings else 0,
            }

        return result

    def print_stats(self) -> None:
        """Print timing statistics to log."""
        stats = self.get_stats()

        if not stats:
            log.info("No profiling data available")
            return

        log.info("Performance Profiling Results:")
        log.info("=" * 80)
        log.info(f"{'Function':<40} {'Calls':>8} {'Total(s)':>10} {'Avg(ms)':>10} {'Min(ms)':>10} {'Max(ms)':>10}")
        log.info("=" * 80)

        # Sort by total time
        sorted_stats = sorted(
            stats.items(),
            key=lambda x: x[1]["total_time"],
            reverse=True
        )

        for name, stat in sorted_stats:
            log.info(
                f"{name:<40} {stat['calls']:>8} {stat['total_time']:>10.3f} "
                f"{stat['avg_time']*1000:>10.2f} {stat['min_time']*1000:>10.2f} {stat['max_time']*1000:>10.2f}"
            )

        log.info("=" * 80)

    def clear(self) -> None:
        """Clear all profiling data."""
        self._timings.clear()
        self._call_counts.clear()
        log.info("Profiling data cleared")


# Global profiler instance
_profiler: Optional[PerformanceProfiler] = None
_async_profiler: Optional[AsyncPerformanceProfiler] = None


def get_profiler() -> PerformanceProfiler:
    """Get global profiler instance."""
    global _profiler
    if _profiler is None:
        _profiler = PerformanceProfiler()
    return _profiler


def get_async_profiler() -> AsyncPerformanceProfiler:
    """Get global async profiler instance."""
    global _async_profiler
    if _async_profiler is None:
        _async_profiler = AsyncPerformanceProfiler()
    return _async_profiler


def start_profiling() -> None:
    """Start global profiling."""
    get_profiler().start()


def stop_profiling() -> None:
    """Stop global profiling and print results."""
    get_profiler().stop()
    get_profiler().print_stats()


def print_profiling_stats() -> None:
    """Print profiling statistics."""
    get_profiler().print_stats()
    get_async_profiler().print_stats()
