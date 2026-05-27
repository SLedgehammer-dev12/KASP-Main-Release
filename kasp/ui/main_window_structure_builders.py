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
            ("🚪 Çıkış Yap", None, "logout"),
            None,
            ("🚪 Kapat", "Ctrl+Q", "close"),
        ],
        "🛠️ Araçlar": [
            ("📚 Kütüphane Yöneticisi", None, "open_library_manager"),
            ("🧹 Önbelleği Temizle", None, "clear_engine_cache"),
            None,
            ("👥 Kullanıcı Yönetimi", None, "show_admin_panel"),
        ],
        "🎨 Görünüm": [
            ("__submenu_theme__", None, None),
            None,
            ("__submenu_lang__", None, None),
        ],
        "❓ Yardım": [
            ("📖 Örnekler", None, "show_examples"),
            ("Guncellemeleri Kontrol Et", None, "_check_for_updates_manual"),
            None,
            ("📘 Termodinamik El Kitabı", None, "show_thermodynamics_handbook"),
            None,
            ("ℹ️ Hakkında", None, "show_about_dialog"),
        ],
    }


def get_theme_options():
    return [
        ("☀️ Açık", "light"),
        ("🌙 Koyu", "dark"),
        ("🔧 Mühendislik", "engineering"),
    ]


def get_language_options():
    return [
        ("🇹🇷 Türkçe", "tr"),
        ("🇬🇧 English", "en"),
    ]


def build_main_menu(window):
    from PyQt5.QtWidgets import QAction, QActionGroup, QMenu

    menu_bar = window.menuBar()
    window._theme_actions = {}
    window._language_actions = {}

    for menu_title, items in get_main_menu_specs().items():
        menu = menu_bar.addMenu(menu_title)
        for item in items:
            if item is None:
                menu.addSeparator()
                continue

            label, shortcut, handler_name = item
            if label == "__submenu_theme__":
                theme_menu = QMenu("Tema", menu)
                theme_group = QActionGroup(window)
                theme_group.setExclusive(True)
                for theme_label, theme_key in get_theme_options():
                    action = QAction(theme_label, window)
                    action.setCheckable(True)
                    action.triggered.connect(lambda checked, tk=theme_key: window.switch_theme(tk))
                    theme_group.addAction(action)
                    theme_menu.addAction(action)
                    window._theme_actions[theme_key] = action
                menu.addMenu(theme_menu)
            elif label == "__submenu_lang__":
                lang_menu = QMenu("Dil / Language", menu)
                lang_group = QActionGroup(window)
                lang_group.setExclusive(True)
                for lang_label, lang_key in get_language_options():
                    action = QAction(lang_label, window)
                    action.setCheckable(True)
                    action.triggered.connect(lambda checked, lk=lang_key: window.switch_language(lk))
                    lang_group.addAction(action)
                    lang_menu.addAction(action)
                    window._language_actions[lang_key] = action
                menu.addMenu(lang_menu)
            elif handler_name == "_check_for_updates_manual":
                action = QAction(label, window)
                if shortcut:
                    action.setShortcut(shortcut)
                action.triggered.connect(lambda _checked=False: window._check_for_updates(manual=True))
                menu.addAction(action)
            else:
                action = QAction(label, window)
                if shortcut:
                    action.setShortcut(shortcut)
                action.triggered.connect(getattr(window, handler_name))
                menu.addAction(action)


def build_main_tabs(window):
    from PyQt5.QtGui import QFont
    from PyQt5.QtWidgets import QTabWidget, QWidget
    from kasp.ui.responsive import scaled_font_pt

    tabs = QTabWidget()
    tabs.setFont(QFont("Inter", scaled_font_pt(10)))

    tab_attrs = ("design_tab", "performance_tab", "log_tab")
    for attr_name, title in zip(tab_attrs, get_main_tab_titles()):
        tab = QWidget()
        setattr(window, attr_name, tab)
        tabs.addTab(tab, title)

    window.main_layout.addWidget(tabs)
