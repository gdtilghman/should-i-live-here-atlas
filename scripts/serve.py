"""Local-only gzip preview for the static mockups. Run from any directory."""
import gzip
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT=Path(__file__).resolve().parents[1]/'dist'
cache={}
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        rel=unquote(urlsplit(self.path).path).lstrip('/') or 'index.html'
        target=(ROOT/rel).resolve()
        if not target.is_relative_to(ROOT.resolve()) or not target.is_file():
            self.send_error(404);return
        stat=target.stat()
        compressed='gzip' in self.headers.get('Accept-Encoding','')
        key=(str(target),stat.st_mtime_ns,compressed)
        if key not in cache:
            data=target.read_bytes()
            cache[key]=gzip.compress(data) if compressed else data
        data=cache[key]
        self.send_response(200)
        self.send_header('Content-Type',mimetypes.guess_type(target)[0] or 'application/octet-stream')
        if compressed:self.send_header('Content-Encoding','gzip')
        self.send_header('Vary','Accept-Encoding')
        self.send_header('Cache-Control','no-cache')
        self.send_header('Content-Length',str(len(data)))
        self.end_headers();self.wfile.write(data)
if __name__=='__main__':
    print('Should I Live Here preview: http://127.0.0.1:4173',flush=True)
    ThreadingHTTPServer(('127.0.0.1',4173),Handler).serve_forever()
