@echo off
setlocal
set "CARPETA=%~dp0media\imagenes_productos"
if not exist "%CARPETA%" mkdir "%CARPETA%"
start "" explorer "%CARPETA%"
endlocal
