#!/usr/bin/env python3
"""
Mock FortiGate — tiny HTTP stub that speaks just enough of the FortiOS API to
let the shipped sample tools (fortigate-health-check, fortigate-interface-status,
etc.) execute end-to-end without a real device.

The goal is NOT to simulate FortiOS behavior realistically. The goal is to
return plausible-looking JSON so the signing / verification / execution pipeline
can be proven on a laptop with nothing but Python installed.

Usage:
    python scripts/mock-fortigate.py                    # listens on 0.0.0.0:8443 (HTTP)
    python scripts/mock-fortigate.py --port 9443        # custom port
    python scripts/mock-fortigate.py --host 127.0.0.1   # loopback only

Point credentials at it via scripts/sample_credentials.yaml.example.

Stdlib only — no pip install required.
"""

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


FAKE_RESPONSES = {
    "/api/v2/monitor/system/status": {
        "http_method": "GET",
        "results": {
            "version": "v7.4.3",
            "build": 2572,
            "hostname": "mock-fortigate",
            "model": "FGT-VM64",
            "serial": "MOCK0000000001",
            "log_disk_status": "available",
            "fortiguard": {"license": "valid"},
        },
        "status": "success",
    },
    "/api/v2/monitor/system/resource/usage": {
        "http_method": "GET",
        "results": {
            "cpu": [{"current": 12, "average": 10}],
            "memory": [{"current": 38, "average": 36}],
            "session": [{"current": 1420, "average": 1300}],
            "disk": [{"current": 22, "average": 22}],
        },
        "status": "success",
    },
    "/api/v2/monitor/system/interface": {
        "http_method": "GET",
        "results": {
            "port1": {"status": "up", "link": True, "speed": 1000, "ip": "192.0.2.1", "mask": "255.255.255.0"},
            "port2": {"status": "up", "link": True, "speed": 1000, "ip": "198.51.100.1", "mask": "255.255.255.0"},
            "port3": {"status": "down", "link": False, "speed": 0, "ip": "0.0.0.0", "mask": "0.0.0.0"},
        },
        "status": "success",
    },
    "/api/v2/monitor/router/ipv4": {
        "http_method": "GET",
        "results": [
            {"ip_mask": "0.0.0.0/0", "type": "static", "gateway": "192.0.2.254", "interface": "port1", "distance": 10, "metric": 0},
            {"ip_mask": "10.0.0.0/8", "type": "bgp", "gateway": "198.51.100.254", "interface": "port2", "distance": 20, "metric": 100},
        ],
        "status": "success",
    },
    "/api/v2/monitor/vpn/ipsec": {
        "http_method": "GET",
        "results": [
            {"name": "mock-tunnel-1", "proxyid": [{"status": "up", "p2name": "phase2-1"}], "rx_bytes": 12345678, "tx_bytes": 87654321},
        ],
        "status": "success",
    },
}


class MockHandler(BaseHTTPRequestHandler):
    def _reply(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _route(self):
        path = self.path.split("?", 1)[0]
        if path == "/health":
            return self._reply({"status": "ok", "mock": True})
        if path in FAKE_RESPONSES:
            return self._reply(FAKE_RESPONSES[path])
        return self._reply(
            {"error": "mock does not implement this path", "path": path, "available": list(FAKE_RESPONSES.keys())},
            status=404,
        )

    def do_GET(self):
        self._route()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        _ = self.rfile.read(length) if length else b""
        self._reply({"status": "success", "mock": True, "echo_path": self.path})

    def log_message(self, fmt, *args):
        sys.stderr.write("[mock-fortigate] %s - %s\n" % (self.address_string(), fmt % args))


def main():
    parser = argparse.ArgumentParser(description="Mock FortiGate for local Trust Anchor testing")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8443)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), MockHandler)
    print(f"[mock-fortigate] Listening on http://{args.host}:{args.port}", file=sys.stderr)
    print("[mock-fortigate] Endpoints:", file=sys.stderr)
    for p in FAKE_RESPONSES:
        print(f"  GET  {p}", file=sys.stderr)
    print("  GET  /health", file=sys.stderr)
    print("[mock-fortigate] Ctrl+C to stop.", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[mock-fortigate] Shutting down.", file=sys.stderr)


if __name__ == "__main__":
    main()
