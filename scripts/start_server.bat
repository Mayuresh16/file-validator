@echo off
REM ================================================================
REM Start the File Validator web server (Windows CMD / batch).
REM
REM Usage:
REM   start_server.bat          -- starts in dev mode (default)
REM   start_server.bat dev      -- starts in dev mode
REM   start_server.bat prod     -- starts in prod mode
REM ================================================================
setlocal enabledelayedexpansion

REM -- Determine environment (default: dev) --
set "ENV=%~1"
if "%ENV%"=="" set "ENV=dev"

REM -- Normalise to lowercase --
if /I "%ENV%"=="DEV"  set "ENV=dev"
if /I "%ENV%"=="PROD" set "ENV=prod"

REM -- Resolve paths --
set "SCRIPT_DIR=%~dp0"
REM Strip trailing backslash
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

for %%I in ("%SCRIPT_DIR%\..") do set "REPO_ROOT=%%~fI"
set "MAIN_MODULE=%REPO_ROOT%\file-validator-webserver\src\file_validator_webserver\main.py"

echo ================================
echo Synchronizing dependencies...
pushd "%REPO_ROOT%"
uv sync
popd
echo ================================

echo Script directory : %SCRIPT_DIR%
echo Repository root  : %REPO_ROOT%
echo Working directory: %CD%

REM -- Set PYTHONPATH so both packages are importable --
set "PYTHONPATH=%REPO_ROOT%\file-validator-core\src;%REPO_ROOT%\file-validator-webserver\src;%PYTHONPATH%"
echo PYTHONPATH       : %PYTHONPATH%

echo ================================
echo Starting server in '%ENV%' environment...
echo ================================

if "%ENV%"=="dev" (
    echo Running in development mode...
    uv run fastapi dev "%MAIN_MODULE%" ^
        --app app ^
        --host 127.0.0.1 ^
        --port 9000
) else if "%ENV%"=="prod" (
    echo Running in production mode...
    uv run fastapi run "%MAIN_MODULE%" ^
        --app app ^
        --host 127.0.0.1 ^
        --port 9290
) else (
    echo Unknown environment: %ENV%
    echo Usage: start_server.bat [dev^|prod]
    exit /b 1
)

echo ================================
echo Server stopped.
echo ================================

endlocal
