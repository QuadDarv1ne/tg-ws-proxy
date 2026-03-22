"""
Plugin System for TG WS Proxy.

Provides extensibility through plugins:
- Connection hooks
- Traffic monitoring
- Custom authentication
- Event handlers

Author: Dupley Maxim Igorevich
© 2026 Dupley Maxim Igorevich. All rights reserved.
"""

from __future__ import annotations

import asyncio
import importlib
import logging
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger('tg-ws-plugins')


class PluginEvent(Enum):
    """Plugin events."""
    # Connection events
    CLIENT_CONNECT = auto()
    CLIENT_DISCONNECT = auto()
    CLIENT_AUTHENTICATED = auto()
    CLIENT_REJECTED = auto()

    # Traffic events
    BYTES_RECEIVED = auto()
    BYTES_SENT = auto()
    TRAFFIC_THRESHOLD = auto()

    # Connection pool events
    WS_CONNECTION_CREATED = auto()
    WS_CONNECTION_CLOSED = auto()
    TCP_FALLBACK_USED = auto()
    POOL_EXHAUSTED = auto()

    # Error events
    WS_ERROR = auto()
    CONNECTION_ERROR = auto()
    PROXY_ERROR = auto()

    # System events
    PROXY_STARTED = auto()
    PROXY_STOPPED = auto()
    CONFIG_RELOADED = auto()


@dataclass
class PluginContext:
    """Context passed to plugin handlers."""
    event: PluginEvent
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0

    # Connection info
    client_ip: str | None = None
    client_port: int | None = None
    dc_id: int | None = None

    # Traffic info
    bytes_count: int | None = None

    # Error info
    error: Exception | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        if self.timestamp == 0.0:
            try:
                self.timestamp = asyncio.get_event_loop().time()
            except RuntimeError:
                import time
                self.timestamp = time.time()


class Plugin(ABC):
    """Base plugin class."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Plugin name."""
        pass

    @property
    def version(self) -> str:
        """Plugin version."""
        return "1.0.0"

    @property
    def description(self) -> str:
        """Plugin description."""
        return ""

    @abstractmethod
    async def on_load(self) -> None:
        """Called when plugin is loaded."""
        pass

    @abstractmethod
    async def on_unload(self) -> None:
        """Called when plugin is unloaded."""
        pass

    @abstractmethod
    async def handle_event(self, context: PluginContext) -> None:
        """Handle plugin event."""
        pass


class PluginManager:
    """Plugin manager for loading and managing plugins."""

    def __init__(self, plugins_dir: str | None = None):
        self._plugins: dict[str, Plugin] = {}
        self._handlers: dict[PluginEvent, list[Callable[[PluginContext], None]]] = {}
        self._plugins_dir = plugins_dir
        self._enabled_events: set[PluginEvent] = set()

    def register_handler(
        self,
        event: PluginEvent,
        handler: Callable[[PluginContext], None],
    ) -> None:
        """Register event handler."""
        if event not in self._handlers:
            self._handlers[event] = []
        self._handlers[event].append(handler)
        self._enabled_events.add(event)
        log.debug("Registered handler for event: %s", event.name)

    def unregister_handler(
        self,
        event: PluginEvent,
        handler: Callable[[PluginContext], None],
    ) -> None:
        """Unregister event handler."""
        if event in self._handlers:
            self._handlers[event].remove(handler)
            if not self._handlers[event]:
                del self._handlers[event]
                self._enabled_events.discard(event)

    async def emit_event(self, context: PluginContext) -> None:
        """Emit event to all registered handlers."""
        if context.event not in self._enabled_events:
            return

        handlers = self._handlers.get(context.event, [])
        for handler in handlers:
            try:
                result = handler(context)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                log.error("Handler error for event %s: %s", context.event.name, e)

    async def load_plugin(self, plugin_path: str) -> bool:
        """Load plugin from file path."""
        try:
            path = Path(plugin_path)
            if not path.exists():
                log.error("Plugin not found: %s", plugin_path)
                return False

            # Add plugin directory to path
            plugin_dir = str(path.parent)
            if plugin_dir not in sys.path:
                sys.path.insert(0, plugin_dir)

            # Import plugin module
            module_name = path.stem
            module = importlib.import_module(module_name)

            # Find Plugin subclass
            plugin_class = None
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type) and
                    issubclass(attr, Plugin) and
                    attr is not Plugin):
                    plugin_class = attr
                    break

            if not plugin_class:
                log.error("No Plugin subclass found in %s", plugin_path)
                return False

            # Instantiate and initialize plugin
            plugin = plugin_class()
            await plugin.on_load()

            self._plugins[plugin.name] = plugin

            # Register plugin's event handlers
            if hasattr(plugin, 'get_handlers'):
                handlers = plugin.get_handlers()
                for event, handler in handlers.items():
                    self.register_handler(event, handler)

            log.info("Loaded plugin: %s v%s", plugin.name, plugin.version)
            return True

        except Exception as e:
            log.error("Failed to load plugin %s: %s", plugin_path, e)
            return False

    async def unload_plugin(self, plugin_name: str) -> bool:
        """Unload plugin by name."""
        if plugin_name not in self._plugins:
            return False

        plugin = self._plugins[plugin_name]
        await plugin.on_unload()

        # Remove plugin's handlers
        if hasattr(plugin, 'get_handlers'):
            handlers = plugin.get_handlers()
            for event, handler in handlers.items():
                self.unregister_handler(event, handler)

        del self._plugins[plugin_name]
        log.info("Unloaded plugin: %s", plugin_name)
        return True

    def get_plugin(self, name: str) -> Plugin | None:
        """Get plugin by name."""
        return self._plugins.get(name)

    def list_plugins(self) -> list[str]:
        """List loaded plugins."""
        return list(self._plugins.keys())

    def get_statistics(self) -> dict:
        """Get plugin statistics."""
        return {
            "loaded_plugins": len(self._plugins),
            "plugins": [
                {
                    "name": p.name,
                    "version": p.version,
                    "description": p.description,
                }
                for p in self._plugins.values()
            ],
            "enabled_events": len(self._enabled_events),
        }


# Built-in plugins

class LoggingPlugin(Plugin):
    """Plugin for logging connection events."""

    @property
    def name(self) -> str:
        return "logging"

    @property
    def description(self) -> str:
        return "Log connection events"

    async def handle_event(self, context: PluginContext) -> None:
        if context.event in (PluginEvent.CLIENT_CONNECT, PluginEvent.CLIENT_DISCONNECT):
            log.info(
                "Client %s: %s:%s",
                context.event.name.lower(),
                context.client_ip,
                context.client_port
            )
        elif context.event == PluginEvent.WS_ERROR and context.error:
            log.error("WebSocket error: %s", context.error_message)


class MetricsPlugin(Plugin):
    """Plugin for collecting metrics."""

    def __init__(self) -> None:
        self._metrics: dict[str, Any] = {
            "connections": 0,
            "disconnections": 0,
            "bytes_received": 0,
            "bytes_sent": 0,
            "errors": 0,
        }

    @property
    def name(self) -> str:
        return "metrics"

    @property
    def description(self) -> str:
        return "Collect proxy metrics"

    async def handle_event(self, context: PluginContext) -> None:
        if context.event == PluginEvent.CLIENT_CONNECT:
            self._metrics["connections"] += 1
        elif context.event == PluginEvent.CLIENT_DISCONNECT:
            self._metrics["disconnections"] += 1
        elif context.event == PluginEvent.BYTES_RECEIVED and context.bytes_count:
            self._metrics["bytes_received"] += context.bytes_count
        elif context.event == PluginEvent.BYTES_SENT and context.bytes_count:
            self._metrics["bytes_sent"] += context.bytes_count
        elif context.event in (PluginEvent.WS_ERROR, PluginEvent.CONNECTION_ERROR):
            self._metrics["errors"] += 1

    def get_metrics(self) -> dict:
        """Get collected metrics."""
        return self._metrics.copy()


class AutoReconnectPlugin(Plugin):
    """Plugin for automatic reconnection on errors."""

    def __init__(self, max_retries: int = 3, retry_delay: float = 1.0):
        self._max_retries = max_retries
        self._retry_delay = retry_delay
        self._retry_counts: dict[str, int] = {}

    @property
    def name(self) -> str:
        return "auto-reconnect"

    @property
    def description(self) -> str:
        return f"Auto-reconnect on errors (max {self._max_retries} retries)"

    async def handle_event(self, context: PluginContext) -> None:
        if context.event == PluginEvent.CONNECTION_ERROR:
            client_key = f"{context.client_ip}:{context.client_port}"
            retries = self._retry_counts.get(client_key, 0)

            if retries < self._max_retries:
                self._retry_counts[client_key] = retries + 1
                log.info(
                    "Auto-reconnect attempt %d/%d for %s",
                    retries + 1,
                    self._max_retries,
                    client_key
                )
                await asyncio.sleep(self._retry_delay * (retries + 1))
                # Trigger reconnection logic here
            else:
                log.warning(
                    "Max reconnection attempts reached for %s",
                    client_key
                )
                del self._retry_counts[client_key]
        elif context.event == PluginEvent.CLIENT_CONNECT:
            # Reset retry count on successful connection
            client_key = f"{context.client_ip}:{context.client_port}"
            self._retry_counts.pop(client_key, None)


# Global plugin manager
_plugin_manager: PluginManager | None = None


def get_plugin_manager() -> PluginManager:
    """Get or create global plugin manager."""
    global _plugin_manager
    if _plugin_manager is None:
        _plugin_manager = PluginManager()
    return _plugin_manager


def emit_event(event: PluginEvent, **kwargs: Any) -> None:
    """Emit event to plugin manager."""
    context = PluginContext(event=event, data=kwargs)
    pm = get_plugin_manager()
    asyncio.create_task(pm.emit_event(context))


__all__ = [
    'Plugin',
    'PluginManager',
    'PluginEvent',
    'PluginContext',
    'LoggingPlugin',
    'MetricsPlugin',
    'AutoReconnectPlugin',
    'get_plugin_manager',
    'emit_event',
]
