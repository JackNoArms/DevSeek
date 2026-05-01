@echo off
cd /d "%~dp0"
python main.py
if errorlevel 1 (
    echo.
    echo Erro ao iniciar o DevSeek.
    echo Verifique se as dependencias estao instaladas: install.bat
    pause
)
