import sys
import os
from release_metadata import APP_VERSION
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtGui import QFont, QIcon
from PyQt5.QtCore import Qt, PYQT_VERSION_STR, QT_VERSION_STR
import logging

# Security improvement: Use absolute path and insert at beginning
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Safe imports with detailed error messages
def safe_import():
    """Safely import required modules with fallback"""
    global KaspMainWindow, setup_logging, install_exception_handler
    
    try:
        from kasp.ui.main_window import KaspMainWindow
    except ImportError as e:
        print(f"CRITICAL: Cannot import KaspMainWindow", file=sys.stderr)
        print(f"Error: {e}", file=sys.stderr)
        print(f"Make sure 'kasp/ui/main_window.py' exists in: {current_dir}", file=sys.stderr)
        sys.exit(1)
    
    try:
        from kasp.logging_handler import setup_logging
    except ImportError as e:
        print(f"WARNING: Cannot import logging_handler: {e}", file=sys.stderr)
        print("Using fallback logging configuration", file=sys.stderr)
        
        def setup_logging():
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s - %(levelname)s - %(name)s - %(funcName)s - Line %(lineno)d - %(message)s',
                handlers=[
                    logging.FileHandler('kasp_error.log', encoding='utf-8'),
                    logging.StreamHandler(sys.stdout)
                ]
            )
            logger = logging.getLogger(__name__)
            logger.info("KASP v%s - Using fallback logging", APP_VERSION)
            return logger
    
    try:
        from kasp.exception_handler import install_exception_handler
    except ImportError as e:
        print(f"WARNING: Cannot import exception_handler: {e}", file=sys.stderr)
        print("Using fallback exception handler", file=sys.stderr)
        
        def install_exception_handler():
            def handle_exception(exc_type, exc_value, exc_traceback):
                if issubclass(exc_type, KeyboardInterrupt):
                    sys.__excepthook__(exc_type, exc_value, exc_traceback)
                    return
                logging.getLogger(__name__).critical(
                    "Uncaught exception", 
                    exc_info=(exc_type, exc_value, exc_traceback)
                )
            sys.excepthook = handle_exception

# Perform safe imports
safe_import()

def show_critical_error(message: str, details: str = None):
    """Show critical error dialog before application exit"""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    msg_box = QMessageBox()
    msg_box.setIcon(QMessageBox.Critical)
    msg_box.setWindowTitle("KASP - Kritik Hata")
    msg_box.setText(message)
    
    if details:
        msg_box.setDetailedText(details)
    
    msg_box.setStandardButtons(QMessageBox.Ok)
    msg_box.exec_()

def main():
    """Main application entry point with comprehensive error handling"""
    logger = None
    app = None
    window = None
    
    try:
        # Initialize logging first
        logger = setup_logging()
        logger.info("=" * 80)
        logger.info("KASP v%s - Application Starting", APP_VERSION)
        logger.info(f"Python Version: {sys.version}")
        logger.info(f"PyQt5 Version: {PYQT_VERSION_STR}")
        logger.info(f"Qt Version: {QT_VERSION_STR}")
        logger.info(f"Working Directory: {current_dir}")
        logger.info("=" * 80)
        
        # Install global exception handler
        install_exception_handler()
        
        # CRITICAL FIX: High DPI must be set BEFORE QApplication creation
        if hasattr(Qt, 'AA_EnableHighDpiScaling'):
            QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
            logger.info("✓ High DPI scaling enabled")
        
        if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
            QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
            logger.info("✓ High DPI pixmaps enabled")
        
        # Create QApplication instance
        app = QApplication(sys.argv)
        logger.info("✓ QApplication created")
        
        # Set application metadata
        app.setApplicationName("KASP")
        app.setApplicationVersion(APP_VERSION)
        app.setOrganizationName("KASP Engineering")
        app.setOrganizationDomain("kasp.engineering")
        app.setApplicationDisplayName(f"KASP v{APP_VERSION} - Termodinamik Analiz")
        logger.info("✓ Application metadata set")
        
        # Set application style
        app.setStyle("Fusion")
        logger.info("✓ Application style set to Fusion")
        
        # V4.6: Responsive DPI-aware font (replaces fixed 9pt)
        try:
            from kasp.ui.responsive import apply_responsive_font
            apply_responsive_font(app, base_pt=9)
        except Exception:
            from PyQt5.QtGui import QFont
            app.setFont(QFont("Segoe UI", 9))
            logger.info("✓ Application font set to Segoe UI 9pt (fallback)")
        
        # Set application icon if exists
        icon_path = os.path.join(current_dir, "resources", "icon.ico")
        if os.path.exists(icon_path):
            app.setWindowIcon(QIcon(icon_path))
            logger.info(f"✓ Application icon loaded: {icon_path}")
        else:
            logger.warning(f"⚠ Application icon not found: {icon_path}")
        
        # Create main window
        logger.info("Creating main window...")
        window = KaspMainWindow()
        logger.info("✓ Main window created")
        
        # Log window initial state
        logger.info(f"Window geometry: {window.size().width()}x{window.size().height()}")
        logger.info(f"Window position: ({window.x()}, {window.y()})")
        
        # CRITICAL FIX: Ensure window is properly displayed
        window.show()
        logger.info("✓ window.show() called")
        
        # Force window to normal state (not minimized)
        window.setWindowState(window.windowState() & ~Qt.WindowMinimized | Qt.WindowActive)
        logger.info("✓ Window state normalized")
        
        # Raise and activate window to bring to front
        window.raise_()
        logger.info("✓ Window raised")
        
        window.activateWindow()
        logger.info("✓ Window activated")
        
        # Force process events to ensure window is drawn
        app.processEvents()
        logger.info("✓ Events processed")
        
        # Verify window visibility
        logger.info(f"Window visible: {window.isVisible()}")
        logger.info(f"Window active: {window.isActiveWindow()}")
        logger.info(f"Window minimized: {window.isMinimized()}")
        
        # Log successful startup
        logger.info("=" * 80)
        logger.info("KASP application started successfully")
        logger.info("Entering event loop...")
        logger.info("=" * 80)
        
        # Enter event loop
        exit_code = app.exec_()
        
        # Log clean shutdown
        logger.info("=" * 80)
        logger.info(f"Event loop exited with code: {exit_code}")
        logger.info("KASP application shutting down...")
        
        # Cleanup before exit
        if window:
            window.close()
            window.deleteLater()
            logger.info("✓ Main window cleaned up")
        
        logger.info("✓ Application closed successfully")
        logger.info("=" * 80)
        
        sys.exit(exit_code)
        
    except ImportError as e:
        error_msg = f"Modül yükleme hatası: {str(e)}"
        if logger:
            logger.critical(error_msg, exc_info=True)
        else:
            print(f"CRITICAL ERROR: {error_msg}", file=sys.stderr)
        
        show_critical_error(
            "KASP modülleri yüklenemedi!\n\nLütfen uygulamayı yeniden yükleyin.",
            str(e)
        )
        sys.exit(1)
        
    except Exception as e:
        error_msg = f"Beklenmeyen hata: {str(e)}"
        if logger:
            logger.critical(error_msg, exc_info=True)
        else:
            print(f"CRITICAL ERROR: {error_msg}", file=sys.stderr)
        
        show_critical_error(
            "KASP başlatılamadı!\n\nDetaylar için hata logunu kontrol edin.",
            str(e)
        )
        sys.exit(1)
        
    finally:
        # Ensure cleanup happens
        if logger:
            logger.info("Cleanup completed")

if __name__ == "__main__":
    main()
