"""
KASP Profesyonel Hesaplama Raporu Sablonu / Professional Calculation Report Template.

Iki dilli (TR/EN) — dil secimi i18n modulunden `get_language()` ile yapilir.
Tum yer tutucular `{{DEGISKEN_ADI}}` formatindadir.
"""

from __future__ import annotations

import logging
import datetime
import os
from html import escape
from typing import Any, Mapping

try:
    from kasp.i18n import is_english, get_language
except ImportError:
    def is_english() -> bool:
        return False
    def get_language() -> str:
        return "tr"

try:
    from reportlab.platypus import Table, TableStyle, Paragraph, Spacer, PageBreak, KeepTogether
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
    REPORTLAB_LOADED = True
except ImportError:
    REPORTLAB_LOADED = False


def _register_template_fonts():
    if not REPORTLAB_LOADED:
        return
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        import sys
        if getattr(sys, "frozen", False):
            fdir = os.path.join(sys._MEIPASS, "resources", "fonts")
        else:
            fdir = os.path.join(os.path.dirname(__file__), "..", "..", "resources", "fonts")
        regular = os.path.join(fdir, "DejaVuSans.ttf")
        bold = os.path.join(fdir, "DejaVuSans-Bold.ttf")
        if os.path.exists(regular):
            pdfmetrics.registerFont(TTFont("DejaVuSans", regular))
        if os.path.exists(bold):
            pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", bold))
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.warning(f"Template DejaVuSans font registration failed: {e}")


_register_template_fonts()

logger = logging.getLogger(__name__)

_APP_VERSION_PLACEHOLDER = "{{app_version}}"


# =============================================================================
# DIL BLOKLARI / LANGUAGE BLOCKS
# =============================================================================

_TR = {

    "report_title": "KASP v{{app_version}} — Kompresor Tasarim ve Hesaplama Raporu",
    "report_date_label": "Rapor Tarihi",
    "report_generated_by": "KASP v{{app_version}} tarafindan olusturulmustur — Gelismis Termodinamik Motor (V4.5)",

    # --- Bolum Basliklari ---
    "sec1_title": "1. PROJE BILGILERI",
    "sec2_title": "2. PROSES KOSULLARI",
    "sec3_title": "3. GAZ KOMPOZISYONU ve TERMOFIZIKSEL OZELLIKLER",
    "sec4_title": "4. HAL DENKLEMI (EOS) ve TERMODINAMIK OZELLIK HESAPLARI",
    "sec5_title": "5. KOMPRESOR SIKISTIRMA HESAPLAMALARI",
    "sec6_title": "6. GUC HESAPLAMALARI",
    "sec7_title": "7. YAKIT ve ISIL HESAPLAR",
    "sec8_title": "8. KADEME-KADEME ANALIZ",
    "sec9_title": "9. TURBIN SECIMI",
    "sec10_title": "10. ASME PTC 10 OLCUM BELIRSIZLIGI ANALIZI",
    "sec11_title": "11. ENDUSTRI STANDARTLARI KARSILASTIRMASI",
    "sec12_title": "12. STANDARTLAR ve REFERANSLAR",
    "sec13_title": "13. UYARILAR ve ONERILER",
    "sec14_title": "14. TERMODINAMIK DIYAGRAMLAR",

    # --- Tablo Basliklari ---
    "parametre": "Parametre",
    "deger": "Deger",
    "birim": "Birim",
    "giris": "Giris",
    "cikis": "Cikis",
    "degisim": "Degisim (%)",
    "proje_adi": "Proje Adi",
    "unite_sayisi": "Unite Sayisi",
    "kademe_sayisi": "Kademe Sayisi",
    "gaz_kompozisyonu": "Gaz Kompozisyonu",
    "eos_metodu": "EOS (Hal Denklemi) Metodu",
    "hesaplama_metodu": "Hesaplama Metodu",
    "ortam_sicakligi": "Ortam Sicakligi",
    "ortam_basinci": "Ortam Basinci",
    "rakim": "Rakim",
    "bagil_nem": "Bagil Nem",
    "basinc": "Basinc",
    "sicaklik": "Sikistirma Orani",
    "pol_verim": "Politropik Verim",
    "isil_verim": "Isil Verim",
    "mek_verim": "Mekanik Verim",

    # --- Enerji / Guc ---
    "kutlesel_debi": "Kutlesel Debi",
    "toplam_kutlesel_debi": "Toplam Kutlesel Debi",
    "hacimsel_debi_giris": "Hacimsel Debi (Giris ACMH)",
    "gaz_gucu": "Gaz Gucu",
    "mekanik_kayip": "Mekanik Kayip",
    "saft_gucu": "Saft Gucu",
    "motor_gucu": "Motor Gucu",
    "unite_gucu": "Unite Gucu (+%4 API 617)",
    "unite_basina": "Unite Basina",
    "toplam": "Toplam (x{{num_units}})",
    "ozet_guc": "OZET GUC DENGESI",

    # --- Yakit ---
    "yakit_gazi_bilesimi": "Yakit Gazi Bilesimi",
    "lhv_kaynagi": "LHV Kaynagi",
    "lhv_deger": "LHV (Alt Isil Deger)",
    "hhv_deger": "HHV (Ust Isil Deger)",
    "yakit_isil_gucu": "Yakit Isil Gucu",
    "isi_orani": "Isi Orani (HR)",
    "yakit_tuketimi": "Yakit Tuketimi",
    "yakit_ozet": "YAKIT TUKETIM OZETI (Unite Basina)",

    # --- Kademe ---
    "kademe": "Kademe",
    "stage_p_giris": "P_giris (bar(a))",
    "stage_t_giris": "T_giris (°C)",
    "stage_p_cikis": "P_cikis (bar(a))",
    "stage_t_cikis": "T_cikis (°C)",
    "stage_head": "Head (kJ/kg)",
    "stage_poly_eff": "η_poly (tasarim)",
    "stage_dh": "ΔH (kJ/kg)",
    "stage_z_avg": "Z_avg",
    "stage_guc": "Guc (kW)",
    "toplam_head": "Toplam Politropik Head",
    "toplam_gaz_gucu_kademe": "Toplam Gaz Gucu",
    "gercek_pol_verim": "Gercek Politropik Verim",
    "intercooler_bilgi": "Ara sogutucu basinc kaybi: {{ic_dp_pct}}%, Ara sogutucu sonrasi sicaklik: {{ic_t}}°C",

    # --- Turbin ---
    "gerekli_guc": "Gerekli Guc (unite basi)",
    "saha_duzeltme_basligi": "Saha Duzeltme Faktorleri (ISO 2314)",
    "duzeltme_faktoru": "Duzeltme Faktoru",
    "ham_deger": "Ham Deger",
    "uygulanan": "Uygulanan",
    "sicaklik_f": "Sicaklik (T_ref/T_amb)",
    "basinc_f": "Basinc (P_site/P_ref)",
    "rakim_f": "Rakim [exp(-h/8500)]",
    "giris_kaybi_f": "Giris Kaybi",
    "egzoz_kaybi_f": "Egzoz Kaybi",
    "nem_f": "Nem",
    "toplam_guc_faktoru": "Toplam Guc Faktoru",
    "puanlama_baslik": "Agirlikli Puanlama Algoritmasi",
    "oneri_turbinler": "Onerilen Turbinler",
    "turbin_sira": "#",
    "turbin_ad": "Turbin",
    "turbin_guc": "Guc (kW)",
    "turbin_hr": "Isi Orani",
    "turbin_verim": "Verim",
    "turbin_surge": "Surge %",
    "turbin_puan": "Puan",
    "turbin_oneri": "Oneri",

    # --- Belirsizlik ---
    "olcum_parametresi": "Olcum Parametresi",
    "enstruman_tipi": "Enstruman Tipi",
    "standart_belirsizlik": "Standart Belirsizlik (σ)",
    "giris_basinci_s": "Giris Basinci",
    "cikis_basinci_s": "Cikis Basinci",
    "giris_sicakligi_s": "Giris Sicakligi",
    "kutlesel_debi_s": "Kutlesel Debi",
    "birlesik_belirsizlik": "Birlesik Belirsizlik (σ_combined)",
    "genisletilmis_belirsizlik": "Genisletilmis Belirsizlik (U_95%)",
    "sonuc_guven_araligi": "Sonuc (η_poly, %95 GA)",
    "katki_dagilimi": "Katki Dagilimi",

    # --- Standart Karsilastirma ---
    "tasarim_degeri": "Tasarim Degeri",
    "endustri_standard": "Endustri Standardi",
    "degerlendirme": "Degerlendirme",
    "durum": "Durum",

    # --- Uyarilar ---
    "uyari_yok": "Hesaplama sirasinda herhangi bir uyari olusmadi.",

    # --- Metot Aciklamalari ---
    "method_1_desc": (
        "Metot 1 — Ortalama Ozellikler (Average Properties):\n"
        "Giris ve cikis noktalarindaki k ve Z degerlerinin aritmetik/logaritmik "
        "ortalamasi alinarak politropik us (n) hesaplanir. Iteratif yakinsama "
        "(relaksasyon faktor = 0.5) ile cikis sicakligi bulunur. Hizlidir, "
        "cogu gaz karisimi icin yeterli dogruluk saglar."
    ),
    "method_2_desc": (
        "Metot 2 — Uc Nokta (Endpoint):\n"
        "Yalnizca cikis noktasindaki k₂ degeri kullanilarak politropik us hesaplanir. "
        "Relaksasyon faktor = 0.8 ile iteratif yakinsama yapilir. Yuksek basinc "
        "oranlarinda (PR > 3.0) Metot 1'e gore daha gercekci k degeri saglar."
    ),
    "method_3_desc": (
        "Metot 3 — Artimli Basinc (Incremental Pressure):\n"
        "Basinc araligi geometrik olarak N esit adima bolunur. Her adimda k ve Z "
        "hesaplanarak adim-adim entegrasyon yapilir. En yuksek dogruluk — ozellikle "
        "PR > 4.0 ve gercek gaz etkilerinin belirgin oldugu durumlar icin onerilir."
    ),
    "method_4_desc": (
        "Metot 4 — Dogrudan Entalpi-Entropi (Direct H-S):\n"
        "Izentropik entalpi farki (ΔH_isen) dogrudan H ve S uzerinden hesaplanir. "
        "η_isen = (PR^(k-1/k) - 1) / (PR^(k-1/k·η_poly) - 1) iliskisiyle "
        "ΔH_actual bulunur. Newton-Raphson ile H(P,T) = H₁ + ΔH_actual esitligi "
        "cozulur. En entalpi-tabanli dogrudan hesap."
    ),
}


_EN = {

    "report_title": "KASP v{{app_version}} — Compressor Design and Calculation Report",
    "report_date_label": "Report Date",
    "report_generated_by": "Generated by KASP v{{app_version}} — Advanced Thermodynamic Engine (V4.5)",

    # --- Section Titles ---
    "sec1_title": "1. PROJECT INFORMATION",
    "sec2_title": "2. PROCESS CONDITIONS",
    "sec3_title": "3. GAS COMPOSITION AND THERMOPHYSICAL PROPERTIES",
    "sec4_title": "4. EQUATION OF STATE (EOS) AND THERMODYNAMIC PROPERTY CALCULATIONS",
    "sec5_title": "5. COMPRESSOR COMPRESSION CALCULATIONS",
    "sec6_title": "6. POWER CALCULATIONS",
    "sec7_title": "7. FUEL AND THERMAL CALCULATIONS",
    "sec8_title": "8. STAGE-BY-STAGE ANALYSIS",
    "sec9_title": "9. TURBINE SELECTION",
    "sec10_title": "10. ASME PTC 10 MEASUREMENT UNCERTAINTY ANALYSIS",
    "sec11_title": "11. INDUSTRY STANDARDS COMPARISON",
    "sec12_title": "12. STANDARDS AND REFERENCES",
    "sec13_title": "13. WARNINGS AND RECOMMENDATIONS",
    "sec14_title": "14. THERMODYNAMIC DIAGRAMS",

    # --- Table Headers ---
    "parametre": "Parameter",
    "deger": "Value",
    "birim": "Unit",
    "giris": "Inlet",
    "cikis": "Outlet",
    "degisim": "Change (%)",
    "proje_adi": "Project Name",
    "unite_sayisi": "Number of Units",
    "kademe_sayisi": "Number of Stages",
    "gaz_kompozisyonu": "Gas Composition",
    "eos_metodu": "EOS (Equation of State) Method",
    "hesaplama_metodu": "Calculation Method",
    "ortam_sicakligi": "Ambient Temperature",
    "ortam_basinci": "Ambient Pressure",
    "rakim": "Altitude",
    "bagil_nem": "Relative Humidity",
    "basinc": "Pressure",
    "sicaklik": "Compression Ratio",
    "pol_verim": "Polytropic Efficiency",
    "isil_verim": "Thermal Efficiency",
    "mek_verim": "Mechanical Efficiency",

    # --- Energy / Power ---
    "kutlesel_debi": "Mass Flow Rate",
    "toplam_kutlesel_debi": "Total Mass Flow Rate",
    "hacimsel_debi_giris": "Volumetric Flow (Inlet ACMH)",
    "gaz_gucu": "Gas Power",
    "mekanik_kayip": "Mechanical Loss",
    "saft_gucu": "Shaft Power",
    "motor_gucu": "Motor Power",
    "unite_gucu": "Unit Power (+4% API 617)",
    "unite_basina": "Per Unit",
    "toplam": "Total (×{{num_units}})",
    "ozet_guc": "POWER BALANCE SUMMARY",

    # --- Fuel ---
    "yakit_gazi_bilesimi": "Fuel Gas Composition",
    "lhv_kaynagi": "LHV Source",
    "lhv_deger": "LHV (Lower Heating Value)",
    "hhv_deger": "HHV (Higher Heating Value)",
    "yakit_isil_gucu": "Fuel Thermal Power",
    "isi_orani": "Heat Rate (HR)",
    "yakit_tuketimi": "Fuel Consumption",
    "yakit_ozet": "FUEL CONSUMPTION SUMMARY (Per Unit)",

    # --- Stage ---
    "kademe": "Stage",
    "stage_p_giris": "P_in (bar(a))",
    "stage_t_giris": "T_in (°C)",
    "stage_p_cikis": "P_out (bar(a))",
    "stage_t_cikis": "T_out (°C)",
    "stage_head": "Head (kJ/kg)",
    "stage_poly_eff": "η_poly (design)",
    "stage_dh": "ΔH (kJ/kg)",
    "stage_z_avg": "Z_avg",
    "stage_guc": "Power (kW)",
    "toplam_head": "Total Polytropic Head",
    "toplam_gaz_gucu_kademe": "Total Gas Power (Stages)",
    "gercek_pol_verim": "Actual Polytropic Efficiency",
    "intercooler_bilgi": "Intercooler pressure drop: {{ic_dp_pct}}%, Intercooler outlet temperature: {{ic_t}}°C",

    # --- Turbine ---
    "gerekli_guc": "Required Power (per unit)",
    "saha_duzeltme_basligi": "Site Correction Factors (ISO 2314)",
    "duzeltme_faktoru": "Correction Factor",
    "ham_deger": "Raw Value",
    "uygulanan": "Applied",
    "sicaklik_f": "Temperature (T_ref/T_amb)",
    "basinc_f": "Pressure (P_site/P_ref)",
    "rakim_f": "Altitude [exp(-h/8500)]",
    "giris_kaybi_f": "Inlet Loss",
    "egzoz_kaybi_f": "Exhaust Loss",
    "nem_f": "Humidity",
    "toplam_guc_faktoru": "Total Power Factor",
    "puanlama_baslik": "Weighted Scoring Algorithm",
    "oneri_turbinler": "Recommended Turbines",
    "turbin_sira": "#",
    "turbin_ad": "Turbine",
    "turbin_guc": "Power (kW)",
    "turbin_hr": "Heat Rate",
    "turbin_verim": "Efficiency",
    "turbin_surge": "Surge %",
    "turbin_puan": "Score",
    "turbin_oneri": "Recommendation",

    # --- Uncertainty ---
    "olcum_parametresi": "Measurement Parameter",
    "enstruman_tipi": "Instrument Type",
    "standart_belirsizlik": "Standard Uncertainty (σ)",
    "giris_basinci_s": "Inlet Pressure",
    "cikis_basinci_s": "Outlet Pressure",
    "giris_sicakligi_s": "Inlet Temperature",
    "kutlesel_debi_s": "Mass Flow Rate",
    "birlesik_belirsizlik": "Combined Uncertainty (σ_combined)",
    "genisletilmis_belirsizlik": "Expanded Uncertainty (U_95%)",
    "sonuc_guven_araligi": "Result (η_poly, 95% CI)",
    "katki_dagilimi": "Contribution Breakdown",

    # --- Standards Comparison ---
    "tasarim_degeri": "Design Value",
    "endustri_standard": "Industry Standard",
    "degerlendirme": "Rating",
    "durum": "Status",

    # --- Warnings ---
    "uyari_yok": "No warnings were generated during the calculation.",

    # --- Method Descriptions ---
    "method_1_desc": (
        "Method 1 — Average Properties:\n"
        "Uses the arithmetic/logarithmic average of k and Z values at inlet and "
        "outlet points to calculate the polytropic exponent (n). Iterative convergence "
        "(relaxation factor = 0.5) determines outlet temperature. Fast; sufficient "
        "accuracy for most gas mixtures."
    ),
    "method_2_desc": (
        "Method 2 — Endpoint:\n"
        "Uses only the outlet k₂ value to calculate the polytropic exponent. "
        "Relaxation factor = 0.8 for iterative convergence. Provides more realistic "
        "k values at high pressure ratios (PR > 3.0) compared to Method 1."
    ),
    "method_3_desc": (
        "Method 3 — Incremental Pressure:\n"
        "Divides the pressure range geometrically into N equal steps. k and Z are "
        "recalculated at each step for step-by-step integration. Highest accuracy — "
        "recommended especially for PR > 4.0 and cases with significant real-gas effects."
    ),
    "method_4_desc": (
        "Method 4 — Direct Enthalpy-Entropy (H-S):\n"
        "Isentropic enthalpy difference (ΔH_isen) is computed directly from H and S. "
        "η_isen = (PR^(k-1/k) - 1) / (PR^(k-1/k·η_poly) - 1) relates isentropic and "
        "polytropic efficiencies. Newton-Raphson solves H(P,T) = H₁ + ΔH_actual. "
        "The most direct enthalpy-based calculation."
    ),
}


# =============================================================================
# ORTAK METINLER — Dilden bagimsiz formuller ve referanslar
# =============================================================================

_COMMON = {

    # -- EOS Formulleri --
    "eos_formulas_tr": """<b>Hesaplama Formulleri (Genel Termodinamik):</b><br/><br/>
<b>Ideal Gaz Isi Kapasitesi:</b><br/>
Cp_ig(T) = A + B·T + C·T² + D·T³ &nbsp; (NASA/Shomate polinomlari)<br/><br/>
<b>Gercek Gaz Duzeltmesi — Peng-Robinson (1976) / SRK (1972):</b><br/>
Cp_real = (Cp_ig + Cp_dep_g) / M_kg &nbsp; [J/kg·K]<br/>
Cv_real = (Cv_ig + Cv_dep_g) / M_kg &nbsp; [J/kg·K]<br/>
H = (H_ig + H_dep_g) / M_kg &nbsp; [J/kg]<br/>
S = (S_ig + S_dep_g) / M_kg &nbsp; [J/kg·K]<br/>
k = Cp_real / Cv_real<br/><br/>
<b>Peng-Robinson Kubik EOS:</b><br/>
Z³ − (1−B)Z² + (A−2B−3B²)Z − (AB−B²−B³) = 0<br/>
A = 0.45724·α(T)·P_r / T_r²<br/>
B = 0.07780·P_r / T_r<br/>
α(T) = [1 + κ·(1 − √T_r)]²<br/>
κ = 0.37464 + 1.54226·ω − 0.26992·ω²<br/><br/>
<b>Ses Hizi (Ideal Gaz):</b><br/>
a = √(k·P/ρ) &nbsp; [m/s]<br/><br/>
<b>Referanslar:</b><br/>
• Peng, D.Y. &amp; Robinson, D.B. (1976). "A New Two-Constant Equation of State." Ind. Eng. Chem. Fundam. 15: 59–64.<br/>
• Soave, G. (1972). "Equilibrium constants from a modified Redlich-Kwong EOS." Chem. Eng. Sci. 27: 1197–1203.<br/>
• GERG-2008 / ISO 20765-1 — Natural gas — Calculation of thermodynamic properties.""",

    "eos_formulas_en": """<b>Calculation Formulas (General Thermodynamics):</b><br/><br/>
<b>Ideal Gas Heat Capacity:</b><br/>
Cp_ig(T) = A + B·T + C·T² + D·T³ &nbsp; (NASA/Shomate polynomials)<br/><br/>
<b>Real Gas Correction — Peng-Robinson (1976) / SRK (1972):</b><br/>
Cp_real = (Cp_ig + Cp_dep_g) / M_kg &nbsp; [J/kg·K]<br/>
Cv_real = (Cv_ig + Cv_dep_g) / M_kg &nbsp; [J/kg·K]<br/>
H = (H_ig + H_dep_g) / M_kg &nbsp; [J/kg]<br/>
S = (S_ig + S_dep_g) / M_kg &nbsp; [J/kg·K]<br/>
k = Cp_real / Cv_real<br/><br/>
<b>Peng-Robinson Cubic EOS:</b><br/>
Z³ − (1−B)Z² + (A−2B−3B²)Z − (AB−B²−B³) = 0<br/>
A = 0.45724·α(T)·P_r / T_r²<br/>
B = 0.07780·P_r / T_r<br/>
α(T) = [1 + κ·(1 − √T_r)]²<br/>
κ = 0.37464 + 1.54226·ω − 0.26992·ω²<br/><br/>
<b>Speed of Sound (Ideal Gas):</b><br/>
a = √(k·P/ρ) &nbsp; [m/s]<br/><br/>
<b>References:</b><br/>
• Peng, D.Y. &amp; Robinson, D.B. (1976). "A New Two-Constant Equation of State." Ind. Eng. Chem. Fundam. 15: 59–64.<br/>
• Soave, G. (1972). "Equilibrium constants from a modified Redlich-Kwong EOS." Chem. Eng. Sci. 27: 1197–1203.<br/>
• GERG-2008 / ISO 20765-1 — Natural gas — Calculation of thermodynamic properties.""",

    "polytropic_formulas_tr": """<b>Temel Politropik Sikistirma Denklemi (API 617):</b><br/><br/>
H_poly = Z_avg · R_s · T₁ · (1/n) · [(P₂/P₁)^n − 1] &nbsp; [kJ/kg]<br/><br/>
<b>Politropik Sicaklik Ussu:</b><br/>
n = (k − 1) / (k · η_poly)<br/><br/>
<b>Cikis Sicakligi:</b><br/>
T₂ = T₁ · (P₂/P₁)^n &nbsp; [K]<br/><br/>
<b>Ozgul Gaz Sabiti:</b><br/>
R_s = R_u / MW_avg &nbsp; [J/kg·K]<br/>
R_u = 8.314462 J/(mol·K) (Evrensel Gaz Sabiti)<br/><br/>
<b>Logaritmik Ortalama Z (ASME PTC 10):</b><br/>
Z_avg = (Z₂ − Z₁) / ln(Z₂/Z₁)<br/><br/>
<b>Politropik Verim (Test/Gercek Olcumu):</b><br/>
η_poly = W_poly / ΔH_actual &nbsp; [—]<br/>
σ = ln(T₂/T₁) / ln(P₂/P₁) &nbsp; ≡ n (politropik us)<br/>
W_poly = (1/σ) · Z_avg · R_s · T₁ · [(P₂/P₁)^σ − 1] &nbsp; [J/kg]""",

    "polytropic_formulas_en": """<b>Fundamental Polytropic Compression Equation (API 617):</b><br/><br/>
H_poly = Z_avg · R_s · T₁ · (1/n) · [(P₂/P₁)^n − 1] &nbsp; [kJ/kg]<br/><br/>
<b>Polytropic Temperature Exponent:</b><br/>
n = (k − 1) / (k · η_poly)<br/><br/>
<b>Outlet Temperature:</b><br/>
T₂ = T₁ · (P₂/P₁)^n &nbsp; [K]<br/><br/>
<b>Specific Gas Constant:</b><br/>
R_s = R_u / MW_avg &nbsp; [J/kg·K]<br/>
R_u = 8.314462 J/(mol·K) (Universal Gas Constant)<br/><br/>
<b>Logarithmic Mean Z (ASME PTC 10):</b><br/>
Z_avg = (Z₂ − Z₁) / ln(Z₂/Z₁)<br/><br/>
<b>Polytropic Efficiency (Test/Actual Measurement):</b><br/>
η_poly = W_poly / ΔH_actual &nbsp; [—]<br/>
σ = ln(T₂/T₁) / ln(P₂/P₁) &nbsp; ≡ n (polytropic exponent)<br/>
W_poly = (1/σ) · Z_avg · R_s · T₁ · [(P₂/P₁)^σ − 1] &nbsp; [J/kg]""",

    "isentropic_solvers_tr": """<b>Izentropik Sicaklik Cozuculeri (3 Yedekli Metot):</b><br/><br/>
<table border="1" cellpadding="4" cellspacing="0">
<tr><th>Cozucu</th><th>Yontem</th><th>Formul</th></tr>
<tr><td>FD-NR</td><td>Sonlu Fark Newton-Raphson</td>
<td>T_{k+1} = T_k − (S(T_k)−S₁)/dS_dT<br/>dS_dT ≈ (S(T+ΔT)−S(T))/ΔT</td></tr>
<tr><td>AJ-NR</td><td>Analitik Jacobian NR</td>
<td>T_{k+1} = T_k − 0.9·(S(T_k)−S₁)·T_k/Cp(T_k)<br/>(dS/dT)_P = Cp/T</td></tr>
<tr><td>Brent</td><td>Brent Hibrit Kok Bulma</td>
<td>Dekker-Brent: Ikili bolme + kiris + ters kuadratik interpolasyon</td></tr>
</table><br/>
En guvenilir sonuc AJ-NR'den alinir; uc metot karsilastirmali calistirilir.<br/><br/>
<b>Referans:</b> Brent, R.P. (1973). "Algorithms for Minimization without Derivatives." Prentice-Hall. Ch. 4.""",

    "isentropic_solvers_en": """<b>Isentropic Temperature Solvers (3 Fallback Methods):</b><br/><br/>
<table border="1" cellpadding="4" cellspacing="0">
<tr><th>Solver</th><th>Method</th><th>Formula</th></tr>
<tr><td>FD-NR</td><td>Finite Difference Newton-Raphson</td>
<td>T_{k+1} = T_k − (S(T_k)−S₁)/dS_dT<br/>dS_dT ≈ (S(T+ΔT)−S(T))/ΔT</td></tr>
<tr><td>AJ-NR</td><td>Analytical Jacobian NR</td>
<td>T_{k+1} = T_k − 0.9·(S(T_k)−S₁)·T_k/Cp(T_k)<br/>(dS/dT)_P = Cp/T</td></tr>
<tr><td>Brent</td><td>Brent Hybrid Root-Finding</td>
<td>Dekker-Brent: Bisection + Secant + Inverse Quadratic Interpolation</td></tr>
</table><br/>
The most reliable result is taken from AJ-NR; all three are run for cross-comparison.<br/><br/>
<b>Reference:</b> Brent, R.P. (1973). "Algorithms for Minimization without Derivatives." Prentice-Hall. Ch. 4.""",

    "api617_integral_tr": """<b>API 617 Appendix C — Sayisal Integrasyon (PR > 4.0):</b><br/><br/>
Basinc adimlari: P_i = geomspace(P₁, P₂, N+1)<br/>
Her adimda: k_i = k(P_mid, T_i), &nbsp; Z_i = Z(P_mid, T_i)<br/><br/>
Basinc agirlikli ortalama k:<br/>
&nbsp; k_integral = Σ(w_i · k_i) / Σ(w_i), &nbsp; w_i = ΔP_i = P_{i+1} − P_i<br/><br/>
Entegre n_ust:<br/>
&nbsp; n_minus_1_over_n = (k_integral − 1) / (k_integral · η_poly)""",

    "api617_integral_en": """<b>API 617 Appendix C — Numerical Integration (PR > 4.0):</b><br/><br/>
Pressure steps: P_i = geomspace(P₁, P₂, N+1)<br/>
At each step: k_i = k(P_mid, T_i), &nbsp; Z_i = Z(P_mid, T_i)<br/><br/>
Pressure-weighted average k:<br/>
&nbsp; k_integral = Σ(w_i · k_i) / Σ(w_i), &nbsp; w_i = ΔP_i = P_{i+1} − P_i<br/><br/>
Integrated exponent:<br/>
&nbsp; n_minus_1_over_n = (k_integral − 1) / (k_integral · η_poly)""",

    # -- Guc Formulleri --
    "power_formulas_tr": """<b>Guc Zinciri (API 617, ASME PTC 10 Section 5):</b><br/><br/>
① <b>Gaz Gucu:</b> P_gas = ṁ × ΔH_actual &nbsp; [kW]<br/>
② <b>Mekanik Kayip (ExxonMobil Ampirik):</b><br/>
&nbsp; Loss_kW = 0.65 × ACMH⁰·⁴⁵ &nbsp; (maks. saft gucunun %10'u)<br/>
③ <b>Saft Gucu:</b> P_shaft = P_gas + P_mech_loss &nbsp; [kW]<br/>
④ <b>Motor Gucu:</b> P_motor = P_shaft / η_mech &nbsp; [kW]<br/>
⑤ <b>Unite Gucu (API 617 %4 Emniyet Marji):</b> P_unit = P_motor × 1.04 &nbsp; [kW]""",

    "power_formulas_en": """<b>Power Chain (API 617, ASME PTC 10 Section 5):</b><br/><br/>
① <b>Gas Power:</b> P_gas = ṁ × ΔH_actual &nbsp; [kW]<br/>
② <b>Mechanical Loss (ExxonMobil Empirical):</b><br/>
&nbsp; Loss_kW = 0.65 × ACMH⁰·⁴⁵ &nbsp; (max 10% of shaft power)<br/>
③ <b>Shaft Power:</b> P_shaft = P_gas + P_mech_loss &nbsp; [kW]<br/>
④ <b>Motor Power:</b> P_motor = P_shaft / η_mech &nbsp; [kW]<br/>
⑤ <b>Unit Power (API 617 4% Safety Margin):</b> P_unit = P_motor × 1.04 &nbsp; [kW]""",

    # -- Yakit/Isil Formuller --
    "fuel_formulas_tr": """<b>Isil Deger (ISO 6976:2016):</b><br/><br/>
<b>Molar LHV:</b> LHV_molar = Σ(LHV_i × x_i) &nbsp; [kJ/mol]<br/>
&nbsp; (ISO 6976:2016 Table 3 — molar ideal-gas net calorific values at 15°C)<br/><br/>
<b>Kutlesel LHV:</b> LHV_mass = LHV_molar / M_avg &nbsp; [kJ/kg]<br/><br/>
<b>Gercek Gaz Z Duzeltmesi:</b> LHV_corrected = LHV_mass / Z(T=15°C, P=101325 Pa)<br/><br/>
<b>HHV (Ust Isil Deger):</b><br/>
HHV = LHV + m_H₂O,uretilen × 2441.7 &nbsp; [kJ/kg]<br/>
&nbsp; (2441.7 kJ/kg = suyun 25°C'deki buharlasma gizli isisi)<br/><br/>
<b>Isi Orani ve Yakit Tuketimi (ISO 2314):</b><br/>
P_fuel = P_motor / η_therm &nbsp; [kW]<br/>
HR = P_fuel × 3600 / P_motor &nbsp; [kJ/kWh]<br/>
η_therm = 3600 / HR &nbsp; (dogrulama)<br/>
ṁ_fuel = P_fuel × 3600 / LHV &nbsp; [kg/h]""",

    "fuel_formulas_en": """<b>Heating Value (ISO 6976:2016):</b><br/><br/>
<b>Molar LHV:</b> LHV_molar = Σ(LHV_i × x_i) &nbsp; [kJ/mol]<br/>
&nbsp; (ISO 6976:2016 Table 3 — molar ideal-gas net calorific values at 15°C)<br/><br/>
<b>Mass LHV:</b> LHV_mass = LHV_molar / M_avg &nbsp; [kJ/kg]<br/><br/>
<b>Real Gas Z Correction:</b> LHV_corrected = LHV_mass / Z(T=15°C, P=101325 Pa)<br/><br/>
<b>HHV (Higher Heating Value):</b><br/>
HHV = LHV + m_H₂O,produced × 2441.7 &nbsp; [kJ/kg]<br/>
&nbsp; (2441.7 kJ/kg = latent heat of vaporization of water at 25°C)<br/><br/>
<b>Heat Rate and Fuel Consumption (ISO 2314):</b><br/>
P_fuel = P_motor / η_therm &nbsp; [kW]<br/>
HR = P_fuel × 3600 / P_motor &nbsp; [kJ/kWh]<br/>
η_therm = 3600 / HR &nbsp; (verification)<br/>
ṁ_fuel = P_fuel × 3600 / LHV &nbsp; [kg/h]""",

    # -- Turbin Puanlama --
    "turbine_scoring_tr": """<b>Agirlikli Puanlama (0–100):</b><br/><br/>
Score = 0.40·S_power + 0.30·S_eff + 0.20·S_surge + 0.10·S_type<br/><br/>
<b>Guc Skoru:</b> Ideal guc marji %5–20 (API 617 optimum oversize)<br/>
<b>Verim Skoru:</b> HR_ref = 8500–14000 kJ/kWh araliginda lineer<br/>
<b>Surge Skoru:</b> >%20 surge mesafesi = 100, <%10 = API 617 ihlal<br/>
<b>Tip Skoru:</b> Aero-Derivative = 100, Industrial/Aero = 90, Industrial = 80, Heavy-Duty = 70, Centrifugal = 60""",

    "turbine_scoring_en": """<b>Weighted Scoring (0–100):</b><br/><br/>
Score = 0.40·S_power + 0.30·S_eff + 0.20·S_surge + 0.10·S_type<br/><br/>
<b>Power Score:</b> Ideal power margin 5–20% (API 617 optimum oversize)<br/>
<b>Efficiency Score:</b> HR_ref = 8500–14000 kJ/kWh linear range<br/>
<b>Surge Score:</b> >20% surge margin = 100, <10% = API 617 violation<br/>
<b>Type Score:</b> Aero-Derivative = 100, Industrial/Aero = 90, Industrial = 80, Heavy-Duty = 70, Centrifugal = 60""",

    # -- Saha Duzeltmeleri --
    "site_corrections_tr": """<b>ISO Saha Duzeltme Faktorleri (ISO 2314 / ASME PTC 22):</b><br/><br/>
f_T = T_ref / T_amb &nbsp; (T_ref = 288.15 K)<br/>
f_P = P_site / P_ref &nbsp; (P_ref = 101.325 kPa)<br/>
f_alt = exp(−altitude / 8500) &nbsp; (ISA standart atmosfer)<br/>
f_inlet = (P_site − ΔP_inlet) / P_site<br/>
f_exhaust = 1.0 − 0.005 × (ΔP_exhaust / ΔP_ref)<br/>
f_humidity = 1.0 − 0.0002 × (RH − 60)<br/><br/>
P_corrected = P_actual × (f_T · f_P · f_inlet · f_exhaust · f_humidity)⁻¹""",

    "site_corrections_en": """<b>ISO Site Correction Factors (ISO 2314 / ASME PTC 22):</b><br/><br/>
f_T = T_ref / T_amb &nbsp; (T_ref = 288.15 K)<br/>
f_P = P_site / P_ref &nbsp; (P_ref = 101.325 kPa)<br/>
f_alt = exp(−altitude / 8500) &nbsp; (ISA standard atmosphere)<br/>
f_inlet = (P_site − ΔP_inlet) / P_site<br/>
f_exhaust = 1.0 − 0.005 × (ΔP_exhaust / ΔP_ref)<br/>
f_humidity = 1.0 − 0.0002 × (RH − 60)<br/><br/>
P_corrected = P_actual × (f_T · f_P · f_inlet · f_exhaust · f_humidity)⁻¹""",

    # -- Belirsizlik --
    "uncertainty_formulas_tr": """<b>ASME PTC 10 Appendix B — RSS (Root-Sum-Square) Belirsizlik Yayilimi:</b><br/><br/>
<b>Birlesik Belirsizlik:</b><br/>
σ_combined = √[ Σ(S_i · σ_i)² ]<br/><br/>
S_i = ∂f/∂x_i ≈ (f(x+Δx) − f(x−Δx)) / (2·Δx) &nbsp; (merkezi fark sayisal turev)<br/><br/>
<b>Genisletilmis Belirsizlik (%95 Guven Araligi):</b><br/>
U_95% = k × σ_combined, &nbsp; k = 2.0 &nbsp; (normal dagilim)""",

    "uncertainty_formulas_en": """<b>ASME PTC 10 Appendix B — RSS (Root-Sum-Square) Uncertainty Propagation:</b><br/><br/>
<b>Combined Uncertainty:</b><br/>
σ_combined = √[ Σ(S_i · σ_i)² ]<br/><br/>
S_i = ∂f/∂x_i ≈ (f(x+Δx) − f(x−Δx)) / (2·Δx) &nbsp; (central difference numerical derivative)<br/><br/>
<b>Expanded Uncertainty (95% Confidence Interval):</b><br/>
U_95% = k × σ_combined, &nbsp; k = 2.0 &nbsp; (normal distribution)""",

    # -- Standart Referanslar --
    "standards_refs_tr": """<b>Bu rapor asagidaki endustri standartlarina uygun olarak hazirlanmistir:</b><br/><br/>
<b>Termodinamik ve Performans:</b><br/>
• ASME PTC 10-1997 — Performance Test Code on Compressors and Exhausters<br/>
• ASME PTC 10 — Appendix B: Measurement Uncertainty (RSS method, k=2.0)<br/>
• ASME PTC 22-2014 — Performance Test Code on Gas Turbines<br/>
• ISO 2314:2009 — Gas turbines — Acceptance tests<br/>
• ISO 6976:2016 — Natural gas — Calculation of calorific values (LHV/HHV)<br/><br/>
<b>Kompresor Tasarimi:</b><br/>
• API 617 (8th Ed.) — Axial and Centrifugal Compressors and Expander-compressors<br/>
• API 617 — Appendix C: Polytropic exponent numerical integration<br/><br/>
<b>Turbin ve Ekipman:</b><br/>
• API 616 (5th Ed.) — Gas Turbines for the Petroleum, Chemical, and Gas Industry Services<br/>
• ISO 3977:2009 — Gas turbines — Procurement<br/><br/>
<b>Hal Denklemleri:</b><br/>
• Peng, D.Y. &amp; Robinson, D.B. (1976). Ind. Eng. Chem. Fundam. 15: 59–64.<br/>
• Soave, G. (1972). Chem. Eng. Sci. 27: 1197–1203.<br/>
• GERG-2008 / ISO 20765-1 — Natural gas — Calculation of thermodynamic properties<br/><br/>
<b>Rapor Motoru:</b> KASP v{{app_version}} (Termodinamik Motor V4.5 — 4 Metotlu)""",

    "standards_refs_en": """<b>This report has been prepared in accordance with the following industry standards:</b><br/><br/>
<b>Thermodynamics and Performance:</b><br/>
• ASME PTC 10-1997 — Performance Test Code on Compressors and Exhausters<br/>
• ASME PTC 10 — Appendix B: Measurement Uncertainty (RSS method, k=2.0)<br/>
• ASME PTC 22-2014 — Performance Test Code on Gas Turbines<br/>
• ISO 2314:2009 — Gas turbines — Acceptance tests<br/>
• ISO 6976:2016 — Natural gas — Calculation of calorific values (LHV/HHV)<br/><br/>
<b>Compressor Design:</b><br/>
• API 617 (8th Ed.) — Axial and Centrifugal Compressors and Expander-compressors<br/>
• API 617 — Appendix C: Polytropic exponent numerical integration<br/><br/>
<b>Turbine and Equipment:</b><br/>
• API 616 (5th Ed.) — Gas Turbines for the Petroleum, Chemical, and Gas Industry Services<br/>
• ISO 3977:2009 — Gas turbines — Procurement<br/><br/>
<b>Equations of State:</b><br/>
• Peng, D.Y. &amp; Robinson, D.B. (1976). Ind. Eng. Chem. Fundam. 15: 59–64.<br/>
• Soave, G. (1972). Chem. Eng. Sci. 27: 1197–1203.<br/>
• GERG-2008 / ISO 20765-1 — Natural gas — Calculation of thermodynamic properties<br/><br/>
<b>Report Engine:</b> KASP v{{app_version}} (Thermodynamic Engine V4.5 — 4 Methods)""",

    # -- Consistentcy Mode --
    "consistency_mode_tr": """<b>Tutarlilik Modu (Iteratif Yakinsama):</b><br/><br/>
η_kullanilan = η_hedef olarak baslar, her iterasyonda hesaplanan η ile<br/>
relaksasyonlu guncelleme yapilir:<br/><br/>
η_new = α × η_calculated + (1−α) × η_current<br/><br/>
α = relaksasyon faktoru (varsayilan 0.35)<br/>
Yakinsama kriteri: |η_calculated − η_current| < tolerans""",

    "consistency_mode_en": """<b>Consistency Mode (Iterative Convergence):</b><br/><br/>
Starts with η_used = η_target, applies relaxed update at each iteration:<br/><br/>
η_new = α × η_calculated + (1−α) × η_current<br/><br/>
α = relaxation factor (default 0.35)<br/>
Convergence criterion: |η_calculated − η_current| < tolerance""",

    "stage_pr_formula_tr": """<b>Kademe Basinc Orani:</b><br/>
PR_stage = (PR_total / (1 − ΔP_araloss)^(N−1))^(1/N)""",

    "stage_pr_formula_en": """<b>Stage Pressure Ratio:</b><br/>
PR_stage = (PR_total / (1 − ΔP_intercooler)^(N−1))^(1/N)""",

    "iso6976_lhv_table_tr": """<b>ISO 6976:2016 Table 3 — Molar Ideal-Gaz Net Kalorifik Degerler (15°C):</b><br/><br/>
CH₄: 802.62 | C₂H₆: 1429.35 | C₃H₈: 2044.20 | i-C₄H₁₀: 2650.88 | n-C₄H₁₀: 2660.74<br/>
i-C₅H₁₂: 3270.28 | n-C₅H₁₂: 3277.20 | n-C₆H₁₄: 3894.10 | n-C₇H₁₆: 4511.00<br/>
n-C₈H₁₈: 5127.90 | n-C₉H₂₀: 5744.80 | n-C₁₀H₂₂: 6361.70<br/>
H₂: 241.83 | H₂S: 517.93 &nbsp; (kJ/mol)<br/>
Inertler (N₂, CO₂, H₂O, Ar, He, O₂, Ne, Kr, Xe): 0""",

    "iso6976_lhv_table_en": """<b>ISO 6976:2016 Table 3 — Molar Ideal-Gas Net Calorific Values (15°C):</b><br/><br/>
CH₄: 802.62 | C₂H₆: 1429.35 | C₃H₈: 2044.20 | i-C₄H₁₀: 2650.88 | n-C₄H₁₀: 2660.74<br/>
i-C₅H₁₂: 3270.28 | n-C₅H₁₂: 3277.20 | n-C₆H₁₄: 3894.10 | n-C₇H₁₆: 4511.00<br/>
n-C₈H₁₈: 5127.90 | n-C₉H₂₀: 5744.80 | n-C₁₀H₂₂: 6361.70<br/>
H₂: 241.83 | H₂S: 517.93 &nbsp; (kJ/mol)<br/>
Inerts (N₂, CO₂, H₂O, Ar, He, O₂, Ne, Kr, Xe): 0""",

    "available_eos_models_tr": (
        "<b>Kullanilabilir EOS Modelleri:</b><br/>"
        "• <b>CoolProp</b> — Yüksek dogruluklu Helmholtz enerji modelleri (GERG-2008). "
        "En genis akiskan veritabani. Dogal gaz karisimlari icin referans.<br/>"
        "• <b>Peng-Robinson (PR)</b> — Kubik EOS, iyi faz dengesi tahmini. "
        "Hidrokarbon sistemleri icin endustri standardi.<br/>"
        "• <b>Soave-Redlich-Kwong (SRK)</b> — Kubik EOS, PR'a benzer. "
        "Dusuk sicakliklarda ve polar olmayan sistemlerde iyi performans.<br/>"
        "• <b>AGA8 (GERG-2008)</b> — Dogal gaz icin ISO referans EOS. "
        "pyaga8 kutuphanesi uzerinden en dogru Z-faktor ve yogunluk hesabi."
    ),
    "available_eos_models_en": (
        "<b>Available EOS Models:</b><br/>"
        "• <b>CoolProp</b> — High-accuracy Helmholtz energy models (GERG-2008). "
        "Most extensive fluid database. Reference for natural gas mixtures.<br/>"
        "• <b>Peng-Robinson (PR)</b> — Cubic EOS, good phase equilibrium predictions. "
        "Industry standard for hydrocarbon systems.<br/>"
        "• <b>Soave-Redlich-Kwong (SRK)</b> — Cubic EOS, similar to PR. "
        "Good performance at low temperatures and non-polar systems.<br/>"
        "• <b>AGA8 (GERG-2008)</b> — ISO reference EOS for natural gas. "
        "Most accurate Z-factor and density via the pyaga8 library."
    ),

    "benchmark_scale_tr": (
        "Degerlendirme Skalasi: "
        "Excellent/Mukemmel (≥88) / Good/Iyi (≥85) / Fair/Orta (≥80) / "
        "Below Standard/Standart Alti (<80)"
    ),
    "benchmark_scale_en": (
        "Rating Scale: "
        "Excellent (≥88) / Good (≥85) / Fair (≥80) / "
        "Below Standard (<80)"
    ),
}


# =============================================================================
# Sablon Sinifi
# =============================================================================

class ReportTemplate:
    """Iki dilli (TR/EN) profesyonel hesaplama raporu sablonu."""

    def __init__(self):
        self._lang = get_language()
        self._en = self._lang.startswith("en")
        self._t = _EN if self._en else _TR
        self._c = _COMMON

    # -- Dil secimi --
    @property
    def language(self) -> str:
        return self._lang

    def _k(self, key: str) -> str:
        """Anahtari TR/EN dil blogundan getirir, yoksa ortak metinden dener."""
        return self._t.get(key) or self._c.get(key) or key

    @staticmethod
    def _fill(template: str, context: Mapping[str, Any]) -> str:
        """Yer tutuculari context sozlugu ile doldurur."""
        if not template or "{{" not in template:
            return template
        result = template
        for key, value in context.items():
            placeholder = "{{" + key + "}}"
            if placeholder in result:
                result = result.replace(placeholder, _safe_str(value))
        return result

    # =========================================================================
    # HTML Rapor
    # =========================================================================

    def render_html(self, context: Mapping[str, Any]) -> str:
        """HTML formatinda tam raporu dondurur."""
        ctx = dict(context)
        ctx.setdefault("app_version", "V4.5")
        ctx.setdefault("report_date", datetime.datetime.now().strftime("%d/%m/%Y %H:%M"))
        ctx.setdefault("warnings_html", "")
        ctx.setdefault("consistency_html", "")
        ctx.setdefault("stage_rows_html", "")
        ctx.setdefault("turbine_rows_html", "")
        ctx.setdefault("uncertainty_breakdown_html", "")

        fill = lambda k: self._fill(self._k(k), ctx)
        cf = lambda k: self._fill(self._c.get(k, ""), ctx)

        en = self._en
        t = self._k

        # --- EOS display name ---
        eos_display = {
            "coolprop": "CoolProp (GERG-2008 / Helmholtz)",
            "pr": "Peng-Robinson (Thermo PR)",
            "srk": "Soave-Redlich-Kwong (Thermo SRK)",
            "aga8": "AGA8 (GERG-2008 / ISO 20765-1)",
        }
        eos_method = str(ctx.get("eos_method", "")).lower()
        eos_name = eos_display.get(eos_method, eos_method.upper())

        # --- Method display ---
        method_map = {
            "average": "Metot 1: Ortalama Ozellikler" if not en else "Method 1: Average Properties",
            "endpoint": "Metot 2: Uc Nokta (Endpoint)" if not en else "Method 2: Endpoint",
            "incremental": "Metot 3: Artimli Basinc (Incremental)" if not en else "Method 3: Incremental Pressure",
            "direct_hs": "Metot 4: Dogrudan H-S (Direct H-S)" if not en else "Method 4: Direct H-S",
        }
        method_key = str(ctx.get("method_key", "average")).lower()
        method_display = method_map.get(method_key, ctx.get("method", method_key))

        # --- LHV source ---
        lhv_source = str(ctx.get("lhv_source", "kasp")).lower()
        lhv_map = {
            "iso6976": "ISO 6976:2016",
            "kasp": "KASP Veritabani" if not en else "KASP Database",
            "thermo": "Thermo Kutuphanesi" if not en else "Thermo Library",
        }
        lhv_src_display = lhv_map.get(lhv_source, lhv_source)

        parts = []

        # -- Baslik --
        parts.append(f"""<div style="text-align:center; margin-bottom:30px;">
<h1>{fill("report_title")}</h1>
<h2>{ctx.get("project_name", "")}</h2>
<p><b>{t("report_date_label")}:</b> {ctx.get("report_date")} | {fill("report_generated_by")}</p>
</div>""")

        # -- 1. PROJE BILGILERI --
        parts.append(f"<h2>{t('sec1_title')}</h2>")
        parts.append(f"""<table border="1" cellpadding="6" cellspacing="0" width="100%">
<tr><th width="35%">{t('parametre')}</th><th>{t('deger')}</th><th width="15%">{t('birim')}</th></tr>
<tr><td>{t('proje_adi')}</td><td>{ctx.get('project_name','')}</td><td></td></tr>
<tr><td>{t('unite_sayisi')}</td><td>{ctx.get('num_units','')}</td><td></td></tr>
<tr><td>{t('kademe_sayisi')}</td><td>{ctx.get('num_stages','')}</td><td></td></tr>
<tr><td>{t('gaz_kompozisyonu')}</td><td>{_safe_str(ctx.get('composition_summary',''))}</td><td></td></tr>
<tr><td>{t('eos_metodu')}</td><td>{eos_name}</td><td></td></tr>
<tr><td>{t('hesaplama_metodu')}</td><td>{method_display}</td><td></td></tr>
<tr><td>{t('ortam_sicakligi')}</td><td>{ctx.get('ambient_temp','')}</td><td>°C</td></tr>
<tr><td>{t('ortam_basinci')}</td><td>{ctx.get('ambient_pressure','')}</td><td>kPa</td></tr>
<tr><td>{t('rakim')}</td><td>{ctx.get('altitude','')}</td><td>m</td></tr>
<tr><td>{t('bagil_nem')}</td><td>{ctx.get('humidity','')}</td><td>%</td></tr>
</table><br/>""")

        # -- 2. PROSES KOSULLARI --
        parts.append(f"<h2>{t('sec2_title')}</h2>")
        parts.append(f"""<table border="1" cellpadding="6" cellspacing="0" width="100%">
<tr><th width="30%">{t('parametre')}</th><th width="25%">{t('giris')}</th><th width="25%">{t('cikis')}</th><th width="15%">{t('birim')}</th></tr>
<tr><td>{t('basinc')}</td><td>{ctx.get('p_in','')}</td><td>{ctx.get('p_out','')}</td><td>{ctx.get('p_in_unit','')}</td></tr>
<tr><td>{t('sicaklik')}</td><td>{ctx.get('t_in','')}</td><td>{ctx.get('t_out','')}</td><td>{ctx.get('t_in_unit','')} / °C</td></tr>
<tr><td>{t('sicaklik')}</td><td colspan="2" align="center">{ctx.get('compression_ratio','')}</td><td>—</td></tr>
<tr><td>{t('pol_verim')}</td><td>{ctx.get('design_poly_eff','')}%</td><td>{ctx.get('actual_poly_eff','')}%</td><td>%</td></tr>
<tr><td>{t('isil_verim')}</td><td>{ctx.get('therm_eff','')}%</td><td>—</td><td>%</td></tr>
<tr><td>{t('mek_verim')}</td><td>{ctx.get('mech_eff','')}%</td><td>—</td><td>%</td></tr>
</table><br/>""")

        # -- 3. GAZ KOMPOZISYONU --
        parts.append(f"<h2>{t('sec3_title')}</h2>")
        parts.append(f"<h3>3.1 {'Bilesen Analizi' if not en else 'Component Analysis'}</h3>")
        parts.append(ctx.get("composition_table_html", ""))
        parts.append(f"<p><b>{'Karisim Molar Kutlesi' if not en else 'Mixture Molar Mass'}:</b> {ctx.get('mixture_mw','')} g/mol</p>")

        parts.append(f"<h3>3.2 {'Isil Deger Hesabi (ISO 6976:2016)' if not en else 'Heating Value Calculation (ISO 6976:2016)'}</h3>")
        parts.append(f"<p>{cf('iso6976_lhv_table_' + ('en' if en else 'tr'))}</p>")
        parts.append(f"<p>{cf('fuel_formulas_' + ('en' if en else 'tr'))}</p>")
        parts.append(f"""<table border="1" cellpadding="6" cellspacing="0" width="60%">
<tr><th>{t('parametre')}</th><th>{t('deger')}</th><th>{t('birim')}</th></tr>
<tr><td>{t('lhv_deger')}</td><td>{ctx.get('calculated_lhv','')}</td><td>kJ/kg</td></tr>
<tr><td>{t('hhv_deger')}</td><td>{ctx.get('calculated_hhv','')}</td><td>kJ/kg</td></tr>
</table><br/>""")

        # -- 4. EOS --
        parts.append(f"<h2>{t('sec4_title')}</h2>")
        parts.append(f"<p><b>{'Secilen EOS Modeli:' if not en else 'Selected EOS Model:'}</b> {eos_name}</p>")
        parts.append(f"<p>{cf('available_eos_models_' + ('en' if en else 'tr'))}</p>")

        parts.append(f"<h3>{'Cozumlenen Termodinamik Ozellikler' if not en else 'Solved Thermodynamic Properties'}</h3>")
        parts.append(f"""<table border="1" cellpadding="6" cellspacing="0" width="100%">
<tr><th>{'Ozellik' if not en else 'Property'}</th><th>{'Giris' if not en else 'Inlet'} ({ctx.get('t_in','')}/{ctx.get('p_in','')})</th><th>{'Cikis' if not en else 'Outlet'} ({ctx.get('t_out','')}/{ctx.get('p_out','')})</th><th>{t('degisim')}</th></tr>
<tr><td>Z ({'Sikistirilabilirlik' if not en else 'Compressibility'})</td><td>{ctx.get('z_in','')}</td><td>{ctx.get('z_out','')}</td><td>{ctx.get('z_change_pct','')}%</td></tr>
<tr><td>k (Cp/Cv)</td><td>{ctx.get('k_in','')}</td><td>{ctx.get('k_out','')}</td><td>{ctx.get('k_change_pct','')}%</td></tr>
<tr><td>Cp (kJ/kg·K)</td><td>{ctx.get('cp_in','')}</td><td>{ctx.get('cp_out','')}</td><td>{ctx.get('cp_change_pct','')}%</td></tr>
<tr><td>Cv (kJ/kg·K)</td><td>{ctx.get('cv_in','')}</td><td>{ctx.get('cv_out','')}</td><td>{ctx.get('cv_change_pct','')}%</td></tr>
<tr><td>&rho; (kg/m³)</td><td>{ctx.get('rho_in','')}</td><td>{ctx.get('rho_out','')}</td><td>{ctx.get('rho_change_pct','')}%</td></tr>
<tr><td>H (kJ/kg)</td><td>{ctx.get('h_in','')}</td><td>{ctx.get('h_out','')}</td><td>{ctx.get('delta_h','')} &Delta;</td></tr>
<tr><td>S (kJ/kg·K)</td><td>{ctx.get('s_in','')}</td><td>{ctx.get('s_out','')}</td><td>—</td></tr>
<tr><td>&mu; (&mu;Pa·s)</td><td>{ctx.get('mu_in','')}</td><td>{ctx.get('mu_out','')}</td><td>—</td></tr>
<tr><td>{'Ses Hizi' if not en else 'Sound Speed'} (m/s)</td><td>{ctx.get('a_in','')}</td><td>{ctx.get('a_out','')}</td><td>—</td></tr>
</table><br/>""")

        parts.append(f"<p>{cf('eos_formulas_' + ('en' if en else 'tr'))}</p>")
        parts.append(f"<p><b>{'Not:' if not en else 'Note:'}</b> {'Onbellek (LRU Cache) ile 3000 noktaya kadar saklama. Isabet orani:' if not en else 'LRU Cache stores up to 3000 points. Hit rate:'} {ctx.get('cache_hit_rate_pct','')}%</p>")

        # -- 5. SİKISTIRMA HESAPLAMALARI --
        parts.append(f"<h2>{t('sec5_title')}</h2>")
        parts.append(f"<p><b>{'Hesaplama Metodu:' if not en else 'Calculation Method:'}</b> {method_display}</p>")

        # Metot aciklamasi
        method_desc_keys = {
            "average": "method_1_desc",
            "endpoint": "method_2_desc",
            "incremental": "method_3_desc",
            "direct_hs": "method_4_desc",
        }
        desc_key = method_desc_keys.get(method_key, "method_1_desc")
        parts.append(f"<p style='white-space:pre-line'>{t(desc_key)}</p>")

        parts.append(f"<p>{cf('polytropic_formulas_' + ('en' if en else 'tr'))}</p>")
        parts.append(f"<p>{cf('isentropic_solvers_' + ('en' if en else 'tr'))}</p>")
        parts.append(f"<p>{cf('api617_integral_' + ('en' if en else 'tr'))}</p>")

        parts.append(f"<h3>{'Hesaplama Sonuclari' if not en else 'Calculation Results'}</h3>")
        parts.append(f"""<table border="1" cellpadding="6" cellspacing="0" width="60%">
<tr><th>{t('parametre')}</th><th>{t('deger')}</th><th>{t('birim')}</th></tr>
<tr><td>{'Politropik Head' if not en else 'Polytropic Head'} (H_poly)</td><td>{ctx.get('calculated_head','')}</td><td>kJ/kg</td></tr>
<tr><td>{'Cikis Sicakligi' if not en else 'Outlet Temperature'} (T₂)</td><td>{ctx.get('calculated_t_out','')}</td><td>K ({ctx.get('calculated_t_out_c','')}°C)</td></tr>
<tr><td>{'Ortalama Z Faktoru' if not en else 'Average Z Factor'}</td><td>{ctx.get('calculated_z_avg','')}</td><td>—</td></tr>
<tr><td>{'Ortalama k (Cp/Cv)' if not en else 'Average k (Cp/Cv)'}</td><td>{ctx.get('calculated_k_avg','')}</td><td>—</td></tr>
<tr><td>{'Yakinsama Iterasyonu' if not en else 'Convergence Iterations'}</td><td>{ctx.get('convergence_iterations','')}</td><td></td></tr>
<tr><td>{'Yakinsama Durumu' if not en else 'Convergence Status'}</td><td>{ctx.get('convergence_status','')}</td><td></td></tr>
</table><br/>""")

        # Consistency mode
        if ctx.get("consistency_mode") == "True":
            parts.append(f"<h3>{'Tutarlilik Modu' if not en else 'Consistency Mode'}</h3>")
            parts.append(f"<p>{cf('consistency_mode_' + ('en' if en else 'tr'))}</p>")
            parts.append(ctx.get("consistency_html", ""))

        # -- 6. GUC --
        parts.append(f"<h2>{t('sec6_title')}</h2>")
        parts.append(f"<p><b>{'Debi:' if not en else 'Flow:'}</b></p>")
        parts.append(f"""<table border="1" cellpadding="6" cellspacing="0" width="60%">
<tr><td>{t('kutlesel_debi')}</td><td>{ctx.get('mass_flow_per_unit','')} kg/s ({t('unite_basina')})</td></tr>
<tr><td>{t('toplam_kutlesel_debi')}</td><td>{ctx.get('mass_flow_total','')} kg/s</td></tr>
<tr><td>{t('hacimsel_debi_giris')}</td><td>{ctx.get('inlet_acmh_per_unit','')} m³/h ({t('unite_basina')})</td></tr>
</table><br/>""")

        parts.append(f"<p>{cf('power_formulas_' + ('en' if en else 'tr'))}</p>")

        num_units = ctx.get('num_units', 1)
        parts.append(f"<h3>{t('ozet_guc')}</h3>")
        parts.append(f"""<table border="1" cellpadding="6" cellspacing="0" width="100%">
<tr><th width="30%"></th><th width="30%">{t('unite_basina')}</th><th width="30%">{self._fill(t('toplam'), {'num_units': num_units})}</th></tr>
<tr><td>{t('gaz_gucu')}</td><td>{ctx.get('pg_per_unit','')} kW</td><td>{ctx.get('pg_total','')} kW</td></tr>
<tr><td>{t('mekanik_kayip')}</td><td>{ctx.get('ml_per_unit','')} kW</td><td>{ctx.get('ml_total','')} kW</td></tr>
<tr><td>{t('saft_gucu')}</td><td>{ctx.get('ps_per_unit','')} kW</td><td>{ctx.get('ps_total','')} kW</td></tr>
<tr><td>{t('motor_gucu')}</td><td>{ctx.get('pm_per_unit','')} kW</td><td>{ctx.get('pm_total','')} kW</td></tr>
<tr><td>{t('unite_gucu')}</td><td>{ctx.get('pu_per_unit','')} kW</td><td>{ctx.get('pu_total','')} kW</td></tr>
</table><br/>""")

        # -- 7. YAKIT --
        parts.append(f"<h2>{t('sec7_title')}</h2>")
        parts.append(f"""<table border="1" cellpadding="6" cellspacing="0" width="60%">
<tr><td>{t('yakit_gazi_bilesimi')}</td><td>{_safe_str(ctx.get('fuel_composition_summary',''))}</td></tr>
<tr><td>{t('lhv_kaynagi')}</td><td>{lhv_src_display}</td></tr>
<tr><td>{t('lhv_deger')}</td><td>{ctx.get('calculated_lhv','')} kJ/kg</td></tr>
<tr><td>{t('hhv_deger')}</td><td>{ctx.get('calculated_hhv','')} kJ/kg</td></tr>
</table><br/>""")

        parts.append(f"<h3>{t('yakit_ozet')}</h3>")
        parts.append(f"""<table border="1" cellpadding="6" cellspacing="0" width="60%">
<tr><td>{t('yakit_isil_gucu')}</td><td>{ctx.get('fuel_thermal_kw','')} kW</td></tr>
<tr><td>{t('isi_orani')}</td><td>{ctx.get('heat_rate','')} kJ/kWh</td></tr>
<tr><td>{t('yakit_tuketimi')}</td><td>{ctx.get('fuel_unit_kgh','')} kg/h ({t('unite_basina')})<br/>{ctx.get('fuel_total_kgh','')} kg/h ({'toplam' if not en else 'total'})</td></tr>
<tr><td>{t('isil_verim')}</td><td>{ctx.get('heat_rate_eff_pct','')}%</td></tr>
</table><br/>""")

        # -- 8. KADEME --
        parts.append(f"<h2>{t('sec8_title')}</h2>")
        parts.append(f"<p>{self._fill(t('intercooler_bilgi'), {'ic_dp_pct': ctx.get('intercooler_dp_pct',''), 'ic_t': ctx.get('intercooler_t','')})}</p>")
        parts.append(f"<p>{cf('stage_pr_formula_' + ('en' if en else 'tr'))}</p>")
        parts.append(f"""<table border="1" cellpadding="4" cellspacing="0" width="100%">
<tr><th>{t('kademe')}</th><th>{t('stage_p_giris')}</th><th>{t('stage_t_giris')}</th><th>{t('stage_p_cikis')}</th><th>{t('stage_t_cikis')}</th><th>{t('stage_head')}</th><th>{t('stage_poly_eff')}</th><th>{t('stage_dh')}</th><th>{t('stage_z_avg')}</th><th>{t('stage_guc')}</th></tr>
{ctx.get('stage_rows_html','')}
</table><br/>""")
        parts.append(f"""<table border="1" cellpadding="6" cellspacing="0" width="60%">
<tr><td>{t('toplam_head')}</td><td>{ctx.get('total_poly_head','')} kJ/kg</td></tr>
<tr><td>{t('toplam_gaz_gucu_kademe')}</td><td>{ctx.get('total_stage_gas_power','')} kW</td></tr>
<tr><td>{t('gercek_pol_verim')}</td><td>{ctx.get('actual_poly_eff_pct','')}%</td></tr>
</table><br/>""")

        # -- 9. TURBIN --
        parts.append(f"<h2>{t('sec9_title')}</h2>")
        parts.append(f"<p><b>{t('gerekli_guc')}:</b> {ctx.get('required_power_kw','')} kW</p>")

        parts.append(f"<h3>{t('saha_duzeltme_basligi')}</h3>")
        parts.append(f"<p>{cf('site_corrections_' + ('en' if en else 'tr'))}</p>")
        parts.append(f"""<table border="1" cellpadding="6" cellspacing="0" width="80%">
<tr><th>{t('duzeltme_faktoru')}</th><th>{t('ham_deger')}</th><th>{t('uygulanan')}</th></tr>
<tr><td>{t('sicaklik_f')}</td><td>{ctx.get('temp_factor_raw','')}</td><td>{ctx.get('temp_factor_applied','')}</td></tr>
<tr><td>{t('basinc_f')}</td><td>{ctx.get('press_factor_raw','')}</td><td>{ctx.get('press_factor_applied','')}</td></tr>
<tr><td>{t('rakim_f')}</td><td>{ctx.get('alt_factor_raw','')}</td><td>{ctx.get('alt_factor_applied','')}</td></tr>
<tr><td>{t('giris_kaybi_f')}</td><td>{ctx.get('inlet_factor_raw','')}</td><td>{ctx.get('inlet_factor_applied','')}</td></tr>
<tr><td>{t('egzoz_kaybi_f')}</td><td>{ctx.get('exh_factor_raw','')}</td><td>{ctx.get('exh_factor_applied','')}</td></tr>
<tr><td>{t('nem_f')}</td><td>{ctx.get('hum_factor_raw','')}</td><td>{ctx.get('hum_factor_applied','')}</td></tr>
<tr><td><b>{t('toplam_guc_faktoru')}</b></td><td colspan="2" align="center"><b>{ctx.get('total_power_factor','')}</b></td></tr>
</table><br/>""")

        parts.append(f"<h3>{t('puanlama_baslik')}</h3>")
        parts.append(f"<p>{cf('turbine_scoring_' + ('en' if en else 'tr'))}</p>")

        parts.append(f"<h3>{t('oneri_turbinler')}</h3>")
        parts.append(f"""<table border="1" cellpadding="6" cellspacing="0" width="100%">
<tr><th>{t('turbin_sira')}</th><th>{t('turbin_ad')}</th><th>{t('turbin_guc')}</th><th>{t('turbin_hr')}</th><th>{t('turbin_verim')}</th><th>{t('turbin_surge')}</th><th>{t('turbin_puan')}</th><th>{t('turbin_oneri')}</th></tr>
{ctx.get('turbine_rows_html','')}
</table><br/>""")

        # -- 10. BELIRSIZLIK --
        parts.append(f"<h2>{t('sec10_title')}</h2>")
        parts.append(f"<p>{cf('uncertainty_formulas_' + ('en' if en else 'tr'))}</p>")
        parts.append(f"""<table border="1" cellpadding="6" cellspacing="0" width="100%">
<tr><th>{t('olcum_parametresi')}</th><th>{t('enstruman_tipi')}</th><th>{t('standart_belirsizlik')}</th></tr>
<tr><td>{t('giris_basinci_s')}</td><td>{ctx.get('p_in_instrument','')}</td><td>±{ctx.get('p_in_uncertainty','')}</td></tr>
<tr><td>{t('cikis_basinci_s')}</td><td>{ctx.get('p_out_instrument','')}</td><td>±{ctx.get('p_out_uncertainty','')}</td></tr>
<tr><td>{t('giris_sicakligi_s')}</td><td>{ctx.get('t_in_instrument','')}</td><td>±{ctx.get('t_in_uncertainty','')}</td></tr>
<tr><td>{t('kutlesel_debi_s')}</td><td>{ctx.get('flow_instrument','')}</td><td>±{ctx.get('flow_uncertainty','')}</td></tr>
</table><br/>""")
        parts.append(f"""<table border="1" cellpadding="6" cellspacing="0" width="60%">
<tr><td>{t('birlesik_belirsizlik')}</td><td>{ctx.get('combined_uncertainty','')}</td></tr>
<tr><td>{t('genisletilmis_belirsizlik')}</td><td>{ctx.get('expanded_uncertainty','')}</td></tr>
<tr><td>{t('sonuc_guven_araligi')}</td><td>{ctx.get('poly_eff_value','')} ± {ctx.get('poly_eff_uncertainty','')}</td></tr>
</table><br/>""")
        parts.append(f"<h4>{t('katki_dagilimi')}</h4>")
        parts.append(ctx.get("uncertainty_breakdown_html", ""))

        # -- 11. STANDART KARSILASTIRMA --
        parts.append(f"<h2>{t('sec11_title')}</h2>")
        parts.append(f"<p>{cf('benchmark_scale_' + ('en' if en else 'tr'))}</p>")
        parts.append(f"""<table border="1" cellpadding="6" cellspacing="0" width="100%">
<tr><th>{t('parametre')}</th><th>{t('tasarim_degeri')}</th><th>{t('endustri_standard')}</th><th>{t('degerlendirme')}</th></tr>
<tr><td>{'Politropik Verim' if not en else 'Polytropic Efficiency'}</td><td>{ctx.get('actual_poly_eff_pct','')}%</td><td>{'API 617: 85–88%+' if not en else 'API 617: 85–88%+'}</td><td>{ctx.get('poly_rating','')}</td></tr>
<tr><td>{'Izentropik Verim' if not en else 'Isentropic Efficiency'}</td><td>{ctx.get('isen_approx','')}%</td><td>{'ISO 2314: 82–85%+' if not en else 'ISO 2314: 82–85%+'}</td><td>{ctx.get('isen_rating','')}</td></tr>
<tr><td>{t('mek_verim')}</td><td>{ctx.get('mech_eff','')}%</td><td>{'API 617: 97.5–99%+' if not en else 'API 617: 97.5–99%+'}</td><td>{ctx.get('mech_rating','')}</td></tr>
<tr><td>{t('sicaklik')}</td><td>{ctx.get('pr_value','')}</td><td>{'API 617: 1.05–4.5' if not en else 'API 617: 1.05–4.5'}</td><td>{ctx.get('pr_rating','')}</td></tr>
<tr><td>{'Guc Marji' if not en else 'Power Margin'}</td><td>{ctx.get('power_margin','')}%</td><td>{'API 617: 5–20%' if not en else 'API 617: 5–20%'}</td><td>{ctx.get('margin_rating','')}</td></tr>
<tr><td>{'Surge Mesafesi' if not en else 'Surge Margin'}</td><td>{ctx.get('surge_margin','')}%</td><td>{'API 617: >10%' if not en else 'API 617: >10%'}</td><td>{ctx.get('surge_rating','')}</td></tr>
</table><br/>""")

        # -- 12. STANDARTLAR --
        parts.append(f"<h2>{t('sec12_title')}</h2>")
        parts.append(f"<p>{cf('standards_refs_' + ('en' if en else 'tr'))}</p>")

        # -- 13. UYARILAR --
        parts.append(f"<h2>{t('sec13_title')}</h2>")
        warnings_html = ctx.get("warnings_html", "")
        parts.append(warnings_html if warnings_html else f"<p>{t('uyari_yok')}</p>")

        # -- 14. DIYAGRAMLAR --
        diagrams_html = ctx.get("diagrams_html", "")
        if diagrams_html:
            parts.append(f"<h2>{t('sec14_title')}</h2>")
            parts.append(diagrams_html)

        return "\n".join(parts)

    # =========================================================================
    # ReportLab PDF Story
    # =========================================================================

    def generate_reportlab_story(self, context: Mapping[str, Any]):
        """ReportLab Platypus story olusturur (PDF icin)."""
        if not REPORTLAB_LOADED:
            raise ImportError("ReportLab kutuphanesi yuklu degil")

        ctx = dict(context)
        ctx.setdefault("app_version", "V4.5")
        ctx.setdefault("report_date", datetime.datetime.now().strftime("%d/%m/%Y %H:%M"))

        styles = getSampleStyleSheet()
        for style_name in styles.byName:
            styles[style_name].fontName = "DejaVuSans"
        title_style = styles["Title"]
        h2_style = styles["Heading2"]
        h3_style = styles["Heading3"]
        normal_style = styles["Normal"]

        en = self._en
        t = self._k

        story = []

        # -- Baslik --
        story.append(Paragraph(self._fill(t("report_title"), ctx), title_style))
        story.append(Paragraph(
            f"<b>{_esc(ctx.get('project_name',''))}</b><br/>"
            f"{t('report_date_label')}: {ctx.get('report_date')}",
            normal_style,
        ))
        story.append(Spacer(1, 10 * mm))

        # -- 1. Proje --
        story.append(Paragraph(t("sec1_title"), h2_style))
        story.append(self._make_table([
            [t("proje_adi"), _esc(ctx.get("project_name","")), ""],
            [t("unite_sayisi"), _esc(str(ctx.get("num_units",""))), ""],
            [t("kademe_sayisi"), _esc(str(ctx.get("num_stages",""))), ""],
            [t("gaz_kompozisyonu"), _esc(str(ctx.get("composition_summary",""))), ""],
            [t("eos_metodu"), _esc(str(ctx.get("eos_method",""))), ""],
            [t("hesaplama_metodu"), _esc(str(ctx.get("method_display",""))), ""],
            [t("ortam_sicakligi"), _esc(str(ctx.get("ambient_temp",""))), "°C"],
            [t("ortam_basinci"), _esc(str(ctx.get("ambient_pressure",""))), "kPa"],
            [t("rakim"), _esc(str(ctx.get("altitude",""))), "m"],
            [t("bagil_nem"), _esc(str(ctx.get("humidity",""))), "%"],
        ], col_widths=[120, 180, 60]))
        story.append(Spacer(1, 8 * mm))

        # -- 2. Proses Kosullari --
        story.append(Paragraph(t("sec2_title"), h2_style))
        story.append(self._make_table([
            [t("parametre"), t("giris"), t("cikis"), t("birim")],
            [t("basinc"), _esc(str(ctx.get("p_in",""))), _esc(str(ctx.get("p_out",""))), _esc(str(ctx.get("p_in_unit","")))],
            [t("sicaklik"), _esc(str(ctx.get("t_in",""))), _esc(str(ctx.get("t_out",""))), _esc(str(ctx.get("t_in_unit",""))) + " / °C"],
            ["Sikistirma Orani" if not en else "Compression Ratio", "—", _esc(str(ctx.get("compression_ratio",""))), "—"],
            [t("pol_verim"), _esc(str(ctx.get("design_poly_eff",""))) + "%", _esc(str(ctx.get("actual_poly_eff",""))) + "%", "%"],
            [t("isil_verim"), _esc(str(ctx.get("therm_eff",""))) + "%", "—", "%"],
            [t("mek_verim"), _esc(str(ctx.get("mech_eff",""))) + "%", "—", "%"],
        ], col_widths=[100, 80, 80, 60], header=True))
        story.append(Spacer(1, 8 * mm))

        # -- 4. EOS Formulleri --
        story.append(Paragraph(t("sec4_title"), h2_style))
        story.append(Paragraph(self._c.get("eos_formulas_en" if en else "eos_formulas_tr", ""), normal_style))
        story.append(Spacer(1, 8 * mm))

        # -- 5. Sikistirma Formulleri --
        story.append(Paragraph(t("sec5_title"), h2_style))
        story.append(Paragraph(self._c.get("polytropic_formulas_en" if en else "polytropic_formulas_tr", ""), normal_style))
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph(self._c.get("isentropic_solvers_en" if en else "isentropic_solvers_tr", ""), normal_style))
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph(self._c.get("api617_integral_en" if en else "api617_integral_tr", ""), normal_style))
        story.append(Spacer(1, 8 * mm))

        # -- 6. Guc Formulleri --
        story.append(Paragraph(t("sec6_title"), h2_style))
        story.append(Paragraph(self._c.get("power_formulas_en" if en else "power_formulas_tr", ""), normal_style))
        story.append(Spacer(1, 8 * mm))

        # -- 7. Yakit Formulleri --
        story.append(Paragraph(t("sec7_title"), h2_style))
        story.append(Paragraph(self._c.get("fuel_formulas_en" if en else "fuel_formulas_tr", ""), normal_style))
        story.append(Spacer(1, 8 * mm))

        # -- 9. Turbin Puanlama --
        story.append(Paragraph(t("sec9_title"), h2_style))
        story.append(Paragraph(self._c.get("turbine_scoring_en" if en else "turbine_scoring_tr", ""), normal_style))
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph(self._c.get("site_corrections_en" if en else "site_corrections_tr", ""), normal_style))
        story.append(Spacer(1, 8 * mm))

        # -- 10. Belirsizlik --
        story.append(Paragraph(t("sec10_title"), h2_style))
        story.append(Paragraph(self._c.get("uncertainty_formulas_en" if en else "uncertainty_formulas_tr", ""), normal_style))
        story.append(Spacer(1, 8 * mm))

        # -- 12. Standart Referanslar --
        story.append(Paragraph(t("sec12_title"), h2_style))
        story.append(Paragraph(self._fill(
            self._c.get("standards_refs_en" if en else "standards_refs_tr", ""), ctx
        ), normal_style))
        story.append(Spacer(1, 8 * mm))

        # -- 13. Uyarilar --
        warnings_html = ctx.get("warnings_html", "")
        story.append(Paragraph(t("sec13_title"), h2_style))
        if warnings_html:
            story.append(Paragraph(warnings_html, normal_style))
        else:
            story.append(Paragraph(t("uyari_yok"), normal_style))

        return story

    # =========================================================================
    # Yardimcilar
    # =========================================================================

    @staticmethod
    def _make_table(data, col_widths=None, header=True):
        """ReportLab Table yardimcisi."""
        tbl = Table(data, colWidths=col_widths)
        style_cmds = [
            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
        ]
        if header:
            style_cmds += [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ]
        tbl.setStyle(TableStyle(style_cmds))
        return tbl


# =============================================================================
# Yardimci Fonksiyonlar
# =============================================================================

def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.4g}"
    return escape(str(value))


def _esc(value: Any) -> str:
    if value is None:
        return ""
    return escape(str(value))


# =============================================================================
# Kullanim: build_context fonksiyonu — hesaplama sonuclarindan template context'i olusturur
# =============================================================================

def build_design_report_context(inputs: Mapping[str, Any], results: Mapping[str, Any]) -> dict:
    """
    `calculate_design_performance()` sonuclarindan sablon context'i olusturur.

    Rapor sablonunun bekledigi tum `{{...}}` yer tutucularini doldurmak icin
    gerekli anahtar-deger ciftlerini hesaplar.
    """
    from kasp.core.constants import SUPPORTED_GASES, MOLAR_MASSES

    ctx = {}

    # --- Temel Bilgiler ---
    ctx["project_name"] = inputs.get("project_name", "")
    ctx["num_units"] = int(inputs.get("num_units", 1))
    ctx["num_stages"] = int(inputs.get("num_stages", 1))
    ctx["eos_method"] = inputs.get("eos_method", "coolprop")
    ctx["method"] = inputs.get("method", "Metot 1: Ortalama Ozellikler")
    ctx["method_key"] = _resolve_method_key(ctx["method"])
    ctx["ambient_temp"] = float(inputs.get("ambient_temp", 15.0))
    ctx["ambient_pressure"] = float(inputs.get("ambient_pressure", 101.325))
    ctx["altitude"] = int(inputs.get("altitude", 0))
    ctx["humidity"] = float(inputs.get("humidity", 60.0))
    ctx["lhv_source"] = inputs.get("lhv_source", "kasp")

    # --- Proses Kosullari ---
    ctx["p_in"] = str(inputs.get("p_in", ""))
    ctx["p_in_unit"] = inputs.get("p_in_unit", "bar(a)")
    ctx["t_in"] = str(inputs.get("t_in", ""))
    ctx["t_in_unit"] = inputs.get("t_in_unit", "°C")
    ctx["p_out"] = str(inputs.get("p_out", ""))
    ctx["p_out_unit"] = inputs.get("p_out_unit", "bar(a)")
    ctx["design_poly_eff"] = f"{float(inputs.get('poly_eff', 85.0)):.1f}"
    ctx["therm_eff"] = f"{float(inputs.get('therm_eff', 35.0)):.1f}"
    ctx["mech_eff"] = f"{float(inputs.get('mech_eff', 98.0)):.1f}"

    # --- Sonuclar ---
    t_out_c = float(results.get("t_out", 0))
    ctx["t_out"] = f"{t_out_c:.1f}"
    ctx["t_out_unit"] = "°C"
    ctx["compression_ratio"] = f"{float(results.get('compression_ratio', 0)):.2f}"
    ctx["actual_poly_eff"] = f"{float(results.get('actual_poly_efficiency', 0)) * 100:.2f}"
    ctx["actual_poly_eff_pct"] = ctx["actual_poly_eff"]
    ctx["calculated_head"] = f"{float(results.get('head_kj_kg', 0)):.2f}"

    # -- Guc --
    ctx["mass_flow_per_unit"] = f"{float(results.get('mass_flow_per_unit_kgs', 0)):.3f}"
    ctx["mass_flow_total"] = f"{float(results.get('mass_flow_total_kgs', 0)):.3f}"
    ctx["inlet_acmh_per_unit"] = f"{float(results.get('inlet_vol_flow_acmh_per_unit', 0)):.0f}"
    ctx["pg_per_unit"] = f"{float(results.get('power_gas_per_unit_kw', 0)):.0f}"
    ctx["pg_total"] = f"{float(results.get('power_gas_total_kw', 0)):.0f}"
    ctx["ml_per_unit"] = f"{float(results.get('mech_loss_per_unit_kw', 0)):.0f}"
    ctx["ml_total"] = f"{float(results.get('mech_loss_total_kw', 0)):.0f}"
    ctx["ps_per_unit"] = f"{float(results.get('power_shaft_per_unit_kw', 0)):.0f}"
    ctx["ps_total"] = f"{float(results.get('power_shaft_total_kw', 0)):.0f}"
    ctx["pm_per_unit"] = f"{float(results.get('power_motor_per_unit_kw', 0)):.0f}"
    ctx["pm_total"] = f"{float(results.get('power_motor_per_unit_kw', 0)) * int(inputs.get('num_units', 1)):.0f}"
    ctx["pu_per_unit"] = f"{float(results.get('power_unit_kw', 0)):.0f}"
    ctx["pu_total"] = f"{float(results.get('power_unit_total_kw', 0)):.0f}"

    # -- Yakit --
    ctx["calculated_lhv"] = f"{float(results.get('lhv', 0)):.0f}"
    ctx["calculated_hhv"] = f"{float(results.get('hhv', 0)):.0f}"
    ctx["fuel_unit_kgh"] = f"{float(results.get('fuel_unit_kgh', 0)):.1f}"
    ctx["fuel_total_kgh"] = f"{float(results.get('fuel_total_kgh', 0)):.1f}"
    ctx["heat_rate"] = f"{float(results.get('heat_rate', 0)):.0f}"
    hr_value = float(results.get("heat_rate", 0))
    ctx["heat_rate_eff_pct"] = f"{3600.0 / hr_value * 100:.1f}" if hr_value > 0 else "0.0"
    ctx["fuel_thermal_kw"] = f"{float(results.get('fuel_unit_kgh',0)) * float(results.get('lhv',0)) / 3600:.0f}"

    # -- Termodinamik Ozellikler --
    inlet_props = results.get("inlet_properties", {})
    outlet_props = results.get("outlet_properties", {})

    ctx["z_in"] = f"{float(inlet_props.get('Z', 1.0)):.4f}"
    ctx["z_out"] = f"{float(outlet_props.get('Z', 1.0)):.4f}"
    ctx["k_in"] = f"{float(inlet_props.get('k', 1.4)):.3f}"
    ctx["k_out"] = f"{float(outlet_props.get('k', 1.4)):.3f}"
    ctx["cp_in"] = f"{float(inlet_props.get('Cp', 0)) / 1000:.3f}"
    ctx["cp_out"] = f"{float(outlet_props.get('Cp', 0)) / 1000:.3f}"
    ctx["cv_in"] = f"{float(inlet_props.get('Cv', 0)) / 1000:.3f}"
    ctx["cv_out"] = f"{float(outlet_props.get('Cv', 0)) / 1000:.3f}"
    ctx["rho_in"] = f"{float(inlet_props.get('rho', 0)):.3f}"
    ctx["rho_out"] = f"{float(outlet_props.get('rho', 0)):.3f}"
    ctx["h_in"] = f"{float(inlet_props.get('H', 0)):.1f}"
    ctx["h_out"] = f"{float(outlet_props.get('H', 0)):.1f}"
    delta_h_j_kg = float(outlet_props.get("H", 0)) - float(inlet_props.get("H", 0))
    ctx["delta_h"] = f"{(delta_h_j_kg / 1000):.2f} kJ/kg"
    ctx["s_in"] = f"{float(inlet_props.get('S', 0)):.3f}"
    ctx["s_out"] = f"{float(outlet_props.get('S', 0)):.3f}"
    ctx["mu_in"] = f"{float(inlet_props.get('mu', 0)) * 1e6:.2f}"
    ctx["mu_out"] = f"{float(outlet_props.get('mu', 0)) * 1e6:.2f}"
    ctx["a_in"] = f"{float(inlet_props.get('a', 0)):.1f}"
    ctx["a_out"] = f"{float(outlet_props.get('a', 0)):.1f}"

    # Degisim yuzdeleri
    def _pct_change(key, v_in, v_out):
        try:
            vi = float(v_in)
            vo = float(v_out)
            if vi != 0:
                ctx[key] = f"{((vo - vi) / vi * 100):+.1f}"
            else:
                ctx[key] = "—"
        except (ValueError, TypeError):
            ctx[key] = "—"

    _pct_change("z_change_pct", ctx["z_in"], ctx["z_out"])
    _pct_change("k_change_pct", ctx["k_in"], ctx["k_out"])
    cp_in_val = float(inlet_props.get("Cp", 0))
    cp_out_val = float(outlet_props.get("Cp", 0))
    _pct_change("cp_change_pct", str(cp_in_val), str(cp_out_val))
    _pct_change("cv_change_pct", str(float(inlet_props.get("Cv", 0))), str(float(outlet_props.get("Cv", 0))))
    _pct_change("rho_change_pct", ctx["rho_in"], ctx["rho_out"])

    # -- Gaz Kompozisyonu (HTML tablosu) --
    gas_comp = inputs.get("gas_comp", {})
    comp_rows = ""
    for comp, frac in sorted(gas_comp.items()):
        if float(frac) <= 0.01:
            continue
        mw = MOLAR_MASSES.get(comp.upper(), 0)
        comp_rows += f"<tr><td>{comp}</td><td>{frac:.2f}</td><td>{mw:.3f}</td></tr>\n"
    total_mw = sum(
        MOLAR_MASSES.get(c.upper(), 0) * float(f) / 100.0
        for c, f in gas_comp.items()
    )
    ctx["mixture_mw"] = f"{total_mw:.3f}"

    comp_table_html = f"""<table border="1" cellpadding="4" cellspacing="0" width="80%">
<tr><th>{'Bilesen' if not is_english() else 'Component'}</th><th>{'Mol %' if not is_english() else 'Mol %'}</th><th>{'Molar Kutle (g/mol)' if not is_english() else 'Molar Mass (g/mol)'}</th></tr>
{comp_rows}
</table>"""
    ctx["composition_table_html"] = comp_table_html

    comp_names = ", ".join(f"{c}: {f:.1f}%" for c, f in sorted(gas_comp.items()) if float(f) > 0.01)
    ctx["composition_summary"] = comp_names or ("Karışım" if not is_english() else "Mixture")
    ctx["fuel_composition_summary"] = comp_names

    # -- Kademeler (HTML satirlari) --
    staged_results = results.get("stages", [])
    stage_rows = ""
    for stage in staged_results:
        p_in_bar = float(stage.get("p_in", 0)) / 1e5
        t_in_c = float(stage.get("t_in", 273.15)) - 273.15
        p_out_bar = float(stage.get("p_out", 0)) / 1e5
        t_out_c = float(stage.get("t_out", 273.15)) - 273.15
        head = float(stage.get("head_kj_kg", 0))
        poly_eff = float(stage.get("poly_eff_design", 0))
        dh = float(stage.get("delta_h_kj_kg", 0))
        z_avg = float(stage.get("z_avg", 0))
        power = float(stage.get("power_gas_kw", 0))
        stage_rows += (
            f"<tr><td>{stage.get('stage','')}</td><td>{p_in_bar:.2f}</td><td>{t_in_c:.1f}</td>"
            f"<td>{p_out_bar:.2f}</td><td>{t_out_c:.1f}</td><td>{head:.2f}</td>"
            f"<td>{poly_eff:.4f}</td><td>{dh:.2f}</td><td>{z_avg:.4f}</td><td>{power:.1f}</td></tr>\n"
        )
    ctx["stage_rows_html"] = stage_rows
    total_poly_head = sum(float(s.get("head_kj_kg", 0)) for s in staged_results)
    total_gas_power = sum(float(s.get("power_gas_kw", 0)) for s in staged_results)
    ctx["total_poly_head"] = f"{total_poly_head:.2f}"
    ctx["total_stage_gas_power"] = f"{total_gas_power:.1f}"
    ctx["intercooler_dp_pct"] = str(inputs.get("intercooler_dp_pct", 2.0))
    ctx["intercooler_t"] = str(inputs.get("intercooler_t", 40.0))

    # -- Belirsizlik (ASME PTC 10) --
    uncertainty = results.get("uncertainty") or {}
    poly_unc = uncertainty.get("polytropic_efficiency", {})
    ctx["combined_uncertainty"] = f"{float(poly_unc.get('combined_uncertainty', 0)):.4f}"
    ctx["expanded_uncertainty"] = f"{float(poly_unc.get('expanded_uncertainty', 0)):.4f}"
    ctx["poly_eff_value"] = f"{float(poly_unc.get('value', 0)):.4f}"
    ctx["poly_eff_uncertainty"] = f"±{float(poly_unc.get('expanded_uncertainty', 0)):.4f}"

    # Enstruman bilgileri
    ctx["p_in_uncertainty"] = "0.0025 (of reading)"
    ctx["p_out_uncertainty"] = "0.0025 (of reading)"
    ctx["t_in_uncertainty"] = "0.15°C"
    ctx["flow_uncertainty"] = "0.001 (of reading)"
    ctx["p_in_instrument"] = "Pressure Transducer (±0.25% FS)"
    ctx["p_out_instrument"] = "Pressure Transducer (±0.25% FS)"
    ctx["t_in_instrument"] = "RTD Pt100 Class A (±0.15°C)"
    ctx["flow_instrument"] = "Coriolis Meter (±0.1% rate)"

    breakdown = poly_unc.get("breakdown", {})
    if breakdown:
        rows = ""
        for param, contrib in sorted(breakdown.items(), key=lambda x: -abs(x[1])):
            rows += f"<tr><td>{param}</td><td>{contrib:.1f}%</td></tr>\n"
        ctx["uncertainty_breakdown_html"] = (
            '<table border="1" cellpadding="4" cellspacing="0" width="50%">'
            f'<tr><th>{"Parametre" if not is_english() else "Parameter"}</th><th>%</th></tr>{rows}</table>'
        )
    else:
        ctx["uncertainty_breakdown_html"] = "—"

    # -- Warnings --
    warnings = results.get("warnings") or []
    if warnings:
        w_html = "".join(f"&bull; {escape(w)}<br/>" for w in warnings)
        ctx["warnings_html"] = w_html
    else:
        ctx["warnings_html"] = ""

    # -- Benchmark ratings --
    actual_poly = float(results.get("actual_poly_efficiency", 0)) * 100
    isen_approx = actual_poly * 0.96
    ctx["isen_approx"] = f"{isen_approx:.2f}"
    ctx["pr_value"] = ctx["compression_ratio"]
    ctx["power_margin"] = "—"
    ctx["surge_margin"] = "—"
    ctx["poly_rating"] = _benchmark_rating(actual_poly, "polytropic_eff")
    ctx["isen_rating"] = _benchmark_rating(isen_approx, "isentropic_eff")
    mech = float(inputs.get("mech_eff", 98.0))
    ctx["mech_rating"] = _benchmark_rating(mech, "mechanical_eff")
    ctx["pr_rating"] = "In Range" if 1.05 <= float(results.get("compression_ratio", 0)) <= 4.5 else "Out of Range"
    ctx["margin_rating"] = "—"
    ctx["surge_rating"] = "—"

    return ctx


def _resolve_method_key(method_label: str) -> str:
    ml = method_label.lower()
    if "metot 2" in ml or "endpoint" in ml or "uc nokta" in ml:
        return "endpoint"
    if "metot 3" in ml or "artimli" in ml or "incremental" in ml:
        return "incremental"
    if "metot 4" in ml or "h-s" in ml or "dogrudan" in ml or "direct" in ml:
        return "direct_hs"
    return "average"


def _benchmark_rating(value: float, param_type: str) -> str:
    if param_type == "polytropic_eff":
        if value >= 88.0:
            return "Excellent (" + (u"Mükemmel" if not is_english() else "Excellent") + ")"
        elif value >= 85.0:
            return "Good (" + (u"İyi" if not is_english() else "Good") + ")"
        elif value >= 80.0:
            return "Fair (" + (u"Orta" if not is_english() else "Fair") + ")"
        else:
            return "Below Standard (" + (u"Standart Altı" if not is_english() else "Below Std.") + ")"
    elif param_type == "isentropic_eff":
        if value >= 85.0:
            return "Excellent (" + (u"Mükemmel" if not is_english() else "Excellent") + ")"
        elif value >= 82.0:
            return "Good (" + (u"İyi" if not is_english() else "Good") + ")"
        elif value >= 78.0:
            return "Fair (" + (u"Orta" if not is_english() else "Fair") + ")"
        else:
            return "Below Standard (" + (u"Standart Altı" if not is_english() else "Below Std.") + ")"
    elif param_type == "mechanical_eff":
        if value >= 99.0:
            return "Excellent (" + (u"Mükemmel" if not is_english() else "Excellent") + ")"
        elif value >= 97.5:
            return "Good (" + (u"İyi" if not is_english() else "Good") + ")"
        elif value >= 95.0:
            return "Fair (" + (u"Orta" if not is_english() else "Fair") + ")"
        else:
            return "Below Standard (" + (u"Standart Altı" if not is_english() else "Below Std.") + ")"
    return "N/A"
