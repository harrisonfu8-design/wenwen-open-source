# Source scope

Last updated: 2026-11-23

WenWen is **semi-open source**, not a fully open-source project. The Windows
client shell, installer, documentation, and client-side licensing UI are
published. The core recognition and invoice/OCR algorithms and the hosted
backend are closed source.

## Public source

| Path | What it contains |
| --- | --- |
| `filekeeper/ui.py` | Desktop UI shell and workflows |
| `filekeeper/main.py`, `run.py` | Application entry points |
| `filekeeper/license.py`, `registration.py`, `support.py` | Client-side licensing, registration, and support UI |
| `filekeeper/filetype.py` | File-extension helpers |
| `filekeeper/__init__.py` | Package metadata |
| `installer/` | NSIS installer scripts and assets |
| `build.ps1`, `文件管家.spec` | Packaging scripts for the private build pipeline |
| `assets/`, `docs/`, `signpath/` | Product assets, documentation, and signing policy templates |
| `.github/workflows/codeql.yml` | Static analysis for the public Python files |
| `README*`, `LICENSE`, `PRIVACY.md`, `SECURITY.md`, `CONTRIBUTING.md` | Project documents |

## Closed source / excluded

| Component | Why it is excluded |
| --- | --- |
| `filekeeper/core.py` (real implementation) | Content extraction, folder scoring, duplicate detection, archival, search, and ledger logic |
| `filekeeper/invoice.py` (real implementation) | Invoice field extraction, validation, categorization, and reimbursement logic |
| `filekeeper/ocr.py` (real implementation) | OCR routing and image/PDF text extraction |
| Licensing/order/support backend | Runs on the hosted service and contains customer, payment, and operational data |
| Build secrets, signing keys, certificates, production configuration | Security-sensitive material |
| Private model data, learned dictionaries, training/evaluation data | Proprietary inputs |

The public `filekeeper/core.py`, `filekeeper/invoice.py`, and
`filekeeper/ocr.py` files are placeholders. They intentionally raise
`ImportError` and contain no algorithm or API implementation.

## Build status

The public tree is **not a complete build**. The official Windows binary and
installer are built in the private repository from the public shell plus the
closed core. Running `build.ps1` in this public tree stops with an explicit
message instead of producing a broken package.

There is no public GitHub Actions build/release workflow. CodeQL remains
enabled for the public Python files.

## License boundary

The public source is licensed under the **WenWen Semi-Open Source License
v1.0** in [LICENSE](../LICENSE). It is source-available, not OSI-approved open
source. Commercial use and redistribution of modified source require written
permission. Excluded materials are not licensed.

Third-party libraries and assets keep their own licenses. They are not
relicensed by the WenWen license.

## Contributions

Contributions are welcome for the public UI, installer scripts, documentation,
and client-side licensing/support UI. Do not submit core algorithm code,
private data, secrets, or binaries. By contributing, you agree to the
contribution license in [LICENSE](../LICENSE) and
[CONTRIBUTING.md](../CONTRIBUTING.md).

## Security

Report vulnerabilities through GitHub private vulnerability reporting:
<https://github.com/harrisonfu8-design/wenwen-open-source/security/advisories/new>.
Do not post exploit details, customer data, or closed-source material in a
public issue.
