@echo off
cd /d "%~dp0"
py install.py
if errorlevel 1 (
  echo.
  echo Installation failed. Read the message above.
)
echo.
pause