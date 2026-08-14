#!/usr/bin/env python3
"""Static server for OllamaStats dashboard + daily self-update."""
import http.server
import socketserver
import os
import sys
import threading
import time

PORT = int(os.environ.get("PORT", 8080))
DIR = os.path.dirname(os.path.abspath(__file__))
SCRAPE_INTERVAL = 24 * 3600  # 24 hours


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIR, **kwargs)

    def do_GET(self):
        if self.path.startswith('/data/'):
            super().do_GET()
        elif self.path == '/' or self.path == '/index.html':
            self.path = '/index.html'
            super().do_GET()
        else:
            filepath = os.path.join(DIR, self.path.lstrip('/'))
            if os.path.isfile(filepath):
                super().do_GET()
            else:
                self.path = '/index.html'
                super().do_GET()


def run_update():
    """Import and run the full scrape + rebuild pipeline."""
    # Add DIR to path so daily_update can find it
    if DIR not in sys.path:
        sys.path.insert(0, DIR)

    try:
        from daily_update import (
            scrape_ollama_models,
            scrape_benchmarks,
            scrape_context_windows,
            rebuild_dashboard,
            print_summary,
            OWNER_MAP,
        )

        print("[update] Scraping models...")
        models = scrape_ollama_models()
        print(f"[update] {len(models)} models found")

        print("[update] Scraping benchmarks...")
        benchmarks = scrape_benchmarks()
        print(f"[update] {len(benchmarks)} benchmarks")

        print("[update] Enriching owners...")
        for m in models:
            if 'owner' not in m or not m['owner']:
                m['owner'] = OWNER_MAP.get(m['name'],
                                           m['name'].split('-')[0].split('_')[0].title())

        print("[update] Scraping context windows...")
        ctx_map = scrape_context_windows(models)
        for m in models:
            ctx = ctx_map.get(m['name'], [])
            if ctx:
                m['ctx'] = ctx

        print("[update] Rebuilding dashboard...")
        rebuild_dashboard(models, benchmarks)
        print("[update] Done.")
    except Exception as e:
        print(f"[update] ERROR: {e}", flush=True)


def update_loop():
    """Run the update once at startup then every 24h."""
    time.sleep(5)  # Let the web server start first
    run_update()
    while True:
        time.sleep(SCRAPE_INTERVAL)
        run_update()


if __name__ == '__main__':
    # Start the daily scraper in background
    t = threading.Thread(target=update_loop, daemon=True)
    t.start()

    httpd = socketserver.TCPServer(("0.0.0.0", PORT), Handler)
    print(f"Serving OllamaStats on 0.0.0.0:{PORT}", flush=True)
    httpd.serve_forever()
