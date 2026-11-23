# SignPath 状态与签名路线

本仓库自 2026-11-23 起为**半开源**：核心识别、发票解析、OCR 算法和托管后端
闭源。因此本项目**不符合 SignPath Foundation 免费开源签名项目**的
“无闭源组件”预期，不应把重审 SignPath 作为近期目标。

## 当前状态

- 2026-11-22 提交 SignPath Foundation 免费开源签名申请。
- 同日收到拒绝：项目公开可见度与社区信号不足（stars、forks、contributors、
  独立文章/讨论、持续活跃度）。这不是代码质量结论。
- 未获得 Organization、Project、Policy、Artifact Configuration 或 API Token。
- SignPath GitHub App 安装在 `harrisonfu8-design`，原先仅授权旧的
  `wenwen-filekeeper` 仓库。
- 旧仓库已转私有；公开仓库为 `wenwen-open-source`。
- 所有已发布二进制仍为 `NotSigned`；在证书真正签发前，README 与站点不得使用
  “已由 SignPath 签名”的表述。

## 为什么不再走免费 OSS 签名

SignPath Foundation 的免费项目面向可公开构建的开源项目。文文的核心算法、
构建输入和后端是闭源的，公开树也不能完整构建。即使公开可见度提升，免费 OSS
申请仍很可能因闭源组件被拒。继续包装成“完整开源”会误导审核方和用户。

## 现实路线：付费代码签名

1. 选择 CA（如 DigiCert、Sectigo、SSL.com 等）的 Windows Authenticode
   代码签名证书，完成企业/个人身份验证。
2. 使用硬件令牌或云 HSM 保管私钥，禁止把私钥或证书导出到仓库。
3. 在私有构建仓库中配置签名步骤，签名后再发布安装包。
4. 每次发布记录证书主体、时间戳、SHA-256 和签名校验结果。
5. 在 README 与官网公布签名者身份和验证步骤；未拿到证书前保持 `NotSigned`。

## 验证

```powershell
Get-AuthenticodeSignature .\文文_安装包_v1.5.20.exe | Format-List Status,SignerCertificate
```

当前未签名版本应为 `NotSigned`。证书签发后，`Status` 应为 `Valid`，签名者
应为实际证书主体；在拿到证书前不要预设或宣称签名者名称。

## 已知限制

- 公开树不包含核心算法，不能复现官方二进制。
- 付费证书不能消除所有 SmartScreen 警告，新证书仍需积累信誉。
- 不购买流量、不刷星、不用小号；公开材料只陈述可核验事实。
