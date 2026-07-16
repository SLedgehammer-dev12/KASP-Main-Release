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
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from kasp.security import (
    LOCKOUT_LEVELS,
    check_lockout,
    get_lockout_remaining,
    generate_initial_admin_password,
    hash_password,
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
        self._setup_ui()
        self._update_lockout_state()

    def _setup_ui(self):
        self.setWindowTitle(tr("KASP — Giriş"))
        try:
            from kasp.ui.responsive import scaled
            w, h = scaled(400), scaled(260)
        except Exception:
            w, h = 400, 260
        self.setMinimumSize(int(w * 0.7), int(h * 0.7))
        self.resize(w, h)
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

        forgot_btn = QPushButton(tr("Şifremi Unuttum"))
        forgot_btn.clicked.connect(self._forgot_password)
        btn_layout.addWidget(forgot_btn)

        cancel_btn = QPushButton(tr("Çıkış"))
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def _forgot_password(self):
        username = self._username_edit.text().strip().lower()
        if username != "admin":
            QMessageBox.warning(
                self, tr("Bilgi"),
                tr("Sadece admin kullanicisi icin sifre sifirlama yapilabilir.\n"
                   "Admin sifrenizi unuttuysaniz kullanici adi olarak 'admin' yazip tekrar deneyin.")
            )
            return

        db = self._user_manager.db
        admin_user = db.get_user_by_username("admin")
        if not admin_user:
            QMessageBox.critical(self, tr("Hata"), tr("Admin kullanicisi bulunamadi."))
            return

        admin_id = admin_user.get("id")
        if not admin_id:
            QMessageBox.critical(self, tr("Hata"), tr("Admin kullanici ID'si alinamadi."))
            return

        reply = QMessageBox.question(
            self, tr("Admin Sifre Sifirlama"),
            tr("Admin sifresi sifirlanacak ve yeni bir gecici sifre olusturulacak.\n\n"
               "Devam etmek istiyor musunuz?"),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if reply != QMessageBox.Yes:
            return

        new_password = generate_initial_admin_password()
        new_hash = hash_password(new_password)

        ok = db.update_user(admin_id, password_hash=new_hash,
                            must_change_password=1, is_active=1)
        if not ok:
            QMessageBox.critical(
                self, tr("Hata"),
                tr(f"Sifre guncellenemedi. Veritabani hatasi olabilir.\n"
                   f"Admin ID: {admin_id}")
            )
            return

        verified = self._user_manager.authenticate("admin", new_password)
        if verified is None:
            QMessageBox.critical(
                self, tr("Hata"),
                tr("Sifre olusturuldu ancak dogrulama basarisiz.\n"
                   "Lutfen programi yeniden baslatin.")
            )
            return

        self._password_edit.setText(new_password)
        self._password_edit.setFocus()
        QMessageBox.information(
            self, tr("Yeni Sifre"),
            tr(f"Admin sifresi sifirlandi.\n\n"
               f"Gecici sifre: {new_password}\n\n"
               f"Bu sifre sifre alanina otomatik yerlestirildi.\n"
               f"Giris Yap butonuna tiklayarak giris yapabilirsiniz.")
        )

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
            record_attempt(success=False)
            self._password_edit.clear()
            self._password_edit.setFocus()
            self._status_label.setText(tr("Hatalı kullanıcı adı veya şifre."))
            self._status_label.setStyleSheet("color: #c62828;")
            self._update_lockout_state()

    def authenticated_user(self):
        return getattr(self, "_authenticated_user", None)

    def _update_lockout_state(self):
        locked, msg = check_lockout()

        if self._lockout_timer:
            self._lockout_timer.stop()
            self._lockout_timer = None

        if locked:
            self._login_btn.setEnabled(False)
            self._username_edit.setEnabled(False)
            self._password_edit.setEnabled(False)
            self._status_label.setText(f"⏳ {msg}")
            self._status_label.setStyleSheet("color: #c62828;")
            self._lockout_timer = QTimer(self)
            self._lockout_timer.timeout.connect(self._on_lockout_tick)
            self._lockout_timer.start(self._LOCKOUT_TIMER_INTERVAL)
        else:
            self._login_btn.setEnabled(True)
            self._username_edit.setEnabled(True)
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
            if self._lockout_timer:
                self._lockout_timer.stop()
                self._lockout_timer = None
            self._login_btn.setEnabled(True)
            self._username_edit.setEnabled(True)
            self._password_edit.setEnabled(True)
            self._status_label.setText("")
            self._password_edit.setFocus()
        else:
            self._status_label.setText(f"Kilitli: {msg}")

    def reject(self):
        if self._lockout_timer:
            self._lockout_timer.stop()
        super().reject()


def _find_lockout_level(remaining_attempts):
    for limit, _ in LOCKOUT_LEVELS:
        if remaining_attempts < limit:
            return max(1, limit - remaining_attempts)
    return max(1, LOCKOUT_LEVELS[-1][0] - remaining_attempts + 1)
