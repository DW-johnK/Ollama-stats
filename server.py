#!/usr/bin/env python3
"""Static server for Open Ollama dashboard. Serves index.html on any path."""
import http.server
import socketserver
import os

PORT = int(os.environ.get("PORT", 8080))
DIR = os.path.dirname(os.path.abspath(__file__))

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIR, **kwargs)
    
    def do_GET(self):
        # Serve index.html for all routes (SPA-friendly)
        if self.path.startswith('/data/'):
            super().do_GET()
        elif self.path == '/' or self.path == '/index.html':
            self.path = '/index.html'
            super().do_GET()
        else:
            # Try the file, fall back to index.html
            filepath = os.path.join(DIR, self.path.lstrip('/'))
            if os.path.isfile(filepath):
                super().do_GET()
            else:
                self.path = '/index.html'
                super().do_GET()

if __name__ == '__main__':
    httpd = socketserver.TCPServer(("0.0.0.0", PORT), Handler)
    print(f"Serving Open Ollama on 0.0.0.0:{PORT}")
    httpd.serve_forever()
