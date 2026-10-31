@echo off
setlocal
cd /d "%~dp0"
echo CUSTOM U v0.7.7 - Prepare certificate for DigitalOcean
set /p "CERTPATH=Enter full path to your already verified Supabase CA certificate: "
set "CERTPATH=%CERTPATH:"=%"
if not exist "%CERTPATH%" (
 echo ERROR: Cannot find certificate at that location.
 pause
 exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -Command "$bytes=[IO.File]::ReadAllBytes($env:CERTPATH); $txt=[Text.Encoding]::ASCII.GetString($bytes); if (-not $txt.StartsWith('-----BEGIN CERTIFICATE-----')) { throw 'Not a PEM certificate' }; $val=[Convert]::ToBase64String($bytes); Set-Clipboard -Value $val; Write-Host 'SUCCESS: Base64 CA certificate copied to Windows clipboard.'"
if errorlevel 1 (
 echo ERROR: Could not encode certificate.
) else (
 echo Paste the copied value into the DigitalOcean CUSTOMU_PG_CA_B64 environment variable.
 echo Mark it ENCRYPTED and RUN TIME. Do NOT paste it into GitHub or this chat.
)
pause
