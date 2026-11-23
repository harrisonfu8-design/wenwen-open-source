# Privacy policy / 隐私政策

Last updated: 2026-11-22

文文（FileKeeper）是一个本地优先的 Windows 文件和发票整理工具。本政策说明客户端会处理哪些数据、何时联网，以及数据保存在哪里。

## 1. 本地数据

客户端默认把以下数据保存在 `%APPDATA%\FileKeeper\`：

- `records.db`：归档记录、发票台账、目录方案、搜索索引；
- `license.json`：机器码、注册码、试用/订阅状态与本地授权缓存；
- `brand_logo.png`：从官方服务端下载的品牌图缓存；
- 错误日志、支付二维码临时图片等运行文件。

这些数据只在本机使用。卸载客户端不会自动删除 `%APPDATA%\FileKeeper\`，以便重装后继续使用；用户可自行删除该目录。

## 2. 不会上传的内容

客户端**不会上传**用户拖入的文件内容、文件名、归档路径、发票明细或台账数据。文件识别、分类、OCR 和 Excel 导出均在本机完成。

在线客服是用户主动打开并发送消息时才联网；消息内容由用户自己输入。

## 3. 会联网的功能

客户端会访问官方服务端 `https://sw.olilily.com`，用于以下功能：

| 功能 | 请求 | 发送的数据 | 目的 |
| --- | --- | --- | --- |
| 首次注册 / 授权刷新 | `POST /api/register`、`POST /api/status` | 机器码、客户端版本 | 开通 24 小时试用、校验订阅状态 |
| 在线客服 | `POST /api/support/send`、`GET /api/support/messages` | 机器码、注册码、客户端版本、用户输入的聊天内容 | 显示客服会话与回复 |
| 创建订单 / 查询订单 | `POST /api/order`、`GET /api/order/<no>`、`POST /api/order/<no>/claim` | 机器码、注册码、订阅月数、订单号、用户填写的交易单号 | 生成订单、确认付款、开通订阅 |
| 品牌图 | `GET /api/brand/logo` | 客户端版本（User-Agent）、时间戳 | 下载运营后台配置的品牌图 |
| 收款码 | 服务端返回的 `qr_url` | 无额外个人信息 | 显示付款二维码 |

机器码由 Windows 安装标识、CPU 名称、磁盘卷序列号和网卡地址摘要生成，用于把授权绑定到当前电脑。它不包含姓名、邮箱、手机号或文件内容。

服务端可能记录请求时间、IP 地址、机器码、注册码、订单与客服消息，用于授权管理、防滥用和客服回复。服务端数据由文文项目维护者管理。

## 4. 第三方组件

客户端使用的 Python 库（PyMuPDF、python-docx、openpyxl、pypdf、Pillow、cryptography、tkinterdnd2、winocr、WinRT）在本机运行，不包含广告或分析 SDK，不向第三方上传用户文件。

当前客户端和官网安装包均为 `NotSigned`；Microsoft Store 包在认证通过后由 Microsoft 重签名。项目未使用 SignPath 或其他 CA 证书。该状态不涉及最终用户运行时的数据。

## 5. 数据保留与删除

- 本地数据：用户可随时删除 `%APPDATA%\FileKeeper\`。
- 服务端授权、订单与客服数据：如需查询或删除，请通过 <https://github.com/harrisonfu8-design/wenwen-open-source/issues> 联系维护者，并说明机器码或注册码。为防止授权滥用，部分交易与审计记录可能按法律或财务要求保留。

## 6. 儿童

本软件不面向 13 岁以下儿童，也不主动收集儿童个人信息。

## 7. 政策更新

本政策更新会提交到本仓库，并同步到官网 <https://sw.olilily.com/>。重大变化会在下载页或客户端中提示。
