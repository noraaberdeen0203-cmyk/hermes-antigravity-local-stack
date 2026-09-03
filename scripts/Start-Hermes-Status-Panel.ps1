#Requires -Version 5.1
param(
    [string]$Distro,
    [string]$Helper,
    [string]$PanelUrl = 'http://127.0.0.1:9120/',
    [string]$HealthUrl = 'http://127.0.0.1:9120/api/health'
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($Distro)) {
    $Distro = $env:HERMES_WSL_DISTRO
}
if ([string]::IsNullOrWhiteSpace($Helper)) {
    $Helper = $env:STATUS_PANEL_HELPER
}
if ([string]::IsNullOrWhiteSpace($Distro) -or [string]::IsNullOrWhiteSpace($Helper)) {
    throw '请提供 -Distro 和 -Helper，或设置 HERMES_WSL_DISTRO 与 STATUS_PANEL_HELPER。'
}

function Test-HermesStatusPanel {
    try {
        $request = [System.Net.HttpWebRequest]::Create($HealthUrl)
        $request.Method = 'GET'
        $request.Proxy = [System.Net.GlobalProxySelection]::GetEmptyWebProxy()
        $request.Timeout = 3000
        $request.ReadWriteTimeout = 3000
        $request.KeepAlive = $false
        $response = $request.GetResponse()
        $reader = $null
        try {
            $reader = New-Object System.IO.StreamReader($response.GetResponseStream())
            $body = $reader.ReadToEnd()
            return ([int]$response.StatusCode -eq 200 -and $body -match '"ok"\s*:\s*true')
        } finally {
            if ($reader) { $reader.Dispose() }
            $response.Close()
        }
    } catch {
        return $false
    }
}

if (-not (Test-HermesStatusPanel)) {
    & wsl.exe -d $Distro -- bash $Helper | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Hermes Status Panel 启动失败（退出码 $LASTEXITCODE）。"
    }

    $deadline = (Get-Date).AddSeconds(30)
    do {
        Start-Sleep -Milliseconds 500
        if (Test-HermesStatusPanel) { break }
    } while ((Get-Date) -lt $deadline)
}

if (-not (Test-HermesStatusPanel)) {
    throw 'Hermes Status Panel 未在 30 秒内就绪。'
}

Start-Process -FilePath $PanelUrl
