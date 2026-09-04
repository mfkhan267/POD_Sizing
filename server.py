#!/usr/bin/env python3
"""Zero-dependency local server for the Kubernetes Cluster Capacity Planner."""
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import os

HOST = "127.0.0.1"
PORT = 8000

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    print(f"Kubernetes Cluster Capacity Planner: http://{HOST}:{PORT}")
    print("Press Ctrl+C to stop.")
    ThreadingHTTPServer((HOST, PORT), SimpleHTTPRequestHandler).serve_forever()
