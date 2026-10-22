@echo off
rem PD Save Editor: cleanup (closes the editor, removes its data, WebView2 cache and _MEI temp leftovers; saves are kept)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0cleanup.ps1"
