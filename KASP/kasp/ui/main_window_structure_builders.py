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
        "⚙️ Ayarlar": {
            "🌐 Dil": [
                ("@checkable", "🇹🇷 Türkçe", "language", "tr"),
                ("@checkable", "🇬🇧 English", "language", "en"),
            ],
            "🎨 Tema": [
                ("@checkable", "☀️ Açık Tema", "theme", "light"),
                ("@checkable", "🌙 Koyu Tema", "theme", "dark"),
                ("@checkable", "🔧 Mühendislik", "theme", "engineering"),
            ],
        },
        "❓ Yardım": [
            ("📖 Örnekler", None, "show_examples"),
            ("Guncellemeleri Kontrol Et", None, "_check_for_updates_manual"),
            ("ℹ️ Hakkında", None, "show_about_dialog"),
        ],
    }


def build_main_menu(window):
    from PyQt5.QtWidgets import QAction, QActionGroup

    from kasp.config_manager import get_config_manager

    config = get_config_manager()
    saved_lang = config.get("app.language", "tr")
    saved_theme = config.get("app.theme", "light")

    window._language_actions = {}
    window._theme_actions = {}

    menu_bar = window.menuBar()
    for menu_title, items in get_main_menu_specs().items():
        menu = menu_bar.addMenu(menu_title)

        if isinstance(items, dict):
            _build_sub_menu_structure(window, menu, items, saved_lang, saved_theme)
        else:
            _build_flat_menu(window, menu, items)


def _build_flat_menu(window, menu, items):
    from PyQt5.QtWidgets import QAction

    for item in items:
        if item is None:
            menu.addSeparator()
            continue

        label, shortcut, handler_name = item
        action = QAction(label, window)
        if shortcut:
            action.setShortcut(shortcut)
        if handler_name == "_check_for_updates_manual":
            action.triggered.connect(lambda _checked=False: window._check_for_updates(manual=True))
        else:
            action.triggered.connect(getattr(window, handler_name))
        menu.addAction(action)


def _build_sub_menu_structure(window, menu, sub_specs, saved_lang, saved_theme):
    from PyQt5.QtWidgets import QAction, QActionGroup

    for sub_title, sub_items in sub_specs.items():
        sub_menu = menu.addMenu(sub_title)
        group = QActionGroup(window)
        group.setExclusive(True)

        for spec in sub_items:
            marker, label, group_name, value = spec
            action = QAction(label, window)
            action.setCheckable(True)
            action.setData(value)

            if group_name == "language":
                action.setChecked(value == saved_lang)
                action.triggered.connect(
                    lambda checked, v=value: window._on_switch_language(v) if checked else None
                )
                window._language_actions[value] = action
            elif group_name == "theme":
                action.setChecked(value == saved_theme)
                action.triggered.connect(
                    lambda checked, v=value: window._on_switch_theme(v) if checked else None
                )
                window._theme_actions[value] = action

            group.addAction(action)
            sub_menu.addAction(action)


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
