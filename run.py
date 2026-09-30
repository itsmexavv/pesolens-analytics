"""Run the standalone PesoLens project: python run.py --port 8000."""
import argparse
import json
import mimetypes
import os
import re
import sqlite3
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from app import Peso
from core import APIError

ROOT = Path(__file__).resolve().parent


def allowed_addresses(port, environ=None):
    """Trust local addresses and only this Codespace's exact forwarded host."""
    environ = os.environ if environ is None else environ
    hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
    origins = {f"http://{host}" for host in hosts}
    name = environ.get("CODESPACE_NAME", "")
    domain = environ.get("GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN", "")
    if (environ.get("CODESPACES") == "true"
            and re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name)
            and len(domain) <= 253
            and re.fullmatch(r"[a-z0-9]+(?:[-a-z0-9]*[a-z0-9])?(?:\.[a-z0-9]+(?:[-a-z0-9]*[a-z0-9])?)+", domain)):
        forwarded_host = f"{name}-{port}.{domain}"
        hosts.add(forwarded_host)
        origins.add(f"https://{forwarded_host}")
    return hosts, origins


def create_server(port=8000, data_dir=None):
    directory = Path(data_dir) if data_dir else ROOT / "data"
    apps = {"peso": Peso(directory/"peso.db")}

    class Handler(BaseHTTPRequestHandler):
        def respond(self, status, body, mime="application/json; charset=utf-8"):
            raw = json.dumps(body, allow_nan=False).encode() if mime.startswith("application/json") else (body.encode() if isinstance(body, str) else body)
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers()
            self.wfile.write(raw)

        def dispatch(self):
            try:
                host = self.headers.get("Host", "")
                if host not in self.server.allowed_hosts:
                    raise APIError("Use the localhost or Codespaces URL for this server.", 403)
                url = urlsplit(self.path)
                if url.path == "/api/health" and self.command == "GET":
                    self.respond(200, {"app": "PesoLens", "status": "ok"})
                elif url.path.startswith("/api/"):
                    parts = url.path.split("/", 3)
                    if len(parts) < 4 or parts[2] not in apps:
                        raise APIError("Project API not found.", 404)
                    data = {}
                    if self.command != "GET":
                        origin = self.headers.get("Origin")
                        if origin and origin not in self.server.allowed_origins:
                            raise APIError("Cross-origin writes are not allowed.", 403)
                        if not self.headers.get("Content-Type", "").startswith("application/json"):
                            raise APIError("Send application/json.", 415)
                        try:
                            length = int(self.headers.get("Content-Length", "0"))
                        except ValueError:
                            raise APIError("Invalid body length.")
                        if not 0 < length <= 150_000:
                            raise APIError("JSON body must be 1–150,000 bytes.", 413)
                        try:
                            data = json.loads(self.rfile.read(length), parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
                        except (ValueError, UnicodeDecodeError):
                            raise APIError("Invalid JSON.")
                        if not isinstance(data, dict):
                            raise APIError("JSON body must be an object.")
                    result = apps[parts[2]].handle(self.command, "/"+parts[3], data, parse_qs(url.query))
                    if isinstance(result, tuple):
                        self.respond(200, result[0], result[1])
                    else:
                        self.respond(201 if self.command == "POST" else 200, result)
                elif self.command == "GET":
                    name = url.path.lstrip("/") or "index.html"
                    web_root = ROOT.resolve()
                    file = (web_root/name).resolve()
                    if name not in {"index.html", "guide.html", "app.js", "style.css", "icon.svg"} or not file.is_file():
                        raise APIError("Page not found.", 404)
                    self.respond(200, file.read_bytes(), mimetypes.guess_type(file)[0] or "application/octet-stream")
                else:
                    raise APIError("Method not allowed.", 405)
            except APIError as exc:
                self.respond(exc.status, {"error": str(exc)})
            except sqlite3.IntegrityError:
                self.respond(409, {"error": "That record already exists or conflicts with a data constraint."})
            except Exception as exc:
                print(f"Server error: {type(exc).__name__}: {exc}", file=sys.stderr)
                self.respond(500, {"error": "Unexpected server error. Check the server terminal."})

        do_GET = do_POST = do_PATCH = do_DELETE = dispatch

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.allowed_hosts, server.allowed_origins = allowed_addresses(server.server_port)
    server.daemon_threads = True
    return server


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--data-dir", type=Path, help="Optional directory for local SQLite databases")
    args = parser.parse_args()
    server = create_server(args.port, args.data_dir)
    print(f"PesoLens ready: http://127.0.0.1:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
