@echo off
setlocal
cd /d "%~dp0"

echo ==========================================
echo  Choco Control - Instalacion inicial
 echo ==========================================

where py >nul 2>nul
if errorlevel 1 (
    echo No se encontro Python. Instale Python 3.12 o superior y marque Add Python to PATH.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Creando entorno virtual...
    py -m venv .venv
    if errorlevel 1 goto :error
)

call ".venv\Scripts\activate.bat"
echo Instalando dependencias Python del sistema OCR y Django...
python -m pip install --upgrade pip
if errorlevel 1 goto :error
pip install -r requirements.txt
if errorlevel 1 goto :error

echo Preparando base de datos y catalogo...
python manage.py migrate
if errorlevel 1 goto :error
python manage.py cargar_catalogo_inicial
if errorlevel 1 goto :error

echo.
echo Aplicacion lista. Se abrira en el navegador.
start "" http://127.0.0.1:8000/

echo Creando acceso directo en el escritorio...
if exist "CREAR_ACCESO_DIRECTO_CHOCO.bat" (
    call "CREAR_ACCESO_DIRECTO_CHOCO.bat"
) else (
    echo No se encontro CREAR_ACCESO_DIRECTO_CHOCO.bat. Se omitio el acceso directo.
)

python manage.py runserver
exit /b 0

:error
echo.
echo Ocurrio un error durante la instalacion o ejecucion.
echo Copie el texto mostrado en esta ventana para revisarlo.
pause
exit /b 1
