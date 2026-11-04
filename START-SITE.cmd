@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
if exist "%~dp0.venv\Scripts\python.exe" (
  "%~dp0.venv\Scripts\python.exe" "%~dp0scripts\start_django.py"
  goto finished
)
set "IR_PYTHON=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if exist "%IR_PYTHON%" (
  "%IR_PYTHON%" "%~dp0scripts\start_django.py"
  goto finished
)
where py >nul 2>nul
if not errorlevel 1 (
  py -3 "%~dp0scripts\start_django.py"
  goto finished
)
python "%~dp0scripts\start_django.py"
:finished
pause
