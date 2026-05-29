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
            <p>KASP uygulaması, kompresör tasarım hesaplamalarını en yüksek bilimsel ve endüstriyel hassasiyetle (ASME PTC 10, API 617) çözmek üzere tasarlanmıştır. Bu kılavuz, arka planda koşan karmaşık termodinamik ve aerodinamik adımları anlaşılır hale getirmek için hazırlanmıştır.</p>

            <div class="info-box">
                <b>💡 Altın Kural:</b> Kompresör hesaplama zinciri iki bağımsız seviyede çalışır:
                <ol>
                    <li><b>Durum-Seviyesi Çözücü (State EoS Solver):</b> Tekil noktalarda kök bulma.</li>
                    <li><b>Yol-Seviyesi Sıkıştırma Yordamı (Compression Path Method):</b> Emişten çıkışa integrasyon yolu.</li>
                </ol>
            </div>

            <h2>1. Durum-Seviyesi EoS Çözücüler (State Model)</h2>
            <p>Bu seviye, gazın belirli bir basınç (P) ve sıcaklıkta (T) yoğunluk, sıkıştırılabilirlik faktörü (Z), entalpi (H), entropi (S) gibi tüm fiziksel özelliklerini belirleyen termodinamik teorileri barındırır. Kübik hal denklemleri, matematiksel olarak birer <b>kök bulma (root solving)</b> problemidir:</p>
            <pre>Z³ - (1-B)Z² + (A - 3B² - 2B)Z - (AB - B² - B³) = 0</pre>
            <p>Bu 3. dereceden kübik polinom çözüldüğünde en fazla 3 gerçel kök çıkabilir. EoS Çözücü, termodinamik kurallara (Gibbs serbest enerjisine) göre gaz fazına ait en büyük gerçel kökü veya sıvı fazına ait en küçük gerçel kökü seçen sayısal bir algoritmadır.</p>

            <h3>Mevcut Durum Modelleri:</h3>
            <table>
                <tr>
                    <th style="width: 25%;">Model (EoS)</th>
                    <th>Açıklama ve Kullanım Alanı</th>
                </tr>
                <tr>
                    <td><b>CoolProp (HEOS)</b></td>
                    <td>Yüksek hassasiyetli endüstri standardı termodinamik kütüphane (GERG-2008). Doğal gaz ve saf akışkan karışımları için referans kabul edilir.</td>
                </tr>
                <tr>
                    <td><b>SINTEF thermopack</b></td>
                    <td>Sıvılaşma ve faz ayrışması sınırlarında son derece hızlı ve kararlı çözüm sunan gelişmiş açık kaynaklı endüstriyel EoS motoru.</td>
                </tr>
                <tr>
                    <td><b>Petrobras ccp</b></td>
                    <td>ASME PTC 10 standartlarında test edilmiş, Petrobras'ın doğrulanmış performans hesaplama motoru.</td>
                </tr>
                <tr>
                    <td><b>Peng-Robinson / SRK</b></td>
                    <td>Geleneksel kübik hal denklemleri. Özellikle ağır hidrokarbon ağırlıklı karışımlarda hızlı sonuç üretir.</td>
                </tr>
                <tr>
                    <td><b>AGA8-DC92</b></td>
                    <td>Doğal gaz boru hattı taşımacılığı için geliştirilmiş, Z-faktörü odaklı hassas standart.</td>
                </tr>
            </table>

            <h2>2. Sıkıştırma Yolu Yöntemleri (Path Sizing)</h2>
            <p>Emiş koşullarından çıkış basıncına giden termodinamik sıkıştırma eğrisi boyunca <b>politropik integrali (∫ V dP)</b> çözmek için kullanılan nümerik şemalardır. Bunlar kendi başlarına birer EoS çözücü değildir, yol boyunca EoS çözücüden sürekli özellik çekerler.</p>
            
            <h3>Yol Entegrasyon Metotları:</h3>
            <ul>
                <li><b>Metot 1 (Ortalama Özellikler - Average Properties):</b> API 617 Appendix C standardını temel alır. Giriş ve çıkış durumlarındaki özelliklerin (k ve Z) ortalamasını kullanarak çıkış sıcaklığı T₂'yi basit bir iterasyon döngüsü ile yakınsatır.</li>
                <li><b>Metot 2 (Uç Nokta Yöntemi - Endpoint Method):</b> Sıkıştırma üssünü (polytropic exponent) doğrudan kompresörün çıkış koşullarına (outlet endpoint) göre hesaplar.</li>
                <li><b>Metot 3 (Artımlı Yol Entegrasyonu - Incremental Pressure):</b> Basınç farkını küçük dilimlere (örneğin 10 veya 100 adıma) bölerek, her adımda yerel EoS özelliklerini çözer ve kompresör yolunu adım adım integre eder. Çok kademeli sistemlerde hassasiyeti artırır.</li>
                <li><b>Metot 4 (Doğrudan H-S Yöntemi - Mollier Path):</b> Gerçek entalpi ve entropi farklarını (Mollier diyagramı üzerinde) kullanarak doğrudan entalpi yolunu integre eder. Termodinamik açıdan en kararlı ve hassas fiziksel yöntemdir.</li>
            </ul>

            <div class="warning-box">
                <b>⚠️ Sıvılaşma ve Thermo Health İzleme:</b> KASP, her iterasyon adımında EoS çözücüden gelen faz durumlarını kontrol eder. Eğer gaz sıvı veya iki faz bölgesine girerse, Z faktörü 0.5'in altına düşerse arayüzde <b>CRITICAL / WARNING</b> uyarıları göstererek kompresörde sıvı hasarı oluşmasını önler.
            </div>
        </div>

        <div class="divider"></div>

        <!-- ================= ENGLISH SECTION ================= -->
        <div class="lang-section">
            <h1>🇺🇸 KASP Thermodynamics Handbook & Help Guide</h1>
            <p>KASP application is designed to solve compressor sizing and design calculations with the highest degree of scientific and industrial precision (ASME PTC 10, API 617). This handbook explains the thermodynamic and aerodynamic calculation steps running in the background.</p>

            <div class="info-box">
                <b>💡 Golden Rule:</b> The compressor calculation chain operates on two distinct levels:
                <ol>
                    <li><b>State-Level EoS Solver:</b> Mathematical root-finding at a single state.</li>
                    <li><b>Path-Level Sizing Method:</b> Numerical integration of the polytropic path.</li>
                </ol>
            </div>

            <h2>1. State-Level EoS Solvers (State Model)</h2>
            <p>This level consists of thermodynamic theories determining the physical properties of a gas (density, compressibility factor Z, enthalpy H, entropy S, Cp, Cv) at a given pressure (P) and temperature (T). Cubic equations of state are mathematical <b>root-finding</b> problems:</p>
            <pre>Z³ - (1-B)Z² + (A - 3B² - 2B)Z - (AB - B² - B³) = 0</pre>
            <p>Solving this 3rd-degree cubic polynomial yields up to 3 real roots. The EoS Solver is a numerical algorithm that identifies and selects the correct physical root (largest real root for vapor phase, smallest real root for liquid phase) according to Gibbs free energy minimization.</p>

            <h3>Supported State Models (Equations of State):</h3>
            <table>
                <tr>
                    <th style="width: 25%;">Model (EoS)</th>
                    <th>Description and Application Areas</th>
                </tr>
                <tr>
                    <td><b>CoolProp (HEOS)</b></td>
                    <td>High-accuracy industry standard library (GERG-2008). Widely accepted as a reference for natural gas and pure fluid mixtures.</td>
                </tr>
                <tr>
                    <td><b>SINTEF thermopack</b></td>
                    <td>Advanced, robust open-source EoS engine offering ultra-fast and exceptionally stable calculations near condensation boundaries.</td>
                </tr>
                <tr>
                    <td><b>Petrobras ccp</b></td>
                    <td>Petrobras' officially validated centrifugal compressor performance engine, fully tested against ASME PTC 10.</td>
                </tr>
                <tr>
                    <td><b>Peng-Robinson / SRK</b></td>
                    <td>Classic cubic equations of state. Highly efficient and robust, particularly for heavy hydrocarbon mixtures.</td>
                </tr>
                <tr>
                    <td><b>AGA8-DC92</b></td>
                    <td>Natural gas pipeline standard specializing in highly accurate Z-factor computations.</td>
                </tr>
            </table>

            <h2>2. Compression Path Sizing Methods</h2>
            <p>Numerical integration schemes used to solve the <b>polytropic integral ( ∫ V dP )</b> along the thermodynamic compression curve from inlet to outlet pressure. Sizing methods are not thermodynamic EoS models; they iteratively query the EoS solver for local properties.</p>
            
            <h3>Path Integration Methods:</h3>
            <ul>
                <li><b>Method 1 (Average Properties):</b> Based on API 617 Appendix C. Uses arithmetic or logarithmic averages of inlet/outlet properties (k and Z) to converge on the discharge temperature T₂.</li>
                <li><b>Method 2 (Endpoint Method):</b> Calculates the polytropic exponent referencing directly the discharge endpoint conditions of the compressor.</li>
                <li><b>Method 3 (Incremental Pressure Path):</b> Divides the pressure span into multiple increments (e.g., 10 or 100 steps), solving local EoS properties at each step and integrating numerically. Highly accurate for complex sizing paths.</li>
                 <li><b>Method 4 (Direct H-S Method):</b> Operates on the Mollier enthalpy-entropy plane, utilizing enthalpy definitions and efficiency ratios ($\eta_{{\text{{poly}}}} = \frac{{dH_{{\text{{isen}}}}}}{{dH_{{\text{{actual}}}}}}$) to integrate the polytropic curve. Physically the most stable and rigorous method.</li>
            </ul>
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
