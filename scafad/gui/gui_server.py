#!/usr/bin/env python3
"""
SCAFAD GUI Server - Lightweight HTTP server for the React analyst console.
Uses only Python stdlib: http.server, http.client, json, subprocess, urllib, os.

This server:
- Serves the SCAFAD React dashboard from scafad/gui/frontend/dist/
- Reverse-proxies /api/* requests to the FastAPI backend on 127.0.0.1:8088
  (transparent to the React app; supports JSON endpoints and SSE streams)
- Proxies Lambda invocations via POST /invoke (legacy live-AWS path)
- Requires AWS CLI to be installed and configured for /invoke
"""

import http.server
import http.client
import json
import subprocess
import os
import sys
from urllib.parse import urlparse
from pathlib import Path

# Backend (FastAPI/uvicorn) address — start_gui.py spawns it on this port.
BACKEND_HOST = '127.0.0.1'
BACKEND_PORT = 8088


class SCAfadGUIHandler(http.server.BaseHTTPRequestHandler):
    """HTTP request handler for SCAFAD GUI server."""

    # MIME type map for static asset serving
    _MIME = {
        '.html': 'text/html; charset=utf-8',
        '.js':   'application/javascript',
        '.css':  'text/css',
        '.svg':  'image/svg+xml',
        '.ico':  'image/x-icon',
        '.png':  'image/png',
        '.woff2': 'font/woff2',
        '.woff':  'font/woff',
        '.json':  'application/json',
    }

    def _serve_file(self, filepath: Path, mime: str) -> None:
        """Send a static file response."""
        try:
            data = filepath.read_bytes()
            self.send_response(200)
            self.send_header('Content-type', mime)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': str(e)}).encode())

    def _proxy_to_backend(self, method: str) -> None:
        """Forward the current request to the FastAPI backend on BACKEND_PORT.

        Streams the response back transparently. Supports SSE (text/event-stream)
        by chunked-streaming the upstream body until EOF.
        """
        # Hop-by-hop headers we must not forward (RFC 7230 §6.1).
        HOP_BY_HOP = {
            'connection', 'keep-alive', 'proxy-authenticate',
            'proxy-authorization', 'te', 'trailers',
            'transfer-encoding', 'upgrade',
        }

        # Build outgoing request
        try:
            content_length = int(self.headers.get('Content-Length', 0) or 0)
        except ValueError:
            content_length = 0
        body = self.rfile.read(content_length) if content_length > 0 else None

        out_headers = {}
        for h, v in self.headers.items():
            if h.lower() in HOP_BY_HOP:
                continue
            if h.lower() == 'host':
                continue  # rewrite below
            out_headers[h] = v
        out_headers['Host'] = f'{BACKEND_HOST}:{BACKEND_PORT}'

        # Open upstream connection. For SSE we need a long-lived response,
        # so use a moderately long timeout but rely on the upstream sending
        # heartbeats to keep the socket alive.
        conn = http.client.HTTPConnection(
            BACKEND_HOST, BACKEND_PORT, timeout=300
        )
        try:
            conn.request(method, self.path, body=body, headers=out_headers)
            resp = conn.getresponse()
        except (ConnectionRefusedError, OSError) as exc:
            self.send_response(502)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({
                'error': 'Backend unreachable',
                'detail': (
                    f'FastAPI backend not responding at '
                    f'{BACKEND_HOST}:{BACKEND_PORT}. '
                    'Ensure start_gui.py spawned the backend, or run '
                    'scripts/run_gui_dev.ps1 manually.'
                ),
                'exception': str(exc),
            }).encode())
            return

        # Detect SSE
        upstream_ctype = resp.getheader('Content-Type') or ''
        is_sse = upstream_ctype.startswith('text/event-stream')

        # Forward status + headers (filter hop-by-hop and Content-Length for SSE)
        self.send_response(resp.status)
        for h, v in resp.getheaders():
            if h.lower() in HOP_BY_HOP:
                continue
            if is_sse and h.lower() == 'content-length':
                continue
            self.send_header(h, v)
        # Permissive CORS to keep dev parity (Vite already does this in dev)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        try:
            if is_sse:
                # Stream chunks until upstream closes the connection.
                while True:
                    chunk = resp.read(4096)
                    if not chunk:
                        break
                    try:
                        self.wfile.write(chunk)
                        self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError):
                        break
            else:
                # Buffered: read whole body then write.
                payload = resp.read()
                self.wfile.write(payload)
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def do_GET(self) -> None:
        """Serve the React dashboard or proxy /api/* to the FastAPI backend."""
        gui_dir   = Path(__file__).parent
        react_dist = gui_dir / 'frontend' / 'dist'
        parsed    = urlparse(self.path)
        req_path  = parsed.path.rstrip('/')

        # --- API requests are proxied to the FastAPI backend ---
        if parsed.path.startswith('/api/') or parsed.path == '/api':
            self._proxy_to_backend('GET')
            return

        # --- Static assets (JS bundles, CSS, fonts, icons) ---
        if req_path.startswith('/assets/') or req_path in ('/favicon.svg', '/favicon.ico'):
            asset_file = react_dist / req_path.lstrip('/')
            if asset_file.exists() and asset_file.is_file():
                suffix = asset_file.suffix
                mime   = self._MIME.get(suffix, 'application/octet-stream')
                self._serve_file(asset_file, mime)
            else:
                self.send_response(404)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                self.wfile.write(b'Asset not found')
            return

        # --- Root and all SPA routes -> React index.html ---
        react_index = react_dist / 'index.html'
        if react_index.exists():
            self._serve_file(react_index, 'text/html; charset=utf-8')
            return

        # No React build found
        self.send_response(503)
        self.send_header('Content-type', 'text/plain; charset=utf-8')
        self.end_headers()
        self.wfile.write(
            b'SCAFAD React dashboard not found. '
            b'Run "npm install && npm run build" inside scafad/gui/frontend/.'
        )

    def do_POST(self) -> None:
        """Handle Lambda invocation requests or proxy /api/* to the backend."""
        # --- API requests are proxied to the FastAPI backend ---
        if self.path.startswith('/api/') or self.path == '/api':
            self._proxy_to_backend('POST')
            return

        if self.path == '/invoke':
            try:
                content_length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(content_length)

                # Parse request payload
                try:
                    payload = json.loads(body.decode('utf-8'))
                except json.JSONDecodeError:
                    self.send_response(400)
                    self.send_header('Content-type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    error_response = json.dumps(
                        {'error': 'Invalid JSON in request body'}
                    )
                    self.wfile.write(error_response.encode('utf-8'))
                    return

                # Get Lambda configuration from environment
                lambda_function = os.environ.get(
                    'AWS_LAMBDA_FUNCTION', 'scafad-layer0-dev'
                )
                region = os.environ.get('AWS_REGION', 'eu-west-2')

                # Invoke Lambda via AWS CLI
                try:
                    result = subprocess.run(
                        [
                            'aws',
                            'lambda',
                            'invoke',
                            '--function-name',
                            lambda_function,
                            '--region',
                            region,
                            '--payload',
                            json.dumps(payload),
                            '/tmp/scafad_lambda_response.json',
                        ],
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )

                    if result.returncode != 0:
                        self.send_response(500)
                        self.send_header('Content-type', 'application/json')
                        self.send_header('Access-Control-Allow-Origin', '*')
                        self.end_headers()
                        self.wfile.write(json.dumps({
                            'error': 'AWS Lambda invocation failed',
                            'details': result.stderr,
                        }).encode('utf-8'))
                        return

                    # Read Lambda response
                    try:
                        with open('/tmp/scafad_lambda_response.json', 'r') as f:
                            lambda_response = json.load(f)
                    except (FileNotFoundError, json.JSONDecodeError):
                        self.send_response(500)
                        self.send_header('Content-type', 'application/json')
                        self.send_header('Access-Control-Allow-Origin', '*')
                        self.end_headers()
                        self.wfile.write(json.dumps(
                            {'error': 'Failed to read Lambda response'}
                        ).encode('utf-8'))
                        return

                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps(lambda_response).encode('utf-8'))

                except subprocess.TimeoutExpired:
                    self.send_response(504)
                    self.send_header('Content-type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps(
                        {'error': 'Lambda invocation timed out'}
                    ).encode('utf-8'))
                except FileNotFoundError:
                    self.send_response(500)
                    self.send_header('Content-type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        'error': 'AWS CLI not found. Please ensure AWS CLI is installed and in PATH.'
                    }).encode('utf-8'))

            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({'error': str(e)}).encode('utf-8'))
        else:
            self.send_response(404)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'Not found')

    def do_PUT(self) -> None:
        if self.path.startswith('/api/') or self.path == '/api':
            self._proxy_to_backend('PUT')
            return
        self.send_response(404); self.end_headers(); self.wfile.write(b'Not found')

    def do_DELETE(self) -> None:
        if self.path.startswith('/api/') or self.path == '/api':
            self._proxy_to_backend('DELETE')
            return
        self.send_response(404); self.end_headers(); self.wfile.write(b'Not found')

    def do_PATCH(self) -> None:
        if self.path.startswith('/api/') or self.path == '/api':
            self._proxy_to_backend('PATCH')
            return
        self.send_response(404); self.end_headers(); self.wfile.write(b'Not found')

    def do_OPTIONS(self) -> None:
        if self.path.startswith('/api/') or self.path == '/api':
            self._proxy_to_backend('OPTIONS')
            return
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods',
                         'GET, POST, PUT, DELETE, PATCH, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def log_message(self, format: str, *args) -> None:
        # Quiet by default
        pass


def run_server(port: int = 8765) -> None:
    server_address = ('127.0.0.1', port)
    httpd = http.server.HTTPServer(server_address, SCAfadGUIHandler)
    print(f'SCAFAD GUI server running at http://localhost:{port}')
    print('Open this URL in your browser to access the dashboard.')
    print('Press Ctrl+C to stop the server.')
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print('\nServer stopped.')
        sys.exit(0)


if __name__ == '__main__':
    run_server()
