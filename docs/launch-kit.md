# 半开源发布行动清单

本仓库已于 2026-11-23 从完整 MIT 开源切换为**半开源**：UI 壳、安装器、文档和
客户端授权/客服界面公开，核心识别、发票解析、OCR 算法和托管后端闭源。

## 发布前检查

1. 旧 `wenwen-filekeeper` 仓库已转私有，完整源码、历史和发布记录保留在私有仓库。
2. 公开 `wenwen-open-source` 仓库的历史从干净根提交开始，不含核心源码。
3. `filekeeper/core.py`、`invoice.py`、`ocr.py` 只有占位说明，导入即抛 `ImportError`。
4. 公开树没有 build/release workflow；只有 CodeQL。
5. `LICENSE` 为 WenWen Semi-Open Source License v1.0，`docs/OPEN_SOURCE_SCOPE.md` 已写明公开/闭源边界。
6. 官网下载、SHA-256 和 `NotSigned` 说明准确；不引用已退役的公开 CI 发布或旧构建证明。

## 可投递的公开渠道

按社区规则先读置顶帖，再发布；同一内容不要跨多个版块刷屏。发布时明确写“半开源”，
不要写“完整开源”或“全部源码已公开”。

| 渠道 | 入口 | 适合的内容 | 注意 |
| --- | --- | --- | --- |
| Hacker News | <https://news.ycombinator.com/submit> | Show HN：本地优先的 Windows 文件/发票整理器 | 标题直白，正文短，主动说明核心闭源 |
| Reddit | r/software、r/windows、r/productivity | “I built a local-first file organizer” | 先看 subreddit 规则，禁止纯广告 |
| V2EX | <https://www.v2ex.com/new> | 分享创造 / 程序员 | 用“分享创造”节点，附半开源说明和下载 |
| 少数派 | <https://sspai.com/> | 效率工具、文件整理方法 | 投稿而非硬广，写使用场景 |
| Product Hunt | <https://www.producthunt.com/> | 新工具发布 | 需要账号与素材，首日互动很关键 |
| AlternativeTo | <https://alternativeto.net/> | 作为本地文件整理器收录 | 提交产品信息，等待审核 |
| Softpedia | <https://www.softpedia.com/> | Windows 软件收录 | 提交下载页与介绍 |
| GitHub Discussions | 仓库 Discussions | 使用问题、安装验证、UI 壳反馈 | 把外部反馈沉淀回仓库 |

## 英文发布文案（可改）

**Title:** Show HN: WenWen – a local-first Windows file and invoice organizer

**Body:**

I built WenWen for people who keep losing documents. You drop a PDF, Word file,
Excel sheet, image, or scan into the window; it reads the content, suggests a
title and category, files it into a folder, and records every move in a local
ledger. There is also an invoice view that extracts date, seller, amount, and
invoice number, with duplicate warnings and Excel export.

The client is a Windows desktop app built with Python, PyInstaller, and NSIS.
File contents stay local; only licensing, orders, and support chat contact the
server. The repository is semi-open: the UI shell, installer, documentation, and
client licensing/support UI are public, while the core recognition and
invoice/OCR algorithms are closed:
https://github.com/harrisonfu8-design/wenwen-open-source

Download and guide: https://sw.olilily.com/

It is currently unsigned, so SmartScreen may show “Unknown publisher”. The
SHA-256 is published on the official site. I applied to the SignPath Foundation
OSS program but was not approved; with a closed core, a paid certificate is the
realistic path. Happy to answer questions about the semi-open scope, the
local-first design, or the invoice extraction limits.

## 中文发布文案（可改）

**标题：** 我做了一个本地优先的 Windows 文件和发票整理工具，采用半开源

**正文：**

平时文件一多就找不到，所以我做了「文文」：把 PDF、Word、Excel、图片或扫描件
拖进窗口，它会读内容、给标题和分类、归档到对应文件夹，并记录每次归档；发票
还能识别日期、销售方、金额和发票号，支持去重、筛选和 Excel 导出。

客户端是 Windows 桌面程序，Python + PyInstaller + NSIS 构建，文件内容默认
只留在本机。仓库是半开源：UI 壳、安装器、文档和客户端授权/客服界面公开，
核心识别与发票/OCR 算法闭源：
https://github.com/harrisonfu8-design/wenwen-open-source

下载和教程：https://sw.olilily.com/

目前安装包还没有受信任签名，Windows 可能提示“未知发布者”；SHA-256 公布在
官网。我申请过 SignPath Foundation 的免费开源签名，但因公开可见度不足被拒；
带闭源核心的项目也不适合该 OSS 项目，后续会考虑付费证书。欢迎试用后提
Issue，尤其是不同 Windows 版本下的安装和 UI 问题。

## 两周节奏

- 第 1 天：发布半开源仓库，更新官网 GitHub 入口，发 GitHub Discussion。
- 第 2–3 天：投 1 个主渠道（HN 或 V2EX），不要同日多平台刷屏。
- 第 4–7 天：逐条回复 Issue，修 1–2 个公开范围问题，更新文档。
- 第 8–14 天：整理 2–3 条外部引用/讨论，写一篇“为什么核心闭源、UI 公开”的
  技术文章，再投 1 个渠道。
- 不把 SignPath 免费 OSS 重审作为近期目标；若要签名，按付费证书路线准备预算、
  身份验证和私钥保管流程。

## 对外表述红线

- 可以写：半开源、UI/安装器/文档公开、核心算法闭源、源码可见但非 OSI 开源。
- 不要写：完整开源、全部源码公开、OSI 认证、SignPath Foundation 签名、
  已签名、可信发布者。
- 不要暗示闭源核心包含在公开仓库，或公开树可以完整构建。
