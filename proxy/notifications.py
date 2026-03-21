"""
Notification System for TG WS Proxy.

Provides notifications via:
- Telegram Bot
- Discord Webhook
- Email
- Push notifications

Author: Dupley Maxim Igorevich
© 2026 Dupley Maxim Igorevich. All rights reserved.
"""

from __future__ import annotations

import asyncio
import logging
import smtplib
from dataclasses import dataclass, field
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import Enum, auto
from typing import Any

log = logging.getLogger('tg-notifications')


class NotificationPriority(Enum):
    """Notification priority levels."""
    LOW = auto()
    NORMAL = auto()
    HIGH = auto()
    CRITICAL = auto()


class NotificationType(Enum):
    """Notification types."""
    INFO = auto()
    WARNING = auto()
    ERROR = auto()
    DC_FAILOVER = auto()
    PERFORMANCE = auto()
    SECURITY = auto()
    SYSTEM = auto()


@dataclass
class Notification:
    """Notification data container."""
    type: NotificationType
    priority: NotificationPriority
    title: str
    message: str
    timestamp: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.timestamp == 0.0:
            try:
                self.timestamp = asyncio.get_event_loop().time()
            except RuntimeError:
                import time
                self.timestamp = time.time()

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            'type': self.type.name,
            'priority': self.priority.name,
            'title': self.title,
            'message': self.message,
            'timestamp': self.timestamp,
            'metadata': self.metadata,
        }


class TelegramBotNotifier:
    """Send notifications via Telegram Bot."""

    def __init__(self, bot_token: str, chat_id: str | int):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self._session = None

    async def send(self, notification: Notification) -> bool:
        """Send notification via Telegram."""
        try:
            import aiohttp

            # Format message
            priority_emoji = {
                NotificationPriority.LOW: 'ℹ️',
                NotificationPriority.NORMAL: '📢',
                NotificationPriority.HIGH: '⚠️',
                NotificationPriority.CRITICAL: '🚨',
            }

            message = (
                f"{priority_emoji.get(notification.priority, '📢')} "
                f"<b>{notification.title}</b>\n\n"
                f"<code>{notification.message}</code>"
            )

            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

            payload = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': 'HTML',
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=10) as response:
                    if response.status == 200:
                        log.debug("Telegram notification sent")
                        return True
                    else:
                        log.warning("Telegram API error: %d", response.status)
                        return False

        except ImportError:
            log.warning("aiohttp not installed, cannot send Telegram notification")
            return False
        except Exception as e:
            log.error("Telegram notification error: %s", e)
            return False


class DiscordWebhookNotifier:
    """Send notifications via Discord Webhook."""

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    async def send(self, notification: Notification) -> bool:
        """Send notification via Discord."""
        try:
            import aiohttp

            # Map priority to Discord color
            priority_colors = {
                NotificationPriority.LOW: 0x3498db,  # Blue
                NotificationPriority.NORMAL: 0x2ecc71,  # Green
                NotificationPriority.HIGH: 0xf39c12,  # Orange
                NotificationPriority.CRITICAL: 0xe74c3c,  # Red
            }

            # Map type to emoji
            type_emoji = {
                NotificationType.INFO: 'ℹ️',
                NotificationType.WARNING: '⚠️',
                NotificationType.ERROR: '❌',
                NotificationType.DC_FAILOVER: '🔄',
                NotificationType.PERFORMANCE: '📊',
                NotificationType.SECURITY: '🔒',
                NotificationType.SYSTEM: '⚙️',
            }

            embed = {
                'title': f"{type_emoji.get(notification.type, '📢')} {notification.title}",
                'description': f"```{notification.message}```",
                'color': priority_colors.get(notification.priority, 0x3498db),
                'footer': {
                    'text': 'TG WS Proxy',
                },
                'timestamp': asyncio.get_event_loop().time(),
            }

            if notification.metadata:
                fields = []
                for key, value in notification.metadata.items():
                    fields.append({
                        'name': str(key),
                        'value': f"```{value}```",
                        'inline': True,
                    })
                embed['fields'] = fields

            payload = {
                'embeds': [embed],
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.webhook_url,
                    json=payload,
                    timeout=10
                ) as response:
                    if response.status in (200, 204):
                        log.debug("Discord notification sent")
                        return True
                    else:
                        log.warning("Discord webhook error: %d", response.status)
                        return False

        except ImportError:
            log.warning("aiohttp not installed, cannot send Discord notification")
            return False
        except Exception as e:
            log.error("Discord notification error: %s", e)
            return False


class EmailNotifier:
    """Send notifications via Email."""

    def __init__(
        self,
        smtp_server: str,
        smtp_port: int,
        username: str,
        password: str,
        from_email: str,
        to_emails: list[str],
    ):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.from_email = from_email
        self.to_emails = to_emails

    def send(self, notification: Notification) -> bool:
        """Send notification via Email."""
        try:
            msg = MIMEMultipart()
            msg['From'] = self.from_email
            msg['To'] = ', '.join(self.to_emails)
            msg['Subject'] = f"[TG WS Proxy] {notification.title}"

            # Email body
            body = f"""
TG WS Proxy Notification

Type: {notification.type.name}
Priority: {notification.priority.name}
Title: {notification.title}

Message:
{notification.message}

Metadata:
{notification.metadata}
            """.strip()

            msg.attach(MIMEText(body, 'plain'))

            # Send email
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.username, self.password)
            server.send_message(msg)
            server.quit()

            log.debug("Email notification sent")
            return True

        except Exception as e:
            log.error("Email notification error: %s", e)
            return False


class NotificationManager:
    """Centralized notification management."""

    def __init__(self):
        self._notifiers: list[TelegramBotNotifier | DiscordWebhookNotifier | EmailNotifier] = []
        self._notification_history: list[Notification] = []
        self._max_history = 100
        self._rate_limit: dict[str, float] = {}  # type -> last_sent_time
        self._rate_limit_seconds = 60.0  # 1 minute between same type notifications

    def add_notifier(
        self,
        notifier: TelegramBotNotifier | DiscordWebhookNotifier | EmailNotifier
    ) -> None:
        """Add a notifier."""
        self._notifiers.append(notifier)

    def remove_notifier(
        self,
        notifier: TelegramBotNotifier | DiscordWebhookNotifier | EmailNotifier
    ) -> None:
        """Remove a notifier."""
        if notifier in self._notifiers:
            self._notifiers.remove(notifier)

    async def send(self, notification: Notification) -> bool:
        """Send notification to all configured notifiers."""
        # Check rate limit
        type_key = notification.type.name
        now = asyncio.get_event_loop().time()

        last_sent = self._rate_limit.get(type_key, 0)
        if now - last_sent < self._rate_limit_seconds:
            log.debug("Notification rate limited: %s", type_key)
            return False

        # Send to all notifiers
        tasks = []
        for notifier in self._notifiers:
            tasks.append(notifier.send(notification))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Update rate limit
        if any(r is True for r in results):
            self._rate_limit[type_key] = now

            # Add to history
            self._notification_history.append(notification)
            if len(self._notification_history) > self._max_history:
                self._notification_history = self._notification_history[-self._max_history:]

            return True

        return False

    async def send_info(self, title: str, message: str, **metadata: Any) -> bool:
        """Send info notification."""
        notification = Notification(
            type=NotificationType.INFO,
            priority=NotificationPriority.NORMAL,
            title=title,
            message=message,
            metadata=metadata,
        )
        return await self.send(notification)

    async def send_warning(self, title: str, message: str, **metadata: Any) -> bool:
        """Send warning notification."""
        notification = Notification(
            type=NotificationType.WARNING,
            priority=NotificationPriority.HIGH,
            title=title,
            message=message,
            metadata=metadata,
        )
        return await self.send(notification)

    async def send_error(self, title: str, message: str, **metadata: Any) -> bool:
        """Send error notification."""
        notification = Notification(
            type=NotificationType.ERROR,
            priority=NotificationPriority.CRITICAL,
            title=title,
            message=message,
            metadata=metadata,
        )
        return await self.send(notification)

    async def send_dc_failover(
        self,
        from_dc: int,
        to_dc: int,
        reason: str
    ) -> bool:
        """Send DC failover notification."""
        notification = Notification(
            type=NotificationType.DC_FAILOVER,
            priority=NotificationPriority.HIGH,
            title=f"DC Failover: DC{from_dc} → DC{to_dc}",
            message=reason,
            metadata={
                'from_dc': from_dc,
                'to_dc': to_dc,
            }
        )
        return await self.send(notification)

    def get_history(self, limit: int = 20) -> list[Notification]:
        """Get notification history."""
        return self._notification_history[-limit:]

    def get_statistics(self) -> dict:
        """Get notification statistics."""
        type_counts: dict[str, int] = {}
        priority_counts: dict[str, int] = {}

        for notification in self._notification_history:
            type_counts[notification.type.name] = type_counts.get(notification.type.name, 0) + 1
            priority_counts[notification.priority.name] = priority_counts.get(notification.priority.name, 0) + 1

        return {
            'total_sent': len(self._notification_history),
            'notifiers_count': len(self._notifiers),
            'by_type': type_counts,
            'by_priority': priority_counts,
        }


# Global notification manager
_notification_manager: NotificationManager | None = None


def get_notification_manager() -> NotificationManager:
    """Get or create global notification manager."""
    global _notification_manager
    if _notification_manager is None:
        _notification_manager = NotificationManager()
    return _notification_manager


def setup_telegram_notifications(bot_token: str, chat_id: str | int) -> None:
    """Setup Telegram notifications."""
    manager = get_notification_manager()
    manager.add_notifier(TelegramBotNotifier(bot_token, chat_id))
    log.info("Telegram notifications enabled")


def setup_discord_notifications(webhook_url: str) -> None:
    """Setup Discord notifications."""
    manager = get_notification_manager()
    manager.add_notifier(DiscordWebhookNotifier(webhook_url))
    log.info("Discord notifications enabled")


def setup_email_notifications(
    smtp_server: str,
    smtp_port: int,
    username: str,
    password: str,
    from_email: str,
    to_emails: list[str],
) -> None:
    """Setup Email notifications."""
    manager = get_notification_manager()
    manager.add_notifier(EmailNotifier(
        smtp_server, smtp_port, username, password, from_email, to_emails
    ))
    log.info("Email notifications enabled")


async def notify_info(title: str, message: str, **metadata: Any) -> bool:
    """Send info notification."""
    return await get_notification_manager().send_info(title, message, **metadata)


async def notify_warning(title: str, message: str, **metadata: Any) -> bool:
    """Send warning notification."""
    return await get_notification_manager().send_warning(title, message, **metadata)


async def notify_error(title: str, message: str, **metadata: Any) -> bool:
    """Send error notification."""
    return await get_notification_manager().send_error(title, message, **metadata)


async def notify_dc_failover(from_dc: int, to_dc: int, reason: str) -> bool:
    """Send DC failover notification."""
    return await get_notification_manager().send_dc_failover(from_dc, to_dc, reason)


__all__ = [
    'NotificationManager',
    'Notification',
    'NotificationType',
    'NotificationPriority',
    'TelegramBotNotifier',
    'DiscordWebhookNotifier',
    'EmailNotifier',
    'get_notification_manager',
    'setup_telegram_notifications',
    'setup_discord_notifications',
    'setup_email_notifications',
    'notify_info',
    'notify_warning',
    'notify_error',
    'notify_dc_failover',
]
