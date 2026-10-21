"""지도 사이트 + 청약 경쟁률 API 로컬 서버. 표준 라이브러리만 사용한다.

    python backend/server.py --directory public --state-dir data/runtime --port 8765

GET  /api/competition          캐시된 신청 현황. 30분이 지났으면 백엔드가 다시 조회한다.
POST /api/competition/refresh  캐시를 무시하고 즉시 조회한다(동일 출처만 허용).
그 밖의 경로는 --directory의 정적 파일이다. 백그라운드 스레드가 30분마다 갱신한다.
"""
import argparse
import json
import sys
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from competition import INTERVAL_MS, CompetitionService, SqliteStore  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


class Handler(SimpleHTTPRequestHandler):
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map, '.js': 'application/javascript; charset=utf-8', '.json': 'application/json; charset=utf-8', '.webp': 'image/webp', '.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8'}

    def __init__(self, *args, service=None, service_error=None, **kwargs):
        self.service, self.service_error = service, service_error
        super().__init__(*args, **kwargs)

    def send_json(self, body, status=200, extra=None):
        data = json.dumps(body, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        for k, v in {'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store', 'Content-Length': str(len(data)), **(extra or {})}.items(): self.send_header(k, v)
        self.end_headers(); self.wfile.write(data)

    def api(self, method):
        path = self.path.split('?', 1)[0]
        if path not in ('/api/competition', '/api/competition/refresh'): return False
        if not self.service: self.send_json({'error': self.service_error}, 503); return True
        if method == 'GET' and path == '/api/competition':
            result = self.service.read()
            if result['status'] != 'ok': result = self.service.refresh()
            self.send_json(result); return True
        if method != 'POST' or path != '/api/competition/refresh':
            self.send_json({'error': 'Method not allowed'}, 405, {'Allow': 'POST' if path.endswith('/refresh') else 'GET'}); return True
        origin = self.headers.get('Origin')
        if origin and origin != 'http://' + (self.headers.get('Host') or ''): self.send_json({'error': 'Origin not allowed'}, 403); return True
        result = self.service.refresh(force=True)
        self.send_json(result, 502 if result['status'] == 'unavailable' else 200); return True

    def do_GET(self):
        if not self.api('GET'): super().do_GET()

    def do_HEAD(self):
        if not self.api('HEAD'): super().do_HEAD()

    def do_POST(self):
        if not self.api('POST'): self.send_error(405)

    def log_message(self, fmt, *args):
        if self.path.startswith('/api/'): super().log_message(fmt, *args)


def create_server(directory, state_dir, port=8765, bind='127.0.0.1', fetcher=None):
    directory = Path(directory).resolve()
    if not (directory / 'index.html').is_file(): raise SystemExit(f'사이트 폴더가 아닙니다(index.html 없음): {directory}')
    service, error = None, None
    config = directory / 'competition-config.json'
    if config.is_file():
        meta = json.loads(config.read_text(encoding='utf-8'))
        store = SqliteStore(Path(state_dir) / 'competition.sqlite')
        service = CompetitionService(meta, store, **({'fetcher': fetcher} if fetcher else {}))
    else:
        error = 'competition-config.json이 없어 경쟁률을 조회하지 않습니다. 데이터셋을 다시 activate하세요.'
    server = ThreadingHTTPServer((bind, port), partial(Handler, directory=str(directory), service=service, service_error=error))
    server.daemon_threads = True
    return server, service, error


def refresh_loop(service, stop):
    service.refresh()
    while not stop.wait(INTERVAL_MS / 1000):
        try: service.refresh(force=True)
        except Exception as e: print('경쟁률 갱신 실패:', e, file=sys.stderr)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--directory', default=str(ROOT / 'public')); p.add_argument('--state-dir', default=str(ROOT / 'data/runtime'))
    p.add_argument('--port', type=int, default=8765); p.add_argument('--bind', default='127.0.0.1')
    args = p.parse_args(argv)
    server, service, error = create_server(args.directory, args.state_dir, args.port, args.bind)
    stop = threading.Event()
    if service: threading.Thread(target=refresh_loop, args=(service, stop), daemon=True).start()
    host, port = server.server_address[:2]
    print(f'지도: http://{"localhost" if host in ("127.0.0.1", "0.0.0.0") else host}:{port}/', flush=True)
    print(f'사이트 폴더: {Path(args.directory).resolve()}', flush=True)
    print(f'경쟁률 소스: {service.url}\n경쟁률: 위 LH 원문을 30분마다 조회합니다(설정: competition-config.json).' if service else '경쟁률: ' + error, flush=True)
    print('종료: Ctrl+C', flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: stop.set(); server.server_close()


if __name__ == '__main__':
    main()
