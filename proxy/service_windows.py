"""Windows service wrapper for TG WS Proxy."""

from __future__ import annotations

import os
import socket
import subprocess
import sys

import servicemanager
import win32event
import win32service
import win32serviceutil


class TgWsProxyService(win32serviceutil.ServiceFramework):
    _svc_name_ = "TgWsProxy"
    _svc_display_name_ = "Telegram WebSocket Bridge Proxy"
    _svc_description_ = "Ensures stable Telegram connection via WebSocket tunnel."

    def __init__(self, args: list[str]) -> None:
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        socket.setdefaulttimeout(60)
        self.process: subprocess.Popen | None = None

    def SvcStop(self) -> None:
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.hWaitStop)
        if self.process:
            self.process.terminate()

    def SvcDoRun(self) -> None:
        servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE,
                              servicemanager.PYS_SERVICE_STARTED,
                              (self._svc_name_, ''))
        self.main()

    def main(self) -> None:
        # Path to python executable and the proxy module
        executable = sys.executable
        script_path = os.path.join(os.path.dirname(__file__), "tg_ws_proxy.py")

        # Start the proxy as a subprocess
        # You might want to pass specific arguments here
        self.process = subprocess.Popen([executable, script_path, "--port", "8080", "--host", "0.0.0.0"])

        # Wait for stop event
        win32event.WaitForSingleObject(self.hWaitStop, win32event.INFINITE)

if __name__ == '__main__':
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(TgWsProxyService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(TgWsProxyService)
