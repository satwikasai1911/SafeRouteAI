@echo off
cd /d "%~dp0backend"
python import_sample_csv.py
echo.
echo Sample data imported as UNVERIFIED.
pause
