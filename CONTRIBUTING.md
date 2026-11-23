# Contributing

感谢你愿意改进文文。提交前请先读本文件。

## 基本规则

- 使用 GitHub Issue 描述问题或建议，再提交 Pull Request。
- 每个提交必须包含 `Signed-off-by` 行，表示你确认有权提交该代码（DCO）。可用 `git commit -s` 自动添加。
- 不得提交任何密钥、证书、生产配置、客户数据、安装包、构建产物、截图或日志。
- 不得引入来源不明的二进制、广告 SDK、遥测 SDK 或与公开范围无关的闭源依赖。
- 闭源核心算法与后端由维护者在私有仓库维护，不通过公开 Pull Request 提交。
- 新依赖必须使用 OSI 认可的许可证，并在 Pull Request 中说明用途和版本。

## 代码要求

- 保持现有代码风格，优先小步修改，不无关重排。
- 公开范围是 UI 壳、安装器、文档、客户端授权/客服界面和公开工具；核心识别、发票解析、OCR 与后端不在本仓库。
- 修改 UI、安装器、授权/客服界面或文档时，补充可复现的测试步骤或截图说明。
- 不提交真实客户发票、真实姓名、真实路径或可识别个人的数据；测试数据必须脱敏。
- 修改版本时，必须同时更新 `filekeeper/license.py`、`assets/version_info.txt` 和 `installer/install.nsi`，三处必须一致。
- 修改构建脚本、CI 或签名配置时，必须在 Pull Request 中单独说明，并由维护者审核。公开树不能完整构建，构建与发布在私有仓库完成。

## 提交前检查

```powershell
python -m compileall filekeeper
```

确认：

- 公开 UI 壳、授权/客服界面、安装器脚本和文档可以正常阅读与静态检查；
- 没有把 `dist/`、`build/`、`installer/app/`、`release/`、`*.exe`、`*.pfx`、`*.pem` 或用户数据带进提交；
- 没有提交 `filekeeper/core.py`、`invoice.py`、`ocr.py` 的真实实现、私有核心、模型或后端代码；
- 没有声称公开树可以完整构建或已签名。`NotSigned` 是当前正式发布状态，取得受信任证书后才会由私有构建流程送签。

## 审核与合并

外部 Pull Request 必须由维护者审核后才能合并。构建脚本、CI、签名配置和发布标签的修改必须由 Approver 审核。签名请求由 Approver 逐次批准。

参与本项目即表示同意遵守 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)。
