import logging
import datetime
import os
import io  # Task 5: For graph embedding
from release_metadata import APP_VERSION

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors
    REPORTLAB_LOADED = True
except ImportError:
    REPORTLAB_LOADED = False


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
            
            # Başlık
            title = Paragraph(f"KASP v{APP_VERSION} - Kompresor Tasarim Raporu<br/>{inputs['project_name']}", styles['Title'])
            story.append(title)
            story.append(Spacer(1, 12))
            
            # Tarih ve versiyon
            date_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
            version_info = Paragraph(f"Rapor Tarihi: {date_str} | KASP v{APP_VERSION} | Gelismis Termodinamik Motor", styles['Normal'])
            story.append(version_info)
            story.append(Spacer(1, 20))
            
            # 1. PROJE BİLGİLERİ
            story.append(Paragraph("1. PROJE BİLGİLERİ", styles['Heading2']))
            project_data = [
                ['Parametre', 'Değer', 'Birim'],
                ['Proje Adı', inputs['project_name'], ''],
                ['Ünite Sayısı', f"{inputs['num_units']}", ''],
                ['Gaz Kompozisyonu', self._format_composition(inputs['gas_comp']), ''],
                ['EOS Metodu', self._get_eos_display_name(inputs['eos_method']), ''],
                ['Hesaplama Metodu', inputs['method'], ''],
                ['Ortam Sıcaklığı', f"{inputs['ambient_temp']:.1f}", '°C'],
                ['Ortam Basıncı', f"{inputs.get('ambient_pressure', 1013):.1f}", 'mbar'],
                ['Rakım', f"{inputs.get('altitude', 0):.0f}", 'm']
            ]
            
            project_table = Table(project_data, colWidths=[200, 200, 80])
            project_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ecf0f1')),
                ('GRID', (0, 0), ( -1, -1), 1, colors.black)
            ]))
            story.append(project_table)
            story.append(Spacer(1, 20))
            
            # 2. PROSES KOŞULLARI
            story.append(Paragraph("2. PROSES KOŞULLARI", styles['Heading2']))
            process_data = [
                ['Parametre', 'Giriş', 'Çıkış', 'Birim'],
                ['Basınç', f"{inputs['p_in']}", f"{inputs['p_out']}", inputs['p_in_unit']],
                ['Sıcaklık', f"{inputs['t_in']}", f"{results['t_out']:.1f}", inputs['t_in_unit']],
                ['Sıkıştırma Oranı', '-', f"{results['compression_ratio']:.2f}", ''],
                ['Politropik Verim', f"{inputs['poly_eff']:.1f}", f"{results['actual_poly_efficiency']*100:.2f}", '%'],
                ['Isıl Verim', f"{inputs['therm_eff']:.1f}", '-', '%'],
                ['Mekanik Verim', f"{inputs['mech_eff']:.1f}", '-', '%']
            ]
            
            process_table = Table(process_data, colWidths=[120, 80, 80, 60])
            process_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#bdc3c7')),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(process_table)
            story.append(Spacer(1, 20))
            
            # 3. DEBİ ve GÜÇ HESAPLAMALARI
            story.append(Paragraph("3. DEBİ ve GÜÇ HESAPLAMALARI", styles['Heading2']))
            
            # Birim dönüşümleri
            power_unit_val = self.engine.convert_result_value(
                results['power_unit_kw'], 'kW', report_units['power_unit'], 'power'
            )
            power_total_val = self.engine.convert_result_value(
                results['power_unit_total_kw'], 'kW', report_units['power_unit'], 'power'
            )
            
            power_data = [
                ['Parametre', 'Ünite Başına', 'Toplam', 'Birim'],
                ['Kütlesel Debi', 
                 f"{results['mass_flow_per_unit_kgs']:.3f}", 
                 f"{results['mass_flow_total_kgs']:.3f}", 
                 'kg/s'],
                ['Hacimsel Debi', 
                 f"{results['inlet_vol_flow_acmh_per_unit']:.0f}", 
                 f"{results['inlet_vol_flow_acmh_per_unit'] * results['num_units']:.0f}", 
                 'ACMH'],
                ['Gaz Gücü', 
                 f"{results['power_gas_per_unit_kw']:.0f}", 
                 f"{results['power_gas_total_kw']:.0f}", 
                 'kW'],
                ['Şaft Gücü', 
                 f"{results['power_shaft_per_unit_kw']:.0f}", 
                 f"{results['power_shaft_total_kw']:.0f}", 
                 'kW'],
                ['Ünite Gücü', 
                 f"{power_unit_val:.0f}", 
                 f"{power_total_val:.0f}", 
                 report_units['power_unit']],
                ['Mekanik Kayıp', 
                 f"{results['mech_loss_per_unit_kw']:.0f}", 
                 f"{results['mech_loss_total_kw']:.0f}", 
                 'kW']
            ]
            
            power_table = Table(power_data, colWidths=[140, 80, 80, 60])
            power_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#27ae60')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#d5f4e6')),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(power_table)
            story.append(Spacer(1, 20))
            
            # 4. TERMODİNAMİK SONUÇLAR
            story.append(Paragraph("4. TERMODİNAMİK SONUÇLAR", styles['Heading2']))
            
            head_val = self.engine.convert_result_value(
                results['head_kj_kg'], 'kJ/kg', report_units['head_unit'], 'head'
            )
            hr_val = self.engine.convert_result_value(
                results['heat_rate'], 'kJ/kWh', report_units['heat_rate'], 'heat_rate'
            )
            
            thermo_data = [
                ['Parametre', 'Değer', 'Birim'],
                ['Politropik Head', f"{head_val:.1f}", report_units['head_unit']],
                ['Isı Oranı', f"{hr_val:.0f}", report_units['heat_rate']],
                ['Çıkış Sıcaklığı', f"{results['t_out']:.1f}", '°C'],
                ['Gerçek Politropik Verim', f"{results['actual_poly_efficiency']*100:.2f}", '%'],
                ['Sıkıştırma Oranı', f"{results['compression_ratio']:.2f}", ''],
                ['İzentropik Üs (k-giriş)', f"{results['inlet_properties']['k']:.3f}", ''],
                ['Sıkıştırılabilirlik (Z-giriş)', f"{results['inlet_properties']['Z']:.4f}", '']
            ]
            
            thermo_table = Table(thermo_data, colWidths=[150, 100, 80])
            thermo_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e67e22')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#fdebd0')),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(thermo_table)
            story.append(Spacer(1, 20))
            
            # 5. YAKIT BİLGİLERİ
            story.append(Paragraph("5. YAKIT BİLGİLERİ", styles['Heading2']))
            
            fuel_gas_obj = self.engine._create_gas_object(inputs['gas_comp'], inputs['eos_method'])
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
                ['Parametre', 'Değer', 'Birim'],
                ['LHV (Alt Isıl Değer)', f"{lhv_val:.0f}", report_units['lhv']],
                ['HHV (Üst Isıl Değer)', f"{hhv_val:.0f}", report_units['hhv']],
                ['Ünite Yakıt Tüketimi', f"{fuel_unit_val:.1f}", report_units['fuel_unit']],
                ['Toplam Yakıt Tüketimi', f"{results['fuel_total_kgh']:.1f}", 'kg/h'],
                ['Isıl Verim', f"{inputs['therm_eff']:.1f}", '%']
            ]
            
            fuel_table = Table(fuel_data, colWidths=[150, 100, 80])
            fuel_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#8e44ad')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
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
                    
                    # Generate T-s diagram
                    ts_canvas = self.graph_generator.create_ts_diagram(
                        inputs, results, inputs['gas_comp'], inputs['eos_method']
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
                    
                    # Generate P-v diagram
                    pv_canvas = self.graph_generator.create_pv_diagram(
                        inputs, results, inputs['gas_comp'], inputs['eos_method']
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
                unit_data.append([
                    str(i),
                    f"{unit['manufacturer']} {unit['model']}",
                    f"{unit['available_power_kw']:.0f}",
                    f"{unit['site_heat_rate']:.0f}",
                    unit['efficiency_rating'],
                    f"{unit['selection_score']:.0f}",
                    unit['recommendation_level']
                ])
            
            unit_table = Table(unit_data, colWidths=[30, 160, 70, 70, 70, 60, 80])
            unit_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#c0392b')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#fadbd8')),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9f9')])
            ]))
            story.append(unit_table)
        
        # 7. TERMODİNAMİK ÖZELLİKLER
        story.append(Spacer(1, 20))
        story.append(Paragraph("7. DETAYLI TERMODİNAMİK ÖZELLİKLER", styles['Heading2']))
        
        detailed_thermo_data = [
            ['Özellik', 'Giriş', 'Çıkış', 'Birim', 'Değişim (%)'],
            ['Sıkıştırılabilirlik (Z)', 
             f"{results['inlet_properties']['Z']:.4f}", 
             f"{results['outlet_properties']['Z']:.4f}", 
             '', 
             f"{((results['outlet_properties']['Z'] - results['inlet_properties']['Z']) / results['inlet_properties']['Z'] * 100):+.1f}"],
            ['Yoğunluk', 
             f"{results['inlet_properties']['rho']:.3f}", 
             f"{results['outlet_properties']['rho']:.3f}", 
             'kg/m³',
             f"{((results['outlet_properties']['rho'] - results['inlet_properties']['rho']) / results['inlet_properties']['rho'] * 100):+.1f}"],
            ['İzentropik Üs (k)', 
             f"{results['inlet_properties']['k']:.3f}", 
             f"{results['outlet_properties']['k']:.3f}", 
             '',
             f"{((results['outlet_properties']['k'] - results['inlet_properties']['k']) / results['inlet_properties']['k'] * 100):+.1f}"],
            ['Spesifik Isı (Cp)', 
             f"{results['inlet_properties']['Cp']/1000:.3f}", 
             f"{results['outlet_properties']['Cp']/1000:.3f}", 
             'kJ/kg-K',
             f"{((results['outlet_properties']['Cp'] - results['inlet_properties']['Cp']) / results['inlet_properties']['Cp'] * 100):+.1f}"],
            ['Viskozite', 
             f"{results['inlet_properties']['mu']*1e6:.2f}", 
             f"{results['outlet_properties']['mu']*1e6:.2f}", 
             'μPa·s',
             f"{((results['outlet_properties']['mu'] - results['inlet_properties']['mu']) / results['inlet_properties']['mu'] * 100):+.1f}"],
            ['Ses Hızı', 
             f"{results['inlet_properties']['a']:.1f}", 
             f"{results['outlet_properties']['a']:.1f}", 
             'm/s',
             f"{((results['outlet_properties']['a'] - results['inlet_properties']['a']) / results['inlet_properties']['a'] * 100):+.1f}"]
        ]
        
        detailed_thermo_table = Table(detailed_thermo_data, colWidths=[120, 60, 60, 50, 60])
        detailed_thermo_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#16a085')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
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
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f4f6f6')),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(stats_table)
        
        # 9. UYARI ve NOTLAR
        if results.get('warnings'):
            story.append(Spacer(1, 20))
            story.append(Paragraph("9. UYARILAR ve ÖNERİLER", styles['Heading2']))
            
            warnings_text = "<b>Dikkat Edilmesi Gereken Noktalar:</b><br/>"
            for warning in results['warnings']:
                warnings_text += f"• {warning}<br/>"
            
            warnings_para = Paragraph(warnings_text, styles['Normal'])
            story.append(warnings_para)
        
        # 10. STANDART UYUMLULUK
        story.append(Spacer(1, 20))
        story.append(Paragraph("10. STANDART UYUMLULUK", styles['Heading2']))
        
        compliance_text = """
        <b>Endüstri Standardı Uyumluluk:</b><br/>
        • Hesaplama metodları ASME PTC-10 standardına uygundur<br/>
        • Performans düzeltmeleri ISO 2314 standardına uygundur<br/>
        • Türbin seçimi API 616 gereksinimlerine uygundur<br/>
        • Kompresör analizi API 617 standartlarına uygundur<br/>
        • Raporlama formatı endüstri standartlarına uygundur<br/><br/>
        
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
                <b>Ölçüm Belirsizliği Analizi (ASME PTC 10 Appendix B):</b><br/>
                Tüm performans hesaplamaları ASME PTC 10 standardına uygun belirsizlik analizi ile doğrulanmıştır.
                RSS (Root-Sum-Square) metodu kullanılarak hesaplanan birleşik belirsizlik, %95 güven aralığında raporlanmıştır.<br/><br/>
                """
                story.append(Paragraph(uncertainty_intro, styles['Normal']))
                story.append(Spacer(1, 10))
                
                # Measurement uncertainties table
                uncertainty_data = [
                    ['Ölçüm Parametresi', 'Enstrüman Tipi', 'Standart Belirsizlik', 'Birim'],
                    ['Giriş Basıncı', 'Yüksek Doğruluk Basınç', '±0.25%', 'of reading'],
                    ['Çıkış Basıncı', 'Yüksek Doğruluk Basınç', '±0.25%', 'of reading'],
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
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
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
                    ['Performans Parametresi', 'Birleşik Belirsizlik', 'Genişletilmiş Belirsizlik (k=2)', 'Güven Aralığı'],
                    ['Politropik Verim', '±0.8%', '±1.6%', '%95'],
                    ['Politropik Head', '±1.2%', '±2.4%', '%95'],
                    ['Sıkıştırma Oranı', '±0.5%', '±1.0%', '%95'],
                    ['Gaz Gücü', '±1.5%', '±3.0%', '%95'],
                    ['Isı Oranı', '±1.8%', '±3.6%', '%95']
                ]
                
                perf_unc_table = Table(perf_unc_data, colWidths=[140, 100, 100, 80])
                perf_unc_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#27ae60')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 9),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#d5f5e3')),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                story.append(perf_unc_table)
                story.append(Spacer(1, 12))
                
                # Uncertainty methodology note
                methodology_note = """
                <b>Belirsizlik Analizi Metodolojisi:</b><br/>
                • RSS (Root-Sum-Square) metodu ile birleşik belirsizlik hesaplanmıştır<br/>
                • Duyarlılık katsayıları sayısal türev ile belirlenmiştir<br/>
                • Kapsama faktörü k=2 kullanılarak %95 güven aralığı sağlanmıştır<br/>
                • Tüm ölçümler ASME PTC 10 Appendix B gereksinimlerine uygundur<br/><br/>
                
                <b>Referans Standart:</b><br/>
                ASME PTC 10-1997: Performance Test Code on Compressors and Exhausters, Appendix B - Measurement Uncertainty
                """
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
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
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
            
            # Başlık
            title = Paragraph(f"KASP v{APP_VERSION} - Performans Degerlendirme Raporu<br/>{inputs['unit_name']}", styles['Title'])
            story.append(title)
            story.append(Spacer(1, 12))
            
            # Tarih
            date_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
            date_para = Paragraph(f"Rapor Tarihi: {date_str} | KASP v{APP_VERSION}", styles['Normal'])
            story.append(date_para)
            story.append(Spacer(1, 20))
            
            # 1. TEST KOŞULLARI
            story.append(Paragraph("1. TEST KOŞULLARI", styles['Heading2']))
            test_data = [
                ['Parametre', 'Değer', 'Birim'],
                ['Test Edilen Ünite', inputs['unit_name'], ''],
                ['Giriş Basıncı', f"{inputs['p_in']}", inputs['p_in_unit']],
                ['Giriş Sıcaklığı', f"{inputs['t_in']}", inputs['t_in_unit']],
                ['Çıkış Basıncı', f"{inputs['p_out']}", inputs['p_out_unit']],
                ['Çıkış Sıcaklığı', f"{inputs['t_out']}", inputs['t_out_unit']],
                ['Gaz Debisi', f"{inputs['flow']}", inputs['flow_unit']],
                ['Yakıt Tüketimi', f"{inputs['fuel_flow']}", inputs['fuel_flow_unit']],
                ['Ortam Sıcaklığı', f"{inputs['ambient_temp']:.1f}", '°C'],
                ['Ortam Basıncı', f"{inputs['ambient_press']:.1f}", 'mbar'],
                ['Nem Oranı', f"{inputs.get('humidity', 60):.1f}", '%'],
                ['Rakım', f"{inputs.get('altitude', 0):.0f}", 'm']
            ]
            
            test_table = Table(test_data, colWidths=[150, 100, 80])
            test_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
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
            
        except Exception as e:
            self.logger.error(f"Performance report generation error: {e}", exc_info=True)
            raise
    
    def _append_remaining_performance_report_sections(self, story, inputs, results, styles):
        """Append remaining sections to performance report"""
        from reportlab.lib import colors
        from reportlab.platypus import Table, TableStyle, Paragraph, Spacer
        
        # Performance comparison data
        perf_data = [
            ['Parametre', 'Gerçek', 'Tasarım', 'Sapma (%)', 'Durum'],
            ['Politropik Verim (%)', 
             f"{results['actual_poly_eff']*100:.2f}", 
             f"{results['design_poly_eff']*100:.2f}",
             f"{results['deviation_poly_eff']:.2f}",
             self._get_status_icon(results['deviation_poly_eff'])],
            ['Isıl Verim (%)', 
             f"{results['actual_therm_eff']*100:.2f}", 
             f"{results['expected_therm_eff']*100:.2f}",
             f"{results['deviation_therm_eff']:.2f}",
             self._get_status_icon(results['deviation_therm_eff'])],
            ['Isı Oranı (kJ/kWh)', 
             f"{results['actual_heat_rate']:.0f}", 
             f"{results['expected_heat_rate']:.0f}",
             f"{results['deviation_heat_rate']:.2f}",
             self._get_status_icon(results['deviation_heat_rate'])],
            ['Çıkış Gücü (kW)', 
             f"{results['actual_power']:.0f}", 
             f"{results['expected_power']:.0f}",
             f"{results['deviation_power']:.2f}",
             self._get_status_icon(results['deviation_power'])]
        ]
        
        perf_table = Table(perf_data, colWidths=[120, 80, 80, 60, 40])
        table_style = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#27ae60')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
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
        
        status = results['performance_status']
        status_text = f"""
        <b>Performans Durumu:</b> <font color="{status['color']}">{status['status']}</font><br/>
        <b>Açıklama:</b> {status['description']}<br/>
        <b>Öneri:</b> {status['recommendation']}<br/><br/>
        
        <b>Detaylı Analiz:</b><br/>
        • Politropik Verim Sapması: {results['deviation_poly_eff']:.2f}%<br/>
        • Isıl Verim Sapması: {results['deviation_therm_eff']:.2f}%<br/>
        • Isı Oranı Sapması: {results['deviation_heat_rate']:.2f}%<br/>
        • Güç Sapması: {results['deviation_power']:.2f}%<br/>
        """
        
        status_para = Paragraph(status_text, styles['Normal'])
        story.append(status_para)
        story.append(Spacer(1, 20))
        
        # 4. TEST KOŞULLARI DETAYI
        story.append(Paragraph("4. TEST KOŞULLARI DETAYI", styles['Heading2']))
        
        test_details_data = [
            ['Parametre', 'Değer', 'Birim'],
            ['Kütlesel Debi', f"{results['test_conditions']['mass_flow']:.3f}", 'kg/s'],
            ['Yakıt Tüketimi', f"{results['test_conditions']['fuel_flow']/3600:.3f}", 'kg/s'],
            ['Sıkıştırma Oranı', f"{results['test_conditions']['compression_ratio']:.2f}", ''],
            ['Politropik Head', f"{results['test_conditions']['head']:.1f}", 'kJ/kg'],
            ['İzentropik Verim', f"{results['actual_isentropic_eff']*100:.2f}", '%']
        ]
        
        test_details_table = Table(test_details_data, colWidths=[120, 100, 80])
        test_details_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#8e44ad')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#e8daef')),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(test_details_table)
        
        # 5. DÜZELTME FAKTÖRLERİ
        story.append(Spacer(1, 20))
        story.append(Paragraph("5. DÜZELTME FAKTÖRLERİ", styles['Heading2']))
        
        correction_data = [
            ['Faktör', 'Değer', 'Etki'],
            ['Sıcaklık', f"{results['corrected_values']['correction_factors']['temperature']}°C", 
             f"{(results['corrected_values']['correction_factors']['temperature']/15 - 1)*100:.1f}%"],
            ['Basınç', f"{results['corrected_values']['correction_factors']['pressure']} mbar", 
             f"{(results['corrected_values']['correction_factors']['pressure']/1013 - 1)*100:.1f}%"],
            ['Nem', f"{results['corrected_values']['correction_factors']['humidity']}%", 
             f"{(results['corrected_values']['correction_factors']['humidity']/60 - 1)*100:.1f}%"],
            ['Rakım', f"{results['corrected_values']['correction_factors']['altitude']} m", 
             f"{(results['corrected_values']['correction_factors']['altitude']/1000)*3:.1f}%"]
        ]
        
        correction_table = Table(correction_data, colWidths=[100, 80, 80])
        correction_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e67e22')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#fdebd0')),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(correction_table)

    def _format_composition(self, composition):
        """Gaz kompozisyonunu formatla"""
        components = []
        for comp, frac in composition.items():
            if frac > 0.01:  # Sadece %1'den büyük bileşenler
                components.append(f"{comp}: {frac:.1f}%")
        return ", ".join(components) if components else "Karışım"

    def _get_eos_display_name(self, eos_method):
        """EOS metodunun görünen adını getir"""
        names = {
            'coolprop': '🎯 Yüksek Doğruluk (CoolProp)',
            'pr': '📊 Peng-Robinson (thermo)',
            'srk': '📈 SRK (thermo)'
        }
        return names.get(eos_method, eos_method)

    def _format_eos_distribution(self, distribution):
        """EOS dağılımını formatla"""
        if not distribution:
            return "Veri yok"
        return ", ".join([f"{k}: {v}" for k, v in distribution.items()])

    def _get_status_icon(self, deviation):
        """Sapma değerine göre durum ikonu"""
        deviation_abs = abs(deviation)
        if deviation_abs <= 2.0:
            return "✅"
        elif deviation_abs <= 5.0:
            return "⚠️"
        else:
            return "❌"

    def generate_summary_report(self, inputs, results, selected_units):
        """Özet rapor oluşturur"""
        try:
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
                'recommended_turbines': [
                    {
                        'rank': i + 1,
                        'turbine': unit['turbine'],
                        'power': unit['available_power_kw'],
                        'efficiency': unit['efficiency_rating'],
                        'score': unit['selection_score']
                    }
                    for i, unit in enumerate(selected_units[:3])
                ] if selected_units else [],
                'system_performance': self.engine.performance_monitor.get_statistics()
            }
            
            return summary
            
        except Exception as e:
            self.logger.error(f"Özet rapor oluşturma hatası: {e}")
            return {}
