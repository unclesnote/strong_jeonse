"""start_site.sh 보조: 실행 중인 backend/server.py 프로세스를 /proc에서 찾는다.

    python scripts/site_procs.py [사이트폴더 ...]

출력(TSV): PID, 사이트 폴더(절대경로), bind, port. 사이트 폴더를 주면 그 사이트만 출력한다.
PID 파일을 쓰지 않으므로 수동으로 띄운 서버도 찾는다. /proc이 없는 OS에서는 아무것도 출력하지 않는다.
"""
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


if __name__ == '__main__':
    wanted = {Path(p).resolve() for p in sys.argv[1:]}
    for pid, directory, bind, port in servers():
        if not wanted or directory in wanted: print(f'{pid}\t{directory}\t{bind}\t{port}')
