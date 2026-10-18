"""Serve the actual production build under the GitHub Pages subroute for QA."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import shutil

from scripts.market import ROOT

if __name__ == '__main__':
    target = ROOT / '.cache/preview/rrg-kiko'
    target.mkdir(parents=True, exist_ok=True)
    shutil.copytree(ROOT / 'dist', target, dirs_exist_ok=True)
    handler = partial(SimpleHTTPRequestHandler, directory=str(target.parent))
    ThreadingHTTPServer(('127.0.0.1', 4173), handler).serve_forever()
