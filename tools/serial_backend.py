#!/usr/bin/env python3
"""Small cross-platform serial backend for USB2BLE witness helpers."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
import select
import sys
import time

try:
    import termios
    import tty
except ImportError:  # pragma: no cover - exercised on Windows
    termios = None  # type: ignore[assignment]
    tty = None  # type: ignore[assignment]


BAUD = termios.B115200 if termios is not None else 115200


class PosixSerialPort:
    def __init__(self, path: str, baud: int = BAUD) -> None:
        if termios is None or tty is None:
            raise RuntimeError("POSIX termios serial support is not available on this platform")
        self.fd = os.open(path, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        self._previous_attrs = termios.tcgetattr(self.fd)

        attrs = termios.tcgetattr(self.fd)
        tty.setraw(self.fd)
        attrs = termios.tcgetattr(self.fd)
        attrs[4] = baud
        attrs[5] = baud
        attrs[2] |= termios.CLOCAL | termios.CREAD
        termios.tcsetattr(self.fd, termios.TCSANOW, attrs)

    def close(self) -> None:
        termios.tcsetattr(self.fd, termios.TCSANOW, self._previous_attrs)
        os.close(self.fd)

    def write_line(self, line: str) -> None:
        os.write(self.fd, (line.rstrip("\r\n") + "\n").encode("utf-8"))

    def read_text(self, timeout: float) -> str:
        deadline = time.monotonic() + timeout
        chunks: list[bytes] = []
        while time.monotonic() < deadline:
            remaining = max(0.0, deadline - time.monotonic())
            readable, _, _ = select.select([self.fd], [], [], min(0.1, remaining))
            if not readable:
                continue
            try:
                chunk = os.read(self.fd, 8192)
            except BlockingIOError:
                continue
            if chunk:
                chunks.append(chunk)
        return b"".join(chunks).decode("utf-8", errors="replace")


if os.name == "nt":
    GENERIC_READ = 0x80000000
    GENERIC_WRITE = 0x40000000
    OPEN_EXISTING = 3
    INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value
    PURGE_RXCLEAR = 0x0008
    PURGE_TXCLEAR = 0x0004

    class DCB(ctypes.Structure):
        _fields_ = [
            ("DCBlength", wintypes.DWORD),
            ("BaudRate", wintypes.DWORD),
            ("fBitFields", wintypes.DWORD),
            ("wReserved", wintypes.WORD),
            ("XonLim", wintypes.WORD),
            ("XoffLim", wintypes.WORD),
            ("ByteSize", wintypes.BYTE),
            ("Parity", wintypes.BYTE),
            ("StopBits", wintypes.BYTE),
            ("XonChar", ctypes.c_char),
            ("XoffChar", ctypes.c_char),
            ("ErrorChar", ctypes.c_char),
            ("EofChar", ctypes.c_char),
            ("EvtChar", ctypes.c_char),
            ("wReserved1", wintypes.WORD),
        ]

    class COMMTIMEOUTS(ctypes.Structure):
        _fields_ = [
            ("ReadIntervalTimeout", wintypes.DWORD),
            ("ReadTotalTimeoutMultiplier", wintypes.DWORD),
            ("ReadTotalTimeoutConstant", wintypes.DWORD),
            ("WriteTotalTimeoutMultiplier", wintypes.DWORD),
            ("WriteTotalTimeoutConstant", wintypes.DWORD),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateFileW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.GetCommState.argtypes = [wintypes.HANDLE, ctypes.POINTER(DCB)]
    kernel32.GetCommState.restype = wintypes.BOOL
    kernel32.SetCommState.argtypes = [wintypes.HANDLE, ctypes.POINTER(DCB)]
    kernel32.SetCommState.restype = wintypes.BOOL
    kernel32.SetCommTimeouts.argtypes = [wintypes.HANDLE, ctypes.POINTER(COMMTIMEOUTS)]
    kernel32.SetCommTimeouts.restype = wintypes.BOOL
    kernel32.PurgeComm.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.PurgeComm.restype = wintypes.BOOL
    kernel32.ReadFile.argtypes = [
        wintypes.HANDLE,
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        wintypes.LPVOID,
    ]
    kernel32.ReadFile.restype = wintypes.BOOL
    kernel32.WriteFile.argtypes = [
        wintypes.HANDLE,
        wintypes.LPCVOID,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        wintypes.LPVOID,
    ]
    kernel32.WriteFile.restype = wintypes.BOOL


def _raise_last_os_error() -> None:
    raise ctypes.WinError(ctypes.get_last_error())


def _windows_port_path(path: str) -> str:
    if path.startswith("\\\\.\\"):
        return path
    if path.upper().startswith("COM"):
        return "\\\\.\\" + path
    return path


class WindowsSerialPort:
    def __init__(self, path: str, baud: int = 115200) -> None:
        self.handle = kernel32.CreateFileW(
            _windows_port_path(path),
            GENERIC_READ | GENERIC_WRITE,
            0,
            None,
            OPEN_EXISTING,
            0,
            None,
        )
        if self.handle == INVALID_HANDLE_VALUE:
            _raise_last_os_error()

        dcb = DCB()
        dcb.DCBlength = ctypes.sizeof(DCB)
        if not kernel32.GetCommState(self.handle, ctypes.byref(dcb)):
            self.close()
            _raise_last_os_error()
        dcb.BaudRate = int(baud)
        dcb.ByteSize = 8
        dcb.Parity = 0
        dcb.StopBits = 0
        dcb.fBitFields |= 0x0001
        if not kernel32.SetCommState(self.handle, ctypes.byref(dcb)):
            self.close()
            _raise_last_os_error()

        timeouts = COMMTIMEOUTS(
            ReadIntervalTimeout=50,
            ReadTotalTimeoutMultiplier=0,
            ReadTotalTimeoutConstant=50,
            WriteTotalTimeoutMultiplier=0,
            WriteTotalTimeoutConstant=1000,
        )
        if not kernel32.SetCommTimeouts(self.handle, ctypes.byref(timeouts)):
            self.close()
            _raise_last_os_error()
        kernel32.PurgeComm(self.handle, PURGE_RXCLEAR | PURGE_TXCLEAR)

    def close(self) -> None:
        if getattr(self, "handle", None):
            kernel32.CloseHandle(self.handle)
            self.handle = None

    def write_line(self, line: str) -> None:
        data = (line.rstrip("\r\n") + "\n").encode("utf-8")
        written = wintypes.DWORD()
        if not kernel32.WriteFile(self.handle, data, len(data), ctypes.byref(written), None):
            _raise_last_os_error()
        if written.value != len(data):
            raise OSError(f"short serial write: {written.value} of {len(data)} bytes")

    def read_text(self, timeout: float) -> str:
        deadline = time.monotonic() + timeout
        chunks: list[bytes] = []
        while time.monotonic() < deadline:
            buffer = ctypes.create_string_buffer(8192)
            read = wintypes.DWORD()
            if not kernel32.ReadFile(self.handle, buffer, len(buffer), ctypes.byref(read), None):
                _raise_last_os_error()
            if read.value:
                chunks.append(buffer.raw[: read.value])
            else:
                time.sleep(0.01)
        return b"".join(chunks).decode("utf-8", errors="replace")


NativeSerialPort = WindowsSerialPort if sys.platform == "win32" else PosixSerialPort
