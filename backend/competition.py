"""LH 신청 현황(경쟁률) 파서와 30분 캐시 서비스. 표준 라이브러리만 사용한다.

backend/competition.mjs(호스팅 Worker)와 같은 규칙·같은 JSON을 만든다.
두 구현의 결과는 tests/test_competition.py가 같은 원문 픽스처로 대조한다.
"""
import html as htmllib
import json
import re
import sqlite3
import threading
import time
import unicodedata
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

INTERVAL_MS = 30 * 60 * 1000
RETRY_MS = 5 * 60 * 1000
LOCK_MS = 45 * 1000
MAX_BYTES = 4 * 1024 * 1024
FIELDS = ('supply', 'recruitment', 'applications')


class CompetitionError(Exception):
    pass


def clean(s):
    return re.sub(r'\s+', ' ', htmllib.unescape(re.sub(r'<[^>]*>', ' ', str(s)))).strip()


def group_key(s):
    return re.sub(r'\s+', '', unicodedata.normalize('NFC', str(s)))


def count(text):
    value = clean(text)
    if value in ('', '-', '—', '미공개'): return None
    if not re.fullmatch(r'\d[\d,]*', value): raise CompetitionError('신청 현황 숫자 형식이 바뀌었습니다.')
    return int(value.replace(',', ''))


def notice_id(meta):
    return str(meta.get('id') or meta.get('noticeId'))


def source_for(meta):
    url = urlsplit(meta['sourceUrl'])
    if url.scheme != 'https' or url.hostname != 'apply.lh.or.kr' or url.port or url.path != '/lhapply/apply/wt/wrtanc/selectWrtancInfo.do' or url.username or url.password:
        raise CompetitionError('지원하지 않는 LH 원문 URL입니다.')
    ids = parse_qs(url.query).get('panId', [])
    if len(ids) != 1 or ids[0] != notice_id(meta) or not ids[0].isdigit(): raise CompetitionError('데이터와 원문 공고 ID가 다릅니다.')
    return meta['sourceUrl']


def ratio(applications, base):
    return applications / base if applications is not None and base else None


def parse_competition(html, meta):
    source_url, nid = source_for(meta), notice_id(meta)
    notice = re.search(r'<input\b(?=[^>]*\bname\s*=\s*["\']panId["\'])(?=[^>]*\bvalue\s*=\s*["\']([^"\']+)["\'])[^>]*>', html, re.I)
    if not notice or notice.group(1) != nid: raise CompetitionError('응답이 요청한 LH 공고와 일치하지 않습니다.')
    table = re.search(r'<table\b[^>]*\bid\s*=\s*["\']htyListTb08["\'][^>]*>([\s\S]*?)</table>', html, re.I)
    if not table: raise CompetitionError('지원하는 신청 현황 표가 없습니다. 원문 구조 또는 공개 여부를 확인하세요.')
    head = re.search(r'<thead\b[^>]*>([\s\S]*?)</thead>', table.group(1), re.I)
    head = head.group(1) if head else ''
    for label in ('공급호수', '모집인원', '신청건수'):
        if label not in clean(head): raise CompetitionError('신청 현황 표의 열 구성이 바뀌었습니다.')
    totals_row = next((r for r in re.findall(r'<tr\b[^>]*>([\s\S]*?)</tr>', head, re.I) if clean(r).startswith('합계')), None)
    total_cells = [clean(c) for c in re.findall(r'<th\b[^>]*>([\s\S]*?)</th>', totals_row, re.I)] if totals_row else []
    body = re.search(r'<tbody\b[^>]*>([\s\S]*?)</tbody>', table.group(1), re.I)
    if not body: raise CompetitionError('신청 현황 행이 없습니다.')
    rows = []
    for tr in re.findall(r'<tr\b[^>]*>([\s\S]*?)</tr>', body.group(1), re.I):
        cells = {k: clean(v) for k, v in re.findall(r'<td\b[^>]*\bdata-th-code\s*=\s*["\'](\d+)["\'][^>]*>([\s\S]*?)</td>', tr, re.I)}
        if not cells.get('1'): continue
        if not all(k in cells for k in ('2', '3', '4')): raise CompetitionError('일부 신청 현황 행의 열이 누락되었습니다.')
        rows.append({'groupName': cells['1'], 'supply': count(cells['2']), 'recruitment': count(cells['3']), 'applications': count(cells['4'])})
    if not rows: raise CompetitionError('주택군 신청 현황이 비어 있습니다.')
    # 같은 주택군이 여러 행이면 합산한다. 한 행이라도 미공개면 그 수치는 null이다.
    groups = {}
    for row in rows:
        key = group_key(row['groupName'])
        g = groups.setdefault(key, {'groupName': row['groupName'], 'key': key, 'supply': 0, 'recruitment': 0, 'applications': 0, 'sourceRowCount': 0})
        for k in FIELDS: g[k] = None if g[k] is None or row[k] is None else g[k] + row[k]
        g['sourceRowCount'] += 1
    groups = [{**g, 'supplyRatio': ratio(g['applications'], g['supply']), 'recruitmentRatio': ratio(g['applications'], g['recruitment'])} for g in groups.values()]
    totals = {k: None if any(g[k] is None for g in groups) else sum(g[k] for g in groups) for k in FIELDS}
    if len(total_cells) != 4: raise CompetitionError('공급정보 합계 행을 확인할 수 없습니다.')
    for i, k in enumerate(FIELDS):
        if count(total_cells[i + 1]) != totals[k]: raise CompetitionError('신청 현황 합계가 개별 행과 다릅니다.')
    if isinstance(meta.get('expectedGroups'), list) and {g['key'] for g in groups} != {group_key(x) for x in meta['expectedGroups']}:
        raise CompetitionError('원문 주택군과 현재 데이터셋이 다릅니다. 데이터 교체를 확인하세요.')
    if isinstance(meta.get('totalUnits'), int) and meta['totalUnits'] != totals['supply']:
        raise CompetitionError('원문 공급호수가 현재 주택목록과 다릅니다. 정정 자료를 확인하세요.')
    return {'noticeId': nid, 'sourceUrl': source_url, 'scope': 'housing-group', 'groups': groups, 'sourceRowCount': len(rows),
            'totals': {**totals, 'supplyRatio': ratio(totals['applications'], totals['supply']), 'recruitmentRatio': ratio(totals['applications'], totals['recruitment'])}}


class SqliteStore:
    """competition.mjs의 D1 스키마와 같은 테이블. 연결은 요청마다 새로 연다."""
    SCHEMA = 'CREATE TABLE IF NOT EXISTS competition_cache (notice_id TEXT PRIMARY KEY,payload TEXT,last_success INTEGER,last_attempt INTEGER,last_error TEXT,lock_until INTEGER NOT NULL DEFAULT 0,lock_token TEXT)'

    def __init__(self, path):
        self.path = str(path); Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db: db.execute('PRAGMA journal_mode=WAL'); db.execute(self.SCHEMA)

    def connect(self):
        db = sqlite3.connect(self.path, timeout=5); db.row_factory = sqlite3.Row; return db

    def read(self, nid):
        with self.connect() as db:
            row = db.execute('SELECT * FROM competition_cache WHERE notice_id=?', (nid,)).fetchone()
        return dict(row) if row else None

    def acquire(self, nid, now, token):
        with self.connect() as db:
            db.execute('INSERT OR IGNORE INTO competition_cache(notice_id) VALUES (?)', (nid,))
            return db.execute('UPDATE competition_cache SET lock_until=?,lock_token=?,last_attempt=? WHERE notice_id=? AND lock_until<=?', (now + LOCK_MS, token, now, nid, now)).rowcount == 1

    def save(self, nid, token, payload, now):
        with self.connect() as db:
            db.execute('UPDATE competition_cache SET payload=?,last_success=?,last_attempt=?,last_error=NULL,lock_until=0,lock_token=NULL WHERE notice_id=? AND lock_token=?', (payload, now, now, nid, token))

    def fail(self, nid, token, now, message):
        with self.connect() as db:
            db.execute('UPDATE competition_cache SET last_attempt=?,last_error=?,lock_until=0,lock_token=NULL WHERE notice_id=? AND lock_token=?', (now, message, nid, token))


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise CompetitionError('LH 원문이 다른 주소로 이동했습니다.')


def fetch_html(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'LHNoticeMap/1.0', 'Accept': 'text/html', 'Cache-Control': 'no-cache'})
    try:
        with urllib.request.build_opener(_NoRedirect).open(request, timeout=25) as response:
            data = response.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as e:
        raise CompetitionError(f'LH 원문 응답 HTTP {e.code}') from e
    except TimeoutError as e:
        raise CompetitionError('LH 원문 조회 시간 초과') from e
    except urllib.error.URLError as e:
        raise CompetitionError('LH 원문 연결 실패: ' + str(e.reason)) from e
    if len(data) > MAX_BYTES: raise CompetitionError('LH 응답 크기가 예상 범위를 초과했습니다.')
    return data.decode('utf-8')


def iso(ms):
    return datetime.fromtimestamp(ms / 1000, timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z') if ms else None


class CompetitionService:
    def __init__(self, meta, store, fetcher=fetch_html, now=lambda: int(time.time() * 1000)):
        self.meta, self.url, self.store, self.fetcher, self.now = meta, source_for(meta), store, fetcher, now
        self.id = notice_id(meta); self._lock = threading.Lock(); self._pending = None

    def view(self, record):
        record = record or {}
        payload = json.loads(record['payload']) if record.get('payload') else None
        success = record.get('last_success')
        if payload: status = 'stale-error' if record.get('last_error') else 'stale' if self.now() - success >= INTERVAL_MS else 'ok'
        else: status = 'unavailable' if record.get('last_error') else 'pending'
        return {'schemaVersion': '1.0.0', 'noticeId': self.id, 'sourceUrl': self.url, 'intervalMinutes': 30, 'status': status,
                'lastSuccessAt': iso(success), 'lastAttemptAt': iso(record.get('last_attempt')), 'nextRefreshAt': iso(success + INTERVAL_MS) if success else None,
                'lastError': record.get('last_error'), 'data': payload}

    def read(self):
        return self.view(self.store.read(self.id))

    def refresh(self, force=False):
        # 동시 요청은 진행 중인 한 번의 조회를 기다려 같은 결과를 받는다.
        with self._lock:
            pending = self._pending
            if pending is None: self._pending = pending = threading.Event(); owner = True
            else: owner = False
        if not owner:
            pending.wait(60); return self.read()
        try:
            return self._perform(force)
        finally:
            with self._lock: self._pending = None
            pending.set()

    def _perform(self, force):
        now, prior = self.now(), self.store.read(self.id)
        if not force and prior:
            if prior.get('last_success') and now - prior['last_success'] < INTERVAL_MS: return self.view(prior)
            # 실패 후에는 폴링하는 화면이 LH를 반복 호출하지 않도록 5분 쉰다.
            if prior.get('last_error') and now - (prior.get('last_attempt') or 0) < RETRY_MS: return self.view(prior)
        token = str(uuid.uuid4())
        if not self.store.acquire(self.id, now, token): return {**self.read(), 'refreshing': True}
        try:
            parsed = parse_competition(self.fetcher(self.url), self.meta)
            self.store.save(self.id, token, json.dumps(parsed, ensure_ascii=False), self.now())
        except Exception as e:
            message = str(e) if isinstance(e, CompetitionError) else f'{type(e).__name__}: {e}'
            self.store.fail(self.id, token, self.now(), message[:220])
        return self.read()
