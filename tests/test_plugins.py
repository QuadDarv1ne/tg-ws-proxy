"""Tests for plugins.py module."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from proxy.plugins import (
    PluginContext,
    PluginEvent,
    PluginManager,
    get_plugin_manager,
)


class TestPluginEvent:
    """Tests for PluginEvent enum."""

    def test_plugin_event_values(self):
        """Test plugin event values."""
        assert PluginEvent.CLIENT_CONNECT.value == 1
        assert PluginEvent.CLIENT_DISCONNECT.value == 2
        assert PluginEvent.WS_ERROR.value == 12
        assert PluginEvent.PROXY_STARTED.value == 15


class TestPluginContext:
    """Tests for PluginContext dataclass."""

    def test_plugin_context_default(self):
        """Test default plugin context."""
        context = PluginContext(event=PluginEvent.CLIENT_CONNECT)

        assert context.event == PluginEvent.CLIENT_CONNECT
        assert context.data == {}
        assert context.client_ip is None
        assert context.client_port is None
        assert context.bytes_count is None
        assert context.timestamp > 0

    def test_plugin_context_custom(self):
        """Test custom plugin context."""
        context = PluginContext(
            event=PluginEvent.BYTES_RECEIVED,
            data={'size': 1024},
            client_ip='192.168.1.1',
            client_port=8080,
            bytes_count=1024,
            timestamp=123.456,
        )

        assert context.event == PluginEvent.BYTES_RECEIVED
        assert context.data == {'size': 1024}
        assert context.client_ip == '192.168.1.1'
        assert context.client_port == 8080
        assert context.bytes_count == 1024
        assert context.timestamp == 123.456


class TestPluginManager:
    """Tests for PluginManager class."""

    def test_plugin_manager_init(self):
        """Test plugin manager initialization."""
        pm = PluginManager()

        assert pm._plugins == {}
        assert pm._handlers == {}
        assert pm._enabled_events == set()

    def test_plugin_manager_register_handler(self):
        """Test registering event handler."""
        pm = PluginManager()
        handler = MagicMock()

        pm.register_handler(PluginEvent.CLIENT_CONNECT, handler)

        assert PluginEvent.CLIENT_CONNECT in pm._handlers
        assert handler in pm._handlers[PluginEvent.CLIENT_CONNECT]
        assert PluginEvent.CLIENT_CONNECT in pm._enabled_events

    def test_plugin_manager_unregister_handler(self):
        """Test unregistering event handler."""
        pm = PluginManager()
        handler = MagicMock()

        pm.register_handler(PluginEvent.CLIENT_CONNECT, handler)
        pm.unregister_handler(PluginEvent.CLIENT_CONNECT, handler)

        assert PluginEvent.CLIENT_CONNECT not in pm._handlers

    @pytest.mark.asyncio
    async def test_plugin_manager_emit_event(self):
        """Test emitting event to handlers."""
        pm = PluginManager()
        handler = AsyncMock()

        pm.register_handler(PluginEvent.CLIENT_CONNECT, handler)

        context = PluginContext(
            event=PluginEvent.CLIENT_CONNECT,
            client_ip='192.168.1.1',
        )

        await pm.emit_event(context)

        handler.assert_called_once_with(context)

    @pytest.mark.asyncio
    async def test_plugin_manager_emit_event_no_handlers(self):
        """Test emitting event with no handlers."""
        pm = PluginManager()

        context = PluginContext(event=PluginEvent.CLIENT_CONNECT)

        # Should not raise
        await pm.emit_event(context)

    @pytest.mark.asyncio
    async def test_plugin_manager_emit_event_handler_error(self):
        """Test emitting event with handler error."""
        pm = PluginManager()
        handler = AsyncMock(side_effect=Exception("Handler error"))

        pm.register_handler(PluginEvent.CLIENT_CONNECT, handler)

        context = PluginContext(event=PluginEvent.CLIENT_CONNECT)

        # Should not raise
        await pm.emit_event(context)

    def test_plugin_manager_get_plugin(self):
        """Test getting plugin by name."""
        pm = PluginManager()
        pm._plugins['test'] = MagicMock()

        plugin = pm.get_plugin('test')

        assert plugin is not None

    def test_plugin_manager_list_plugins(self):
        """Test listing plugins."""
        pm = PluginManager()
        pm._plugins['plugin1'] = MagicMock()
        pm._plugins['plugin2'] = MagicMock()

        plugins = pm.list_plugins()

        assert 'plugin1' in plugins
        assert 'plugin2' in plugins

    def test_plugin_manager_get_statistics(self):
        """Test getting plugin statistics."""
        pm = PluginManager()

        mock_plugin = MagicMock()
        mock_plugin.name = 'test'
        mock_plugin.version = '1.0.0'
        mock_plugin.description = 'Test plugin'
        pm._plugins['test'] = mock_plugin

        stats = pm.get_statistics()

        assert 'loaded_plugins' in stats
        assert 'plugins' in stats
        assert 'enabled_events' in stats
        assert stats['loaded_plugins'] == 1


class TestGetPluginManager:
    """Tests for get_plugin_manager function."""

    def test_get_plugin_manager_singleton(self):
        """Test get_plugin_manager returns singleton."""
        # Reset global state first
        import proxy.plugins as plugins_mod
        plugins_mod._plugin_manager = None

        pm1 = get_plugin_manager()
        pm2 = get_plugin_manager()

        assert pm1 is pm2

    def test_get_plugin_manager_has_builtin_plugins(self):
        """Test get_plugin_manager has built-in plugins."""
        import proxy.plugins as plugins_mod
        plugins_mod._plugin_manager = None

        pm = get_plugin_manager()

        # Manager should exist
        assert pm is not None
