# 发布前安全体检：Authenticode 状态、SHA256、Windows Defender、可选 ClamAV
# 用法：
#   .\scan_release.ps1 -Paths 'installer\文件管家_安装包_v1.5.9.exe','dist\文件管家'
param(
    [Parameter(Mandatory = $true)][string[]]$Paths,
    [string]$OutFile = ''
)

$ErrorActionPreference = 'Stop'
$results = @()

function Defender-Scan([string]$path) {
    $mp = 'C:\Program Files\Windows Defender\MpCmdRun.exe'
    if (-not (Test-Path $mp)) { return @{ ok = $null; detail = 'MpCmdRun 不存在' } }
    $out = & $mp -Scan -ScanType 3 -File $path 2>&1 | Out-String
    $exit = $LASTEXITCODE
    $threat = ($out -match 'found (?:\d+ )?threats|Threat found|发现威胁|检测到威胁')
    $clean = (($exit -eq 0) -and (-not $threat)) -or ($out -match 'found no threats|no threats found|未发现威胁')
    return @{ ok = [bool]$clean; detail = "exit=$exit`n$($out.Trim())" }
}

function Clam-Scan([string]$path) {
    $clam = Get-Command clamscan.exe -ErrorAction SilentlyContinue
    if (-not $clam) { return @{ ok = $null; detail = 'ClamAV 未安装' } }
    $out = & $clam.Source -i $path 2>&1 | Out-String
    $clean = ($LASTEXITCODE -eq 0)
    return @{ ok = [bool]$clean; detail = $out.Trim() }
}

foreach ($p in $Paths) {
    $full = (Resolve-Path -LiteralPath $p).Path
    $item = Get-Item -LiteralPath $full
    if ($item.PSIsContainer) {
        $mainExe = Join-Path $full '文件管家.exe'
        if (Test-Path -LiteralPath $mainExe) {
            $sig = Get-AuthenticodeSignature -LiteralPath $mainExe
            $signed = $null -ne $sig.SignerCertificate
            $results += [ordered]@{
                path = $mainExe; kind = 'main-exe'; bytes = (Get-Item $mainExe).Length
                sha256 = (Get-FileHash -LiteralPath $mainExe -Algorithm SHA256).Hash
                authenticode = $sig.Status.ToString(); signed = $signed
                signer = if ($signed) { $sig.SignerCertificate.Subject } else { '' }
            }
        }
        $def = Defender-Scan $full
        $clam = Clam-Scan $full
    }
    else {
        $sig = Get-AuthenticodeSignature -LiteralPath $full
        $signed = $null -ne $sig.SignerCertificate
        $results += [ordered]@{
            path = $full; kind = 'file'; bytes = $item.Length
            sha256 = (Get-FileHash -LiteralPath $full -Algorithm SHA256).Hash
            authenticode = $sig.Status.ToString(); signed = $signed
            signer = if ($signed) { $sig.SignerCertificate.Subject } else { '' }
        }
        $def = Defender-Scan $full
        $clam = Clam-Scan $full
    }
    $results[-1].defender_ok = $def.ok
    $results[-1].defender_detail = $def.detail
    $results[-1].clamav_ok = $clam.ok
    $results[-1].clamav_detail = $clam.detail
}

$json = $results | ConvertTo-Json -Depth 6
if ($OutFile) { $json | Set-Content -LiteralPath $OutFile -Encoding UTF8 }
$json

