"""NeqSim Entegrasyon Testleri."""

import pytest
import os
import sys


def _has_java_and_jpype() -> bool:
    """Java/JVM ve jpype1 kurulu mu?"""
    try:
        import jpype
        import subprocess
        result = subprocess.run(["java", "-version"], capture_output=True, text=True)
        return result.returncode == 0
    except Exception:
        return False


class TestNeqSimIntegration:
    """NeqSim entegrasyon testleri."""

    def test_neqsim_input_builder(self):
        """GasMixtureBuilder.build_neqsim_input doğru NeqSim formatında çıktı üretmeli."""
        from kasp.core.mixture import GasMixtureBuilder

        # Basit metan/etan karışımı
        comp = {"METHANE": 0.9, "ETHANE": 0.1}
        result = GasMixtureBuilder.build_neqsim_input(comp)

        assert "methane" in result
        assert "ethane" in result
        assert abs(result["methane"] - 0.9) < 1e-6
        assert abs(result["ethane"] - 0.1) < 1e-6
        # Toplam 1.0 olmalı
        assert abs(sum(result.values()) - 1.0) < 1e-6

    def test_neqsim_input_builder_complex(self):
        """Karmaşık karışım için NeqSim formatı."""
        from kasp.core.mixture import GasMixtureBuilder

        comp = {
            "METHANE": 0.85,
            "ETHANE": 0.1,
            "PROPANE": 0.03,
            "NITROGEN": 0.02,
        }
        result = GasMixtureBuilder.build_neqsim_input(comp)

        # NeqSim bileşen isimleri kontrolü
        assert "methane" in result
        assert "ethane" in result
        assert "propane" in result
        assert "nitrogen" in result
        assert abs(sum(result.values()) - 1.0) < 1e-6

    def test_neqsim_input_builder_isomers(self):
        """İzomerler için NeqSim bileşen isimleri."""
        from kasp.core.mixture import GasMixtureBuilder

        comp = {
            "ISOBUTANE": 0.5,
            "BUTANE": 0.5,
        }
        result = GasMixtureBuilder.build_neqsim_input(comp)

        assert "i-butane" in result
        assert "n-butane" in result
        assert abs(sum(result.values()) - 1.0) < 1e-6

    def test_neqsim_input_normalization(self):
        """Yüzde 100 olmayan girdiler normalize edilmeli."""
        from kasp.core.mixture import GasMixtureBuilder

        # Yüzde olarak verilmiş (normalize edilmemiş)
        comp = {"METHANE": 80.0, "ETHANE": 20.0}
        result = GasMixtureBuilder.build_neqsim_input(comp)

        assert abs(result["methane"] - 0.8) < 1e-6
        assert abs(result["ethane"] - 0.2) < 1e-6
        assert abs(sum(result.values()) - 1.0) < 1e-6

    def test_neqsim_input_empty_fraction_skipped(self):
        """Sıfır kesirli bileşenler atlanmalı."""
        from kasp.core.mixture import GasMixtureBuilder

        comp = {"METHANE": 1.0, "ETHANE": 0.0}
        result = GasMixtureBuilder.build_neqsim_input(comp)

        assert "methane" in result
        assert "ethane" not in result
        assert result["methane"] == 1.0

    def test_neqsim_unknown_component_warning(self, caplog):
        """Bilinmeyen bileşenler atlanmalı ve uyarı verilmeli."""
        from kasp.core.mixture import GasMixtureBuilder

        comp = {"METHANE": 0.5, "UNKNOWN_GAS": 0.5}
        result = GasMixtureBuilder.build_neqsim_input(comp)

        assert "methane" in result
        assert "UNKNOWN_GAS" not in result
        assert any("NeqSim bileşen eşlemesi bulunamadı" in record.message for record in caplog.records)

    @pytest.mark.skipif(
        not _has_java_and_jpype(),
        reason="Java/JVM ve jpype1 gerekli"
    )
    def test_neqsim_load(self):
        """NeqSim JVM yüklenebilmeli."""
        from kasp.core.properties import ThermodynamicSolver
        solver = ThermodynamicSolver()
        # Sadece yükleme testi - JVM başlatılır
        assert solver._neqsim_available() is True

    @pytest.mark.skipif(
        not _has_java_and_jpype(),
        reason="Java/JVM ve jpype1 gerekli"
    )
    def test_neqsim_solve_methane(self):
        """Metan için NeqSim çözücüsü çalışmalı ve CoolProp ile tutarlı olmalı."""
        from kasp.core.properties import ThermodynamicSolver
        from kasp.core.mixture import GasMixtureBuilder

        solver = ThermodynamicSolver()
        if not solver._neqsim_available():
            pytest.skip("NeqSim yüklenemedi")

        # Basit metan testi
        comp = GasMixtureBuilder.build_neqsim_input({"METHANE": 1.0})
        state = solver._solve_neqsim(101325.0, 300.0, comp)

        assert state is not None
        assert state.Z > 0
        assert state.density > 0
        assert state.H != 0
        assert state.S != 0

    @pytest.mark.skipif(
        not _has_java_and_jpype(),
        reason="Java/JVM ve jpype1 gerekli"
    )
    def test_neqsim_vs_coolprop_methane(self):
        """NeqSim ve CoolProp metan için tutarlı sonuç vermeli."""
        from kasp.core.properties import ThermodynamicSolver
        from kasp.core.mixture import GasMixtureBuilder

        solver = ThermodynamicSolver()
        if not solver._neqsim_available():
            pytest.skip("NeqSim yüklenemedi")

        # Metan 100%
        comp_neqsim = GasMixtureBuilder.build_neqsim_input({"METHANE": 1.0})
        comp_coolprop = GasMixtureBuilder.build_coolprop_string(
            GasMixtureBuilder.validate_and_normalize({"METHANE": 1.0})
        )

        state_neqsim = solver._solve_neqsim(101325.0, 300.0, comp_neqsim)
        state_coolprop = solver._solve_coolprop(101325.0, 300.0, comp_coolprop)

        # Yoğunluk %5 tolerans içinde olmalı (referans bağımsız)
        rel_diff = abs(state_neqsim.density - state_coolprop.density) / state_coolprop.density
        assert rel_diff < 0.05, f"Yoğunluk sapması %5'ten fazla: NeqSim={state_neqsim.density:.2f}, CoolProp={state_coolprop.density:.2f}"
        # Z faktörü %5 içinde
        rel_z = abs(state_neqsim.Z - state_coolprop.Z) / max(abs(state_coolprop.Z), 1e-6)
        assert rel_z < 0.05, f"Z sapması %5'ten fazla: NeqSim={state_neqsim.Z:.4f}, CoolProp={state_coolprop.Z:.4f}"
        # Entalpi mutlak referansı farklı olabilir, sadece sonlu olduğu kontrol edilir
        assert abs(state_neqsim.H) < 1e7 and abs(state_coolprop.H) < 1e7


def _has_java_and_jpype() -> bool:
    """Java/JVM ve jpype1 kurulu mu?"""
    try:
        import jpype
        import subprocess
        result = subprocess.run(["java", "-version"], capture_output=True, text=True)
        return result.returncode == 0
    except Exception:
        return False


class TestNeqSimEngineIntegration:
    """NeqSim ThermoEngine ile entegrasyon testi."""

    def test_thermo_engine_accepts_neqsim(self):
        """ThermoEngine 'neqsim' eos_method kabul etmeli."""
        from kasp.core.thermo import ThermoEngine

        engine = ThermoEngine()
        # Sadece dispatch hatası vermemeli - available false dönebilecek ama metod tanınmalı
        comp_frac = {"METHANE": 1.0}
        gas_obj = engine._create_gas_object(comp_frac, "neqsim")
        assert isinstance(gas_obj, dict)
        assert "methane" in gas_obj

    def test_thermo_engine_rejects_unknown_eos(self):
        """Bilinmeyen EOS metodu hata vermeli."""
        from kasp.core.thermo import ThermoEngine

        engine = ThermoEngine()
        comp_frac = {"METHANE": 1.0}
        with pytest.raises(ValueError, match="Bilinmeyen EOS metodu"):
            engine._create_gas_object(comp_frac, "unknown_eos")


class TestNeqSimUIBinding:
    """NeqSim UI binding testleri."""

    def test_eos_method_from_ui_text_neqsim(self):
        """NeqSim UI metni doğru eos_method'a çevrilmeli."""
        from kasp.ui.design_input_binding import eos_method_from_ui_text

        # Normal seçenek
        result, err = eos_method_from_ui_text("NeqSim (CPA/SRK)")
        assert result == "neqsim"
        assert err is None

        # Eksik Java durumu
        result, err = eos_method_from_ui_text("NeqSim (Java Gerekli)")
        assert result is None
        assert err is not None
        assert "Java" in err

    def test_eos_method_from_ui_text_unknown(self):
        """Bilinmeyen EOS metodu hata vermeli."""
        from kasp.ui.design_input_binding import eos_method_from_ui_text

        result, err = eos_method_from_ui_text("Bilinmeyen EOS")
        assert result == "bilinmeyen eos"
        assert err is not None
        assert "EOS Hatası" in err