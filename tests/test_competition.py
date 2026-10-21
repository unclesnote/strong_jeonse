import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from competition import INTERVAL_MS, RETRY_MS, CompetitionError, CompetitionService, SqliteStore, parse_competition  # noqa: E402
from server import create_server  # noqa: E402

FIXTURE = (ROOT / 'tests/fixtures/lh_competition_2015122300020927.html').read_text(encoding='utf-8')
META = json.loads((ROOT / 'public/competition-config.json').read_text(encoding='utf-8'))


def find_node():
    return os.environ.get('NODE') or shutil.which('node')


class ParserTest(unittest.TestCase):
    def test_parses_supply_table_and_totals(self):
        p = parse_competition(FIXTURE, META)
        self.assertEqual(len(p['groups']), len(META['expectedGroups']))
        self.assertEqual([p['totals'][k] for k in ('supply', 'recruitment', 'applications')], [344, 835, 5222])
        g = next(x for x in p['groups'] if x['groupName'] == '수원고색(디케이타워)')
        self.assertEqual([g['supply'], g['recruitment'], g['applications'], g['supplyRatio']], [3, 10, 102, 34])
        self.assertGreaterEqual(p['sourceRowCount'], len(p['groups']))

    def test_rejects_other_notice_or_changed_dataset(self):
        cases = [(FIXTURE.replace('2015122300020927', '2015122300099999'), META, '일치하지'),
                 (FIXTURE, {**META, 'totalUnits': 343}, '공급호수'),
                 (FIXTURE, {**META, 'expectedGroups': META['expectedGroups'][1:]}, '주택군'),
                 (FIXTURE.replace('htyListTb08', 'other'), META, '신청 현황 표'),
                 (FIXTURE, {**META, 'sourceUrl': 'https://example.com/?panId=' + META['id']}, 'URL')]
        for html, meta, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(CompetitionError, message): parse_competition(html, meta)

    def test_matches_hosted_javascript_parser(self):
        node = find_node()
        if not node: self.skipTest('Node.js 22.5+ 없음: JS 파서 대조 생략(로컬 실행에는 불필요)')
        script = "import {parseCompetition} from './backend/competition.mjs';import {readFileSync} from 'node:fs';process.stdout.write(JSON.stringify(parseCompetition(readFileSync(process.argv[1],'utf8'),JSON.parse(readFileSync(process.argv[2],'utf8')))))"
        out = subprocess.run([node, '--input-type=module', '-e', script, str(ROOT / 'tests/fixtures/lh_competition_2015122300020927.html'), str(ROOT / 'public/competition-config.json')], cwd=ROOT, capture_output=True, text=True, timeout=60, check=True)
        self.assertEqual(json.loads(out.stdout), parse_competition(FIXTURE, META))


class ServiceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.now, self.calls, self.fail = 1_000_000, 0, False
        self.service = CompetitionService(META, SqliteStore(Path(self.tmp.name) / 'c.sqlite'), fetcher=self.fetch, now=lambda: self.now)

    def fetch(self, url):
        self.calls += 1
        if self.fail: raise CompetitionError('LH 원문 응답 HTTP 503')
        return FIXTURE

    def test_fresh_cache_reused_stale_refetched_force_bypasses(self):
        self.assertEqual(self.service.refresh()['status'], 'ok'); self.assertEqual(self.calls, 1)
        self.now += 60_000; self.service.refresh(); self.assertEqual(self.calls, 1)
        self.service.refresh(force=True); self.assertEqual(self.calls, 2)
        self.now += INTERVAL_MS; self.assertEqual(self.service.read()['status'], 'stale')
        self.assertEqual(self.service.refresh()['status'], 'ok'); self.assertEqual(self.calls, 3)

    def test_failure_keeps_last_good_data_and_backs_off(self):
        self.service.refresh(); self.fail = True; self.now += INTERVAL_MS
        view = self.service.refresh()
        self.assertEqual(view['status'], 'stale-error'); self.assertIn('503', view['lastError'])
        self.assertEqual(view['data']['totals']['applications'], 5222)
        self.now += RETRY_MS - 1; self.service.refresh(); self.assertEqual(self.calls, 2)
        self.now += 1; self.service.refresh(); self.assertEqual(self.calls, 3)

    def test_unpublished_is_unavailable_not_zero(self):
        self.fail = True
        view = self.service.refresh()
        self.assertEqual(view['status'], 'unavailable'); self.assertIsNone(view['data'])


class ServerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        site = Path(self.tmp.name) / 'site'; site.mkdir()
        (site / 'index.html').write_text('<!doctype html>ok', encoding='utf-8')
        shutil.copy(ROOT / 'public/competition-config.json', site / 'competition-config.json')
        self.server, _, _ = create_server(site, Path(self.tmp.name) / 'state', port=0, fetcher=lambda url: FIXTURE)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close); self.addCleanup(self.server.shutdown)
        self.base = 'http://127.0.0.1:%d' % self.server.server_address[1]

    def request(self, path, method='GET', headers=None):
        try:
            with urllib.request.urlopen(urllib.request.Request(self.base + path, method=method, headers=headers or {}), timeout=10) as r: return r.status, r.read()
        except urllib.error.HTTPError as e: return e.code, e.read()

    def test_static_and_api(self):
        self.assertEqual(self.request('/'), (200, b'<!doctype html>ok'))
        status, body = self.request('/api/competition')
        self.assertEqual(status, 200); self.assertEqual(json.loads(body)['data']['totals']['applications'], 5222)
        self.assertEqual(self.request('/api/competition/refresh', 'POST')[0], 200)
        self.assertEqual(self.request('/api/competition/refresh')[0], 405)
        self.assertEqual(self.request('/api/competition/refresh', 'POST', {'Origin': 'http://evil.example'})[0], 403)
        self.assertEqual(self.request('/../AGENTS.md')[0], 404)


class NodeHostedSuiteTest(unittest.TestCase):
    def test_node_suite(self):
        node = find_node()
        if not node: self.skipTest('Node.js 22.5+ 없음: 호스팅 Worker용 JS 테스트 생략(로컬 실행에는 불필요)')
        result = subprocess.run([node, '--test', str(ROOT / 'tests/competition.test.mjs')], cwd=ROOT, capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
