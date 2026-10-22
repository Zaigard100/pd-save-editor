# PD Save Editor - автоматическая диагностика для Windows.
# Собирает сведения о системе, запускает редактор с подробным логом и упаковывает всё в zip
# рядом со скриптом (папка reports). Сохранения игры не читаются и не изменяются.
$ErrorActionPreference = 'Continue'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$out = Join-Path $here "reports\report-$stamp"
New-Item -ItemType Directory -Force -Path $out | Out-Null
$summary = Join-Path $out 'summary.txt'
function Say($text) { Write-Host $text; Add-Content -Path $summary -Value $text -Encoding UTF8 }

Say "=== PD Save Editor diagnostics $stamp ==="

# ---------------------------------------------------------------- system
Say "`n--- System"
try {
    $os = Get-CimInstance Win32_OperatingSystem
    Say ("Windows: {0} {1} build {2} ({3})" -f $os.Caption, $os.Version, $os.BuildNumber, $os.OSArchitecture)
} catch { Say "Windows: $_" }
try { Get-CimInstance Win32_Processor | ForEach-Object { Say "CPU: $($_.Name)" } } catch {}
try { Get-CimInstance Win32_VideoController | ForEach-Object { Say "GPU: $($_.Name) driver $($_.DriverVersion)" } } catch {}
try { Say ("RAM: {0:N1} GB" -f ((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB)) } catch {}
Say "User: $env:USERNAME   APPDATA: $env:APPDATA   TEMP: $env:TEMP"

# ---------------------------------------------------------------- WebView2 / .NET
Say "`n--- WebView2 runtime (needed for the editor window)"
$wv = $null
foreach ($k in @('HKLM:\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}',
                 'HKLM:\SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}',
                 'HKCU:\Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}')) {
    try { $v = (Get-ItemProperty -Path $k -ErrorAction Stop).pv; if ($v) { $wv = $v; Say "WebView2: $v  ($k)" } } catch {}
}
if (-not $wv) { Say "WebView2: NOT FOUND (the editor will fall back to the browser)" }
try {
    $rel = (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full' -ErrorAction Stop).Release
    Say ".NET Framework 4 release: $rel"
} catch { Say ".NET Framework 4: NOT FOUND" }

# ---------------------------------------------------------------- the editor executable
Say "`n--- Editor executable"
$cands = @()
$cands += Get-ChildItem -Path $here -Filter 'PDSaveEditor*.exe' -ErrorAction SilentlyContinue
$dl = Join-Path $env:USERPROFILE 'Downloads'
$cands += Get-ChildItem -Path $dl -Filter 'PDSaveEditor*.exe' -ErrorAction SilentlyContinue
$cands = $cands | Sort-Object { if ($_.Name -match 'debug') { 0 } else { 1 } }, LastWriteTime -Descending
foreach ($c in $cands) { Say ("found: {0}  {1:N1} MB  {2}" -f $c.FullName, ($c.Length / 1MB), $c.LastWriteTime) }
$exe = $cands | Select-Object -First 1
if (-not $exe) { Say "No PDSaveEditor*.exe next to this script or in Downloads. Copy the .exe into this folder and run again." }

if ($exe) {
    try {
        $zone = Get-Content -Path $exe.FullName -Stream Zone.Identifier -ErrorAction Stop
        Say "Mark-of-the-Web: present (file downloaded from the internet) -> unblocking"
        Unblock-File -Path $exe.FullName
    } catch { Say "Mark-of-the-Web: none" }
    try {
        $sig = Get-FileHash -Algorithm SHA256 -Path $exe.FullName
        Say "SHA256: $($sig.Hash)"
    } catch {}
}

# ---------------------------------------------------------------- antivirus
Say "`n--- Windows Defender detections (PyInstaller programs are sometimes quarantined)"
try {
    $det = Get-MpThreatDetection -ErrorAction Stop | Where-Object { ($_.Resources -join ' ') -match 'PDSaveEditor|_MEI' }
    if ($det) { $det | Format-List * | Out-String | ForEach-Object { Say $_ } } else { Say "none for PDSaveEditor" }
} catch { Say "Defender query not available: $_" }

# ---------------------------------------------------------------- run the editor
$appdata = Join-Path $env:APPDATA 'PDSaveEditor'
$log = Join-Path $appdata 'pdsave-editor.log'
function Probe($port) {
    try { $r = Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 -Uri "http://127.0.0.1:$port/api/saves"; return $r.StatusCode } catch { return "no answer ($($_.Exception.Message))" }
}
function RunEditor($label, $argList, $seconds) {
    Say "`n--- Run: $label  ($($exe.Name) $argList)"
    $env:PDSAVE_DEBUG = '1'
    $so = Join-Path $out "$label.stdout.txt"; $se = Join-Path $out "$label.stderr.txt"
    $before = if (Test-Path $log) { (Get-Item $log).Length } else { 0 }
    $p = Start-Process -FilePath $exe.FullName -ArgumentList $argList -PassThru -RedirectStandardOutput $so -RedirectStandardError $se
    $port = $null
    for ($i = 0; $i -lt $seconds; $i++) {
        Start-Sleep -Seconds 1
        if ($p.HasExited) { break }
        if (-not $port -and (Test-Path $log)) {
            $m = Select-String -Path $log -Pattern 'http://127\.0\.0\.1:(\d+)/' | Select-Object -Last 1
            if ($m) { $port = $m.Matches[0].Groups[1].Value }
        }
    }
    if ($p.HasExited) { Say "process exited after ~$i s with code $($p.ExitCode)" }
    else {
        Say "process still running after $seconds s (good sign)"
        if ($port) { Say "server http://127.0.0.1:$port -> $(Probe $port)" } else { Say "server port not found in log" }
        Get-Process | Where-Object { $_.Name -like 'msedgewebview2*' } | Select-Object -First 3 | ForEach-Object { Say "webview2 process: $($_.Id) $($_.Name)" }
        try { Stop-Process -Id $p.Id -Force } catch {}
        Get-Process -Name 'PDSaveEditor*' -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    }
    Remove-Item Env:PDSAVE_DEBUG -ErrorAction SilentlyContinue
}
if ($exe) {
    RunEditor 'server-only' '--no-browser --port 8765' 20
    Start-Sleep -Seconds 2
    RunEditor 'window' '--port 8775' 45
}

# ---------------------------------------------------------------- collect files
Say "`n--- Collected files"
if (Test-Path $appdata) {
    Get-ChildItem -Path $appdata -Filter 'pdsave-editor.log*' | ForEach-Object { Copy-Item $_.FullName $out; Say "copied $($_.Name)" }
    if (Test-Path (Join-Path $appdata 'settings.json')) { Copy-Item (Join-Path $appdata 'settings.json') $out }
    Get-ChildItem -Path $appdata -Recurse -ErrorAction SilentlyContinue | Where-Object { -not $_.PSIsContainer } |
        Select-Object FullName, Length, LastWriteTime | Format-Table -AutoSize | Out-String -Width 300 |
        Set-Content -Path (Join-Path $out 'appdata-files.txt') -Encoding UTF8
} else { Say "no $appdata (the editor never got far enough to create it)" }
Get-ChildItem -Path $env:TEMP -Filter '_MEI*' -Directory -ErrorAction SilentlyContinue |
    Select-Object FullName, LastWriteTime | Format-Table -AutoSize | Out-String | Set-Content (Join-Path $out 'temp-mei-dirs.txt') -Encoding UTF8

Say "`n--- Windows event log (last 3 hours)"
try {
    Get-WinEvent -FilterHashtable @{ LogName = 'Application'; StartTime = (Get-Date).AddHours(-3) } -ErrorAction Stop |
        Where-Object { $_.Message -match 'PDSaveEditor|msedgewebview2|python3|WebView2|_MEI' } |
        Select-Object TimeCreated, ProviderName, Id, LevelDisplayName, Message | Format-List | Out-String -Width 400 |
        Set-Content -Path (Join-Path $out 'eventlog.txt') -Encoding UTF8
    Say "saved eventlog.txt"
} catch { Say "event log not available: $_" }

# ---------------------------------------------------------------- zip
$zip = Join-Path $here "reports\pdsave-debug-$stamp.zip"
Compress-Archive -Path (Join-Path $out '*') -DestinationPath $zip -Force
Say "`nREPORT: $zip"
Write-Host "`nSend this zip file. Press Enter to close." -ForegroundColor Green
[void](Read-Host)
