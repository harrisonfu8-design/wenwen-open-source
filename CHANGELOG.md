# Changelog

## v1.5.20 — 2026-11-23 (official download, unsigned)

- Added promo-code input to the client registration / renewal window, with
  apply, clear, and benefit text.
- Promo codes support percentage discount, fixed discount, bonus license days,
  total-use limits, per-machine limits, and expiry; the server recalculates the
  final amount and records the code, discount, and bonus days on the order.
- Added a backend promo-code management page; bonus days are added to the
  license when payment is confirmed.
- Bumped client, executable metadata, and NSIS installer version to `1.5.20.0`.
- Official installer:
  <https://sw.olilily.com/dl/WenWen_Setup_v1.5.20.exe>
  · SHA-256 `68DF982626EF09829D8EEC5FCB49D362464580B1CE231F3691AE6ABC07DF4C92`
  · `NotSigned`.
- Prepared Store-identity MSIX `WenWen_1.5.20.0_x64_store.msix`
  (113,699,326 bytes · SHA-256
  `D0C5F8BD1A561F0A8A69E2220BAA5E3D16CF4997D82A3180E83089EE8F139C40`);
  not yet uploaded to Partner Center.

## 2026-11-23 — semi-open transition

- Public repository changed from full MIT open source to **semi-open source**.
- Removed the core recognition, invoice-extraction, and OCR implementations
  from the public tree. `filekeeper/core.py`, `invoice.py`, and `ocr.py` are
  now placeholders; the real implementations remain in the private repository.
- Replaced the MIT license with the WenWen Semi-Open Source License v1.0.
- Retired the public build/release workflow and the old public CI release.
  Official downloads remain on the official website with published SHA-256.
- Added `docs/OPEN_SOURCE_SCOPE.md` and updated source, verification, media,
  FAQ, security, and contributing documents.

## v1.5.19 — 2026-11-23 (official download, unsigned)

- Bumped client, executable metadata, and NSIS installer version to `1.5.19.0`.
- Removed the backend admin address, default admin account, and default password
  from the installer’s `注册说明.txt`; the public copy keeps only user-facing
  registration and subscription instructions.
- Added GitHub Actions build provenance attestations for uploaded artifacts.
- Built from the public workflow and published as a pre-release with the client
  and installer attached, plus SHA-256 hashes.
- Still `NotSigned`; no trusted Authenticode certificate has been issued.
- Packaged a Partner Center-identity MSIX for the Microsoft Store and submitted
  it for certification on 2026-11-23. Store listing in Simplified Chinese and
  English, IARC age rating, zero-price availability, and the `runFullTrust`
  justification are complete. The submission is in certification; Store installs
  will be re-signed by Microsoft after it passes.
- Official site download switched to v1.5.19 on 2026-11-23. Older installers were retired from the public download directory because their `注册说明.txt` contained the backend admin address and default credentials; the backend default password is no longer valid.

## v1.5.18 — 2026-11-22

- Added the in-app “使用教程” entry pointing to <https://sw.olilily.com/guide/>.
- Published the illustrated user guide and the official download page.
- Fixed installer version metadata so uninstall entries use the release version
  instead of a stale value.
- Published the Windows client and installer source under the MIT License
  (historical; superseded by the semi-open license on 2026-11-23).
- Added GitHub Actions build workflow, SignPath configuration templates, and a
  public code-signing policy.
- Official installer remains unsigned (`NotSigned`).

## v1.5.17 and earlier

Earlier builds were distributed through the official site before the public
repository existed. Their source is not part of this repository’s public
history.
