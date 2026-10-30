@echo off
cd /d "%~dp0frontend"
echo Open this address in the laptop browser: http://localhost:5500
python -m http.server 5500 --bind 0.0.0.0
pause
