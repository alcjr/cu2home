<#
================================================================================
 Instalar_CU2Home.ps1
 Instalación / despliegue local del proyecto cu2home (Django + PostgreSQL)
================================================================================
 Qué hace, en orden, con validación en cada paso:
   1. Comprueba PostgreSQL 18 (lo instala si falta) + extensión PostGIS
      (necesaria porque el proyecto usa django.contrib.gis / backend postgis)
   2. Crea la base de datos cu2home_db (si no existe)
   3. Restaura la copia de seguridad backup_cu2home_db_AAAAMMDD.dump
   4. Comprueba Python 3.11.9 (lo instala si falta) y actualiza el PATH del SO
   5. Comprueba Django 5.2.17 a nivel global (lo instala si falta)
   6. Descomprime cu2home.zip en C:\cu2home
   7. Crea el entorno virtual C:\cu2home\venv
   8. Activa el entorno virtual
   9. Instala dependencias (requirements.txt corregido, ver notas más abajo)
  10. Lanza cu2home_local.bat

 USO:
   Clic derecho -> "Ejecutar como administrador" sobre Instalar_CU2Home.bat
   (ese .bat simplemente eleva privilegios y llama a este .ps1)

   o bien, desde una consola PowerShell YA elevada:
   PS> Set-ExecutionPolicy -Scope Process Bypass -Force
   PS> .\Instalar_CU2Home.ps1

 Coloca en la MISMA carpeta que este script, antes de ejecutarlo:
   - cu2home.zip
   - backup_cu2home_db_AAAAMMDD.dump   (el más reciente se detecta solo)
   - requirements.txt                  (opcional, ya va dentro del zip)
================================================================================
#>

[CmdletBinding()]
param(
    [string]$ProjectRoot          = 'C:\cu2home',
    [string]$SourceZip            = (Join-Path $PSScriptRoot 'cu2home.zip'),
    [string]$BackupDumpPath       = '',                       # vacío = autodetectar en $PSScriptRoot

    [string]$PgMajorVersion       = '18',
    [string]$PgInstallerUrl       = 'https://get.enterprisedb.com/postgresql/postgresql-18.6-1-windows-x64.exe',
    [string]$PostgisInstallerUrl  = 'https://ftp.postgresql.org/pub/postgis/pg18/v3.6.2/win64/postgis-bundle-pg18x64-setup-3.6.2-1.exe',
    [string]$PgSuperUser          = 'postgres',
    [string]$PgSuperPassword      = 'ADMIN',
    [string]$PgPort               = '5432',
    [string]$DbName               = 'cu2home_db',

    [string]$PyVersion            = '3.11.9',
    [string]$PyInstallerUrl       = 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe',

    [string]$DjangoVersion        = '5.2.17'
)

$ErrorActionPreference = 'Stop'
$ProgressPreference    = 'SilentlyContinue'   # acelera Invoke-WebRequest
$WorkDir   = Join-Path $env:TEMP 'cu2home_setup'
$LogFile   = Join-Path $WorkDir  ("install_log_{0}.txt" -f (Get-Date -Format 'yyyyMMdd_HHmmss'))
New-Item -ItemType Directory -Path $WorkDir -Force | Out-Null

# ------------------------------------------------------------------------------
# Utilidades
# ------------------------------------------------------------------------------
function Write-Log {
    param([string]$Message, [string]$Level = 'INFO')
    $line = "[{0}] [{1}] {2}" -f (Get-Date -Format 'HH:mm:ss'), $Level, $Message
    Add-Content -Path $LogFile -Value $line
    switch ($Level) {
        'STEP' { Write-Host "`n=== $Message ===" -ForegroundColor Cyan }
        'OK'   { Write-Host "    OK: $Message" -ForegroundColor Green }
        'WARN' { Write-Host "    AVISO: $Message" -ForegroundColor Yellow }
        'ERR'  { Write-Host "    ERROR: $Message" -ForegroundColor Red }
        default{ Write-Host "    $Message" }
    }
}

function Stop-Install {
    param([string]$Message)
    Write-Log -Message $Message -Level 'ERR'
    Write-Log -Message "Instalación interrumpida. Revisa el log: $LogFile" -Level 'ERR'
    Read-Host "Pulsa Enter para cerrar"
    exit 1
}

function Test-IsAdmin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $p  = New-Object Security.Principal.WindowsPrincipal($id)
    return $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Update-SessionPath {
    # Refresca PATH de la sesión actual de PowerShell con lo que haya en Machine + User
    $machine = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $user    = [Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = "$machine;$user"
}

function Add-MachinePath {
    param([string]$Dir)
    if (-not (Test-Path $Dir)) { return }
    $current = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    if ($current -notlike "*$Dir*") {
        [Environment]::SetEnvironmentVariable('Path', "$current;$Dir", 'Machine')
        Write-Log "Añadido al PATH del sistema: $Dir" 'OK'
    }
    Update-SessionPath
}

function Invoke-Download {
    param([string]$Url, [string]$OutFile)
    if (Test-Path $OutFile) {
        Write-Log "Ya descargado: $OutFile"
        return
    }
    Write-Log "Descargando $Url ..."
    try {
        Invoke-WebRequest -Uri $Url -OutFile $OutFile -UseBasicParsing
    } catch {
        Stop-Install "No se pudo descargar '$Url'. Comprueba la conexión a internet o actualiza la URL del instalador en los parámetros del script. Detalle: $($_.Exception.Message)"
    }
    if (-not (Test-Path $OutFile)) { Stop-Install "La descarga de '$Url' no generó el archivo esperado." }
}

# ------------------------------------------------------------------------------
# Comprobación inicial: privilegios de administrador
# ------------------------------------------------------------------------------
if (-not (Test-IsAdmin)) {
    Stop-Install "Este script debe ejecutarse como Administrador (necesario para instalar software y modificar variables de entorno del sistema)."
}

Write-Host "================================================================" -ForegroundColor Magenta
Write-Host "   INSTALACIÓN CU2HOME - $(Get-Date)" -ForegroundColor Magenta
Write-Host "   Log detallado: $LogFile" -ForegroundColor Magenta
Write-Host "================================================================" -ForegroundColor Magenta

# ==============================================================================
# PASO 1: PostgreSQL 18 (+ PostGIS, requerido por django.contrib.gis)
# ==============================================================================
Write-Log "PASO 1/10: Comprobando PostgreSQL $PgMajorVersion" 'STEP'

$PgBinDir = "C:\Program Files\PostgreSQL\$PgMajorVersion\bin"
$psqlExe  = Join-Path $PgBinDir 'psql.exe'

if (Test-Path $psqlExe) {
    Write-Log "PostgreSQL $PgMajorVersion ya está instalado en $PgBinDir" 'OK'
} else {
    Write-Log "PostgreSQL $PgMajorVersion no encontrado. Se instalará." 'WARN'
    $pgInstaller = Join-Path $WorkDir 'postgresql-installer.exe'
    Invoke-Download -Url $PgInstallerUrl -OutFile $pgInstaller

    # Instalación desatendida (silenciosa). Referencia: EDB installer switches.
    $pgArgs = @(
        '--mode', 'unattended',
        '--unattendedmodeui', 'none',
        '--superpassword', $PgSuperPassword,
        '--servicename', "postgresql-x64-$PgMajorVersion",
        '--serverport', $PgPort,
        '--disable-components', 'stackbuilder'
    )
    Write-Log "Ejecutando instalador de PostgreSQL en modo silencioso..."
    $proc = Start-Process -FilePath $pgInstaller -ArgumentList $pgArgs -Wait -PassThru
    if ($proc.ExitCode -ne 0) { Stop-Install "El instalador de PostgreSQL devolvió el código de error $($proc.ExitCode)." }

    if (-not (Test-Path $psqlExe)) { Stop-Install "PostgreSQL no quedó instalado en la ruta esperada ($PgBinDir)." }
    Write-Log "PostgreSQL $PgMajorVersion instalado correctamente." 'OK'
}

Add-MachinePath -Dir $PgBinDir

# --- PostGIS (el proyecto usa 'django.contrib.gis.db.backends.postgis') ------
$postgisMarker = "C:\Program Files\PostgreSQL\$PgMajorVersion\share\extension\postgis.control"
if (Test-Path $postgisMarker) {
    Write-Log "PostGIS ya está instalado." 'OK'
} else {
    Write-Log "PostGIS no encontrado. Se instalará (necesario por django.contrib.gis)." 'WARN'
    $postgisInstaller = Join-Path $WorkDir 'postgis-installer.exe'
    Invoke-Download -Url $PostgisInstallerUrl -OutFile $postgisInstaller
    # Instalador NSIS: /S = silencioso, /D=directorio destino (debe ser el último argumento, sin comillas)
    $proc = Start-Process -FilePath $postgisInstaller -ArgumentList "/S /D=C:\Program Files\PostgreSQL\$PgMajorVersion" -Wait -PassThru
    if ($proc.ExitCode -ne 0) {
        Write-Log "El instalador de PostGIS devolvió código $($proc.ExitCode). Puede requerir instalación manual (StackBuilder) si el proyecto usa capas geoespaciales." 'WARN'
    } else {
        Write-Log "PostGIS instalado." 'OK'
    }
}

# Asegurar que el servicio está en marcha
try {
    $svc = Get-Service -Name "postgresql-x64-$PgMajorVersion" -ErrorAction Stop
    if ($svc.Status -ne 'Running') {
        Start-Service $svc
        Write-Log "Servicio postgresql-x64-$PgMajorVersion iniciado." 'OK'
    } else {
        Write-Log "Servicio de PostgreSQL ya en ejecución." 'OK'
    }
} catch {
    Write-Log "No se encontró el servicio 'postgresql-x64-$PgMajorVersion'. Comprueba el nombre del servicio con 'Get-Service *postgre*'." 'WARN'
}

$env:PGPASSWORD = $PgSuperPassword

# ==============================================================================
# PASO 2: Crear base de datos cu2home_db
# ==============================================================================
Write-Log "PASO 2/10: Creando base de datos '$DbName' (si no existe)" 'STEP'

$psql = Join-Path $PgBinDir 'psql.exe'
$exists = & $psql -h localhost -p $PgPort -U $PgSuperUser -tAc "SELECT 1 FROM pg_database WHERE datname='$DbName'" 2>> $LogFile
if ($LASTEXITCODE -ne 0) { Stop-Install "No se pudo conectar a PostgreSQL para comprobar la base de datos. Revisa usuario/clave (usuario=$PgSuperUser)." }

if ($exists -match '1') {
    Write-Log "La base de datos '$DbName' ya existe. No se vuelve a crear." 'OK'
} else {
    & $psql -h localhost -p $PgPort -U $PgSuperUser -c "CREATE DATABASE $DbName;" 2>> $LogFile
    if ($LASTEXITCODE -ne 0) { Stop-Install "Fallo al crear la base de datos '$DbName'." }
    Write-Log "Base de datos '$DbName' creada." 'OK'
}

& $psql -h localhost -p $PgPort -U $PgSuperUser -d $DbName -c "CREATE EXTENSION IF NOT EXISTS postgis;" 2>> $LogFile
if ($LASTEXITCODE -ne 0) {
    Write-Log "No se pudo crear la extensión PostGIS en '$DbName'. El proyecto usa modelos geoespaciales y la fallará al migrar/consultar." 'WARN'
} else {
    Write-Log "Extensión PostGIS habilitada en '$DbName'." 'OK'
}

# ==============================================================================
# PASO 3: Restaurar copia de seguridad
# ==============================================================================
Write-Log "PASO 3/10: Restaurando copia de seguridad" 'STEP'

if ([string]::IsNullOrWhiteSpace($BackupDumpPath)) {
    $found = Get-ChildItem -Path $PSScriptRoot -Filter 'backup_cu2home_db_*.dump' -ErrorAction SilentlyContinue |
             Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $found) { Stop-Install "No se encontró ningún archivo 'backup_cu2home_db_AAAAMMDD.dump' junto al script. Colócalo en: $PSScriptRoot" }
    $BackupDumpPath = $found.FullName
}
if (-not (Test-Path $BackupDumpPath)) { Stop-Install "El archivo de backup indicado no existe: $BackupDumpPath" }
Write-Log "Usando backup: $BackupDumpPath"

$pgRestore = Join-Path $PgBinDir 'pg_restore.exe'
& $pgRestore -h localhost -p $PgPort -U $PgSuperUser -d $DbName --clean --if-exists --no-owner --no-privileges $BackupDumpPath 2>> $LogFile
# pg_restore puede devolver código != 0 solo por avisos (p.ej. objetos que no existían para el --clean).
# Se valida comprobando que al menos existan tablas tras la restauración.
$tableCount = & $psql -h localhost -p $PgPort -U $PgSuperUser -d $DbName -tAc "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'"
if ([int]$tableCount -gt 0) {
    Write-Log "Backup restaurado correctamente ($tableCount tablas en 'public')." 'OK'
} else {
    Stop-Install "La restauración del backup no dejó tablas en la base de datos. Revisa el log: $LogFile"
}

# ==============================================================================
# PASO 4: Python 3.11.9
# ==============================================================================
Write-Log "PASO 4/10: Comprobando Python $PyVersion" 'STEP'

function Get-Py311Path {
    $candidates = @(
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
        "C:\Python311\python.exe"
    )
    foreach ($c in $candidates) { if (Test-Path $c) { return $c } }
    $cmd = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    return $null
}

$pyPath = Get-Py311Path
$pyOk = $false
if ($pyPath) {
    $verOut = & $pyPath --version 2>&1
    if ($verOut -match [regex]::Escape($PyVersion)) { $pyOk = $true }
    Write-Log "Python detectado: $verOut ($pyPath)"
}

if ($pyOk) {
    Write-Log "Python $PyVersion ya está instalado." 'OK'
} else {
    Write-Log "Python $PyVersion no encontrado (o versión distinta). Se instalará." 'WARN'
    $pyInstaller = Join-Path $WorkDir 'python-installer.exe'
    Invoke-Download -Url $PyInstallerUrl -OutFile $pyInstaller
    $pyArgs = @('/quiet', 'InstallAllUsers=1', 'PrependPath=1', 'Include_pip=1', 'Include_test=0')
    $proc = Start-Process -FilePath $pyInstaller -ArgumentList $pyArgs -Wait -PassThru
    if ($proc.ExitCode -ne 0) { Stop-Install "El instalador de Python devolvió el código $($proc.ExitCode)." }

    Update-SessionPath
    $pyPath = Get-Py311Path
    if (-not $pyPath) { Stop-Install "Python se instaló pero no se encuentra python.exe. Revisa manualmente el PATH del sistema." }
    Add-MachinePath -Dir (Split-Path $pyPath)
    Add-MachinePath -Dir (Join-Path (Split-Path $pyPath) 'Scripts')
    Write-Log "Python $PyVersion instalado y PATH del sistema actualizado." 'OK'
}

# ==============================================================================
# PASO 5: Django 5.2.17 (comprobación/instalación global)
# ==============================================================================
Write-Log "PASO 5/10: Comprobando Django $DjangoVersion (entorno global)" 'STEP'
Write-Log "Nota: Django se reinstalará también dentro del entorno virtual en el PASO 9 vía requirements.txt; esa es la copia que realmente usará la aplicación."

$djangoOut = & $pyPath -m django --version 2>&1
if ($LASTEXITCODE -eq 0 -and $djangoOut -match [regex]::Escape($DjangoVersion)) {
    Write-Log "Django $DjangoVersion ya está instalado globalmente." 'OK'
} else {
    Write-Log "Instalando Django==$DjangoVersion a nivel global..." 'WARN'
    & $pyPath -m pip install --quiet --upgrade pip
    & $pyPath -m pip install --quiet "Django==$DjangoVersion"
    if ($LASTEXITCODE -ne 0) { Stop-Install "No se pudo instalar Django $DjangoVersion globalmente." }
    Write-Log "Django $DjangoVersion instalado globalmente." 'OK'
}

# ==============================================================================
# PASO 6: Descomprimir cu2home.zip en C:\cu2home
# ==============================================================================
Write-Log "PASO 6/10: Descomprimiendo proyecto en $ProjectRoot" 'STEP'

if (-not (Test-Path $SourceZip)) { Stop-Install "No se encuentra cu2home.zip en: $SourceZip" }

if (Test-Path $ProjectRoot) {
    Write-Log "$ProjectRoot ya existe. Se conservará y se sobrescribirán los archivos del zip." 'WARN'
} else {
    New-Item -ItemType Directory -Path $ProjectRoot -Force | Out-Null
}

Expand-Archive -Path $SourceZip -DestinationPath $ProjectRoot -Force
if (-not (Test-Path (Join-Path $ProjectRoot 'manage.py'))) { Stop-Install "Tras descomprimir no se encuentra manage.py en $ProjectRoot. ¿El zip tiene una carpeta raíz extra?" }
Write-Log "Proyecto descomprimido en $ProjectRoot" 'OK'

# --- Corrección: cu2home_local.bat apunta a una ruta antigua (c:\01_project\cu2home) ---
$localBat = Join-Path $ProjectRoot 'cu2home_local.bat'
if (Test-Path $localBat) {
    $content = Get-Content $localBat -Raw
    $fixed = $content -replace 'cd /d "c:\\01_project\\cu2home"', "cd /d `"$ProjectRoot`""
    if ($fixed -ne $content) {
        Set-Content -Path $localBat -Value $fixed -NoNewline
        Write-Log "Corregida la ruta del proyecto dentro de cu2home_local.bat -> $ProjectRoot" 'OK'
    }
}

# --- Corrección: requirements.txt fija Django <5.1, en conflicto con Django 5.2.17 pedido ---
$reqPath = Join-Path $ProjectRoot 'requirements.txt'
if (Test-Path $reqPath) {
    $req = Get-Content $reqPath
    $newReq = New-Object System.Collections.Generic.List[string]
    $seenRedis = $false
    foreach ($line in $req) {
        if ($line -match '^\s*Django\s*[><=]') {
            $newReq.Add("Django==$DjangoVersion")
            continue
        }
        if ($line -match '^\s*redis\s*[><=]') {
            if ($seenRedis) { continue }   # eliminar línea 'redis' duplicada
            $seenRedis = $true
        }
        $newReq.Add($line)
    }
    Set-Content -Path $reqPath -Value $newReq
    Write-Log "requirements.txt corregido: Django fijado a $DjangoVersion (antes restringía <5.1) y eliminada la línea 'redis' duplicada." 'OK'
}

# ==============================================================================
# PASO 7: Crear entorno virtual
# ==============================================================================
Write-Log "PASO 7/10: Creando entorno virtual en $ProjectRoot\venv" 'STEP'

$venvDir = Join-Path $ProjectRoot 'venv'
if (Test-Path (Join-Path $venvDir 'Scripts\python.exe')) {
    Write-Log "El entorno virtual ya existe." 'OK'
} else {
    & $pyPath -m venv $venvDir
    if ($LASTEXITCODE -ne 0) { Stop-Install "No se pudo crear el entorno virtual." }
    Write-Log "Entorno virtual creado." 'OK'
}

# ==============================================================================
# PASO 8: Activar entorno virtual (en esta misma sesión de PowerShell)
# ==============================================================================
Write-Log "PASO 8/10: Activando entorno virtual" 'STEP'
$venvPython = Join-Path $venvDir 'Scripts\python.exe'
$venvPip    = Join-Path $venvDir 'Scripts\pip.exe'
if (-not (Test-Path $venvPython)) { Stop-Install "No se encuentra python.exe dentro del entorno virtual." }
. (Join-Path $venvDir 'Scripts\Activate.ps1')
Write-Log "Entorno virtual activado ($venvPython)." 'OK'

# ==============================================================================
# PASO 9: Instalar dependencias
# ==============================================================================
Write-Log "PASO 9/10: Instalando dependencias (pip install -r requirements.txt)" 'STEP'

& $venvPython -m pip install --quiet --upgrade pip
& $venvPip install -r $reqPath
if ($LASTEXITCODE -ne 0) { Stop-Install "Fallo instalando dependencias desde requirements.txt. Revisa el log: $LogFile" }
Write-Log "Dependencias instaladas en el entorno virtual." 'OK'

$djangoVenvVer = & $venvPython -m django --version
Write-Log "Django dentro del venv: $djangoVenvVer"

# ==============================================================================
# PASO 10: Ejecutar cu2home_local.bat
# ==============================================================================
Write-Log "PASO 10/10: Lanzando cu2home_local.bat" 'STEP'

if (-not (Test-Path $localBat)) { Stop-Install "No se encuentra cu2home_local.bat en $ProjectRoot" }

Write-Log "Se abrirá una nueva ventana con el servidor de desarrollo Django (http://127.0.0.1:8000)." 'OK'
Start-Process -FilePath $localBat -WorkingDirectory $ProjectRoot

Write-Host "`n================================================================" -ForegroundColor Magenta
Write-Host "   INSTALACIÓN COMPLETADA" -ForegroundColor Magenta
Write-Host "   Proyecto en : $ProjectRoot"
Write-Host "   Log         : $LogFile"
Write-Host "   Servidor    : http://127.0.0.1:8000  (ventana aparte)"
Write-Host "================================================================" -ForegroundColor Magenta
Write-Host "`nRevisa las notas de corrección en README_INSTALACION.md (GDAL/PROJ, SECRET_KEY, etc.)" -ForegroundColor Yellow
Read-Host "Pulsa Enter para cerrar esta ventana"
