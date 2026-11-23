# Security policy

## Supported version

Security fixes are applied to the latest release line. The current public release is `1.5.19.x`.

## Reporting a vulnerability

Please do **not** open a public issue for a vulnerability that could be exploited. Use GitHub's private vulnerability reporting:

<https://github.com/harrisonfu8-design/wenwen-open-source/security/advisories/new>

Include the affected version, Windows version, reproduction steps, impact, and any proof-of-concept. We aim to acknowledge reports within 7 days and to publish a fix or mitigation within 30 days for confirmed high-impact issues. Please allow time for a fix before public disclosure.

## Scope

In scope:

- the public Windows UI shell and client licensing/support UI in `filekeeper/`;
- the NSIS installer in `installer/`;
- the public CodeQL workflow in `.github/workflows/`;
- the behavior of the official binary, including the closed core.

Out of scope:

- the hosted licensing and support service infrastructure;
- social engineering;
- issues that require an already compromised local administrator account;
- reports that only demonstrate that a user can modify the public code and rebuild it.

## Release integrity

Every release should be built by the GitHub Actions workflow. Current releases are unsigned; no trusted code-signing certificate has been issued. Verify before running:

```powershell
Get-AuthenticodeSignature .\文文_安装包_v1.5.19.exe | Format-List Status,SignerCertificate
Get-FileHash .\文文_安装包_v1.5.19.exe -Algorithm SHA256
```

The download page publishes the SHA-256 of each installer. Current builds are expected to show `Status = NotSigned`. If a trusted certificate is issued later, a valid signature must show `Status = Valid` and a subject matching the certificate published by the project; no such certificate exists today.

## Design notes

- The client does not use UPX or packers, and does not include telemetry or analytics SDKs.
- File recognition, OCR, SQLite storage, and Excel export run locally.
- Licensing uses an Ed25519 public key embedded in the client and a hosted signing service. The public client licensing code can be studied and modified; code signing and server-side checks are the primary release-integrity controls, not binary obfuscation.
- Secrets, private keys, production configuration, customer data, and signing credentials must never be committed. The repository ignores `*.pfx`, `*.pem`, `*.key`, environment files, build outputs, and local data.
