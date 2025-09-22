@echo off
echo ========================================
echo    SISTEMA OLIVION - INICIALIZACAO
echo ========================================
echo.
echo Verificando porta 3003...
netstat -ano | findstr :3003
if %errorlevel%==0 (
    echo ERRO: Porta 3003 em uso!
    echo Liberando porta...
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr :3003') do taskkill /PID %%a /F
    timeout /t 2 > nul
)

echo.
echo Iniciando Sistema Olivion...
echo.
echo ==========================================
echo  ACESSAR: http://localhost:3003
echo  LOGIN: admin
echo  SENHA: admin  
echo ==========================================
echo.

python app.py
pause