# 搜索排名检查器

本机 PyQt6 + Playwright / Chromium。无需 API，不登录 Google，不使用代理池，不绕过 CAPTCHA。

## 安装和启动

需要 Python 3.10+，先释放足够磁盘空间（建议至少 1 GB）。在本目录执行：

```powershell
python -m pip install -r requirements.txt
python -m playwright install chromium
```

然后双击 start.pyw（需 Windows 已关联 Python 的 .pyw 文件），或者运行 python app.py。

## 使用

输入域名、国家、语言、查询深度（1–100，默认 100）和关键词（每行一个，最多 20 个）。查询自动打开 Chromium，批次结束时关闭。页间等待 4–7 秒，关键词间等待 6–12 秒，串行执行。

遇到验证码或同意页面，最多等待 3 分钟，请在 Chromium 窗口手动处理。超时停止批次，不尝试绕过 CAPTCHA。取消在当前网页加载结束后生效，加载超时 30 秒。

使用项目专用 `browser-profile` 保存浏览器会话，不连接个人 Chrome，也不要求登录。保留会话不保证免于验证码。请勿同时运行两个查询程序使用同一个 profile。

搜索结果出现后自动向下滚动，读取结果及下一页链接。若页面解析失败，将覆盖保存 `diagnostics/last-page.json` 和 `last-page.png`，便于检查 Google 页面结构。诊断可能包含关键词和结果信息，仅保存在本机，不上传仓库。

国家 gl 和语言 hl 只是搜索偏好，真实出口 IP 仍影响地区结果，不保证所选国家当地的排名。网络必须能访问 Google。

排名按解析到的网页结果顺序计算，支持子域名，尽量排除广告和特殊模块。达到指定深度未找到显示 >深度；结果不足或结构变化显示结果不足。随机等待不能保证不触发限制。

## SQLite 历史

同目录 rankings.sqlite3 保存 UTC 日期时间、关键词、排名、URL、域名、国家、语言、设备、查询深度和状态。界面显示当前、上次排名及变化。按同一域名、国家、语言、设备和深度比较，只使用成功记录。37→20 显示 ↑17；超出范围无法得出准确差值，显示进入/离开范围。没有历史显示 —。

## 模块

- google_parser.py：DOM 选择器、结果链接、下一页和验证页识别，页面改版优先修改这里。
- scraper.py：Chromium 生命周期、分页、等待及手工验证流程。
- core.py：域名匹配和结果模型。
- storage.py：SQLite 保存和历史比较。
- app.py：PyQt6 界面。

运行 python -m unittest -v 验证本地逻辑，不请求 Google。

Playwright 文档：https://playwright.dev/python/docs/browsers

## 手动打包 Windows 程序

在项目目录打开 PowerShell，使用同一个 Python 环境执行：

```powershell
python -m pip install -r requirements-build.txt
$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path (Get-Location) 'browsers'
python -m playwright install chromium
python -m PyInstaller --clean --noconfirm rank_checker.spec
```

输出为 `dist/搜索排名检查器/搜索排名检查器.exe`。这是目录版，请保留整个 `dist/搜索排名检查器` 文件夹，包括 `_internal`，不要单独移动 exe。Chromium 随目录打包，运行时无需额外安装 Python 或浏览器。

spec 使用 `assets/app.ico` 作为程序图标，包含 16、24、32、48、64、128、256 像素尺寸；图形界面也使用同一图标。`assets/app.svg` 是可编辑源图。

打包后的历史数据库在 exe 同目录生成，更新程序时保留 `rankings.sqlite3`。请把程序放在有写入权限的目录。源码运行时数据库仍保存在项目目录。

打包需要足够磁盘空间，建议至少预留 2 GB。升级 Playwright 后，应重新执行浏览器安装和打包，确保浏览器版本匹配。当前已验证 spec 语法、图标和本地测试，尚未完整构建 exe。

打包机制参考：[PyInstaller spec 文档](https://pyinstaller.org/en/stable/spec-files.html)、[Playwright 浏览器路径配置](https://playwright.dev/python/docs/browsers)。
