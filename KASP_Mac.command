#!/bin/bash
# KASP macOS Double-Click Launcher

# Projenin bulunduğu klasöre geçiş yap
cd "$(dirname "$0")"

echo "=========================================="
echo "      KASP Compressor Analysis & Selection"
VERSION=$(python3 -c "from release_metadata import RELEASE_VERSION; print(RELEASE_VERSION)")
echo "            macOS Launcher v${VERSION}"
echo "=========================================="
echo ""

# Sanal ortamı tespit et ve aktif et
if [ -d ".venv" ]; then
    echo "[1/2] Aktif ediliyor: .venv..."
    source .venv/bin/activate
elif [ -d "venv" ]; then
    echo "[1/2] Aktif ediliyor: venv..."
    source venv/bin/activate
else
    echo "HATA: Sanal ortam (.venv veya venv) bulunamadı!"
    echo "Lütfen bağımlılıkların yüklü olduğundan emin olun."
    read -p "Çıkmak için Enter'a basın..."
    exit 1
fi

echo "[2/2] KASP Başlatılıyor..."
echo ""
python3 main.py

# Program kapandığında terminali otomatik kapatmak veya hata izlemek için beklet
if [ $? -ne 0 ]; then
    echo ""
    echo "Program beklenmedik bir hata ile kapandı."
    read -p "Hata çıktılarını incelemek için Enter'a basın..."
fi
