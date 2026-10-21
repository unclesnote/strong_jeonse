"""start_site.sh·delete_site.sh 보조: 사이트 목록과 실행 중인 backend/server.py 프로세스를 찾는다.

    python scripts/site_procs.py [사이트폴더 ...]      실행 중 서버(TSV: PID, 사이트 폴더, bind, port)
    python scripts/site_procs.py --sites [runs폴더 ...]  사이트 목록(TSV: 경로, 설명, 경쟁률 소스, 실행 상태)

서버는 PID 파일 없이 /proc의 `backend/server.py --directory` 인자로 찾으므로 수동으로 띄운 서버도 찾는다.
/proc이 없는 OS에서는 실행 중 서버를 찾지 못한다. 사이트 목록은 작업공간 public/이 먼저, 실행 폴더는 최신순이다.
"""
import json
import os
import sys
from pathlib import Path


def options(args):
    found = {}
    for i, a in enumerate(args):
        if a.startswith('--') and '=' in a: k, v = a.split('=', 1); found[k] = v
        elif a.startswith('--') and i + 1 < len(args): found[a] = args[i + 1]
    return found


def servers():
    proc = Path('/proc')
    if not proc.is_dir(): return
    for entry in proc.iterdir():
        if not entry.name.isdigit() or int(entry.name) == os.getpid(): continue
        try:
            argv = [a.decode('utf-8', 'replace') for a in (entry / 'cmdline').read_bytes().split(b'\0') if a]
            cwd = Path(os.readlink(entry / 'cwd'))
        except OSError:
            continue
        script = next((i for i, a in enumerate(argv) if Path(a).name == 'server.py' and Path(a).parent.name == 'backend'), None)
        if script is None or not any('python' in Path(a).name for a in argv[:script]): continue
        opts = options(argv[script + 1:])
        server = (cwd / argv[script]).resolve()
        directory = (cwd / opts.get('--directory', str(server.parents[1] / 'public'))).resolve()
        yield int(entry.name), directory, opts.get('--bind', '127.0.0.1'), opts.get('--port', '8765')


def sites(runs_dirs):
    """사이트 폴더(index.html·data.js)마다 (절대경로, 설명, 경쟁률 소스 URL, 실행 중 주소) 행."""
    host = lambda b: 'localhost' if b in ('127.0.0.1', '0.0.0.0', '') else b
    running = {}
    for pid, directory, bind, port in servers(): running.setdefault(directory, []).append(f'http://{host(bind)}:{port}/ (PID {pid})')

    def row(d, label):
        d = d.resolve()
        try:
            c = json.loads((d / 'competition-config.json').read_text(encoding='utf-8')); title, source = c['title'], c['sourceUrl']
        except Exception:
            title, source = '(제목 없음)', '(경쟁률 설정 없음 — 소스 URL 미등록)'
        return f"{d}\t{label} {title}\t{source}\t{', '.join(running.get(d, []))}"

    ok = lambda d: (d / 'index.html').is_file() and (d / 'data.js').is_file()
    rows = [row(Path('public'), '[현재 작업공간]')] if ok(Path('public')) else []
    runs = []
    for base in runs_dirs:
        for d in Path(base).glob('*/site/dist'):
            if not ok(d): continue
            try: status = json.loads((d.parents[1] / 'reports/run.json').read_text(encoding='utf-8')).get('status', '?')
            except Exception: status = '?'
            runs.append((d.stat().st_mtime, row(d, f'[{d.parents[1].name} · {status}]')))
    return rows + [r for _, r in sorted(runs, reverse=True)]


if __name__ == '__main__':
    if sys.argv[1:2] == ['--sites']:
        print('\n'.join(sites(sys.argv[2:])))
    else:
        wanted = {Path(p).resolve() for p in sys.argv[1:]}
        for pid, directory, bind, port in servers():
            if not wanted or directory in wanted: print(f'{pid}\t{directory}\t{bind}\t{port}')
