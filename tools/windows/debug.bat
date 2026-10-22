@echo off
rem PD Save Editor: automatic diagnostics. Creates reports\pdsave-debug-*.zip next to this file.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0debug.ps1"
