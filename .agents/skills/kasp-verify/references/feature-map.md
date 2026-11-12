# KASP Feature Map

Authoritative machine-readable source: [`features.json`](features.json).
That file drives `kasp_verify.py features`, the doctor integrity check and the
`Fxx` IDs used in the evidence ledger. Keep IDs stable; add new IDs instead of
renumbering.

| ID | Area | Feature | Entry point |
|---|---|---|---|
| F01 | auth | Login, session, logout | Header > Giriş |
| F02 | design | Compressor design calculation | Tasarım tab |
| F03 | performance | ASME PTC-10 performance test | Performans tab |
| F04 | shootout | EOS × method shootout | Mühendislik Shootout tab |
| F05 | station | Summary and equipment cards | İstasyon > özet |
| F06 | station | 2D P&ID and pipe schedule | İstasyon > P&ID |
| F07 | station-3d | 3D digital twin loads | İstasyon > 3D |
| F08 | station-3d | Click, HUD, camera fly-to | 3D sahne |
| F09 | station-3d | Equipment teardown popup | 3D ekipman tıklaması |
| F10 | reports | PDF design report | Header > PDF |
| F11 | reports | Module and station Excel | Header > Excel |
| F12 | projects | Save, load, import, export | Header > Projeler |
| F13 | logs | System logs and SSE | Sistem Logları tab |
| F14 | users | User administration | Header > Kullanıcılar |
| F15 | modules | Integration modules | Results > modüller |
| F16 | harness | OpenCode + Antigravity skill discovery | Repository root |

## Usage

```bash
python3 .agents/skills/kasp-verify/scripts/kasp_verify.py features
python3 .agents/skills/kasp-verify/scripts/kasp_verify.py features --area station-3d
python3 .agents/skills/kasp-verify/scripts/kasp_verify.py features --feature F09
```

Each entry carries `verify` steps, `expected` behaviour and `gotchas` that were
learned from the real app. When a feature changes, update its entry in
`features.json` in the same change as the code.
