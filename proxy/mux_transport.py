"""
Connection Multiplexing for TG WS Proxy.

Implements connection multiplexing for improved performance:
- Multiple logical streams over single TCP connection
- Reduces connection overhead and latency
- Better resource utilization
- Connection pooling with smart reuse

Author: Dupley Maxim Igorevich
© 2026 Dupley Maxim Igorevich. All rights reserved.
"""

from __future__ import annotations

import asyncio
import logging
import struct
import time
from dataclasses import dataclass, field

log = logging.getLogger('tg-ws-mux')


@dataclass
class MuxStream:
    """Multiplexed stream."""
    stream_id: int
    created_at: float = field(default_factory=time.monotonic)
    last_activity: float = field(default_factory=time.monotonic)
    bytes_sent: int = 0
    bytes_received: int = 0
    state: str = 'open'  # open, half-closed, closed
    receive_buffer: bytearray = field(default_factory=bytearray)
    receive_event: asyncio.Event = field(default_factory=asyncio.Event)


class ConnectionMuxer:
    """
    Connection Multiplexer.

    Allows multiple logical streams over a single TCP connection.
    Reduces connection establishment overhead.

    Frame format:
    - Stream ID (4 bytes, big-endian)
    - Length (4 bytes, big-endian)
    - Data (variable)
    """

    # Special stream IDs
    CONTROL_STREAM_ID = 0
    MAX_STREAM_ID = 0x7FFFFFFF

    # Frame overhead
    FRAME_HEADER_SIZE = 8  # 4 bytes stream_id + 4 bytes length

    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        max_streams: int = 100,
    ):
        """
        Initialize multiplexer.

        Args:
            reader: Underlying stream reader
            writer: Underlying stream writer
            max_streams: Maximum concurrent streams
        """
        self.reader = reader
        self.writer = writer
        self.max_streams = max_streams

        # Stream management
        self._streams: dict[int, MuxStream] = {}
        self._next_stream_id = 1
        self._stream_lock = asyncio.Lock()

        # Receive queue for incoming frames
        self._receive_queue: asyncio.Queue[tuple[int, bytes]] = asyncio.Queue()

        # Background receive task
        self._receive_task: asyncio.Task | None = None
        self._running = False

        # Stats
        self.frames_sent = 0
        self.frames_received = 0
        self.bytes_overhead = 0

    async def start(self) -> None:
        """Start multiplexer background tasks."""
        self._running = True
        self._receive_task = asyncio.create_task(self._receive_loop())
        log.info("Connection muxer started (max_streams=%d)", self.max_streams)

    async def stop(self) -> None:
        """Stop multiplexer and close all streams."""
        self._running = False

        # Cancel receive task
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass

        # Close all streams
        async with self._stream_lock:
            for stream in self._streams.values():
                stream.state = 'closed'
                stream.receive_event.set()
            self._streams.clear()

        log.info("Connection muxer stopped")

    async def _receive_loop(self) -> None:
        """Background task to receive and demultiplex frames."""
        try:
            while self._running:
                # Read frame header
                header = await self.reader.readexactly(self.FRAME_HEADER_SIZE)
                stream_id, length = struct.unpack('!II', header)

                # Read frame data
                if length > 0:
                    data = await self.reader.readexactly(length)
                else:
                    data = b''

                self.frames_received += 1
                self.bytes_overhead += self.FRAME_HEADER_SIZE

                # Update stream
                async with self._stream_lock:
                    if stream_id in self._streams:
                        stream = self._streams[stream_id]
                        stream.last_activity = time.monotonic()
                        stream.bytes_received += length

                        if data:
                            stream.receive_buffer.extend(data)
                            stream.receive_event.set()

                # Queue for processing
                await self._receive_queue.put((stream_id, data))

        except asyncio.CancelledError:
            pass
        except asyncio.IncompleteReadError:
            log.debug("Mux receive: connection closed")
        except Exception as e:
            log.error("Mux receive error: %s", e)

    async def create_stream(self) -> int:
        """
        Create new multiplexed stream.

        Returns:
            Stream ID
        """
        async with self._stream_lock:
            if len(self._streams) >= self.max_streams:
                raise RuntimeError(f"Maximum streams ({self.max_streams}) reached")

            stream_id = self._next_stream_id
            self._next_stream_id = (self._next_stream_id + 2) & self.MAX_STREAM_ID
            if self._next_stream_id == 0:
                self._next_stream_id = 1

            stream = MuxStream(stream_id=stream_id)
            self._streams[stream_id] = stream

            log.debug("Mux stream created: %d", stream_id)
            return stream_id

    async def send_data(self, stream_id: int, data: bytes) -> bool:
        """
        Send data on a stream.

        Args:
            stream_id: Stream ID
            data: Data to send

        Returns:
            True if sent successfully
        """
        if not self._running:
            return False

        try:
            # Build frame
            header = struct.pack('!II', stream_id, len(data))
            frame = header + data

            self.writer.write(frame)
            await self.writer.drain()

            self.frames_sent += 1
            self.bytes_overhead += self.FRAME_HEADER_SIZE

            # Update stream stats
            async with self._stream_lock:
                if stream_id in self._streams:
                    self._streams[stream_id].bytes_sent += len(data)
                    self._streams[stream_id].last_activity = time.monotonic()

            return True

        except Exception as e:
            log.error("Mux send error: %s", e)
            return False

    async def recv_data(
        self,
        stream_id: int,
        max_size: int = 65536,
        timeout: float | None = None
    ) -> bytes | None:
        """
        Receive data from a stream.

        Args:
            stream_id: Stream ID
            max_size: Maximum bytes to read
            timeout: Read timeout

        Returns:
            Data or None on timeout/close
        """
        async with self._stream_lock:
            if stream_id not in self._streams:
                return None
            stream = self._streams[stream_id]

        # Wait for data
        try:
            if timeout:
                await asyncio.wait_for(stream.receive_event.wait(), timeout)
            else:
                await stream.receive_event.wait()
        except asyncio.TimeoutError:
            return None

        # Read data
        async with self._stream_lock:
            if not stream.receive_buffer:
                return None

            data = bytes(stream.receive_buffer[:max_size])
            del stream.receive_buffer[:max_size]

            # Clear event if buffer empty
            if not stream.receive_buffer:
                stream.receive_event.clear()

            return data

    async def close_stream(self, stream_id: int) -> None:
        """Close a stream."""
        async with self._stream_lock:
            if stream_id in self._streams:
                self._streams[stream_id].state = 'closed'
                self._streams[stream_id].receive_event.set()
                del self._streams[stream_id]

        log.debug("Mux stream closed: %d", stream_id)

    def get_stream_ids(self) -> list[int]:
        """Get list of active stream IDs."""
        return list(self._streams.keys())

    def get_stats(self) -> dict:
        """Get multiplexer statistics."""
        return {
            'running': self._running,
            'active_streams': len(self._streams),
            'max_streams': self.max_streams,
            'frames_sent': self.frames_sent,
            'frames_received': self.frames_received,
            'bytes_overhead': self.bytes_overhead,
            'streams': [
                {
                    'id': s.stream_id,
                    'state': s.state,
                    'bytes_sent': s.bytes_sent,
                    'bytes_received': s.bytes_received,
                    'age': time.monotonic() - s.created_at,
                }
                for s in self._streams.values()
            ]
        }


class MuxTransport:
    """
    Multiplexed Transport for Telegram proxy.

    Wraps existing connection with multiplexing support.
    """

    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        max_streams: int = 100,
    ):
        """
        Initialize mux transport.

        Args:
            reader: Underlying reader
            writer: Underlying writer
            max_streams: Maximum concurrent streams
        """
        self.reader = reader
        self.writer = writer
        self.max_streams = max_streams

        self._mux: ConnectionMuxer | None = None
        self._stream_id: int | None = None

    async def connect(self) -> bool:
        """Initialize multiplexer."""
        try:
            self._mux = ConnectionMuxer(
                reader=self.reader,
                writer=self.writer,
                max_streams=self.max_streams
            )

            await self._mux.start()

            # Create default stream for this transport
            self._stream_id = await self._mux.create_stream()

            log.info("Mux transport initialized (stream=%d)", self._stream_id)
            return True

        except Exception as e:
            log.error("Mux transport connect error: %s", e)
            return False

    async def send(self, data: bytes) -> bool:
        """Send data over muxed stream."""
        if not self._mux or self._stream_id is None:
            return False

        return await self._mux.send_data(self._stream_id, data)

    async def recv(
        self,
        max_size: int = 65536,
        timeout: float | None = None
    ) -> bytes | None:
        """Receive data from muxed stream."""
        if not self._mux or self._stream_id is None:
            return None

        return await self._mux.recv_data(self._stream_id, max_size, timeout)

    async def close(self) -> None:
        """Close mux transport."""
        if self._mux:
            if self._stream_id is not None:
                await self._mux.close_stream(self._stream_id)
            await self._mux.stop()
            self._mux = None
            self._stream_id = None

    def get_stats(self) -> dict:
        """Get transport statistics."""
        if not self._mux:
            return {'connected': False}

        stats = self._mux.get_stats()
        stats['current_stream'] = self._stream_id
        stats['connected'] = True
        return stats


class MuxConnectionPool:
    """
    Pool of multiplexed connections.

    Manages multiple underlying connections with multiplexing.
    """

    def __init__(
        self,
        host: str,
        port: int,
        max_connections: int = 4,
        max_streams_per_conn: int = 50,
    ):
        """
        Initialize mux pool.

        Args:
            host: Target host
            port: Target port
            max_connections: Maximum underlying connections
            max_streams_per_conn: Maximum streams per connection
        """
        self.host = host
        self.port = port
        self.max_connections = max_connections
        self.max_streams_per_conn = max_streams_per_conn

        self._connections: list[MuxTransport] = []
        self._connection_index = 0
        self._lock = asyncio.Lock()

        # Stats
        self.connections_created = 0
        self.streams_created = 0

    async def add_connection(self) -> MuxTransport | None:
        """Add new connection to pool."""
        async with self._lock:
            if len(self._connections) >= self.max_connections:
                log.warning("Max connections reached")
                return None

            try:
                reader, writer = await asyncio.open_connection(
                    self.host,
                    self.port
                )

                mux = MuxTransport(
                    reader=reader,
                    writer=writer,
                    max_streams=self.max_streams_per_conn
                )

                if await mux.connect():
                    self._connections.append(mux)
                    self.connections_created += 1
                    log.info("Mux pool: added connection %d", len(self._connections))
                    return mux

            except Exception as e:
                log.error("Failed to add mux connection: %s", e)

            return None

    async def get_transport(self) -> MuxTransport | None:
        """
        Get available transport from pool.

        Uses round-robin selection.
        """
        async with self._lock:
            if not self._connections:
                # Create first connection
                return await self.add_connection()

            # Round-robin selection
            self._connection_index = (self._connection_index + 1) % len(self._connections)
            return self._connections[self._connection_index]

    async def close_all(self) -> None:
        """Close all connections in pool."""
        async with self._lock:
            for mux in self._connections:
                await mux.close()
            self._connections.clear()

        log.info("Mux pool: all connections closed")

    def get_stats(self) -> dict:
        """Get pool statistics."""
        return {
            'pool_size': len(self._connections),
            'max_connections': self.max_connections,
            'connections_created': self.connections_created,
            'connections': [
                {
                    'idx': i,
                    'active': i == self._connection_index,
                    'stats': mux.get_stats()
                }
                for i, mux in enumerate(self._connections)
            ]
        }


async def create_muxed_connection(
    host: str,
    port: int,
    max_streams: int = 100
) -> MuxTransport | None:
    """
    Create multiplexed connection.

    Args:
        host: Target host
        port: Target port
        max_streams: Maximum streams

    Returns:
        MuxTransport instance or None
    """
    try:
        reader, writer = await asyncio.open_connection(host, port)

        mux = MuxTransport(reader, writer, max_streams)

        if await mux.connect():
            return mux

        await mux.close()

    except Exception as e:
        log.error("Failed to create mux connection: %s", e)

    return None


async def create_mux_pool(
    host: str,
    port: int,
    max_connections: int = 4,
    max_streams_per_conn: int = 50
) -> MuxConnectionPool:
    """
    Create multiplexed connection pool.

    Args:
        host: Target host
        port: Target port
        max_connections: Maximum connections
        max_streams_per_conn: Streams per connection

    Returns:
        MuxConnectionPool instance
    """
    pool = MuxConnectionPool(
        host=host,
        port=port,
        max_connections=max_connections,
        max_streams_per_conn=max_streams_per_conn
    )

    # Pre-create one connection
    await pool.add_connection()

    return pool
