@echo off
echo Iniciando Sistema de Ventas y Stock...
echo.

start "Backend" cmd /k "cd backend && uvicorn app.main:app --reload"

timeout /t 3 /nobreak > nul

start "Frontend" cmd /k "cd frontend && python -m http.server 5500"

timeout /t 2 /nobreak > nul

start http://127.0.0.1:5500/login.html

echo.
echo Sistema iniciado. No cierres las dos ventanas negras que se abrieron.
echo Podes cerrar esta ventana.
pause
