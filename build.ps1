# Semi-open packaging reference. This public tree is incomplete and refuses to build.
# Run from the repository root: .\build.ps1 -Python .\.venv\Scripts\python.exe
param(
    [string]$Python = 'python'
)

$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot
Set-Location -LiteralPath $here

# Semi-open public tree: the closed core, invoice, and OCR modules are
# intentionally omitted. Refuse to produce a broken package.
throw "This is the semi-open public source tree. The closed core is not included, so a complete client cannot be built here. See docs/OPEN_SOURCE_SCOPE.md."

$ver = [regex]::Match((Get-Content -LiteralPath 'filekeeper\license.py' -Raw), 'VERSION = "([^"]+)"').Groups[1].Value
$vi = [regex]::Match((Get-Content -LiteralPath 'assets\version_info.txt' -Raw), "FileVersion', '([^']+)'").Groups[1].Value
$nsi = [regex]::Match((Get-Content -LiteralPath 'installer\install.nsi' -Raw), '!define PRODUCT_VERSION "([^"]+)"').Groups[1].Value
if (-not $ver -or $ver -ne $vi -or $ver -ne $nsi) {
    throw "Version mismatch: license.py=$ver version_info=$vi install.nsi=$nsi"
}

Write-Host "BUILD_VERSION=$ver"
$buildDir = Join-Path $here 'build'
$assetsDir = Join-Path $here 'assets'
New-Item -ItemType Directory -Path $buildDir -Force | Out-Null

$pyArgs = @(
    '--noconfirm', '--clean', '--onedir', '--windowed', '--noupx',
    '--specpath', $buildDir,
    '--name', '文件管家',
    '--icon', (Join-Path $assetsDir 'filekeeper.ico'),
    '--version-file', (Join-Path $assetsDir 'version_info.txt'),
    '--manifest', (Join-Path $assetsDir 'app.manifest'),
    '--add-data', "$assetsDir;assets",
    '--collect-all', 'tkinterdnd2',
    '--hidden-import', 'docx',
    '--hidden-import', 'openpyxl',
    '--hidden-import', 'pypdf',
    '--hidden-import', 'PIL',
    '--hidden-import', 'PIL.Image',
    '--hidden-import', 'winocr',
    '--hidden-import', 'winrt.windows.media.ocr',
    '--hidden-import', 'winrt.windows.graphics.imaging',
    '--hidden-import', 'winrt.windows.storage.streams',
    '--hidden-import', 'winrt.windows.globalization',
    '--collect-submodules', 'winrt',
    '--hidden-import', 'pymupdf',
    '--exclude-module', 'onnxruntime',
    '--exclude-module', 'pymupdf.layout',
    '--exclude-module', 'pymupdf_layout',
    '--exclude-module', 'pymupdf4llm',
    '--hidden-import', 'filekeeper.invoice',
    '--hidden-import', 'filekeeper.ocr',
    (Join-Path $here 'run.py')
)

& $Python -m PyInstaller @pyArgs
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed' }

$dist = Join-Path $here 'dist\文件管家'
$payload = Join-Path $here 'installer\app'
if (-not (Test-Path -LiteralPath (Join-Path $dist '文件管家.exe'))) { throw 'Main executable not found' }
if (Test-Path -LiteralPath $payload) { Remove-Item -LiteralPath $payload -Recurse -Force }
Copy-Item -LiteralPath $dist -Destination $payload -Recurse -Force

$v1 = (Get-Item -LiteralPath (Join-Path $dist '文件管家.exe')).VersionInfo.FileVersion
$v2 = (Get-Item -LiteralPath (Join-Path $payload '文件管家.exe')).VersionInfo.FileVersion
if ($v1 -ne $v2) { throw "Installer payload version mismatch: $v1 / $v2" }

$exe = Join-Path $dist '文件管家.exe'
$exeHash = (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash
$sig = Get-AuthenticodeSignature -LiteralPath $exe
$releaseDir = Join-Path $here 'release'
New-Item -ItemType Directory -Path $releaseDir -Force | Out-Null

$commit = $env:GITHUB_SHA
if (Test-Path -LiteralPath '.git') {
    try {
        $commit = (& git rev-parse HEAD).Trim()
    } catch {
        $commit = $env:GITHUB_SHA
    }
}

$manifest = [ordered]@{
    version = $ver
    built_at = (Get-Date).ToString('s')
    git_commit = $commit
    app_dir = $dist
    app_dir_bytes = (Get-ChildItem -LiteralPath $dist -Recurse -File | Measure-Object Length -Sum).Sum
    app_dir_files = (Get-ChildItem -LiteralPath $dist -Recurse -File | Measure-Object).Count
    exe = $exe
    exe_bytes = (Get-Item -LiteralPath $exe).Length
    exe_sha256 = $exeHash
    authenticode = $sig.Status.ToString()
    signed = ($null -ne $sig.SignerCertificate)
}
$manifestPath = Join-Path $releaseDir "manifest_v$ver.json"
$manifest | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
Write-Host "MANIFEST=$manifestPath"
Write-Host "EXE=$exe BYTES=$($manifest.exe_bytes) SHA256=$exeHash SIGNATURE=$($manifest.authenticode)"
