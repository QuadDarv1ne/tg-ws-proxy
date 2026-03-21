"""
GitHub Update Checker for TG WS Proxy.

Checks for new releases on GitHub and notifies users.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Callable

log = logging.getLogger('tg-ws-updater')

# Current version
CURRENT_VERSION = "2.10.0"
GITHUB_API_URL = "https://api.github.com/repos/Flowseal/tg-ws-proxy/releases/latest"

# Check interval (24 hours)
CHECK_INTERVAL = 24 * 60 * 60


class UpdateChecker:
    """Check for updates on GitHub."""

    def __init__(
        self,
        current_version: str = CURRENT_VERSION,
        check_interval: int = CHECK_INTERVAL,
        on_update_available: Callable[[str, str], None] | None = None,
    ) -> None:
        self.current_version = current_version
        self.check_interval = check_interval
        self.on_update_available = on_update_available
        self._last_check = 0.0
        self._latest_version: str | None = None
        self._release_info: dict | None = None
        self._check_task: asyncio.Task | None = None
        self._running = False

    def _parse_version(self, version: str) -> tuple[int, ...]:
        """Parse version string to tuple for comparison."""
        try:
            # Remove 'v' prefix if present
            version = version.lstrip('v')
            return tuple(int(x) for x in version.split('.'))
        except (ValueError, AttributeError):
            return (0,)

    def _is_newer(self, latest: str, current: str) -> bool:
        """Check if latest version is newer than current."""
        try:
            latest_tuple = self._parse_version(latest)
            current_tuple = self._parse_version(current)
            return latest_tuple > current_tuple
        except Exception:
            return False

    async def check_for_updates(self, force: bool = False) -> dict | None:
        """
        Check for updates on GitHub.

        Args:
            force: Force check even if recently checked

        Returns:
            Release info dict if update available, None otherwise
        """
        now = time.monotonic()

        # Skip if recently checked (unless forced)
        if not force and (now - self._last_check) < self.check_interval:
            log.debug("Skipping update check (recently checked)")
            return None

        self._last_check = now

        try:
            # Use asyncio for HTTP request
            import urllib.error
            import urllib.request

            loop = asyncio.get_event_loop()

            def fetch_release_info() -> dict | None:
                try:
                    req = urllib.request.Request(
                        GITHUB_API_URL,
                        headers={
                            'Accept': 'application/vnd.github.v3+json',
                            'User-Agent': f'TG-WS-Proxy/{self.current_version}'
                        }
                    )
                    with urllib.request.urlopen(req, timeout=10) as response:
                        return json.loads(response.read().decode())  # type: ignore[no-any-return]
                except Exception as e:
                    log.debug("Failed to fetch release info: %s", e)
                    return None

            release_info = await loop.run_in_executor(None, fetch_release_info)

            if not release_info:
                return None

            self._release_info = release_info
            latest_version = release_info.get('tag_name', '').lstrip('v')

            if not latest_version:
                return None

            self._latest_version = latest_version

            # Check if update is available
            if self._is_newer(latest_version, self.current_version):
                log.info(
                    "New version available: %s (current: %s)",
                    latest_version,
                    self.current_version
                )

                # Notify callback
                if self.on_update_available:
                    release_notes = release_info.get('body', 'No release notes')
                    self.on_update_available(latest_version, release_notes)

                return {
                    'current_version': self.current_version,
                    'latest_version': latest_version,
                    'release_url': release_info.get('html_url', ''),
                    'release_notes': release_notes,
                    'published_at': release_info.get('published_at', ''),
                }
            else:
                log.debug("Already on latest version: %s", latest_version)
                return None

        except Exception as e:
            log.error("Update check failed: %s", e)
            return None

    async def _check_loop(self) -> None:
        """Background loop for periodic checks."""
        log.info("Update checker started (interval: %d hours)", self.check_interval // 3600)

        while self._running:
            try:
                await asyncio.sleep(self.check_interval)
                await self.check_for_updates()
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error("Update checker error: %s", e)

        log.info("Update checker stopped")

    def start(self) -> None:
        """Start background update checker."""
        if self._running:
            log.warning("Update checker already running")
            return

        self._running = True

        try:
            self._check_task = asyncio.create_task(self._check_loop())
        except Exception as e:
            log.warning("Failed to start update checker: %s", e)
            self._running = False

    def stop(self) -> None:
        """Stop background update checker."""
        self._running = False
        if self._check_task:
            self._check_task.cancel()
            self._check_task = None

    def get_latest_version(self) -> str | None:
        """Get the latest known version."""
        return self._latest_version

    def get_release_info(self) -> dict | None:
        """Get the latest release info."""
        return self._release_info


# Global update checker instance
_update_checker: UpdateChecker | None = None


def get_update_checker() -> UpdateChecker:
    """Get or create global update checker."""
    global _update_checker
    if _update_checker is None:
        _update_checker = UpdateChecker()
    return _update_checker


async def check_for_updates(force: bool = False) -> dict | None:
    """Check for updates (convenience function)."""
    return await get_update_checker().check_for_updates(force=force)


def start_update_checker(on_update_available: Callable[[str, str], None] | None = None) -> None:
    """Start background update checker."""
    checker = get_update_checker()
    if on_update_available:
        checker.on_update_available = on_update_available
    checker.start()


def stop_update_checker() -> None:
    """Stop background update checker."""
    get_update_checker().stop()
