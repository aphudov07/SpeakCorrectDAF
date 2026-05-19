@echo off
cd /d "%~dp0"
echo ============================================
echo  DAF App - sborka .exe
echo ============================================
echo.
echo [1/2] Proverka zavisimostey...
python -m pip install pyaudio numpy pyinstaller --quiet
if %errorlevel% neq 0 (
    echo OSHIBKA: ne udalos ustanovit zavisimosti.
    pause
    exit /b 1
)
echo.
echo [2/2] Sborka .exe s ikonkoy...
python -m PyInstaller --onefile --windowed --icon=daf_icon.ico --name "DAF_App" daf_app.py
if %errorlevel% neq 0 (
    echo OSHIBKA pri sborke.
    pause
    exit /b 1
)
echo.
echo Gotovo! Fayl: dist\DAF_App.exe
echo.
pause
