@echo off
chcp 65001 >nul
title cu2home - Servidor Local Django

echo ===============================================
echo    Iniciando cu2home - Servidor Local Django
echo ===============================================
echo.

:: Ir al directorio del proyecto
cd /d "c:\cu2home"

echo [1/3] Activando entorno virtual...
if not exist "venv\Scripts\activate.bat" (
    echo ERROR: No se encuentra el entorno virtual en:
    echo        c:\cu2home\venv
    pause
    exit /b 1
)

call venv\Scripts\activate.bat

echo [2/3] Entorno virtual activado correctamente.
echo [3/3] Iniciando servidor Django...

echo.
echo Servidor disponible en: http://127.0.0.1:8000
echo Presiona Ctrl + C (o Ctrl + Break) para detener.
echo.

python manage.py runserver