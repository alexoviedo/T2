#!/usr/bin/env python3
"""Serve the browser Gamepad API witness and capture posted snapshots."""

from __future__ import annotations

import argparse
import datetime as dt
import http.server
import json
import pathlib
import socketserver
import sys
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parent


class WitnessHandler(http.server.SimpleHTTPRequestHandler):
    capture_file: pathlib.Path

    def __init__(self, *args: Any, directory: str | None = None, **kwargs: Any) -> None:
        super().__init__(*args, directory=directory or str(ROOT), **kwargs)

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stdout.write("[gamepad-witness] " + (fmt % args) + "\n")
        sys.stdout.flush()

    def do_GET(self) -> None:  # noqa: N802 - stdlib callback name
        if self.path == "/":
            self.path = "/index.html"
        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802 - stdlib callback name
        if self.path != "/capture":
            self.send_error(404)
            return

        length = int(self.headers.get("content-length", "0"))
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self.send_error(400, "invalid json")
            return

        line = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        with self.capture_file.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
        sys.stdout.write("[capture] " + line + "\n")
        sys.stdout.flush()

        self.send_response(204)
        self.end_headers()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--out-dir", default="target/gamepad-witness")
    args = parser.parse_args()

    out_dir = pathlib.Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    WitnessHandler.capture_file = out_dir / f"gamepad_witness_{stamp}.jsonl"

    class ReusableTCPServer(socketserver.TCPServer):
        allow_reuse_address = True

    with ReusableTCPServer((args.host, args.port), WitnessHandler) as httpd:
        url = f"http://{args.host}:{args.port}/"
        print(f"Serving USB2BLE Gamepad Witness at {url}")
        print(f"Capture file: {WitnessHandler.capture_file}")
        print("Press Ctrl+C to stop.")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
