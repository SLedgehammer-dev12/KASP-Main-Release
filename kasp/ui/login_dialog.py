"""KASP Login Dialog — Brute-Force Korumalı Giriş Penceresi."""

import time

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from kasp.security import (
    LOCKOUT_LEVELS,
    check_lockout,
    get_lockout_remaining,
    record_attempt,
    verify_password,
)
from kasp.i18n import tr


class LoginDialog(QDialog):
    _LOCKOUT_TIMER_INTERVAL = 1000

    def __init__(self, password_hash: str, parent=None):
        super().__init__(parent)
        self._password_hash = password_hash
        self._remaining_lockout = get_lockout_remaining()
        self._lockout_timer = None
        self._setup_ui()
        self._update_lockout_state()

    def _setup_ui(self):
        self.setWindowTitle(tr("KASP — Giriş"))
        # V4.7: Responsive dialog size
        try:
            from kasp.ui.responsive import scaled
            w, h = scaled(380), scaled(220)
        except Exception:
            w, h = 380, 220
        self.setFixedSize(w, h)
        self.setWindowFlags(
            Qt.Dialog | Qt.WindowTitleHint | Qt.WindowCloseButtonHint
        )

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 20, 24, 20)

        title = QLabel(tr("🔒 KASP Giriş"))
        title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        self._status_label = QLabel("")
        self._status_label.setAlignment(Qt.AlignCenter)
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

        pw_layout = QHBoxLayout()
        self._password_edit = QLineEdit()
        self._password_edit.setEchoMode(QLineEdit.Password)
        self._password_edit.setPlaceholderText(tr("Şifre"))
        self._password_edit.returnPressed.connect(self._try_login)
        pw_layout.addWidget(self._password_edit)

        self._show_pw_cb = QCheckBox(tr("👁️"))
        self._show_pw_cb.toggled.connect(self._toggle_password_visibility)
        pw_layout.addWidget(self._show_pw_cb)
        layout.addLayout(pw_layout)

        btn_layout = QHBoxLayout()
        self._login_btn = QPushButton(tr("Giriş Yap"))
        self._login_btn.clicked.connect(self._try_login)
        self._login_btn.setDefault(True)
        btn_layout.addWidget(self._login_btn)

        cancel_btn = QPushButton(tr("Çıkış"))
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def _toggle_password_visibility(self, checked):
        self._password_edit.setEchoMode(
            QLineEdit.Normal if checked else QLineEdit.Password
        )

    def _try_login(self):
        locked, msg = check_lockout()
        if locked:
            self._update_lockout_state()
            return

        password = self._password_edit.text()
        if verify_password(password, self._password_hash):
            record_attempt(success=True)
            self.accept()
        else:
            record_attempt(success=False)
            self._password_edit.clear()
            self._password_edit.setFocus()
            self._update_lockout_state()

    def _update_lockout_state(self):
        locked, msg = check_lockout()

        if self._lockout_timer:
            self._lockout_timer.stop()
            self._lockout_timer = None

        if locked:
            self._login_btn.setEnabled(False)
            self._password_edit.setEnabled(False)
            self._status_label.setText(f"⏳ {msg}")
            self._status_label.setStyleSheet("color: #c62828;")
            self._lockout_timer = QTimer(self)
            self._lockout_timer.timeout.connect(self._on_lockout_tick)
            self._lockout_timer.start(self._LOCKOUT_TIMER_INTERVAL)
        else:
            self._login_btn.setEnabled(True)
            self._password_edit.setEnabled(True)
            remaining = get_lockout_remaining()
            if remaining > 0:
                level_info = _find_lockout_level(remaining)
                self._status_label.setText(
                    tr(f"Kalan deneme: {level_info}")
                )
                self._status_label.setStyleSheet("color: #b25300;")
            else:
                self._status_label.setText("")

    def _on_lockout_tick(self):
        self._remaining_lockout = get_lockout_remaining()
        locked, msg = check_lockout()
        if not locked:
            self._update_lockout_state()
            self._password_edit.setFocus()
        else:
            self._status_label.setText(f"⏳ {msg}")

    def reject(self):
        if self._lockout_timer:
            self._lockout_timer.stop()
        super().reject()


def _find_lockout_level(remaining_attempts):
    for limit, _ in LOCKOUT_LEVELS:
        if remaining_attempts < limit:
            return max(1, limit - remaining_attempts)
    return max(1, LOCKOUT_LEVELS[-1][0] - remaining_attempts + 1)
