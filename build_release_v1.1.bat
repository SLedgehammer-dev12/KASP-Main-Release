@echo off
chcp 65001 > nul
setlocal

for /f "usebackq delims=" %%I in (`python -c "from release_metadata import RELEASE_SPEC_FILENAME; print(RELEASE_SPEC_FILENAME)"`) do set "RELEASE_SPEC=%%I"
for /f "usebackq delims=" %%I in (`python -c "from release_metadata import RELEASE_EXE_NAME; print(RELEASE_EXE_NAME)"`) do set "RELEASE_EXE=%%I"
for /f "usebackq delims=" %%I in (`python -c "from release_metadata import RELEASE_TAG; print(RELEASE_TAG)"`) do set "RELEASE_TAG=%%I"

echo ============================================
echo   KASP %RELEASE_TAG% - Release Build Script
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
copy /Y "%SRC%release_metadata.py" "%BUILD%\release_metadata.py" > nul
copy /Y "%SRC%%RELEASE_SPEC%" "%BUILD%\%RELEASE_SPEC%" > nul
if exist "%SRC%resources" robocopy "%SRC%resources" "%BUILD%\resources" /MIR /NP /NFL /NDL > nul
echo      OK - Sources copied.

echo.
echo [2/3] Running PyInstaller...
cd /d "%BUILD%"
"%BUILD%\venv\Scripts\pyinstaller.exe" --clean "%RELEASE_SPEC%"
if errorlevel 1 (
    echo ERROR: PyInstaller failed!
    pause & exit /b 1
)
echo      OK - Build complete.

echo.
echo [3/3] Copying EXE back to project...
if not exist "%SRC%dist" mkdir "%SRC%dist"
copy /Y "%BUILD%\dist\%RELEASE_EXE%" "%SRC%dist\%RELEASE_EXE%"
if errorlevel 1 (
    echo ERROR: Could not copy EXE!
    pause & exit /b 1
)

echo.
echo ============================================
echo   SUCCESS! %RELEASE_EXE% is ready in:
echo   %SRC%dist\
echo ============================================
pause
