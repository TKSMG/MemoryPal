"""Serve the in-memory fake Supabase (latest_app/tests/fake_supabase.py) over HTTP.

Used by sync_interop.py so the desktop's Python client and the phone's
TypeScript client can sync with each other against one server, locally.
"""

import sys
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "latest_app" / "tests"))

from fake_supabase import FakeSupabase  # noqa: E402


def serve(fake, port=0):
    """Start serving `fake` on localhost; returns (server, base_url)."""

    class Handler(BaseHTTPRequestHandler):
        def handle_any(self):
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length else None
            headers = {name: value for name, value in self.headers.items() if name.lower() in ("apikey", "authorization", "content-type", "prefer", "accept")}
            request = urllib.request.Request(f"http://localhost{self.path}", data=body, headers=headers, method=self.command)
            try:
                with fake.open(request) as response:
                    status, payload = 200, response.read()
            except urllib.error.HTTPError as error:
                status, payload = error.code, error.read()
            except urllib.error.URLError:
                self.close_connection = True
                return
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        do_GET = do_POST = do_PUT = do_DELETE = handle_any

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}"


if __name__ == "__main__":
    server, url = serve(FakeSupabase(confirm_email=False), int(sys.argv[1]) if len(sys.argv) > 1 else 54321)
    print(f"fake Supabase on {url}  (publishable key: sb_publishable_test)")
    threading.Event().wait()
