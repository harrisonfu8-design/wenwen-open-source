# Download verification

This page records what can be checked independently. The official website
installer is **v1.5.20**. The public repository is semi-open: the UI shell,
installer, documentation, and client licensing/support UI are published, but
the core recognition and invoice/OCR algorithms are closed and are not in the
public tree. See [OPEN_SOURCE_SCOPE.md](OPEN_SOURCE_SCOPE.md).

## Official v1.5.20

| Item | Value |
| --- | --- |
| Download | <https://sw.olilily.com/dl/WenWen_Setup_v1.5.20.exe?v=20261123d> |
| Size | 87,867,072 bytes |
| SHA-256 | `716244575637116710FB8A4E749B2E641D81D2AAD9C1CAE714B0485E1998C4EC` |
| Authenticode | `NotSigned` |

The installer shows a privacy policy page and requires the consent checkbox
before installation continues. The same policy is installed as `隐私政策.txt`.

Installed main program:

| Item | Value |
| --- | --- |
| Path | `%LOCALAPPDATA%\Programs\FileKeeper\文件管家.exe` |
| Size | 11,036,823 bytes |
| SHA-256 | `DA39A8E178370BED94F5FBF466F9B39C3AA0216423DD64F778C8E0AA3C635084` |
| Authenticode | `NotSigned` |

The official installer is distributed from the official website. The earlier
public GitHub CI release was retired during the semi-open transition; do not
rely on old release links or old public build attestations. The SHA-256 values
above are the primary public check.

## Retired installers

Earlier installers have been removed from the official download directory for
security reasons. Their bundled registration notes are obsolete; users should
upgrade to v1.5.20 and rely only on the credentials and links shown on the
official site and current client.

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
Get-FileHash .\WenWen_Setup_v1.5.20.exe -Algorithm SHA256
Get-AuthenticodeSignature .\WenWen_Setup_v1.5.20.exe | Format-List Status,StatusMessage,SignerCertificate
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
