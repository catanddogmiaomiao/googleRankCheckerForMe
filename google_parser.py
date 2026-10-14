"""Google DOM selectors and link normalization; update this module when layout changes."""
from urllib.parse import urlsplit, parse_qs

EXTRACT_SCRIPT = r'''() => {
  const root = document.querySelector('#search');
  if (!root) return [];
  const results = [];
  for (const title of root.querySelectorAll('h3')) {
    const a = title.closest('a');
    if (!a || !title.getClientRects().length) continue;
    if (a.closest('#tads, #tadsb, [data-text-ad], [data-google-query-id]')) continue;
    // Google organic web results generally use one of these containers.
    if (!title.closest('.MjjYud, .g, [data-sokoban-container]')) continue;
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
    return bool(page.locator("a#pnnext").count())

def is_challenge(page):
    return ("/sorry/" in page.url or "consent.google." in page.url
            or page.locator('iframe[src*="recaptcha"], form[action*="/sorry/"]').count() > 0)
