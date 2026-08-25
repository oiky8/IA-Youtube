@echo off
title CHECK CUSTOM API KEY
color 0B
cd /d "%~dp0"

echo ====================================================
echo   KIEM TRA CUSTOM API / KEY / MODEL
echo ====================================================
echo.

set "TARGET_FILE=AI_MOD_ALL_IN_ONE.py"
set "PYTHON_CMD="
where python >nul 2>nul
if not errorlevel 1 set "PYTHON_CMD=python"
if "%PYTHON_CMD%"=="" (
    py -3 -c "print('python-ok')" >nul 2>nul
    if not errorlevel 1 set "PYTHON_CMD=py -3"
)

if "%PYTHON_CMD%"=="" (
    echo [LOI] Chua tim thay Python de chay.
    pause
    exit /b 1
)

%PYTHON_CMD% "%TARGET_FILE%" --custom-check
set "RESULT=%ERRORLEVEL%"

echo.
if "%RESULT%"=="0" (
    echo [OK] CUSTOM API / KEY / MODEL HOAT DONG DAY DU.
) else (
    echo [CHUA OK] Xem loi ben tren roi sua .env hoac bat server custom.
)
echo ====================================================
pause
exit /b %RESULT%
