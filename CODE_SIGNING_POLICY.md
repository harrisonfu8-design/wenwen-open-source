# Code signing policy

**Current status: no trusted code-signing certificate is in use. All published
WenWen binaries are unsigned (`NotSigned`).**

WenWen applied to the SignPath Foundation free open-source signing program on
2026-11-22. The application was not approved at that time because the project
did not yet show enough public visibility and community signals. No certificate
was issued, and this repository does not claim that any binary is signed.

WenWen is now semi-open: the core recognition, invoice-extraction, and OCR
algorithms and the hosted backend are closed. That does not meet the SignPath
Foundation free OSS program's no-closed-components expectation, so a paid
code-signing certificate is the realistic path. This policy describes the
intended signing process if a trusted certificate is obtained. Until that
happens, the statements below are forward-looking, not a claim of current
signing.

## What will be signed

- `文件管家.exe` — the main Windows client.
- `文文_安装包_v*.exe` — the NSIS installer.

Only artifacts built by the private build workflow from the complete private
source are eligible. The public semi-open tree is incomplete and cannot produce
an official build. Local builds and binaries built from modified or untracked
source are not signed.

## Build and release

- Build workflow: maintained in the private repository, not in this public tree.
- Build runner: GitHub-hosted `windows-latest` or an equivalent controlled runner.
- Trigger: a version tag in the private repository, or a controlled manual build.
- The workflow builds the client with PyInstaller, packages it with NSIS, and
  can submit the unsigned artifacts to a signing service when credentials exist.
- Every signing request must be manually approved by an Approver.
- The release version must match in `filekeeper/license.py`,
  `assets/version_info.txt`, `installer/install.nsi`, and executable metadata.

## Team roles and members

| Role | Responsibility | Member |
| --- | --- | --- |
| Author | Modifies source; responsible for build and release | [@harrisonfu8-design](https://github.com/harrisonfu8-design) |
| Reviewer | Reviews pull requests from non-committers before merge | [@harrisonfu8-design](https://github.com/harrisonfu8-design) |
| Approver | Approves each signing request | [@harrisonfu8-design](https://github.com/harrisonfu8-design) |

All members must enable multi-factor authentication for GitHub and for the
signing service. Changes to build scripts, CI configuration, or signing
configuration require review before merge.

## Origin verification

When a signing service is used, it verifies that each signed artifact was
produced by the GitHub Actions run associated with the private build repository
and the approved signing request. The request records the source repository,
commit, workflow run, artifact, and approver.

## Verification

Users can verify a downloaded file in PowerShell:

```powershell
Get-AuthenticodeSignature .\文文_安装包_v1.5.20.exe | Format-List Status,StatusMessage,SignerCertificate
Get-FileHash .\文文_安装包_v1.5.20.exe -Algorithm SHA256
```

For the current v1.5.20 release, `Status` is expected to be `NotSigned`. A
future signed release must show `Status = Valid` and the actual certificate
subject. The expected SHA-256 values for current builds are listed in
[docs/VERIFICATION.md](docs/VERIFICATION.md).

## Privacy

See [PRIVACY.md](PRIVACY.md). The client does not upload file contents. Licensing,
order, support-chat, and brand-logo requests go to the official service endpoint
described in the privacy policy.
