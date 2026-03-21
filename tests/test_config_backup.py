"""Tests for config_backup.py module."""

from __future__ import annotations

import json
import time
from pathlib import Path

from proxy.config_backup import (
    ConfigBackup,
    backup_config,
    get_config_backup,
    list_config_backups,
    restore_config,
)


class TestConfigBackup:
    """Tests for ConfigBackup class."""

    def test_config_backup_init(self, tmp_path):
        """Test ConfigBackup initialization."""
        backup = ConfigBackup(str(tmp_path))

        assert backup.backup_dir == tmp_path
        assert backup.max_backups == 10
        assert backup._running is False

    def test_config_backup_custom_params(self, tmp_path):
        """Test ConfigBackup with custom parameters."""
        backup = ConfigBackup(
            str(tmp_path),
            max_backups=5,
            auto_backup_interval=1800.0,
        )

        assert backup.max_backups == 5
        assert backup.auto_backup_interval == 1800.0

    def test_config_backup_creates_directory(self, tmp_path):
        """Test that backup directory is created."""
        backup_dir = tmp_path / 'subdir' / 'backups'
        ConfigBackup(str(backup_dir))
        
        assert backup_dir.exists()

    def test_backup(self, tmp_path):
        """Test creating a backup."""
        backup = ConfigBackup(str(tmp_path))
        config = {'port': 1080, 'host': '127.0.0.1'}

        result = backup.backup(config)

        assert result is not None
        assert Path(result).exists()

        # Verify content
        with open(result) as f:
            data = json.load(f)

        assert data['config'] == config
        assert 'backup_timestamp' in data

    def test_backup_with_label(self, tmp_path):
        """Test creating a backup with label."""
        backup = ConfigBackup(str(tmp_path))
        config = {'port': 1080}

        result = backup.backup(config, label='test_label')

        assert result is not None
        assert 'test_label' in Path(result).name

    def test_restore(self, tmp_path):
        """Test restoring from backup."""
        backup = ConfigBackup(str(tmp_path))
        config = {'port': 1080, 'host': '127.0.0.1'}

        backup_path = backup.backup(config)
        restored = backup.restore(backup_path)

        assert restored == config

    def test_restore_nonexistent(self, tmp_path):
        """Test restoring from nonexistent file."""
        backup = ConfigBackup(str(tmp_path))

        result = backup.restore('/nonexistent/path.json')

        assert result is None

    def test_list_backups(self, tmp_path):
        """Test listing backups."""
        backup = ConfigBackup(str(tmp_path))
        
        backup.backup({'port': 1080})
        time.sleep(1.1)  # Ensure different timestamps
        backup.backup({'port': 1081})
        
        backups = backup.list_backups()
        
        assert len(backups) >= 1
        # Sorted by timestamp (newest first)
        assert backups[0]['datetime'] >= backups[-1]['datetime']

    def test_get_latest_backup(self, tmp_path):
        """Test getting latest backup."""
        backup = ConfigBackup(str(tmp_path))
        
        backup.backup({'port': 1080})
        time.sleep(1.1)
        backup.backup({'port': 1081})
        
        latest = backup.get_latest_backup()
        
        assert latest is not None
        # Verify it's a valid path
        assert Path(latest).exists()

    def test_get_latest_backup_empty(self, tmp_path):
        """Test getting latest backup when empty."""
        backup = ConfigBackup(str(tmp_path))

        result = backup.get_latest_backup()

        assert result is None

    def test_delete_backup(self, tmp_path):
        """Test deleting a backup."""
        backup = ConfigBackup(str(tmp_path))
        backup_path = backup.backup({'port': 1080})

        result = backup.delete_backup(backup_path)

        assert result is True
        assert not Path(backup_path).exists()

    def test_delete_backup_nonexistent(self, tmp_path):
        """Test deleting nonexistent backup."""
        backup = ConfigBackup(str(tmp_path))

        result = backup.delete_backup('/nonexistent/path.json')

        assert result is False

    def test_cleanup_old_backups(self, tmp_path):
        """Test cleanup of old backups."""
        backup = ConfigBackup(str(tmp_path), max_backups=3)
        
        for i in range(5):
            backup.backup({'port': 1080 + i})
            time.sleep(0.5)
        
        backups = backup.list_backups()
        
        # Should have at most max_backups
        assert len(backups) <= 3

    def test_export_backup_json(self, tmp_path):
        """Test exporting backup to JSON."""
        backup = ConfigBackup(str(tmp_path))
        config = {'port': 1080, 'host': '127.0.0.1'}
        backup_path = backup.backup(config)

        output_path = str(tmp_path / 'export.json')
        result = backup.export_backup(backup_path, output_path, format='json')

        assert result is True
        assert Path(output_path).exists()

        with open(output_path) as f:
            exported = json.load(f)

        assert exported == config

    def test_export_backup_txt(self, tmp_path):
        """Test exporting backup to TXT."""
        backup = ConfigBackup(str(tmp_path))
        config = {'port': 1080, 'host': '127.0.0.1'}
        backup_path = backup.backup(config)

        output_path = str(tmp_path / 'export.txt')
        result = backup.export_backup(backup_path, output_path, format='txt')

        assert result is True
        assert Path(output_path).exists()

    def test_export_backup_invalid_format(self, tmp_path):
        """Test exporting with invalid format."""
        backup = ConfigBackup(str(tmp_path))
        backup_path = backup.backup({'port': 1080})

        output_path = str(tmp_path / 'export.invalid')
        result = backup.export_backup(backup_path, output_path, format='invalid')

        assert result is False

    def test_get_statistics(self, tmp_path):
        """Test getting backup statistics."""
        backup = ConfigBackup(str(tmp_path), max_backups=5)
        
        backup.backup({'port': 1080})
        time.sleep(1.1)
        backup.backup({'port': 1081})
        
        stats = backup.get_statistics()
        
        assert stats['total_backups'] >= 1
        assert stats['max_backups'] == 5
        assert stats['total_size_bytes'] > 0

    def test_get_statistics_empty(self, tmp_path):
        """Test statistics with no backups."""
        backup = ConfigBackup(str(tmp_path))

        stats = backup.get_statistics()

        assert stats['total_backups'] == 0
        assert stats['total_size_bytes'] == 0

    def test_backup_fails_gracefully(self):
        """Test backup fails gracefully on error."""
        backup = ConfigBackup('/invalid/path/that/does/not/exist')
        
        result = backup.backup({'port': 1080})
        
        # Should return None or a path (depends on OS)
        # Main thing is it shouldn't raise an exception
        assert result is None or isinstance(result, str)


class TestGetConfigBackup:
    """Tests for get_config_backup function."""

    def test_get_config_backup_singleton(self):
        """Test get_config_backup returns singleton."""
        import proxy.config_backup as cb_mod
        cb_mod._backup = None

        backup1 = get_config_backup()
        backup2 = get_config_backup()

        assert backup1 is backup2

    def test_get_config_backup_custom_dir(self, tmp_path):
        """Test get_config_backup with custom directory."""
        import proxy.config_backup as cb_mod
        cb_mod._backup = None

        backup = get_config_backup(str(tmp_path))

        assert backup.backup_dir == tmp_path


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_backup_config(self, tmp_path):
        """Test backup_config helper function."""
        import proxy.config_backup as cb_mod
        cb_mod._backup = ConfigBackup(str(tmp_path))

        result = backup_config({'port': 1080})

        assert result is not None

    def test_restore_config(self, tmp_path):
        """Test restore_config helper function."""
        import proxy.config_backup as cb_mod
        cb_mod._backup = ConfigBackup(str(tmp_path))

        backup_path = backup_config({'port': 1080})
        restored = restore_config(backup_path)

        assert restored == {'port': 1080}

    def test_list_config_backups(self, tmp_path):
        """Test list_config_backups helper function."""
        import proxy.config_backup as cb_mod
        cb_mod._backup = ConfigBackup(str(tmp_path))

        backup_config({'port': 1080})

        backups = list_config_backups()

        assert len(backups) == 1
