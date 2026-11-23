# FAQ

## Is WenWen code-signed?

No. The current official build (v1.5.20) is `NotSigned`. A SignPath Foundation free OSS application was declined on
2026-11-22 because the project did not yet show enough public visibility or
community signals. No certificate was issued.

## Why does Windows SmartScreen say “Unknown publisher”?

SmartScreen warns when a downloaded executable has no trusted Authenticode
signature or has not built reputation yet. An unsigned build can still be
legitimate, but Windows cannot tie it to a verified publisher. Verify the
SHA-256 published on the official website before running it.

## Is there a free way to avoid SmartScreen without buying a certificate?

Only through the Microsoft Store: an MSIX package submitted to the Store does
not need a CA-trusted signature, and Microsoft re-signs it after certification.
A free individual developer account is available. This covers Store installs
only — the NSIS installer and direct downloads remain unsigned. Store policy,
commerce rules, and certification still apply. See
[Microsoft’s code-signing options](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/code-signing-options).

The full client builds as an MSIX after excluding a redundant `python-docx`
template folder that uses the OPC-reserved `_rels` names. The v1.5.20 Store
package was submitted on 2026-11-23 and is currently in Microsoft certification.
It is not yet publicly available. Once certification passes, Store installs are
re-signed by Microsoft. Details: [msix.md](msix.md).

## Will this change soon?

Only if a trusted certificate is obtained. The project will not claim to be
signed before that happens. See
[CODE_SIGNING_POLICY.md](../CODE_SIGNING_POLICY.md).

## Does WenWen upload my files?

No. File contents, extracted text, and the local archive ledger stay on the
machine. The client contacts the official service for licensing, orders,
support chat, and brand-logo requests. See [PRIVACY.md](../PRIVACY.md).

## Does it work offline?

Core filing, search, the local ledger, and exports work on the local machine.
License activation and account-related actions need a connection to the
official service.

## Which files are supported?

PDF, Word, Excel, images, plain text, and common archive formats. Invoice
extraction works best on text-based PDFs and clear scans; OCR quality depends
on the scan.

## Can I build it myself?

No, not from this public tree alone. WenWen is semi-open: the UI shell,
installer, documentation, and client-side licensing/support UI are public, but
the core recognition, invoice-extraction, and OCR modules are closed and
omitted. `build.ps1` stops with an explicit message. The official binaries are
built in the private repository with the closed core.

## Why is only part of the client public?

The Windows UI shell, installer scripts, documentation, and client-side
licensing/support UI are published under the WenWen Semi-Open Source License.
The core recognition, invoice-extraction, and OCR algorithms are closed, and
the licensing/order/support backend contains customer and payment data and is
not published. See [OPEN_SOURCE_SCOPE.md](OPEN_SOURCE_SCOPE.md).

## What does the semi-open license allow?

You may view, clone, modify, and build the public portions for personal
evaluation, learning, research, and non-commercial internal testing. Commercial
use, paid distribution, or use in a commercial product requires written
permission. The closed core is not licensed. The license is not OSI-approved
open source. See [LICENSE](../LICENSE).

## How do I verify a download?

1. Compare the SHA-256 with the value published on the official website.
2. Check the Authenticode status:
   `Get-AuthenticodeSignature .\WenWen_Setup_v1.5.20.exe` — current builds
   return `NotSigned`.
3. If the hash does not match, do not run the file; report the URL and hash
   through the issue tracker.

## Where is my data stored?

Files are filed into folders you choose. Application data and the local
database live under `%APPDATA%\FileKeeper`. The program itself installs under
`%LOCALAPPDATA%\Programs\FileKeeper` by default.

## How do I report a bug?

Open an issue with the Windows version, WenWen version, steps to reproduce,
and sanitized logs. Do not attach real invoices, ID documents, or customer
data. Security issues should go through GitHub Security Advisories.
