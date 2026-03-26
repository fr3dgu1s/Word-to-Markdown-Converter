@echo off
color 0A
title Docling AI Server Engine

echo ==========================================
echo    Starting Docling Local AI Server...
echo ==========================================
echo.

:: 1. Force the terminal to the exact app folder (Foolproof step)
cd /d C:\temp\Word-to-MD-App

:: 2. Start the Python server in a new background window
start "Docling Backend" cmd /k "python -m uvicorn server:app"

:: 3. Wait 4 seconds for the AI to load into memory
echo Waiting for the AI engine to boot...
timeout /t 4 /nobreak > nul

:: 4. Open the web interface
echo Opening your app...
start http://localhost:8000

:: 5. Close this green launcher window
exit