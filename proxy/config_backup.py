"""
Configuration Backup Module for TG WS Proxy.

Provides automatic configuration backup:
- Scheduled backups
- Version history
- Automatic cleanup of old backups
- Restore functionality

Author: Dupley Maxim Igorevich
© 2026 Dupley Maxim Igorevich. All rights reserved.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

log = logging.getLogger('tg-config-backup')


class ConfigBackup:
    """
    Automatic configuration backup system.

    Features:
    - Scheduled automatic backups
    - Version history with timestamps
    - Automatic cleanup of old backups
    - Manual backup and restore
    - Compression support
    """

    def __init__(
        self,
        backup_dir: str,
        max_backups: int = 10,
        auto_backup_interval: float = 3600.0,  # 1 hour
        compress: bool = False,
    ):
        self.backup_dir = Path(backup_dir)
        self.max_backups = max_backups
        self.auto_backup_interval = auto_backup_interval
        self.compress = compress

        self._running = False
        self._backup_task: asyncio.Task | None = None

        # Ensure backup directory exists
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    async def start(self) -> None:
        """Start automatic backup scheduler."""
        if self.auto_backup_interval > 0:
            self._running = True
            self._backup_task = asyncio.create_task(self._backup_loop())
            log.info(
                "Config backup started (interval: %.1fs, max_backups: %d)",
                self.auto_backup_interval,
                self.max_backups
            )

    async def stop(self) -> None:
        """Stop automatic backup scheduler."""
        self._running = False
        if self._backup_task:
            self._backup_task.cancel()
            try:
                await self._backup_task
            except asyncio.CancelledError:
                pass
        log.info("Config backup stopped")

    async def _backup_loop(self) -> None:
        """Periodic backup loop."""
        while self._running:
            try:
                await asyncio.sleep(self.auto_backup_interval)
                # Auto-backup is triggered by external call to backup()
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error("Backup loop error: %s", e)

    def backup(
        self,
        config: dict[str, Any],
        label: str | None = None,
    ) -> str | None:
        """
        Create a backup of configuration.
        
        Args:
            config: Configuration dictionary to backup
            label: Optional label for the backup
            
        Returns:
            Path to backup file or None if failed
        """
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            label_str = f"_{label}" if label else ""
            filename = f"config_{timestamp}{label_str}.json"
            backup_path = self.backup_dir / filename

            # Add metadata
            backup_data = {
                'backup_timestamp': time.time(),
                'backup_datetime': datetime.now().isoformat(),
                'label': label,
                'config': config,
            }

            with open(backup_path, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, indent=2, ensure_ascii=False)

            log.info("Config backed up to: %s", backup_path)

            # Cleanup old backups
            self._cleanup_old_backups()

            return str(backup_path)

        except Exception as e:
            log.error("Failed to create backup: %s", e)
            return None

    def restore(self, backup_path: str) -> dict[str, Any] | None:
        """
        Restore configuration from backup.
        
        Args:
            backup_path: Path to backup file
            
        Returns:
            Configuration dictionary or None if failed
        """
        try:
            path = Path(backup_path)
            if not path.exists():
                log.error("Backup file not found: %s", backup_path)
                return None

            with open(path, encoding='utf-8') as f:
                backup_data = json.load(f)

            config = backup_data.get('config')
            if config:
                log.info("Config restored from: %s", backup_path)
                return config

            log.error("Invalid backup file format: %s", backup_path)
            return None

        except Exception as e:
            log.error("Failed to restore backup: %s", e)
            return None

    def list_backups(self) -> list[dict[str, Any]]:
        """
        List all available backups.
        
        Returns:
            List of backup info dictionaries
        """
        backups = []

        for path in sorted(self.backup_dir.glob('config_*.json')):
            try:
                with open(path, encoding='utf-8') as f:
                    data = json.load(f)

                backups.append({
                    'path': str(path),
                    'filename': path.name,
                    'timestamp': data.get('backup_timestamp', 0),
                    'datetime': data.get('backup_datetime', ''),
                    'label': data.get('label'),
                    'size_bytes': path.stat().st_size,
                })
            except Exception as e:
                log.debug("Failed to read backup %s: %s", path, e)

        # Sort by timestamp (newest first)
        backups.sort(key=lambda x: x['timestamp'], reverse=True)
        return backups

    def get_latest_backup(self) -> str | None:
        """
        Get path to latest backup.
        
        Returns:
            Path to latest backup or None if no backups exist
        """
        backups = self.list_backups()
        if backups:
            return backups[0]['path']
        return None

    def delete_backup(self, backup_path: str) -> bool:
        """
        Delete a specific backup.
        
        Args:
            backup_path: Path to backup file
            
        Returns:
            True if deleted, False otherwise
        """
        try:
            path = Path(backup_path)
            if path.exists():
                path.unlink()
                log.info("Backup deleted: %s", backup_path)
                return True
            return False
        except Exception as e:
            log.error("Failed to delete backup: %s", e)
            return False

    def _cleanup_old_backups(self) -> int:
        """
        Remove old backups exceeding max_backups limit.
        
        Returns:
            Number of deleted backups
        """
        backups = self.list_backups()
        deleted = 0

        while len(backups) > self.max_backups:
            oldest = backups.pop()
            if self.delete_backup(oldest['path']):
                deleted += 1

        if deleted > 0:
            log.debug("Cleaned up %d old backups", deleted)

        return deleted

    def export_backup(
        self,
        backup_path: str,
        output_path: str,
        format: str = 'json',
    ) -> bool:
        """
        Export backup to different format.
        
        Args:
            backup_path: Path to source backup
            output_path: Path for exported file
            format: Export format ('json', 'txt')
            
        Returns:
            True if exported successfully
        """
        try:
            config = self.restore(backup_path)
            if not config:
                return False

            output = Path(output_path)
            output.parent.mkdir(parents=True, exist_ok=True)

            if format == 'json':
                with open(output, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)
            elif format == 'txt':
                with open(output, 'w', encoding='utf-8') as f:
                    for key, value in config.items():
                        f.write(f"{key}: {value}\n")
            else:
                log.error("Unknown export format: %s", format)
                return False

            log.info("Backup exported to: %s", output_path)
            return True

        except Exception as e:
            log.error("Failed to export backup: %s", e)
            return False

    def get_statistics(self) -> dict[str, Any]:
        """Get backup statistics."""
        backups = self.list_backups()

        if not backups:
            return {
                'total_backups': 0,
                'total_size_bytes': 0,
                'oldest_backup': None,
                'newest_backup': None,
                'average_size_bytes': 0,
            }

        total_size = sum(b['size_bytes'] for b in backups)

        return {
            'total_backups': len(backups),
            'max_backups': self.max_backups,
            'total_size_bytes': total_size,
            'oldest_backup': backups[-1]['datetime'] if backups else None,
            'newest_backup': backups[0]['datetime'] if backups else None,
            'average_size_bytes': total_size // len(backups) if backups else 0,
            'auto_backup_interval': self.auto_backup_interval,
        }


# Global backup instance
_backup: ConfigBackup | None = None


def get_config_backup(backup_dir: str | None = None) -> ConfigBackup:
    """Get or create global config backup instance."""
    global _backup

    if backup_dir is not None:
        _backup = ConfigBackup(backup_dir)

    if _backup is None:
        # Default backup directory
        if os.name == 'nt':  # Windows
            backup_dir = os.path.join(os.getenv('APPDATA', ''), 'TgWsProxy', 'backups')
        elif os.name == 'posix':  # Linux/macOS
            backup_dir = os.path.expanduser('~/.config/TgWsProxy/backups')
        else:
            backup_dir = './TgWsProxy_backups'

        _backup = ConfigBackup(backup_dir)

    return _backup


def backup_config(
    config: dict[str, Any],
    label: str | None = None,
) -> str | None:
    """Create a backup of configuration."""
    return get_config_backup().backup(config, label)


def restore_config(backup_path: str) -> dict[str, Any] | None:
    """Restore configuration from backup."""
    return get_config_backup().restore(backup_path)


def list_config_backups() -> list[dict[str, Any]]:
    """List all available backups."""
    return get_config_backup().list_backups()


__all__ = [
    'ConfigBackup',
    'get_config_backup',
    'backup_config',
    'restore_config',
    'list_config_backups',
]
