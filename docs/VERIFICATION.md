# Download verification

This page records what can be checked independently. The official website
installer is **v1.5.19**. The public repository is semi-open: the UI shell,
installer, documentation, and client licensing/support UI are published, but
the core recognition and invoice/OCR algorithms are closed and are not in the
public tree. See [OPEN_SOURCE_SCOPE.md](OPEN_SOURCE_SCOPE.md).

## Official v1.5.19

| Item | Value |
| --- | --- |
| Download | <https://sw.olilily.com/dl/WenWen_Setup_v1.5.19.exe> |
| Size | 85,688,413 bytes |
| SHA-256 | `E6FA60D791AE8414F12F5DA3967E79548025EAEFC4A7D49C20FA36AB4DD8F2E4` |
| Authenticode | `NotSigned` |

Installed main program:

| Item | Value |
| --- | --- |
| Path | `%LOCALAPPDATA%\Programs\FileKeeper\文件管家.exe` |
| Size | 11,099,824 bytes |
| SHA-256 | `D2DE433F02FFAA4751E4CC2C90554299C12EA85F3DA2D89EDEC485761612BEC8` |
| Authenticode | `NotSigned` |

The official installer is distributed from the official website. The earlier
public GitHub CI release was retired during the semi-open transition; do not
rely on old release links or old public build attestations. The SHA-256 values
above are the primary public check.

## Retired v1.5.18 installer

The v1.5.18 installer has been removed from the official download directory. Its
`注册说明.txt` contained the backend management address, default admin account,
and default password. The backend default password is no longer valid, but users
who still have the old installer should upgrade to v1.5.19 and should not rely on
the credentials printed in that file.

## Reproduce locally

The public tree is **not a complete build**. The closed core modules are
placeholders and `build.ps1` stops with an explicit message. Local reproduction
of the official binary requires the private core and is not available from this
repository.

The public UI and installer scripts can still be reviewed and type-checked:

```powershell
python -m compileall filekeeper
```

## Signature and hash checks

```powershell
Get-FileHash .\WenWen_Setup_v1.5.19.exe -Algorithm SHA256
Get-AuthenticodeSignature .\WenWen_Setup_v1.5.19.exe | Format-List Status,StatusMessage,SignerCertificate
```

`Status` is expected to be `NotSigned`. No trusted code-signing certificate has
been issued. A semi-open project with a closed core is not eligible for the
SignPath Foundation OSS program in its current form.

## What “verified” means here

- A matching SHA-256 shows the file is the one described on this page.
- `NotSigned` is expected for current releases. It is not a malware verdict.
- A future trusted signature must show `Status = Valid` and a real certificate
  subject. Until then, no signature is claimed.
- If a download’s hash does not match, do not run it; report the URL and hash in
  the issue tracker.
