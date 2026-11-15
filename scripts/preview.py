"""Loopback-only design preview. Serves only preview files and original artwork, never TV data."""
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import unquote,urlsplit
import argparse

ROOT=Path(__file__).resolve().parents[1]
class Preview(SimpleHTTPRequestHandler):
 def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(ROOT),**kwargs)
 def do_GET(self):
  path=unquote(urlsplit(self.path).path).lstrip('/')
  if path=='':
   self.send_response(302);self.send_header('Location','/preview/native.html');self.end_headers();return
  target=(ROOT/path).resolve()
  allowed=any(target.is_relative_to(ROOT/prefix) for prefix in ['preview','src/Cove.Native/assets'])
  if not allowed or not target.is_file():self.send_error(404);return
  super().do_GET()
parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8770);args=parser.parse_args()
server=ThreadingHTTPServer(('127.0.0.1',args.port),Preview)
print(f'Cove layout preview: http://127.0.0.1:{args.port}/',flush=True)
try:server.serve_forever()
except KeyboardInterrupt:pass
finally:server.server_close()
