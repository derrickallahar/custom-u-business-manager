@echo off
setlocal
cd /d "%~dp0"
echo Custom U v0.7.7 - Repository contents check
set "BAD=0"
for %%F in (requirements.txt runtime.txt Procfile cloud_main.py cloud_server.py pilot_core.py staff_auth.py static\index.html static\app.js static\style.css) do (
 if not exist "%%F" (
  echo MISSING: %%F
  set "BAD=1"
 )
)
if "%BAD%"=="1" (
 echo ERROR: Extract all files from the ZIP and preserve the static folder.
) else (
 echo CHECK COMPLETE: All required application source files are present.
 echo Upload THE CONTENTS of this folder to the ROOT of your private GitHub repository.
)
echo.
echo NEVER upload your database connection URI, password, CA cert, or customer data.
pause
