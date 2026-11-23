# MSIX packaging and Microsoft Store submission notes

These notes record the MSIX packaging work, the `0x8007007b` fix, and the current
Microsoft Store submission state for WenWen.

## Store submission status

As of 2026-11-23, the Store MSIX has been submitted and is in certification.

- Store product: 文文-文件和发票管理
- Store ID: `9P9JJXPMMX1G`
- Public listing: <https://apps.microsoft.com/detail/9P9JJXPMMX1G>
- Submission: Submission 1
- Current state: 正在认证 / in certification
- Publish setting: publish automatically after certification passes
- Store listing: Simplified Chinese and English (United States), both complete
- Age rating: IARC questionnaire completed
- Restricted capability: `runFullTrust` justification submitted for approval

The submitted package is:

- Package: `WenWen_1.5.19.0_x64_store.msix`
- Size: 113,697,476 bytes
- Version: `1.5.19.0`
- Architecture: `x64`
- Entry point: `Windows.FullTrustApplication`
- Capability: `rescap:runFullTrust`
- Device family: `Windows.Desktop`, minimum `10.0.17763.0`
- Local signature: unsigned

The package uses the `Package/Identity/Name` and
`Package/Identity/Publisher` values reserved in Partner Center, with
`PublisherDisplayName` set to the reserved publisher name. `Properties/DisplayName`
and `uap:VisualElements@DisplayName` use the reserved product name
`文文-文件和发票管理`.

Partner Center accepted the upload after validation. Microsoft re-signs
Store-distributed MSIX packages during the Store publishing pipeline, so a
successfully certified Store install does not depend on a local self-signed
certificate. The direct NSIS installer and direct downloads remain `NotSigned`.

## v1.5.20 Store package prepared (not submitted)

A v1.5.20.0 Store-identity package has been built locally from the same full
client layout, with the `default-docx-template` folder excluded. It has not
been uploaded to Partner Center; Submission 1 remains the v1.5.19.0 package.

- Package: `WenWen_1.5.20.0_x64_store.msix`
- Size: 113,699,326 bytes
- SHA-256: `D0C5F8BD1A561F0A8A69E2220BAA5E3D16CF4997D82A3180E83089EE8F139C40`
- Version: `1.5.20.0`
- Architecture: `x64`
- Local signature: unsigned

## Layout fix for 0x8007007b

`python-docx` ships an unpacked copy of its default template under:

```
_internal\docx\templates\default-docx-template
```

That folder contains OPC-reserved names (`_rels` and `[Content_Types].xml`).
MSIX part names reject them and `MakeAppx` fails with `0x8007007b`.

The folder is redundant: `docx/api.py` loads
`templates/default.docx`, not `default-docx-template`. Exclude the unpacked
template folder from the MSIX layout, keep `default.docx`, and packing succeeds.

A first Store-identity package used the short display name `文文` and was
rejected because that name was not reserved. Rebuilding with the reserved name
`文文-文件和发票管理` fixed the validation error.

## Historical local signature test

Before the Store submission, a self-signed package was built to verify the
packaging and signing steps:

- Package: `WenWen_1.5.19.0_x64_clean.msix`
- Size (signed): 113,677,364 bytes
- SHA-256: `888F5716F3F4398F42179EDF48C776595292DF0B0A4225B7427175745A341057`
- Identity name: `Olilily.WenWen.Test`
- Publisher: `CN=WenWen MSIX Test`

That package was only a local test. It is not the Store submission package.

A self-signed MSIX needs its root certificate trusted, and sideloading must be
allowed. On the test machine neither condition was enabled, so
`Add-AppxPackage` stopped with `0x800B0109` (untrusted root) or `0x80073CFF`
(sideloading disabled). The package itself built and signed successfully.

## Store submission checklist

Completed for Submission 1:

1. Microsoft Store developer account and reserved product name.
2. Partner Center publisher identity copied into `AppxManifest.xml`.
3. MSIX built from the full client layout, excluding the redundant
   `default-docx-template` folder.
4. Store listing assets, privacy policy URL, support contact, age rating,
   pricing and commerce settings supplied.
5. Restricted capability justification supplied for `runFullTrust`.
6. Submitted for certification.

Still external to this repository:

- Microsoft certification result.
- Store re-signing and public availability after certification.
- Any certification failure or policy feedback from Microsoft.
