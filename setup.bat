@echo off
title MikroControl - Setup
cd /d "%~dp0"

echo ============================================
echo    MikroControl - Configuración Inicial
echo ============================================
echo.

REM Crear .env si no existe
if not exist ".env" (
    echo [1/5] Creando .env desde .env.example...
    copy .env.example .env >nul
    echo       Editá SECRET_KEY y DB_PASSWORD en .env antes de producción.
) else (
    echo [1/5] .env ya existe, ok.
)

REM Entorno virtual backend
if not exist "backend\venv" (
    echo [2/5] Creando entorno virtual Python...
    cd backend
    python -m venv venv
    cd ..
    echo       Entorno virtual creado en backend\venv
) else (
    echo [2/5] Entorno virtual ya existe, ok.
)

REM Instalar dependencias backend
echo [3/5] Instalando dependencias del backend...
call backend\venv\Scripts\activate.bat
pip install -r backend\requirements.txt -q
call deactivate

REM Instalar dependencias frontend
if not exist "frontend\node_modules" (
    echo [4/5] Instalando dependencias del frontend...
    cd frontend
    call npm install
    cd ..
) else (
    echo [4/5] Dependencias del frontend ya instaladas, ok.
)

REM Directorios necesarios
echo [5/5] Creando directorios necesarios...
if not exist "backend\static\logo" mkdir backend\static\logo
if not exist "backend\backups" mkdir backend\backups

echo.
echo ============================================
echo    Setup completado exitosamente.
echo ============================================
echo.
echo Para iniciar la app ejecutá: start.bat
echo.
echo URLs de desarrollo:
echo   Frontend: http://localhost:3000
echo   Backend:  http://localhost:8000
echo   Docs API: http://localhost:8000/api/docs
echo.
pause
