"""Unit tests for proxy profiler module."""



from proxy.profiler import AsyncPerformanceProfiler, PerformanceProfiler


class TestPerformanceProfiler:
    """Tests for PerformanceProfiler class."""

    def test_init(self):
        """Test profiler initialization."""
        profiler = PerformanceProfiler()
        assert profiler._profiler is None
        assert profiler._stats is None
        assert profiler._is_profiling is False

    def test_start_stop(self):
        """Test start and stop profiling."""
        profiler = PerformanceProfiler()
        profiler.start()
        assert profiler._is_profiling is True
        assert profiler._profiler is not None
        profiler.stop()

    def test_stop_without_start(self):
        """Test stopping without starting does nothing."""
        profiler = PerformanceProfiler()
        profiler.stop()  # Should not raise
        assert profiler._is_profiling is False

    def test_get_stats_empty(self):
        """Test get_stats without profiling."""
        profiler = PerformanceProfiler()
        stats = profiler.get_stats()
        assert stats == {}

    def test_profile_sync_function(self):
        """Test profiling a synchronous function."""
        profiler = PerformanceProfiler()

        def test_func():
            return 42

        result = profiler.profile(test_func)

        assert result == 42
        assert profiler._stats is not None

    def test_profile_async_function(self):
        """Test profiling an async function."""
        import asyncio

        profiler = PerformanceProfiler()

        async def test_func():
            return 42

        result = asyncio.run(profiler.profile_async(test_func))

        assert result == 42
        assert profiler._stats is not None

    def test_print_stats(self, caplog):
        """Test print_stats method."""
        profiler = PerformanceProfiler()

        def test_func():
            return 42

        profiler.profile(test_func)

        # Should not raise
        profiler.print_stats()

    def test_get_stats_with_data(self):
        """Test get_stats after profiling."""
        profiler = PerformanceProfiler()

        def test_func():
            return 42

        profiler.profile(test_func)
        stats = profiler.get_stats()

        assert isinstance(stats, dict)

    def test_start_while_already_profiling(self, caplog):
        """Test starting while already profiling."""
        profiler = PerformanceProfiler()
        profiler.start()
        profiler.start()  # Should log warning

        assert "Profiling already in progress" in caplog.text


class TestAsyncPerformanceProfiler:
    """Tests for AsyncPerformanceProfiler class."""

    def test_init(self):
        """Test async profiler initialization."""
        profiler = AsyncPerformanceProfiler()
        assert profiler._timings == {}
        assert profiler._call_counts == {}

    def test_record_timing(self):
        """Test _record_timing method."""
        profiler = AsyncPerformanceProfiler()
        profiler._record_timing("test_func", 0.5)

        assert "test_func" in profiler._timings
        assert profiler._timings["test_func"] == [0.5]
        assert profiler._call_counts["test_func"] == 1

    def test_record_timing_limit(self):
        """Test _record_timing keeps only last 1000 measurements."""
        profiler = AsyncPerformanceProfiler()

        for i in range(1005):
            profiler._record_timing("test_func", i * 0.001)

        assert len(profiler._timings["test_func"]) == 1000
        assert profiler._timings["test_func"][0] == 0.005

    def test_get_stats_empty(self):
        """Test get_stats without profiling."""
        profiler = AsyncPerformanceProfiler()
        stats = profiler.get_stats()
        assert stats == {}

    def test_get_stats_with_data(self):
        """Test get_stats after profiling."""
        profiler = AsyncPerformanceProfiler()
        profiler._record_timing("test_func", 0.1)
        profiler._record_timing("test_func", 0.2)
        profiler._record_timing("test_func", 0.3)
        profiler._call_counts["test_func"] = 3

        stats = profiler.get_stats()

        assert 'test_func' in stats
        assert stats['test_func']['calls'] == 3
        assert stats['test_func']['total_time'] == 0.6
        assert abs(stats['test_func']['avg_time'] - 0.2) < 0.001
        assert stats['test_func']['min_time'] == 0.1
        assert stats['test_func']['max_time'] == 0.3
        assert stats['test_func']['last_time'] == 0.3

    def test_get_stats_multiple_functions(self):
        """Test get_stats with multiple functions."""
        profiler = AsyncPerformanceProfiler()
        profiler._record_timing("func_a", 0.1)
        profiler._record_timing("func_b", 0.2)

        stats = profiler.get_stats()
        assert 'func_a' in stats
        assert 'func_b' in stats

    def test_clear(self):
        """Test clear method."""
        profiler = AsyncPerformanceProfiler()
        profiler._record_timing("test_func", 0.5)
        profiler.clear()

        assert profiler._timings == {}
        assert profiler._call_counts == {}

    def test_profile_async_method(self):
        """Test profile_async method."""
        import asyncio

        profiler = AsyncPerformanceProfiler()

        async def test_func():
            return 42

        result = asyncio.run(profiler.profile_async(test_func))

        assert result == 42
        assert "test_func" in profiler._timings

    def test_profile_async_with_args(self):
        """Test profile_async with arguments."""
        import asyncio

        profiler = AsyncPerformanceProfiler()

        async def test_func(x, y):
            return x + y

        result = asyncio.run(profiler.profile_async(test_func, "test_func", 2, 3))

        assert result == 5
        assert "test_func" in profiler._timings

    def test_profile_async_with_kwargs(self):
        """Test profile_async with keyword arguments."""
        import asyncio

        profiler = AsyncPerformanceProfiler()

        async def test_func(x, y=10):
            return x + y

        result = asyncio.run(profiler.profile_async(test_func, "test_func", 2, y=5))

        assert result == 7
        assert "test_func" in profiler._timings


class TestPerformanceProfilerExtended:
    """Extended tests for PerformanceProfiler."""

    def test_profile_async_method(self):
        """Test profile_async method."""
        import asyncio

        profiler = AsyncPerformanceProfiler()

        async def test_func():
            return 42

        result = asyncio.run(profiler.profile_async(test_func))

        assert result == 42
        assert "test_func" in profiler._timings


class TestAsyncPerformanceProfilerExtended:
    """Extended tests for AsyncPerformanceProfiler."""

    def test_clear_multiple_times(self):
        """Test clear can be called multiple times."""
        profiler = AsyncPerformanceProfiler()

        profiler._record_timing("func1", 0.1)
        profiler.clear()
        profiler.clear()  # Should not raise

        assert profiler._timings == {}

    def test_get_stats_empty_async(self):
        """Test get_stats on empty async profiler."""
        profiler = AsyncPerformanceProfiler()
        stats = profiler.get_stats()

        assert stats == {}
