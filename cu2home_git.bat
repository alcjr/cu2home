@echo off
setlocal EnableDelayedExpansion

:: ============================================================
::  GIT BATCH - Commit automatico con timestamp
::  Formato commit: hh:mm:ss / dd-mm-aaaa
:: ============================================================

echo.
echo ============================================
echo    GIT BATCH - Auto Commit y Push
echo ============================================
echo.

:: -----------------------------------------------------------
:: 1. Verificar que git esta instalado
:: -----------------------------------------------------------
git --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Git no esta instalado o no esta en el PATH.
    echo          Por favor, instala Git desde https://git-scm.com/
    pause
    exit /b 1
)
echo [OK] Git detectado correctamente.
echo.

:: -----------------------------------------------------------
:: 2. Verificar que estamos dentro de un repositorio Git
:: -----------------------------------------------------------
git rev-parse --git-dir >nul 2>&1
if errorlevel 1 (
    echo [ERROR] No estas dentro de un repositorio Git.
    echo          Ejecuta este script desde la raiz de tu repo.
    pause
    exit /b 1
)
echo [OK] Repositorio Git detectado.
echo.

:: -----------------------------------------------------------
:: 3. Obtener rama actual
:: -----------------------------------------------------------
for /f "tokens=*" %%a in ('git rev-parse --abbrev-ref HEAD') do set "RAMA=%%a"
echo [INFO] Rama actual: %RAMA%
echo.

:: -----------------------------------------------------------
:: 4. Obtener fecha y hora actual
:: -----------------------------------------------------------
:: Formato: hh:mm:ss / dd-mm-aaaa
for /f "tokens=1-3 delims=/ " %%a in ("%date%") do (
    set "DIA=%%a"
    set "MES=%%b"
    set "ANIO=%%c"
)

for /f "tokens=1-3 delims=:,. " %%a in ("%time: =0%") do (
    set "HORA=%%a"
    set "MIN=%%b"
    set "SEG=%%c"
)

:: Ajustar formato de hora si tiene espacio inicial
if "%HORA:~0,1%"==" " set "HORA=0%HORA:~1,1%"

set "TIMESTAMP=%HORA%:%MIN%:%SEG% / %DIA%-%MES%-%ANIO%"
echo [INFO] Timestamp del commit: %TIMESTAMP%
echo.

:: -----------------------------------------------------------
:: 5. Verificar si hay cambios para commitear
:: -----------------------------------------------------------
git diff --cached --quiet
set "STAGED_CHANGES=%errorlevel%"

git diff --quiet
set "UNSTAGED_CHANGES=%errorlevel%"

if %STAGED_CHANGES% equ 0 if %UNSTAGED_CHANGES% equ 0 (
    echo [AVISO] No hay cambios para commitear.
    echo          El repositorio esta limpio.
    echo.
    goto PUSH_ONLY
)

:: -----------------------------------------------------------
:: 6. git add .
:: -----------------------------------------------------------
echo [PASO 1/3] Ejecutando: git add .
git add .
if errorlevel 1 (
    echo.
    echo [ERROR] Fallo al ejecutar 'git add .'
    echo          Revisa los permisos de los archivos.
    pause
    exit /b 1
)
echo [OK] Archivos anadidos al staging area.
echo.

:: -----------------------------------------------------------
:: 7. git commit
:: -----------------------------------------------------------
echo [PASO 2/3] Ejecutando: git commit -m "%TIMESTAMP%"
git commit -m "%TIMESTAMP%"
if errorlevel 1 (
    echo.
    echo [ERROR] Fallo al ejecutar 'git commit'.
    echo          Posibles causas:
    echo          - No hay cambios para commitear
    echo          - Problema con el mensaje de commit
    echo          - Configuracion de usuario Git incompleta
    pause
    exit /b 1
)
echo [OK] Commit realizado con exito.
echo.

:: -----------------------------------------------------------
:: 8. git push
:: -----------------------------------------------------------
:PUSH_ONLY
echo [PASO 3/3] Ejecutando: git push origin %RAMA%
git push origin %RAMA%
if errorlevel 1 (
    echo.
    echo [ERROR] Fallo al ejecutar 'git push'.
    echo          Posibles causas:
    echo          - No tienes permisos en el repositorio remoto
    echo          - La rama remota no existe
    echo          - Hay conflictos que debes resolver primero
    echo          - No tienes conexion a internet
    echo.
    echo [SUGERENCIA] Intenta ejecutar manualmente:
    echo              git push origin %RAMA%
    pause
    exit /b 1
)
echo [OK] Push realizado con exito a la rama '%RAMA%'.
echo.

:: -----------------------------------------------------------
:: 9. Resumen final
:: -----------------------------------------------------------
echo ============================================
echo              RESUMEN DE OPERACIONES
echo ============================================
echo  Rama:      %RAMA%
echo  Commit:    %TIMESTAMP%
echo  Estado:    COMPLETADO CON EXITO
echo ============================================
echo.

endlocal
pause
exit /b 0
