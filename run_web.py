"""KASP Web Platform Server Launcher (run_web.py).

Starts the FastAPI + Modular ES6 web platform for local engineering use.
Access via browser at http://127.0.0.1:8000
"""

import os
import sys
import socket
import uvicorn

# Set environment defaults for local web platform
os.environ.setdefault("KASP_API_ENABLE", "1")
os.environ.setdefault("KASP_API_TOKEN", "kasp-local-token")
os.environ.setdefault("KASP_API_HOST", "127.0.0.1")

def find_available_port(preferred_ports=[8080, 8000, 8081, 8082]):
    for port in preferred_ports:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return 8080

if __name__ == "__main__":
    host = os.environ.get("KASP_API_HOST", "127.0.0.1")
    specified_port = os.environ.get("KASP_API_PORT")
    port = int(specified_port) if specified_port else find_available_port()
    os.environ["KASP_API_PORT"] = str(port)

    print("=" * 65)
    print("🚀 KASP Web Platformu Başlatılıyor...")
    print(f"🌐 Tarayıcınızdan erişin: http://{host}:{port}")
    print(f"📘 Termodinamik El Kitabı: http://{host}:{port} (Üst Menü)")
    print(f"🏭 Kompresör İstasyonu (Station P&ID): http://{host}:{port}")
    print("=" * 65)
    uvicorn.run("kasp.api.server:app", host=host, port=port, log_level="info")
