"""Builders for the top-level KASP main window structure."""

from __future__ import annotations


def get_main_tab_titles():
    return [
        "📊 Tasarım / Simülasyon",
        "📈 Performans Değerlendirme",
        "📋 Sistem Logları",
    ]


def get_main_menu_specs():
    return {
        "📁 Dosya": [
            ("🆕 Yeni Proje", "Ctrl+N", "new_project"),
            ("📂 Proje Aç...", "Ctrl+O", "load_project"),
            ("💾 Projeyi Kaydet...", "Ctrl+S", "save_project"),
            None,
            ("📤 Sonuçları Dışa Aktar", "Ctrl+E", "export_results"),
            None,
            ("🚪 Çıkış", "Ctrl+Q", "close"),
        ],
        "🛠️ Araçlar": [
            ("📚 Kütüphane Yöneticisi", None, "open_library_manager"),
            ("🧹 Önbelleği Temizle", None, "clear_engine_cache"),
        ],
        "❓ Yardım": [
            ("📖 Örnekler", None, "show_examples"),
            ("ℹ️ Hakkında", None, "show_about_dialog"),
        ],
    }


def build_main_menu(window):
    from PyQt5.QtWidgets import QAction

    menu_bar = window.menuBar()
    for menu_title, items in get_main_menu_specs().items():
        menu = menu_bar.addMenu(menu_title)
        for item in items:
            if item is None:
                menu.addSeparator()
                continue

            label, shortcut, handler_name = item
            action = QAction(label, window)
            if shortcut:
                action.setShortcut(shortcut)
            action.triggered.connect(getattr(window, handler_name))
            menu.addAction(action)


def build_main_tabs(window):
    from PyQt5.QtGui import QFont
    from PyQt5.QtWidgets import QTabWidget, QWidget

    tabs = QTabWidget()
    tabs.setFont(QFont("Inter", 10))

    tab_attrs = ("design_tab", "performance_tab", "log_tab")
    for attr_name, title in zip(tab_attrs, get_main_tab_titles()):
        tab = QWidget()
        setattr(window, attr_name, tab)
        tabs.addTab(tab, title)

    window.main_layout.addWidget(tabs)
