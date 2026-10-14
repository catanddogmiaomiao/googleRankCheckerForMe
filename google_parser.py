"""Google DOM selectors and link normalization; update this module when layout changes."""
from urllib.parse import urlsplit, parse_qs, urljoin
import re

EXTRACT_SCRIPT = r'''() => {
  const root = document.querySelector('#search') || document.querySelector('#rso') || document.querySelector('#main');
  if (!root) return [];
  const results = [];
  for (const title of root.querySelectorAll('h3')) {
    const a = title.closest('a') || title.querySelector('a') || title.parentElement.querySelector('a[href]');
    if (!a || !title.getClientRects().length) continue;
    if (a.closest('#tads, #tadsb, [data-text-ad], [data-google-query-id]')) continue;
    results.push(a.href);
  }
  return results;
}'''


def destination(url):
    parsed = urlsplit(url)
    if parsed.hostname and (parsed.hostname == 'google.com' or parsed.hostname.endswith('.google.com')):
        if parsed.path == '/url':
            params = parse_qs(parsed.query)
            url = (params.get('q') or params.get('url') or [''])[0]
        else:
            return ''
    return url if url.startswith(('https://', 'http://')) else ''


def read_results(page):
    return [link for link in map(destination, page.evaluate(EXTRACT_SCRIPT)) if link]

def has_next(page):
    return bool(next_url(page))


def click_next(page):
    """Click the actual Next control, with pagination URL as a fallback."""
    control = page.locator('a#pnnext:visible').first
    if not control.count():
        control = page.get_by_role('link', name=re.compile(r'^(Next|下一页|下页|次へ|Suivant|Weiter)(\s|$)', re.I)).first
    before = page.url
    if control.count() and control.is_visible():
        control.scroll_into_view_if_needed(timeout=5000)
        control.click(timeout=10000)
    else:
        target = next_url(page)
        if not target:
            return False
        page.goto(target, wait_until='domcontentloaded', timeout=30000)
    page.wait_for_function('(old) => location.href !== old', arg=before, timeout=15000)
    page.wait_for_load_state('domcontentloaded', timeout=15000)
    return True


def next_url(page):
    current = int(parse_qs(urlsplit(page.url).query).get('start', ['0'])[0])
    candidates = page.locator('a#pnnext, a[href*="start="]').evaluate_all(
        '(links) => links.filter(a => a.getClientRects().length).map(a => a.href)')
    valid = []
    for href in candidates:
        parsed = urlsplit(urljoin(page.url, href))
        query = parse_qs(parsed.query)
        try:
            offset = int(query.get('start', ['0'])[0])
        except ValueError:
            continue
        if ((parsed.hostname or '').removeprefix('www.') == (urlsplit(page.url).hostname or '').removeprefix('www.') and parsed.path == '/search'
                and (not query.get('q') or query.get('q') == parse_qs(urlsplit(page.url).query).get('q'))
                and offset > current):
            valid.append((offset, parsed.geturl()))
    return min(valid)[1] if valid else ''

def is_challenge(page):
    return ("/sorry/" in page.url or "consent.google." in page.url
            or page.locator('iframe[src*="recaptcha"]:visible, form[action*="/sorry/"]:visible').count() > 0)
