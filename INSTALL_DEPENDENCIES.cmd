@echo off
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  python -m pip install -r requirements.txt
) else (
  py -3 -m pip install -r requirements.txt
)
if errorlevel 1 pause
