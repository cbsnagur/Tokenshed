#!/usr/bin/env python3
"""tokenshed dashboard: serves stats_dashboard.html plus a live copy of the
stats ledger on localhost, so the page can re-read it on a timer. Browsers
refuse to re-read files under AppData from a file:// page.
"""
import argparse
import http.server
import os
import sys
import webbrowser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _stats import ledger_path  # noqa: E402

DASHBOARD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stats_dashboard.html")


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        routes = {
            "/": (DASHBOARD, "text/html; charset=utf-8"),
            "/stats.jsonl": (ledger_path(), "text/plain; charset=utf-8"),
        }
        path, ctype = routes.get(self.path.split("?")[0], (None, None))
        try:
            with open(path, "rb") as f:
                body = f.read()
        except (OSError, TypeError):
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def main(argv=None):
    parser = argparse.ArgumentParser(description="Serve the Tokenshed savings dashboard on localhost.")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true", help="don't open the dashboard automatically")
    args = parser.parse_args(argv)

    server = http.server.ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://127.0.0.1:{args.port}/"
    print(f"tokenshed dashboard at {url} (reading {ledger_path()}); Ctrl+C to stop")
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
