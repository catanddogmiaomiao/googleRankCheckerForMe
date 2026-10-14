import sys
from pathlib import Path
from PyQt6.QtGui import QIcon
import random
import threading
import queue
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit, QComboBox, QPlainTextEdit, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QProgressBar, QAbstractItemView, QSpinBox)
from core import normalize_domain
from scraper import GoogleBrowserProvider
from storage import History, comparison

COUNTRIES = {'美国 (us)': ('us', 'en'), '英国 (gb)': ('gb', 'en'), '加拿大 (ca)': ('ca', 'en'), '澳大利亚 (au)': ('au', 'en'), '日本 (jp)': ('jp', 'ja'), '德国 (de)': ('de', 'de'), '法国 (fr)': ('fr', 'fr'), '印度 (in)': ('in', 'en'), '新加坡 (sg)': ('sg', 'en'), '香港 (hk)': ('hk', 'zh-TW'), '台湾 (tw)': ('tw', 'zh-TW')}

class App(QWidget):
    def __init__(self):
        super().__init__()
        self.events = queue.Queue()
        self.cancel = threading.Event()
        self.results = []
        self.history = History()
        self.setWindowTitle('搜索排名检查器')
        self.resize(1060, 780)
        self.setMinimumSize(800, 600)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)
        title = QLabel('搜索排名检查器')
        title.setObjectName('title')
        layout.addWidget(title)
        layout.addWidget(QLabel('Chromium · 桌面端自然排名 · 无需 API / Google 登录'))
        form = QFormLayout()
        self.domain = QLineEdit('book2audiogo.com')
        self.country = QComboBox()
        self.country.addItems(COUNTRIES)
        self.language = QLineEdit('en')
        self.country.currentTextChanged.connect(lambda text: self.language.setText(COUNTRIES[text][1]))
        form.addRow('域名 / 网站 URL', self.domain)
        form.addRow('国家 / 地区', self.country)
        form.addRow('搜索语言代码', self.language)
        self.depth = QSpinBox()
        self.depth.setRange(1, 100)
        self.depth.setValue(100)
        self.depth.setSuffix(' 条')
        form.addRow('查询深度', self.depth)
        layout.addLayout(form)
        layout.addWidget(QLabel('关键词 · 每行一个，最多 20 个，自动去重'))
        self.words = QPlainTextEdit('ebook to audiobook\nconvert ebook to audiobook\nepub to mp3\npdf to audiobook')
        self.words.setMaximumHeight(140)
        layout.addWidget(self.words)
        controls = QHBoxLayout()
        self.start_button = QPushButton('查询排名')
        self.start_button.setObjectName('primary')
        self.start_button.clicked.connect(self.start)
        self.stop_button = QPushButton('取消')
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop)
        controls.addWidget(self.start_button)
        controls.addWidget(self.stop_button)
        controls.addStretch()
        controls.addWidget(QLabel('逐页读取 · 遇到验证码请在浏览器手动处理'))
        layout.addLayout(controls)
        self.progress = QProgressBar()
        self.progress.setValue(0)
        layout.addWidget(self.progress)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(['关键词', '当前排名', '上次排名', '变化', '已读取', '匹配链接 / 说明'])
        self.table.verticalHeader().hide()
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setWordWrap(False)
        self.table.setColumnWidth(0, 270)
        self.table.setColumnWidth(1, 130)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table, 1)
        self.status = QLabel('准备就绪 · 查询时自动打开 Chromium')
        layout.addWidget(self.status)
        self.setStyleSheet('''
            QWidget { font-family: "Microsoft YaHei UI"; font-size: 13px; color: #263347; background: #f5f7fb; }
            QLabel#title { font-size: 25px; font-weight: 600; }
            QLineEdit, QComboBox, QPlainTextEdit { background: white; border: 1px solid #d6ddea; border-radius: 6px; padding: 8px; }
            QPushButton { padding: 9px 22px; border: 1px solid #d6ddea; border-radius: 6px; background: white; }
            QPushButton#primary { background: #2563eb; color: white; border: none; }
            QPushButton:disabled { background: #e4e8ef; color: #8993a3; }
            QTableWidget { background: white; alternate-background-color: #f1f5fb; border: 1px solid #d6ddea; gridline-color: #e8edf5; }
            QHeaderView::section { background: #eaf0fa; border: none; padding: 10px; font-weight: 600; }
            QProgressBar { border: none; background: #e4eaf4; text-align: center; }
            QProgressBar::chunk { background: #93b5fa; }
        ''')
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll)
        self.timer.start(100)

    def stop(self):
        self.cancel.set()
        self.stop_button.setEnabled(False)
        self.status.setText('正在取消，等待当前网页加载结束…')

    def start(self):
        try:
            domain = normalize_domain(self.domain.text())
            language = self.language.text().strip()
            if not language or len(language) > 12:
                raise ValueError('请输入语言代码，例如 en、ja 或 zh-TW。')
            words = list(dict.fromkeys(w.strip() for w in self.words.toPlainText().splitlines() if w.strip()))
            if not words:
                raise ValueError('请输入至少一个关键词。')
            if len(words) > 20:
                raise ValueError('每次最多查询 20 个关键词，请分批查询。')
        except ValueError as error:
            QMessageBox.warning(self, '检查输入', str(error))
            return
        country = COUNTRIES[self.country.currentText()][0]
        depth = self.depth.value()
        self.cancel.clear()
        self.results.clear()
        self.table.setRowCount(len(words))
        for index, word in enumerate(words):
            self.set_row(index, word, '等待查询', '')
        self.progress.setRange(0, len(words))
        self.progress.setValue(0)
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.status.setText(f'正在查询 0/{len(words)}…')
        def worker():
            try:
                with GoogleBrowserProvider(lambda message: self.events.put(('status', message))) as provider:
                    for index, word in enumerate(words):
                        if self.cancel.is_set():
                            break
                        if index:
                            delay = random.uniform(6, 12)
                            self.events.put(('status', f'下一关键词前等待 {delay:.1f} 秒…'))
                            if self.cancel.wait(delay):
                                break
                        try:
                            result = provider.check(domain, country, language, word, self.cancel, depth)
                            self.events.put(('result', index, result))
                            if result.status in ('blocked', 'parse_error'):
                                break
                        except Exception as error:
                            detail = str(error) if isinstance(error, RuntimeError) else '浏览器查询失败，请检查网络或浏览器窗口。'
                            self.events.put(('error', index, detail))
                            break
            except Exception:
                self.events.put(('fatal', 'Chromium 启动失败。请按使用说明安装 Playwright 和 Chromium。'))
            finally:
                self.events.put(('done',))
        threading.Thread(target=worker, daemon=True).start()

    def set_row(self, row, keyword, rank, detail, previous='—', change='—', count=0):
        for col, text in enumerate((keyword, rank, previous, change, str(count), detail)):
            item = QTableWidgetItem(text)
            item.setToolTip(text)
            self.table.setItem(row, col, item)

    def poll(self):
        try:
            while True:
                event = self.events.get_nowait()
                if event[0] == 'status':
                    self.status.setText(event[1])
                    continue
                if event[0] == 'fatal':
                    self.status.setText(event[1])
                    QMessageBox.warning(self, '浏览器启动失败', event[1])
                    continue
                if event[0] == 'done':
                    for row in range(self.table.rowCount()):
                        if self.table.item(row, 1).text() == '等待查询':
                            self.table.item(row, 1).setText('已取消' if self.cancel.is_set() else '未查询')
                    self.start_button.setEnabled(True)
                    self.stop_button.setEnabled(False)
                    self.status.setText('已取消' if self.cancel.is_set() else '查询完成')
                else:
                    row = event[1]
                    if event[0] == 'error':
                        self.set_row(row, self.table.item(row, 0).text(), '查询失败', event[2])
                    else:
                        result = event[2]
                        self.results.append(result)
                        rank = str(result.position) if result.position else {'ok': f'>{result.depth}', 'incomplete': '结果不足', 'cancelled': '已取消', 'blocked': '需要手动处理', 'parse_error': '解析失败'}[result.status]
                        try:
                            old = self.history.previous(result)
                            previous, change = comparison(result, old)
                            self.history.save(result)
                            detail = result.url or result.detail
                        except Exception:
                            previous, change = '—', '—'
                            detail = (result.url or result.detail) + '（历史保存失败）'
                        self.set_row(row, result.keyword, rank, detail, previous, change, result.scanned_count)
                    self.progress.setValue(row + 1)
                    self.status.setText(f'已处理 {row + 1}/{self.table.rowCount()}')
        except queue.Empty:
            pass

    def closeEvent(self, event):
        self.cancel.set()
        event.accept()

def main():
    app = QApplication(sys.argv)
    resource_root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
    app.setWindowIcon(QIcon(str(resource_root / 'assets' / 'app.ico')))
    app.setStyle('Fusion')
    window = App()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
