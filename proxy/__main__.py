"""
Entry point for running TG WS Proxy.

Usage:
    python -m proxy --socks-port 1080 --verbose
"""

from .tg_ws_proxy import main

if __name__ == '__main__':
    main()
