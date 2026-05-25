import logging
import numpy as np

try:
    import matplotlib
    matplotlib.use("Qt5Agg")
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    import matplotlib.pyplot as plt
    MATPLOTLIB_LOADED = True
    MATPLOTLIB_IMPORT_ERROR = None
except ImportError as import_error:
    MATPLOTLIB_LOADED = False
    MATPLOTLIB_IMPORT_ERROR = import_error
    from PyQt5.QtWidgets import QWidget as FigureCanvas

from PyQt5.QtWidgets import QVBoxLayout, QLabel
from PyQt5.QtCore import Qt

class MplCanvas(FigureCanvas):
    """DPI-aware Matplotlib canvas with responsive resize."""

    def __init__(self, parent=None, width=8, height=5, dpi=None):
        if dpi is None:
            try:
                from kasp.ui.responsive import get_dpi
                dpi = int(get_dpi())
            except Exception:
                dpi = 100
        if MATPLOTLIB_LOADED:
            self.fig = Figure(figsize=(width, height), dpi=dpi)
            FigureCanvas.__init__(self, self.fig)
            self.setParent(parent)
            self._default_size = (width, height)
        else:
            FigureCanvas.__init__(self, parent)
            self.layout = QVBoxLayout(self)
            warning_label = QLabel("Grafik Modülü Yüklenemedi.\nMatplotlib kütüphanesi kurulu değil.")
            warning_label.setAlignment(Qt.AlignCenter)
            warning_label.setStyleSheet("color: red; font-weight: bold;")
            self.layout.addWidget(warning_label)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not MATPLOTLIB_LOADED or not hasattr(self, "fig"):
            return
        w_px = event.size().width()
        h_px = event.size().height()
        if w_px < 50 or h_px < 50:
            return
        dpi = self.fig.get_dpi()
        self.fig.set_size_inches(w_px / dpi, h_px / dpi, forward=True)
        self.draw_idle()

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
            self.logger.exception(f"T-s diyagramı oluşturma hatası: {e}")
            import sys; print(f"GRAPH ERROR (ts): {e}", file=sys.stderr)
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
            self.logger.exception(f"P-v diyagramı oluşturma hatası: {e}")
            import sys; print(f"GRAPH ERROR (pv): {e}", file=sys.stderr)
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

    # -----------------------------------------------------------------
    # YENİ GRAFİKLER (V4.7)
    # -----------------------------------------------------------------

    def create_hs_mollier_diagram(self, inputs, results, composition, eos_method):
        """H-S (Mollier) diyagramı — endüstri standardı."""
        if not MATPLOTLIB_LOADED:
            return None
        try:
            canvas = MplCanvas(width=8, height=6)
            ax = canvas.fig.add_subplot(111)

            gas_obj = self.engine._create_gas_object(composition, eos_method)
            p_in_pa = self.engine.convert_pressure_to_pa(float(inputs["p_in"]), inputs["p_in_unit"])
            p_out_pa = self.engine.convert_pressure_to_pa(float(inputs["p_out"]), inputs["p_out_unit"])
            t_in_k = self.engine.convert_temperature_to_k(float(inputs["t_in"]), inputs["t_in_unit"])
            t_out_k = results["t_out"] + 273.15

            state_in = self.engine.thermo_solver.get_properties(p_in_pa, t_in_k, gas_obj, eos_method)
            h1 = state_in.H / 1000.0
            s1 = state_in.S / 1000.0

            from kasp.core.aerodynamics import CompressorAerodynamics
            t_isen_k = CompressorAerodynamics.calculate_isentropic_outlet_temp(
                state_in, p_out_pa, self.engine.thermo_solver, gas_obj, eos_method
            )
            state_isen = self.engine.thermo_solver.get_properties(p_out_pa, t_isen_k, gas_obj, eos_method)
            h2_isen = state_isen.H / 1000.0
            s2_isen = state_isen.S / 1000.0

            state_out = self.engine.thermo_solver.get_properties(p_out_pa, t_out_k, gas_obj, eos_method)
            h2_actual = state_out.H / 1000.0
            s2_actual = state_out.S / 1000.0

            k_val = state_in.k if state_in.k > 1.0 else 1.4
            poly_eff_frac = results.get("actual_poly_efficiency", inputs.get("poly_eff", 85.0) / 100.0)
            if poly_eff_frac > 1.0:
                poly_eff_frac /= 100.0
            n_path = (k_val - 1) / (k_val * poly_eff_frac)
            pressures = np.geomspace(p_in_pa, p_out_pa, 40)
            h_path, s_path = [], []
            for p in pressures:
                t_k = t_in_k * (p / p_in_pa) ** n_path
                try:
                    p_state = self.engine.thermo_solver.get_properties(p, t_k, gas_obj, eos_method)
                    h_path.append(p_state.H / 1000.0)
                    s_path.append(p_state.S / 1000.0)
                except Exception:
                    pass
            if len(h_path) < 2:
                h_path, s_path = [h1, h2_actual], [s1, s2_actual]

            ax.plot(s_path, h_path, "b-", linewidth=2, label="Gerçek Proses")
            ax.plot([s1, s2_isen], [h1, h2_isen], "r--", linewidth=2, label="İzentropik")
            ax.plot(s1, h1, "go", markersize=8, label="Giriş")
            ax.plot(s2_isen, h2_isen, "ro", markersize=8, label="İzentropik Çıkış")
            ax.plot(s2_actual, h2_actual, "bo", markersize=8, label="Gerçek Çıkış")

            delta_h = h2_actual - h1
            delta_h_isen = h2_isen - h1
            ax.annotate("", xy=(s2_actual, h1 + delta_h_isen), xytext=(s1, h1),
                        arrowprops=dict(arrowstyle="->", color="blue", lw=1.5))
            ax.annotate("", xy=(s2_actual, h2_actual), xytext=(s2_actual, h1),
                        arrowprops=dict(arrowstyle="->", color="red", lw=1.5))
            ax.text(s2_actual + 0.02, h1 + delta_h_isen / 2,
                    f"ΔH_isen={delta_h_isen:.1f}", fontsize=9, color="blue")
            ax.text(s2_actual + 0.02, h1 + delta_h_isen + delta_h / 2,
                    f"ΔH_act={delta_h:.1f}", fontsize=9, color="red")

            ax.set_xlabel("Entropi (kJ/kg·K)")
            ax.set_ylabel("Entalpi (kJ/kg)")
            ax.set_title("H-S (Mollier) Diyagramı — Kompresör Prosesi")
            ax.grid(True, alpha=0.3)
            ax.legend(loc="lower right")
            canvas.fig.tight_layout()
            return canvas
        except Exception as e:
            self.logger.error(f"H-S Mollier diyagramı hatası: {e}")
            return None

    def create_power_sankey(self, results):
        """Sankey enerji akış diyagramı."""
        if not MATPLOTLIB_LOADED:
            return None
        try:
            from matplotlib.sankey import Sankey
            canvas = MplCanvas(width=10, height=4)
            ax = canvas.fig.add_subplot(111)
            ax.axis("off")

            fuel_kw = float(results.get("fuel_thermal_kw",
                         float(results.get("fuel_unit_kgh", 0)) * float(results.get("lhv", 0)) / 3600))
            motor_kw = float(results.get("power_motor_per_unit_kw",
                         float(results.get("power_unit_kw", 0)) / 1.04))
            shaft_kw = float(results.get("power_shaft_per_unit_kw",
                         motor_kw * float(results.get("mech_eff", results.get("mech_eff", 98.0)) / 100.0
                         if float(results.get("mech_eff", 98.0)) < 1.0 else 0.98)))
            gas_kw = float(results.get("power_gas_per_unit_kw", shaft_kw * 0.92))
            if fuel_kw <= 0:
                fuel_kw = motor_kw / 0.35

            fuel_loss = fuel_kw - motor_kw
            mech_loss = motor_kw - shaft_kw
            poly_loss = shaft_kw - gas_kw

            sankey = Sankey(ax=ax, scale=0.6 / max(fuel_kw, 1), format="%.0f", unit=" kW")
            s0 = sankey.add(flows=[fuel_kw, -fuel_loss, -motor_kw],
                            labels=["Yakıt Girişi", "Isıl Kayıp", "Motor Gücü"],
                            orientations=[0, -1, 0], facecolor="#e74c3c")
            s1 = sankey.add(flows=[motor_kw, -mech_loss, -shaft_kw],
                            labels=["", "Mekanik Kayıp", "Şaft Gücü"],
                            orientations=[0, -1, 0], facecolor="#f39c12",
                            prior=0, connect=(2, 0))
            s2 = sankey.add(flows=[shaft_kw, -poly_loss, -gas_kw],
                            labels=["", "Termo. Kayıp", "Gaz Gücü"],
                            orientations=[0, -1, 0], facecolor="#2ecc71",
                            prior=1, connect=(2, 0))
            sankey.finish()
            canvas.fig.suptitle("Enerji Akışı (Sankey) — Ünite Başına", fontweight="bold")
            canvas.fig.tight_layout()
            return canvas
        except Exception as e:
            self.logger.error(f"Sankey diyagramı hatası: {e}")
            return None

    def create_kz_pressure_path(self, inputs, composition, eos_method):
        """k ve Z basınç yolu grafiği."""
        if not MATPLOTLIB_LOADED:
            return None
        try:
            canvas = MplCanvas(width=8, height=5)
            ax1 = canvas.fig.add_subplot(111)
            ax2 = ax1.twinx()

            gas_obj = self.engine._create_gas_object(composition, eos_method)
            p_in_pa = self.engine.convert_pressure_to_pa(float(inputs["p_in"]), inputs["p_in_unit"])
            p_out_pa = self.engine.convert_pressure_to_pa(float(inputs["p_out"]), inputs["p_out_unit"])
            t_in_k = self.engine.convert_temperature_to_k(float(inputs["t_in"]), inputs["t_in_unit"])

            state_in = self.engine.thermo_solver.get_properties(p_in_pa, t_in_k, gas_obj, eos_method)
            poly_eff = min(float(inputs.get("poly_eff", 90.0)) / 100.0, 0.99)
            k0 = state_in.k if state_in.k > 1.0 else 1.4
            n_path = (k0 - 1) / (k0 * poly_eff)

            pressures = np.geomspace(p_in_pa, p_out_pa, 50)
            k_vals, z_vals, pr_vals = [], [], []
            t_current = t_in_k
            for p in pressures:
                t_current = t_in_k * (p / p_in_pa) ** n_path
                t_current = max(100, min(2000, t_current))
                try:
                    s = self.engine.thermo_solver.get_properties(p, t_current, gas_obj, eos_method)
                    k_vals.append(s.k)
                    z_vals.append(s.Z)
                    pr_vals.append(p / p_in_pa)
                except Exception:
                    pr_vals.append(p / p_in_pa)

            l1, = ax1.plot(pr_vals, k_vals, "b-", linewidth=2, label="k (Cp/Cv)")
            l2, = ax2.plot(pr_vals, z_vals, "r-", linewidth=2, label="Z")
            ax1.set_xlabel("Basınç Oranı (P/P_in)")
            ax1.set_ylabel("k = Cp/Cv", color="b")
            ax2.set_ylabel("Z (Sıkıştırılabilirlik)", color="r")
            ax1.tick_params(axis="y", labelcolor="b")
            ax2.tick_params(axis="y", labelcolor="r")
            lines = [l1, l2]
            ax1.legend(lines, [l.get_label() for l in lines], loc="best")
            ax1.set_title("k ve Z — Sıkıştırma Yolu Boyunca (API 617 Referans)")
            ax1.grid(True, alpha=0.3)
            canvas.fig.tight_layout()
            return canvas
        except Exception as e:
            self.logger.error(f"k-Z basınç yolu hatası: {e}")
            return None

    def create_stage_overview(self, results):
        """Kademe-kademe P, T, η özet bar chart."""
        if not MATPLOTLIB_LOADED:
            return None
        try:
            stages = results.get("stages", [])
            if not stages:
                return None
            canvas = MplCanvas(width=10, height=6)
            n = len(stages)
            idx = np.arange(n)

            p_ins = [float(s.get("p_in", 0)) / 1e5 for s in stages]
            p_outs = [float(s.get("p_out", 0)) / 1e5 for s in stages]
            t_ins = [float(s.get("t_in", 273.15)) - 273.15 for s in stages]
            t_outs = [float(s.get("t_out", 273.15)) - 273.15 for s in stages]
            effs = [float(s.get("poly_eff_diagnostic", s.get("poly_eff_design", 0))) * 100 for s in stages]
            heads = [float(s.get("head_kj_kg", 0)) for s in stages]

            ax1 = canvas.fig.add_subplot(221)
            w = 0.35
            ax1.bar(idx - w/2, p_ins, w, label="P_giriş", color="#3498db")
            ax1.bar(idx + w/2, p_outs, w, label="P_çıkış", color="#e74c3c")
            ax1.set_ylabel("bar(a)")
            ax1.set_title("Basınç")
            ax1.set_xticks(idx)
            ax1.set_xticklabels([f"K{s.get('stage','')}" for s in stages])
            ax1.legend()

            ax2 = canvas.fig.add_subplot(222)
            ax2.bar(idx - w/2, t_ins, w, label="T_giriş", color="#2ecc71")
            ax2.bar(idx + w/2, t_outs, w, label="T_çıkış", color="#f39c12")
            ax2.set_ylabel("°C")
            ax2.set_title("Sıcaklık")
            ax2.set_xticks(idx)
            ax2.set_xticklabels([f"K{s.get('stage','')}" for s in stages])
            ax2.legend()

            ax3 = canvas.fig.add_subplot(223)
            colors_eff = ["#27ae60" if e >= 85 else "#f39c12" if e >= 75 else "#e74c3c" for e in effs]
            ax3.bar(idx, effs, color=colors_eff)
            ax3.set_ylabel("%")
            ax3.set_title("Politropik Verim")
            ax3.set_xticks(idx)
            ax3.set_xticklabels([f"K{s.get('stage','')}" for s in stages])
            ax3.axhline(y=85, color="gray", linestyle="--", alpha=0.5)

            ax4 = canvas.fig.add_subplot(224)
            ax4.bar(idx, heads, color="#9b59b6")
            ax4.set_ylabel("kJ/kg")
            ax4.set_title("Politropik Head")
            ax4.set_xticks(idx)
            ax4.set_xticklabels([f"K{s.get('stage','')}" for s in stages])

            canvas.fig.suptitle("Kademe-Kademe Özet", fontweight="bold")
            canvas.fig.tight_layout()
            return canvas
        except Exception as e:
            self.logger.error(f"Kademe özet grafiği hatası: {e}")
            return None

    def create_turbine_radar(self, selected_units):
        """Türbin radar (spider) karşılaştırma grafiği."""
        if not MATPLOTLIB_LOADED or not selected_units:
            return None
        try:
            canvas = MplCanvas(width=8, height=6)
            ax = canvas.fig.add_subplot(111, polar=True)

            categories = ["Güç Uygunluğu", "Isıl Verim", "Surge Marjı", "Stonewall", "Tip Skoru"]
            N = len(categories)
            angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
            angles += angles[:1]
            ax.set_xticks(angles[:-1])
            ax.set_xticklabels(categories)
            ax.set_ylim(0, 100)

            colors_line = ["#2ecc71", "#3498db", "#e74c3c", "#f39c12", "#9b59b6"]
            for i, unit in enumerate(selected_units[:5]):
                power = min(100, max(0, 100 - abs(unit.power_margin_percent - 10) * 2))
                hr = min(100, max(0, (14000 - unit.site_heat_rate) / 55))
                surge = min(100, max(0, unit.surge_margin_percent * 5))
                stonewall = min(100, max(0, unit.stonewall_margin_percent * 5))
                type_map = {"Aero-Derivative": 100, "Industrial/Aero": 90, "Industrial": 80,
                            "Heavy-Duty": 70, "Centrifugal": 60}
                type_score = type_map.get(unit.type_str, 65)
                values = [power, hr, surge, stonewall, type_score]
                values += values[:1]
                color = colors_line[i % len(colors_line)]
                label = f"{unit.manufacturer} {unit.model}"[:25]
                ax.fill(angles, values, alpha=0.15, color=color)
                ax.plot(angles, values, "o-", linewidth=2, label=label, color=color)

            ax.set_title("Türbin Radar Karşılaştırması", fontweight="bold", pad=20)
            ax.legend(loc="upper right", bbox_to_anchor=(1.35, 1.1), fontsize=8)
            canvas.fig.tight_layout()
            return canvas
        except Exception as e:
            self.logger.error(f"Türbin radar grafiği hatası: {e}")
            return None

    def create_convergence_dashboard(self, consistency_history):
        """3-panel yakınsama dashboard."""
        if not MATPLOTLIB_LOADED or not consistency_history or len(consistency_history) < 2:
            return None
        try:
            canvas = MplCanvas(width=12, height=5)
            iters = [h.get("iteration", i + 1) for i, h in enumerate(consistency_history)]
            eta_used = [h.get("eta_used", 0) for h in consistency_history]
            eta_calc = [h.get("eta_calculated", 0) for h in consistency_history]
            t_out = [h.get("t_out", 0) for h in consistency_history]
            residuals = [h.get("residual", 0) for h in consistency_history]

            ax1 = canvas.fig.add_subplot(131)
            ax1.plot(iters, eta_used, "b--o", label="η_kullanılan", markersize=4)
            ax1.plot(iters, eta_calc, "r-s", label="η_hesaplanan", markersize=4)
            ax1.set_xlabel("İterasyon")
            ax1.set_ylabel("Verim (%)")
            ax1.set_title("η Yakınsaması")
            ax1.legend(fontsize=8)
            ax1.grid(True, alpha=0.3)

            ax2 = canvas.fig.add_subplot(132)
            ax2.plot(iters, t_out, "g-o", markersize=4)
            ax2.set_xlabel("İterasyon")
            ax2.set_ylabel("T_çıkış (°C)")
            ax2.set_title("Sıcaklık Yakınsaması")
            ax2.grid(True, alpha=0.3)

            ax3 = canvas.fig.add_subplot(133)
            ax3.semilogy(iters, residuals, "m-s", markersize=4)
            ax3.set_xlabel("İterasyon")
            ax3.set_ylabel("Kalıntı |η_c − η_u| (log)")
            ax3.set_title("Kalıntı (Residual)")
            ax3.grid(True, alpha=0.3)

            canvas.fig.suptitle("Hesaplama Yakınsama Dashboard", fontweight="bold")
            canvas.fig.tight_layout()
            return canvas
        except Exception as e:
            self.logger.error(f"Yakınsama dashboard hatası: {e}")
            return None


class GraphManager:
    """Grafik yönetim sınıfı"""
    
    def __init__(self, engine):
        self.generator = GraphGenerator(engine)
        self.current_graphs = {}
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def generate_all_graphs(self, inputs, results, selected_units=None, composition=None, eos_method=None):
        """Tüm grafikleri oluştur (V4.7 — 8 grafik seti)"""
        graphs = {}
        comp = composition or inputs.get("gas_comp", {})
        eos = eos_method or inputs.get("eos_method", "coolprop")

        self._graph_error = None

        try:
            if not MATPLOTLIB_LOADED:
                self.current_graphs = {}
                self._graph_error = f"Matplotlib yuklu degil: {MATPLOTLIB_IMPORT_ERROR}"
                self.logger.error("Grafik modulu yuklenemedi: %s", MATPLOTLIB_IMPORT_ERROR)
                return graphs

            if not comp or not isinstance(comp, dict) or len(comp) == 0:
                self._graph_error = "Gaz kompozisyonu tanimlanmamis veya bos."
                self.logger.warning(self._graph_error)
                return graphs

            gen = self.generator

            # 1. T-s Diyagramı
            graphs["ts_diagram"] = gen.create_ts_diagram(inputs, results, comp, eos)

            # 2. P-v Diyagramı
            graphs["pv_diagram"] = gen.create_pv_diagram(inputs, results, comp, eos)

            # 3. H-S (Mollier) Diyagramı — YENİ
            graphs["hs_mollier"] = gen.create_hs_mollier_diagram(inputs, results, comp, eos)

            # 4. Güç Dağılımı (Sankey) — YENİ
            graphs["power_breakdown"] = gen.create_power_sankey(results)

            # 5. k-Z Basınç Yolu — YENİ
            graphs["kz_path"] = gen.create_kz_pressure_path(inputs, comp, eos)

            # 6. Kademe Özeti — YENİ
            graphs["stage_overview"] = gen.create_stage_overview(results)

            # 7. Türbin Radarı — YENİ
            if selected_units:
                graphs["performance_comparison"] = gen.create_turbine_radar(selected_units)

            # 8. Yakınsama Dashboard — YENİ
            if "consistency_history" in results:
                graphs["convergence"] = gen.create_convergence_dashboard(results["consistency_history"])

            # 9. Önbellek Performansı (yedek)
            cache_stats = gen.engine.thermo_solver.get_cache_stats()
            graphs["cache_performance"] = gen.create_cache_performance_chart(cache_stats)

            self.current_graphs = {name: graph for name, graph in graphs.items() if graph is not None}
            missing_graphs = [name for name, graph in graphs.items() if graph is None]
            if missing_graphs:
                self.logger.warning("Olusturulamayan grafikler: %s", ", ".join(missing_graphs))
                if not self._graph_error:
                    self._graph_error = f"Su grafikler olusturulamadi: {', '.join(missing_graphs)}"
            if self.current_graphs:
                self.logger.info("%s grafik basariyla olusturuldu", len(self.current_graphs))
            else:
                self.logger.error("Hic grafik olusturulamadi; ayrinti icin onceki grafik hata loglarini kontrol edin.")
                if not self._graph_error:
                    self._graph_error = "Tum grafikler olusturulamadi. Log dosyasini kontrol edin."
            
        except Exception as e:
            self.logger.exception(f"Grafik oluşturma hatası: {e}")
            self._graph_error = str(e)
            import sys
            print(f"GRAPH ERROR: {e}", file=sys.stderr)
        
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
