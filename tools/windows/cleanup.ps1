# PD Save Editor - уборщик для Windows.
# Закрывает редактор и удаляет его служебные данные: извлечённые данные игры, настройки, лог,
# кэш окна WebView2 и остатки распаковки PyInstaller (%TEMP%\_MEI*).
# Сохранения игры (odsave*.sav) НЕ трогаются.
$ErrorActionPreference = 'Continue'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "PD Save Editor cleanup" -ForegroundColor Yellow
Write-Host "Removes: %APPDATA%\PDSaveEditor, WebView2 cache of the editor, %TEMP%\_MEI* leftovers."
Write-Host "Game saves are NOT touched."
$answer = Read-Host "Continue? (Y/n)"
if ($answer -match '^[nNнН]') { exit }

Get-Process -Name 'PDSaveEditor*' -ErrorAction SilentlyContinue | ForEach-Object {
    Write-Host "closing $($_.Name) ($($_.Id))"; Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 1

$appdata = Join-Path $env:APPDATA 'PDSaveEditor'
if (Test-Path $appdata) {
    # keep the last log on the flash drive before deleting it
    $keep = Join-Path $here ("reports\log-before-cleanup-" + (Get-Date -Format 'yyyyMMdd-HHmmss'))
    New-Item -ItemType Directory -Force -Path $keep | Out-Null
    Get-ChildItem -Path $appdata -Filter 'pdsave-editor.log*' -ErrorAction SilentlyContinue | Copy-Item -Destination $keep
    Remove-Item -Recurse -Force $appdata -ErrorAction SilentlyContinue
    if (Test-Path $appdata) { Write-Host "could not fully remove $appdata (file in use?)" -ForegroundColor Red }
    else { Write-Host "removed $appdata (old log copied to $keep)" }
} else { Write-Host "no $appdata" }

foreach ($d in @((Join-Path $env:APPDATA 'pywebview'), (Join-Path $env:LOCALAPPDATA 'pywebview'))) {
    if (Test-Path $d) { Remove-Item -Recurse -Force $d -ErrorAction SilentlyContinue; Write-Host "removed $d" }
}

$mei = Get-ChildItem -Path $env:TEMP -Filter '_MEI*' -Directory -ErrorAction SilentlyContinue
foreach ($m in $mei) {
    Remove-Item -Recurse -Force $m.FullName -ErrorAction SilentlyContinue
    if (-not (Test-Path $m.FullName)) { Write-Host "removed $($m.FullName)" }
}

Write-Host "`nDone. Press Enter to close." -ForegroundColor Green
[void](Read-Host)
