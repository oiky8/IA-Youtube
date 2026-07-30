@echo off
title AI MOD BOT - DIAGNOSTIC TOOL
color 0A

cd /d "%~dp0"

echo ====================================================
echo   DANG KIEM TRA LOI HE THONG AI MOD BOT V25...
echo ====================================================
echo.

set "TARGET_FILE=AI_MOD_ALL_IN_ONE.py"
if not exist "%TARGET_FILE%" (
    echo [LOI] KHONG TIM THAY %TARGET_FILE% TRONG THU MUC NAY!
    echo Thu muc hien tai: %cd%
    goto end
)

set "PYTHON_CMD="
where python >nul 2>nul
if not errorlevel 1 set "PYTHON_CMD=python"
if "%PYTHON_CMD%"=="" (
    py -3 -c "print('python-ok')" >nul 2>nul
    if not errorlevel 1 set "PYTHON_CMD=py -3"
)

if "%PYTHON_CMD%"=="" (
    echo [LOI] Chua tim thay Python de chay bot.
    echo Cai Python 3.10+ roi chay: py -3 -m pip install -r requirements.txt
    goto end
)

echo [INFO] Tim thay file: %TARGET_FILE%
echo [INFO] Dang khoi chay chan doan bang: %PYTHON_CMD%
echo.

%PYTHON_CMD% "%TARGET_FILE%" --check

:end
echo.
echo ====================================================
echo [THONG BAO]
echo 1. Neu thay "HE THONG KHOE MANH" - Bot chay binh thuong.
echo 2. Neu thay "PHAT HIEN BENH LY" - Doc ky cac loi hien ra.
echo 3. Chi tiet loi da duoc ghi vao file: bot.log
echo ====================================================
pause
