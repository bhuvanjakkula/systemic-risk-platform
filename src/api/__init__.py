"""Local development HTTP API. Run with python -m src.api."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from src.common.pipeline import analyze


class Handler(BaseHTTPRequestHandler):
    def respond(self, status, payload):
        body = json.dumps(payload, allow_nan=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self.respond(200, {'status': 'ok', 'model_version': '0.1.0'}) if self.path == '/health' else self.respond(404, {'error': 'Not found'})

    def do_POST(self):
        if self.path != '/analyze':
            return self.respond(404, {'error': 'Not found'})
        try:
            if self.headers.get('Transfer-Encoding'):
                raise ValueError('Transfer-Encoding is unsupported')
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 1048576:
                return self.respond(413, {'error': 'Request body missing or too large'})
            payload = json.loads(self.rfile.read(length))
            result = analyze(payload)
        except (ValueError, UnicodeError) as exc:
            return self.respond(400, {'error': str(exc)})
        self.respond(200, result)

    def setup(self):
        super().setup()
        self.connection.settimeout(10)


def serve(host='127.0.0.1', port=8000):
    with ThreadingHTTPServer((host, port), Handler) as server:
        print(f'Systemic Risk API: http://{host}:{port}', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
