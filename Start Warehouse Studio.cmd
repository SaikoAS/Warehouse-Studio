@echo off
setlocal DisableDelayedExpansion
title Warehouse Studio
set "PYTHON_MANAGER_AUTOMATIC_INSTALL=false"
if not defined WAREHOUSE_STUDIO_PYTHON set "WAREHOUSE_STUDIO_PYTHON=python.exe"
"%WAREHOUSE_STUDIO_PYTHON%" -I -c "import sys; sys.exit(sys.version_info < (3, 13))" >nul 2>&1
if errorlevel 1 (
    echo Warehouse Studio needs an existing Python 3.13 or newer installation.
    echo Set WAREHOUSE_STUDIO_PYTHON to the full path of your approved python.exe and try again.
    goto failed
)
"%WAREHOUSE_STUDIO_PYTHON%" -I "%~dp0runtime\server.py"
if not errorlevel 1 exit /b 0
:failed
echo.
pause
exit /b 1
