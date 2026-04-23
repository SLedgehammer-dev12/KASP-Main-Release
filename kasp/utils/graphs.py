import logging
import numpy as np

try:
    import matplotlib
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    import matplotlib.pyplot as plt
    MATPLOTLIB_LOADED = True
except ImportError:
    MATPLOTLIB_LOADED = False
    from PyQt5.QtWidgets import QWidget as FigureCanvas

from PyQt5.QtWidgets import QVBoxLayout, QLabel
from PyQt5.QtCore import Qt

class MplCanvas(FigureCanvas):
    """Matplotlib canvas sınıfı"""
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        if MATPLOTLIB_LOADED:
            self.fig = Figure(figsize=(width, height), dpi=dpi)
            super(MplCanvas, self).__init__(self.fig)
            self.setParent(parent)
        else:
            super(MplCanvas, self).__init__(parent)
            self.layout = QVBoxLayout(self)
            warning_label = QLabel("Grafik Modülü Yüklenemedi.\nMatplotlib kütüphanesi kurulu değil.")
            warning_label.setAlignment(Qt.AlignCenter)
            warning_label.setStyleSheet("color: red; font-weight: bold;")
            self.layout.addWidget(warning_label)

class GraphGenerator:
    """Grafik oluşturma sınıfı"""
    
    def __init__(self, engine):
        self.engine = engine
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def create_cache_performance_chart(self, cache_stats):
        """Önbellek performans grafiği"""
        if not MATPLOTLIB_LOADED:
            return None
            
        try:
            canvas = MplCanvas(width=8, height=6)
            fig = canvas.fig
            
            # Çoklu grafik
            ax1 = fig.add_subplot(121)
            ax2 = fig.add_subplot(122)
            
            # Önbellek isabet oranı
            labels = ['İsabet', 'Kaçırma']
            sizes = [cache_stats['hits'], cache_stats['misses']]
            colors = ['#2ecc71', '#e74c3c']
            
            ax1.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)
            ax1.set_title('Önbellek İsabet Oranı', fontweight='bold')
            
            # Önbellek kullanımı
            cache_usage = cache_stats['size'] / cache_stats['max_size'] * 100
            ax2.bar(['Kullanım'], [cache_usage], color='#3498db', alpha=0.7)
            ax2.set_ylabel('Kullanım (%)', fontweight='bold')
            ax2.set_title('Önbellek Kullanımı', fontweight='bold')
            ax2.set_ylim(0, 100)
            
            # Değer etiketi
            ax2.text(0, cache_usage + 2, f'{cache_usage:.1f}%', 
                    ha='center', va='bottom', fontweight='bold')
            
            fig.suptitle('Önbellek Performans İstatistikleri', fontsize=14, fontweight='bold')
            fig.tight_layout()
            
            return canvas
            
        except Exception as e:
            self.logger.error(f"Önbellek performans grafiği hatası: {e}")
            return None

    def create_ts_diagram(self, inputs, results, gas_composition, eos_method):
        """T-s (Sıcaklık-Entropi) diyagramı oluşturur"""
        if not MATPLOTLIB_LOADED:
            return None
            
        try:
            canvas = MplCanvas(width=8, height=6)
            fig = canvas.fig
            ax = fig.add_subplot(111)
            
            # Gaz objesi oluştur
            gas_obj = self.engine._create_gas_object(gas_composition, eos_method)
            
            # Basınç değerleri
            p_in_pa = self.engine.convert_pressure_to_pa(float(inputs['p_in']), inputs['p_in_unit'])
            p_out_pa = self.engine.convert_pressure_to_pa(float(inputs['p_out']), inputs['p_out_unit'])
            t_in_k = self.engine.convert_temperature_to_k(float(inputs['t_in']), inputs['t_in_unit'])
            
            # Entropi değerleri
            props_in = self.engine.thermo_solver.get_properties(p_in_pa, t_in_k, gas_obj, eos_method)
            
            # İzentropik çıkış sıcaklığı
            from kasp.core.aerodynamics import CompressorAerodynamics
            t_out_isen_k = CompressorAerodynamics.calculate_isentropic_outlet_temp(
                props_in, p_out_pa, self.engine.thermo_solver, gas_obj, eos_method
            )
            t_out_actual_k = results['t_out'] + 273.15 # Gerçek çıkış sıcaklığı (K)
            
            props_out_isen = self.engine.thermo_solver.get_properties(p_out_pa, t_out_isen_k, gas_obj, eos_method)
            props_out_actual = self.engine.thermo_solver.get_properties(p_out_pa, t_out_actual_k, gas_obj, eos_method)
            
            s_in = props_in.S / 1000  # kJ/kg-K (ThermodynamicState OBJ)
            s_out_isen = props_out_isen.S / 1000
            s_out_actual = props_out_actual.S / 1000
            
            # T-s eğrisi için veri noktaları (basitleştirilmiş)
            s_min = min(s_in, s_out_actual) - 0.05
            s_max = max(s_in, s_out_actual) + 0.05
            s_range = np.linspace(s_min, s_max, 50)
            
            # İzentropik proses çizgisi (Sabit Entropi)
            t_isen_values = np.linspace(t_in_k - 273.15, t_out_isen_k - 273.15, 20)
            s_isen_line = [s_in] * 20
            
            # Gerçek proses çizgisi (Gerçek politropik eğri hesabı)
            pressures = np.geomspace(p_in_pa, p_out_pa, 20)
            t_actual_values = []
            s_actual_values = []
            
            poly_eff_frac = inputs['poly_eff'] / 100.0
            k_val = props_in.k if props_in.k > 1.0 else 1.4
            n_minus_1_over_n = (k_val - 1) / (k_val * poly_eff_frac)
            
            for p in pressures:
                t_k_path = t_in_k * (p / p_in_pa) ** n_minus_1_over_n
                try:
                    props = self.engine.thermo_solver.get_properties(p, t_k_path, gas_obj, eos_method)
                    t_actual_values.append(t_k_path - 273.15)
                    s_actual_values.append(props.S / 1000)
                except Exception:
                    # Hata varsa lineer yaklaşımla devam et
                    pass
            
            # Eğer hesaplama başarısız olduysa lineer geri dönüş (fallback)
            if len(t_actual_values) < 2:
                t_actual_values = np.linspace(t_in_k - 273.15, t_out_actual_k - 273.15, 20)
                s_actual_values = np.linspace(s_in, s_out_actual, 20)

            
            # Grafik çizimi
            ax.plot(s_isen_line, t_isen_values, 'r--', linewidth=2, label='İzentropik Proses (Basit)', alpha=0.7)
            ax.plot(s_actual_values, t_actual_values, 'b-', linewidth=2, label='Gerçek Proses', alpha=0.8)
            
            # Noktalar
            ax.plot(s_in, t_in_k - 273.15, 'go', markersize=8, label='Giriş')
            ax.plot(s_out_isen, t_out_isen_k - 273.15, 'ro', markersize=8, label='İzentropik Çıkış')
            ax.plot(s_out_actual, t_out_actual_k - 273.15, 'bo', markersize=8, label='Gerçek Çıkış')
            
            # Eksenler ve başlık
            ax.set_xlabel('Entropi (kJ/kg·K)', fontsize=12, fontweight='bold')
            ax.set_ylabel('Sıcaklık (°C)', fontsize=12, fontweight='bold')
            ax.set_title('T-s Diyagramı - Kompresör Prosesi', fontsize=14, fontweight='bold')
            
            # Grid ve legend
            ax.grid(True, alpha=0.3)
            ax.legend(loc='best')
            
            # Verimlilik bilgisi
            if (t_out_actual_k - t_in_k) > 0:
                isen_efficiency = ((t_out_isen_k - t_in_k) / (t_out_actual_k - t_in_k)) * 100
                text_str = f'İzentropik Verim: {isen_efficiency:.1f}%'
                ax.text(0.05, 0.95, text_str, transform=ax.transAxes, fontsize=10,
                    verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
            
            fig.tight_layout()
            return canvas
            
        except Exception as e:
            self.logger.error(f"T-s diyagramı oluşturma hatası: {e}")
            return None

    def create_pv_diagram(self, inputs, results, gas_composition, eos_method):
        """P-v (Basınç-Hacim) diyagramı oluşturur"""
        if not MATPLOTLIB_LOADED:
            return None
        
        try:
            canvas = MplCanvas(width=8, height=6)
            fig = canvas.fig
            ax = fig.add_subplot(111)
            
            gas_obj = self.engine._create_gas_object(gas_composition, eos_method)
            
            # Basınç değerleri
            p_in_pa = self.engine.convert_pressure_to_pa(float(inputs['p_in']), inputs['p_in_unit'])
            p_out_pa = self.engine.convert_pressure_to_pa(float(inputs['p_out']), inputs['p_out_unit'])
            t_in_k = self.engine.convert_temperature_to_k(float(inputs['t_in']), inputs['t_in_unit'])
            t_out_k = self.engine.convert_temperature_to_k(results['t_out'], '°C')
            
            # Hacim değerleri
            props_in = self.engine.thermo_solver.get_properties(p_in_pa, t_in_k, gas_obj, eos_method)
            props_out = self.engine.thermo_solver.get_properties(p_out_pa, t_out_k, gas_obj, eos_method)
            
            v_in = 1 / props_in.density  # m³/kg
            v_out = 1 / props_out.density
            
            # Politropik proses eğrisi
            pressures = np.geomspace(p_in_pa, p_out_pa, 50)
            volumes = []
            
            for p in pressures:
                try:
                    # Politropik ilişki: P * v^n = sabit
                    poly_eff_frac = inputs['poly_eff'] / 100.0
                    n_minus_1_over_n = (props_in.k - 1) / (props_in.k * poly_eff_frac)
                    n = 1 / (1 - n_minus_1_over_n) if abs(n_minus_1_over_n) > 1e-6 else props_in.k 
                    v = v_in * (p_in_pa / p) ** (1/n)
                    volumes.append(v)
                except:
                    volumes.append(np.nan)
            
            # İzentropik proses eğrisi
            volumes_isen = []
            for p in pressures:
                try:
                    # İzentropik ilişki: P * v^k = sabit
                    v = v_in * (p_in_pa / p) ** (1/props_in.k)
                    volumes_isen.append(v)
                except:
                    volumes_isen.append(np.nan)
            
            # Grafik çizimi
            ax.plot([v * 1000 for v in volumes], [p / 1000 for p in pressures], 
                   'b-', linewidth=2, label='Politropik Proses')
            ax.plot([v * 1000 for v in volumes_isen], [p / 1000 for p in pressures], 
                   'r--', linewidth=2, label='İzentropik Proses', alpha=0.7)
            
            # Noktalar
            ax.plot(v_in * 1000, p_in_pa / 1000, 'go', markersize=8, label='Giriş')
            ax.plot(v_out * 1000, p_out_pa / 1000, 'ro', markersize=8, label='Çıkış')
            
            # Eksenler ve başlık
            ax.set_xlabel('Spesifik Hacim (L/kg)', fontsize=12, fontweight='bold')
            ax.set_ylabel('Basınç (kPa)', fontsize=12, fontweight='bold')
            ax.set_title('P-v Diyagramı - Kompresör Prosesi', fontsize=14, fontweight='bold')
            
            # Log scale for better visualization
            ax.set_yscale('log')
            ax.set_xscale('log')
            
            ax.grid(True, alpha=0.3)
            ax.legend(loc='best')
            
            # İş bilgisi
            work_poly = results['head_kj_kg']
            text_str = f'Politropik İş: {work_poly:.1f} kJ/kg'
            ax.text(0.05, 0.95, text_str, transform=ax.transAxes, fontsize=10,
                   verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
            
            fig.tight_layout()
            return canvas
            
        except Exception as e:
            self.logger.error(f"P-v diyagramı oluşturma hatası: {e}")
            return None

    def create_performance_chart(self, selected_units):
        """Performans karşılaştırma grafiği"""
        if not MATPLOTLIB_LOADED or not selected_units:
            return None
            
        try:
            canvas = MplCanvas(width=10, height=6)
            fig = canvas.fig
            
            # Verileri hazırla
            turbines = [f"{unit.manufacturer}\n{unit.model}" for unit in selected_units]
            powers = [unit.available_power_kw for unit in selected_units]
            heat_rates = [unit.site_heat_rate for unit in selected_units]
            scores = [unit.selection_score for unit in selected_units]
            colors = ['#2ecc71', '#3498db', '#e74c3c', '#f39c12', '#9b59b6']
            
            # Çoklu grafik
            ax1 = fig.add_subplot(131)
            bars = ax1.bar(turbines, powers, color=colors[:len(turbines)], alpha=0.7)
            ax1.set_ylabel('Güç (kW)', fontweight='bold')
            ax1.set_title('Mevcut Güç', fontweight='bold')
            ax1.tick_params(axis='x', rotation=45)
            
            # Değerleri çubukların üzerine yaz
            for bar, power in zip(bars, powers):
                height = bar.get_height()
                ax1.text(bar.get_x() + bar.get_width()/2., height + 100,
                        f'{power:.0f}', ha='center', va='bottom', fontweight='bold')
            
            ax2 = fig.add_subplot(132)
            bars2 = ax2.bar(turbines, heat_rates, color=colors[:len(turbines)], alpha=0.7)
            ax2.set_ylabel('Isı Oranı (kJ/kWh)', fontweight='bold')
            ax2.set_title('Isı Oranı', fontweight='bold')
            ax2.tick_params(axis='x', rotation=45)
            
            for bar, hr in zip(bars2, heat_rates):
                height = bar.get_height()
                ax2.text(bar.get_x() + bar.get_width()/2., height + 100,
                        f'{hr:.0f}', ha='center', va='bottom', fontweight='bold')
            
            ax3 = fig.add_subplot(133)
            bars3 = ax3.bar(turbines, scores, color=colors[:len(turbines)], alpha=0.7)
            ax3.set_ylabel('Seçim Puanı', fontweight='bold')
            ax3.set_title('Seçim Puanı', fontweight='bold')
            ax3.tick_params(axis='x', rotation=45)
            
            for bar, score in zip(bars3, scores):
                height = bar.get_height()
                ax3.text(bar.get_x() + bar.get_width()/2., height + 2,
                        f'{score:.1f}', ha='center', va='bottom', fontweight='bold')
            
            fig.suptitle('Türbin Performans Karşılaştırması', fontsize=16, fontweight='bold')
            fig.tight_layout()
            
            return canvas
            
        except Exception as e:
            self.logger.error(f"Performans grafiği oluşturma hatası: {e}")
            return None

    def create_convergence_plot(self, consistency_history):
        """Yakınsama grafiği"""
        if not MATPLOTLIB_LOADED or not consistency_history:
            return None
            
        try:
            canvas = MplCanvas(width=8, height=6)
            fig = canvas.fig
            ax = fig.add_subplot(111)
            
            if not consistency_history or not isinstance(consistency_history, list) or len(consistency_history) < 2:
                ax.text(0.5, 0.5, "Yakınsama Verisi Yetersiz", 
                        transform=ax.transAxes, ha='center', va='center')
                fig.tight_layout()
                return canvas
            
            iterations = [hist.get('iteration', i) for i, hist in enumerate(consistency_history)]
            temperatures = [hist.get('t_out', 0) for hist in consistency_history]
            
            # Sıcaklık yakınsaması
            if temperatures:
                # Zaten 't_out' °C cinsindeydi (273.15 çıkarmaya gerek yok)
                temp_history = [t for i, t in zip(iterations, temperatures) if i > 0]
                iter_points = [i for i in iterations if i > 0]
                
                # Giriş sıcaklığını referans olarak ekle
                temp_base = temperatures[0] - 273.15
                
                # İterasyon farkını çiz (Yakınsama hızı)
                temp_diffs = [abs(temp_history[i] - temp_history[i-1]) for i in range(1, len(temp_history))]
                
                ax.plot(iter_points[1:], temp_diffs, 'b-o', linewidth=2, 
                       markersize=4, label='T Farkı (K)')
                
                # İkinci eksen (Sıcaklık değeri)
                ax2 = ax.twinx()
                ax2.plot(iter_points, temp_history, 'g--', linewidth=1, label='Çıkış Sıcaklığı (°C)', alpha=0.7)
                ax2.legend(loc='lower right')
                ax2.set_ylabel('Sıcaklık (°C)', fontweight='bold', color='green')
            
            ax.set_xlabel('İterasyon', fontweight='bold')
            ax.set_ylabel('Ardışık T Farkı (K)', fontweight='bold', color='blue')
            ax.set_title('Hesaplama Yakınsaması (T-farkı)', fontweight='bold')
            ax.legend(loc='upper right')
            ax.grid(True, alpha=0.3)
            
            # Yakınsama bilgisi
            if len(temperatures) > 1:
                final_diff = abs(temperatures[-1] - temperatures[-2])
                ax.text(0.05, 0.95, f'Son Fark: {final_diff:.2e} K', transform=ax.transAxes,
                       bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
            
            fig.tight_layout()
            return canvas
            
        except Exception as e:
            self.logger.error(f"Yakınsama grafiği oluşturma hatası: {e}")
            return None

    def create_power_breakdown_chart(self, results):
        """Güç dağılım grafiği"""
        if not MATPLOTLIB_LOADED:
            return None
            
        try:
            canvas = MplCanvas(width=8, height=6)
            fig = canvas.fig
            ax = fig.add_subplot(111)
            
            # Güç bileşenleri
            power_gas = results.get('power_gas_per_unit_kw', 0)
            power_shaft = results.get('power_shaft_per_unit_kw', 0)
            power_unit = results.get('power_unit_kw', 0)
            
            # Güç Kaybı = Şaft Gücü - Gaz Gücü (Polytropik kayıp)
            poly_loss = power_shaft - power_gas
            # Motor Elektriksel/Isıl Kayıp (Motor Gücü - Şaft Gücü)
            mech_loss = power_unit - power_shaft
            
            if power_unit <= 0:
                ax.text(0.5, 0.5, "Güç Hesaplaması Sıfır", 
                        transform=ax.transAxes, ha='center', va='center')
                fig.tight_layout()
                return canvas
            
            # Veriler
            sizes = [power_gas, poly_loss, mech_loss]
            labels = [
                f'Gaz Gücü (Faydalı)\n{power_gas:.0f} kW', 
                f'Kompresör Kaybı (Termo)\n{poly_loss:.0f} kW',
                f'Motor Kaybı (Mekanik/Isıl)\n{mech_loss:.0f} kW'
            ]
            colors = ['#2ecc71', '#f1c40f', '#e74c3c']
            explode = (0.05, 0, 0) 
            
            # Pasta grafik
            wedges, texts, autotexts = ax.pie(sizes, explode=explode, labels=labels, colors=colors,
                                            autopct='%1.1f%%', shadow=True, startangle=90)
            
            # Yazı stilleri
            for autotext in autotexts:
                autotext.set_color('black')
                autotext.set_fontweight('bold')
            
            ax.set_title('Gereken Motor Gücü Dağılımı - Ünite Başına', fontweight='bold')
            ax.text(0.05, 0.05, f'Toplam Gerekli Motor Gücü: {power_unit:.0f} kW', 
                    transform=ax.transAxes, fontsize=10, bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
            fig.tight_layout()
            return canvas
            
        except Exception as e:
            self.logger.error(f"Güç dağılım grafiği hatası: {e}")
            return None

class GraphManager:
    """Grafik yönetim sınıfı"""
    
    def __init__(self, engine):
        self.generator = GraphGenerator(engine)
        self.current_graphs = {}
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def generate_all_graphs(self, inputs, results, selected_units=None):
        """Tüm grafikleri oluştur"""
        graphs = {}
        
        try:
            # T-s diyagramı
            graphs['ts_diagram'] = self.generator.create_ts_diagram(
                inputs, results, inputs['gas_comp'], inputs['eos_method']
            )
            
            # P-v diyagramı
            graphs['pv_diagram'] = self.generator.create_pv_diagram(
                inputs, results, inputs['gas_comp'], inputs['eos_method']
            )
            
            # Güç dağılımı
            graphs['power_breakdown'] = self.generator.create_power_breakdown_chart(results)
            
            # Yakınsama grafiği
            if 'consistency_history' in results:
                graphs['convergence'] = self.generator.create_convergence_plot(
                    results['consistency_history']
                )
            
            # Türbin performansı
            if selected_units:
                graphs['performance_comparison'] = self.generator.create_performance_chart(selected_units)
            
            # Önbellek performansı
            cache_stats = self.generator.engine.thermo_solver.get_cache_stats()
            graphs['cache_performance'] = self.generator.create_cache_performance_chart(cache_stats)
            
            self.current_graphs = graphs
            self.logger.info(f"{len(graphs)} grafik başarıyla oluşturuldu")
            
        except Exception as e:
            self.logger.error(f"Grafik oluşturma hatası: {e}")
        
        return graphs
    
    def save_graphs_to_file(self, base_filename):
        """Grafikleri dosyaya kaydet"""
        try:
            if not MATPLOTLIB_LOADED:
                 self.logger.warning("Matplotlib yüklü değil, grafik kaydedilemiyor.")
                 return False
                 
            for name, graph in self.current_graphs.items():
                if graph and hasattr(graph, 'fig'):
                    filename = f"{base_filename}_{name}.png"
                    graph.fig.savefig(filename, dpi=300, bbox_inches='tight', 
                                    facecolor='white', edgecolor='none')
                    self.logger.info(f"Grafik kaydedildi: {filename}")
            
            return True
        except Exception as e:
            self.logger.error(f"Grafik kaydetme hatası: {e}")
            return False
    
    def clear_graphs(self):
        """Grafikleri temizle"""
        if MATPLOTLIB_LOADED:
            for graph in self.current_graphs.values():
                if graph and hasattr(graph, 'fig'):
                    plt.close(graph.fig)
        self.current_graphs = {}
        self.logger.info("Grafikler temizlendi")
