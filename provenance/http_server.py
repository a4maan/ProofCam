"""Loopback-only development transport. Never use this server for public deployment."""
import sqlite3
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

from .protocol import MAX_MESSAGE, Rejected, encode


def make_server(service, port=8765):
    class Handler(BaseHTTPRequestHandler):
        server_version = 'ProofCamDev/1'
        sys_version = ''

        def setup(self):
            super().setup()
            self.connection.settimeout(5)

        def log_message(self, *_args):
            pass  # No paths, hashes, tokens, headers or bodies in access logs.

        def reply(self, status, body):
            self.send_response(status)
            self.send_header('Content-Type', 'application/cbor')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(body)

        def dispatch(self):
            # Bound even unauthenticated development requests; no persistent network identifiers.
            minute = int(time.time())//60
            if self.server.bucket != minute:
                self.server.bucket, self.server.requests = minute, 0
            self.server.requests += 1
            if self.server.requests > 120:
                self.reply(429, encode({'error':'transport_quota_exceeded'})); return
            try:
                expected = {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}
                if len(self.headers.get_all('Host', [])) != 1 or self.headers.get('Host') not in expected:
                    raise Rejected('invalid_host')
                if self.command == 'GET':
                    if not self.path.startswith('/v1/records/'):
                        raise Rejected('unknown_route')
                    result = service.lookup(self.path[len('/v1/records/'):])
                else:
                    routes = {'/v1/enroll':service.enroll, '/v1/challenges':service.challenge,
                              '/v1/register':service.register, '/v1/remove':service.remove}
                    action = routes.get(self.path)
                    if action is None:
                        raise Rejected('unknown_route')
                    lengths = self.headers.get_all('Content-Length', [])
                    if len(lengths) != 1 or not 1 <= len(lengths[0]) <= 5 or not lengths[0].isascii() or not lengths[0].isdigit():
                        raise Rejected('invalid_content_length')
                    size = int(lengths[0])
                    if self.headers.get('Transfer-Encoding') or not 0 < size <= MAX_MESSAGE:
                        raise Rejected('invalid_message_size')
                    if self.headers.get_all('Content-Type', []) != ['application/cbor']:
                        raise Rejected('unsupported_content_type')
                    data = self.rfile.read(size)
                    if len(data) != size:
                        raise Rejected('incomplete_message')
                    result = action(data)
                self.reply(200, result if isinstance(result,bytes) else encode(result))
            except Rejected as exc:
                status = 404 if str(exc)=='record_unavailable' else 429 if str(exc)=='quota_exceeded' else 400
                self.reply(status, encode({'error':str(exc)}))
            except (TimeoutError, ConnectionError):
                self.close_connection = True
            except sqlite3.Error:
                self.reply(503, encode({'error':'storage_unavailable'}))

        do_POST = dispatch
        do_GET = dispatch

    server = HTTPServer(('127.0.0.1', port), Handler)
    server.bucket, server.requests = 0, 0
    return server
