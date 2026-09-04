# Instalación cu2home — guía rápida

## Preparar la carpeta de instalación

Descomprimir todos los archivos .zip

Copia estos 4 archivos **juntos, en la misma carpeta**, en el equipo Windows destino:

```
Instalar_CU2Home.bat
Instalar_CU2Home.ps1
cu2home.zip
backup_cu2home_db_20260831.dump
```

(`requirements.txt` no hace falta aparte: ya va dentro de `cu2home.zip`.)

## Ejecutar

Doble clic en **`Instalar_CU2Home.bat`** → aceptar el aviso de UAC (pide permisos de administrador,
imprescindibles para instalar PostgreSQL/Python y modificar el PATH del sistema).

El script hace, en orden y con comprobaciones en cada paso (no reinstala lo que ya esté presente):

1. PostgreSQL 18 (+ **PostGIS**, ver nota 1) — se instala si falta
2. Crea la base `cu2home_db` si no existe, y habilita la extensión PostGIS
3. Restaura `backup_cu2home_db_*.dump` (detecta automáticamente el más reciente en la carpeta)
4. Python 3.11.9 — se instala si falta, y se añade al PATH del sistema
5. Django 5.2.17 a nivel global — se instala si falta
6. Descomprime `cu2home.zip` en `C:\cu2home`
7. Crea el entorno virtual `C:\cu2home\venv`
8. Activa el entorno virtual
9. `pip install -r requirements.txt`
10. Ejecuta `cu2home_local.bat` (abre el servidor de desarrollo en `http://127.0.0.1:8000`)

Todo queda registrado en un log dentro de `%TEMP%\cu2home_setup\install_log_*.txt`.

Si necesitas otra ubicación, contraseña o puerto, se puede lanzar con parámetros, por ejemplo:

```powershell
.\Instalar_CU2Home.ps1 -ProjectRoot "D:\cu2home" -PgSuperPassword "OtraClave"
```

---

## Correcciones aplicadas / a tener en cuenta

Revisando el contenido real del zip y del `.env` incluido, encontré varias cosas que convenía
corregir o avisar (tal y como pedías):

1. **El proyecto usa PostGIS, no solo PostgreSQL.**
   `cu2home/settings.py` define `'ENGINE': 'django.contrib.gis.db.backends.postgis'` y
   `django.contrib.gis` está en `INSTALLED_APPS`. Instalar solo el motor PostgreSQL 18 no habría
   sido suficiente: la migración/consulta habría fallado al no existir la extensión PostGIS. El
   script instala también el bundle de PostGIS y ejecuta `CREATE EXTENSION postgis;` en la base.

2. **`requirements.txt` pedía una versión de Django incompatible con lo solicitado.**
   El archivo traía `Django>=5.0,<5.1`, lo que instalaría Django 5.0.x — no 5.2.17 como pide el
   punto 5. El script corrige esa línea a `Django==5.2.17` antes de hacer `pip install`.

3. **`requirements.txt` traía la dependencia `redis` duplicada** (dos restricciones distintas
   de versión). No era un conflicto grave, pero se limpió dejando una sola línea.

4. **`cu2home_local.bat` apuntaba a una ruta antigua.** Tenía `cd /d "c:\01_project\cu2home"`,
   pero el despliegue pedido es en `C:\cu2home`. El script la corrige automáticamente tras
   descomprimir.

5. **Variables GDAL/PROJ del `.env` apuntan a una ruta de Miniconda que no existirá en el
   equipo destino** (`C:\Users\USER\miniconda3\...`). GeoDjango necesita esas librerías para
   funcionar. El bundle de PostGIS que instala el script ya trae GDAL/PROJ dentro de
   `C:\Program Files\PostgreSQL\18\bin`, así que **tendrás que actualizar manualmente estas
   4 líneas del `.env`** (no lo hice automáticamente porque el `.env` contiene contraseñas y
   claves reales, y preferí no tocarlo sin tu confirmación):
   ```
   GDAL_BIN_DIR_WIN=C:\Program Files\PostgreSQL\18\bin
   GDAL_LIBRARY_PATH_WIN=C:\Program Files\PostgreSQL\18\bin\gdal311.dll
   GDAL_DATA_WIN=C:\Program Files\PostgreSQL\18\gdal-data
   PROJ_LIB_WIN=C:\Program Files\PostgreSQL\18\share\contrib\postgis-3.6\proj
   ```
   El nombre exacto de la dll `gdalXXX.dll` y de las carpetas de datos puede variar según la
   versión del bundle; revisa el contenido de `C:\Program Files\PostgreSQL\18\bin` tras la
   instalación y ajusta la ruta si hace falta.

6. **El `.env` incluido no es apto para producción**: `SECRET_KEY` es el valor por defecto de
   Django, `DEBUG=True`, y la contraseña de PostgreSQL (`ADMIN`) y del SMTP están en texto
   plano. Válido para uso local, pero conviene cambiarlo antes de exponer el servidor.

7. **Las URLs de descarga de PostgreSQL 18 y PostGIS están fijadas a versiones concretas**
   (18.6-1 y 3.6.2-1, las más recientes disponibles al escribir este script). Si para cuando lo
   ejecutes hay una versión más nueva, ajusta los parámetros `-PgInstallerUrl` y
   `-PostgisInstallerUrl`, o simplemente instala PostgreSQL a mano y vuelve a lanzar el script
   (detectará que ya está instalado y saltará ese paso).

8. **Paso 5 (Django global) es algo atípico.** Django normalmente solo se instala dentro del
   entorno virtual (paso 9), no a nivel de sistema. Se implementó tal y como se pidió, pero la
   copia que realmente usa la aplicación es la del `venv`, que también queda fijada a 5.2.17
   gracias a la corrección del punto 2.
