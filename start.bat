@echo off
title MikroControl - Panel de Control
cd /d "%~dp0"

if not "%1"=="" goto %1

:MENU
cls
echo ============================================
echo        MikroControl - Gestión MikroTik
echo ============================================
echo.
echo  [1] Iniciar TODO (Backend + Frontend)
echo  [2] Iniciar solo Backend
echo  [3] Iniciar solo Frontend
echo  [4] Iniciar con Docker Compose
echo  [5] Abrir navegador
echo  [6] Salir
echo.
set /p opcion="Seleccioná una opción: "

if "%opcion%"=="1" goto BOTH
if "%opcion%"=="2" goto BACKEND
if "%opcion%"=="3" goto FRONTEND
if "%opcion%"=="4" goto DOCKER
if "%opcion%"=="5" goto BROWSER
if "%opcion%"=="6" exit
goto MENU

:BOTH
cls
echo ============================================
echo  Iniciando Backend + Frontend (una ventana)
echo ============================================
echo.
if not exist "backend\.env" copy .env.example backend\.env >nul 2>&1
if not exist "backend\venv" (
    echo ERROR: Falta backend\venv. Ejecutá setup.bat primero.
    pause
    exit /b
)
call backend\venv\Scripts\activate.bat
pip install -r backend\requirements.txt -q
    if not exist "frontend\node_modules" (
        cd frontend
        call npm install
        cd ..
    )
    echo.
    echo IMPORTANTE (v2): Requiere PostgreSQL en localhost:5432
    echo   - Si no lo tenés, usá la opcion 4 (Docker Compose)
    echo   - O instala Postgres y verifica DATABASE_URL en el .env
    echo.
    echo Backend: http://localhost:8000
    echo Frontend: http://localhost:3000
    echo Docs:    http://localhost:8000/api/docs
    echo.
    echo Cerra esta ventana o presioná Ctrl+C para detener todo.
    echo.
cd backend
start /b uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
cd ..\frontend
call npm run dev
cd ..
exit

:BACKEND
cls
echo ============================================
echo       Iniciando Backend...
echo ============================================
echo.
if not exist "backend\.env" copy .env.example backend\.env >nul 2>&1
if not exist "backend\venv" (
    echo ERROR: Falta backend\venv. Ejecutá setup.bat primero.
    pause
    exit /b
)
call backend\venv\Scripts\activate.bat
pip install -r backend\requirements.txt -q
echo.
echo Servidor: http://localhost:8000
echo Docs:     http://localhost:8000/api/docs
echo.
echo Ctrl+C para detener.
echo.
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
cd ..
if errorlevel 1 pause
exit

:FRONTEND
cls
echo ============================================
echo       Iniciando Frontend...
echo ============================================
echo.
if not exist "frontend\node_modules" (
    cd frontend
    call npm install
    cd ..
)
echo.
echo Servidor: http://localhost:3000
echo.
echo Ctrl+C para detener.
echo.
cd frontend
call npm run dev
cd ..
if errorlevel 1 pause
exit

:DOCKER
cls
echo ============================================
echo       Iniciando con Docker Compose...
echo ============================================
echo.
if not exist ".env" (
    copy .env.example .env >nul
    echo IMPORTANTE: Editá .env y cambia SECRET_KEY y DB_PASSWORD
    echo.
)
docker compose up -d --build
echo.
echo Nginx:    http://localhost
echo Frontend: http://localhost:3000
echo API:      http://localhost:8000
echo.
echo Logs: docker compose logs -f backend
echo Stop: docker compose down
echo.
pause
exit

:BROWSER
cls
echo ============================================
echo          Abrir en navegador
echo ============================================
echo.
echo  [1] Frontend (http://localhost:3000)
echo  [2] Backend API (http://localhost:8000)
echo  [3] Documentación API (http://localhost:8000/api/docs)
echo  [4] Nginx (http://localhost)
echo  [5] Volver
echo.
set /p opb="Opción: "

if "%opb%"=="1" start http://localhost:3000
if "%opb%"=="2" start http://localhost:8000
if "%opb%"=="3" start http://localhost:8000/api/docs
if "%opb%"=="4" start http://localhost
if "%opb%"=="5" goto MENU
goto BROWSER
