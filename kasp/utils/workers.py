from PyQt5.QtCore import QObject, pyqtSignal
import logging
import time


class ProgressTracker:
    """
    Track calculation progress and estimate time remaining.
    
    Uses exponential moving average for smoother ETA predictions.
    """
    
    def __init__(self, total_steps=100):
        self.total_steps = total_steps
        self.current_step = 0
        self.start_time = time.time()
        self.last_update_time = self.start_time
        self.step_times = []
        self.alpha = 0.3  # Smoothing factor for EMA
        self.ema = None
        
    def update(self, step):
        """
        Update progress and return estimated time remaining in seconds.
        
        Args:
            step: Current progress step (0-100)
            
        Returns:
            float: Estimated seconds remaining, or None if not enough data
        """
        current_time = time.time()
        
        # Calculate time since last update
        if self.current_step > 0:
            step_duration = current_time - self.last_update_time
            step_progress = step - self.current_step
            
            if step_progress > 0:
                time_per_percent = step_duration / step_progress
                
                # Exponential moving average for smoother predictions
                if self.ema is None:
                    self.ema = time_per_percent
                else:
                    self.ema = self.alpha * time_per_percent + (1 - self.alpha) * self.ema
                
                # Calculate ETA
                remaining_progress = self.total_steps - step
                eta = self.ema * remaining_progress
                
                self.current_step = step
                self.last_update_time = current_time
                
                return max(0, eta)  # Never return negative
        
        self.current_step = step
        self.last_update_time = current_time
        return None


class CalculationWorker(QObject):
    """
    Enhanced calculation worker with detailed progress tracking and cancellation support.
    
    Task 4: Real-time progress bar enhancement
    - Granular progress tracking (12 steps)
    - Status messages
    - Time estimation
    - Cancellation support
    """
    
    # Signals
    finished = pyqtSignal(dict, list)
    error = pyqtSignal(str)
    progress = pyqtSignal(int)  # Legacy - for backward compatibility
    progress_detailed = pyqtSignal(int, str)  # (percentage, message)
    time_remaining = pyqtSignal(float)  # Estimated seconds remaining
    cancelled = pyqtSignal()

    def __init__(self, engine, inputs, all_turbines_data, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.inputs = inputs
        self.all_turbines_data = all_turbines_data
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Task 4: Cancellation and progress tracking
        self._cancel_requested = False
        self.progress_tracker = ProgressTracker(total_steps=100)

    def request_cancel(self):
        """Request calculation cancellation."""
        self._cancel_requested = True
        self.logger.info("⚠️ Cancellation requested by user")

    def emit_progress(self, percentage, message):
        """
        Emit progress update with time estimate.
        
        Args:
            percentage: Progress percentage (0-100)
            message: Status message
        """
        # Emit both old and new signals for compatibility
        self.progress.emit(percentage)
        self.progress_detailed.emit(percentage, message)
        
        # Calculate and emit time estimate
        eta = self.progress_tracker.update(percentage)
        if eta is not None:
            self.time_remaining.emit(eta)
        
        self.logger.debug(f"Progress: {percentage}% - {message}")

    def run(self):
        """
        Execute calculation with granular progress tracking.
        
        Progress Steps:
        0%   - Initialization
        5%   - Input validation
        10%  - Gas object creation
        20%  - Inlet property calculations
        30%  - Outlet property calculations
        40%  - Polytropic calculations
        50%  - Power calculations
        60%  - Fuel calculations
        70%  - Starting unit selection
        80%  - Filtering compatible units
        90%  - Ranking units
        95%  - Finalizing results
        100% - Complete
        """
        try:
            # Step 1: Initialization (0%)
            self.emit_progress(0, "Initializing calculation...")
            if self._cancel_requested:
                self.cancelled.emit()
                return
            
            # Step 2: Input validation (5%)
            self.emit_progress(5, "Validating inputs...")
            self.logger.info("🚀 Calculation worker started")
            self.logger.info(f"Selected EOS: {self.inputs.get('eos_method', 'N/A').upper()}")
            
            if self._cancel_requested:
                self.cancelled.emit()
                return
            
            # Step 3: Gas object creation (10%)
            self.emit_progress(10, "Creating gas mixture...")
            
            # Step 4: Thermodynamic calculations (20-60%)
            self.emit_progress(20, "Hesaplamalar başlıyor...")

            if self._cancel_requested:
                self.cancelled.emit()
                return

            self.emit_progress(30, "Termodinamik özellikler hesaplanıyor...")

            if self._cancel_requested:
                self.cancelled.emit()
                return

            self.emit_progress(40, "EOS motoru çalıştırılıyor...")

            # --- Ana termodinamik hesaplama (% 40-60 arasında gerçekleşiyor) ---
            self.logger.info("Phase 1: Thermodynamic calculation starting...")
            results_raw = self.engine.calculate_design_performance_with_mode(self.inputs)
            self.logger.info("Phase 1: Thermodynamic calculation complete ✓")
            
            if self._cancel_requested:
                self.cancelled.emit()
                return
            
            self.emit_progress(50, "Calculating power requirements...")
            
            if self._cancel_requested:
                self.cancelled.emit()
                return
            
            self.emit_progress(60, "Analyzing fuel consumption...")
            
            # --- Unit Selection Phase (70-95%) ---
            required_power_per_unit_kw = results_raw['power_unit_kw']
            site_conditions = {
                'ambient_temp':     self.inputs['ambient_temp'],
                'altitude':         self.inputs['altitude'],
                # V4.3 Fix 4: Birim kPa — 1013 mbar değil, 101.325 kPa!
                # UI'dan kPa olarak geldiğinden emin olun.
                'ambient_pressure': self.inputs.get('ambient_pressure', self.inputs.get('ambient_press', 101.325)),  # kPa
                'humidity':         self.inputs.get('humidity', 60),
                'flow':             results_raw.get('mass_flow_per_unit_kgs', 0.0)
            }
            
            self.emit_progress(70, "Searching for suitable turbines...")
            self.logger.info(
                f"Phase 2: Unit selection starting. "
                f"Required power (per unit): {required_power_per_unit_kw:.2f} kW"
            )
            
            if self._cancel_requested:
                self.cancelled.emit()
                return
            
            self.emit_progress(80, "Filtering compatible turbines...")
            
            selected_units = self.engine.select_units(
                required_power_per_unit_kw, 
                site_conditions, 
                self.all_turbines_data, 
                limit=5
            )
            
            if self._cancel_requested:
                self.cancelled.emit()
                return
            
            self.emit_progress(90, "Ranking turbine options...")
            self.logger.info(f"Phase 2: Unit selection complete. Found {len(selected_units)} units ✓")
            
            if self._cancel_requested:
                self.cancelled.emit()
                return
            
            # Step 12: Finalization (95-100%)
            self.emit_progress(95, "Finalizing results...")
            
            if self._cancel_requested:
                self.cancelled.emit()
                return
            
            self.emit_progress(100, "Calculation complete!")
            self.logger.info("✅ All calculations completed successfully")
            
            # Emit results
            self.finished.emit(results_raw, selected_units)
        
        except Exception as e:
            error_message = f"Critical calculation error: {e}"
            self.logger.error(error_message, exc_info=True)
            self.error.emit(error_message)
