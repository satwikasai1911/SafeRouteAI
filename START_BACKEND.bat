@echo off
cd /d "%~dp0backend"
echo Enter a private admin key (at least 20 characters).
set /p SAFEROUTE_ADMIN_KEY=Admin key: 
if "%SAFEROUTE_ADMIN_KEY%"=="" (echo Admin key cannot be empty.& pause & exit /b 1)
set SAFEROUTE_ALLOWED_ORIGINS=*
echo Starting SafeRoute AI API on port 8000...
python main.py
pause
