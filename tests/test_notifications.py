"""Tests for notifications.py module."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from proxy.notifications import (
    DiscordWebhookNotifier,
    EmailNotifier,
    Notification,
    NotificationManager,
    NotificationPriority,
    NotificationType,
    TelegramBotNotifier,
    get_notification_manager,
)


class TestNotificationPriority:
    """Tests for NotificationPriority enum."""

    def test_priority_values(self):
        """Test priority values."""
        assert NotificationPriority.LOW.value == 1
        assert NotificationPriority.NORMAL.value == 2
        assert NotificationPriority.HIGH.value == 3
        assert NotificationPriority.CRITICAL.value == 4


class TestNotificationType:
    """Tests for NotificationType enum."""

    def test_type_values(self):
        """Test notification type values."""
        assert NotificationType.INFO.value == 1
        assert NotificationType.WARNING.value == 2
        assert NotificationType.ERROR.value == 3
        assert NotificationType.DC_FAILOVER.value == 4


class TestNotification:
    """Tests for Notification dataclass."""

    def test_notification_default(self):
        """Test default notification."""
        notification = Notification(
            type=NotificationType.INFO,
            priority=NotificationPriority.NORMAL,
            title="Test",
            message="Test message",
            timestamp=123.456,
        )

        assert notification.type == NotificationType.INFO
        assert notification.priority == NotificationPriority.NORMAL
        assert notification.title == "Test"
        assert notification.message == "Test message"
        assert notification.metadata == {}
        assert notification.timestamp == 123.456

    def test_notification_with_metadata(self):
        """Test notification with metadata."""
        notification = Notification(
            type=NotificationType.DC_FAILOVER,
            priority=NotificationPriority.HIGH,
            title="DC Failover",
            message="Switched from DC2 to DC4",
            timestamp=123.456,
            metadata={'from_dc': 2, 'to_dc': 4},
        )

        assert notification.metadata == {'from_dc': 2, 'to_dc': 4}

    def test_notification_to_dict(self):
        """Test notification to_dict method."""
        notification = Notification(
            type=NotificationType.ERROR,
            priority=NotificationPriority.CRITICAL,
            title="Error",
            message="Something went wrong",
            timestamp=123.456,
        )

        result = notification.to_dict()

        assert result['type'] == 'ERROR'
        assert result['priority'] == 'CRITICAL'
        assert result['title'] == 'Error'
        assert result['message'] == 'Something went wrong'


class TestTelegramBotNotifier:
    """Tests for TelegramBotNotifier class."""

    def test_telegram_notifier_init(self):
        """Test Telegram notifier initialization."""
        notifier = TelegramBotNotifier(
            bot_token='123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11',
            chat_id='123456789'
        )

        assert notifier.bot_token == '123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11'
        assert notifier.chat_id == '123456789'

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Requires aiohttp module")
    async def test_telegram_notifier_send_success(self):
        """Test successful Telegram notification."""
        notifier = TelegramBotNotifier('token', 'chat_id')

        notification = Notification(
            type=NotificationType.INFO,
            priority=NotificationPriority.NORMAL,
            title="Test",
            message="Test message",
            timestamp=123.456,
        )

        with patch('aiohttp.ClientSession') as mock_session:
            mock_response = MagicMock()
            mock_response.status = 200
            mock_context = MagicMock()
            mock_context.__aenter__.return_value = mock_response
            mock_session.return_value.post.return_value = mock_context

            result = await notifier.send(notification)

            assert result is True

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Requires aiohttp module")
    async def test_telegram_notifier_send_error(self):
        """Test Telegram notification with error."""
        notifier = TelegramBotNotifier('token', 'chat_id')

        notification = Notification(
            type=NotificationType.INFO,
            priority=NotificationPriority.NORMAL,
            title="Test",
            message="Test message",
            timestamp=123.456,
        )

        with patch('aiohttp.ClientSession') as mock_session:
            mock_response = MagicMock()
            mock_response.status = 400
            mock_context = MagicMock()
            mock_context.__aenter__.return_value = mock_response
            mock_session.return_value.post.return_value = mock_context

            result = await notifier.send(notification)

            assert result is False


class TestDiscordWebhookNotifier:
    """Tests for DiscordWebhookNotifier class."""

    def test_discord_notifier_init(self):
        """Test Discord notifier initialization."""
        notifier = DiscordWebhookNotifier('https://discord.com/api/webhooks/123/abc')

        assert notifier.webhook_url == 'https://discord.com/api/webhooks/123/abc'

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Requires aiohttp module")
    async def test_discord_notifier_send_success(self):
        """Test successful Discord notification."""
        notifier = DiscordWebhookNotifier('webhook_url')

        notification = Notification(
            type=NotificationType.INFO,
            priority=NotificationPriority.NORMAL,
            title="Test",
            message="Test message",
            timestamp=123.456,
        )

        with patch('aiohttp.ClientSession') as mock_session:
            mock_response = MagicMock()
            mock_response.status = 204
            mock_context = MagicMock()
            mock_context.__aenter__.return_value = mock_response
            mock_session.return_value.post.return_value = mock_context

            result = await notifier.send(notification)

            assert result is True

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Requires aiohttp module")
    async def test_discord_notifier_send_with_metadata(self):
        """Test Discord notification with metadata."""
        notifier = DiscordWebhookNotifier('webhook_url')

        notification = Notification(
            type=NotificationType.DC_FAILOVER,
            priority=NotificationPriority.HIGH,
            title="DC Failover",
            message="Switched DC",
            timestamp=123.456,
            metadata={'from_dc': 2, 'to_dc': 4},
        )

        with patch('aiohttp.ClientSession') as mock_session:
            mock_response = MagicMock()
            mock_response.status = 200
            mock_context = MagicMock()
            mock_context.__aenter__.return_value = mock_response
            mock_session.return_value.post.return_value = mock_context

            result = await notifier.send(notification)

            assert result is True


class TestEmailNotifier:
    """Tests for EmailNotifier class."""

    def test_email_notifier_init(self):
        """Test Email notifier initialization."""
        notifier = EmailNotifier(
            smtp_server='smtp.example.com',
            smtp_port=587,
            username='user@example.com',
            password='secret',
            from_email='alerts@example.com',
            to_emails=['admin@example.com'],
        )

        assert notifier.smtp_server == 'smtp.example.com'
        assert notifier.smtp_port == 587
        assert notifier.username == 'user@example.com'

    def test_email_notifier_send_success(self):
        """Test successful Email notification."""
        notifier = EmailNotifier(
            smtp_server='smtp.example.com',
            smtp_port=587,
            username='user',
            password='pass',
            from_email='from@example.com',
            to_emails=['to@example.com'],
        )

        notification = Notification(
            type=NotificationType.INFO,
            priority=NotificationPriority.NORMAL,
            title="Test",
            message="Test message",
            timestamp=123.456,
        )

        with patch('smtplib.SMTP') as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value = mock_server

            result = notifier.send(notification)

            assert result is True
            assert mock_server.send_message.called

    def test_email_notifier_send_error(self):
        """Test Email notification with error."""
        notifier = EmailNotifier(
            smtp_server='smtp.example.com',
            smtp_port=587,
            username='user',
            password='pass',
            from_email='from@example.com',
            to_emails=['to@example.com'],
        )

        notification = Notification(
            type=NotificationType.INFO,
            priority=NotificationPriority.NORMAL,
            title="Test",
            message="Test message",
            timestamp=123.456,
        )

        with patch('smtplib.SMTP', side_effect=Exception('SMTP error')):
            result = notifier.send(notification)

            assert result is False


class TestNotificationManager:
    """Tests for NotificationManager class."""

    def test_notification_manager_init(self):
        """Test notification manager initialization."""
        manager = NotificationManager()

        assert manager._notifiers == []
        assert manager._notification_history == []
        assert manager._max_history == 100

    def test_notification_manager_add_notifier(self):
        """Test adding notifier."""
        manager = NotificationManager()
        notifier = MagicMock()

        manager.add_notifier(notifier)

        assert notifier in manager._notifiers

    def test_notification_manager_remove_notifier(self):
        """Test removing notifier."""
        manager = NotificationManager()
        notifier = MagicMock()
        manager.add_notifier(notifier)

        manager.remove_notifier(notifier)

        assert notifier not in manager._notifiers

    def test_notification_manager_remove_nonexistent_notifier(self):
        """Test removing non-existent notifier."""
        manager = NotificationManager()
        notifier = MagicMock()

        # Should not raise
        manager.remove_notifier(notifier)

    @pytest.mark.asyncio
    async def test_notification_manager_send(self):
        """Test sending notification."""
        manager = NotificationManager()
        notifier = AsyncMock()
        notifier.send.return_value = True
        manager.add_notifier(notifier)

        notification = Notification(
            type=NotificationType.INFO,
            priority=NotificationPriority.NORMAL,
            title="Test",
            message="Test message",
        )

        result = await manager.send(notification)

        assert result is True
        assert len(manager._notification_history) == 1

    @pytest.mark.asyncio
    async def test_notification_manager_send_rate_limited(self):
        """Test rate limiting."""
        manager = NotificationManager()
        manager._rate_limit_seconds = 60.0

        notifier = AsyncMock()
        notifier.send.return_value = True
        manager.add_notifier(notifier)

        notification1 = Notification(
            type=NotificationType.INFO,
            priority=NotificationPriority.NORMAL,
            title="Test 1",
            message="Message 1",
        )

        # First notification should succeed
        await manager.send(notification1)

        # Second should be rate limited
        notification2 = Notification(
            type=NotificationType.INFO,
            priority=NotificationPriority.NORMAL,
            title="Test 2",
            message="Message 2",
        )

        result = await manager.send(notification2)

        assert result is False

    @pytest.mark.asyncio
    async def test_notification_manager_send_info(self):
        """Test send_info helper method."""
        manager = NotificationManager()
        notifier = AsyncMock()
        notifier.send.return_value = True
        manager.add_notifier(notifier)

        result = await manager.send_info("Title", "Message")

        assert result is True

    @pytest.mark.asyncio
    async def test_notification_manager_send_warning(self):
        """Test send_warning helper method."""
        manager = NotificationManager()
        notifier = AsyncMock()
        notifier.send.return_value = True
        manager.add_notifier(notifier)

        result = await manager.send_warning("Title", "Message")

        assert result is True

    @pytest.mark.asyncio
    async def test_notification_manager_send_error(self):
        """Test send_error helper method."""
        manager = NotificationManager()
        notifier = AsyncMock()
        notifier.send.return_value = True
        manager.add_notifier(notifier)

        result = await manager.send_error("Title", "Message")

        assert result is True

    @pytest.mark.asyncio
    async def test_notification_manager_send_dc_failover(self):
        """Test send_dc_failover helper method."""
        manager = NotificationManager()
        notifier = AsyncMock()
        notifier.send.return_value = True
        manager.add_notifier(notifier)

        result = await manager.send_dc_failover(2, 4, "High latency")

        assert result is True

    def test_notification_manager_get_history(self):
        """Test getting notification history."""
        manager = NotificationManager()

        # Add notifications to history directly
        for i in range(5):
            manager._notification_history.append(
                Notification(
                    type=NotificationType.INFO,
                    priority=NotificationPriority.NORMAL,
                    title=f"Test {i}",
                    message=f"Message {i}",
                    timestamp=float(i),
                )
            )

        history = manager.get_history()

        assert len(history) == 5

    def test_notification_manager_get_history_limit(self):
        """Test getting limited notification history."""
        manager = NotificationManager()

        for i in range(10):
            manager._notification_history.append(
                Notification(
                    type=NotificationType.INFO,
                    priority=NotificationPriority.NORMAL,
                    title=f"Test {i}",
                    message=f"Message {i}",
                    timestamp=float(i),
                )
            )

        history = manager.get_history(limit=5)

        assert len(history) == 5

    def test_notification_manager_get_statistics(self):
        """Test getting notification statistics."""
        manager = NotificationManager()

        # Add notifications
        manager._notification_history.append(
            Notification(
                type=NotificationType.INFO,
                priority=NotificationPriority.NORMAL,
                title="Test",
                message="Message",
                timestamp=1.0,
            )
        )
        manager._notification_history.append(
            Notification(
                type=NotificationType.ERROR,
                priority=NotificationPriority.CRITICAL,
                title="Error",
                message="Error message",
                timestamp=2.0,
            )
        )

        stats = manager.get_statistics()

        assert stats['total_sent'] == 2
        assert 'by_type' in stats
        assert 'by_priority' in stats


class TestGetNotificationManager:
    """Tests for get_notification_manager function."""

    def test_get_notification_manager_singleton(self):
        """Test get_notification_manager returns singleton."""
        manager1 = get_notification_manager()
        manager2 = get_notification_manager()

        assert manager1 is manager2

    def test_get_notification_manager_creates_new(self):
        """Test get_notification_manager creates new instance."""
        import proxy.notifications as notif_mod
        notif_mod._notification_manager = None

        manager = get_notification_manager()

        assert isinstance(manager, NotificationManager)
