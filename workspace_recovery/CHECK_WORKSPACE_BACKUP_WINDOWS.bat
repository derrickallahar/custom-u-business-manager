@echo off
setlocal
cd /d "%~dp0"
if not exist ".workspace_venv\Scripts\python.exe" goto setup
".workspace_venv\Scripts\python.exe" recover_workspace.py
pause
exit /b
:setup
echo Run SETUP_WINDOWS.bat once before this recovery check.
pause
exit /b 1
