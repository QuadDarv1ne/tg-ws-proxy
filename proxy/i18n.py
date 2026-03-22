"""
Internationalization (i18n) module for TG WS Proxy.

Provides translations for UI strings in multiple languages.
"""

from __future__ import annotations

import json
import os
from typing import Literal

# Supported languages
Language = Literal["ru", "en", "zh"]

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

    "zh": {
        # App title and header
        "app_title": "TG WS Proxy — 控制面板",
        "app_name": "TG WS Proxy",
        "app_description": "Telegram Desktop 的本地 SOCKS5 代理",

        # Status
        "status_ok": "运行正常",
        "status_degraded": "性能下降",
        "status_unhealthy": "无法工作",
        "status_online": "在线",
        "status_offline": "离线",

        # Statistics
        "stat_total_connections": "总连接数",
        "stat_ws_connections": "WebSocket",
        "stat_tcp_connections": "TCP 回退",
        "stat_pool_efficiency": "池效率",
        "stat_traffic": "流量",
        "stat_bytes_up": "上传",
        "stat_bytes_down": "下载",
        "stat_cpu_usage": "CPU",
        "stat_memory_usage": "内存",
        "stat_active_connections": "活动连接",
        "stat_errors": "错误",
        "stat_latency": "延迟",

        # DC Stats
        "dc_stats_title": "DC 统计",
        "dc_id": "DC",
        "dc_connections": "连接",
        "dc_latency": "延迟",
        "dc_error_rate": "错误率",
        "dc_optimal": "✓ 最佳",

        # Settings
        "settings_title": "设置",
        "settings_host": "主机",
        "settings_port": "端口",
        "settings_dc_ip": "DC IP 地址",
        "settings_verbose": "详细日志",
        "settings_save": "保存",
        "settings_cancel": "取消",
        "settings_restart": "重启",

        # Actions
        "action_refresh": "刷新",
        "action_export_csv": "导出 CSV",
        "action_export_json": "导出 JSON",
        "action_copy_config": "复制配置",
        "action_qr_code": "二维码",
        "action_logs": "日志",
        "action_settings": "设置",
        "action_exit": "退出",

        # Notifications
        "notify_update_available": "新版本可用：{version}",
        "notify_update_download": "下载",
        "notify_update_later": "稍后",
        "notify_copied": "已复制",
        "notify_saved": "已保存",
        "notify_error": "错误",

        # Live logs
        "logs_title": "实时日志",
        "logs_ws_success": "WS 连接",
        "logs_tcp_fallback": "TCP 回退",
        "logs_http_rejected": "HTTP 已拒绝",
        "logs_passthrough": "直通",

        # Health
        "health_status": "状态",
        "health_uptime": "运行时间",
        "health_last_check": "最后检查",

        # Time
        "time_just_now": "刚刚",
        "time_minutes_ago": "{min} 分钟前",
        "time_hours_ago": "{hours} 小时前",
        "time_days_ago": "{days} 天前",

        # Errors
        "error_load_stats": "加载统计失败",
        "error_connection": "连接错误",
        "error_timeout": "超时",
        "error_unknown": "未知错误",

        # PWA
        "pwa_install": "安装应用",
        "pwa_install_desc": "添加到主屏幕以快速访问",
        "pwa_dismiss": "关闭",
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
            "zh": "中文",
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
            return language  # type: ignore[no-any-return]
    except (OSError, json.JSONDecodeError):
        pass

    return DEFAULT_LANGUAGE
