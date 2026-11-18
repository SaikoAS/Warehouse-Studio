@echo off
setlocal DisableDelayedExpansion
set "PYTHON_MANAGER_AUTOMATIC_INSTALL=false"
if not defined WAREHOUSE_STUDIO_PYTHON set "WAREHOUSE_STUDIO_PYTHON=python.exe"
"%WAREHOUSE_STUDIO_PYTHON%" -I "%~dp0runtime\shortcuts.py" remove
set "RESULT=%errorlevel%"
pause
exit /b %RESULT%
