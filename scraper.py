"""Visible Chromium scraper. Challenges are handled by the user, never bypassed."""
import time
import os
import sys
from pathlib import Path
import random
import json
from datetime import datetime, timezone
from urllib.parse import urlencode, urlsplit, parse_qs
from core import RankResult, matches

from google_parser import read_results, next_url, is_challenge


class GoogleBrowserProvider:
    def __init__(self, notify=lambda message: None):
        self.notify = notify

    def __enter__(self):
        if getattr(sys, 'frozen', False):
            os.environ['PLAYWRIGHT_BROWSERS_PATH'] = str(Path(sys._MEIPASS) / 'browsers')
        elif (Path(__file__).parent / 'browsers').is_dir():
            os.environ['PLAYWRIGHT_BROWSERS_PATH'] = str(Path(__file__).parent / 'browsers')
        from playwright.sync_api import sync_playwright
        self.runtime = sync_playwright().start()
        try:
            self.data_root = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).parent
            self.context = self.runtime.chromium.launch_persistent_context(
                str(self.data_root / 'browser-profile'), headless=False,
                viewport={'width': 1280, 'height': 900})
            self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
        except Exception:
            self.runtime.stop()
            raise
        return self

    def __exit__(self, *args):
        try:
            self.context.close()
        finally:
            self.runtime.stop()

    def read_results(self):
        return read_results(self.page)

    def diagnostics(self, reason):
        try:
            directory = self.data_root / 'diagnostics'
            directory.mkdir(exist_ok=True)
            details = self.page.evaluate('''() => ({url: location.href, title: document.title,
                headings: document.querySelectorAll('h3').length,
                roots: ['search','rso','main'].filter(id => document.getElementById(id)),
                headingLinks: [...document.querySelectorAll('h3')].slice(0,15).map(h => ({
                    text: h.innerText, html: h.outerHTML, parent: h.parentElement.outerHTML.slice(0,1500)}))})''')
            details['reason'] = reason
            (directory / 'last-page.json').write_text(json.dumps(details, ensure_ascii=False, indent=2), encoding='utf-8')
            self.page.screenshot(path=str(directory / 'last-page.png'))
        except Exception:
            pass

    def scroll_results(self, cancel):
        self.notify('搜索页面已打开，正在向下滚动并读取结果…')
        # Ordinary scrolling triggers lazy loading; no stealth or CAPTCHA bypass.
        for _ in range(12):
            if cancel.is_set():
                break
            at_bottom = self.page.evaluate('''() => {
                window.scrollBy(0, Math.max(600, innerHeight * 0.8));
                return scrollY + innerHeight >= document.documentElement.scrollHeight - 10;
            }''')
            self.page.wait_for_timeout(300)
            if at_bottom:
                break

    def wait_for_results(self, cancel):
        deadline = time.monotonic() + 20
        manual_deadline = None
        was_challenged = False
        while not cancel.is_set():
            if self.page.is_closed():
                raise RuntimeError('查询浏览器已关闭。')
            try:
                # A hidden/stale CAPTCHA iframe must not block a loaded result page.
                links = self.read_results()
                if links and '/sorry/' not in self.page.url and 'consent.google.' not in self.page.url:
                    return links, 'ok'
                challenged = is_challenge(self.page)
            except Exception:
                # Manual completion can destroy the old document during navigation.
                if time.monotonic() >= (manual_deadline or deadline):
                    return [], 'blocked' if manual_deadline else 'incomplete'
                self.page.wait_for_timeout(300)
                continue
            if challenged:
                was_challenged = True
                if manual_deadline is None:
                    manual_deadline = time.monotonic() + 180
                    self.notify('请在浏览器手动处理验证码，完成后自动继续…')
                if time.monotonic() >= manual_deadline:
                    return [], 'blocked'
            else:
                if was_challenged:
                    self.notify('验证码已完成，正在识别搜索页面…')
                    deadline = time.monotonic() + 20
                    manual_deadline = None
                    was_challenged = False
                if time.monotonic() >= deadline:
                    return [], 'incomplete'
            self.page.wait_for_timeout(500)
        return [], 'cancelled'

    def check(self, domain, country, language, keyword, cancel, depth=100):
        result = RankResult(domain, country, language, keyword, datetime.now(timezone.utc).isoformat())
        result.depth = depth
        seen = set()
        target = 'https://www.google.com/search?' + urlencode(dict(q=keyword, gl=country, hl=language, pws=0))
        for page_number in range(15):
            if cancel.is_set():
                result.status, result.detail = 'cancelled', '已取消'
                return result
            self.notify(f'正在读取「{keyword}」第 {page_number + 1} 页…')
            try:
                self.page.goto(target,
                               wait_until='domcontentloaded', timeout=30000)
            except Exception:
                raise RuntimeError('Google 页面加载失败，请检查网络是否能访问 Google。') from None
            links, state = self.wait_for_results(cancel)
            if state in ('blocked', 'cancelled'):
                result.status, result.detail = state, '手动处理超时' if state == 'blocked' else '已取消'
                return result
            if not links:
                self.diagnostics('搜索页面未识别到结果')
                result.status, result.detail = 'incomplete', f'仅解析到 {len(seen)} 条；页面无结果或结构变化'
                return result
            self.scroll_results(cancel)
            links = self.read_results() or links
            added = 0
            for url in links:
                if url in seen:
                    continue
                seen.add(url)
                added += 1
                if matches(url, domain):
                    result.position, result.url = len(seen), url
                    return result
                if len(seen) == depth:
                    result.detail = f'已读取前 {depth} 条解析结果，未找到域名'
                    return result
            self.notify(f'第 {page_number + 1} 页读取 {added} 条，累计 {len(seen)} 条')
            target = next_url(self.page)
            if not added or not target:
                if not target:
                    self.diagnostics('未识别到下一页链接')
                break
            self.notify(f'已读取 {len(seen)} 条，等待几秒后翻页…')
            until = time.monotonic() + random.uniform(4, 7)
            while time.monotonic() < until and not cancel.is_set():
                self.page.wait_for_timeout(200)
        result.status, result.detail = 'incomplete', f'仅解析到 {len(seen)} 条结果，未找到域名'
        return result
