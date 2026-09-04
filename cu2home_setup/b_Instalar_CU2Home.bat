@echo off
setlocal

:: ============================================================
:: Lanzador de instalacion cu2home
:: Simplemente eleva privilegios (si hace falta) y ejecuta
:: Instalar_CU2Home.ps1, que esta en la MISMA carpeta.
:: ============================================================

set "SCRIPT_DIR=%~dp0"
set "PS1=%SCRIPT_DIR%Instalar_CU2Home.ps1"

if not exist "%PS1%" (
    echo ERROR: No se encuentra Instalar_CU2Home.ps1 junto a este .bat
    echo Ruta esperada: %PS1%
    pause
    exit /b 1
)

:: Comprobar si ya se ejecuta como administrador
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Solicitando privilegios de administrador...
    powershell -NoProfile -Command "Start-Process cmd -ArgumentList '/c \"\"%~f0\"\"' -Verb RunAs"
    exit /b
)

cd /d "%SCRIPT_DIR%"
powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1%"
pause
