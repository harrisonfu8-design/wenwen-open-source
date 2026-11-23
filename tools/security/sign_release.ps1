# 文件管家 Authenticode 代码签名脚本（开源 osslsigncode / Windows signtool 双后端）
# 用法示例：
#   .\sign_release.ps1 -PfxPath C:\keys\filekeeper.pfx -PfxPassword '***' `
#     -Files 'dist\文件管家\文件管家.exe','installer\app\文件管家.exe'
#   然后重新编译 NSIS 安装包，再对安装包执行一次：
#   .\sign_release.ps1 -PfxPath ... -Files 'installer\文件管家_安装包_v1.5.9.exe'
#
# 说明：必须“先签主程序，再打安装包，最后签安装包”，否则安装包内嵌的仍是未签名 exe。
param(
    [Parameter(Mandatory = $true)][string[]]$Files,
    [Parameter(Mandatory = $true)][string]$PfxPath,
    [Parameter(Mandatory = $true)][string]$PfxPassword,
    [string]$TimestampUrl = 'http://timestamp.digicert.com',
    [string]$Description = '文件管家 - 智能文件整理',
    [string]$Url = 'https://sw.olilily.com/'
)

$ErrorActionPreference = 'Stop'

function Find-Ossligncode {
    $cmd = Get-Command osslsigncode.exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $root = Join-Path $env:LOCALAPPDATA 'Microsoft\WinGet\Packages'
    if (Test-Path $root) {
        $hit = Get-ChildItem $root -Recurse -Filter osslsigncode.exe -ErrorAction SilentlyContinue |
            Select-Object -First 1
        if ($hit) { return $hit.FullName }
    }
    return $null
}

function Find-Signtool {
    $cmd = Get-Command signtool.exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $kits = 'C:\Program Files (x86)\Windows Kits\10\bin'
    if (Test-Path $kits) {
        $hit = Get-ChildItem $kits -Recurse -Filter signtool.exe -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -match '\x64\' } | Select-Object -First 1
        if ($hit) { return $hit.FullName }
    }
    return $null
}

if (-not (Test-Path -LiteralPath $PfxPath)) { throw "找不到证书文件：$PfxPath" }
$files = @($Files | ForEach-Object { (Resolve-Path -LiteralPath $_).Path })
foreach ($f in $files) {
    if (-not (Test-Path -LiteralPath $f -PathType Leaf)) { throw "找不到待签名文件：$f" }
}

$signtool = Find-Signtool
$ossl = Find-Ossligncode
if (-not $signtool -and -not $ossl) {
    throw '未找到 signtool.exe 或 osslsigncode.exe。可执行：winget install MichalTrojnara.osslsigncode'
}

foreach ($f in $files) {
    Write-Host "SIGNING $f"
    if ($signtool) {
        & $signtool sign /f $PfxPath /p $PfxPassword /fd SHA256 `
            /tr $TimestampUrl /td SHA256 /d $Description /du $Url $f
        if ($LASTEXITCODE -ne 0) { throw "signtool 签名失败：$f" }
    }
    else {
        $tmp = "$f.signed"
        if (Test-Path -LiteralPath $tmp) { Remove-Item -LiteralPath $tmp -Force }
        & $ossl sign -pkcs12 $PfxPath -pass $PfxPassword -h sha256 `
            -n $Description -i $Url -t $TimestampUrl -in $f -out $tmp
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $tmp)) {
            throw "osslsigncode 签名失败：$f"
        }
        Move-Item -LiteralPath $tmp -Destination $f -Force
    }

    $sig = Get-AuthenticodeSignature -LiteralPath $f
    $hasSigner = $null -ne $sig.SignerCertificate
    Write-Host ("  STATUS={0} SIGNER={1} SUBJECT={2}" -f `
        $sig.Status, $hasSigner, $(if ($hasSigner) { $sig.SignerCertificate.Subject } else { '' }))
    if (-not $hasSigner) { throw "签名后仍未检测到签名证书：$f" }
    # 正式发布必须信任链有效；自签名证书只用于流水线联调，不能对外发布。
    if ($sig.Status -ne 'Valid') {
        Write-Warning "签名已写入，但证书信任状态为 $($sig.Status)（自签名/未受信证书不可公开发布）"
    }
}

Write-Host 'DONE. 若签名了主程序，请重新编译 NSIS 安装包，再对安装包签名。'
