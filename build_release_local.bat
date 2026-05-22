@echo off
chcp 65001 > nul
setlocal

for /f "usebackq delims=" %%I in (`python -c "from release_metadata import LOCAL_SPEC_FILENAME; print(LOCAL_SPEC_FILENAME)"`) do set "LOCAL_SPEC=%%I"

echo ============================================
echo   KASP - Local Workspace Build
echo ============================================
echo.

if not exist "venv\Scripts\python.exe" (
    echo Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo ERROR: python command not found.
        pause
        exit /b 1
    )
)

call venv\Scripts\activate
pip install -r requirements.txt
pyinstaller --clean "%LOCAL_SPEC%"

echo.
echo Local build finished.
pause
