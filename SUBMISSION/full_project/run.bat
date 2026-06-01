@echo off
REM ============================================================
REM AI Labor Market Simulation — one-click launcher (Windows)
REM
REM What this does:
REM   1) checks Python is on PATH
REM   2) installs the requirements (only if needed)
REM   3) opens TWO terminal windows:
REM        - backend  on http://localhost:8000
REM        - frontend on http://localhost:5500
REM   4) opens the dashboard in the default browser
REM
REM Close the two terminal windows to stop the system.
REM ============================================================

setlocal ENABLEDELAYEDEXPANSION
cd /d "%~dp0"

echo.
echo ============================================================
echo   AI Labor Market Simulation - Launcher
echo ============================================================
echo.

REM --- 1) Make sure Python is available ---
where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python is not installed or not on PATH.
    echo         Install Python 3.10+ from https://www.python.org
    echo         and tick "Add Python to PATH" during setup.
    echo.
    pause
    exit /b 1
)

REM --- 2) Install/refresh dependencies the first time ---
REM     We touch a marker file so this only runs once.
if not exist ".deps_installed" (
    echo [SETUP] Installing dependencies from requirements.txt ...
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] pip install failed. See the error above.
        pause
        exit /b 1
    )
    echo. > .deps_installed
    echo [SETUP] Dependencies installed.
    echo.
)

REM --- 3) Start backend in a new window ---
echo [RUN] Starting backend  on http://localhost:8000 ...
start "AI Sim - Backend"  cmd /k "cd /d ""%~dp0"" && python -m uvicorn backend.app:app --port 8000 --reload"

REM --- 4) Start frontend in a new window ---
echo [RUN] Starting frontend on http://localhost:5500 ...
start "AI Sim - Frontend" cmd /k "cd /d ""%~dp0"" && python -m http.server 5500 --directory frontend"

REM --- 5) Give the servers a moment, then open the browser ---
echo [RUN] Waiting 4 seconds for servers to start ...
timeout /t 4 /nobreak >nul

start "" http://localhost:5500/index.html

echo.
echo ============================================================
echo   READY
echo   Dashboard: http://localhost:5500/index.html
echo   Backend  : http://localhost:8000/docs   (Swagger)
echo.
echo   To stop : close the two server windows
echo ============================================================
echo.
pause
