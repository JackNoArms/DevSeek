@echo off
echo ============================================
echo   DevSeek - Instalacao de dependencias
echo ============================================
echo.

echo [1/2] Instalando dependencias Python...
pip install setuptools PyQt5 undetected-chromedriver selenium watchdog
if errorlevel 1 (
    echo ERRO: Falha ao instalar pacotes. Verifique se o pip esta no PATH.
    pause
    exit /b 1
)

echo.
echo [2/2] Verificando instalacao...
python -c "import PyQt5; print('PyQt5 OK')"
python -c "import undetected_chromedriver; print('undetected-chromedriver OK')"
python -c "import selenium; print('Selenium OK')"

echo.
echo ============================================
echo   Instalacao concluida!
echo   IMPORTANTE: o Google Chrome precisa estar
echo   instalado no computador.
echo.
echo   Execute o DevSeek com:  python main.py
echo   Ou clique duas vezes em:  run.bat
echo ============================================
pause
