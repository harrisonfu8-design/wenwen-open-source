# Build the NSIS installer from installer\app.
# Signing is performed by the GitHub Actions + SignPath workflow, not by this script.
param()

$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot
Set-Location -LiteralPath $here
$root = Split-Path -Parent $here

$ver = [regex]::Match((Get-Content -LiteralPath (Join-Path $root 'filekeeper\license.py') -Raw), 'VERSION = "([^"]+)"').Groups[1].Value
if (-not $ver) { throw 'Cannot read VERSION from filekeeper\license.py' }

$exe = Join-Path $here 'app\文件管家.exe'
if (-not (Test-Path -LiteralPath $exe)) { throw 'installer\app\文件管家.exe not found. Run build.ps1 first.' }
$exeVer = (Get-Item -LiteralPath $exe).VersionInfo.FileVersion
if ($exeVer -ne $ver) { throw "Main executable version $exeVer does not match source version $ver" }

$makensis = (Get-Command makensis.exe -ErrorAction SilentlyContinue).Source
if (-not $makensis) {
    foreach ($candidate in @(
        'C:\Program Files (x86)\NSIS\makensis.exe',
        'C:\Program Files\NSIS\makensis.exe'
    )) {
        if (Test-Path -LiteralPath $candidate) { $makensis = $candidate; break }
    }
}
if (-not $makensis) { throw 'makensis.exe not found. Install NSIS 3 and add it to PATH.' }

$shortVer = $ver -replace '\.0$', ''
& $makensis "/DPRODUCT_VERSION=$ver" "/DPRODUCT_VERSION_SHORT=$shortVer" 'install.nsi'
if ($LASTEXITCODE -ne 0) { throw 'NSIS build failed' }

$out = Join-Path $here "文文_安装包_v$shortVer.exe"
if (-not (Test-Path -LiteralPath $out)) { throw "Installer not generated: $out" }

$hash = (Get-FileHash -LiteralPath $out -Algorithm SHA256).Hash
$sig = Get-AuthenticodeSignature -LiteralPath $out
Write-Host "INSTALLER=$out BYTES=$((Get-Item $out).Length) SHA256=$hash"
Write-Host "SIGNATURE=$($sig.Status)"
