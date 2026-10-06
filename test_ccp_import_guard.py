"""Regresyon: ccp backend'i yüklenemese (ör. paketlenmiş uygulamada eksik veri
dosyası -> FileNotFoundError) bile KASP çökmemeli; isteğe bağlı backend güvenli
şekilde devre dışı kalmalı (CCP_LOADED = False).
"""

import subprocess
import sys
import textwrap


def test_properties_import_survives_ccp_data_error():
    code = textwrap.dedent(
        """
        import sys, importlib.abc

        class BoomFinder(importlib.abc.MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                if fullname == "ccp" or fullname.startswith("ccp."):
                    # Paketlenmiş uygulamada ccp/config/new_units.txt eksikse oluşan hata
                    raise FileNotFoundError("simulated missing ccp/config/new_units.txt")
                return None

        sys.meta_path.insert(0, BoomFinder())
        import kasp.core.properties as p
        assert p.CCP_LOADED is False, "ccp yüklenemediğinde CCP_LOADED False olmalı"
        import kasp.core.thermo  # noqa: F401
        print("OK")
        """
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout
