@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set "DEMO_PYTHON=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if exist "%DEMO_PYTHON%" goto bundled
where py >nul 2>nul
if not errorlevel 1 goto pylauncher
where python >nul 2>nul
if not errorlevel 1 goto systempython
echo Python 3 is required. Open this project in Codex and ask to start the demo.
pause
exit /b 1
:bundled
"%DEMO_PYTHON%" "%~dp0scripts\start_demo.py"
goto finished
:pylauncher
py -3 "%~dp0scripts\start_demo.py"
goto finished
:systempython
python "%~dp0scripts\start_demo.py"
:finished
pause
