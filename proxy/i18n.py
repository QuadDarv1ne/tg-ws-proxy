"""
Internationalization (i18n) module for TG WS Proxy.

Provides translations for UI strings in multiple languages.
"""

from __future__ import annotations

import json
import os
from typing import Literal

# Supported languages
Language = Literal["ru", "en"]

# Default language
DEFAULT_LANGUAGE: Language = "ru"

# Translations dictionary
TRANSLATIONS: dict[Language, dict[str, str]] = {
    "ru": {
        # App title and header
        "app_title": "TG WS Proxy — Панель управления",
        "app_name": "TG WS Proxy",
        "app_description": "Локальный SOCKS5-прокси для Telegram Desktop",

        # Status
        "status_ok": "Работает нормально",
        "status_degraded": "Работает с проблемами",
        "status_unhealthy": "Не работает",
        "status_online": "Онлайн",
        "status_offline": "Офлайн",

        # Statistics
        "stat_total_connections": "Всего подключений",
        "stat_ws_connections": "WebSocket",
        "stat_tcp_connections": "TCP fallback",
        "stat_pool_efficiency": "Эффективность пула",
        "stat_traffic": "Трафик",
        "stat_bytes_up": "Исходящий",
        "stat_bytes_down": "Входящий",
        "stat_cpu_usage": "CPU",
        "stat_memory_usage": "Память",
        "stat_active_connections": "Активные",
        "stat_errors": "Ошибки",
        "stat_latency": "Задержка",

        # DC Stats
        "dc_stats_title": "Статистика по DC",
        "dc_id": "DC",
        "dc_connections": "Подключения",
        "dc_latency": "Задержка",
        "dc_error_rate": "Ошибки",
        "dc_optimal": "✓ Оптимальный",

        # Settings
        "settings_title": "Настройки",
        "settings_host": "Хост",
        "settings_port": "Порт",
        "settings_dc_ip": "DC IP адреса",
        "settings_verbose": "Подробный лог",
        "settings_save": "Сохранить",
        "settings_cancel": "Отмена",
        "settings_restart": "Перезапустить",

        # Actions
        "action_refresh": "Обновить",
        "action_export_csv": "Экспорт CSV",
        "action_export_json": "Экспорт JSON",
        "action_copy_config": "Копировать конфиг",
        "action_qr_code": "QR-код",
        "action_logs": "Логи",
        "action_settings": "Настройки",
        "action_exit": "Выход",

        # Notifications
        "notify_update_available": "Доступна новая версия: {version}",
        "notify_update_download": "Скачать",
        "notify_update_later": "Позже",
        "notify_copied": "Скопировано",
        "notify_saved": "Сохранено",
        "notify_error": "Ошибка",

        # Live logs
        "logs_title": "Live Логи",
        "logs_ws_success": "WS подключение",
        "logs_tcp_fallback": "TCP fallback",
        "logs_http_rejected": "HTTP отклонён",
        "logs_passthrough": "Прямой проход",

        # Health
        "health_status": "Статус",
        "health_uptime": "Время работы",
        "health_last_check": "Последняя проверка",

        # Time
        "time_just_now": "Только что",
        "time_minutes_ago": "{min} мин. назад",
        "time_hours_ago": "{hours} ч. назад",
        "time_days_ago": "{days} дн. назад",

        # Errors
        "error_load_stats": "Не удалось загрузить статистику",
        "error_connection": "Ошибка подключения",
        "error_timeout": "Превышено время ожидания",
        "error_unknown": "Неизвестная ошибка",

        # PWA
        "pwa_install": "Установить приложение",
        "pwa_install_desc": "Добавьте на домашний экран для быстрого доступа",
        "pwa_dismiss": "Отклонить",
    },

    "en": {
        # App title and header
        "app_title": "TG WS Proxy — Dashboard",
        "app_name": "TG WS Proxy",
        "app_description": "Local SOCKS5 proxy for Telegram Desktop",

        # Status
        "status_ok": "Running normally",
        "status_degraded": "Degraded performance",
        "status_unhealthy": "Not working",
        "status_online": "Online",
        "status_offline": "Offline",

        # Statistics
        "stat_total_connections": "Total Connections",
        "stat_ws_connections": "WebSocket",
        "stat_tcp_connections": "TCP Fallback",
        "stat_pool_efficiency": "Pool Efficiency",
        "stat_traffic": "Traffic",
        "stat_bytes_up": "Upload",
        "stat_bytes_down": "Download",
        "stat_cpu_usage": "CPU",
        "stat_memory_usage": "Memory",
        "stat_active_connections": "Active",
        "stat_errors": "Errors",
        "stat_latency": "Latency",

        # DC Stats
        "dc_stats_title": "DC Statistics",
        "dc_id": "DC",
        "dc_connections": "Connections",
        "dc_latency": "Latency",
        "dc_error_rate": "Errors",
        "dc_optimal": "✓ Optimal",

        # Settings
        "settings_title": "Settings",
        "settings_host": "Host",
        "settings_port": "Port",
        "settings_dc_ip": "DC IP Addresses",
        "settings_verbose": "Verbose Logging",
        "settings_save": "Save",
        "settings_cancel": "Cancel",
        "settings_restart": "Restart",

        # Actions
        "action_refresh": "Refresh",
        "action_export_csv": "Export CSV",
        "action_export_json": "Export JSON",
        "action_copy_config": "Copy Config",
        "action_qr_code": "QR Code",
        "action_logs": "Logs",
        "action_settings": "Settings",
        "action_exit": "Exit",

        # Notifications
        "notify_update_available": "New version available: {version}",
        "notify_update_download": "Download",
        "notify_update_later": "Later",
        "notify_copied": "Copied",
        "notify_saved": "Saved",
        "notify_error": "Error",

        # Live logs
        "logs_title": "Live Logs",
        "logs_ws_success": "WS Connection",
        "logs_tcp_fallback": "TCP Fallback",
        "logs_http_rejected": "HTTP Rejected",
        "logs_passthrough": "Passthrough",

        # Health
        "health_status": "Status",
        "health_uptime": "Uptime",
        "health_last_check": "Last Check",

        # Time
        "time_just_now": "Just now",
        "time_minutes_ago": "{min} min ago",
        "time_hours_ago": "{hours} hr ago",
        "time_days_ago": "{days} days ago",

        # Errors
        "error_load_stats": "Failed to load statistics",
        "error_connection": "Connection error",
        "error_timeout": "Timeout exceeded",
        "error_unknown": "Unknown error",

        # PWA
        "pwa_install": "Install App",
        "pwa_install_desc": "Add to home screen for quick access",
        "pwa_dismiss": "Dismiss",
    },
}


class I18n:
    """Internationalization manager."""

    def __init__(self, language: Language = DEFAULT_LANGUAGE) -> None:
        self.language = language
        self._translations = TRANSLATIONS.get(language, TRANSLATIONS[DEFAULT_LANGUAGE])

    def set_language(self, language: Language) -> None:
        """Change current language."""
        self.language = language
        self._translations = TRANSLATIONS.get(language, TRANSLATIONS[DEFAULT_LANGUAGE])

    def get(self, key: str, **kwargs: str | int) -> str:
        """
        Get translation for key.

        Args:
            key: Translation key
            **kwargs: Format arguments

        Returns:
            Translated string
        """
        text = self._translations.get(key, key)
        if kwargs:
            try:
                return text.format(**kwargs)
            except (KeyError, ValueError):
                return text
        return text

    def t(self, key: str, **kwargs: str | int) -> str:
        """Alias for get()."""
        return self.get(key, **kwargs)

    def get_available_languages(self) -> list[Language]:
        """Get list of available languages."""
        return list(TRANSLATIONS.keys())

    def get_language_name(self, language: Language) -> str:
        """Get human-readable language name."""
        names = {
            "ru": "Русский",
            "en": "English",
        }
        return names.get(language, language)


# Global i18n instance
_i18n: I18n | None = None


def get_i18n() -> I18n:
    """Get or create global i18n instance."""
    global _i18n
    if _i18n is None:
        _i18n = I18n()
    return _i18n


def set_language(language: Language) -> None:
    """Set global language."""
    get_i18n().set_language(language)


def t(key: str, **kwargs: str | int) -> str:
    """Translate key using global i18n instance."""
    return get_i18n().get(key, **kwargs)


def load_language_from_config(config_path: str | None = None) -> Language:
    """Load language from config file."""
    if not config_path or not os.path.exists(config_path):
        return DEFAULT_LANGUAGE

    try:
        with open(config_path) as f:
            config = json.load(f)
        language = config.get('language', DEFAULT_LANGUAGE)
        if language in TRANSLATIONS:
            set_language(language)
            return language
    except (OSError, json.JSONDecodeError):
        pass

    return DEFAULT_LANGUAGE
