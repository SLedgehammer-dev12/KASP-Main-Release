@echo off
chcp 65001 > nul
setlocal

echo ============================================
echo   KASP V4.6.1 - EXE Build Script
echo ============================================
echo.

set "SRC=%~dp0"
set "BUILD=C:\KASP_build"

echo [1/3] Copying updated source files to build directory...
robocopy "%SRC%kasp" "%BUILD%\kasp" /MIR /XD __pycache__ /NP /NFL /NDL
if errorlevel 8 (
    echo ERROR: robocopy failed!
    pause & exit /b 1
)
copy /Y "%SRC%main.py" "%BUILD%\main.py" > nul
copy /Y "%SRC%KASP_V461.spec" "%BUILD%\KASP_V461.spec" > nul
echo      OK - Sources copied.

echo.
echo [2/3] Running PyInstaller...
cd /d "%BUILD%"
"%BUILD%\venv\Scripts\pyinstaller.exe" --clean KASP_V461.spec
if errorlevel 1 (
    echo ERROR: PyInstaller failed!
    pause & exit /b 1
)
echo      OK - Build complete.

echo.
echo [3/3] Copying EXE back to project...
if not exist "%SRC%dist" mkdir "%SRC%dist"
copy /Y "%BUILD%\dist\KASP V4.6.1.exe" "%SRC%dist\KASP V4.6.1.exe"
if errorlevel 1 (
    echo ERROR: Could not copy EXE!
    pause & exit /b 1
)

echo.
echo ============================================
echo   SUCCESS! KASP V4.6.1.exe is ready in:
echo   %SRC%dist\
echo ============================================
pause
