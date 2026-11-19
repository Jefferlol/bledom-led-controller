@echo off
setlocal enabledelayedexpansion

:: Moverse a la raíz del proyecto (un directorio arriba de scripts/)
cd /d "%~dp0.."

echo ===================================================
echo Iniciando Microservicio BLEDOM LED Controller
echo Directorio: %CD%
echo ===================================================

:: Detectar entorno virtual .venv
if exist ".venv\Scripts\python.exe" (
    echo [INFO] Utilizando entorno virtual local .venv...
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
    echo [AVISO] Entorno virtual .venv no encontrado. Usando Python del sistema...
    set "PYTHON_EXE=python"
)

:: Verificar si existe archivo .env
if not exist ".env" (
    if exist ".env.example" (
        echo [INFO] Creando archivo .env a partir de .env.example...
        copy ".env.example" ".env" >nul
    )
)

:: Ejecutar servidor Uvicorn con recarga deshabilitada para producción
"%PYTHON_EXE%" -m uvicorn app.main:app --host 0.0.0.0 --port 8085

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] El servidor finalizo con codigo de error %ERRORLEVEL%.
    pause
)
