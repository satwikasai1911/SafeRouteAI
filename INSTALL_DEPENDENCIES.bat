@echo off
cd /d "%~dp0backend"
echo Installing SafeRoute AI Python packages...
python -m pip install --upgrade "pip<25.1"
if errorlevel 1 goto error
python -m pip install -r requirements.txt
if errorlevel 1 goto error
echo.
echo Installation complete. Now double-click START_BACKEND.bat
pause
exit /b 0
:error
echo.
echo Installation failed. Take a photo of this Command Prompt error and share it.
pause
exit /b 1
