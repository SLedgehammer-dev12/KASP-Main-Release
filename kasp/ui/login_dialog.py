"""KASP Login Dialog — Gelişmiş Kullanıcı Giriş Penceresi."""

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
)
from kasp.i18n import tr


class LoginDialog(QDialog):
    _LOCKOUT_TIMER_INTERVAL = 1000

    def __init__(self, user_manager, parent=None):
        super().__init__(parent)
        self._user_manager = user_manager
        self._remaining_lockout = get_lockout_remaining()
        self._lockout_timer = None
        self._was_locked = False
        self._setup_ui()
        self._update_lockout_state(is_initial=True)

    def _setup_ui(self):
        self.setWindowTitle(tr("KASP — Giriş"))
        try:
            from kasp.ui.responsive import scaled
            w, h = scaled(400), scaled(295)
        except Exception:
            w, h = 400, 295
        self.setFixedSize(w, h)
        self.setWindowFlags(
            Qt.Dialog | Qt.WindowTitleHint | Qt.WindowCloseButtonHint
        )

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(24, 18, 24, 18)

        title = QLabel(tr("🔒 KASP Giriş"))
        title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        self._status_label = QLabel("")
        self._status_label.setAlignment(Qt.AlignCenter)
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

        self._username_edit = QLineEdit()
        self._username_edit.setPlaceholderText(tr("Kullanıcı Adı"))
        layout.addWidget(self._username_edit)

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

        forgot_layout = QHBoxLayout()
        forgot_layout.setAlignment(Qt.AlignCenter)
        self._forgot_btn = QPushButton(tr("❓ Şifremi Unuttum"))
        self._forgot_btn.setFlat(True)
        self._forgot_btn.setCursor(Qt.PointingHandCursor)
        self._forgot_btn.setStyleSheet(
            "QPushButton { border: none; color: #2563EB; font-size: 11px; text-decoration: underline; background: transparent; }"
            "QPushButton:hover { color: #1D4ED8; }"
        )
        self._forgot_btn.clicked.connect(self._open_password_recovery)
        forgot_layout.addWidget(self._forgot_btn)
        layout.addLayout(forgot_layout)

    def _open_password_recovery(self):
        from kasp.ui.password_recovery_dialog import PasswordRecoveryDialog
        curr_user = self._username_edit.text().strip()
        dialog = PasswordRecoveryDialog(self._user_manager, self, default_username=curr_user)
        if dialog.exec_() == QDialog.Accepted:
            if dialog.recovered_username:
                self._username_edit.setText(dialog.recovered_username)
            self._password_edit.clear()
            self._password_edit.setFocus()
            self._update_lockout_state()
            self._status_label.setText(tr("Şifreniz sıfırlandı. Lütfen yeni şifrenizle giriş yapın."))
            self._status_label.setStyleSheet("color: #15803D; font-weight: bold;")

    def _toggle_password_visibility(self, checked):
        self._password_edit.setEchoMode(
            QLineEdit.Normal if checked else QLineEdit.Password
        )

    def _try_login(self):
        locked, msg = check_lockout()
        if locked:
            self._update_lockout_state()
            return

        username = self._username_edit.text().strip()
        password = self._password_edit.text()

        if not username:
            self._status_label.setText(tr("Kullanıcı adı gerekli."))
            self._status_label.setStyleSheet("color: #c62828;")
            return

        user = self._user_manager.authenticate(username, password)
        if user is not None:
            record_attempt(success=True)
            self._authenticated_user = user
            self.accept()
        else:
            just_locked, lock_msg = record_attempt(success=False)
            self._password_edit.clear()
            self._password_edit.setFocus()
            if just_locked:
                self._was_locked = True
                self._update_lockout_state()
            else:
                remaining = get_lockout_remaining()
                self._status_label.setText(
                    tr(f"Hatalı kullanıcı adı veya şifre. (Kalan deneme: {remaining})")
                )
                self._status_label.setStyleSheet("color: #c62828;")

    def authenticated_user(self):
        return getattr(self, "_authenticated_user", None)

    def _update_lockout_state(self, is_initial=False):
        locked, msg = check_lockout()

        if self._lockout_timer:
            self._lockout_timer.stop()
            self._lockout_timer = None

        if locked:
            self._was_locked = True
            self._login_btn.setEnabled(False)
            self._username_edit.setEnabled(False)
            self._password_edit.setEnabled(False)
            self._status_label.setText(f"⏳ {msg}")
            self._status_label.setStyleSheet("color: #c62828; font-weight: bold;")
            self._lockout_timer = QTimer(self)
            self._lockout_timer.timeout.connect(self._on_lockout_tick)
            self._lockout_timer.start(self._LOCKOUT_TIMER_INTERVAL)
        else:
            self._login_btn.setEnabled(True)
            self._username_edit.setEnabled(True)
            self._password_edit.setEnabled(True)
            self._password_edit.setFocus()

            if self._was_locked:
                self._was_locked = False
                remaining = get_lockout_remaining()
                self._status_label.setText(
                    tr(f"Kilit açıldı. Lütfen şifrenizi girin. (Kalan deneme: {remaining})")
                )
                self._status_label.setStyleSheet("color: #15803D; font-weight: bold;")
            elif not is_initial:
                remaining = get_lockout_remaining()
                self._status_label.setText(tr(f"Kalan deneme: {remaining}"))
                self._status_label.setStyleSheet("color: #b25300;")
            else:
                self._status_label.setText("")

    def _on_lockout_tick(self):
        self._remaining_lockout = get_lockout_remaining()
        locked, msg = check_lockout()
        if not locked:
            self._update_lockout_state()
        else:
            self._status_label.setText(f"⏳ {msg}")
            self._status_label.setStyleSheet("color: #c62828; font-weight: bold;")

    def reject(self):
        if self._lockout_timer:
            self._lockout_timer.stop()
        super().reject()
