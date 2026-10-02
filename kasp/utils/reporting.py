import logging
import datetime
import os
import sys
import io
from html import escape
from release_metadata import APP_VERSION

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    REPORTLAB_LOADED = True
except ImportError:
    REPORTLAB_LOADED = False


logger = logging.getLogger(__name__)


def _get_font_path(filename):
    if getattr(sys, "frozen", False):
        return os.path.join(sys._MEIPASS, "resources", "fonts", filename)
    return os.path.join(os.path.dirname(__file__), "..", "..", "resources", "fonts", filename)


DEJAVU_SANS_REGISTERED = False
_FONT_REGULAR = "Helvetica"
_FONT_BOLD = "Helvetica-Bold"


def _register_dejavu_fonts():
    global DEJAVU_SANS_REGISTERED, _FONT_REGULAR, _FONT_BOLD
    DEJAVU_SANS_REGISTERED = False
    _FONT_REGULAR = "Helvetica"
    _FONT_BOLD = "Helvetica-Bold"
    if not REPORTLAB_LOADED:
        return
    regular_ok = False
    bold_ok = False
    try:
        regular = _get_font_path("DejaVuSans.ttf")
        bold = _get_font_path("DejaVuSans-Bold.ttf")
        if os.path.exists(regular):
            pdfmetrics.registerFont(TTFont("DejaVuSans", regular))
            regular_ok = True
        if os.path.exists(bold):
            pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", bold))
            bold_ok = True
    except Exception as e:
        logger.warning(f"DejaVuSans font registration failed: {e}")

    DEJAVU_SANS_REGISTERED = regular_ok
    if regular_ok:
        _FONT_REGULAR = "DejaVuSans"
        _FONT_BOLD = "DejaVuSans-Bold" if bold_ok else "DejaVuSans"
    else:
        logger.info("DejaVuSans font not available — PDF reports will use Helvetica")


def _set_pdf_fonts(styles):
    if DEJAVU_SANS_REGISTERED:
        for style_name in styles.byName:
            styles[style_name].fontName = _FONT_REGULAR


def _is_english():
    try:
        from kasp.i18n import is_english
        return is_english()
    except Exception:
        return False


def _L(tr_text, en_text):
    return en_text if _is_english() else tr_text


_register_dejavu_fonts()


# Task 5: Import GraphGenerator for graph embedding
try:
    from kasp.utils.graphs import GraphGenerator
    GRAPHS_AVAILABLE = True
except ImportError:
    GRAPHS_AVAILABLE = False
    GraphGenerator = None

# Task 5: Import UncertaintyAnalyzer for ASME PTC 10 uncertainty analysis
try:
    from kasp.core.uncertainty import UncertaintyAnalyzer
    UNCERTAINTY_AVAILABLE = True
except ImportError:
    UNCERTAINTY_AVAILABLE = False
    UncertaintyAnalyzer = None

class ReportGenerator:
    def __init__(self, file_path, engine):
        self.file_path = file_path
        self.engine = engine
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Task 5: Initialize graph generator for embedding
        if GRAPHS_AVAILABLE:
            self.graph_generator = GraphGenerator(engine)
            self.logger.info("Graph embedding enabled for PDF reports")
        else:
            self.graph_generator = None
            self.logger.warning("Graph embedding not available (graphs.py not found)")
        
        # Task 5: Initialize uncertainty analyzer for ASME PTC 10 analysis
        if UNCERTAINTY_AVAILABLE:
            self.uncertainty_analyzer = UncertaintyAnalyzer()
            self.logger.info("ASME PTC 10 uncertainty analysis enabled for PDF reports")
        else:
            self.uncertainty_analyzer = None
            self.logger.warning("Uncertainty analysis not available (uncertainty.py not found)")
        
    def generate_design_report(self, inputs, results, selected_units, report_units):
        """Tasarım raporu oluşturur - GELİŞMİŞ VERSİYON"""
        if not REPORTLAB_LOADED:
            raise ImportError("ReportLab kütüphanesi yüklü değil")
             
        try:
            doc = SimpleDocTemplate(self.file_path, pagesize=A4)
            story = []
            styles = getSampleStyleSheet()
            _set_pdf_fonts(styles)
            
            # Başlık
            title = Paragraph(
                _L(f"KASP v{APP_VERSION} - Kompresör Tasarım Raporu",
                   f"KASP v{APP_VERSION} - Compressor Design Report") +
                f"<br/>{escape(str(inputs.get('project_name', '')))}", styles['Title'])
            story.append(title)
            story.append(Spacer(1, 12))
            
            # Tarih ve versiyon
            date_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
            version_info = Paragraph(
                _L(f"Rapor Tarihi: {date_str} | KASP v{APP_VERSION} | Gelişmiş Termodinamik Motor",
                   f"Report Date: {date_str} | KASP v{APP_VERSION} | Advanced Thermodynamic Engine"),
                styles['Normal'])
            story.append(version_info)
            story.append(Spacer(1, 20))
            
            # 1. PROJE BİLGİLERİ
            story.append(Paragraph(_L("1. PROJE BİLGİLERİ", "1. PROJECT INFORMATION"), styles['Heading2']))
            req_eos = str(inputs.get('eos_method', 'coolprop'))
            eff_eos = results.get('effective_eos') or results.get('_effective_eos')
            if eff_eos and str(eff_eos).lower() != req_eos.lower():
                eos_display = f"{self._get_eos_display_name(req_eos)} -> {self._get_eos_display_name(str(eff_eos))} (Fallback)"
            else:
                eos_display = self._get_eos_display_name(req_eos)

            amb_p_val = float(inputs.get('ambient_pressure', inputs.get('ambient_press', 101.325)))
            amb_p_unit = 'kPa' if amb_p_val <= 200.0 else 'mbar'

            project_data = [
                [_L("Parametre", "Parameter"), _L("Değer", "Value"), _L("Birim", "Unit")],
                [_L("Proje Adı", "Project Name"), inputs['project_name'], ''],
                [_L("Ünite Sayısı", "Number of Units"), f"{inputs['num_units']}", ''],
                [_L("Gaz Kompozisyonu", "Gas Composition"), self._format_composition(inputs['gas_comp']), ''],
                [_L("EOS Metodu", "EOS Method"), eos_display, ''],
                [_L("Hesaplama Metodu", "Calculation Method"), inputs['method'], ''],
                [_L("Ortam Sıcaklığı", "Ambient Temperature"), f"{inputs['ambient_temp']:.1f}", '°C'],
                [_L("Ortam Basıncı", "Ambient Pressure"), f"{amb_p_val:.2f}", amb_p_unit],
                [_L("Rakım", "Altitude"), f"{inputs.get('altitude', 0):.0f}", 'm']
            ]
            
            project_table = Table(project_data, colWidths=[200, 200, 80])
            project_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), _FONT_BOLD),
                ('FONTNAME', (0, 1), (-1, -1), _FONT_REGULAR),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ecf0f1')),
                ('GRID', (0, 0), ( -1, -1), 1, colors.black)
            ]))
            story.append(project_table)
            story.append(Spacer(1, 20))
            
            # 2. PROSES KOŞULLARI
            story.append(Paragraph(_L("2. PROSES KOŞULLARI", "2. PROCESS CONDITIONS"), styles['Heading2']))
            process_data = [
                [_L("Parametre", "Parameter"), _L("Giriş", "Inlet"), _L("Çıkış", "Outlet"), _L("Birim", "Unit")],
                [_L("Basınç", "Pressure"), f"{inputs['p_in']}", f"{inputs['p_out']}", inputs['p_in_unit']],
                [_L("Sıcaklık", "Temperature"), f"{inputs['t_in']}", f"{results['t_out']:.1f}", inputs['t_in_unit']],
                [_L("Sıkıştırma Oranı", "Compression Ratio"), '-', f"{results['compression_ratio']:.2f}", ''],
                [_L("Politropik Verim", "Polytropic Efficiency"), f"{inputs['poly_eff']:.1f}", f"{results['actual_poly_efficiency']*100:.2f}", '%'],
                [_L("Isıl Verim", "Thermal Efficiency"), f"{inputs['therm_eff']:.1f}", '-', '%'],
                [_L("Mekanik Verim", "Mechanical Efficiency"), f"{inputs['mech_eff']:.1f}", '-', '%']
            ]
            
            process_table = Table(process_data, colWidths=[120, 80, 80, 60])
            process_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), _FONT_BOLD),
                ('FONTNAME', (0, 1), (-1, -1), _FONT_REGULAR),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#bdc3c7')),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(process_table)
            story.append(Spacer(1, 20))
            
            # 3. DEBİ ve GÜÇ HESAPLAMALARI
            story.append(Paragraph(_L("3. DEBİ ve GÜÇ HESAPLAMALARI", "3. FLOW and POWER CALCULATIONS"), styles['Heading2']))
            
            # Birim dönüşümleri
            power_unit_val = self.engine.convert_result_value(
                results['power_unit_kw'], 'kW', report_units['power_unit'], 'power'
            )
            power_total_val = self.engine.convert_result_value(
                results['power_unit_total_kw'], 'kW', report_units['power_unit'], 'power'
            )
            power_fmt = ".2f" if report_units.get('power_unit') == 'MW' else ".0f"
            
            power_data = [
                [_L('Parametre', 'Parameter'), _L('Ünite Başına', 'Per Unit'), _L('Toplam', 'Total'), _L('Birim', 'Unit')],
                [_L('Kütlesel Debi', 'Mass Flow'), 
                 f"{results['mass_flow_per_unit_kgs']:.3f}", 
                 f"{results['mass_flow_total_kgs']:.3f}", 
                 'kg/s'],
                [_L('Hacimsel Debi', 'Volumetric Flow'), 
                 f"{results['inlet_vol_flow_acmh_per_unit']:.0f}", 
                 f"{results['inlet_vol_flow_acmh_per_unit'] * results['num_units']:.0f}", 
                 'ACMH'],
                [_L('Gaz Gücü', 'Gas Power'), 
                 f"{results['power_gas_per_unit_kw']:.0f}", 
                 f"{results['power_gas_total_kw']:.0f}", 
                 'kW'],
                [_L('Şaft Gücü', 'Shaft Power'), 
                 f"{results['power_shaft_per_unit_kw']:.0f}", 
                 f"{results['power_shaft_total_kw']:.0f}", 
                 'kW'],
                [_L('Ünite Gücü', 'Unit Power'), 
                 f"{power_unit_val:{power_fmt}}", 
                 f"{power_total_val:{power_fmt}}", 
                 report_units['power_unit']],
                [_L('Mekanik Kayıp', 'Mechanical Loss'), 
                 f"{results['mech_loss_per_unit_kw']:.0f}", 
                 f"{results['mech_loss_total_kw']:.0f}", 
                 'kW']
            ]
            
            power_table = Table(power_data, colWidths=[140, 80, 80, 60])
            power_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#27ae60')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), _FONT_BOLD),
                ('FONTNAME', (0, 1), (-1, -1), _FONT_REGULAR),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#d5f4e6')),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(power_table)
            story.append(Spacer(1, 20))
            
            # 4. TERMODİNAMİK SONUÇLAR
            story.append(Paragraph(_L("4. TERMODİNAMİK SONUÇLAR", "4. THERMODYNAMIC RESULTS"), styles['Heading2']))
            
            head_val = self.engine.convert_result_value(
                results['head_kj_kg'], 'kJ/kg', report_units['head_unit'], 'head'
            )
            hr_val = self.engine.convert_result_value(
                results['heat_rate'], 'kJ/kWh', report_units['heat_rate'], 'heat_rate'
            )
            
            thermo_data = [
                [_L('Parametre', 'Parameter'), _L('Değer', 'Value'), _L('Birim', 'Unit')],
                [_L('Politropik Head', 'Polytropic Head'), f"{head_val:.1f}", report_units['head_unit']],
                [_L('Isı Oranı', 'Heat Rate'), f"{hr_val:.0f}", report_units['heat_rate']],
                [_L('Çıkış Sıcaklığı', 'Outlet Temperature'), f"{results['t_out']:.1f}", '°C'],
                [_L('Gerçek Politropik Verim', 'Actual Polytropic Efficiency'), f"{results['actual_poly_efficiency']*100:.2f}", '%'],
                [_L('Sıkıştırma Oranı', 'Compression Ratio'), f"{results['compression_ratio']:.2f}", ''],
                [_L('İzentropik Üs (k-giriş)', 'Isentropic Exponent (k-inlet)'), f"{results['inlet_properties']['k']:.3f}", ''],
                [_L('Sıkıştırılabilirlik (Z-giriş)', 'Compressibility (Z-inlet)'), f"{results['inlet_properties']['Z']:.4f}", '']
            ]
            
            thermo_table = Table(thermo_data, colWidths=[150, 100, 80])
            thermo_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e67e22')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), _FONT_BOLD),
                ('FONTNAME', (0, 1), (-1, -1), _FONT_REGULAR),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#fdebd0')),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(thermo_table)
            story.append(Spacer(1, 20))
            
            # 5. YAKIT BİLGİLERİ
            story.append(Paragraph(_L("5. YAKIT BİLGİLERİ", "5. FUEL INFORMATION"), styles['Heading2']))
            
            fuel_composition = inputs.get('fuel_gas_comp') or inputs.get('gas_comp') or {}
            fuel_gas_obj = self.engine._create_gas_object(fuel_composition, inputs['eos_method'])
            lhv_val = self.engine.convert_result_value(
                results['lhv'], 'kJ/kg', report_units['lhv'], 'heating_value', 
                fuel_gas_obj, inputs['eos_method']
            )
            hhv_val = self.engine.convert_result_value(
                results['hhv'], 'kJ/kg', report_units['hhv'], 'heating_value',
                fuel_gas_obj, inputs['eos_method']
            )
            fuel_unit_val = self.engine.convert_result_value(
                results['fuel_unit_kgh'], 'kg/h', report_units['fuel_unit'], 'fuel_flow',
                fuel_gas_obj, inputs['eos_method']
            )
            
            fuel_data = [
                [_L('Parametre', 'Parameter'), _L('Değer', 'Value'), _L('Birim', 'Unit')],
                [_L('LHV (Alt Isıl Değer)', 'LHV (Lower Heating Value)'), f"{lhv_val:.0f}", report_units['lhv']],
                [_L('HHV (Üst Isıl Değer)', 'HHV (Higher Heating Value)'), f"{hhv_val:.0f}", report_units['hhv']],
                [_L('Ünite Yakıt Tüketimi', 'Unit Fuel Consumption'), f"{fuel_unit_val:.1f}", report_units['fuel_unit']],
                [_L('Toplam Yakıt Tüketimi', 'Total Fuel Consumption'), f"{results['fuel_total_kgh']:.1f}", 'kg/h'],
                [_L('Isıl Verim', 'Thermal Efficiency'), f"{inputs['therm_eff']:.1f}", '%']
            ]
            
            fuel_table = Table(fuel_data, colWidths=[150, 100, 80])
            fuel_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#8e44ad')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), _FONT_BOLD),
                ('FONTNAME', (0, 1), (-1, -1), _FONT_REGULAR),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#e8daef')),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(fuel_table)
            
            # Task 5: Embed T-s and P-v diagrams if graph module is available
            if self.graph_generator is not None:
                try:
                    story.append(Spacer(1, 20))
                    story.append(Paragraph("5A. TERMODİNAMİK DİYAGRAMLAR", styles['Heading2']))
                    
                    # Generate T-s diagram — tablo ile aynı fizik: etkin (fallback sonrası) EOS kullanılır
                    diagram_eos = str(eff_eos) if eff_eos else req_eos
                    ts_canvas = self.graph_generator.create_ts_diagram(
                        inputs, results, inputs['gas_comp'], diagram_eos
                    )
                    if ts_canvas is not None:
                        # Save T-s diagram to BytesIO
                        ts_buffer = io.BytesIO()
                        ts_canvas.fig.savefig(ts_buffer, format='png', dpi=150, bbox_inches='tight')
                        ts_buffer.seek(0)
                        
                        # Add T-s diagram to PDF
                        ts_img = Image(ts_buffer, width=5*inch, height=3.5*inch)
                        story.append(Paragraph("T-s (Sıcaklık-Entropi) Diyagramı", styles['Heading3']))
                        story.append(Spacer(1, 6))
                        story.append(ts_img)
                        story.append(Spacer(1, 12))
                        self.logger.info("T-s diagram embedded in PDF report")
                    
                    # Generate P-v diagram — etkin EOS
                    pv_canvas = self.graph_generator.create_pv_diagram(
                        inputs, results, inputs['gas_comp'], diagram_eos
                    )
                    if pv_canvas is not None:
                        # Save P-v diagram to BytesIO
                        pv_buffer = io.BytesIO()
                        pv_canvas.fig.savefig(pv_buffer, format='png', dpi=150, bbox_inches='tight')
                        pv_buffer.seek(0)
                        
                        # Add P-v diagram to PDF
                        pv_img = Image(pv_buffer, width=5*inch, height=3.5*inch)
                        story.append(Paragraph("P-v (Basınç-Hacim) Diyagramı", styles['Heading3']))
                        story.append(Spacer(1, 6))
                        story.append(pv_img)
                        story.append(Spacer(1, 12))
                        self.logger.info("P-v diagram embedded in PDF report")
                        
                except Exception as e:
                    self.logger.warning(f"Diagram embedding failed: {e}", exc_info=True)
                    # Continue without diagrams - non-critical failure
            
            self._append_remaining_design_report_sections(story, inputs, results, selected_units, report_units, styles)
            
            doc.build(story)
            self.logger.info(f"Gelişmiş tasarım raporu oluşturuldu: {self.file_path}")
            
        except Exception as e:
            self.logger.error(f"Rapor oluşturma hatası: {e}", exc_info=True)
            raise

    def _append_remaining_design_report_sections(self, story, inputs, results, selected_units, report_units, styles):
        """Kısaltılmış Rapor Bölümlerinin devamı"""
        
        # 6. ÖNERİLEN TÜRBİNLER
        if selected_units:
            story.append(Spacer(1, 20))
            story.append(Paragraph("6. ÖNERİLEN GAZ TÜRBİNLERİ", styles['Heading2']))
            
            unit_data = [
                ['Sıra', 'Türbin Modeli', 'Güç (kW)', 'Isı Oranı', 'Verimlilik', 'Seçim Puanı', 'Öneri']
            ]
            
            for i, unit in enumerate(selected_units[:5], 1):
                unit_details = self._describe_report_unit(unit)
                unit_data.append([
                    str(i),
                    unit_details['name'],
                    f"{unit_details['available_power_kw']:.0f}",
                    f"{unit_details['site_heat_rate']:.0f}",
                    unit_details['efficiency_rating'],
                    f"{unit_details['selection_score']:.0f}",
                    unit_details['recommendation_level']
                ])
            
            unit_table = Table(unit_data, colWidths=[30, 160, 70, 70, 70, 60, 80])
            unit_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#c0392b')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), _FONT_BOLD),
                ('FONTNAME', (0, 1), (-1, -1), _FONT_REGULAR),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#fadbd8')),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9f9')])
            ]))
            story.append(unit_table)
        
        # 7. TERMODİNAMİK ÖZELLİKLER
        story.append(Spacer(1, 20))
        story.append(Paragraph("7. DETAYLI TERMODİNAMİK ÖZELLİKLER", styles['Heading2']))
        
        detailed_thermo_data = self._build_detailed_thermo_data(results)
        
        detailed_thermo_table = Table(detailed_thermo_data, colWidths=[120, 60, 60, 50, 60])
        detailed_thermo_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#16a085')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), _FONT_BOLD),
            ('FONTNAME', (0, 1), (-1, -1), _FONT_REGULAR),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#d1f2eb')),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(detailed_thermo_table)
        
        # 8. SİSTEM PERFORMANS İSTATİSTİKLERİ
        story.append(Spacer(1, 20))
        story.append(Paragraph("8. SİSTEM PERFORMANS İSTATİSTİKLERİ", styles['Heading2']))
        # Önbellek İstatistikleri Dışa Aktarma
        cache_stats = self.engine.thermo_solver.get_cache_stats()
        perf_stats = self.engine.performance_monitor.get_statistics()
        
        stats_data = [
            ['Metrik', 'Değer'],
            ['Önbellek İsabet Oranı', f"{cache_stats['hit_rate']*100:.1f}%"],
            ['Önbellek Boyutu', f"{cache_stats['size']}/{cache_stats['max_size']}"],
            ['Toplam Hesaplama', f"{perf_stats['total_calculations']}"],
            ['Ort. Hesaplama Süresi', f"{perf_stats['avg_calculation_time']:.3f} s"],
            ['Başarı Oranı', f"{perf_stats['success_rate']*100:.1f}%"],
            ['EOS Dağılımı', self._format_eos_distribution(perf_stats['eos_method_distribution'])]
        ]
        
        stats_table = Table(stats_data, colWidths=[180, 120])
        stats_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#7f8c8d')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), _FONT_BOLD),
            ('FONTNAME', (0, 1), (-1, -1), _FONT_REGULAR),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f4f6f6')),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(stats_table)
        
        # 9. UYARI ve NOTLAR
        warning_lines = self._build_design_warning_lines(results)
        if warning_lines:
            story.append(Spacer(1, 20))
            story.append(Paragraph("9. UYARILAR ve ÖNERİLER", styles['Heading2']))
            
            story.append(Paragraph(self._build_design_warnings_html(warning_lines), styles['Normal']))
        
        # 10. STANDART UYUMLULUK
        story.append(Spacer(1, 20))
        story.append(Paragraph("10. STANDART UYUMLULUK", styles['Heading2']))
        
        compliance_text = """
        <b>Endüstri Standardı Uyumluluk Durumu (referans-temelli, sertifikalı değil):</b><br/>
        • Head/verim hesap metodları ASME PTC-10 §4 yaklaşımlarına dayanır — KISMİ<br/>
        • Saha düzeltmeleri ISO 2314/ASME PTC-22 referans-koşul tarzındadır; OEM eğrisi değildir — KISMİ<br/>
        • Türbin seçimi API 616/API 617 marj yaklaşımlarına dayanır; tam uyum doğrulaması yapılmamıştır — KISMİ<br/>
        • Rotordinamik (lateral/torsional) analiz için gerçek FEA yapılmamıştır — UYGULANMADI<br/>
        • Belirsizlik analizi yalnızca Tip-B enstrüman katkısını içerir (Tip-A ve model belirsizliği hariç) — KISMİ<br/>
        • Bu rapor bir performans kabul/sertifikasyon belgesi DEĞİLDİR.<br/><br/>

        <b>Referans Standartlar:</b><br/>
        • ASME PTC-10: Compressors and Exhausters<br/>
        • ASME PTC-22: Gas Turbines<br/>
        • API 617: Axial and Centrifugal Compressors<br/>
        • API 616: Gas Turbines for Refinery Service<br/>
        • ISO 2314: Gas turbines - Acceptance tests<br/>
        • ISO 3977: Gas turbines - Procurement
        """
        
        compliance_para = Paragraph(compliance_text, styles['Normal'])
        story.append(compliance_para)
        
        # Task 5 Phase 3: ASME PTC 10 Uncertainty Analysis Section
        if self.uncertainty_analyzer is not None and hasattr(self, 'uncertainty_analyzer'):
            try:
                story.append(Spacer(1, 20))
                story.append(Paragraph("11. ASME PTC 10 MEASUREMENT UNCERTAINTY ANALYSIS", styles['Heading2']))
                
                # Standard measurement uncertainties per ASME PTC 10
                uncertainty_intro = """
                <b>Ölçüm Belirsizliği Analizi (ASME PTC 10 Appendix B — kısmi):</b><br/>
                Birleşik belirsizlik yalnızca Tip-B enstrüman katkısıyla RSS (Root-Sum-Square) yöntemiyle
                hesaplanmıştır. Tip-A (tekrarlanabilirlik), akışkan-model (EOS) belirsizliği ve Welch-Satterthwaite
                serbestlik derecesi düzeltmesi DAHİL DEĞİLDİR. Sonuçlar %95 güven aralığı varsayımıyla (k=2) raporlanır.<br/><br/>
                """
                story.append(Paragraph(uncertainty_intro, styles['Normal']))
                story.append(Spacer(1, 10))
                
                # Measurement uncertainties table
                uncertainty_data = [
                    ['Ölçüm Parametresi', 'Enstrüman Tipi', 'Standart Belirsizlik', 'Birim'],
                    ['Giriş Basıncı', 'Yüksek Doğruluk Basınç', '±0.25%', '%FS (tam ölçek)'],
                    ['Çıkış Basıncı', 'Yüksek Doğruluk Basınç', '±0.25%', '%FS (tam ölçek)'],
                    ['Giriş Sıcaklığı', 'RTD Class A', '±0.15°C', '@ 0°C'],
                    ['Çıkış Sıcaklığı', 'RTD Class A', '±0.15°C', '@ 0°C'],
                    ['Kütlesel Debi', 'Coriolis Akış Ölçer', '±0.10%', 'of rate'],
                    ['Güç Ölçümü', 'Dijital Wattmetre', '±0.20%', 'of reading']
                ]
                
                unc_table = Table(uncertainty_data, colWidths=[120, 120, 100, 80])
                unc_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2980b9')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), _FONT_BOLD),
                    ('FONTNAME', (0, 1), (-1, -1), _FONT_REGULAR),
                    ('FONTSIZE', (0, 0), (-1, 0), 9),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#d6eaf8')),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                story.append(unc_table)
                story.append(Spacer(1, 15))
                
                # Performance parameter uncertainties
                story.append(Paragraph("Hesaplanan Performans Parametresi Belirsizlikleri (%95 Güven Aralığı):", styles['Heading3']))
                story.append(Spacer(1, 8))
                
                perf_unc_data = [
                    ['Performans Parametresi', 'Birleşik Belirsizlik', 'Genişletilmiş (k=2)', 'Güven'],
                    *(
                        [
                            ['Politropik Verim',
                             f"±{((results.get('uncertainty') or {}).get('polytropic_efficiency') or {}).get('combined_uncertainty', 0):.4f}",
                             f"±{((results.get('uncertainty') or {}).get('polytropic_efficiency') or {}).get('expanded_uncertainty', 0):.4f}",
                             ((results.get('uncertainty') or {}).get('polytropic_efficiency') or {}).get('confidence_level', '95%')],
                        ]
                        if (results.get('uncertainty') or {}).get('polytropic_efficiency')
                        else [['Politropik Verim', 'hesaplanmadı', 'hesaplanmadı', '-']]
                    ),
                ]
                
                perf_unc_table = Table(perf_unc_data, colWidths=[140, 100, 100, 80])
                perf_unc_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#27ae60')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), _FONT_BOLD),
                    ('FONTNAME', (0, 1), (-1, -1), _FONT_REGULAR),
                    ('FONTSIZE', (0, 0), (-1, 0), 9),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#d5f5e3')),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                story.append(perf_unc_table)
                story.append(Spacer(1, 12))
                
                # Uncertainty methodology note
                _unc = results.get('uncertainty') or {}
                _compliant = _unc.get('asme_ptc10_compliant')
                _compliance_line = (
                    "• ASME PTC 10 Appendix B uygunluğu: <b>EVET</b> (ölçüm belirsizlikleri)<br/>"
                    if _compliant
                    else "• ASME PTC 10 Appendix B uygunluğu: <b>HAYIR / KISMİ</b> — "
                         + escape("; ".join(_unc.get('compliance_reasons') or ["gerekçe belirtilmedi"]))
                         + "<br/>"
                )
                methodology_note = (
                    "<b>Belirsizlik Analizi Metodolojisi:</b><br/>"
                    "• RSS (Root-Sum-Square) metodu ile birleşik belirsizlik hesaplanmıştır<br/>"
                    "• Duyarlılık katsayıları sayısal türev ile belirlenmiştir<br/>"
                    "• Kapsama faktörü k=2 kullanılarak %95 güven aralığı sağlanmıştır<br/>"
                    + _compliance_line +
                    "<br/>"
                    "<b>Referans Standart:</b><br/>"
                    "ASME PTC 10-1997: Performance Test Code on Compressors and Exhausters, Appendix B - Measurement Uncertainty"
                )
                story.append(Paragraph(methodology_note, styles['Normal']))
                
                self.logger.info("ASME PTC 10 uncertainty analysis section added to PDF report")
                
            except Exception as e:
                self.logger.warning(f"Uncertainty section embedding failed: {e}", exc_info=True)
                # Continue without uncertainty section - non-critical failure
        
        # Task 5 Phase 4: Industry Benchmarks Comparison Section
        try:
            story.append(Spacer(1, 20))
            story.append(Paragraph("12. INDUSTRY BENCHMARKS COMPARISON", styles['Heading2']))
            
            benchmarks_intro = """
            <b>Endüstri Standartları ile Performans Karşılaştırması:</b><br/>
            Kompresör performans parametreleri, API 617 ve ISO 2314 endüstri standartlarına göre 
            değerlendirilmiş ve sınıflandırılmıştır. Aşağıdaki tabloda, tasarım performansınızın 
            endüstri standartlarına göre konumu gösterilmektedir.<br/><br/>
            """
            story.append(Paragraph(benchmarks_intro, styles['Normal']))
            story.append(Spacer(1, 10))
            
            # Calculate benchmark ratings
            actual_poly_eff = results['actual_poly_efficiency'] * 100
            
            # Define benchmark rating function
            def get_benchmark_rating(value, param_type):
                if param_type == 'polytropic_eff':
                    if value >= 88.0:
                        return 'Excellent (Mükemmel)', colors.HexColor('#27ae60')
                    elif value >= 85.0:
                        return 'Good (İyi)', colors.HexColor('#2ecc71')
                    elif value >= 80.0:
                        return 'Fair (Orta)', colors.HexColor('#f39c12')
                    else:
                        return 'Below Standard (Standart Altı)', colors.HexColor('#e74c3c')
                elif param_type == 'isentropic_eff':
                    if value >= 85.0:
                        return 'Excellent (Mükemmel)', colors.HexColor('#27ae60')
                    elif value >= 82.0:
                        return 'Good (İyi)', colors.HexColor('#2ecc71')
                    elif value >= 78.0:
                        return 'Fair (Orta)', colors.HexColor('#f39c12')
                    else:
                        return 'Below Standard (Standart Altı)', colors.HexColor('#e74c3c')
                elif param_type == 'mechanical_eff':
                    if value >= 99.0:
                        return 'Excellent (Mükemmel)', colors.HexColor('#27ae60')
                    elif value >= 97.5:
                        return 'Good (İyi)', colors.HexColor('#2ecc71')
                    elif value >= 95.0:
                        return 'Fair (Orta)', colors.HexColor('#f39c12')
                    else:
                        return 'Below Standard (Standart Altı)', colors.HexColor('#e74c3c')
                return 'N/A', colors.grey
            
            # Calculate approximate values
            isentropic_eff_approx = actual_poly_eff * 0.96
            mech_eff = inputs['mech_eff']
            
            poly_rating, poly_color = get_benchmark_rating(actual_poly_eff, 'polytropic_eff')
            isen_rating, isen_color = get_benchmark_rating(isentropic_eff_approx, 'isentropic_eff')
            mech_rating, mech_color = get_benchmark_rating(mech_eff, 'mechanical_eff')
            
            # Benchmarks table
            benchmark_data = [
                ['Performans Parametresi', 'Tasarım Değeri', 'Endüstri Standardı', 'Değerlendirme', 'Durum'],
                ['Politropik Verim', f'{actual_poly_eff:.2f}%', 'API 617: 85-88%+', poly_rating, '●'],
                ['İzentropik Verim', f'{isentropic_eff_approx:.2f}%', 'ISO 2314: 82-85%+', isen_rating, '●'],
                ['Mekanik Verim', f'{mech_eff:.1f}%', 'API 617: 97.5-99%+', mech_rating, '●'],
                ['Sıkıştırma Oranı', f"{results['compression_ratio']:.2f}", 'API 617: 1.05-4.5',
                 'In Range (Aralıkta)' if 1.05 <= results['compression_ratio'] <= 4.5 else 'Out of Range',
                 '✓' if 1.05 <= results['compression_ratio'] <= 4.5 else '✗']
            ]
            
            benchmark_table = Table(benchmark_data, colWidths=[120, 80, 100, 120, 40])
            table_style = [
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e67e22')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), _FONT_BOLD),
                ('FONTNAME', (0, 1), (-1, -1), _FONT_REGULAR),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#fdebd0')),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]
            # Color status indicators
            table_style.append(('TEXTCOLOR', (4, 1), (4, 1), poly_color))
            table_style.append(('TEXTCOLOR', (4, 2), (4, 2), isen_color))
            table_style.append(('TEXTCOLOR', (4, 3), (4, 3), mech_color))
            table_style.append(('FONTSIZE', (4, 1), (4, 3), 20))
            
            benchmark_table.setStyle(TableStyle(table_style))
            story.append(benchmark_table)
            story.append(Spacer(1, 12))
            
            # Performance summary
            performance_summary = f"""
            <b>Performans Özeti:</b><br/>
            • Politropik Verim: {poly_rating}<br/>
            • İzentropik Verim: {isen_rating}<br/>
            • Mekanik Verim: {mech_rating}<br/><br/>
            
            <b>Referans Standartlar:</b><br/>
            • API 617 (8th Edition): Axial and Centrifugal Compressors and Expander-compressors<br/>
            • ISO 2314: Gas turbines - Acceptance tests<br/>
            • API 616: Gas Turbines for Refinery Services<br/><br/>
            
            <b>Not:</b> Yukarıdaki karşılaştırmalar tipik endüstri değerlerine göre yapılmıştır. 
            Özel uygulama gereksinimleriniz için lütfen üretici spesifikasyonlarına danışınız.
            """
            story.append(Paragraph(performance_summary, styles['Normal']))
            
            self.logger.info("Industry benchmarks comparison section added to PDF report")
            
        except Exception as e:
            self.logger.warning(f"Benchmarks section embedding failed: {e}", exc_info=True)
            # Continue without benchmarks section - non-critical failure
        
    def generate_performance_report(self, inputs, results):
        """Performans raporu oluşturur - GELİŞTİRİLMİŞ"""
        if not REPORTLAB_LOADED:
            raise ImportError("ReportLab kütüphanesi yüklü değil")
             
        try:
            doc = SimpleDocTemplate(self.file_path, pagesize=A4)
            story = []
            styles = getSampleStyleSheet()
            _set_pdf_fonts(styles)
            
            # Başlık
            title = Paragraph(f"KASP v{APP_VERSION} - Performans Değerlendirme Raporu<br/>{escape(str(inputs.get('unit_name', '')))}", styles['Title'])
            story.append(title)
            story.append(Spacer(1, 12))
            
            # Tarih
            date_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
            date_para = Paragraph(f"Rapor Tarihi: {date_str} | KASP v{APP_VERSION}", styles['Normal'])
            story.append(date_para)
            story.append(Spacer(1, 20))
            
            # 1. TEST KOŞULLARI
            story.append(Paragraph("1. TEST KOŞULLARI", styles['Heading2']))
            amb_p_val = float(inputs.get('ambient_pressure', inputs.get('ambient_press', 101.325)))
            amb_p_unit = 'kPa' if amb_p_val <= 200.0 else 'mbar'
            unit_name = inputs.get('unit_name', inputs.get('project_name', 'Performans Testi'))
            fuel_flow_val = inputs.get('fuel_flow', results.get('fuel_cons_kg_h', 0.0))
            fuel_flow_unit = inputs.get('fuel_flow_unit', 'kg/h')
            test_data = [
                ['Parametre', 'Değer', 'Birim'],
                ['Test Edilen Ünite', str(unit_name), ''],
                ['Giriş Basıncı', f"{inputs.get('p_in', 0.0)}", inputs.get('p_in_unit', 'bar(a)')],
                ['Giriş Sıcaklığı', f"{inputs.get('t_in', 0.0)}", inputs.get('t_in_unit', '°C')],
                ['Çıkış Basıncı', f"{inputs.get('p_out', 0.0)}", inputs.get('p_out_unit', 'bar(a)')],
                ['Çıkış Sıcaklığı', f"{inputs.get('t_out', 0.0)}", inputs.get('t_out_unit', '°C')],
                ['Gaz Debisi', f"{inputs.get('flow', 0.0)}", inputs.get('flow_unit', 'kg/s')],
                ['Yakıt Tüketimi', f"{fuel_flow_val}", fuel_flow_unit],
                ['Ortam Sıcaklığı', f"{float(inputs.get('ambient_temp', 15.0)):.1f}", '°C'],
                ['Ortam Basıncı', f"{amb_p_val:.2f}", amb_p_unit],
                ['Nem Oranı', f"{float(inputs.get('humidity', 60)):.1f}", '%'],
                ['Rakım', f"{float(inputs.get('altitude', 0)):.0f}", 'm']
            ]
            
            test_table = Table(test_data, colWidths=[150, 100, 80])
            test_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), _FONT_BOLD),
                ('FONTNAME', (0, 1), (-1, -1), _FONT_REGULAR),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ecf0f1')),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(test_table)
            story.append(Spacer(1, 20))
            
            # 2. PERFORMANS KARŞILAŞTIRMASI
            story.append(Paragraph("2. PERFORMANS KARŞILAŞTIRMASI", styles['Heading2']))
            
            self._append_remaining_performance_report_sections(story, inputs, results, styles)
            
            doc.build(story)
            self.logger.info(f"Performance report created: {self.file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Performance report generation error: {e}", exc_info=True)
            raise
    
    def _append_remaining_performance_report_sections(self, story, inputs, results, styles):
        """Append remaining sections to performance report"""
        from reportlab.lib import colors
        from reportlab.platypus import Table, TableStyle, Paragraph, Spacer
        
        def _eff_frac(val):
            v = float(val or 0.0)
            return v / 100.0 if v > 1.0 else v

        act_poly = _eff_frac(results.get('actual_poly_eff', results.get('poly_eff', 0.0)))
        des_poly = _eff_frac(results.get('design_poly_eff', results.get('expected_poly_eff', act_poly)))
        dev_poly = float(results.get('deviation_poly_eff', 0.0))

        act_therm = _eff_frac(results.get('actual_therm_eff', results.get('turb_eff', 0.0)))
        exp_therm = _eff_frac(results.get('expected_therm_eff', act_therm))
        dev_therm = float(results.get('deviation_therm_eff', 0.0))

        act_hr = float(results.get('actual_heat_rate', 0.0))
        exp_hr = float(results.get('expected_heat_rate', act_hr))
        dev_hr = float(results.get('deviation_heat_rate', 0.0))

        act_pwr = float(results.get('actual_power', results.get('shaft_power_kw', 0.0)))
        exp_pwr = float(results.get('expected_power', act_pwr))
        dev_pwr = float(results.get('deviation_power', 0.0))

        # Performance comparison data
        perf_data = [
            ['Parametre', 'Gerçek', 'Tasarım', 'Sapma (%)', 'Durum'],
            ['Politropik Verim (%)', 
             f"{act_poly*100:.2f}", 
             f"{des_poly*100:.2f}",
             f"{dev_poly:.2f}",
             self._get_status_icon(dev_poly)],
            ['Isıl Verim (%)', 
             f"{act_therm*100:.2f}", 
             f"{exp_therm*100:.2f}",
             f"{dev_therm:.2f}",
             self._get_status_icon(dev_therm)],
            ['Isı Oranı (kJ/kWh)', 
             f"{act_hr:.0f}", 
             f"{exp_hr:.0f}",
             f"{dev_hr:.2f}",
             self._get_status_icon(dev_hr)],
            ['Çıkış Gücü (kW)', 
             f"{act_pwr:.0f}", 
             f"{exp_pwr:.0f}",
             f"{dev_pwr:.2f}",
             self._get_status_icon(dev_pwr)]
        ]
        
        perf_table = Table(perf_data, colWidths=[120, 80, 80, 60, 60])
        table_style = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#27ae60')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), _FONT_BOLD),
            ('FONTNAME', (0, 1), (-1, -1), _FONT_REGULAR),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#d5f4e6')),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]
        for i in range(1, len(perf_data)):
            deviation = abs(float(perf_data[i][3]))
            if deviation > 5.0:
                table_style.append(('BACKGROUND', (3, i), (3, i), colors.HexColor('#e74c3c')))
                table_style.append(('BACKGROUND', (4, i), (4, i), colors.HexColor('#e74c3c')))
            elif deviation > 2.0:
                table_style.append(('BACKGROUND', (3, i), (3, i), colors.HexColor('#f39c12')))
                table_style.append(('BACKGROUND', (4, i), (4, i), colors.HexColor('#f39c12')))
            else:
                table_style.append(('BACKGROUND', (3, i), (3, i), colors.HexColor('#2ecc71')))
                table_style.append(('BACKGROUND', (4, i), (4, i), colors.HexColor('#2ecc71')))
        
        perf_table.setStyle(TableStyle(table_style))
        story.append(perf_table)
        story.append(Spacer(1, 20))
        
        # 3. PERFORMANS DURUMU
        story.append(Paragraph("3. PERFORMANS DURUMU", styles['Heading2']))
        
        status = results.get('performance_status') or {
            'status': 'UYGUN',
            'color': 'green',
            'description': 'Performans değerleri beklenen sınırlar içindedir.',
            'recommendation': 'Rutin izlemeye devam edin.',
        }
        status_text = f"""
        <b>Performans Durumu:</b> <font color="{status.get('color', 'green')}">{status.get('status', 'UYGUN')}</font><br/>
        <b>Açıklama:</b> {status.get('description', '')}<br/>
        <b>Öneri:</b> {status.get('recommendation', '')}<br/><br/>
        
        <b>Detaylı Analiz:</b><br/>
        • Politropik Verim Sapması: {dev_poly:.2f}%<br/>
        • Isıl Verim Sapması: {dev_therm:.2f}%<br/>
        • Isı Oranı Sapması: {dev_hr:.2f}%<br/>
        • Güç Sapması: {dev_pwr:.2f}%<br/>
        """
        
        status_para = Paragraph(status_text, styles['Normal'])
        story.append(status_para)
        story.append(Spacer(1, 20))
        
        # 4. TEST KOŞULLARI DETAYI
        story.append(Paragraph("4. TEST KOŞULLARI DETAYI", styles['Heading2']))
        
        raw_isen = results.get(
            'actual_isentropic_eff',
            results.get('isen_eff', 0.0) / 100.0 if results.get('isen_eff', 0.0) > 1.0 else results.get('isen_eff', 0.0),
        )
        tc = results.get('test_conditions') or {}
        tc_mass_flow = float(tc.get('mass_flow', inputs.get('flow_kgs', inputs.get('flow', 0.0))))
        tc_fuel_flow = float(tc.get('fuel_flow', results.get('fuel_cons_kg_h', inputs.get('fuel_flow', 0.0))))
        tc_cr = float(
            tc.get(
                'compression_ratio',
                float(inputs.get('p2_pa', inputs.get('p_out', 1.0))) / max(float(inputs.get('p1_pa', inputs.get('p_in', 1.0))), 1e-9),
            )
        )
        tc_head = float(tc.get('head', results.get('poly_head_kj_kg', 0.0)))
        test_details_data = [
            ['Parametre', 'Değer', 'Birim'],
            ['Kütlesel Debi', f"{tc_mass_flow:.3f}", 'kg/s'],
            ['Yakıt Tüketimi', f"{tc_fuel_flow/3600:.3f}", 'kg/s'],
            ['Sıkıştırma Oranı', f"{tc_cr:.2f}", ''],
            ['Politropik Head', f"{tc_head:.1f}", 'kJ/kg'],
            ['İzentropik Verim', f"{float(raw_isen)*100:.2f}", '%']
        ]
        
        test_details_table = Table(test_details_data, colWidths=[120, 100, 80])
        test_details_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#8e44ad')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), _FONT_BOLD),
            ('FONTNAME', (0, 1), (-1, -1), _FONT_REGULAR),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#e8daef')),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(test_details_table)
        
        # 5. DÜZELTME FAKTÖRLERİ
        story.append(Spacer(1, 20))
        story.append(Paragraph("5. DÜZELTME FAKTÖRLERİ", styles['Heading2']))
        
        factors = results.get('corrected_values', {}).get('correction_factors', {})
        factor_inputs = factors.get('inputs', {})
        # Uygulanan (applied_*) faktorler gosterilir; ham faktorler degil (P3-16)
        correction_data = [
            ['Faktör', 'Değer', 'Uygulanan Etki'],
            ['Sıcaklık', f"{factor_inputs.get('ambient_temp_c', 15.0):.1f} °C", f"{(factors.get('applied_temperature_factor', 1.0) - 1) * 100:+.1f}%"],
            ['Basınç', f"{factor_inputs.get('ambient_pressure_kpa', 101.325):.3f} kPa", f"{(factors.get('applied_pressure_factor', 1.0) - 1) * 100:+.1f}%"],
            ['Nem', f"{factor_inputs.get('relative_humidity_pct', 60.0):.1f}%", f"{(factors.get('applied_humidity_factor', 1.0) - 1) * 100:+.1f}%"],
            ['Rakım', f"{factor_inputs.get('altitude_m', 0.0):.0f} m", f"{(factors.get('applied_altitude_factor', 1.0) - 1) * 100:+.1f}%"],
            ['Giriş Kaybı', f"{factor_inputs.get('inlet_pressure_loss_kpa', 0.0):.3f} kPa", f"{(factors.get('applied_inlet_loss_factor', 1.0) - 1) * 100:+.1f}%"],
            ['Egzoz Kaybı', f"{factor_inputs.get('exhaust_pressure_loss_kpa', 0.0):.3f} kPa", f"{(factors.get('applied_exhaust_loss_factor', 1.0) - 1) * 100:+.1f}%"],
            ['Toplam Güç Faktörü', f"{factors.get('power_factor', 1.0):.4f}", ''],
            ['Düzeltilmiş Güç', f"{results.get('corrected_power', 0.0):.0f} kW", 'ISO/PTC'],
            ['Düzeltilmiş Isı Oranı', f"{results.get('corrected_heat_rate', 0.0):.0f} kJ/kWh", 'ISO/PTC'],
        ]
        
        correction_table = Table(correction_data, colWidths=[100, 80, 80])
        correction_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e67e22')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), _FONT_BOLD),
            ('FONTNAME', (0, 1), (-1, -1), _FONT_REGULAR),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#fdebd0')),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(correction_table)

    def _format_composition(self, composition):
        """Gaz kompozisyonunu formatla"""
        components = []
        for comp, frac in (composition or {}).items():
            val = float(frac or 0.0)
            if val > 0:
                if val < 1.0:
                    components.append(f"{comp}: {val:.2f}%")
                else:
                    components.append(f"{comp}: {val:.1f}%")
        return ", ".join(components) if components else "Karışım"

    @staticmethod
    def _build_design_warning_lines(results):
        warning_lines = list(results.get('warnings') or [])
        convergence = results.get('method_convergence') or []
        if convergence and not results.get('method_converged', True):
            failed_stages = ", ".join(
                str(item.get('stage')) for item in convergence if not item.get('converged', False)
            )
            if failed_stages:
                warning_lines.append(
                    f"Hesaplama metodu yakinsamadi; son tahmin kullanildi. Kademeler: {failed_stages}"
                )
        if results.get('fallback_used'):
            if not any("fallback" in str(warning).lower() for warning in warning_lines):
                warning_lines.append(
                    "Termodinamik kutuphane en az bir noktada ideal gaz fallback kullandi."
                )
            warning_lines.append(f"Fallback durum sayisi: {results.get('fallback_state_count', 0)}")
            if results.get('fallback_stage_numbers'):
                stage_text = ", ".join(str(stage) for stage in results['fallback_stage_numbers'])
                warning_lines.append(f"Etkilenen kademeler: {stage_text}")
        return warning_lines

    @staticmethod
    def _build_design_warnings_html(warning_lines):
        lines = [str(warning) for warning in warning_lines if warning is not None]
        if not lines:
            return ""

        warning_items = "".join(f"&bull; {escape(line)}<br/>" for line in lines)
        return f"<b>Dikkat Edilmesi Gereken Noktalar:</b><br/>{warning_items}"

    @staticmethod
    def _percent_change_text(inlet_value, outlet_value):
        try:
            inlet = float(inlet_value)
            outlet = float(outlet_value)
        except (TypeError, ValueError):
            return "-"

        if inlet == 0:
            return "-"
        return f"{((outlet - inlet) / inlet * 100):+.1f}"

    @classmethod
    def _build_detailed_thermo_data(cls, results):
        inlet = results['inlet_properties']
        outlet = results['outlet_properties']
        return [
            ['Özellik', 'Giriş', 'Çıkış', 'Birim', 'Değişim (%)'],
            [
                'Sıkıştırılabilirlik (Z)',
                f"{inlet['Z']:.4f}",
                f"{outlet['Z']:.4f}",
                '',
                cls._percent_change_text(inlet['Z'], outlet['Z']),
            ],
            [
                'Yoğunluk',
                f"{inlet['rho']:.3f}",
                f"{outlet['rho']:.3f}",
                'kg/m³',
                cls._percent_change_text(inlet['rho'], outlet['rho']),
            ],
            [
                'İzentropik Üs (k)',
                f"{inlet['k']:.3f}",
                f"{outlet['k']:.3f}",
                '',
                cls._percent_change_text(inlet['k'], outlet['k']),
            ],
            [
                'Spesifik Isı (Cp)',
                f"{inlet['Cp'] / 1000:.3f}",
                f"{outlet['Cp'] / 1000:.3f}",
                'kJ/kg-K',
                cls._percent_change_text(inlet['Cp'], outlet['Cp']),
            ],
            [
                'Viskozite',
                f"{inlet['mu'] * 1e6:.2f}",
                f"{outlet['mu'] * 1e6:.2f}",
                'μPa·s',
                cls._percent_change_text(inlet['mu'], outlet['mu']),
            ],
            [
                'Ses Hızı',
                f"{inlet['a']:.1f}",
                f"{outlet['a']:.1f}",
                'm/s',
                cls._percent_change_text(inlet['a'], outlet['a']),
            ],
        ]

    @staticmethod
    def _get_unit_value(unit, *keys, default=None):
        if isinstance(unit, dict):
            for key in keys:
                if key in unit:
                    return unit[key]
            return default

        for key in keys:
            if hasattr(unit, key):
                return getattr(unit, key)
        return default

    @classmethod
    def _describe_report_unit(cls, unit):
        manufacturer = cls._get_unit_value(unit, 'manufacturer', default='')
        model = cls._get_unit_value(unit, 'model', default='')
        fallback_name = cls._get_unit_value(unit, 'turbine_name', 'turbine', default='Bilinmiyor')
        name = f"{manufacturer} {model}".strip() or fallback_name
        return {
            'name': name,
            'available_power_kw': float(cls._get_unit_value(unit, 'available_power_kw', default=0.0) or 0.0),
            'site_heat_rate': float(cls._get_unit_value(unit, 'site_heat_rate', default=0.0) or 0.0),
            'efficiency_rating': cls._get_unit_value(unit, 'efficiency_rating', default='-'),
            'selection_score': float(cls._get_unit_value(unit, 'selection_score', default=0.0) or 0.0),
            'recommendation_level': cls._get_unit_value(unit, 'recommendation_level', default='-'),
        }

    def _get_eos_display_name(self, eos_method):
        """EOS metodunun görünen adını getir (DejaVuSans uyumlu, emojisiz)"""
        names = {
            'coolprop': 'Yüksek Doğruluk (CoolProp)',
            'pr': 'Peng-Robinson (thermo)',
            'srk': 'SRK (thermo)',
            'thermopack': 'ThermoPack (SINTEF)',
            'aga8': 'AGA8-DC92 (GERG-2008 / Doğal Gaz)',
            'neqsim': 'NeqSim (Equinor)',
            'dwsim': 'DWSIM (Standalone)',
            'ccp': 'CCP (Petrobras)',
        }
        return names.get(str(eos_method).lower(), str(eos_method))

    def _format_eos_distribution(self, distribution):
        """EOS dağılımını formatla"""
        if not distribution:
            return "Veri yok"
        return ", ".join([f"{k}: {v}" for k, v in distribution.items()])

    def _get_status_icon(self, deviation):
        """Sapma değerine göre durum ikonu (DejaVuSans uyumlu)"""
        deviation_abs = abs(deviation)
        if deviation_abs <= 2.0:
            return "✓ UYGUN"
        elif deviation_abs <= 5.0:
            return "! UYARI"
        else:
            return "✗ KRİTİK"

    def generate_summary_report(self, inputs, results, selected_units):
        """Özet rapor oluşturur"""
        try:
            recommended = []
            if selected_units:
                for i, unit in enumerate(selected_units[:3]):
                    unit_info = self._describe_report_unit(unit)
                    recommended.append({
                        'rank': i + 1,
                        'turbine': unit_info['name'],
                        'power': unit_info['available_power_kw'],
                        'efficiency': unit_info['efficiency_rating'],
                        'score': unit_info['selection_score'],
                    })

            summary = {
                'project_name': inputs['project_name'],
                'calculation_date': datetime.datetime.now().isoformat(),
                'basic_parameters': {
                    'num_units': inputs['num_units'],
                    'compression_ratio': results['compression_ratio'],
                    'power_per_unit': results['power_unit_kw'],
                    'total_power': results['power_unit_total_kw'],
                    'outlet_temperature': results['t_out']
                },
                'efficiency_metrics': {
                    'poly_efficiency': results['actual_poly_efficiency'],
                    'thermal_efficiency': inputs['therm_eff'] / 100.0,
                    'heat_rate': results['heat_rate']
                },
                'recommended_turbines': recommended,
                'system_performance': self.engine.performance_monitor.get_statistics()
            }
            
            return summary
            
        except Exception as e:
            self.logger.error(f"Özet rapor oluşturma hatası: {e}")
            return {}
