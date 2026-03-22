"""Unit tests for performance profiler module."""

from __future__ import annotations

import asyncio

import pytest

from proxy.performance_profiler import (
    OptimizationSuggestion,
    PerformanceProfiler,
    ProfileResult,
    get_profiler,
    profile_async,
)


class TestProfileResult:
    """Tests for ProfileResult dataclass."""

    def test_get_report(self):
        """Test generating profile report."""
        result = ProfileResult(
            total_time=1.5,
            total_calls=1000,
            primitive_calls=800,
            recursive_calls=50,
            top_functions=[
                ("test.py:1(func)", 100, 0.5, 1.0, 0.01),
                ("test.py:10(func2)", 50, 0.3, 0.5, 0.01),
            ],
            memory_before=50 * 1024 * 1024,
            memory_after=55 * 1024 * 1024,
            memory_delta=5 * 1024 * 1024,
        )

        report = result.get_report(limit=10)

        assert "PERFORMANCE PROFILE REPORT" in report
        assert "Total Time: 1.500s" in report
        assert "Total Calls: 1,000" in report
        assert "Memory Before: 50.00 MB" in report
        assert "Memory Delta: 5.00 MB" in report
        assert "test.py:1(func)" in report


class TestPerformanceProfiler:
    """Tests for PerformanceProfiler class."""

    @pytest.mark.asyncio
    async def test_profile_sync_function(self):
        """Test profiling a synchronous function."""
        profiler = PerformanceProfiler(enable_memory_tracking=False)

        def sync_func(x: int, y: int) -> int:
            return x + y

        result = await profiler.profile(sync_func, 5, 3)

        assert result == 8
        assert result.total_time > 0
        assert result.total_calls > 0

    @pytest.mark.asyncio
    async def test_profile_async_function(self):
        """Test profiling an asynchronous function."""
        profiler = PerformanceProfiler(enable_memory_tracking=False)

        async def async_func(delay: float) -> str:
            await asyncio.sleep(delay)
            return "done"

        result = await profiler.profile(async_func, 0.1)

        assert result == "done"
        assert result.total_time >= 0.1
        assert result.total_calls > 0

    @pytest.mark.asyncio
    async def test_profile_with_kwargs(self):
        """Test profiling with keyword arguments."""
        profiler = PerformanceProfiler(enable_memory_tracking=False)

        async def func_with_kwargs(a: int, b: int = 10) -> int:
            return a + b

        result = await profiler.profile(func_with_kwargs, 5, b=20)

        assert result == 25

    @pytest.mark.asyncio
    async def test_memory_tracking(self):
        """Test memory tracking during profiling."""
        profiler = PerformanceProfiler(enable_memory_tracking=True)

        def allocate_memory() -> list:
            # Allocate some memory
            return [0] * 10000

        result = await profiler.profile(allocate_memory)

        assert result.memory_before >= 0
        assert result.memory_after >= 0
        # Memory delta may be positive or negative depending on GC

    @pytest.mark.asyncio
    async def test_get_suggestions_high_memory(self):
        """Test suggestions for high memory usage."""
        profiler = PerformanceProfiler()

        result = ProfileResult(
            total_time=1.0,
            total_calls=100,
            primitive_calls=80,
            recursive_calls=0,
            top_functions=[],
            memory_before=50 * 1024 * 1024,
            memory_after=110 * 1024 * 1024,
            memory_delta=60 * 1024 * 1024,
        )

        suggestions = profiler.get_suggestions(result)

        # Should suggest memory optimization
        memory_suggestions = [s for s in suggestions if s.category == "Memory"]
        assert len(memory_suggestions) > 0
        assert memory_suggestions[0].priority >= 4

    @pytest.mark.asyncio
    async def test_get_suggestions_high_call_count(self):
        """Test suggestions for high call count."""
        profiler = PerformanceProfiler()

        result = ProfileResult(
            total_time=1.0,
            total_calls=50000,
            primitive_calls=40000,
            recursive_calls=0,
            top_functions=[
                ("test.py:1(func)", 15000, 0.1, 0.5, 0.00003),
            ],
            memory_before=0,
            memory_after=0,
            memory_delta=0,
        )

        suggestions = profiler.get_suggestions(result)

        # Should suggest reducing call count
        cpu_suggestions = [s for s in suggestions if "excessively" in s.description]
        assert len(cpu_suggestions) > 0

    @pytest.mark.asyncio
    async def test_get_suggestions_slow_function(self):
        """Test suggestions for slow functions."""
        profiler = PerformanceProfiler()

        result = ProfileResult(
            total_time=1.0,
            total_calls=100,
            primitive_calls=80,
            recursive_calls=0,
            top_functions=[
                ("test.py:1(slow_func)", 10, 0.05, 0.8, 0.08),
            ],
            memory_before=0,
            memory_after=0,
            memory_delta=0,
        )

        suggestions = profiler.get_suggestions(result)

        # Should suggest optimizing slow function
        slow_suggestions = [s for s in suggestions if "Slow function" in s.description]
        assert len(slow_suggestions) > 0

    @pytest.mark.asyncio
    async def test_get_suggestions_dns(self):
        """Test suggestions for DNS-related bottlenecks."""
        profiler = PerformanceProfiler()

        result = ProfileResult(
            total_time=1.0,
            total_calls=1000,
            primitive_calls=800,
            recursive_calls=0,
            top_functions=[
                ("dns_resolver.py:1(resolve)", 100, 0.1, 0.4, 0.004),
                ("dns_resolver.py:10(cache_lookup)", 200, 0.05, 0.2, 0.001),
            ],
            memory_before=0,
            memory_after=0,
            memory_delta=0,
        )

        suggestions = profiler.get_suggestions(result)

        # Should suggest DNS caching
        dns_suggestions = [s for s in suggestions if "DNS" in s.description]
        assert len(dns_suggestions) > 0

    @pytest.mark.asyncio
    async def test_get_suggestions_websocket(self):
        """Test suggestions for WebSocket-related bottlenecks."""
        profiler = PerformanceProfiler()

        result = ProfileResult(
            total_time=1.0,
            total_calls=500,
            primitive_calls=400,
            recursive_calls=0,
            top_functions=[
                ("websocket_client.py:1(connect)", 50, 0.1, 0.5, 0.01),
                ("websocket_client.py:50(send)", 100, 0.05, 0.3, 0.003),
            ],
            memory_before=0,
            memory_after=0,
            memory_delta=0,
        )

        suggestions = profiler.get_suggestions(result)

        # Should suggest WebSocket optimization
        ws_suggestions = [s for s in suggestions if "WebSocket" in s.description]
        assert len(ws_suggestions) > 0

    @pytest.mark.asyncio
    async def test_suggestions_sorted_by_priority(self):
        """Test that suggestions are sorted by priority."""
        profiler = PerformanceProfiler()

        result = ProfileResult(
            total_time=1.0,
            total_calls=50000,
            primitive_calls=40000,
            recursive_calls=0,
            top_functions=[
                ("test.py:1(slow_func)", 15000, 0.1, 0.8, 0.00005),
            ],
            memory_before=50 * 1024 * 1024,
            memory_after=120 * 1024 * 1024,
            memory_delta=70 * 1024 * 1024,
        )

        suggestions = profiler.get_suggestions(result)

        priorities = [s.priority for s in suggestions]
        assert priorities == sorted(priorities, reverse=True)

    @pytest.mark.asyncio
    async def test_get_all_results(self):
        """Test getting all profile results."""
        profiler = PerformanceProfiler(enable_memory_tracking=False)

        async def func1():
            await asyncio.sleep(0.01)

        async def func2():
            await asyncio.sleep(0.02)

        await profiler.profile(func1)
        await profiler.profile(func2)

        results = profiler.get_all_results()

        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_clear_results(self):
        """Test clearing profile results."""
        profiler = PerformanceProfiler(enable_memory_tracking=False)

        async def func():
            await asyncio.sleep(0.01)

        await profiler.profile(func)
        assert len(profiler.get_all_results()) > 0

        profiler.clear_results()
        assert len(profiler.get_all_results()) == 0


class TestGlobalProfiler:
    """Tests for global profiler functions."""

    @pytest.mark.asyncio
    async def test_get_profiler_singleton(self):
        """Test that get_profiler returns singleton."""
        profiler1 = get_profiler()
        profiler2 = get_profiler()

        assert profiler1 is profiler2

    @pytest.mark.asyncio
    async def test_profile_async_helper(self):
        """Test profile_async helper function."""
        # Clear global profiler
        profiler = get_profiler()
        profiler.clear_results()

        async def my_func(x: int) -> int:
            return x * 2

        result = await profile_async(my_func, 5)

        assert result == 10
        assert len(profiler.get_all_results()) == 1


class TestOptimizationSuggestion:
    """Tests for OptimizationSuggestion dataclass."""

    def test_suggestion_creation(self):
        """Test creating optimization suggestion."""
        suggestion = OptimizationSuggestion(
            priority=5,
            category="CPU",
            description="Optimize hot function",
            expected_improvement="20% faster",
            implementation_effort="medium",
        )

        assert suggestion.priority == 5
        assert suggestion.category == "CPU"
        assert "Optimize" in suggestion.description
