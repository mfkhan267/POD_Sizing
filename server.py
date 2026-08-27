#!/usr/bin/env python3
"""Optional local server for the static Kubernetes Capacity Planner."""
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
import os
ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
print("Kubernetes Capacity Planner")
print("Open: http://localhost:8080")
ThreadingHTTPServer(("127.0.0.1", 8080), SimpleHTTPRequestHandler).serve_forever()
