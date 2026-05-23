import threading
import datetime
import numpy as np

class PerformanceMonitor:
    """Hesaplama performansı izleme sistemi"""
    
    def __init__(self):
        self.metrics = {
            'calculation_time': [],
            'convergence_iterations': [],
            'property_calculations': 0,
            'eos_method_usage': {},
            'error_count': 0,
            'successful_calculations': 0,
            'cache_stats': {'hits': 0, 'misses': 0}
        }
        self._lock = threading.Lock()
        self.start_time = datetime.datetime.now()
    
    def log_performance(self, method_name, duration, iterations=None):
        """Performans metriklerini kaydet"""
        with self._lock:
            self.metrics['calculation_time'].append(duration)
            if iterations is not None:
                self.metrics['convergence_iterations'].append(iterations)
            
            if method_name not in self.metrics['eos_method_usage']:
                self.metrics['eos_method_usage'][method_name] = 0
            self.metrics['eos_method_usage'][method_name] += 1
            
            self.metrics['successful_calculations'] += 1
    
    def log_property_calculation(self):
        """Özellik hesaplama sayacı"""
        with self._lock:
            self.metrics['property_calculations'] += 1
    
    def log_error(self):
        """Hata sayacı"""
        with self._lock:
            self.metrics['error_count'] += 1
    
    def log_cache_hit(self):
        """Cache isabeti"""
        with self._lock:
            self.metrics['cache_stats']['hits'] += 1
    
    def log_cache_miss(self):
        """Cache kaçırma"""
        with self._lock:
            self.metrics['cache_stats']['misses'] += 1
    
    def get_statistics(self):
        """İstatistikleri getir"""
        with self._lock:
            calc_times = self.metrics['calculation_time']
            conv_iters = self.metrics['convergence_iterations']
            cache_stats = self.metrics['cache_stats']
            
            total_cache = cache_stats['hits'] + cache_stats['misses']
            cache_hit_rate = cache_stats['hits'] / total_cache if total_cache > 0 else 0
            
            stats = {
                'total_calculations': len(calc_times),
                'avg_calculation_time': np.mean(calc_times) if calc_times else 0,
                'max_calculation_time': np.max(calc_times) if calc_times else 0,
                'min_calculation_time': np.min(calc_times) if calc_times else 0,
                'avg_convergence_iterations': np.mean(conv_iters) if conv_iters else 0,
                'total_property_calculations': self.metrics['property_calculations'],
                'eos_method_distribution': self.metrics['eos_method_usage'],
                'error_count': self.metrics['error_count'],
                'success_rate': (self.metrics['successful_calculations'] / 
                               (self.metrics['successful_calculations'] + self.metrics['error_count']) 
                               if (self.metrics['successful_calculations'] + self.metrics['error_count']) > 0 else 0),
                'cache_hit_rate': cache_hit_rate,
                'cache_hits': cache_stats['hits'],
                'cache_misses': cache_stats['misses'],
                'uptime_hours': (datetime.datetime.now() - self.start_time).total_seconds() / 3600
            }
            return stats
    
    def reset_statistics(self):
        """İstatistikleri sıfırla"""
        with self._lock:
            self.metrics = {
                'calculation_time': [],
                'convergence_iterations': [],
                'property_calculations': 0,
                'eos_method_usage': {},
                'error_count': 0,
                'successful_calculations': 0,
                'cache_stats': {'hits': 0, 'misses': 0}
            }
