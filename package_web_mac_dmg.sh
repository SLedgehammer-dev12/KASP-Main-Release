#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

WEB_TAG=$(python3 -c "from release_metadata import WEB_RELEASE_TAG; print(WEB_RELEASE_TAG)")
WEB_APP=$(python3 -c "from release_metadata import WEB_MAC_APP_NAME; print(WEB_MAC_APP_NAME)")
WEB_DMG=$(python3 -c "from release_metadata import WEB_MAC_DMG_NAME; print(WEB_MAC_DMG_NAME)")

APP_PATH="dist/${WEB_APP}"
DMG_PATH="dist/${WEB_DMG}"
TMP_DIR="dist/web_dmg_tmp"
VOL_NAME="KASP Web ${WEB_TAG}"

if [[ ! -d "$APP_PATH" ]]; then
  echo "HATA: ${APP_PATH} bulunamadi. Once PyInstaller ile build alin:"
  echo "  pyinstaller --clean KASP_Web_${WEB_TAG}_mac.spec"
  exit 1
fi

echo "==> Ad-hoc code signing: ${APP_PATH}"
codesign --force --deep --sign - "$APP_PATH" || true

echo "==> DMG sahnesi hazirlaniyor: ${TMP_DIR}"
rm -rf "$TMP_DIR"
mkdir -p "$TMP_DIR"
cp -R "$APP_PATH" "$TMP_DIR/"
ln -s /Applications "$TMP_DIR/Applications"

cat > "$TMP_DIR/README - Ilk Calistirma.txt" <<EOF
KASP Web ${WEB_TAG} — Ilk Calistirma Notu
========================================

Bu uygulama yerel KASP Web sunucusunu baslatir ve sistem tarayicinizda
http://127.0.0.1:<port>/ adresini otomatik olarak acar.

1. "KASP Web ${WEB_TAG}.app" simgesini Applications klasorune surukleyin.
2. Ilk acilista macOS Gatekeeper uyarisi cikar ise:
   - Uygulamaya sag tiklayip "Ac" (Open) secin, VEYA
   - Sistem Ayarlari -> Gizlilik ve Guvenlik -> "Yine de Ac" deyin, VEYA
   - Terminal'de calistirin:
     xattr -cr "/Applications/KASP Web ${WEB_TAG}.app"
3. Sunucu loglari: ~/.kasp/logs/kasp-web.log
EOF

echo "==> DMG olusturuluyor: ${DMG_PATH}"
rm -f "$DMG_PATH"
hdiutil create \
  -volname "$VOL_NAME" \
  -srcfolder "$TMP_DIR" \
  -ov \
  -format UDZO \
  "$DMG_PATH"

rm -rf "$TMP_DIR"

echo "==> Tamamlandi: ${DMG_PATH}"
ls -lh "$DMG_PATH"
