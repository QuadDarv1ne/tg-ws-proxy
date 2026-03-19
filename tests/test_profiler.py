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
