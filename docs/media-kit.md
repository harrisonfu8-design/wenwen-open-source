# Media kit

Last updated: 2026-11-23

This page gives journalists, directory editors, and community moderators the
facts and assets needed to describe WenWen accurately. Please do not describe
the current builds as signed.

## Boilerplate (English, 52 words)

WenWen is a local-first Windows desktop app for organizing files and invoices.
Users drag in documents, get a suggested title and category, file them into
folders, and keep a searchable archive and invoice ledger. The public repository
is semi-open: the UI shell, installer, and client licensing/support UI are
published, while the core recognition and invoice/OCR algorithms remain closed.

## 简介（中文，约 90 字）

文文是一款本地优先的 Windows 文件和发票整理工具。把 PDF、Word、Excel、图片或
扫描件拖进窗口，它会读取内容、建议标题与分类、归档到文件夹，并记录每次归档；
发票台账可提取日期、销售方、金额和发票号。公开仓库为半开源：UI 壳、安装器和
客户端授权/客服界面公开，核心识别与发票/OCR 算法闭源。

## Facts

- Product name: WenWen / 文文
- Category: Windows desktop productivity; file organizer; invoice ledger
- Platform: Windows 10/11, x64
- Current official version: 1.5.19 (unsigned)
- Client license: WenWen Semi-Open Source License v1.0 (source-available, not OSI open source)
- Public scope: UI shell, installer, documentation, and client licensing/support UI
- Closed scope: core recognition, invoice extraction, OCR algorithms, and the
  licensing/orders/support backend
- Repository: <https://github.com/harrisonfu8-design/wenwen-open-source>
- English page: <https://sw.olilily.com/en/>
- Chinese page: <https://sw.olilily.com/>
- Guide: <https://sw.olilily.com/guide/>
- FAQ: <https://github.com/harrisonfu8-design/wenwen-open-source/blob/main/docs/faq.md>

## What is different

- **Local-first:** file contents and the archive ledger stay on the user’s
  machine; the client does not upload file contents.
- **Audit trail:** every filing records time, title, category, and full path,
  with undo, batch rename, and Excel export.
- **Invoice workflow:** extracts common invoice fields, warns about duplicates,
  filters, exports to Excel, and merges reimbursement PDFs.
- **Semi-open source:** the UI shell, installer, documentation, and client
  licensing/support UI are public. Core recognition and invoice/OCR algorithms
  are closed and are not in the public repository.

## Assets

All screenshots use demo data. Do not crop out the app name when using them to
illustrate the product.

- Main window: <https://github.com/harrisonfu8-design/wenwen-open-source/raw/main/docs/screenshots/main.png>
- Invoice ledger: <https://github.com/harrisonfu8-design/wenwen-open-source/raw/main/docs/screenshots/invoices.png>
- Archive records: <https://github.com/harrisonfu8-design/wenwen-open-source/raw/main/docs/screenshots/records.png>
- Logo: <https://sw.olilily.com/logo.png>
- Social preview (1280×640): <https://github.com/harrisonfu8-design/wenwen-open-source/raw/main/docs/social-preview.jpg>

## Download and verification

- Official installer: <https://sw.olilily.com/dl/WenWen_Setup_v1.5.19.exe>
- SHA-256: `E6FA60D791AE8414F12F5DA3967E79548025EAEFC4A7D49C20FA36AB4DD8F2E4`
- Verification: <https://github.com/harrisonfu8-design/wenwen-open-source/blob/main/docs/VERIFICATION.md>

## Signing status — please state accurately

- v1.5.19 is **`NotSigned`**. Windows SmartScreen may show
  “Unknown publisher”.
- A SignPath Foundation free OSS application was declined on 2026-11-22 for
  insufficient public visibility and community signals. No certificate was
  issued.
- Do not write “signed by SignPath”, “trusted publisher”, or “certificate by
  SignPath Foundation” for any current build.
- The project is collecting real Windows install/build feedback before a future
  reapplication.

## Contact

- Issues: <https://github.com/harrisonfu8-design/wenwen-open-source/issues>
- Discussions: <https://github.com/harrisonfu8-design/wenwen-open-source/discussions>
- Security reports: use GitHub Security Advisories, not a public issue.

## Usage rules

- You may use the screenshots and logo to describe WenWen.
- Do not imply endorsement by SignPath, Microsoft, or any certificate authority.
- Do not alter screenshots to remove the unsigned warning or add a signature.
- For interviews or additional data, open a GitHub issue with your outlet and
  deadline.
