@echo off
echo ========================================
echo Coach AI - Ollama Setup Script
echo ========================================
echo.

REM Check if Ollama is installed
where ollama >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Ollama is not installed.
    echo.
    echo Please install Ollama first:
    echo 1. Visit: https://ollama.ai/download
    echo 2. Download and run the Windows installer
    echo 3. Re-run this script
    echo.
    pause
    exit /b 1
)

echo [OK] Ollama is installed
echo.

REM Check if Ollama is running
echo Checking if Ollama is running...
ollama list >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [WARNING] Ollama might not be running. Starting Ollama...
    start "" "ollama"
    timeout /t 5 /nobreak >nul
)

echo [OK] Ollama is running
echo.

REM Pull the model
echo Pulling Llama 3.2 3B model (~2GB download)...
echo This may take 2-5 minutes depending on your internet speed.
echo.
ollama pull llama3.2:3b

if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to pull model. Check your internet connection.
    pause
    exit /b 1
)

echo.
echo [OK] Model downloaded successfully
echo.

REM Set environment variable
echo Setting environment variable USE_OLLAMA=true...
setx USE_OLLAMA "true"

echo.
echo ========================================
echo Setup Complete!
echo ========================================
echo.
echo Next steps:
echo 1. RESTART your terminal/PowerShell for env var to take effect
echo 2. Run: python -m streamlit run streamlit_app.py
echo 3. Navigate to "Ask Coach" tab
echo 4. Ask a question and see AI-generated answers!
echo.
echo Models installed:
ollama list
echo.
pause

