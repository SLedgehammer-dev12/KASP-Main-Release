from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
)
import json

from kasp.utils.updater import (
    build_release_notes_html,
    format_bytes,
    is_newer_release,
    pick_default_asset,
)


class CompressorEditDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Kompresor Ekle/Duzenle")
        from kasp.ui.responsive import dialog_size
        self.resize(*dialog_size(0.35, 0.45))
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.manufacturer_edit = QLineEdit()
        self.model_edit = QLineEdit()

        self.max_pr_spin = QDoubleSpinBox()
        self.max_pr_spin.setRange(1.0, 100.0)
        self.max_pr_spin.setValue(3.5)
        self.max_pr_spin.setSingleStep(0.1)

        self.min_flow_spin = QDoubleSpinBox()
        self.min_flow_spin.setRange(0, 1000000)
        self.min_flow_spin.setValue(1000)

        self.max_flow_spin = QDoubleSpinBox()
        self.max_flow_spin.setRange(0, 10000000)
        self.max_flow_spin.setValue(50000)

        self.map_data_edit = QTextEdit()
        self.map_data_edit.setPlaceholderText('{"curve1": [[flow, head, eff], ...]}')

        form_layout.addRow("Uretici:", self.manufacturer_edit)
        form_layout.addRow("Model:", self.model_edit)
        form_layout.addRow("Maks. Basincl Orani:", self.max_pr_spin)
        form_layout.addRow("Min. Akis (kg/h):", self.min_flow_spin)
        form_layout.addRow("Maks. Akis (kg/h):", self.max_flow_spin)
        form_layout.addRow("Performans Haritasi (JSON):", self.map_data_edit)

        layout.addLayout(form_layout)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def get_compressor_data(self):
        try:
            map_data_str = self.map_data_edit.toPlainText()
            map_data = json.loads(map_data_str) if map_data_str.strip() else {}
        except json.JSONDecodeError:
            map_data = {}

        return {
            "manufacturer": self.manufacturer_edit.text(),
            "model": self.model_edit.text(),
            "max_pressure_ratio": self.max_pr_spin.value(),
            "min_flow_kgs": self.min_flow_spin.value(),
            "max_flow_kgs": self.max_flow_spin.value(),
            "performance_map_data": map_data,
        }


class TurbineDetailDialog(QDialog):
    def __init__(self, turbine_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Turbin Detaylari - {turbine_data.get('model', 'Bilinmeyen')}")
        from kasp.ui.responsive import dialog_size
        self.resize(*dialog_size(0.40, 0.35))
        self.turbine_data = turbine_data
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        fields = [
            ("Uretici", "manufacturer"),
            ("Model", "model"),
            ("Tip", "type"),
            ("ISO Guc (kW)", "iso_power_kw"),
            ("ISO Isi Orani (kJ/kWh)", "iso_heat_rate_kj_kwh"),
            ("Surge Flow", "surge_flow"),
            ("Stonewall Flow", "stonewall_flow"),
            ("Maks. Basinc Orani", "max_pressure_ratio"),
            ("Yakit Tipi", "fuel_type"),
        ]

        for label, key in fields:
            value = self.turbine_data.get(key, "-")
            field = QLabel(str(value))
            field.setTextInteractionFlags(Qt.TextSelectableByMouse)
            form_layout.addRow(f"{label}:", field)

        layout.addLayout(form_layout)

        layout.addWidget(QLabel("Duzeltme Faktorleri (JSON):"))
        corr_text = QTextEdit()
        corr_text.setReadOnly(True)
        corr_data = self.turbine_data.get("performance_correction_data", {})
        if isinstance(corr_data, str):
            corr_text.setText(corr_data)
        else:
            corr_text.setText(json.dumps(corr_data, indent=2))
        layout.addWidget(corr_text)

        button_box = QDialogButtonBox(QDialogButtonBox.Close)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)


class TurbineEditDialog(QDialog):
    """Placeholder for future implementation."""


class ChangelogDialog(QDialog):
    """Release notes dialog backed by release metadata."""

    def __init__(self, releases=None, current_release_tag="", parent=None):
        if parent is None and releases is not None and not isinstance(releases, (list, tuple)):
            parent = releases
            releases = None
        super().__init__(parent)
        self.releases = list(releases or [])
        self.current_release_tag = current_release_tag
        self.setWindowTitle("KASP Surum Notlari")
        from kasp.ui.responsive import dialog_size
        self.resize(*dialog_size(0.50, 0.38))
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        notes_text = QTextBrowser()
        notes_text.setOpenExternalLinks(True)
        notes_text.setHtml(
            build_release_notes_html(
                self.releases,
                self.current_release_tag,
                heading="KASP Surum Notlari",
            )
        )
        layout.addWidget(notes_text)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok)
        button_box.accepted.connect(self.accept)
        layout.addWidget(button_box)


class UpdateDialog(QDialog):
    def __init__(self, releases, current_release_tag, parent=None):
        super().__init__(parent)
        self.releases = releases
        self.current_release_tag = current_release_tag
        self.selected_release = None
        self.selected_asset = None
        self.setWindowTitle("KASP Guncelleme Merkezi")
        from kasp.ui.responsive import dialog_size
        self.resize(*dialog_size(0.50, 0.38))
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        header = QLabel(
            f"<h3>KASP Guncellemeleri</h3>"
            f"<p>Yuklu surum: <b>{self.current_release_tag}</b></p>"
        )
        header.setTextFormat(Qt.RichText)
        layout.addWidget(header)

        form = QFormLayout()
        self.release_combo = QComboBox()
        for release in self.releases:
            self.release_combo.addItem(f"{release.tag_name} - {release.display_name}", release)
        self.release_combo.currentIndexChanged.connect(self._update_release_details)

        self.asset_combo = QComboBox()
        self.status_label = QLabel("-")
        self.published_label = QLabel("-")
        self.url_label = QLabel("-")
        self.url_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        form.addRow("Release:", self.release_combo)
        form.addRow("Dosya:", self.asset_combo)
        form.addRow("Durum:", self.status_label)
        form.addRow("Yayin Tarihi:", self.published_label)
        form.addRow("Baglanti:", self.url_label)
        layout.addLayout(form)

        layout.addWidget(QLabel("Release Notlari:"))
        self.notes_text = QTextEdit()
        self.notes_text.setReadOnly(True)
        layout.addWidget(self.notes_text)

        buttons = QHBoxLayout()
        self.download_button = QDialogButtonBox()
        self.download_button.setStandardButtons(QDialogButtonBox.Close)
        self.install_button = self.download_button.addButton(
            "Secili Surumu Indir...",
            QDialogButtonBox.AcceptRole,
        )
        self.install_button.clicked.connect(self._accept_download)
        self.download_button.rejected.connect(self.reject)
        buttons.addWidget(self.download_button)
        layout.addLayout(buttons)

        if self.releases:
            self.release_combo.setCurrentIndex(0)
            self._update_release_details()
        else:
            self.install_button.setEnabled(False)
            self.notes_text.setPlainText("Release bilgisi bulunamadi.")

    def _update_release_details(self):
        release = self.release_combo.currentData()
        if release is None:
            self.asset_combo.clear()
            self.install_button.setEnabled(False)
            self.notes_text.clear()
            return

        self.selected_release = release
        if release.tag_name == self.current_release_tag:
            status = "Kurulu surum"
        elif is_newer_release(release.tag_name, self.current_release_tag):
            status = "Yeni surum mevcut"
        else:
            status = "Daha eski surum"

        self.status_label.setText(status)
        self.published_label.setText(release.published_at or "-")
        self.url_label.setText(release.html_url or "-")
        self.notes_text.setPlainText(release.body or "Release notu bulunmuyor.")

        self.asset_combo.clear()
        for asset in release.assets:
            label = f"{asset.name} ({format_bytes(asset.size)})"
            self.asset_combo.addItem(label, asset)

        default_asset = pick_default_asset(release)
        if default_asset is not None:
            for index in range(self.asset_combo.count()):
                asset = self.asset_combo.itemData(index)
                if asset == default_asset:
                    self.asset_combo.setCurrentIndex(index)
                    break

        self.install_button.setEnabled(self.asset_combo.count() > 0)

    def _accept_download(self):
        self.selected_release = self.release_combo.currentData()
        self.selected_asset = self.asset_combo.currentData()
        if self.selected_release is None or self.selected_asset is None:
            return
        self.accept()


class ThermodynamicsHandbookDialog(QDialog):
    """Bilingual (TR/EN) Thermodynamics Handbook explaining EoS and sizing path integrations."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📘 KASP Termodinamik Kılavuzu & El Kitabı (Thermodynamics Handbook)")
        from kasp.ui.responsive import dialog_size
        self.resize(*dialog_size(0.65, 0.75))
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(True)

        from kasp.ui.theme_manager import ThemeManager
        try:
            from kasp.config_manager import get_config_manager
            theme_name = get_config_manager().get("app.theme", "dark")
        except Exception:
            theme_name = "dark"
        t = ThemeManager.THEMES.get(theme_name, ThemeManager.THEMES["dark"])

        html_content = f"""
        <html>
        <head>
        <style>
            body {{
                background-color: {t['background']};
                color: {t['text']};
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 14px;
                line-height: 1.6;
                margin: 20px;
            }}
            h1 {{
                color: {t['primary']};
                border-bottom: 2px solid {t['border']};
                padding-bottom: 8px;
                font-size: 22px;
            }}
            h2 {{
                color: {t['danger']};
                margin-top: 25px;
                font-size: 18px;
            }}
            h3 {{
                color: {t['primary']};
                font-size: 15px;
            }}
            p {{
                margin-bottom: 15px;
            }}
            ul, ol {{
                margin-left: 20px;
                margin-bottom: 15px;
            }}
            li {{
                margin-bottom: 5px;
            }}
            code {{
                background-color: {t['surface']};
                padding: 2px 5px;
                border-radius: 4px;
                font-family: 'Consolas', monospace;
                color: {t['warning']};
            }}
            pre {{
                background-color: {t['surface']};
                padding: 12px;
                border-radius: 6px;
                border: 1px solid {t['border']};
                overflow-x: auto;
                font-family: 'Consolas', monospace;
                color: {t['text']};
            }}
            .info-box {{
                background-color: {t['surface']};
                border-left: 4px solid {t['primary']};
                padding: 12px;
                border-radius: 4px;
                margin: 15px 0;
            }}
            .warning-box {{
                background-color: {t['surface']};
                border-left: 4px solid {t['warning']};
                padding: 12px;
                border-radius: 4px;
                margin: 15px 0;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin: 15px 0;
            }}
            th, td {{
                border: 1px solid {t['border']};
                padding: 8px 12px;
                text-align: left;
            }}
            th {{
                background-color: {t['surface']};
                color: {t['primary']};
            }}
            tr:nth-child(even) {{
                background-color: {t['surface']};
            }}
            .lang-section {{
                margin-bottom: 40px;
            }}
            .divider {{
                border-top: 2px dashed {t['border']};
                margin: 40px 0;
            }}
        </style>
        </head>
        <body>

        <!-- ================= TURKISH SECTION ================= -->
        <div class="lang-section">
            <h1>🇹🇷 KASP Termodinamik Kılavuzu & El Kitabı</h1>
            <p>KASP uygulaması, kompresör tasarım hesaplamalarını en yüksek bilimsel ve endüstriyel hassasiyetle (ASME PTC 10, API 617) çözmek üzere tasarlanmıştır. Bu kılavuz, arka planda koşan karmaşık termodinamik ve aerodinamik adımları anlaşılır hale getirmek ve doğru işletme şartlarında en uygun durum denklemini (EoS) seçmenizi sağlamak için hazırlanmıştır.</p>

            <div class="info-box">
                <b>💡 Altın Kural:</b> Kompresör hesaplama zinciri iki bağımsız seviyede çalışır:
                <ol>
                    <li><b>Durum-Seviyesi Çözücü (State EoS Solver):</b> Tekil noktalarda (P, T) termodinamik özelliklerin (Z, ρ, H, S, Cp, Cv, a, μ) çözülmesi.</li>
                    <li><b>Yol-Seviyesi Sıkıştırma Yordamı (Compression Path Method):</b> Emişten basma basıncına kadar politropik eğrinin (∫ V dP) integre edilmesi.</li>
                </ol>
            </div>

            <h2>1. Durum-Seviyesi EoS Çözücüler (State Model)</h2>
            <p>Bu seviye, gazın belirli bir basınç (P) ve sıcaklıkta (T) yoğunluk, sıkıştırılabilirlik faktörü (Z), entalpi (H), entropi (S) gibi tüm fiziksel özelliklerini belirleyen termodinamik teorileri barındırır. Kübik hal denklemleri, matematiksel olarak birer <b>kök bulma (root solving)</b> problemidir:</p>
            <pre>Z³ - (1-B)Z² + (A - 3B² - 2B)Z - (AB - B² - B³) = 0</pre>
            <p>Bu 3. dereceden kübik polinom çözüldüğünde en fazla 3 gerçel kök çıkabilir. EoS Çözücü, Gibbs serbest enerjisi minimizasyonuna göre gaz fazına ait en büyük gerçel kökü veya sıvı fazına ait en küçük gerçel kökü seçen sayısal bir algoritmadır.</p>

            <h3>Desteklenen Durum Modelleri (EoS):</h3>
            <table>
                <tr>
                    <th style="width: 25%;">Model (EoS)</th>
                    <th>Açıklama ve Kullanım Alanı</th>
                </tr>
                <tr>
                    <td><b>CoolProp (HEOS)</b></td>
                    <td>Yüksek hassasiyetli endüstri standardı termodinamik kütüphane (GERG-2008 / Helmholtz). Saf akışkanlar ve az bileşenli kuru gaz karışımları için referans kabul edilir.</td>
                </tr>
                <tr>
                    <td><b>🇳🇴 Equinor NeqSim (SRK-CPA)</b></td>
                    <td>Equinor'un açık kaynaklı endüstriyel termodinamik motoru. C1–C6+ zengin doğal gaz, polar bileşenler (su, glikol, metanol) ve asit gazlarında (H₂S, CO₂ > %5) üstün faz dengesi kararlılığı sağlar.</td>
                </tr>
                <tr>
                    <td><b>🌊 SINTEF thermopack</b></td>
                    <td>SINTEF Energy Research tarafından geliştirilen C++ tabanlı ultra hızlı ve faz ayrışması sınırlarında son derece kararlı endüstriyel kübik EoS çözücüsü (~4 ms).</td>
                </tr>
                <tr>
                    <td><b>🇧🇷 Petrobras ccp</b></td>
                    <td>ASME PTC 10 ve API 617 standartlarında test edilmiş, Petrobras'ın doğrulanmış santrifüj kompresör performans hesaplama motoru.</td>
                </tr>
                <tr>
                    <td><b>Peng-Robinson / SRK</b></td>
                    <td>Geleneksel kübik hal denklemleri. Petrol ve doğal gaz endüstrisinde hidrokarbon karışımları için en yaygın kullanılan kararlı standart modellerdir.</td>
                </tr>
                <tr>
                    <td><b>AGA8-DC92 (GERG-88)</b></td>
                    <td>Doğal gaz boru hattı taşımacılığı ve mali sayaçlama için geliştirilmiş, Z-faktörü ve yoğunluk odaklı uluslararası standart (ISO 12213-2).</td>
                </tr>
                <tr>
                    <td><b>🇩🇪 DWSIM Thermodynamics</b></td>
                    <td>.NET tabanlı DWSIM süreç simülatörü termodinamik kütüphanesi. Buhar tabloları ve özel kimyasal karışımlarda geniş bileşen desteği sunar.</td>
                </tr>
            </table>

            <h2>2. Mühendislik Karar Matrisi: Hangi Şartta Hangi EoS Seçilmeli?</h2>
            <p>Termodinamik model seçimi, işlenen gazın kompozisyonuna, polarite durumuna ve hesaplama hızı ihtiyacına göre yapılmalıdır:</p>
            <table>
                <tr>
                    <th style="width: 22%;">Akışkan / Proses Tipi</th>
                    <th style="width: 22%;">Önerilen 1. EoS</th>
                    <th style="width: 20%;">2. Tercih (Fallback)</th>
                    <th style="width: 14%;">Hız / Kararlılık</th>
                    <th style="width: 22%;">Mühendislik Gerekçesi</th>
                </tr>
                <tr>
                    <td><b>Boru Hattı Satış Gazı</b><br>(CH₄ > %90, Kuru)</td>
                    <td><b>AGA8-DC92</b> veya<br><b>SINTEF thermopack</b></td>
                    <td>CoolProp (GERG-2008)</td>
                    <td>Çok Hızlı<br>(~4 ms)</td>
                    <td>Yoğunluk ve Z-faktörü ISO 12213 hassasiyetinde çözülür. Kompresör entalpi yolu için Thermopack süper hızlıdır.</td>
                </tr>
                <tr>
                    <td><b>Zengin Gaz / C1–C6+ Ağır Fraksiyonlar</b> (NGL, Kondensat)</td>
                    <td><b>SINTEF thermopack</b> veya<br><b>Peng-Robinson (PR)</b></td>
                    <td>Equinor NeqSim (CPA)</td>
                    <td>Çok Hızlı & Yüksek Kararlılık</td>
                    <td>Kübik EoS modelleri hidrokarbon VLE dengesini ve kritik nokta yakınsamalarını en kararlı çözen modellerdir. CoolProp çok bileşende yavaş kalabilir.</td>
                </tr>
                <tr>
                    <td><b>Islak / Polar / Asit Gazları</b><br>(H₂O, Glikol, H₂S, CO₂ > %5)</td>
                    <td><b>Equinor NeqSim (SRK-CPA)</b></td>
                    <td>SINTEF thermopack (CPA)</td>
                    <td>Orta Hız<br>(~500 ms)</td>
                    <td>Klasik kübik denklemler hidrojen bağlarını modelleyemez. NeqSim CPA modeli su-hidrokarbon çözünürlüğü ve asit gazı etkilerini tam yakalar.</td>
                </tr>
                <tr>
                    <td><b>Saf Akışkanlar & Soğutma Çevrimleri</b> (Saf Propan, N₂, Saf CO₂, R134a)</td>
                    <td><b>CoolProp (HEOS)</b></td>
                    <td>Peng-Robinson</td>
                    <td>Yüksek Hassasiyet</td>
                    <td>Saf akışkanlarda Helmholtz serbest enerji denklemleri NIST deneysel tablolarıyla birebir uyumludur (< %0.05 hata).</td>
                </tr>
                <tr>
                    <td><b>ASME PTC 10 / API 617 Resmi Doğrulama</b></td>
                    <td><b>Petrobras ccp</b></td>
                    <td>Thermopack (Metot 3)</td>
                    <td>Resmi Standart</td>
                    <td>Fabrika kabul testleri (FAT) ve saha performans dönüşümleri için ASME PTC 10 Bölüm 5 standart formülasyonlarını uygular.</td>
                </tr>
            </table>

            <h2>3. Sıkıştırma Yolu Yöntemleri (Path Sizing)</h2>
            <p>Emiş koşullarından çıkış basıncına giden termodinamik sıkıştırma eğrisi boyunca <b>politropik integrali (∫ V dP)</b> çözmek için kullanılan nümerik şemalardır. Bunlar kendi başlarına birer EoS çözücü değildir; yol boyunca seçilen EoS motorundan (NeqSim, Thermopack, CoolProp vb.) sürekli fiziksel özellik çekerler.</p>
            
            <h3>Sıkıştırma Yolu Yöntemleri Mühendislik Karar Matrisi: Hangi Şartta Hangi Metot Seçilmeli?</h3>
            <table>
                <tr>
                    <th style="width: 20%;">İşletme Şartı / Gaz Tipi</th>
                    <th style="width: 20%;">Önerilen Metot</th>
                    <th style="width: 15%;">Hız & Kararlılık</th>
                    <th style="width: 15%;">Referans Standart</th>
                    <th>Mühendislik Gerekçesi & Fiziksel Mekanizma</th>
                </tr>
                <tr>
                    <td><b>Aşırı Zengin Gazlar (C1–C6+), Süperkritik & Yoğun Faz</b></td>
                    <td><b>Metot 5: Huntington-RK45</b></td>
                    <td>Yüksek (~8 ms)</td>
                    <td>ASME 85-GT-13</td>
                    <td>dT/dP diferansiyel denklemini 4. derece Runge-Kutta ile sürekli çözer. Yoğunluk ve Cp gradyanları sert değişen gazlarda sıfır adım hatasıyla analitik altın standarttır.</td>
                </tr>
                <tr>
                    <td><b>Zengin Gaz (C1–C5), Gerçek Gaz Durum Yolu</b></td>
                    <td><b>Metot 4: Doğrudan H-S</b></td>
                    <td>Yüksek (~4 ms)</td>
                    <td>Schultz Mollier</td>
                    <td>Gerçek entalpi ve entropi (Mollier) değişimlerini doğrudan çözer. f_t ampirik katsayısına ihtiyaç duymaz, over-sizing (aşırı büyük türbin/motor seçimi) riskini önler.</td>
                </tr>
                <tr>
                    <td><b>Yüksek Basınç & Gerçek Gaz Türevleri (X, Y)</b></td>
                    <td><b>Metot 6: Schultz 3-Üslü</b></td>
                    <td>Çok Hızlı (~3 ms)</td>
                    <td>Schultz 1962 ASME</td>
                    <td>İzobarik genleşme (X) ve izotermal sıkışabilirlik (Y) türevlerini kullanarak n_v (hacim), m_T (sıcaklık) ve n_p (iş) üslerini ayrı ayrı hesaplar.</td>
                </tr>
                <tr>
                    <td><b>ASME PTC 10 Fabrika Kabul Testleri (FAT)</b></td>
                    <td><b>Metot 2: Uç Nokta</b></td>
                    <td>Ultra Hızlı (~2 ms)</td>
                    <td>ASME PTC 10 Endpoint</td>
                    <td>Çıkış koşullarını referans alarak f_t Schultz düzeltmesi uygular. Test standı ve garanti noktası doğrulamalarında endüstriyel referanstır.</td>
                </tr>
                <tr>
                    <td><b>Kademeli / Basınç Dilimli Yol Analizi</b></td>
                    <td><b>Metot 3: Artımlı Basınç</b></td>
                    <td>Orta (~12 ms)</td>
                    <td>Huntington Slicing</td>
                    <td>Basınç aralığını 10-100 adıma bölerek yerel politropik üsleri adım adım entegre eder.</td>
                </tr>
                <tr>
                    <td><b>Kuru Satış Gazları (Lean Gas), Ön Fizibilite</b></td>
                    <td><b>Metot 1: Ortalama Özellikler</b></td>
                    <td>Ultra Hızlı (~2 ms)</td>
                    <td>API 617 Appendix C</td>
                    <td>Giriş ve çıkış k ve Z ortalamasını alır. Düşük basınç oranlarında (PR < 1.50) ve ideal gaza yakın akışkanlarda son derece hızlıdır.</td>
                </tr>
            </table>

            <div class="warning-box">
                <b>⚠️ Sıvılaşma ve Thermo Health İzleme:</b> KASP, her iterasyon adımında EoS çözücüden gelen faz durumlarını kontrol eder. Eğer gaz sıvı veya iki faz bölgesine girerse, Z faktörü 0.5'in altına düşerse arayüzde <b>CRITICAL / WARNING</b> uyarıları göstererek kompresörde sıvı hasarı oluşmasını önler.
            </div>
        </div>

        <div class="divider"></div>

        <!-- ================= ENGLISH SECTION ================= -->
        <div class="lang-section">
            <h1>🇺🇸 KASP Thermodynamics Handbook & Help Guide</h1>
            <p>The KASP application is designed to solve compressor sizing and performance design calculations with the highest degree of scientific and industrial precision (ASME PTC 10, API 617). This handbook provides transparent insight into the thermodynamic and aerodynamic calculation steps and guides the selection of the optimal Equation of State (EoS) and Compression Path Method for various process conditions.</p>

            <div class="info-box">
                <b>💡 Golden Rule:</b> The compressor calculation chain operates on two distinct levels:
                <ol>
                    <li><b>State-Level EoS Solver:</b> Mathematical root-finding and property evaluation at a single state (P, T).</li>
                    <li><b>Path-Level Sizing Method:</b> Numerical integration of the polytropic path (∫ V dP) from suction to discharge.</li>
                </ol>
            </div>

            <h2>1. Equation of State (EoS) Engines</h2>
            <p>Equations of State describe the thermodynamic relationships between Pressure (P), Temperature (T), and Volume (V) to evaluate essential properties such as enthalpy, entropy, compressibility factor (Z), and heat capacity (Cp).</p>
            
            <table>
                <tr>
                    <th style="width: 25%;">EoS Engine</th>
                    <th style="width: 25%;">Underlying Technology</th>
                    <th>Recommended Application & Strengths</th>
                </tr>
                <tr>
                    <td><b>🇳🇴 Equinor NeqSim (SRK-CPA / PVT)</b></td>
                    <td>Java-based native library by Equinor with CPA (Cubic-Plus-Association)</td>
                    <td><b>Oil & Gas standard.</b> Excellent for heavy C1-C6+ mixtures, polar fluids (water, MEG/TEG, methanol), and high sour gas (H₂S, CO₂ > 5%).</td>
                </tr>
                <tr>
                    <td><b>🌊 SINTEF thermopack</b></td>
                    <td>High-performance Fortran/C core with Cubic (Peng-Robinson, SRK)</td>
                    <td><b>Super-fast and rock-solid.</b> Highly stable near phase boundaries and multi-component hydrocarbon mixtures (~4 ms execution).</td>
                </tr>
                <tr>
                    <td><b>CoolProp (GERG-2008 / HEOS)</b></td>
                    <td>Helmholtz energy formulations & multiparameter equations</td>
                    <td><b>Pure fluids & lean sales gases.</b> Matches NIST experimental standards with highest accuracy for standard pipeline natural gas.</td>
                </tr>
                <tr>
                    <td><b>🇧🇷 Petrobras ccp</b></td>
                    <td>Python/C engine developed by Petrobras for turbomachinery</td>
                    <td><b>ASME PTC 10 / API 617 validation.</b> Standard industrial engine for centrifugal compressor factory acceptance tests.</td>
                </tr>
                <tr>
                    <td><b>Peng-Robinson / SRK</b></td>
                    <td>Classic cubic equations of state</td>
                    <td><b>Standard hydrocarbon processing.</b> Reliable across standard refining, petrochemical, and gas pipeline applications.</td>
                </tr>
                <tr>
                    <td><b>🇩🇪 DWSIM Thermodynamics</b></td>
                    <td>.NET open-source CAPE-OPEN compliant engine</td>
                    <td><b>Chemical & polar mixtures.</b> Comprehensive steam tables and chemical process simulation capabilities.</td>
                </tr>
            </table>

            <h2>2. Engineering Decision Matrix: Which EoS to Choose?</h2>
            <table>
                <tr>
                    <th style="width: 20%;">Process Condition / Gas Type</th>
                    <th style="width: 20%;">Primary Recommended EoS</th>
                    <th style="width: 15%;">Backup EoS</th>
                    <th style="width: 15%;">Key Strength</th>
                    <th>Engineering Rationale & Physical Mechanism</th>
                </tr>
                <tr>
                    <td><b>Rich Natural Gas (C1–C6+) & Associated Gas</b></td>
                    <td><b>SINTEF thermopack (PR)</b></td>
                    <td>NeqSim / Peng-Robinson</td>
                    <td>Super Fast & VLE Stability</td>
                    <td>Fast and robust cubic root-finding prevents non-convergence near multi-component dew points.</td>
                </tr>
                <tr>
                    <td><b>Polar Components (H₂O, Glycol, Methanol)</b></td>
                    <td><b>Equinor NeqSim (CPA)</b></td>
                    <td>DWSIM / CoolProp</td>
                    <td>Hydrogen Bonding (CPA)</td>
                    <td>CPA accounts for associative hydrogen bonding, essential when water or hydrate inhibitors are present.</td>
                </tr>
                <tr>
                    <td><b>Sour Gas (H₂S > 5%, CO₂ > 10%)</b></td>
                    <td><b>Equinor NeqSim (SRK)</b></td>
                    <td>SINTEF thermopack</td>
                    <td>Binary Interaction Params</td>
                    <td>Calibrated BIP matrices accurately capture acid gas compressibility and non-ideal deviations.</td>
                </tr>
                <tr>
                    <td><b>Lean Sales Gas (C1 > 90%) / Pure Gases (N₂, Air, CO₂)</b></td>
                    <td><b>CoolProp (GERG-2008)</b></td>
                    <td>SINTEF thermopack</td>
                    <td>High Accuracy</td>
                    <td>Helmholtz energy formulations align with NIST experimental data tables (< 0.05% error).</td>
                </tr>
                <tr>
                    <td><b>ASME PTC 10 / API 617 Official Verification</b></td>
                    <td><b>Petrobras ccp</b></td>
                    <td>Thermopack (Method 3)</td>
                    <td>Official Standard</td>
                    <td>Implements ASME PTC 10 Section 5 formulations for test-stand and field performance conversions.</td>
                </tr>
            </table>

            <h2>3. Compression Path Sizing Methods</h2>
            <p>Numerical integration schemes used to solve the <b>polytropic integral ( ∫ V dP )</b> along the thermodynamic compression curve from inlet to outlet pressure. These methods continuously evaluate thermodynamic properties along the path via the active EoS (NeqSim, Thermopack, CoolProp, etc.).</p>
            
            <h3>Compression Methods Engineering Decision Matrix: Which Method to Choose?</h3>
            <table>
                <tr>
                    <th style="width: 20%;">Process Condition / Gas Type</th>
                    <th style="width: 20%;">Recommended Method</th>
                    <th style="width: 15%;">Speed & Stability</th>
                    <th style="width: 15%;">Standard Basis</th>
                    <th>Engineering Rationale & Physical Mechanism</th>
                </tr>
                <tr>
                    <td><b>Rich Gas (C1–C6+), Supercritical & Dense Phase</b></td>
                    <td><b>Method 5: Huntington-RK45</b></td>
                    <td>High (~8 ms)</td>
                    <td>ASME 85-GT-13</td>
                    <td>Continuously integrates the fundamental 1st-law ODE (dT/dP) via 4th-order Runge-Kutta. Analytical gold standard with zero discretization error under steep Cp and density gradients.</td>
                </tr>
                <tr>
                    <td><b>Rich Natural Gas (C1–C5), General Sizing</b></td>
                    <td><b>Method 4: Direct H-S Path</b></td>
                    <td>High (~4 ms)</td>
                    <td>Schultz Mollier</td>
                    <td>Directly integrates the real enthalpy-entropy (Mollier) path. Eliminates empirical f_t corrections, preventing machinery over-sizing.</td>
                </tr>
                <tr>
                    <td><b>High-Pressure Real Gases (X, Y Derivatives)</b></td>
                    <td><b>Method 6: Schultz 3-Exponent</b></td>
                    <td>Very Fast (~3 ms)</td>
                    <td>Schultz 1962 ASME</td>
                    <td>Evaluates isobaric (X) and isothermal (Y) compressibility derivatives to derive three distinct real-gas exponents: n_v (volume), m_T (temperature), and n_p (work).</td>
                </tr>
                <tr>
                    <td><b>ASME PTC 10 Factory Acceptance Testing (FAT)</b></td>
                    <td><b>Method 2: Endpoint Method</b></td>
                    <td>Ultra Fast (~2 ms)</td>
                    <td>ASME PTC 10 Endpoint</td>
                    <td>References discharge state properties with Schultz f_t correction. Standard for test-stand conversion and OEM performance verification.</td>
                </tr>
                <tr>
                    <td><b>Pressure-Sliced Multi-Step Analysis</b></td>
                    <td><b>Method 3: Incremental Pressure</b></td>
                    <td>Medium (~12 ms)</td>
                    <td>Huntington Slicing</td>
                    <td>Divides pressure span into 10–100 discrete increments and integrates local polytropic indices.</td>
                </tr>
                <tr>
                    <td><b>Lean Sales Gas, Early Feasibility</b></td>
                    <td><b>Method 1: Average Properties</b></td>
                    <td>Ultra Fast (~2 ms)</td>
                    <td>API 617 Appendix C</td>
                    <td>Averages inlet and outlet k and Z properties. Very fast for low pressure ratios (PR < 1.50) and near-ideal fluids.</td>
                </tr>
            </table>

            <div class="warning-box">
                <b>⚠️ Condensation & Thermo Health Monitoring:</b> KASP verifies fluid phase at every calculation step. If the gas enters the two-phase or liquid envelope (or if Z drops below 0.5), <b>CRITICAL / WARNING</b> alerts are raised on the interface to protect compressor machinery from liquid slugging.
            </div>
        </div>

        </body>
        </html>
        """
        
        self.browser.setHtml(html_content)
        layout.addWidget(self.browser)

        diagram_label = QLabel("📐 3-Katmanlı Termodinamik Mimari Diyagramı &mdash; 3-Layer Thermodynamic Architecture")
        diagram_label.setAlignment(Qt.AlignCenter)
        diagram_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        layout.addWidget(diagram_label)

        self._setup_diagram(layout, t)

        button_box = QDialogButtonBox(QDialogButtonBox.Close)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _setup_diagram(self, layout, theme):
        from PyQt5.QtSvg import QSvgWidget
        from PyQt5.QtWidgets import QScrollArea
        from kasp.ui.diagram_svg import generate_3layer_diagram_svg

        svg_content = generate_3layer_diagram_svg(theme)
        svg_bytes = bytearray(svg_content, encoding='utf-8')

        self.svg_widget = QSvgWidget()
        self.svg_widget.load(svg_bytes)
        self.svg_widget.setMinimumHeight(420)
        self.svg_widget.setMaximumHeight(520)
        self.svg_widget.setStyleSheet(f"background-color: {theme.get('background', '#1F1F1F')}; border: 1px solid {theme.get('border', '#334155')}; border-radius: 6px;")

        layout.addWidget(self.svg_widget)


class ChangePasswordDialog(QDialog):
    """Kullanıcının kendi şifresini değiştirmesi için dialog."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🔑 Şifre Değiştir")
        self.resize(380, 200)
        self._setup_ui()

    def _setup_ui(self):
        layout = QFormLayout(self)
        layout.setSpacing(10)

        self._old_pw = QLineEdit()
        self._old_pw.setEchoMode(QLineEdit.Password)
        self._old_pw.setPlaceholderText("Mevcut şifre")
        layout.addRow("Mevcut Şifre:", self._old_pw)

        self._new_pw = QLineEdit()
        self._new_pw.setEchoMode(QLineEdit.Password)
        self._new_pw.setPlaceholderText("En az 4 karakter")
        layout.addRow("Yeni Şifre:", self._new_pw)

        self._confirm_pw = QLineEdit()
        self._confirm_pw.setEchoMode(QLineEdit.Password)
        self._confirm_pw.setPlaceholderText("Yeni şifre tekrar")
        layout.addRow("Yeni Şifre Tekrar:", self._confirm_pw)

        self._error_label = QLabel("")
        self._error_label.setStyleSheet("color: #c62828;")
        self._error_label.setWordWrap(True)
        layout.addRow(self._error_label)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _validate_and_accept(self):
        old = self._old_pw.text()
        new = self._new_pw.text()
        confirm = self._confirm_pw.text()

        if not old or not new:
            self._error_label.setText("Tüm alanlar zorunludur.")
            return
        if len(new) < 4:
            self._error_label.setText("Yeni şifre en az 4 karakter olmalıdır.")
            return
        if new != confirm:
            self._error_label.setText("Yeni şifre ve tekrarı eşleşmiyor.")
            return
        if old == new:
            self._error_label.setText("Yeni şifre mevcut şifre ile aynı olamaz.")
            return
        self._old_password = old
        self._new_password = new
        self.accept()

    def get_passwords(self):
        return getattr(self, "_old_password", ""), getattr(self, "_new_password", "")
