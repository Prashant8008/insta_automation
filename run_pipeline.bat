@echo off
cd /d "%~dp0"

echo ==================================================
echo [1/3] Starting local ngrok in background...
echo ==================================================
start "ngrok" /B "%~dp0ngrok.exe" http 8000
timeout /t 5 >nul

echo ==================================================
echo [2/3] Executing Instagram Posting Pipeline...
echo ==================================================
set PYTHONIOENCODING=utf-8
python run_instagram_pipeline.py %*

echo ==================================================
echo [3/3] Shutting down ngrok...
echo ==================================================
taskkill /f /im ngrok.exe >nul 2>&1

echo ==================================================
echo Automation Task Completed!
echo ==================================================
