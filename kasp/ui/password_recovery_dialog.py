"""KASP Password Recovery Dialog — Şifre Kurtarma ve Sıfırlama Penceresi."""

import logging
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from kasp.i18n import tr
from kasp.security import normalize_recovery_key, normalize_security_answer

logger = logging.getLogger(__name__)


class PasswordRecoveryDialog(QDialog):
    """Kullanıcının güvenlik sorusu veya kurtarma anahtarı ile şifresini sıfırlama penceresi."""

    def __init__(self, user_manager, parent=None, default_username=""):
        super().__init__(parent)
        self._user_manager = user_manager
        self.recovered_username = ""
        self._setup_ui()
        if default_username:
            self._username_edit.setText(default_username)
            self._fetch_user_info()

    def _setup_ui(self):
        self.setWindowTitle(tr("🔑 KASP — Şifre Kurtarma"))
        try:
            from kasp.ui.responsive import scaled
            w, h = scaled(440), scaled(470)
        except Exception:
            w, h = 440, 470
        self.setFixedSize(w, h)
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.WindowCloseButtonHint)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 16, 20, 16)

        # Başlık
        title = QLabel(tr("🛡️ Şifre Kurtarma Sihirbazı"))
        title.setFont(QFont("Segoe UI", 13, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel(tr("Hesabınızı güvenlik sorusu veya kurtarma anahtarı ile sıfırlayabilirsiniz."))
        subtitle.setWordWrap(True)
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(subtitle)

        # Kullanıcı Adı Girişi
        user_box = QGroupBox(tr("1. Kullanıcı Bilgisi"))
        user_layout = QHBoxLayout(user_box)
        user_layout.setContentsMargins(10, 8, 10, 8)
        self._username_edit = QLineEdit()
        self._username_edit.setPlaceholderText(tr("Kullanıcı Adı"))
        self._username_edit.returnPressed.connect(self._fetch_user_info)
        user_layout.addWidget(self._username_edit)

        fetch_btn = QPushButton(tr("Sorgula"))
        fetch_btn.clicked.connect(self._fetch_user_info)
        user_layout.addWidget(fetch_btn)
        layout.addWidget(user_box)

        # Yöntem Seçimi
        method_box = QGroupBox(tr("2. Kurtarma Yöntemi"))
        method_layout = QHBoxLayout(method_box)
        method_layout.setContentsMargins(10, 6, 10, 6)

        self._rb_question = QRadioButton(tr("Güvenlik Sorusu"))
        self._rb_key = QRadioButton(tr("Kurtarma Anahtarı"))
        self._rb_question.setChecked(True)

        btn_group = QButtonGroup(self)
        btn_group.addButton(self._rb_question, 0)
        btn_group.addButton(self._rb_key, 1)
        btn_group.buttonClicked.connect(self._on_method_changed)

        method_layout.addWidget(self._rb_question)
        method_layout.addWidget(self._rb_key)
        layout.addWidget(method_box)

        # Stacked Widget (Soru veya Anahtar Formu)
        self._stack = QStackedWidget()

        # Sayfa 0: Güvenlik Sorusu
        page_q = QWidget()
        layout_q = QVBoxLayout(page_q)
        layout_q.setContentsMargins(0, 4, 0, 4)
        layout_q.setSpacing(6)

        self._question_label = QLabel(tr("Tanımlı soru bulunamadı."))
        self._question_label.setWordWrap(True)
        self._question_label.setStyleSheet(
            "padding: 8px; background: rgba(0,0,0,0.04); border-radius: 4px; font-weight: 500;"
        )
        layout_q.addWidget(self._question_label)

        self._answer_edit = QLineEdit()
        self._answer_edit.setPlaceholderText(tr("Güvenlik Sorusu Yanıtınız"))
        layout_q.addWidget(self._answer_edit)
        self._stack.addWidget(page_q)

        # Sayfa 1: Kurtarma Anahtarı
        page_k = QWidget()
        layout_k = QVBoxLayout(page_k)
        layout_k.setContentsMargins(0, 4, 0, 4)
        layout_k.setSpacing(6)

        key_info = QLabel(tr("16 haneli acil kurtarma anahtarınızı giriniz:"))
        key_info.setStyleSheet("font-size: 11px; color: #555;")
        layout_k.addWidget(key_info)

        self._key_edit = QLineEdit()
        self._key_edit.setPlaceholderText("KASP-XXXX-XXXX-XXXX")
        layout_k.addWidget(self._key_edit)
        self._stack.addWidget(page_k)

        layout.addWidget(self._stack)

        # 3. Yeni Şifre Belirleme
        pw_box = QGroupBox(tr("3. Yeni Şifre"))
        pw_layout = QVBoxLayout(pw_box)
        pw_layout.setContentsMargins(10, 8, 10, 8)
        pw_layout.setSpacing(6)

        self._new_pw_edit = QLineEdit()
        self._new_pw_edit.setEchoMode(QLineEdit.Password)
        self._new_pw_edit.setPlaceholderText(tr("Yeni Şifre (En az 8 karakter, büyük-küçük harf ve rakam)"))
        pw_layout.addWidget(self._new_pw_edit)

        self._confirm_pw_edit = QLineEdit()
        self._confirm_pw_edit.setEchoMode(QLineEdit.Password)
        self._confirm_pw_edit.setPlaceholderText(tr("Yeni Şifre Tekrar"))
        self._confirm_pw_edit.returnPressed.connect(self._do_reset)
        pw_layout.addWidget(self._confirm_pw_edit)

        self._show_pw_cb = QCheckBox(tr("👁️ Şifreyi Göster"))
        self._show_pw_cb.toggled.connect(self._toggle_pw_visibility)
        pw_layout.addWidget(self._show_pw_cb)
        layout.addWidget(pw_box)

        # Durum ve Hata Bildirimi
        self._status_label = QLabel("")
        self._status_label.setWordWrap(True)
        self._status_label.setAlignment(Qt.AlignCenter)
        self._status_label.setStyleSheet("font-size: 11px;")
        layout.addWidget(self._status_label)

        # Butonlar
        btn_layout = QHBoxLayout()
        self._reset_btn = QPushButton(tr("Şifreyi Sıfırla"))
        self._reset_btn.setDefault(True)
        self._reset_btn.clicked.connect(self._do_reset)
        btn_layout.addWidget(self._reset_btn)

        cancel_btn = QPushButton(tr("İptal"))
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def _toggle_pw_visibility(self, checked):
        mode = QLineEdit.Normal if checked else QLineEdit.Password
        self._new_pw_edit.setEchoMode(mode)
        self._confirm_pw_edit.setEchoMode(mode)

    def _on_method_changed(self):
        idx = 0 if self._rb_question.isChecked() else 1
        self._stack.setCurrentIndex(idx)

    def _fetch_user_info(self):
        username = self._username_edit.text().strip()
        if not username:
            self._set_status(tr("Lütfen bir kullanıcı adı giriniz."), is_error=True)
            return

        user_dict = self._user_manager.db.get_user_by_username(username)
        if not user_dict:
            self._set_status(tr("Kullanıcı bulunamadı."), is_error=True)
            self._question_label.setText(tr("Kullanıcı bulunamadı."))
            return

        q, err = self._user_manager.get_security_question(username)
        if q:
            self._question_label.setText(f"❓ {q}")
            self._question_label.setStyleSheet(
                "padding: 8px; background: rgba(30, 144, 255, 0.08); border-radius: 4px; font-weight: bold; color: #1E40AF;"
            )
            self._rb_question.setChecked(True)
            self._stack.setCurrentIndex(0)
            self._set_status(tr("Güvenlik sorusu getirildi. Yanıtınızı ve yeni şifrenizi giriniz."), is_error=False)
            self._answer_edit.setFocus()
        else:
            is_admin = user_dict.get("role") == "admin"
            if is_admin:
                self._question_label.setText(
                    tr("Admin hesabı için güvenlik sorusu ayarlanmamış.\n"
                       "Kurtarma Anahtarınızı kullanabilir veya komut satırından 'python main.py --reset-admin' çalıştırabilirsiniz.")
                )
                self._rb_key.setChecked(True)
                self._stack.setCurrentIndex(1)
                self._set_status(tr("Lütfen Kurtarma Anahtarınızı giriniz."), is_error=False)
                self._key_edit.setFocus()
            else:
                self._question_label.setText(
                    tr("Bu kullanıcı için güvenlik sorusu tanımlanmamış.\n"
                       "Lütfen Sistem Yöneticinize (Admin) başvurarak şifrenizi sıfırlatınız.")
                )
                self._set_status(
                    tr("Sistem Yöneticinize başvurunuz. (Admin kullanıcıları Şifre Sıfırlama yetkisine sahiptir)"),
                    is_error=True,
                )

    def _set_status(self, text: str, is_error: bool = False):
        self._status_label.setText(text)
        color = "#DC2626" if is_error else "#16A34A"
        self._status_label.setStyleSheet(f"color: {color}; font-weight: 500; font-size: 11px;")

    def _do_reset(self):
        username = self._username_edit.text().strip()
        new_pw = self._new_pw_edit.text()
        confirm_pw = self._confirm_pw_edit.text()

        if not username:
            self._set_status(tr("Kullanıcı adı boş bırakılamaz."), is_error=True)
            return

        if not new_pw or not confirm_pw:
            self._set_status(tr("Yeni şifre ve tekrarı zorunludur."), is_error=True)
            return

        if new_pw != confirm_pw:
            self._set_status(tr("Yeni şifre ve tekrarı eşleşmiyor."), is_error=True)
            return

        if self._rb_question.isChecked():
            answer = self._answer_edit.text().strip()
            if not answer:
                self._set_status(tr("Lütfen güvenlik sorusu yanıtını giriniz."), is_error=True)
                return
            ok, err = self._user_manager.verify_security_question_and_reset(username, answer, new_pw)
        else:
            key = self._key_edit.text().strip()
            if not key:
                self._set_status(tr("Lütfen kurtarma anahtarını giriniz."), is_error=True)
                return
            ok, err = self._user_manager.verify_recovery_key_and_reset(username, key, new_pw)

        if ok:
            self.recovered_username = username
            QMessageBox.information(
                self,
                tr("Başarılı"),
                tr("Şifreniz başarıyla sıfırlandı!\nYeni şifrenizle giriş yapabilirsiniz."),
            )
            self.accept()
        else:
            self._set_status(err or tr("Şifre sıfırlanamadı."), is_error=True)
