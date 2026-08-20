@echo off
REM ================================================================
REM Start the File Validator web server (Windows CMD / batch).
REM
REM Usage:
REM   start_server.bat --help
REM   start_server.bat -e dev
REM   start_server.bat --env=prod --host=0.0.0.0 --port=8080
REM ================================================================
setlocal enabledelayedexpansion

REM -- Default values --
set "ENV=prod"
set "PORT="
set "HOST="
set "SCRIPT_NAME=%~nx0"

REM -- Parse command line arguments --
:parse_args
if "%~1"=="" goto validate_args

if "%~1"=="--help" (
    call :show_help
    exit /b 0
)

REM Handle --env or -e
if "%~1"=="-e" (
    set "ENV=%~2"
    shift
    shift
    goto parse_args
)
if "%~1"=="--env" (
    set "ENV=%~2"
    shift
    shift
    goto parse_args
)
if "%~1:~0,6%"=="--env=" (
    set "ENV=%~1"
    set "ENV=!ENV:~6!"
    shift
    goto parse_args
)
if "%~1:~0,3%"=="-e=" (
    set "ENV=%~1"
    set "ENV=!ENV:~3!"
    shift
    goto parse_args
)

REM Handle --port or -p
if "%~1"=="-p" (
    set "PORT=%~2"
    shift
    shift
    goto parse_args
)
if "%~1"=="--port" (
    set "PORT=%~2"
    shift
    shift
    goto parse_args
)
if "%~1:~0,7%"=="--port=" (
    set "PORT=%~1"
    set "PORT=!PORT:~7!"
    shift
    goto parse_args
)
if "%~1:~0,3%"=="-p=" (
    set "PORT=%~1"
    set "PORT=!PORT:~3!"
    shift
    goto parse_args
)

REM Handle --host or -h
if "%~1"=="-h" (
    set "HOST=%~2"
    shift
    shift
    goto parse_args
)
if "%~1"=="--host" (
    set "HOST=%~2"
    shift
    shift
    goto parse_args
)
if "%~1:~0,7%"=="--host=" (
    set "HOST=%~1"
    set "HOST=!HOST:~7!"
    shift
    goto parse_args
)
if "%~1:~0,3%"=="-h=" (
    set "HOST=%~1"
    set "HOST=!HOST:~3!"
    shift
    goto parse_args
)

echo Error: Unknown option '%~1'
echo Run '%SCRIPT_NAME% --help' for usage information
exit /b 1

:validate_args
REM -- Normalize to lowercase --
if /I "%ENV%"=="DEV"  set "ENV=dev"
if /I "%ENV%"=="PROD" set "ENV=prod"

REM Validate environment
if not "%ENV%"=="dev" if not "%ENV%"=="prod" (
    echo Error: Invalid environment '%ENV%'. Must be 'dev' or 'prod'.
    exit /b 1
)

REM Validate port if provided
if not "%PORT%"=="" (
    echo %PORT%| findstr /R "^[0-9][0-9]*$" >nul
    if errorlevel 1 (
        echo Error: Port must be a numeric value, got '%PORT%'
        exit /b 1
    )
)

REM Validate host for production environment
if "%ENV%"=="prod" if "%HOST%"=="" (
    echo Error: Host must be specified for production environment
    echo Use -h or --host to specify the host address
    exit /b 1
)

REM -- Set default port based on environment if not specified --
if "%PORT%"=="" (
    if "%ENV%"=="dev" (
        set "PORT=9000"
    ) else (
        set "PORT=9290"
    )
)

REM -- Set default host for dev environment if not specified --
if "%HOST%"=="" if "%ENV%"=="dev" (
    set "HOST=127.0.0.1"
)

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
echo Starting server in '%ENV%' environment...

echo Script directory : %SCRIPT_DIR%
echo Repository root  : %REPO_ROOT%
echo Working directory: %CD%

REM -- Set PYTHONPATH so both packages are importable --
set "PYTHONPATH=%REPO_ROOT%\file-validator-core\src;%REPO_ROOT%\file-validator-webserver\src;%PYTHONPATH%"
echo PYTHONPATH       : %PYTHONPATH%
echo Host             : %HOST%
echo Port             : %PORT%

if "%ENV%"=="dev" (
    echo Running in development mode...
    uv run fastapi dev "%MAIN_MODULE%" ^
        --app app ^
        --host %HOST% ^
        --port %PORT%
) else if "%ENV%"=="prod" (
    echo Running in production mode...
    uv run fastapi run "%MAIN_MODULE%" ^
        --app app ^
        --host %HOST% ^
        --port %PORT%
)

echo ================================
echo Server stopped.
echo ================================

endlocal
exit /b 0

:show_help
echo Usage: %SCRIPT_NAME% [OPTIONS]
echo.
echo Options:
echo   -e, --env ENV     Environment to run (dev^|prod, default: prod)
echo   -p, --port PORT   Port to run on (default: 9000 for dev, 9290 for prod)
echo   -h, --host HOST   Host address to bind (default: 127.0.0.1 for dev, required for prod)
echo       --help        Show this help message
echo.
echo Examples:
echo   %SCRIPT_NAME% -e dev
echo   %SCRIPT_NAME% --env=prod --host=0.0.0.0 --port=8080
echo   %SCRIPT_NAME% -e dev -p 9000 -h localhost
exit /b 0