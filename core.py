"""Provider and result model, independent of the desktop interface."""
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlencode, urlsplit


def normalize_domain(value):
    value = value.strip()
    parsed = urlsplit(value if '://' in value else 'https://' + value)
    host = (parsed.hostname or '').lower().rstrip('.').removeprefix('www.')
    try:
        host = host.encode('idna').decode('ascii')
    except UnicodeError:
        raise ValueError('请输入有效域名。')
    if not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?', host) or '.' not in host or '..' in host:
        raise ValueError('请输入有效域名，例如 book2audiogo.com。')
    return host


def matches(url, domain):
    try:
        host = normalize_domain(url)
        return host == domain or host.endswith('.' + domain)
    except ValueError:
        return False


@dataclass
class RankResult:
    domain: str
    country: str
    language: str
    keyword: str
    checked_at: str
    position: int | None = None
    url: str = ''
    status: str = 'ok'
    detail: str = ''
    provider: str = 'playwright-google'
    device: str = 'desktop'
    depth: int = 100


