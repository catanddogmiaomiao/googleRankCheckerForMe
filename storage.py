"""Local history, scoped by domain, country, language, device and depth."""
import sqlite3
import sys
from contextlib import closing
from pathlib import Path


class History:
    def __init__(self, path=None):
        directory = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).parent
        self.path = path or directory / 'rankings.sqlite3'
        with closing(sqlite3.connect(self.path)) as db:
            db.execute('''CREATE TABLE IF NOT EXISTS rankings (
                id INTEGER PRIMARY KEY, checked_at TEXT, domain TEXT, country TEXT,
                language TEXT, keyword TEXT, position INTEGER, url TEXT,
                status TEXT, detail TEXT, device TEXT, depth INTEGER)''')
            db.commit()

    def previous(self, result):
        with closing(sqlite3.connect(self.path)) as db:
            return db.execute('''SELECT position, checked_at FROM rankings
                WHERE domain=? AND country=? AND language=? AND keyword=?
                AND device=? AND depth=? AND status='ok' ORDER BY id DESC LIMIT 1''',
                (result.domain, result.country, result.language, result.keyword,
                 result.device, result.depth)).fetchone()

    def save(self, result):
        with closing(sqlite3.connect(self.path)) as db:
            db.execute('''INSERT INTO rankings
                (checked_at,domain,country,language,keyword,position,url,status,detail,device,depth)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
                (result.checked_at, result.domain, result.country, result.language,
                 result.keyword, result.position, result.url, result.status,
                 result.detail, result.device, result.depth))
            db.commit()


def comparison(result, previous):
    if previous is None:
        return '—', '—'
    old = previous[0]
    old_text = str(old) if old is not None else f'>{result.depth}'
    if result.status != 'ok':
        return old_text, '—'
    new = result.position
    if new is None and old is None:
        return old_text, '未进入范围'
    if old is None:
        return old_text, '进入范围 ↑'
    if new is None:
        return old_text, '离开范围 ↓'
    delta = old - new
    return old_text, f'↑ {delta}' if delta > 0 else f'↓ {-delta}' if delta < 0 else '持平'
