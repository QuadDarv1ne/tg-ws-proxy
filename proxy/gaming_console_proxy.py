"""
Gaming Console Proxy Support.

Provides proxy configuration for gaming consoles:
- PS4/PS5 proxy setup
- Xbox proxy configuration
- Nintendo Switch proxy
- LAN proxy sharing
- Port forwarding automation

Author: Dupley Maxim Igorevich
© 2026 Dupley Maxim Igorevich. All rights reserved.
"""

from __future__ import annotations

import asyncio
import logging
import socket
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

log = logging.getLogger('tg-ws-gaming-proxy')


class ConsoleType(Enum):
    """Gaming console types."""
    PS4 = auto()
    PS5 = auto()
    XBOX_ONE = auto()
    XBOX_SERIES = auto()
    NINTENDO_SWITCH = auto()


@dataclass
class ConsoleProxyConfig:
    """Gaming console proxy configuration."""
    console_type: ConsoleType
    proxy_host: str = "0.0.0.0"  # Listen on all interfaces for LAN access
    proxy_port: int = 1080
    enable_upnp: bool = True  # Automatic port forwarding
    enable_nat_pmp: bool = True  # NAT Port Mapping Protocol
    manual_forwarding: bool = False  # Manual port forwarding instructions
    # Network settings
    lan_interface: str = ""  # Specific LAN interface
    allowed_ips: list[str] = field(default_factory=list)  # Allowed console IPs
    # Console-specific settings
    console_ip: str = ""  # Static IP for console
    dns_primary: str = "1.1.1.1"  # Cloudflare DNS
    dns_secondary: str = "1.0.0.1"


class GamingConsoleProxy:
    """
    Gaming console proxy manager.

    Features:
    - PS4/PS5 proxy configuration
    - Xbox proxy support
    - Nintendo Switch proxy
    - UPnP port forwarding
    - LAN proxy sharing
    - Network diagnostics
    """

    # Default ports for gaming
    PS4_PORTS = [80, 443, 3478, 3479, 3480, 9295, 9296, 9297]
    PS5_PORTS = [80, 443, 3478, 3479, 3480, 9295, 9296, 9297, 27015, 27036]
    XBOX_PORTS = [80, 443, 3478, 3479, 3074, 53, 88]
    SWITCH_PORTS = [80, 443, 3478, 3479, 6667, 12400, 12420, 28910, 29900, 29901, 29920]

    def __init__(self, config: ConsoleProxyConfig):
        self.config = config
        self._upnp_igd = None
        self._forwarded_ports: list[int] = []

    async def setup_for_console(self) -> dict[str, Any]:
        """
        Setup proxy for gaming console.

        Returns:
            Configuration instructions for console
        """
        log.info("Setting up proxy for %s", self.config.console_type.name)

        # Get LAN IP address
        lan_ip = self._get_lan_ip()

        # Setup port forwarding
        if self.config.enable_upnp:
            await self._setup_upnp_forwarding()

        # Generate configuration instructions
        instructions = self._generate_console_instructions(lan_ip)

        log.info("Console proxy setup complete. LAN IP: %s", lan_ip)

        return {
            'status': 'success',
            'lan_ip': lan_ip,
            'proxy_port': self.config.proxy_port,
            'console_type': self.config.console_type.name,
            'instructions': instructions,
            'forwarded_ports': self._forwarded_ports,
        }

    def _get_lan_ip(self) -> str:
        """Get LAN IP address of this machine."""
        try:
            # Create UDP socket to determine LAN IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            lan_ip = s.getsockname()[0]
            s.close()
            return lan_ip
        except Exception as e:
            log.error("Failed to get LAN IP: %s", e)
            return "192.168.1.100"  # Default fallback

    async def _setup_upnp_forwarding(self) -> None:
        """Setup UPnP port forwarding."""
        try:
            # Try to import miniupnpc
            import miniupnpc

            u = miniupnpc.UPnP()
            u.discover()
            u.selectigd()

            self._upnp_igd = u

            # Get external IP
            external_ip = u.externalipaddress()
            log.info("UPnP gateway found: %s", external_ip)

            # Forward proxy port
            await self._forward_port_upnp(self.config.proxy_port, self.config.proxy_port, 'TCP')

            # Forward gaming ports
            ports_to_forward = self._get_console_ports()
            for port in ports_to_forward:
                await self._forward_port_upnp(port, port, 'TCP')
                await self._forward_port_upnp(port, port, 'UDP')

            log.info("UPnP port forwarding configured")

        except ImportError:
            log.warning("miniupnpc not installed. Install: pip install miniupnpc")
        except Exception as e:
            log.error("UPnP setup failed: %s", e)

    async def _forward_port_upnp(self, external_port: int, internal_port: int,
                                  protocol: str = 'TCP') -> bool:
        """Forward single port via UPnP."""
        if not self._upnp_igd:
            return False

        try:
            lan_ip = self._get_lan_ip()

            self._upnp_igd.addportmapping(
                external_port,
                protocol,
                lan_ip,
                internal_port,
                'TG WS Proxy',
                ''
            )

            self._forwarded_ports.append(external_port)
            log.debug("Forwarded port %d/%s", external_port, protocol)
            return True

        except Exception as e:
            log.debug("Failed to forward port %d: %s", external_port, e)
            return False

    def _get_console_ports(self) -> list[int]:
        """Get ports required for configured console."""
        if self.config.console_type in (ConsoleType.PS4, ConsoleType.PS5):
            return self.PS5_PORTS if self.config.console_type == ConsoleType.PS5 else self.PS4_PORTS
        elif self.config.console_type in (ConsoleType.XBOX_ONE, ConsoleType.XBOX_SERIES):
            return self.XBOX_PORTS
        elif self.config.console_type == ConsoleType.NINTENDO_SWITCH:
            return self.SWITCH_PORTS
        else:
            return [self.config.proxy_port]

    def _generate_console_instructions(self, lan_ip: str) -> dict[str, Any]:
        """Generate setup instructions for console."""
        if self.config.console_type in (ConsoleType.PS4, ConsoleType.PS5):
            return self._generate_playstation_instructions(lan_ip)
        elif self.config.console_type in (ConsoleType.XBOX_ONE, ConsoleType.XBOX_SERIES):
            return self._generate_xbox_instructions(lan_ip)
        elif self.config.console_type == ConsoleType.NINTENDO_SWITCH:
            return self._generate_switch_instructions(lan_ip)
        else:
            return {'error': 'Unknown console type'}

    def _generate_playstation_instructions(self, lan_ip: str) -> dict[str, Any]:
        """Generate PS4/PS5 setup instructions."""
        return {
            'title': f"Настройка прокси для {self.config.console_type.name}",
            'steps': [
                {
                    'step': 1,
                    'title': 'Откройте настройки консоли',
                    'description': 'Перейдите в Settings (Настройки)'
                },
                {
                    'step': 2,
                    'title': 'Сеть',
                    'description': 'Выберите Network (Сеть) → Network Settings (Настройки сети)'
                },
                {
                    'step': 3,
                    'title': 'Настройка подключения',
                    'description': 'Выберите Set Up Internet Connection (Настроить подключение к интернету)'
                },
                {
                    'step': 4,
                    'title': 'Тип подключения',
                    'description': 'Выберите Wi-Fi или LAN кабель (рекомендуется LAN)'
                },
                {
                    'step': 5,
                    'title': 'Метод настройки',
                    'description': 'Выберите Custom (Пользовательская)'
                },
                {
                    'step': 6,
                    'title': 'IP Address Settings',
                    'description': 'Выберите Automatic'
                },
                {
                    'step': 7,
                    'title': 'DHCP Host Name',
                    'description': 'Выберите Do Not Specify'
                },
                {
                    'step': 8,
                    'title': 'DNS Settings',
                    'description': 'Выберите Manual и введите:'
                },
                {
                    'sub_step': 'Primary DNS',
                    'value': self.config.dns_primary
                },
                {
                    'sub_step': 'Secondary DNS',
                    'value': self.config.dns_secondary
                },
                {
                    'step': 9,
                    'title': 'MTU Settings',
                    'description': 'Выберите Automatic'
                },
                {
                    'step': 10,
                    'title': 'Proxy Server',
                    'description': 'Выберите Use и введите:'
                },
                {
                    'sub_step': 'Proxy Server',
                    'value': lan_ip
                },
                {
                    'sub_step': 'Proxy Port',
                    'value': str(self.config.proxy_port)
                },
                {
                    'step': 11,
                    'title': 'Проверка подключения',
                    'description': 'Выберите Test Internet Connection'
                }
            ],
            'quick_settings': {
                'proxy_server': lan_ip,
                'proxy_port': self.config.proxy_port,
                'dns_primary': self.config.dns_primary,
                'dns_secondary': self.config.dns_secondary,
            },
            'notes': [
                'Убедитесь, что консоль и компьютер находятся в одной сети',
                'Брандмауэр Windows должен разрешать подключения на порт ' + str(self.config.proxy_port),
                'Для лучшей производительности используйте LAN кабель',
            ]
        }

    def _generate_xbox_instructions(self, lan_ip: str) -> dict[str, Any]:
        """Generate Xbox setup instructions."""
        return {
            'title': f"Настройка прокси для {self.config.console_type.name}",
            'steps': [
                {
                    'step': 1,
                    'title': 'Откройте настройки',
                    'description': 'Нажмите кнопку Xbox → Profile & system → Settings'
                },
                {
                    'step': 2,
                    'title': 'Общие настройки',
                    'description': 'Выберите General → Network settings'
                },
                {
                    'step': 3,
                    'title': 'Расширенные настройки',
                    'description': 'Выберите Advanced settings'
                },
                {
                    'step': 4,
                    'title': 'DNS',
                    'description': 'Введите DNS серверы:'
                },
                {
                    'sub_step': 'Primary DNS',
                    'value': self.config.dns_primary
                },
                {
                    'sub_step': 'Secondary DNS',
                    'value': self.config.dns_secondary
                },
                {
                    'step': 5,
                    'title': 'Proxy',
                    'description': 'Xbox не поддерживает прокси напрямую. Используйте:'
                },
                {
                    'sub_step': 'Вариант 1',
                    'value': 'Настройте прокси на роутере'
                },
                {
                    'sub_step': 'Вариант 2',
                    'value': f'Используйте ПК как мост (IP: {lan_ip})'
                }
            ],
            'quick_settings': {
                'dns_primary': self.config.dns_primary,
                'dns_secondary': self.config.dns_secondary,
                'pc_proxy_ip': lan_ip,
                'pc_proxy_port': self.config.proxy_port,
            },
            'notes': [
                'Xbox не поддерживает SOCKS5 прокси напрямую',
                'Настройте прокси на уровне роутера или используйте PC как мост',
                'Для PC моста: настройте Internet Connection Sharing в Windows'
            ]
        }

    def _generate_switch_instructions(self, lan_ip: str) -> dict[str, Any]:
        """Generate Nintendo Switch setup instructions."""
        return {
            'title': f"Настройка прокси для {self.config.console_type.name}",
            'steps': [
                {
                    'step': 1,
                    'title': 'Откройте настройки',
                    'description': 'System Settings (Настройки системы)'
                },
                {
                    'step': 2,
                    'title': 'Интернет',
                    'description': 'Выберите Internet → Internet Settings'
                },
                {
                    'step': 3,
                    'title': 'Выберите сеть',
                    'description': 'Найдите вашу Wi-Fi сеть и нажмите на неё'
                },
                {
                    'step': 4,
                    'title': 'Изменение настроек',
                    'description': 'Выберите Change Settings (Изменить настройки)'
                },
                {
                    'step': 5,
                    'title': 'Proxy Settings',
                    'description': 'Прокрутите вниз до Proxy Settings'
                },
                {
                    'step': 6,
                    'title': 'Включите прокси',
                    'description': 'Установите Proxy Server в положение On'
                },
                {
                    'step': 7,
                    'title': 'Введите настройки прокси',
                    'description': ''
                },
                {
                    'sub_step': 'Proxy Server',
                    'value': lan_ip
                },
                {
                    'sub_step': 'Port',
                    'value': str(self.config.proxy_port)
                },
                {
                    'step': 8,
                    'title': 'Сохраните',
                    'description': 'Нажмите Save (Сохранить)'
                },
                {
                    'step': 9,
                    'title': 'Проверка',
                    'description': 'Test Connection (Проверить подключение)'
                }
            ],
            'quick_settings': {
                'proxy_server': lan_ip,
                'proxy_port': self.config.proxy_port,
            },
            'notes': [
                'Switch поддерживает только HTTP прокси',
                'Убедитесь, что прокси поддерживает HTTP режим',
                'Для SOCKS5 используйте DNS tunneling'
            ]
        }

    async def test_console_connection(self, console_ip: str) -> dict[str, Any]:
        """
        Test connection to gaming console.

        Args:
            console_ip: IP address of console

        Returns:
            Test results
        """
        results = {
            'console_ip': console_ip,
            'proxy_reachable': False,
            'latency_ms': 0,
            'ports_open': [],
        }

        try:
            # Test proxy port
            start = asyncio.get_event_loop().time()

            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(console_ip, self.config.proxy_port),
                timeout=5
            )

            latency = (asyncio.get_event_loop().time() - start) * 1000
            writer.close()
            await writer.wait_closed()

            results['proxy_reachable'] = True
            results['latency_ms'] = round(latency, 2)

            # Test gaming ports
            for port in self._get_console_ports()[:5]:  # Test first 5 ports
                try:
                    reader, writer = await asyncio.wait_for(
                        asyncio.open_connection(console_ip, port),
                        timeout=2
                    )
                    writer.close()
                    await writer.wait_closed()
                    results['ports_open'].append(port)
                except Exception:
                    pass

        except Exception as e:
            results['error'] = str(e)

        return results

    def get_firewall_rules(self) -> str:
        """
        Get Windows Firewall rules for gaming proxy.

        Returns:
            PowerShell commands to configure firewall
        """
        rules = f"""
# Windows Firewall Rules for Gaming Console Proxy
# Run as Administrator

# Allow incoming proxy connections
netsh advfirewall firewall add rule name="TG WS Proxy" dir=in action=allow protocol=TCP localport={self.config.proxy_port}

# Allow UDP for gaming
netsh advfirewall firewall add rule name="TG WS Proxy UDP" dir=in action=allow protocol=UDP localport={self.config.proxy_port}

# Allow gaming ports ({self.config.console_type.name})
"""
        for port in self._get_console_ports():
            rules += f"netsh advfirewall firewall add rule name=\"Game Port {port}\" dir=in action=allow protocol=TCP localport={port}\n"

        return rules

    async def cleanup(self) -> None:
        """Cleanup UPnP mappings."""
        if self._upnp_igd:
            try:
                for port in self._forwarded_ports:
                    self._upnp_igd.deleteportmapping(port, 'TCP')
                    self._upnp_igd.deleteportmapping(port, 'UDP')
                log.info("UPnP port mappings removed")
            except Exception as e:
                log.error("UPnP cleanup failed: %s", e)


def create_console_proxy(console_type: str, port: int = 1080) -> GamingConsoleProxy:
    """
    Create gaming console proxy.

    Args:
        console_type: PS4, PS5, XBOX_ONE, XBOX_SERIES, NINTENDO_SWITCH
        port: Proxy port

    Returns:
        GamingConsoleProxy instance
    """
    console_map = {
        'PS4': ConsoleType.PS4,
        'PS5': ConsoleType.PS5,
        'XBOX_ONE': ConsoleType.XBOX_ONE,
        'XBOX_SERIES': ConsoleType.XBOX_SERIES,
        'SWITCH': ConsoleType.NINTENDO_SWITCH,
        'NINTENDO_SWITCH': ConsoleType.NINTENDO_SWITCH,
    }

    console = console_map.get(console_type.upper(), ConsoleType.PS5)
    config = ConsoleProxyConfig(console_type=console, proxy_port=port)

    return GamingConsoleProxy(config)


__all__ = [
    'ConsoleType',
    'ConsoleProxyConfig',
    'GamingConsoleProxy',
    'create_console_proxy',
]
