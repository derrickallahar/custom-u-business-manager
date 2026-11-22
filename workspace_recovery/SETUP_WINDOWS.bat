@echo off
setlocal
cd /d "%~dp0"
py -3 -m venv .workspace_venv
if errorlevel 1 goto failed
".workspace_venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
".workspace_venv\Scripts\python.exe" -c "from zoneinfo import ZoneInfo; ZoneInfo('America/Nassau'); print('Bahamas time-zone data: OK')"
if errorlevel 1 goto failed
echo Setup complete. Run CHECK_WORKSPACE_BACKUP_WINDOWS.bat next.
pause
exit /b 0
:failed
echo Setup failed. Check the error above. Python 3 and an internet connection for installing dependencies are required.
pause
exit /b 1
