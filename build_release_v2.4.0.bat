@echo off
REM KASP Windows Release Build Script v2.4.0
REM Creates: dist\"KASP v2.4.0.exe"

cd /d "%~dp0"

echo ============================================
echo   KASP Windows Release Build — v2.4.0
echo   Thermodynamic Audit & RKF45 + Multi-Stage Opt
echo ============================================
echo.

REM --- Read metadata ---
for /f "delims=" %%i in ('python -c "from release_metadata import RELEASE_SPEC_FILENAME; print(RELEASE_SPEC_FILENAME)"') do set RELEASE_SPEC=%%i
for /f "delims=" %%i in ('python -c "from release_metadata import RELEASE_EXE_NAME; print(RELEASE_EXE_NAME)"') do set RELEASE_EXE=%%i

echo [1/4] Verifying virtual environment...
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else (
    echo WARNING: No virtual environment found. Using system Python.
)

echo [2/4] Cleaning previous build artifacts...
if exist "build" rd /s /q "build"
if exist "dist" rd /s /q "dist"

echo [3/4] Building Windows Executable with PyInstaller...
echo        Spec file: %RELEASE_SPEC%
pyinstaller "%RELEASE_SPEC%" --noconfirm

echo [4/4] Verifying build output...
if exist "dist\%RELEASE_EXE%" (
    echo ============================================
    echo   BUILD SUCCESSFUL!
    echo   Output: dist\%RELEASE_EXE%
    echo ============================================
) else (
    echo ============================================
    echo   BUILD FAILED: Executable not found
    echo ============================================
    exit /b 1
)
