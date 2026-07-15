@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Primero ejecute INSTALAR_Y_ABRIR_WINDOWS.bat
    pause
    exit /b 1
)
call ".venv\Scripts\activate.bat"
start "" http://127.0.0.1:8000/
python manage.py runserver
pause
