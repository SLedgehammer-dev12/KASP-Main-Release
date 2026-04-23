@echo off
echo ===================================================
echo KASP V4.6 - EXE Derleme Araci
echo ===================================================

echo.
echo [1/3] Python Sanal Ortami Kontrol Ediliyor...
if not exist "venv\Scripts\python.exe" (
    echo Sanal ortam bulunamadi, olusturuluyor...
    python -m venv venv
    if errorlevel 1 (
        echo HATA: python komutu bulunamadi. Lutfen Python'un kurulu oldugundan emin olun.
        pause
        exit /b 1
    )
)

echo.
echo [2/3] Gerekli Kutuphaneler Yukleniyor (Bu islme birkac dakika surebilir)...
call venv\Scripts\activate
pip install PyQt5 thermo chemicals scipy reportlab matplotlib CoolProp pyinstaller pandas numpy

echo.
echo [3/3] PyInstaller ile EXE Olusturuluyor...
pyinstaller "KASP V4.6.spec" --noconfirm --clean

echo.
echo ===================================================
if exist "dist\KASP V4.6.exe" (
    echo BASARILI: KASP V4.6.exe 'dist' klasoru icinde olusturuldu!
) else (
    echo HATA: Derleme sirasinda bir sorun olustu.
)
echo ===================================================
pause
