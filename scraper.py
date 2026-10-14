"""Visible Chromium scraper. Challenges are handled by the user, never bypassed."""
import time
import os
import sys
from pathlib import Path
import random
from datetime import datetime, timezone
from urllib.parse import urlencode, urlsplit, parse_qs
from core import RankResult, matches

from google_parser import read_results, has_next, is_challenge


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
            self.browser = self.runtime.chromium.launch(headless=False)
            self.context = self.browser.new_context(viewport={'width': 1280, 'height': 900})
            self.page = self.context.new_page()
        except Exception:
            self.runtime.stop()
            raise
        return self

    def __exit__(self, *args):
        try:
            self.browser.close()
        finally:
            self.runtime.stop()

    def read_results(self):
        return read_results(self.page)

    def check(self, domain, country, language, keyword, cancel, depth=100):
        result = RankResult(domain, country, language, keyword, datetime.now(timezone.utc).isoformat())
        result.depth = depth
        seen = set()
        for page_number in range(15):
            if cancel.is_set():
                result.status, result.detail = 'cancelled', '已取消'
                return result
            self.notify(f'正在读取「{keyword}」第 {page_number + 1} 页…')
            params = dict(q=keyword, gl=country, hl=language, pws=0, start=page_number * 10)
            try:
                self.page.goto('https://www.google.com/search?' + urlencode(params),
                               wait_until='domcontentloaded', timeout=30000)
            except Exception:
                raise RuntimeError('Google 页面加载失败，请检查网络是否能访问 Google。') from None
            self.page.wait_for_timeout(1200)
            links = self.read_results()
            challenged = is_challenge(self.page)
            if challenged:
                self.notify('请在 Chromium 窗口手动完成验证码 / 同意页面，最多等待 3 分钟…')
                deadline = time.monotonic() + 180
                while time.monotonic() < deadline and not cancel.is_set():
                    self.page.wait_for_timeout(500)
                    if not is_challenge(self.page):
                        links = self.read_results()
                        if links:
                            break
                else:
                    result.status = 'cancelled' if cancel.is_set() else 'blocked'
                    result.detail = '已取消' if cancel.is_set() else '手动处理超时，请重新查询'
                    return result
            if not links:
                result.status, result.detail = 'incomplete', f'仅解析到 {len(seen)} 条；页面无结果或结构变化'
                return result
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
            if not added or not has_next(self.page):
                break
            if cancel.wait(random.uniform(4, 7)):
                result.status, result.detail = 'cancelled', '已取消'
                return result
        result.status, result.detail = 'incomplete', f'仅解析到 {len(seen)} 条结果，未找到域名'
        return result
