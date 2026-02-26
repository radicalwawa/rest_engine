@echo off
cd /d "%~dp0.."
where py >nul 2>&1
if errorlevel 1 (echo py launcher not found. Install Python with py or add to PATH. & exit /b 1)
py -X faulthandler python/validate.py
exit /b %errorlevel%
